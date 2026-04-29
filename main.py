import logging
import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.exception_handlers import register_exception_handlers
from api.tasks import router as tasks_router
from auth.security import (
    create_access_token,
    get_dummy_hash,
    hash_password,
    verify_password,
)
from config.settings import settings
from database import Base, engine, get_db
from models.tasks import Task as TaskModel  # noqa: F401 — registra la tabella
from models.user import User as UserModel
from schemas.token import TokenResponse
from schemas.user import UserCreate, UserResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger(__name__)

# -----------------------
# APP SETUP
# -----------------------
app = FastAPI(
    title="Task Manager API",
    description="API per la gestione dei task con autenticazione JWT",
    version="1.0.0",
)

# Exception handlers personalizzati — registrati PRIMA dei middleware
register_exception_handlers(app)

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

app.include_router(tasks_router)


# -----------------------
# HEALTH
# -----------------------
@app.get("/", tags=["health"])
def read_root() -> dict:
    return {"message": "hello world"}


@app.get("/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/debug/settings", tags=["debug"])
def debug_settings() -> dict:
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
@app.post(
    "/auth/register",
    response_model=UserResponse,  # esclude hashed_password, password, e qualsiasi
    status_code=201,  # campo non dichiarato in UserResponse
    tags=["auth"],
    summary="Registra un nuovo utente",
    responses={
        201: {"description": "Utente creato con successo"},
        400: {"description": "Username o email già registrati"},
        422: {"description": "Dati non validi"},
    },
)
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
        logger.error("Errore DB durante registrazione utente: %s", user.username)
        raise HTTPException(status_code=500, detail="Errore durante la registrazione")

    logger.info("Nuovo utente registrato: %s", db_user.username)
    return db_user


@app.post(
    "/auth/token",
    response_model=TokenResponse,  # solo access_token e token_type — niente altro
    tags=["auth"],
    summary="Login — ottieni il token JWT",
    responses={
        200: {"description": "Login effettuato con successo"},
        401: {"description": "Credenziali non valide"},
    },
)
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

    logger.info("Login effettuato: %s", form_data.username)
    return TokenResponse(
        access_token=create_access_token(data={"sub": user.username}),
        token_type="bearer",
    )
