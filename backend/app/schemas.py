from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .constants import (
    DESCRIPTION_MAX,
    PRIORITY_DEFAULT,
    PRIORITY_MAX,
    PRIORITY_MIN,
    TITLE_MAX,
    TaskStatus,
)

# Recorta espacios y rechaza títulos vacíos o formados solo por espacios.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX)]
Description = Annotated[str, Field(max_length=DESCRIPTION_MAX)]
Priority = Annotated[int, Field(ge=PRIORITY_MIN, le=PRIORITY_MAX)]


class TaskCreate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    title: Title
    description: Description | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = PRIORITY_DEFAULT
    due_date: date | None = None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    title: Title | None = None
    description: Description | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    due_date: date | None = None
    # Campos que escriben las automatizaciones (n8n), no el usuario final.
    external_event_id: Annotated[str, Field(max_length=255)] | None = None
    reminded_at: datetime | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: int
    due_date: date | None
    completed_at: datetime | None
    external_event_id: str | None
    reminded_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PrioritizeResponse(BaseModel):
    suggestion: str
