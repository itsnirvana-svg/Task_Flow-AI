"""Configuración y conexiones: nada de direcciones de prueba en producción."""

import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import ENV_FILE, Settings, is_local

NOMBRES = (
    "APP_ENV", "DATABASE_URL", "CORS_ORIGINS", "N8N_WEBHOOK_URL", "N8N_WEBHOOK_SECRET",
    "AUTH_DISABLED", "API_KEYS", "ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "AUTH_SECRET_KEY",
)

CLAVE_LARGA = "k" * 40

PRODUCCION_VALIDA = {
    "app_env": "production",
    "database_url": "postgresql://usuario:clave@db.tu-empresa.com:5432/taskflow",
    "cors_origins": "https://tareas.tu-empresa.com",
    "api_keys": f"n8n:{CLAVE_LARGA}",
}


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    """Las pruebas no deben depender de variables de entorno del equipo."""
    for nombre in NOMBRES:
        monkeypatch.delenv(nombre, raising=False)


def configuracion(**campos):
    return Settings(_env_file=None, **campos)


# ---------------------------------------------------------------- desarrollo


def test_el_valor_por_defecto_es_desarrollo_y_no_envia_eventos():
    ajustes = configuracion()
    assert ajustes.app_env == "development"
    assert ajustes.n8n_webhook_url == ""  # sin URL no se envían eventos
    assert ajustes.cors_origin_list == ["http://localhost:5500"]


@pytest.mark.parametrize(
    ("entrada", "esperada"),
    [
        ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("postgresql://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("sqlite:///./taskflow.db", "sqlite:///./taskflow.db"),
    ],
)
def test_las_urls_de_postgres_de_los_hostings_se_normalizan(entrada, esperada):
    assert configuracion(database_url=entrada).database_url == esperada


def test_el_controlador_de_postgresql_esta_instalado_y_declarado():
    assert importlib.util.find_spec("psycopg") is not None
    requisitos = (ENV_FILE.parent / "backend" / "requirements.txt").read_text(encoding="utf-8")
    assert "psycopg" in requisitos


@pytest.mark.parametrize(
    ("url", "local"),
    [
        ("http://localhost:5678/webhook/x", True),
        ("http://127.0.0.1:8000", True),
        ("http://[::1]:8000", True),
        ("http://app.localhost", True),
        ("https://n8n.tu-empresa.com/webhook/taskflow", False),
    ],
)
def test_reconoce_las_direcciones_locales(url, local):
    assert is_local(url) is local


# ---------------------------------------------------------------- producción


def test_produccion_con_los_valores_por_defecto_no_arranca():
    with pytest.raises(ValidationError) as error:
        configuracion(app_env="production")
    mensaje = str(error.value)
    assert "DATABASE_URL apunta a SQLite" in mensaje
    assert "CORS_ORIGINS incluye localhost" in mensaje


def test_produccion_valida_arranca_y_normaliza_la_base_de_datos():
    ajustes = configuracion(**PRODUCCION_VALIDA)
    assert ajustes.database_url.startswith("postgresql+psycopg://")


def test_produccion_con_webhook_https_y_secreto_es_valida():
    ajustes = configuracion(
        **PRODUCCION_VALIDA,
        n8n_webhook_url="https://n8n.tu-empresa.com/webhook/taskflow",
        n8n_webhook_secret=CLAVE_LARGA,
    )
    assert ajustes.n8n_webhook_url.endswith("/webhook/taskflow")


N8N_PROD = "https://n8n.tu-empresa.com/webhook/taskflow"
N8N_PRUEBAS = "https://n8n.tu-empresa.com/webhook-test/taskflow"


@pytest.mark.parametrize(
    ("campos", "problema"),
    [
        ({"n8n_webhook_url": "http://localhost:5678/webhook/x", "n8n_webhook_secret": "x"},
         "N8N_WEBHOOK_URL apunta a esta misma máquina"),
        ({"n8n_webhook_url": "http://n8n.tu-empresa.com/webhook/x", "n8n_webhook_secret": "x"},
         "N8N_WEBHOOK_URL debe usar https://"),
        ({"n8n_webhook_url": N8N_PRUEBAS, "n8n_webhook_secret": "s"}, "/webhook-test/"),
        ({"n8n_webhook_url": N8N_PROD}, "N8N_WEBHOOK_SECRET es obligatorio"),
        ({"cors_origins": "http://tareas.tu-empresa.com"}, "solo direcciones https://"),
        ({"cors_origins": "https://tareas.tu-empresa.com,http://localhost:5500"},
         "CORS_ORIGINS incluye localhost"),
        ({"database_url": "sqlite:///./taskflow.db"}, "DATABASE_URL apunta a SQLite"),
    ],
)
def test_produccion_rechaza_direcciones_de_prueba(campos, problema):
    with pytest.raises(ValidationError, match=problema):
        configuracion(**{**PRODUCCION_VALIDA, **campos})


def test_produccion_sin_webhook_es_valida_los_eventos_son_opcionales():
    assert configuracion(**PRODUCCION_VALIDA).n8n_webhook_url == ""


# ---------------------------------------------------------------- autenticación


HASH = "scrypt$16384$8$1$c2FsdA==$aGFzaA=="  # solo la forma: estas pruebas no verifican contraseñas


@pytest.mark.parametrize(
    ("campos", "problema"),
    [
        ({"auth_disabled": True}, "AUTH_DISABLED=true deja la API abierta"),
        ({"api_keys": ""}, "Sin credenciales"),
        ({"api_keys": "n8n:corta"}, r"necesita 32\+ caracteres"),
        ({"api_keys": "", "admin_username": "ana", "admin_password_hash": HASH,
          "auth_secret_key": "corta"}, "AUTH_SECRET_KEY necesita 32"),
    ],
)
def test_produccion_exige_autenticacion_segura(campos, problema):
    with pytest.raises(ValidationError, match=problema):
        configuracion(**{**PRODUCCION_VALIDA, **campos})


def test_produccion_acepta_inicio_de_sesion_sin_claves_de_api():
    ajustes = configuracion(
        **{**PRODUCCION_VALIDA, "api_keys": ""},
        admin_username="ana", admin_password_hash=HASH, auth_secret_key=CLAVE_LARGA,
    )
    assert ajustes.login_configured


def test_el_formato_de_las_claves_de_api_se_valida_siempre():
    with pytest.raises(ValidationError, match="nombre:clave"):
        configuracion(api_keys="sin-separador")
    assert configuracion(api_keys="n8n:abc, otro:def").api_key_map == {"n8n": "abc", "otro": "def"}


def test_un_hash_de_contrasena_sin_clave_de_firma_se_rechaza_al_arrancar():
    with pytest.raises(ValidationError, match="AUTH_SECRET_KEY"):
        configuracion(admin_username="ana", admin_password_hash=HASH)


def test_por_defecto_la_autenticacion_esta_activa():
    assert configuracion().auth_disabled is False


# ---------------------------------------------------------------- documentación y código


def test_todas_las_variables_estan_documentadas_en_env_example():
    ejemplo = (ENV_FILE.parent / ".env.example").read_text(encoding="utf-8").upper()
    sin_documentar = [campo for campo in Settings.model_fields if campo.upper() not in ejemplo]
    assert sin_documentar == []


def test_el_codigo_de_la_aplicacion_no_contiene_direcciones_de_prueba():
    """Solo `config.py` puede nombrar localhost (valores por defecto de desarrollo)."""
    codigo = Path(ENV_FILE.parent / "backend" / "app")
    for archivo in codigo.rglob("*.py"):
        if archivo.name == "config.py":
            continue
        texto = archivo.read_text(encoding="utf-8")
        for prohibido in ("localhost", "127.0.0.1", "webhook-test"):
            assert prohibido not in texto, f"{archivo.name} contiene {prohibido}"


# ---------------------------------------------------------------- plantillas sin cambiar


def test_produccion_rechaza_un_secreto_de_webhook_corto():
    with pytest.raises(ValidationError, match=r"N8N_WEBHOOK_SECRET necesita 32\+ caracteres"):
        configuracion(
            **PRODUCCION_VALIDA,
            n8n_webhook_url="https://n8n.tu-empresa.com/webhook/taskflow",
            n8n_webhook_secret="cambia-esto",
        )


@pytest.mark.parametrize("hash_malo", ["scrypt$cambia$esto", "texto", "scrypt$1$2$3$a$"])
def test_produccion_rechaza_un_hash_de_contrasena_mal_formado(hash_malo):
    with pytest.raises(ValidationError, match="ADMIN_PASSWORD_HASH no es un hash válido"):
        configuracion(
            **{**PRODUCCION_VALIDA, "api_keys": ""},
            admin_username="ana", admin_password_hash=hash_malo, auth_secret_key=CLAVE_LARGA,
        )


def test_los_marcadores_de_deploy_env_example_no_arrancan_en_produccion():
    """Quien olvide cambiar un valor de la plantilla recibe un error, no un servidor inseguro."""
    plantilla = {}
    ejemplo = (ENV_FILE.parent / "deploy" / ".env.example").read_text(encoding="utf-8")
    for linea in ejemplo.splitlines():
        if linea and not linea.startswith("#") and "=" in linea:
            nombre, valor = linea.split("=", 1)
            plantilla[nombre] = valor.strip("'")

    with pytest.raises(ValidationError) as error:
        configuracion(
            app_env="production",
            database_url="postgresql://t:t@postgres:5432/taskflow",
            cors_origins=plantilla["CORS_ORIGINS"],
            n8n_webhook_url=f"https://n8n.{plantilla['DOMAIN']}/webhook/taskflow",
            n8n_webhook_secret=plantilla["N8N_WEBHOOK_SECRET"],
            api_keys=plantilla["API_KEYS"],
            admin_username=plantilla["ADMIN_USERNAME"],
            admin_password_hash=plantilla["ADMIN_PASSWORD_HASH"],
            auth_secret_key=plantilla["AUTH_SECRET_KEY"],
        )
    mensaje = str(error.value)
    assert "N8N_WEBHOOK_SECRET necesita" in mensaje
    assert "Cada clave de API_KEYS necesita" in mensaje
    assert "AUTH_SECRET_KEY necesita" in mensaje
    assert "ADMIN_PASSWORD_HASH no es un hash válido" in mensaje
