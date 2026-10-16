from types import SimpleNamespace

from app.config import ENV_FILE, settings
from app.constants import DESCRIPTION_MAX, TaskStatus
from app.routers import ai
from helpers import crear

# ---------------------------------------------------------------- tareas


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_crear_aplica_valores_por_defecto(client):
    tarea = crear(client, title="Escribir README")
    assert tarea["status"] == "todo"
    assert tarea["priority"] == 2
    assert tarea["completed_at"] is None


def test_validacion_rechaza_datos_invalidos(client):
    assert client.post("/api/tasks", json={"title": ""}).status_code == 422
    assert client.post("/api/tasks", json={"title": "x", "priority": 9}).status_code == 422
    assert client.post("/api/tasks", json={"title": "x", "status": "hecho"}).status_code == 422


def test_titulo_solo_con_espacios_se_rechaza(client):  # A2
    assert client.post("/api/tasks", json={"title": "     "}).status_code == 422
    tarea = crear(client)
    assert client.patch(f"/api/tasks/{tarea['id']}", json={"title": "   "}).status_code == 422


def test_titulo_se_guarda_sin_espacios_sobrantes(client):  # A2
    assert crear(client, title="  Informe semanal  ")["title"] == "Informe semanal"


def test_descripcion_tiene_limite(client):  # M2
    assert crear(client, description="a" * DESCRIPTION_MAX)["description"]
    demasiado_larga = "a" * (DESCRIPTION_MAX + 1)
    respuesta = client.post("/api/tasks", json={"title": "x", "description": demasiado_larga})
    assert respuesta.status_code == 422


def test_completar_y_reabrir_mantiene_completed_at(client):
    tarea = crear(client)

    hecha = client.patch(f"/api/tasks/{tarea['id']}", json={"status": "done"}).json()
    assert hecha["status"] == "done"
    assert hecha["completed_at"] is not None

    reabierta = client.patch(f"/api/tasks/{tarea['id']}", json={"status": "in_progress"}).json()
    assert reabierta["completed_at"] is None


def test_crear_ya_completada_rellena_completed_at(client):
    assert crear(client, status="done")["completed_at"] is not None


def test_fechas_incluyen_zona_horaria_utc(client):  # M1
    tarea = crear(client, status="done")
    for campo in ("created_at", "updated_at", "completed_at"):
        assert tarea[campo].endswith("Z"), f"{campo} sin zona horaria: {tarea[campo]}"


def test_listado_filtra_y_pagina(client):
    for i in range(5):
        crear(client, title=f"T{i}", status="done" if i < 2 else "todo")

    assert len(client.get("/api/tasks").json()) == 5
    assert len(client.get("/api/tasks", params={"status": "done"}).json()) == 2
    assert len(client.get("/api/tasks", params={"limit": 2, "offset": 1}).json()) == 2
    assert client.get("/api/tasks", params={"limit": 0}).status_code == 422


def test_filtro_de_estado_invalido_devuelve_422(client):  # M4
    assert client.get("/api/tasks", params={"status": "hecho"}).status_code == 422


def test_estados_del_enum_son_los_de_la_base_de_datos():  # M4
    assert {s.value for s in TaskStatus} == {"todo", "in_progress", "done"}
    esquema = (ENV_FILE.parent / "backend" / "db" / "schema.sql").read_text(encoding="utf-8")
    for estado in TaskStatus:
        assert f"'{estado.value}'" in esquema


def test_eliminar_y_404(client):
    tarea = crear(client)
    assert client.delete(f"/api/tasks/{tarea['id']}").status_code == 204
    assert client.get(f"/api/tasks/{tarea['id']}").status_code == 404
    assert client.patch(f"/api/tasks/{tarea['id']}", json={"title": "x"}).status_code == 404
    assert client.delete(f"/api/tasks/{tarea['id']}").status_code == 404


# ---------------------------------------------------- campos de automatización (A1)


def test_automatizaciones_pueden_guardar_el_id_del_evento(client):  # A1
    tarea = crear(client)
    ahora = "2026-10-16T08:00:00Z"

    respuesta = client.patch(
        f"/api/tasks/{tarea['id']}", json={"external_event_id": "evt_abc", "reminded_at": ahora}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["external_event_id"] == "evt_abc"
    assert respuesta.json()["reminded_at"].startswith("2026-10-16T08:00:00")
    leida = client.get(f"/api/tasks/{tarea['id']}").json()
    assert leida["external_event_id"] == "evt_abc"


def test_se_puede_limpiar_el_id_del_evento(client):  # A1
    tarea = crear(client)
    client.patch(f"/api/tasks/{tarea['id']}", json={"external_event_id": "evt_abc"})
    limpia = client.patch(f"/api/tasks/{tarea['id']}", json={"external_event_id": None})
    assert limpia.json()["external_event_id"] is None


# ---------------------------------------------------------------- IA


def cliente_ia(contenido=None, error=None):
    class Falso:
        class messages:
            @staticmethod
            def create(**kwargs):
                if error:
                    raise error
                Falso.prompt = kwargs["messages"][0]["content"]
                return SimpleNamespace(content=contenido)

    return Falso


def test_ia_sin_clave_devuelve_503(client, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert client.post("/api/ai/prioritize").status_code == 503


def test_ia_usa_solo_tareas_pendientes(client, monkeypatch):
    crear(client, title="Pendiente A", priority=3)
    crear(client, title="Ya hecha", status="done")
    falso = cliente_ia([SimpleNamespace(text="1. Pendiente A")])
    monkeypatch.setattr(settings, "anthropic_api_key", "clave-de-prueba")
    monkeypatch.setattr(ai, "get_client", lambda: falso)

    respuesta = client.post("/api/ai/prioritize")

    assert respuesta.status_code == 200
    assert respuesta.json()["suggestion"] == "1. Pendiente A"
    assert "Pendiente A" in falso.prompt
    assert "Ya hecha" not in falso.prompt


def test_ia_une_varios_bloques_de_texto(client, monkeypatch):
    crear(client)
    falso = cliente_ia([SimpleNamespace(text="Parte 1. "), SimpleNamespace(text="Parte 2.")])
    monkeypatch.setattr(settings, "anthropic_api_key", "clave-de-prueba")
    monkeypatch.setattr(ai, "get_client", lambda: falso)

    assert client.post("/api/ai/prioritize").json()["suggestion"] == "Parte 1. Parte 2."


def test_ia_respuesta_vacia_devuelve_502_y_no_500(client, monkeypatch):  # A3
    crear(client)
    monkeypatch.setattr(settings, "anthropic_api_key", "clave-de-prueba")
    monkeypatch.setattr(ai, "get_client", lambda: cliente_ia([]))

    assert client.post("/api/ai/prioritize").status_code == 502


def test_ia_error_externo_devuelve_502(client, monkeypatch):
    crear(client, title="Algo")
    monkeypatch.setattr(settings, "anthropic_api_key", "clave-de-prueba")
    monkeypatch.setattr(ai, "get_client", lambda: cliente_ia(error=RuntimeError("timeout")))

    assert client.post("/api/ai/prioritize").status_code == 502


# ---------------------------------------------------------------- configuración


def test_el_env_se_busca_en_la_raiz_del_proyecto_sin_depender_del_cwd():  # M5
    assert ENV_FILE.is_absolute()
    assert ENV_FILE.name == ".env"
    assert (ENV_FILE.parent / "backend" / "app").is_dir()
