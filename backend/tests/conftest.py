import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as main_module
from app.config import settings
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client(monkeypatch):
    """Cliente con una base SQLite en memoria nueva por prueba y sin envío real a n8n."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(settings, "n8n_webhook_url", "")
    monkeypatch.setattr(main_module, "engine", engine)  # el arranque no toca la BD real
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
