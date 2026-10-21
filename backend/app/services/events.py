"""Eventos de la aplicación hacia n8n, con el patrón *outbox* transaccional.

Cómo funciona:
1. `record()` guarda el evento en la tabla `event_outbox` dentro de la MISMA transacción que
   el cambio de la tarea: si el cambio se confirma, el evento existe; si no, tampoco.
2. Un `Dispatcher` en segundo plano lee los pendientes en orden y los envía a n8n.
3. Si n8n falla o tarda, el evento sigue en la base de datos y se reintenta con espera
   creciente (5 s, 10 s, 20 s…) hasta un máximo de intentos; luego queda como `dead`.
4. Si la API se reinicia, los pendientes se envían al volver a arrancar: no se pierde nada.

Varios procesos de la API pueden convivir: cada despachador reserva el evento en la base de datos
antes de enviarlo (`Dispatcher._claim`), así que solo uno lo envía.

Garantías: entrega **al menos una vez** (puede haber duplicados tras un fallo) y en el orden
de publicación. n8n debe descartar `event_id` ya procesados y consultar el estado actual de la
tarea en lugar de fiarse solo del contenido del evento.
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings
from ..constants import OutboxStatus
from ..models import OutboxEventModel

logger = logging.getLogger("taskflow.events")

SECRET_HEADER = "X-TaskFlow-Secret"
PURGE_EVERY_SECONDS = 600

_wake = threading.Event()  # despierta al despachador sin esperar al sondeo


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record(db: Session, event: str, data: dict) -> None:
    """Anota el evento en la sesión actual. Se confirma junto con el cambio que lo origina.

    No hace nada si no hay webhook configurado. Después del `commit`, llamar a `notify()`.
    """
    if not settings.n8n_webhook_url:
        return
    now = _now()
    db.add(
        OutboxEventModel(
            event_id=str(uuid4()), event=event, data=data, occurred_at=now, next_attempt_at=now
        )
    )


def notify() -> None:
    """Avisa al despachador de que puede haber eventos nuevos."""
    _wake.set()


def build_payload(row: OutboxEventModel) -> dict:
    return {
        "event": row.event,
        "event_id": row.event_id,  # estable entre reintentos: permite descartar duplicados
        "sequence": row.id,  # creciente y persistente (sobrevive a reinicios)
        "occurred_at": row.occurred_at.isoformat(),
        "data": row.data,
    }


def send(payload: dict) -> None:
    """Un intento de envío a n8n. Lanza una excepción si falla (el despachador reintenta)."""
    headers = {SECRET_HEADER: settings.n8n_webhook_secret} if settings.n8n_webhook_secret else {}
    response = httpx.post(settings.n8n_webhook_url, json=payload, headers=headers, timeout=5.0)
    response.raise_for_status()


def retry_delay(attempts: int) -> float:
    """Espera antes del siguiente intento: base, 2×base, 4×base… hasta el máximo."""
    espera = settings.events_retry_base_seconds * 2 ** (attempts - 1)
    return min(espera, settings.events_retry_max_seconds)


def purge_sent(db: Session) -> int:
    """Elimina los eventos enviados con más antigüedad que la retención. Devuelve cuántos."""
    limit = _now() - timedelta(days=settings.events_retention_days)
    result = db.execute(
        delete(OutboxEventModel).where(
            OutboxEventModel.status == OutboxStatus.SENT.value,
            OutboxEventModel.sent_at < limit,
        )
    )
    db.commit()
    return result.rowcount or 0


class Dispatcher:
    """Hilo que envía los eventos pendientes, de uno en uno y en orden.

    Si el primer pendiente falla, los siguientes esperan (para conservar el orden); cuando
    agota sus intentos pasa a `dead` y el resto continúa.
    """

    def __init__(self, session_factory: sessionmaker, poll_seconds: float | None = None):
        self._session_factory = session_factory
        self._poll = poll_seconds if poll_seconds is not None else settings.events_poll_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="taskflow-outbox", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        _wake.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def pending(self) -> int:
        with self._session_factory() as db:
            query = select(func.count()).select_from(OutboxEventModel)
            query = query.where(OutboxEventModel.status == OutboxStatus.PENDING.value)
            return db.scalar(query) or 0

    def drain(self, timeout: float = 5.0) -> bool:
        """Espera a que no queden pendientes. False si se agota el tiempo."""
        deadline = time.monotonic() + timeout
        while self.pending():
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.02)
        return True

    @staticmethod
    def _claim(db: Session, row_id: int) -> bool:
        """Reserva el evento para este despachador con una actualización atómica.

        La base de datos deja pasar a UN solo despachador: la condición exige que el evento siga
        pendiente, que ya le toque y que nadie lo tenga reservado. Así, varios procesos de la API
        (varios workers o réplicas) no envían el mismo evento dos veces, y como cada uno solo
        reserva el primer pendiente, el orden se conserva. La reserva caduca por si el proceso
        muere a mitad del envío.
        """
        now = _now()
        result = db.execute(
            update(OutboxEventModel)
            .where(
                OutboxEventModel.id == row_id,
                OutboxEventModel.status == OutboxStatus.PENDING.value,
                OutboxEventModel.next_attempt_at <= now,
                or_(OutboxEventModel.locked_until.is_(None), OutboxEventModel.locked_until <= now),
            )
            .values(locked_until=now + timedelta(seconds=settings.events_lease_seconds))
            .execution_options(synchronize_session=False)
        )
        db.commit()
        return result.rowcount == 1

    def dispatch_next(self) -> bool:
        """Intenta enviar el primer pendiente. True si hizo un intento; False si no había nada
        listo (sin pendientes, el primero aún espera su turno de reintento o lo tiene reservado
        otro despachador)."""
        with self._session_factory() as db:
            row = db.scalars(
                select(OutboxEventModel)
                .where(OutboxEventModel.status == OutboxStatus.PENDING.value)
                .order_by(OutboxEventModel.id)
                .limit(1)
            ).first()
            if row is None or row.next_attempt_at > _now():
                return False
            if not self._claim(db, row.id):
                return False
            db.refresh(row)  # el estado confirmado, por si otro lo cambió mientras tanto

            try:
                send(build_payload(row))
            except Exception as exc:  # red, tiempo agotado, HTTP de error o fallo inesperado
                row.attempts += 1
                row.last_error = f"{type(exc).__name__}: {exc}"[:500]
                if row.attempts >= settings.events_max_attempts:
                    row.status = OutboxStatus.DEAD.value
                    logger.error("Evento %s (#%s) descartado tras %s intentos: %s",
                                 row.event, row.id, row.attempts, row.last_error)
                else:
                    row.next_attempt_at = _now() + timedelta(seconds=retry_delay(row.attempts))
                    logger.warning("Evento %s (#%s) falló (intento %s), se reintentará: %s",
                                   row.event, row.id, row.attempts, row.last_error)
            else:
                row.status = OutboxStatus.SENT.value
                row.sent_at = _now()
                row.last_error = None
            row.locked_until = None  # libera la reserva en cualquier resultado
            db.commit()
            return True

    def _run(self) -> None:
        last_purge = time.monotonic()
        while not self._stop.is_set():
            try:
                if settings.n8n_webhook_url and self.dispatch_next():
                    continue  # seguir con el siguiente sin esperar
                if time.monotonic() - last_purge > PURGE_EVERY_SECONDS:
                    with self._session_factory() as db:
                        purge_sent(db)
                    last_purge = time.monotonic()
            except Exception:  # el hilo de envío nunca debe morir
                logger.exception("Error inesperado en el despachador de eventos")
            _wake.wait(self._poll)
            _wake.clear()
