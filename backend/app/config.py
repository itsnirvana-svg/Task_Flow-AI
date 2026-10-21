from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# El .env vive en la raíz del proyecto; la ruta es absoluta para no depender
# del directorio desde el que se arranque la aplicación.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
POSTGRES_DRIVER = "postgresql+psycopg"
MIN_SECRET_LENGTH = 32  # claves de API y clave de firma: 32 caracteres o más en producción


def is_local(url: str) -> bool:
    """¿La dirección apunta a esta misma máquina (entorno de desarrollo o de pruebas)?"""
    host = (urlparse(url).hostname or "").lower()
    return host in LOCAL_HOSTS or host.endswith(".localhost")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # "production" impide arrancar con direcciones de desarrollo o de prueba (ver el validador).
    app_env: Literal["development", "production"] = "development"

    # Base de datos: SQLite en desarrollo; en producción, PostgreSQL:
    # DATABASE_URL=postgresql://usuario:clave@servidor:5432/taskflow
    database_url: str = "sqlite:///./taskflow.db"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    # Tiempo máximo de espera a Claude por llamada (el SDK espera 10 minutos por defecto).
    anthropic_timeout_seconds: float = 30.0
    # Llamadas a la IA permitidas por minuto y por cliente: cada una consume crédito de pago.
    ai_rate_limit_per_minute: int = 10

    # Autenticación de la API. Dos tipos de credencial (ver app/security.py):
    # - claves de API para servicios como n8n: API_KEYS="n8n:clave-larga,otro:clave-larga"
    # - inicio de sesión para personas: ADMIN_USERNAME + ADMIN_PASSWORD_HASH
    #   (el hash se genera con tools/hash_password.py)
    # AUTH_DISABLED=true deja la API abierta y solo se admite en desarrollo.
    auth_disabled: bool = False
    api_keys: str = ""
    admin_username: str = ""
    admin_password_hash: str = ""
    auth_secret_key: str = ""  # firma los tokens de sesión; en producción, mínimo 32 caracteres
    auth_token_minutes: int = 60
    login_max_attempts_per_minute: int = 5  # por dirección IP, para frenar la fuerza bruta

    # Solo desarrollo; en producción, los dominios reales (con https).
    cors_origins: str = "http://localhost:5500"

    # Automatizaciones: un único webhook de n8n que reparte por tipo de evento.
    # Vacío = no se envían eventos.
    n8n_webhook_url: str = ""
    n8n_webhook_secret: str = ""
    # Entrega de eventos (outbox): reintentos con espera creciente y límite de intentos.
    events_poll_seconds: float = 1.0
    events_max_attempts: int = 8
    events_retry_base_seconds: float = 5.0
    events_retry_max_seconds: float = 900.0
    # Cuánto reserva un despachador un evento mientras lo envía (debe superar el tiempo máximo de
    # envío, 5 s). Si el proceso muere a mitad de un envío, otro lo retoma al vencer la reserva.
    events_lease_seconds: float = 30.0
    events_retention_days: int = 7  # los enviados se conservan este tiempo como evidencia

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def api_key_map(self) -> dict[str, str]:
        """`API_KEYS` ("n8n:clave,otro:clave") como {nombre: clave}."""
        pares = (par.split(":", 1) for par in self.api_keys.split(",") if par.strip())
        return {nombre.strip(): clave.strip() for nombre, clave in pares}

    @property
    def login_configured(self) -> bool:
        """¿Está configurado el inicio de sesión de personas?"""
        return bool(self.admin_username and self.admin_password_hash and self.auth_secret_key)

    @field_validator("api_keys")
    @classmethod
    def check_api_keys_format(cls, valor: str) -> str:
        for par in (p for p in valor.split(",") if p.strip()):
            nombre, separador, clave = par.partition(":")
            if not (separador and nombre.strip() and clave.strip()):
                raise ValueError('API_KEYS debe tener el formato "nombre:clave,otro:clave"')
        return valor

    @field_validator("database_url")
    @classmethod
    def use_postgres_driver(cls, url: str) -> str:
        """Los hostings dan `postgres://` o `postgresql://`; SQLAlchemy exige indicar el driver."""
        for scheme in ("postgres://", "postgresql://"):
            if url.startswith(scheme):
                return f"{POSTGRES_DRIVER}://{url[len(scheme):]}"
        return url

    @model_validator(mode="after")
    def require_secret_for_login(self) -> "Settings":
        """Sin clave de firma no se pueden emitir tokens: se avisa al arrancar, no en el login."""
        if self.admin_password_hash and not (self.admin_username and self.auth_secret_key):
            raise ValueError("ADMIN_PASSWORD_HASH requiere ADMIN_USERNAME y AUTH_SECRET_KEY")
        return self

    @model_validator(mode="after")
    def require_definitive_configuration(self) -> "Settings":
        """En producción, ninguna conexión puede apuntar a un entorno de desarrollo o prueba."""
        if self.app_env != "production":
            return self

        problems = []
        problems += self._authentication_problems()
        if self.database_url.startswith("sqlite"):
            problems.append("DATABASE_URL apunta a SQLite: en producción debe ser PostgreSQL")

        origins = self.cors_origin_list
        if not origins or any(is_local(o) for o in origins):
            problems.append("CORS_ORIGINS incluye localhost o está vacío: indica los dominios")
        elif any(not o.startswith("https://") for o in origins):
            problems.append("CORS_ORIGINS debe usar solo direcciones https://")

        if self.n8n_webhook_url:
            if is_local(self.n8n_webhook_url):
                problems.append("N8N_WEBHOOK_URL apunta a esta misma máquina (localhost)")
            elif not self.n8n_webhook_url.startswith("https://"):
                problems.append("N8N_WEBHOOK_URL debe usar https://")
            if "/webhook-test/" in self.n8n_webhook_url:
                problems.append("N8N_WEBHOOK_URL usa /webhook-test/ (atiende una sola petición)")
            if not self.n8n_webhook_secret:
                problems.append("N8N_WEBHOOK_SECRET es obligatorio si hay N8N_WEBHOOK_URL")

        if problems:
            raise ValueError("Configuración no válida para producción:\n- " + "\n- ".join(problems))
        return self

    def _authentication_problems(self) -> list[str]:
        """Qué le falta a la autenticación para poder usarse en producción."""
        problems = []
        if self.auth_disabled:
            problems.append("AUTH_DISABLED=true deja la API abierta: solo se admite en desarrollo")
        if not self.api_key_map and not self.admin_password_hash:
            problems.append("Sin credenciales: define API_KEYS o ADMIN_USERNAME y su hash")
        if any(len(clave) < MIN_SECRET_LENGTH for clave in self.api_key_map.values()):
            problems.append(f"Cada clave de API_KEYS necesita {MIN_SECRET_LENGTH}+ caracteres")
        if self.admin_password_hash and len(self.auth_secret_key) < MIN_SECRET_LENGTH:
            problems.append(f"AUTH_SECRET_KEY necesita {MIN_SECRET_LENGTH}+ caracteres")
        return problems


settings = Settings()
