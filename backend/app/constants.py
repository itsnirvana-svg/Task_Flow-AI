"""Valores compartidos por modelo, validación y rutas: una sola fuente de verdad."""

from enum import Enum


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


PRIORITY_MIN = 1  # baja
PRIORITY_MAX = 4  # urgente
PRIORITY_DEFAULT = 2

TITLE_MAX = 200
DESCRIPTION_MAX = 5000
