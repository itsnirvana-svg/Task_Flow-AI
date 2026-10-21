import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main as main_module
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.routers import ai as ai_router
from app.routers import auth as auth_router
from helpers import CLAVE_DE_PRUEBAS


@pytest.fixture(autouse=True)
def limitadores_limpios():
    """Los limitadores viven en memoria: cada prueba empieza sin llamadas contadas."""
    ai_router.ai_limiter.reset()
    auth_router.login_limiter.reset()


@pytest.fixture()
def engine(tmp_path):
    """Base SQLite en un archivo temporal, nueva en cada prueba.

    Es un archivo (y no ":memory:") para que cada sesión tenga su propia conexión, como en
    producción: con una conexión compartida entre hilos, el cierre de una sesión podría
    deshacer la confirmación de otra.
    """
    motor = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(motor)
    yield motor
    motor.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False)


@pytest.fixture()
def db(session_factory):
    """Sesión directa, para probar la capa de servicios sin pasar por HTTP."""
    with session_factory() as sesion:
        yield sesion


@pytest.fixture()
def client(engine, session_factory, monkeypatch):
    """Cliente HTTP con la base en memoria y sin envío real a n8n."""

    def override_get_db():
        sesion = session_factory()
        try:
            yield sesion
        finally:
            sesion.close()

    monkeypatch.setattr(settings, "n8n_webhook_url", "")
    monkeypatch.setattr(settings, "events_poll_seconds", 0.05)
    # La autenticación está activa y este cliente lleva una clave de API válida.
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "api_keys", f"pruebas:{CLAVE_DE_PRUEBAS}")
    # El arranque y el despachador usan la base de pruebas, no la real.
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(main_module, "SessionLocal", session_factory)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"X-API-Key": CLAVE_DE_PRUEBAS}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def anonimo(client):
    """Cliente SIN credenciales, sobre la misma aplicación y la misma base de pruebas."""
    return TestClient(app)
