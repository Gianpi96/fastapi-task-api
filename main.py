from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import engine, Base, get_db
from models.tasks import Task as TaskModel
from models.user import User as UserModel  # 🔥 serve per creare tabella

from pydantic import BaseModel, Field, field_validator, ConfigDict
from utils.security import hash_password

from fastapi.security import OAuth2PasswordRequestForm
from utils.security import verify_password, create_access_token

app = FastAPI()

# 🔥 IMPORTANTE: crea tabelle DOPO aver importato i modelli
Base.metadata.create_all(bind=engine)


# 🔥 Root endpoint
@app.get("/")
def read_root():
    return {"message": "hello world"}


# 🔥 Health check
@app.get("/health")
def health_check():
    return {"status": "ok"}


# -----------------------
# TASK SCHEMA
# -----------------------
class Task(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )

    id: int
    title: str = Field(..., min_length=3)
    description: Optional[str] = None
    completed: bool = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if value.isdigit():
            raise ValueError("Il titolo non può contenere solo numeri")
        return value.capitalize()


# -----------------------
# GET /tasks
# -----------------------
@app.get("/tasks", response_model=List[Task])
def get_tasks(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    completed: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
):
    query = db.query(TaskModel)

    if completed is not None:
        query = query.filter(TaskModel.completed == completed)

    if search is not None:
        query = query.filter(TaskModel.title.ilike(f"%{search}%"))

    return query.offset(skip).limit(limit).all()


# -----------------------
# GET /tasks/{id}
# -----------------------
@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")

    return task


# -----------------------
# POST /tasks
# -----------------------
@app.post("/tasks", response_model=Task, status_code=201)
def create_task(task: Task, db: Session = Depends(get_db)):
    db_task = TaskModel(**task.model_dump())

    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return db_task


# -----------------------
# PUT /tasks/{id}
# -----------------------
@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, updated_task: Task, db: Session = Depends(get_db)):
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")

    task.title = updated_task.title
    task.description = updated_task.description
    task.completed = updated_task.completed

    db.commit()
    db.refresh(task)

    return task


# -----------------------
# DELETE /tasks/{id}
# -----------------------
@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")

    db.delete(task)
    db.commit()

    return {"message": "Task eliminato"}


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
# POST /auth/register
# -----------------------
@app.post("/auth/register", response_model=UserResponse, status_code=201)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # Controllo duplicati
    existing_user = (
        db.query(UserModel)
        .filter((UserModel.username == user.username) | (UserModel.email == user.email))
        .first()
    )

    if existing_user:
        raise HTTPException(status_code=400, detail="Username o email già registrati")

    # Hash password
    hashed_pwd = hash_password(user.password)

    # Crea utente
    db_user = UserModel(
        username=user.username,
        email=user.email,
        hashed_password=hashed_pwd,
        is_active=True,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@app.post("/auth/token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    # Cerca utente nel DB
    user = db.query(UserModel).filter(UserModel.username == form_data.username).first()

    # Verifica credenziali
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    # Crea JWT
    access_token = create_access_token(data={"sub": user.username})

    return {"access_token": access_token, "token_type": "bearer"}
