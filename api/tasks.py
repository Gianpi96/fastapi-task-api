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


@router.get(
    "",
    response_model=List[TaskResponse],
    summary="Lista task con filtri e paginazione",
    description="""
Restituisce i task dell'utente autenticato con supporto a:

- **Paginazione**: `skip` (offset) e `limit` (max risultati)
- **Filtro stato**: `completed=true` o `completed=false`
- **Ricerca**: `search=parola` cerca nel titolo (case insensitive)

**Esempi:**
- `GET /tasks` → tutti i task (max 10)
- `GET /tasks?limit=5&skip=10` → pagina 3 con 5 elementi
- `GET /tasks?completed=false` → solo task non completati
- `GET /tasks?search=latte` → task con "latte" nel titolo
- `GET /tasks?completed=false&search=spesa` → filtri combinati
    """,
    responses={
        200: {"description": "Lista task restituita con successo"},
        401: {"description": "Token mancante o non valido"},
    },
)
def get_tasks(
    skip: int = Query(
        default=0,
        ge=0,
        description="Numero di task da saltare (offset per la paginazione)",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Numero massimo di task da restituire (max 100)",
    ),
    completed: Optional[bool] = Query(
        default=None,
        description="Filtra per stato: `true` = completati, `false` = da fare, ometti = tutti",
    ),
    search: Optional[str] = Query(
        default=None,
        min_length=1,
        description="Cerca nel titolo del task (case insensitive)",
    ),
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


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Dettaglio di un task",
    responses={
        200: {"description": "Task trovato"},
        401: {"description": "Token mancante o non valido"},
        404: {"description": "Task non trovato o non appartiene all'utente"},
    },
)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    return task_service.get_task(db=db, task_id=task_id, owner_id=current_user.id)


@router.post(
    "",
    response_model=TaskResponse,
    status_code=201,
    summary="Crea un nuovo task",
    description="""
Crea un nuovo task per l'utente autenticato.

Dopo la creazione viene inviata una **notifica email in background** — 
la risposta al client è immediata, l'email parte in modo asincrono.

**Validazioni:**
- `title`: minimo 3 caratteri, non può essere solo numeri
- `description`: opzionale
- `completed`: default `false`
    """,
    responses={
        201: {"description": "Task creato con successo"},
        401: {"description": "Token mancante o non valido"},
        422: {"description": "Dati non validi"},
    },
)
def create_task(
    task: TaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    db_task = task_service.create_task(db=db, task_data=task, owner_id=current_user.id)

    background_tasks.add_task(
        send_task_created_email,
        recipient_email=current_user.email,
        username=current_user.username,
        task_title=db_task.title,
        task_id=db_task.id,
    )

    return db_task


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Aggiorna un task esistente",
    responses={
        200: {"description": "Task aggiornato"},
        401: {"description": "Token mancante o non valido"},
        404: {"description": "Task non trovato"},
        422: {"description": "Dati non validi"},
    },
)
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


@router.delete(
    "/{task_id}",
    summary="Elimina un task",
    responses={
        200: {"description": "Task eliminato"},
        401: {"description": "Token mancante o non valido"},
        404: {"description": "Task non trovato"},
    },
)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    task_service.delete_task(db=db, task_id=task_id, owner_id=current_user.id)
    return {"message": "Task eliminato"}
