"""Rutas HTTP de las tareas (`/api/tasks`).

Capa fina: valida la petición y delega en `task_service`, donde están las reglas de negocio y el
registro de eventos. Los docstrings de cada ruta aparecen en la documentación interactiva (`/docs`).
"""

from typing import Annotated

from fastapi import APIRouter, Query

from ..constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, TaskStatus
from ..database import DbSession
from ..models import TaskModel
from ..schemas import TaskCreate, TaskRead, TaskUpdate
from ..services import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
def list_tasks(
    db: DbSession,
    status: TaskStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TaskModel]:
    """Lista las tareas, las más recientes primero. Admite filtro por estado y paginación."""
    return task_service.list_tasks(db, status, limit, offset)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, db: DbSession) -> TaskModel:
    """Devuelve una tarea; 404 si no existe. n8n la consulta para conocer su estado actual."""
    return task_service.get_task(db, task_id)


@router.post("", response_model=TaskRead, status_code=201)
def create_task(payload: TaskCreate, db: DbSession) -> TaskModel:
    """Crea una tarea y encola el evento `task.created` para n8n."""
    return task_service.create_task(db, payload)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate, db: DbSession) -> TaskModel:
    """Edita solo los campos enviados. Encola `task.completed` o `task.updated` si algo cambió."""
    return task_service.update_task(db, task_id, payload)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: DbSession) -> None:
    """Elimina la tarea y encola `task.deleted` (con el id del evento de Calendar, si lo tiene)."""
    task_service.delete_task(db, task_id)
