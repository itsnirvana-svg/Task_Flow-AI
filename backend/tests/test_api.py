from types import SimpleNamespace

from app.config import settings
from app.routers import ai
from app.services import events


def crear(client, **campos):
    respuesta = client.post("/api/tasks", json={"title": "Tarea", **campos})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


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


def test_completar_y_reabrir_mantiene_completed_at(client):
    tarea = crear(client)

    hecha = client.patch(f"/api/tasks/{tarea['id']}", json={"status": "done"}).json()
    assert hecha["status"] == "done"
    assert hecha["completed_at"] is not None

    reabierta = client.patch(f"/api/tasks/{tarea['id']}", json={"status": "in_progress"}).json()
    assert reabierta["completed_at"] is None


def test_crear_ya_completada_rellena_completed_at(client):
    assert crear(client, status="done")["completed_at"] is not None


def test_listado_filtra_y_pagina(client):
    for i in range(5):
        crear(client, title=f"T{i}", status="done" if i < 2 else "todo")

    assert len(client.get("/api/tasks").json()) == 5
    assert len(client.get("/api/tasks", params={"status": "done"}).json()) == 2
    assert len(client.get("/api/tasks", params={"limit": 2, "offset": 1}).json()) == 2
    assert client.get("/api/tasks", params={"limit": 0}).status_code == 422


def test_eliminar_y_404(client):
    tarea = crear(client)
    assert client.delete(f"/api/tasks/{tarea['id']}").status_code == 204
    assert client.get(f"/api/tasks/{tarea['id']}").status_code == 404
    assert client.patch(f"/api/tasks/{tarea['id']}", json={"title": "x"}).status_code == 404
    assert client.delete(f"/api/tasks/{tarea['id']}").status_code == 404


def test_eventos_se_emiten_en_cada_cambio(client, monkeypatch):
    emitidos = []
    monkeypatch.setattr(events, "emit", lambda evento, datos: emitidos.append((evento, datos)))

    tarea = crear(client)
    client.patch(f"/api/tasks/{tarea['id']}", json={"status": "done"})
    client.delete(f"/api/tasks/{tarea['id']}")

    nombres = [e for e, _ in emitidos]
    assert nombres == ["task.created", "task.updated", "task.completed", "task.deleted"]
    assert emitidos[-1][1]["task_id"] == tarea["id"]


def test_emit_no_hace_nada_sin_url(monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", "")
    assert events.emit("task.created", {"task_id": 1}) is None


def test_emit_envia_secreto_y_tolera_fallos(monkeypatch):
    enviados = {}

    def falso_post(url, json, headers, timeout):
        enviados.update(url=url, json=json, headers=headers)
        raise events.httpx.ConnectError("n8n caído")

    monkeypatch.setattr(settings, "n8n_webhook_url", "http://n8n.test/webhook/taskflow")
    monkeypatch.setattr(settings, "n8n_webhook_secret", "s3cr3to")
    monkeypatch.setattr(events.httpx, "post", falso_post)

    events.emit("task.created", {"task_id": 7})  # no debe lanzar excepción

    assert enviados["headers"] == {"X-TaskFlow-Secret": "s3cr3to"}
    assert enviados["json"]["event"] == "task.created"
    assert enviados["json"]["data"] == {"task_id": 7}
    assert enviados["json"]["event_id"]


def test_ia_sin_clave_devuelve_503(client, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert client.post("/api/ai/prioritize").status_code == 503


def test_ia_usa_solo_tareas_pendientes(client, monkeypatch):
    crear(client, title="Pendiente A", priority=3)
    crear(client, title="Ya hecha", status="done")
    prompts = []

    class ClienteFalso:
        class messages:
            @staticmethod
            def create(**kwargs):
                prompts.append(kwargs["messages"][0]["content"])
                return SimpleNamespace(content=[SimpleNamespace(text="1. Pendiente A")])

    monkeypatch.setattr(settings, "anthropic_api_key", "clave-de-prueba")
    monkeypatch.setattr(ai, "get_client", lambda: ClienteFalso)

    respuesta = client.post("/api/ai/prioritize")
    assert respuesta.status_code == 200
    assert respuesta.json()["suggestion"] == "1. Pendiente A"
    assert "Pendiente A" in prompts[0]
    assert "Ya hecha" not in prompts[0]


def test_ia_error_externo_devuelve_502(client, monkeypatch):
    crear(client, title="Algo")

    class ClienteRoto:
        class messages:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("timeout")

    monkeypatch.setattr(settings, "anthropic_api_key", "clave-de-prueba")
    monkeypatch.setattr(ai, "get_client", lambda: ClienteRoto)

    assert client.post("/api/ai/prioritize").status_code == 502
