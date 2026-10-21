import math
from functools import lru_cache

from anthropic import Anthropic
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..constants import TaskStatus
from ..database import DbSession
from ..models import TaskModel
from ..ratelimit import RateLimiter
from ..schemas import PrioritizeResponse
from ..security import Principal

router = APIRouter(prefix="/api/ai", tags=["ai"])

MAX_TASKS_IN_PROMPT = 50

# Cada llamada consume crédito de pago: se limita por cliente (ver AI_RATE_LIMIT_PER_MINUTE).
ai_limiter = RateLimiter(lambda: settings.ai_rate_limit_per_minute)


@lru_cache
def get_client() -> Anthropic:
    """Un único cliente reutilizable (mantiene conexiones abiertas).

    Con tiempo de espera y un solo reintento: una llamada colgada no debe ocupar un hilo del
    servidor durante minutos.
    """
    return Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.anthropic_timeout_seconds,
        max_retries=1,
    )


def _pending_tasks(db: Session) -> list[TaskModel]:
    query = (
        select(TaskModel)
        .where(TaskModel.status != TaskStatus.DONE.value)
        .order_by(TaskModel.priority.desc(), TaskModel.due_date)
        .limit(MAX_TASKS_IN_PROMPT)
    )
    return list(db.scalars(query))


def _build_prompt(tasks: list[TaskModel]) -> str:
    lines = [
        f"- {t.title} (prioridad actual {t.priority}/4"
        + (f", vence {t.due_date.isoformat()}" if t.due_date else "")
        + ")"
        for t in tasks
    ]
    return (
        "Ordena estas tareas de mayor a menor prioridad y explica brevemente por qué, "
        "en español y de forma concisa:\n" + "\n".join(lines)
    )


@router.post("/prioritize", response_model=PrioritizeResponse)
def prioritize(db: DbSession, principal: Principal) -> PrioritizeResponse:
    """Pide a Claude que sugiera un orden de prioridad para las tareas pendientes."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY no configurada")

    wait = ai_limiter.retry_after(principal)
    if wait is not None:
        raise HTTPException(
            status_code=429,
            detail="Demasiadas peticiones a la IA; espera un momento",
            headers={"Retry-After": str(math.ceil(wait))},
        )

    pending = _pending_tasks(db)
    if not pending:
        return PrioritizeResponse(suggestion="No hay tareas pendientes.")

    try:
        message = get_client().messages.create(
            model=settings.anthropic_model,
            max_tokens=600,
            messages=[{"role": "user", "content": _build_prompt(pending)}],
        )
    except Exception as exc:  # error de red, cuota o clave inválida
        raise HTTPException(status_code=502, detail="El servicio de IA no respondió") from exc

    # La respuesta es una lista de bloques; se unen los de texto y se tolera una lista vacía.
    suggestion = "".join(getattr(block, "text", "") for block in message.content).strip()
    if not suggestion:
        raise HTTPException(status_code=502, detail="La IA devolvió una respuesta vacía")
    return PrioritizeResponse(suggestion=suggestion)
