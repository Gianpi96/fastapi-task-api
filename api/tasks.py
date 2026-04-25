from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models.user import User as UserModel
from schemas.task import TaskCreate, TaskResponse
from services import task_service
from api.deps import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=List[TaskResponse])
def get_tasks(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    completed: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    return task_service.get_tasks(
        db=db,
        owner_id=current_user.id,
        skip=skip,
        limit=limit,
        completed=completed,
        search=search,
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    return task_service.get_task(db=db, task_id=task_id, owner_id=current_user.id)


@router.post("", response_model=TaskResponse, status_code=201)
def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    return task_service.create_task(db=db, task_data=task, owner_id=current_user.id)


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    updated_task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    return task_service.update_task(
        db=db,
        task_id=task_id,
        task_data=updated_task,
        owner_id=current_user.id,
    )


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    task_service.delete_task(db=db, task_id=task_id, owner_id=current_user.id)
    return {"message": "Task eliminato"}
