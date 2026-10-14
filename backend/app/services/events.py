"""Envío de eventos de la aplicación al webhook de n8n.

Diseño: se ejecuta en segundo plano (BackgroundTasks), así que un fallo o una demora de n8n
nunca afecta a la respuesta que recibe el usuario.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from ..config import settings

logger = logging.getLogger("taskflow.events")

SECRET_HEADER = "X-TaskFlow-Secret"


def build_event(event: str, data: dict) -> dict:
    return {
        "event": event,
        "event_id": str(uuid4()),  # permite a n8n descartar duplicados
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def emit(event: str, data: dict) -> None:
    """Envía el evento a n8n. No lanza excepciones: registra el fallo y sigue."""
    url = settings.n8n_webhook_url
    if not url:
        return

    headers = {SECRET_HEADER: settings.n8n_webhook_secret} if settings.n8n_webhook_secret else {}
    try:
        response = httpx.post(url, json=build_event(event, data), headers=headers, timeout=5.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("No se pudo enviar el evento %s a n8n: %s", event, exc)
