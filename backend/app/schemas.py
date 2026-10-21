"""Formas de los datos que entran y salen de la API (validación con Pydantic).

`TaskCreate` y `TaskUpdate` validan lo que envía el cliente; `TaskRead` define la respuesta.
Los límites (longitudes, rango de prioridad) vienen de constants.py, igual que en el modelo.
"""

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
    """Cuerpo de `POST /api/tasks`. Solo `title` es obligatorio."""

    model_config = ConfigDict(use_enum_values=True)

    title: Title
    description: Description | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = PRIORITY_DEFAULT
    due_date: date | None = None


class TaskUpdate(BaseModel):
    """Cuerpo de `PATCH /api/tasks/{id}`: actualización parcial.

    Los campos que no se envían no se tocan (el servicio usa `exclude_unset`). Enviar `null` en
    `title`, `status` o `priority` se ignora, porque esos campos no admiten nulos.
    """

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
    """Respuesta con una tarea. `from_attributes` la construye directamente desde `TaskModel`."""

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
    """Respuesta de `POST /api/ai/prioritize`: texto libre de Claude, no modifica las tareas."""

    suggestion: str
