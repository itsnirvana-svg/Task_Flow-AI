import time
from datetime import datetime
from types import SimpleNamespace

from app.config import ENV_FILE, settings
from app.constants import DESCRIPTION_MAX, TaskStatus
from app.routers import ai
from app.services import events


def crear(client, **campos):
    respuesta = client.post("/api/tasks", json={"title": "Tarea", **campos})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def capturar_envios(monkeypatch):
    """Sustituye el envío HTTP a n8n por una lista de cargas útiles, en orden de salida."""
    cargas = []
    monkeypatch.setattr(settings, "n8n_webhook_url", "http://n8n.test/webhook/taskflow")
    monkeypatch.setattr(events, "send", cargas.append)
    return cargas


def eventos(cargas):
    """Espera a que la cola termine y devuelve [(evento, datos)]."""
    assert events.drain(timeout=5), "la cola de eventos no se vació"
    return [(c["event"], c["data"]) for c in cargas]


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


# ---------------------------------------------------------------- eventos


def test_eventos_del_ciclo_de_vida(client, monkeypatch):  # M3
    cargas = capturar_envios(monkeypatch)

    tarea = crear(client)
    client.patch(f"/api/tasks/{tarea['id']}", json={"status": "done"})
    client.delete(f"/api/tasks/{tarea['id']}")

    recibidos = eventos(cargas)
    assert [e for e, _ in recibidos] == ["task.created", "task.completed", "task.deleted"]
    assert recibidos[-1][1] == {"task_id": tarea["id"], "external_event_id": None}


def test_cambio_de_datos_emite_task_updated_con_los_campos(client, monkeypatch):  # M3
    tarea = crear(client)
    cargas = capturar_envios(monkeypatch)

    client.patch(f"/api/tasks/{tarea['id']}", json={"title": "Nuevo", "priority": 4})

    esperado = {"task_id": tarea["id"], "changed": ["priority", "title"]}
    assert eventos(cargas) == [("task.updated", esperado)]


def test_patch_sin_cambios_no_emite_eventos(client, monkeypatch):  # M3
    tarea = crear(client, title="Igual")
    cargas = capturar_envios(monkeypatch)

    client.patch(f"/api/tasks/{tarea['id']}", json={})
    client.patch(f"/api/tasks/{tarea['id']}", json={"title": "Igual", "status": "todo"})
    client.patch(f"/api/tasks/{tarea['id']}", json={"title": None})  # null ignorado

    assert eventos(cargas) == []


def test_guardar_campos_internos_no_dispara_eventos(client, monkeypatch):  # M3 + A1
    tarea = crear(client)
    cargas = capturar_envios(monkeypatch)

    client.patch(f"/api/tasks/{tarea['id']}", json={"external_event_id": "evt_1"})

    assert eventos(cargas) == []  # evita el bucle: n8n guarda el id y se vuelve a disparar


def test_los_eventos_salen_en_el_orden_en_que_ocurren(client, monkeypatch):  # F1
    cargas = capturar_envios(monkeypatch)

    for i in range(25):
        tarea = crear(client, title=f"T{i}")
        client.patch(f"/api/tasks/{tarea['id']}", json={"status": "done"})

    assert events.drain(timeout=5)
    assert len(cargas) == 50
    secuencias = [c["sequence"] for c in cargas]
    assert secuencias == sorted(secuencias) and len(set(secuencias)) == 50
    # Cada tarea: su task.created siempre antes que su task.completed
    vistos = set()
    for c in cargas:
        tarea_id = c["data"]["task_id"]
        if c["event"] == "task.created":
            vistos.add(tarea_id)
        else:
            assert tarea_id in vistos, "task.completed llegó antes que task.created"


def test_occurred_at_se_fija_al_publicar_no_al_enviar(monkeypatch):  # F1
    cargas = []

    def envio_lento(carga):
        time.sleep(0.3)
        cargas.append(carga)

    monkeypatch.setattr(settings, "n8n_webhook_url", "http://n8n.test/webhook/taskflow")
    monkeypatch.setattr(events, "send", envio_lento)

    antes = datetime.now().astimezone()
    events.publish("task.created", {"task_id": 1})
    despues = datetime.now().astimezone()  # el envío aún no ha terminado

    assert events.drain(timeout=5)
    ocurrido = datetime.fromisoformat(cargas[0]["occurred_at"])
    assert antes <= ocurrido <= despues


def test_publish_no_bloquea_aunque_n8n_tarde(monkeypatch):  # F1
    monkeypatch.setattr(settings, "n8n_webhook_url", "http://n8n.test/webhook/taskflow")
    monkeypatch.setattr(events, "send", lambda carga: time.sleep(0.3))

    inicio = time.monotonic()
    events.publish("task.created", {"task_id": 1})
    assert time.monotonic() - inicio < 0.1
    assert events.drain(timeout=5)


def test_publish_no_hace_nada_sin_url(monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", "")
    cargas = []
    monkeypatch.setattr(events, "send", cargas.append)

    events.publish("task.created", {"task_id": 1})

    assert events.drain(timeout=2)
    assert cargas == []


def test_send_envia_secreto_y_tolera_fallos(monkeypatch):
    enviados = {}

    def falso_post(url, json, headers, timeout):
        enviados.update(url=url, json=json, headers=headers)
        raise events.httpx.ConnectError("n8n caído")

    monkeypatch.setattr(settings, "n8n_webhook_url", "http://n8n.test/webhook/taskflow")
    monkeypatch.setattr(settings, "n8n_webhook_secret", "s3cr3to")
    monkeypatch.setattr(events.httpx, "post", falso_post)

    events.send(events.build_event("task.created", {"task_id": 7}))  # no debe lanzar excepción

    assert enviados["headers"] == {"X-TaskFlow-Secret": "s3cr3to"}
    assert enviados["json"]["event"] == "task.created"
    assert enviados["json"]["data"] == {"task_id": 7}
    assert enviados["json"]["event_id"]
    assert isinstance(enviados["json"]["sequence"], int)


def test_el_hilo_de_envio_sobrevive_a_un_error_inesperado(monkeypatch):
    cargas = []

    def a_veces_falla(carga):
        if carga["data"]["task_id"] == 1:
            raise RuntimeError("fallo inesperado")
        cargas.append(carga)

    monkeypatch.setattr(settings, "n8n_webhook_url", "http://n8n.test/webhook/taskflow")
    monkeypatch.setattr(events, "send", a_veces_falla)

    events.publish("task.created", {"task_id": 1})
    events.publish("task.created", {"task_id": 2})

    assert events.drain(timeout=5)
    assert [c["data"]["task_id"] for c in cargas] == [2]


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
