from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models.user import User as UserModel
from schemas.task import TaskCreate, TaskResponse
from services import task_service
from services.notification_service import send_task_created_email
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
    background_tasks: BackgroundTasks,  # ← iniettato da FastAPI
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    # 1. Salva il task nel DB — operazione sincrona
    db_task = task_service.create_task(db=db, task_data=task, owner_id=current_user.id)

    # 2. Schedula l'email in background — il client NON aspetta
    background_tasks.add_task(
        send_task_created_email,
        recipient_email=current_user.email,
        username=current_user.username,
        task_title=db_task.title,
        task_id=db_task.id,
    )

    # 3. Risposta 201 immediata — l'email parte dopo
    return db_task


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
