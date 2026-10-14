"""Integración con Google Calendar (esqueleto).

Las funciones puras (task_to_event) están implementadas y probadas. Los métodos que hablan
con Google están pendientes: requieren autenticación de usuarios y las credenciales OAuth
configuradas en .env.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def task_to_event(task_id: int, title: str, due_date: date, description: str | None = None) -> dict:
    """Convierte una tarea en el cuerpo de un evento de día completo de Google Calendar.

    En eventos de día completo Google trata `end.date` como exclusivo, por eso se suma un día.
    """
    return {
        "summary": title,
        "description": description or "",
        "start": {"date": due_date.isoformat()},
        "end": {"date": (due_date + timedelta(days=1)).isoformat()},
        "extendedProperties": {"private": {"taskflow_task_id": str(task_id)}},
    }


@dataclass
class BusySlot:
    start: datetime
    end: datetime


class CalendarService:
    """Cliente de Google Calendar para un usuario concreto."""

    def __init__(self, refresh_token: str, calendar_id: str = "primary") -> None:
        self.refresh_token = refresh_token
        self.calendar_id = calendar_id

    # --- Flujo OAuth (no dependen de un usuario ya conectado) ---------------------------

    @staticmethod
    def build_authorization_url(state: str) -> str:
        """URL de consentimiento de Google (access_type=offline, prompt=consent)."""
        raise NotImplementedError

    @staticmethod
    def exchange_code(code: str) -> dict:
        """Intercambia el `code` del callback por access_token y refresh_token."""
        raise NotImplementedError

    # --- Eventos --------------------------------------------------------------------------

    def create_event(self, event: dict) -> str:
        """events.insert. Devuelve el id del evento para guardarlo en tasks.external_event_id."""
        raise NotImplementedError

    def update_event(self, event_id: str, event: dict) -> None:
        """events.patch. Si Google responde 404, el llamador debe recrear el evento."""
        raise NotImplementedError

    def delete_event(self, event_id: str) -> None:
        """events.delete. Ignora el 404 (el evento ya no existe)."""
        raise NotImplementedError

    # --- Disponibilidad -------------------------------------------------------------------

    def free_busy(self, time_min: datetime, time_max: datetime) -> list[BusySlot]:
        """freebusy.query: intervalos ocupados, para sugerir huecos libres a la IA."""
        raise NotImplementedError
