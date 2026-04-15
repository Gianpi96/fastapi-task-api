from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import engine, Base, get_db
from models.tasks import Task as TaskModel
from pydantic import BaseModel, Field, field_validator, ConfigDict

app = FastAPI()


# 🔥 Root endpoint
@app.get("/")
def read_root():
    return {"message": "hello world"}


# 🔥 Health check
@app.get("/health")
def health_check():
    return {"status": "ok"}


Base.metadata.create_all(bind=engine)


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


@app.get("/tasks", response_model=List[Task])
def get_tasks(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    completed: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
):
    print(f">>> skip={skip} limit={limit} completed={completed} search={search}")
    query = db.query(TaskModel)

    if completed is not None:
        query = query.filter(TaskModel.completed == completed)

    if search is not None:
        query = query.filter(TaskModel.title.ilike(f"%{search}%"))

    return query.offset(skip).limit(limit).all()


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")
    return task


@app.post("/tasks", response_model=Task, status_code=201)
def create_task(task: Task, db: Session = Depends(get_db)):
    db_task = TaskModel(**task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


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


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")

    db.delete(task)
    db.commit()

    return {"message": "Task eliminato"}
