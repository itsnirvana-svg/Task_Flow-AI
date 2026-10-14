from functools import lru_cache

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import TaskModel
from ..schemas import PrioritizeResponse

router = APIRouter(prefix="/api/ai", tags=["ai"])


@lru_cache
def get_client() -> Anthropic:
    """Un único cliente reutilizable (mantiene conexiones abiertas)."""
    return Anthropic(api_key=settings.anthropic_api_key)


@router.post("/prioritize", response_model=PrioritizeResponse)
def prioritize(db: Session = Depends(get_db)) -> PrioritizeResponse:
    """Pide a Claude que sugiera un orden de prioridad para las tareas pendientes."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY no configurada")

    pending = list(
        db.scalars(
            select(TaskModel)
            .where(TaskModel.status != "done")
            .order_by(TaskModel.priority.desc(), TaskModel.due_date)
            .limit(50)
        )
    )
    if not pending:
        return PrioritizeResponse(suggestion="No hay tareas pendientes.")

    lines = [
        f"- {t.title} (prioridad actual {t.priority}/4"
        + (f", vence {t.due_date.isoformat()}" if t.due_date else "")
        + ")"
        for t in pending
    ]
    prompt = (
        "Ordena estas tareas de mayor a menor prioridad y explica brevemente por qué, "
        "en español y de forma concisa:\n" + "\n".join(lines)
    )

    try:
        message = get_client().messages.create(
            model=settings.anthropic_model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # error de red, cuota o clave inválida
        raise HTTPException(status_code=502, detail="El servicio de IA no respondió") from exc

    return PrioritizeResponse(suggestion=message.content[0].text)
