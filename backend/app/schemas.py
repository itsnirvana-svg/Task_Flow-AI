from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["todo", "in_progress", "done"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: Status = "todo"
    priority: int = Field(default=2, ge=1, le=4)  # 1 baja ... 4 urgente
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: Status | None = None
    priority: int | None = Field(default=None, ge=1, le=4)
    due_date: date | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: Status
    priority: int
    due_date: date | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PrioritizeResponse(BaseModel):
    suggestion: str
