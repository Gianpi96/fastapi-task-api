import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.tasks import router as tasks_router
from auth.security import (
    create_access_token,
    get_dummy_hash,
    hash_password,
    verify_password,
)
from config.settings import settings
from database import Base, engine, get_db
from models.user import User as UserModel
from models.tasks import Task as TaskModel  # noqa: F401 — registra la tabella
from schemas.user import UserCreate, UserResponse

# -----------------------
# APP SETUP
# -----------------------
app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

Base.metadata.create_all(bind=engine)

# Registra i router
app.include_router(tasks_router)


# -----------------------
# HEALTH
# -----------------------
@app.get("/")
def read_root():
    return {"message": "hello world"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/debug/settings")
def debug_settings():
    if settings.ENV != "development":
        raise HTTPException(status_code=404)
    return {
        "algorithm": "HS256",
        "expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "secret_key_set": bool(settings.SECRET_KEY),
        "secret_key_length": len(settings.SECRET_KEY),
    }


# -----------------------
# AUTH
# -----------------------
@app.post("/auth/register", response_model=UserResponse, status_code=201)
@limiter.limit("3/minute")
def register_user(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(UserModel)
        .filter((UserModel.username == user.username) | (UserModel.email == user.email))
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Username o email già registrati")

    db_user = UserModel(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
        is_active=True,
    )
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Errore durante la registrazione")

    return db_user


@app.post("/auth/token")
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(UserModel).filter(UserModel.username == form_data.username).first()

    candidate_hash = user.hashed_password if user else get_dummy_hash()
    password_ok = verify_password(form_data.password, candidate_hash)

    if not user or not password_ok:
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    return {
        "access_token": create_access_token(data={"sub": user.username}),
        "token_type": "bearer",
    }
