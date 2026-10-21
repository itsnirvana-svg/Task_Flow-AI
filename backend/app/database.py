"""Conexión a la base de datos: motor, fábrica de sesiones y la dependencia `DbSession`."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# SQLite necesita este argumento para usarse desde los hilos de FastAPI.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

# pool_pre_ping: comprueba la conexión antes de usarla y descarta las que el servidor cerró.
engine = create_engine(settings.database_url, connect_args=_connect_args, pool_pre_ping=True)
# autoflush=False: nada se escribe en la base hasta que el servicio llama a flush() o commit(),
# de modo que el cambio y su evento del outbox se confirman siempre juntos.
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """Clase de la que heredan todos los modelos (ver models.py)."""


def get_db() -> Iterator[Session]:
    """Una sesión por petición: se abre al entrar a la ruta y se cierra siempre al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Se declara como parámetro de ruta así: `def ruta(db: DbSession)`.
DbSession = Annotated[Session, Depends(get_db)]
