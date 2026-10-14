from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TaskModel(Base):
    """Tarea. Refleja las columnas de `tasks` en db/schema.sql.

    Transitorio: project_id y created_by aún no existen aquí porque la aplicación
    no tiene proyectos ni autenticación; se añadirán con esas funciones.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="ck_tasks_status"),
        CheckConstraint("priority BETWEEN 1 AND 4", name="ck_tasks_priority"),
        CheckConstraint("(status = 'done') = (completed_at IS NOT NULL)", name="ck_tasks_completed"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default="todo")
    priority: Mapped[int] = mapped_column(SmallInteger, default=2)
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    external_event_id: Mapped[str | None] = mapped_column(String(255), default=None)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
