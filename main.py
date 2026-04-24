import os
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict

# FIX: rate limiting con slowapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import engine, Base, get_db
from models.tasks import Task as TaskModel
from models.user import User as UserModel
from auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    get_dummy_hash,
)
from config.settings import settings


# -----------------------
# APP SETUP
# -----------------------
app = FastAPI()

# FIX: rate limiter globale — chiave = IP remoto
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# FIX: CORS esplicito — mai allow_origins=["*"] con allow_credentials=True
# Aggiorna allow_origins con i domini reali del tuo frontend
_CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

Base.metadata.create_all(bind=engine)


# -----------------------
# TASK SCHEMAS
# -----------------------
class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=3)
    description: Optional[str] = None
    completed: bool = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if value.isdigit():
            raise ValueError("Il titolo non può contenere solo numeri")
        return value.capitalize()


class Task(TaskCreate):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    id: int
    owner_id: int


# -----------------------
# USER SCHEMAS
# -----------------------
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3)
    # FIX: EmailStr invece di str — valida formato email a livello Pydantic
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    is_active: bool
    # hashed_password NON è incluso — mai esporre nel response model


# -----------------------
# AUTH DEPENDENCY
# -----------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserModel:
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Token non valido o scaduto")

    username: str = payload.get("sub")

    if username is None:
        raise HTTPException(status_code=401, detail="Token non valido")

    user = db.query(UserModel).filter(UserModel.username == username).first()

    if user is None:
        raise HTTPException(status_code=401, detail="Utente non trovato")

    return user


# -----------------------
# ROOT & HEALTH
# -----------------------
@app.get("/")
def read_root():
    return {"message": "hello world"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


# FIX: /debug/settings protetto da env guard — non accessibile in produzione
# In produzione (ENV != "development") risponde 404, non rivela nulla
@app.get("/debug/settings")
def debug_settings():
    if settings.ENV != "development":
        raise HTTPException(status_code=404)
    return {
        "algorithm": "HS256",  # hardcoded — non da settings
        "expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "secret_key_set": bool(settings.SECRET_KEY),
        "secret_key_length": len(settings.SECRET_KEY),
    }


# -----------------------
# AUTH ENDPOINTS
# -----------------------
@app.post("/auth/register", response_model=UserResponse, status_code=201)
# FIX: rate limit 3 registrazioni/minuto per IP — previene registrazioni massive
@limiter.limit("3/minute")
def register_user(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    existing_user = (
        db.query(UserModel)
        .filter((UserModel.username == user.username) | (UserModel.email == user.email))
        .first()
    )

    if existing_user:
        raise HTTPException(status_code=400, detail="Username o email già registrati")

    db_user = UserModel(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
        is_active=True,
    )

    # FIX: SQLAlchemyError catturato esplicitamente — nessun traceback esposto al client
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Errore durante la registrazione")

    return db_user


@app.post("/auth/token")
# FIX: rate limit 5 tentativi/minuto per IP — blocca brute-force sulle credenziali
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(UserModel).filter(UserModel.username == form_data.username).first()

    # FIX: timing attack prevention — verify_password eseguito sempre,
    # anche se l'utente non esiste. Impedisce user enumeration via misura dei tempi.
    candidate_hash = user.hashed_password if user else get_dummy_hash()
    password_ok = verify_password(form_data.password, candidate_hash)

    # Controlla sia user che password DOPO aver fatto bcrypt in ogni caso
    if not user or not password_ok:
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    access_token = create_access_token(data={"sub": user.username})

    return {"access_token": access_token, "token_type": "bearer"}


# -----------------------
# TASK ENDPOINTS
# -----------------------
@app.get("/tasks", response_model=List[Task])
def get_tasks(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    completed: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    query = db.query(TaskModel).filter(TaskModel.owner_id == current_user.id)

    if completed is not None:
        query = query.filter(TaskModel.completed == completed)

    if search is not None:
        query = query.filter(TaskModel.title.ilike(f"%{search}%"))

    return query.offset(skip).limit(limit).all()


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    task = (
        db.query(TaskModel)
        .filter(TaskModel.id == task_id, TaskModel.owner_id == current_user.id)
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")

    return task


@app.post("/tasks", response_model=Task, status_code=201)
def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    db_task = TaskModel(**task.model_dump(), owner_id=current_user.id)

    try:
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Errore durante la creazione del task"
        )

    return db_task


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(
    task_id: int,
    updated_task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    task = (
        db.query(TaskModel)
        .filter(TaskModel.id == task_id, TaskModel.owner_id == current_user.id)
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")

    task.title = updated_task.title
    task.description = updated_task.description
    task.completed = updated_task.completed

    try:
        db.commit()
        db.refresh(task)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Errore durante l'aggiornamento del task"
        )

    return task


@app.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    task = (
        db.query(TaskModel)
        .filter(TaskModel.id == task_id, TaskModel.owner_id == current_user.id)
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")

    try:
        db.delete(task)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Errore durante l'eliminazione del task"
        )

    return {"message": "Task eliminato"}
