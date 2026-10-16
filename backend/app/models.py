from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, Index, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from .constants import PRIORITY_DEFAULT, PRIORITY_MAX, PRIORITY_MIN, TaskStatus
from .database import Base


class UTCDateTime(TypeDecorator):
    """Fecha y hora siempre con zona horaria UTC.

    SQLite no guarda la zona horaria y devolvía fechas "ingenuas"; PostgreSQL sí la
    conserva. Así ambos motores se comportan igual.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


_STATUSES = ", ".join(f"'{s.value}'" for s in TaskStatus)
_NOT_DONE = text(f"status <> '{TaskStatus.DONE.value}'")


class TaskModel(Base):
    """Tarea. Refleja las columnas de `tasks` en db/schema.sql.

    Transitorio: project_id y created_by aún no existen aquí porque la aplicación
    no tiene proyectos ni autenticación; se añadirán con esas funciones.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUSES})", name="ck_tasks_status"),
        CheckConstraint(
            f"priority BETWEEN {PRIORITY_MIN} AND {PRIORITY_MAX}", name="ck_tasks_priority"
        ),
        CheckConstraint(
            f"(status = '{TaskStatus.DONE.value}') = (completed_at IS NOT NULL)",
            name="ck_tasks_completed",
        ),
        # Índices de las consultas habituales (los mismos criterios que db/schema.sql).
        Index("idx_tasks_status", "status"),
        Index(
            "idx_tasks_due_pending",
            "due_date",
            sqlite_where=_NOT_DONE,
            postgresql_where=_NOT_DONE,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.TODO.value)
    priority: Mapped[int] = mapped_column(SmallInteger, default=PRIORITY_DEFAULT)
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    external_event_id: Mapped[str | None] = mapped_column(String(255), default=None)
    reminded_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now, onupdate=_now)
