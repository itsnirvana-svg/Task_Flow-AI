from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# El .env vive en la raíz del proyecto; la ruta es absoluta para no depender
# del directorio desde el que se arranque la aplicación.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # Base de datos: SQLite en desarrollo; PostgreSQL con
    # DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/taskflow
    database_url: str = "sqlite:///./taskflow.db"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    cors_origins: str = "http://localhost:5173,http://localhost:5500"

    # Automatizaciones: un único webhook de n8n que reparte por tipo de evento.
    # Vacío = no se envían eventos.
    n8n_webhook_url: str = ""
    n8n_webhook_secret: str = ""
    # Entrega de eventos (outbox): reintentos con espera creciente y límite de intentos.
    events_poll_seconds: float = 1.0
    events_max_attempts: int = 8
    events_retry_base_seconds: float = 5.0
    events_retry_max_seconds: float = 900.0
    events_retention_days: int = 7  # los enviados se conservan este tiempo como evidencia


settings = Settings()
