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
    return task_service.list_tasks(db, status, limit, offset)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, db: DbSession) -> TaskModel:
    return task_service.get_task(db, task_id)


@router.post("", response_model=TaskRead, status_code=201)
def create_task(payload: TaskCreate, db: DbSession) -> TaskModel:
    return task_service.create_task(db, payload)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate, db: DbSession) -> TaskModel:
    return task_service.update_task(db, task_id, payload)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: DbSession) -> None:
    task_service.delete_task(db, task_id)
