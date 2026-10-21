"""Valores compartidos por modelo, validación y rutas: una sola fuente de verdad."""

from enum import Enum


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class OutboxStatus(str, Enum):
    PENDING = "pending"  # a la espera de enviarse (o de reintentarse)
    SENT = "sent"  # n8n lo aceptó
    DEAD = "dead"  # se agotaron los intentos; queda como evidencia


PRIORITY_MIN = 1  # baja
PRIORITY_MAX = 4  # urgente
PRIORITY_DEFAULT = 2

TITLE_MAX = 200
PROJECT_MAX = 60
DESCRIPTION_MAX = 5000

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
