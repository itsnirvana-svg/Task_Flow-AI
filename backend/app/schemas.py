from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

from .constants import (
    DESCRIPTION_MAX,
    PRIORITY_DEFAULT,
    PRIORITY_MAX,
    PRIORITY_MIN,
    PROJECT_MAX,
    TITLE_MAX,
    TaskStatus,
)

# Recorta espacios y rechaza títulos vacíos o formados solo por espacios.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX)]
Description = Annotated[str, Field(max_length=DESCRIPTION_MAX)]
Priority = Annotated[int, Field(ge=PRIORITY_MIN, le=PRIORITY_MAX)]


def _blank_to_none(value):
    return None if isinstance(value, str) and not value.strip() else value


# Nombre del proyecto: se recorta y un texto vacío equivale a «sin proyecto» (null).
Project = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=PROJECT_MAX)] | None,
    BeforeValidator(_blank_to_none),
]


class TaskCreate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    title: Title
    description: Description | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = PRIORITY_DEFAULT
    due_date: date | None = None
    project: Project = None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    title: Title | None = None
    description: Description | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    due_date: date | None = None
    project: Project = None  # null o vacío: quita el proyecto
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
    project: str | None
    completed_at: datetime | None
    external_event_id: str | None
    reminded_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PrioritizeResponse(BaseModel):
    suggestion: str


class LoginRequest(BaseModel):
    """Cuerpo de `POST /api/auth/login`. Los máximos evitan cálculos de hash con textos enormes."""

    username: Annotated[str, Field(min_length=1, max_length=100)]
    password: Annotated[str, Field(min_length=1, max_length=200)]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos de validez del token
