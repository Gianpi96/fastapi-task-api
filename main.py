from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from database import engine, Base, get_db
from models.tasks import Task as TaskModel
from models.user import User as UserModel
from utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
)




# -----------------------
# APP & DB SETUP
# -----------------------
app = FastAPI()
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


# -----------------------
# USER SCHEMAS
# -----------------------
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3)
    email: str
    password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    is_active: bool


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


# -----------------------
# AUTH ENDPOINTS
# -----------------------
@app.post("/auth/register", response_model=UserResponse, status_code=201)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
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

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@app.post("/auth/token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(UserModel).filter(UserModel.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
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
    query = db.query(TaskModel)

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
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")

    return task


@app.post("/tasks", response_model=Task, status_code=201)
def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    db_task = TaskModel(**task.model_dump())

    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return db_task


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(
    task_id: int,
    updated_task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")

    task.title = updated_task.title
    task.description = updated_task.description
    task.completed = updated_task.completed

    db.commit()
    db.refresh(task)

    return task


@app.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")

    db.delete(task)
    db.commit()

    return {"message": "Task eliminato"}
