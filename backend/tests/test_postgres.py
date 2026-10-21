"""Pruebas contra un PostgreSQL real: esquema SQL, migraciones y entrega de eventos.

El resto de las pruebas usan SQLite, que no detecta diferencias con PostgreSQL (tipos, restricciones
NOT NULL, JSONB). Estas solo se ejecutan si se define TEST_POSTGRES_URL, por ejemplo:

    TEST_POSTGRES_URL=postgresql+psycopg://postgres:postgres@localhost:5432/taskflow_test

CUIDADO: cada prueba BORRA y recrea el esquema `public` de esa base. Usa una base de pruebas.
El CI la define con un servicio PostgreSQL (ver .github/workflows/ci.yml).
"""

import os
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.constants import OutboxStatus
from app.database import Base
from app.models import OutboxEventModel, TaskModel
from app.schemas import TaskCreate, TaskUpdate
from app.services import events, task_service

URL = os.environ.get("TEST_POSTGRES_URL", "")
DB_DIR = Path(__file__).resolve().parents[1] / "db"

pytestmark = pytest.mark.skipif(not URL, reason="define TEST_POSTGRES_URL (PostgreSQL de pruebas)")


def ejecutar_script(ruta: Path) -> None:
    """Ejecuta un archivo .sql completo (varias sentencias, con su propio BEGIN/COMMIT)."""
    import psycopg

    with psycopg.connect(URL.replace("+psycopg", ""), autocommit=True) as conexion:
        conexion.execute(ruta.read_text(encoding="utf-8"))


@pytest.fixture()
def pg():
    """Motor sobre una base vacía: se recrea el esquema `public` antes de cada prueba."""
    motor = create_engine(URL)
    with motor.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    yield motor
    motor.dispose()


@pytest.fixture()
def eventos_activos(monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", "http://n8n.test/webhook/taskflow")


def probar_la_aplicacion(motor):
    """Recorre el ciclo de vida de una tarea con el código real de la aplicación."""
    sesiones = sessionmaker(bind=motor, autoflush=False)
    with sesiones() as db:
        tarea_id = task_service.create_task(db, TaskCreate(title="En PostgreSQL", priority=3)).id
        task_service.update_task(db, tarea_id, TaskUpdate(status="done"))
        task_service.delete_task(db, tarea_id)
    with sesiones() as db:
        filas = list(db.scalars(select(OutboxEventModel).order_by(OutboxEventModel.id)))
        assert [f.event for f in filas] == ["task.created", "task.completed", "task.deleted"]
        assert filas[0].data == {"task_id": tarea_id}  # JSONB se devuelve como diccionario
        assert db.scalars(select(TaskModel)).first() is None


# ---------------------------------------------------------------- esquema y migraciones


def test_la_aplicacion_funciona_sobre_una_base_creada_con_schema_sql(pg, eventos_activos):
    ejecutar_script(DB_DIR / "schema.sql")
    probar_la_aplicacion(pg)


def test_la_aplicacion_funciona_sobre_tablas_creadas_por_el_modelo(pg, eventos_activos):
    Base.metadata.create_all(pg)
    probar_la_aplicacion(pg)


def test_las_migraciones_son_idempotentes(pg, eventos_activos):
    ejecutar_script(DB_DIR / "schema.sql")
    for migracion in sorted((DB_DIR / "migrations").glob("*.sql")):
        ejecutar_script(migracion)
        ejecutar_script(migracion)  # una segunda vez no debe fallar
    probar_la_aplicacion(pg)


def test_el_modelo_no_pide_columnas_que_schema_sql_no_tiene(pg):
    """Detecta el desajuste entre models.py y schema.sql en cuanto aparece."""
    ejecutar_script(DB_DIR / "schema.sql")
    consulta = text("SELECT column_name FROM information_schema.columns WHERE table_name = :t")
    with pg.connect() as c:
        for tabla in Base.metadata.sorted_tables:
            en_bd = {fila[0] for fila in c.execute(consulta, {"t": tabla.name})}
            assert {col.name for col in tabla.columns} <= en_bd, f"faltan columnas en {tabla.name}"


# ---------------------------------------------------------------- varios despachadores


def test_varios_despachadores_no_duplican_eventos_en_postgresql(pg, eventos_activos, monkeypatch):
    ejecutar_script(DB_DIR / "schema.sql")
    sesiones = sessionmaker(bind=pg, autoflush=False)
    total = 30
    with sesiones() as db:
        for i in range(total):
            task_service.create_task(db, TaskCreate(title=f"T{i}"))
    recibidos = []

    def envio_lento(carga):
        time.sleep(0.01)
        recibidos.append(carga["sequence"])

    monkeypatch.setattr(events, "send", envio_lento)
    despachadores = [events.Dispatcher(sesiones, poll_seconds=0.01) for _ in range(3)]
    for d in despachadores:
        d.start()
    try:
        assert despachadores[0].drain(timeout=30), "quedaron eventos sin enviar"
        time.sleep(0.3)
    finally:
        for d in despachadores:
            d.stop()

    assert len(recibidos) == total and len(set(recibidos)) == total
    assert recibidos == sorted(recibidos)
    with sesiones() as db:
        estados = {f.status for f in db.scalars(select(OutboxEventModel))}
    assert estados == {OutboxStatus.SENT.value}
