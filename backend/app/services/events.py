"""Envío de eventos de la aplicación al webhook de n8n.

Garantías:
- El evento se construye en el momento en que ocurre el cambio (`occurred_at` y `sequence`
  se fijan al publicar, no al enviar).
- Los eventos salen en el mismo orden en que se publican: una cola con un único hilo de envío.
- Un fallo o una demora de n8n nunca afecta a la respuesta de la API: `publish` no bloquea
  y `send` no lanza excepciones.

Aun así, n8n puede recibir eventos fuera de orden si hay varias instancias de la API o
reintentos. Los flujos deben consultar el estado actual de la tarea en lugar de fiarse
solo del contenido del evento.
"""

import itertools
import logging
import queue
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from ..config import settings

logger = logging.getLogger("taskflow.events")

SECRET_HEADER = "X-TaskFlow-Secret"

_queue: "queue.Queue[dict]" = queue.Queue()
_sequence = itertools.count(1)
_worker_lock = threading.Lock()
_worker: threading.Thread | None = None


def build_event(event: str, data: dict) -> dict:
    return {
        "event": event,
        "event_id": str(uuid4()),  # permite a n8n descartar duplicados
        "sequence": next(_sequence),  # orden de publicación dentro de este proceso
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def publish(event: str, data: dict) -> None:
    """Registra el evento y lo encola para su envío. No bloquea."""
    if not settings.n8n_webhook_url:
        return
    _ensure_worker()
    _queue.put(build_event(event, data))


def send(payload: dict) -> None:
    """Un intento de envío a n8n. No lanza excepciones: registra el fallo y sigue."""
    url = settings.n8n_webhook_url
    if not url:
        return

    headers = {SECRET_HEADER: settings.n8n_webhook_secret} if settings.n8n_webhook_secret else {}
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=5.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("No se pudo enviar el evento %s a n8n: %s", payload.get("event"), exc)


def drain(timeout: float = 5.0) -> bool:
    """Espera a que se envíen los eventos pendientes. Devuelve False si se agota el tiempo."""
    deadline = time.monotonic() + timeout
    while _queue.unfinished_tasks:
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)
    return True


def _ensure_worker() -> None:
    global _worker
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_run, name="taskflow-events", daemon=True)
            _worker.start()


def _run() -> None:
    while True:
        payload = _queue.get()
        try:
            send(payload)  # se busca en el módulo en cada envío (facilita las pruebas)
        except Exception:  # el hilo de envío nunca debe morir
            logger.exception("Error inesperado al enviar el evento")
        finally:
            _queue.task_done()
