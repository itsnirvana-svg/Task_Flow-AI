"""Reglas de negocio de las tareas.

Las rutas HTTP solo traducen peticiones y respuestas; todo lo demás (estado, `completed_at`,
eventos hacia n8n) vive aquí, para reutilizarlo desde cualquier otro punto de entrada
(automatizaciones, scripts, una futura CLI).
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import TaskStatus
from ..models import TaskModel
from ..schemas import TaskCreate, TaskUpdate
from . import events

# Campos que no admiten null: un null explícito en el PATCH se ignora.
NON_NULLABLE = {"title", "status", "priority"}
# Campos que solo rellenan las automatizaciones: cambiarlos no genera eventos
# (evita que n8n se dispare a sí mismo al guardar el id del evento de Calendar).
INTERNAL_FIELDS = {"external_event_id", "reminded_at"}


class TaskNotFoundError(LookupError):
    """La tarea pedida no existe."""


def _sync_completed_at(task: TaskModel) -> None:
    """Mantiene la regla de la BD: una tarea está hecha si y solo si tiene completed_at."""
    if task.status == TaskStatus.DONE and task.completed_at is None:
        task.completed_at = datetime.now(timezone.utc)
    elif task.status != TaskStatus.DONE:
        task.completed_at = None


def get_task(db: Session, task_id: int) -> TaskModel:
    task = db.get(TaskModel, task_id)
    if task is None:
        raise TaskNotFoundError(task_id)
    return task


def list_tasks(
    db: Session, status: TaskStatus | None, limit: int, offset: int
) -> list[TaskModel]:
    query = select(TaskModel).order_by(TaskModel.id.desc()).limit(limit).offset(offset)
    if status:
        query = query.where(TaskModel.status == status.value)
    return list(db.scalars(query))


def create_task(db: Session, payload: TaskCreate) -> TaskModel:
    task = TaskModel(**payload.model_dump())
    _sync_completed_at(task)
    db.add(task)
    db.commit()
    db.refresh(task)
    events.publish("task.created", {"task_id": task.id})
    return task


def update_task(db: Session, task_id: int, payload: TaskUpdate) -> TaskModel:
    task = get_task(db, task_id)

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
        events.publish("task.completed", {"task_id": task.id})
    elif set(changed) - INTERNAL_FIELDS:
        events.publish("task.updated", {"task_id": task.id, "changed": sorted(changed)})
    return task


def delete_task(db: Session, task_id: int) -> None:
    task = get_task(db, task_id)
    # Se captura antes de borrar: n8n lo necesita para eliminar el evento externo.
    data = {"task_id": task.id, "external_event_id": task.external_event_id}
    db.delete(task)
    db.commit()
    events.publish("task.deleted", data)
