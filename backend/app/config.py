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

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/calendar/callback"
    token_encryption_key: str = ""


settings = Settings()
