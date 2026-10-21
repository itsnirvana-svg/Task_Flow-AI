"""Autenticación: claves de API, inicio de sesión, tokens, límites de uso y documentación."""

import time
from types import SimpleNamespace

import jwt
import pytest

from app.config import settings
from app.main import docs_urls
from app.routers import ai
from app.security import create_token, decode_token, hash_password, verify_password
from helpers import CLAVE_DE_PRUEBAS, crear

SECRETO = "s" * 40
CONTRASENA = "una-contraseña-larga-123"

RUTAS_PROTEGIDAS = [
    ("get", "/api/tasks", None),
    ("post", "/api/tasks", {"title": "x"}),
    ("get", "/api/tasks/1", None),
    ("patch", "/api/tasks/1", {"title": "x"}),
    ("delete", "/api/tasks/1", None),
    ("post", "/api/ai/prioritize", None),
]


@pytest.fixture()
def con_login(monkeypatch):
    """Inicio de sesión configurado: usuario `ana` con una contraseña conocida."""
    monkeypatch.setattr(settings, "admin_username", "ana")
    monkeypatch.setattr(settings, "admin_password_hash", hash_password(CONTRASENA))
    monkeypatch.setattr(settings, "auth_secret_key", SECRETO)
    monkeypatch.setattr(settings, "login_max_attempts_per_minute", 5)


def entrar(cliente, usuario="ana", contrasena=CONTRASENA):
    return cliente.post("/api/auth/login", json={"username": usuario, "password": contrasena})


def con_token(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------- sin credenciales


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), RUTAS_PROTEGIDAS)
def test_las_rutas_protegidas_rechazan_a_quien_no_se_identifica(anonimo, metodo, ruta, cuerpo):
    respuesta = getattr(anonimo, metodo)(ruta, **({"json": cuerpo} if cuerpo else {}))

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_sin_credenciales_no_se_crea_ni_se_borra_nada(client, anonimo):
    tarea = crear(client)

    anonimo.post("/api/tasks", json={"title": "intruso"})
    anonimo.delete(f"/api/tasks/{tarea['id']}")

    titulos = [t["title"] for t in client.get("/api/tasks").json()]
    assert titulos == [tarea["title"]]


def test_health_es_publico(anonimo):
    assert anonimo.get("/health").status_code == 200


# ---------------------------------------------------------------- claves de API


def test_una_clave_de_api_valida_da_acceso(client):
    assert client.get("/api/tasks").status_code == 200


@pytest.mark.parametrize(
    "clave",
    ["", "incorrecta", CLAVE_DE_PRUEBAS[:-1], CLAVE_DE_PRUEBAS + "x", CLAVE_DE_PRUEBAS.upper()],
)
def test_una_clave_incorrecta_o_parecida_se_rechaza(anonimo, clave):
    assert anonimo.get("/api/tasks", headers={"X-API-Key": clave}).status_code == 401


def test_cada_cliente_tiene_su_propia_clave(anonimo, monkeypatch):
    monkeypatch.setattr(settings, "api_keys", "n8n:clave-de-n8n,scripts:clave-de-scripts")

    assert anonimo.get("/api/tasks", headers={"X-API-Key": "clave-de-n8n"}).status_code == 200
    assert anonimo.get("/api/tasks", headers={"X-API-Key": "clave-de-scripts"}).status_code == 200

    monkeypatch.setattr(settings, "api_keys", "scripts:clave-de-scripts")  # se revoca la de n8n
    assert anonimo.get("/api/tasks", headers={"X-API-Key": "clave-de-n8n"}).status_code == 401
    assert anonimo.get("/api/tasks", headers={"X-API-Key": "clave-de-scripts"}).status_code == 200


def test_sin_claves_configuradas_ninguna_clave_sirve(anonimo, monkeypatch):
    monkeypatch.setattr(settings, "api_keys", "")
    assert anonimo.get("/api/tasks", headers={"X-API-Key": ""}).status_code == 401
    assert anonimo.get("/api/tasks", headers={"X-API-Key": "cualquiera"}).status_code == 401


# ---------------------------------------------------------------- inicio de sesión


def test_login_correcto_devuelve_un_token_que_da_acceso(anonimo, con_login):
    respuesta = entrar(anonimo)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token_type"] == "bearer" and cuerpo["expires_in"] == 3600
    acceso = anonimo.get("/api/tasks", headers=con_token(cuerpo["access_token"]))
    assert acceso.status_code == 200


def test_usuario_o_contrasena_incorrectos_dan_el_mismo_error(anonimo, con_login):
    mala_contrasena = entrar(anonimo, contrasena="incorrecta-123456")
    mal_usuario = entrar(anonimo, usuario="otro")

    assert mala_contrasena.status_code == mal_usuario.status_code == 401
    assert mala_contrasena.json() == mal_usuario.json()  # no revela cuál de los dos falló


def test_login_no_configurado_responde_503(anonimo):
    assert entrar(anonimo).status_code == 503


def test_login_exige_los_dos_campos_y_limita_su_tamano(anonimo, con_login):
    assert anonimo.post("/api/auth/login", json={"username": "ana"}).status_code == 422
    assert entrar(anonimo, contrasena="x" * 10_000).status_code == 422  # evita cálculos enormes


def test_la_fuerza_bruta_se_frena_con_429(anonimo, con_login):
    for _ in range(5):
        assert entrar(anonimo, contrasena="incorrecta-123456").status_code == 401

    bloqueado = entrar(anonimo, contrasena="incorrecta-123456")
    assert bloqueado.status_code == 429
    assert int(bloqueado.headers["retry-after"]) >= 1
    assert entrar(anonimo).status_code == 429  # ni con la contraseña correcta hasta que pase


# ---------------------------------------------------------------- tokens


def token_de_ana(anonimo):
    return entrar(anonimo).json()["access_token"]


def test_un_token_caducado_se_rechaza(anonimo, con_login, monkeypatch):
    monkeypatch.setattr(settings, "auth_token_minutes", -1)
    token = token_de_ana(anonimo)

    assert anonimo.get("/api/tasks", headers=con_token(token)).status_code == 401


def test_un_token_firmado_con_otra_clave_se_rechaza(anonimo, con_login):
    falso = jwt.encode({"sub": "ana", "exp": time.time() + 600}, "otra-clave" * 4, "HS256")
    assert anonimo.get("/api/tasks", headers=con_token(falso)).status_code == 401


def test_un_token_sin_firma_o_con_otro_algoritmo_se_rechaza(anonimo, con_login):
    sin_firma = jwt.encode({"sub": "ana", "exp": time.time() + 600}, None, algorithm="none")
    otro_algoritmo = jwt.encode({"sub": "ana", "exp": time.time() + 600}, SECRETO, "HS512")

    for token in (sin_firma, otro_algoritmo):
        assert anonimo.get("/api/tasks", headers=con_token(token)).status_code == 401


def test_un_token_sin_caducidad_o_sin_usuario_se_rechaza(anonimo, con_login):
    sin_exp = jwt.encode({"sub": "ana"}, SECRETO, "HS256")
    sin_sub = jwt.encode({"exp": time.time() + 600}, SECRETO, "HS256")

    for token in (sin_exp, sin_sub):
        assert anonimo.get("/api/tasks", headers=con_token(token)).status_code == 401


def test_un_token_manipulado_se_rechaza(anonimo, con_login):
    token = token_de_ana(anonimo)
    cabecera, carga, firma = token.split(".")
    manipulado = ".".join([cabecera, carga[:-2] + "AA", firma])

    assert anonimo.get("/api/tasks", headers=con_token(manipulado)).status_code == 401
    assert anonimo.get("/api/tasks", headers=con_token("no-es-un-token")).status_code == 401


def test_cambiar_la_clave_de_firma_invalida_los_tokens_anteriores(anonimo, con_login, monkeypatch):
    token = token_de_ana(anonimo)
    monkeypatch.setattr(settings, "auth_secret_key", "z" * 40)

    assert anonimo.get("/api/tasks", headers=con_token(token)).status_code == 401


def test_sin_clave_de_firma_ningun_token_es_valido(monkeypatch):
    monkeypatch.setattr(settings, "auth_secret_key", SECRETO)
    token, _ = create_token("ana")
    monkeypatch.setattr(settings, "auth_secret_key", "")

    assert decode_token(token) is None


# ---------------------------------------------------------------- contraseñas


def test_el_hash_se_verifica_y_no_contiene_la_contrasena():
    guardado = hash_password(CONTRASENA)

    assert verify_password(CONTRASENA, guardado)
    assert not verify_password(CONTRASENA + "x", guardado)
    assert CONTRASENA not in guardado and guardado.startswith("scrypt$")


def test_cada_hash_lleva_su_propia_sal():
    assert hash_password(CONTRASENA) != hash_password(CONTRASENA)


MALOS = ["", "texto", "scrypt$a$b", "md5$1$2$3$4$5", "scrypt$1$2$3$!$!"]


@pytest.mark.parametrize("guardado", MALOS)
def test_un_hash_mal_formado_nunca_valida(guardado):
    assert verify_password(CONTRASENA, guardado) is False


# ---------------------------------------------------------------- límite de uso de la IA


def ia_falsa(monkeypatch):
    llamadas = []

    class Mensajes:
        @staticmethod
        def create(**kwargs):
            llamadas.append(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(text="1. Algo")])

    monkeypatch.setattr(settings, "anthropic_api_key", "clave-de-prueba")
    monkeypatch.setattr(ai, "get_client", lambda: SimpleNamespace(messages=Mensajes))
    return llamadas


def test_la_ia_se_limita_por_cliente_y_no_llega_a_claude_al_pasarse(client, monkeypatch):
    monkeypatch.setattr(settings, "ai_rate_limit_per_minute", 2)
    llamadas = ia_falsa(monkeypatch)
    crear(client)

    assert client.post("/api/ai/prioritize").status_code == 200
    assert client.post("/api/ai/prioritize").status_code == 200
    excedida = client.post("/api/ai/prioritize")

    assert excedida.status_code == 429 and int(excedida.headers["retry-after"]) >= 1
    assert len(llamadas) == 2  # la tercera no costó nada


def test_el_limite_de_la_ia_es_independiente_para_cada_cliente(client, anonimo, monkeypatch):
    monkeypatch.setattr(settings, "ai_rate_limit_per_minute", 1)
    monkeypatch.setattr(settings, "api_keys", f"pruebas:{CLAVE_DE_PRUEBAS},otro:{'o' * 40}")
    ia_falsa(monkeypatch)
    crear(client)

    assert client.post("/api/ai/prioritize").status_code == 200
    assert client.post("/api/ai/prioritize").status_code == 429
    otro = anonimo.post("/api/ai/prioritize", headers={"X-API-Key": "o" * 40})
    assert otro.status_code == 200


def test_el_cliente_de_claude_tiene_tiempo_de_espera_y_un_solo_reintento(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "clave-de-prueba")
    monkeypatch.setattr(settings, "anthropic_timeout_seconds", 12.0)
    ai.get_client.cache_clear()
    try:
        cliente = ai.get_client()
        assert cliente.timeout == 12.0 and cliente.max_retries == 1
    finally:
        ai.get_client.cache_clear()


# ---------------------------------------------------------------- desarrollo, cabeceras y docs


def test_con_la_autenticacion_desactivada_en_desarrollo_la_api_queda_abierta(anonimo, monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", True)
    assert anonimo.get("/api/tasks").status_code == 200


def test_las_respuestas_de_la_api_no_se_cachean_ni_se_reinterpretan(client):
    cabeceras = client.get("/api/tasks").headers

    assert cabeceras["x-content-type-options"] == "nosniff"
    assert cabeceras["cache-control"] == "no-store"


def test_la_documentacion_solo_se_publica_en_desarrollo(client):
    assert docs_urls("development")["docs_url"] == "/docs"
    assert client.get("/docs").status_code == 200
    assert docs_urls("production") == {"docs_url": None, "redoc_url": None, "openapi_url": None}


def test_la_documentacion_interactiva_permite_probar_con_credenciales(client):
    esquemas = client.get("/openapi.json").json()["components"]["securitySchemes"]
    assert {"APIKeyHeader", "HTTPBearer"} <= set(esquemas)

