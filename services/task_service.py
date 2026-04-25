from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException

from models.tasks import Task as TaskModel
from schemas.task import TaskCreate


def get_tasks(
    db: Session,
    owner_id: int,
    skip: int = 0,
    limit: int = 10,
    completed: Optional[bool] = None,
    search: Optional[str] = None,
) -> list[TaskModel]:
    query = db.query(TaskModel).filter(TaskModel.owner_id == owner_id)

    if completed is not None:
        query = query.filter(TaskModel.completed == completed)

    if search is not None:
        query = query.filter(TaskModel.title.ilike(f"%{search}%"))

    return query.offset(skip).limit(limit).all()


def get_task(db: Session, task_id: int, owner_id: int) -> TaskModel:
    task = (
        db.query(TaskModel)
        .filter(TaskModel.id == task_id, TaskModel.owner_id == owner_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")
    return task


def create_task(db: Session, task_data: TaskCreate, owner_id: int) -> TaskModel:
    db_task = TaskModel(**task_data.model_dump(), owner_id=owner_id)
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


def update_task(
    db: Session, task_id: int, task_data: TaskCreate, owner_id: int
) -> TaskModel:
    task = get_task(db, task_id, owner_id)

    task.title = task_data.title
    task.description = task_data.description
    task.completed = task_data.completed

    try:
        db.commit()
        db.refresh(task)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Errore durante l'aggiornamento del task"
        )
    return task


def delete_task(db: Session, task_id: int, owner_id: int) -> None:
    task = get_task(db, task_id, owner_id)
    try:
        db.delete(task)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Errore durante l'eliminazione del task"
        )
