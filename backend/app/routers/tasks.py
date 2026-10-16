from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import TaskStatus
from ..database import get_db
from ..models import TaskModel
from ..schemas import TaskCreate, TaskRead, TaskUpdate
from ..services import events

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# Campos que no admiten null: un null explícito en el PATCH se ignora.
NON_NULLABLE = {"title", "status", "priority"}
# Campos que solo rellenan las automatizaciones: cambiarlos no genera eventos
# (evita que n8n se dispare a sí mismo al guardar el id del evento de Calendar).
INTERNAL_FIELDS = {"external_event_id", "reminded_at"}


def _sync_completed_at(task: TaskModel) -> None:
    """Mantiene la regla de la BD: una tarea está hecha si y solo si tiene completed_at."""
    if task.status == TaskStatus.DONE and task.completed_at is None:
        task.completed_at = datetime.now(timezone.utc)
    elif task.status != TaskStatus.DONE:
        task.completed_at = None


def _get_or_404(db: Session, task_id: int) -> TaskModel:
    task = db.get(TaskModel, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return task


@router.get("", response_model=list[TaskRead])
def list_tasks(
    status: TaskStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[TaskModel]:
    query = select(TaskModel).order_by(TaskModel.id.desc()).limit(limit).offset(offset)
    if status:
        query = query.where(TaskModel.status == status.value)
    return list(db.scalars(query))


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, db: Session = Depends(get_db)) -> TaskModel:
    return _get_or_404(db, task_id)


@router.post("", response_model=TaskRead, status_code=201)
def create_task(
    payload: TaskCreate, background: BackgroundTasks, db: Session = Depends(get_db)
) -> TaskModel:
    task = TaskModel(**payload.model_dump())
    _sync_completed_at(task)
    db.add(task)
    db.commit()
    db.refresh(task)
    background.add_task(events.emit, "task.created", {"task_id": task.id})
    return task


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> TaskModel:
    task = _get_or_404(db, task_id)

    requested = {
        field: value
        for field, value in payload.model_dump(exclude_unset=True).items()
        if not (value is None and field in NON_NULLABLE)
    }
    changed = {field: value for field, value in requested.items() if getattr(task, field) != value}
    if not changed:
        return task  # nada que guardar ni que notificar

    was_done = task.status == TaskStatus.DONE
    for field, value in changed.items():
        setattr(task, field, value)
    _sync_completed_at(task)
    db.commit()
    db.refresh(task)

    # Completar emite solo task.completed; el resto de cambios, task.updated.
    if task.status == TaskStatus.DONE and not was_done:
        background.add_task(events.emit, "task.completed", {"task_id": task.id})
    elif set(changed) - INTERNAL_FIELDS:
        data = {"task_id": task.id, "changed": sorted(changed)}
        background.add_task(events.emit, "task.updated", data)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, background: BackgroundTasks, db: Session = Depends(get_db)) -> None:
    task = _get_or_404(db, task_id)
    # Se captura antes de borrar: n8n lo necesita para eliminar el evento externo.
    data = {"task_id": task.id, "external_event_id": task.external_event_id}
    db.delete(task)
    db.commit()
    background.add_task(events.emit, "task.deleted", data)
