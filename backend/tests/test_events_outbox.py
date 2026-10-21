"""Entrega de eventos a n8n con outbox: orden, reintentos, durabilidad y límites."""

import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.config import settings
from app.constants import OutboxStatus
from app.models import OutboxEventModel
from app.schemas import TaskCreate, TaskUpdate
from app.services import events, task_service
from helpers import crear

URL = "http://n8n.test/webhook/taskflow"


@pytest.fixture()
def reintentos_rapidos(monkeypatch):
    """n8n configurado y esperas de reintento de milisegundos, para pruebas ágiles."""
    monkeypatch.setattr(settings, "n8n_webhook_url", URL)
    monkeypatch.setattr(settings, "events_retry_base_seconds", 0.02)
    monkeypatch.setattr(settings, "events_retry_max_seconds", 0.05)


@pytest.fixture()
def n8n(reintentos_rapidos, monkeypatch):
    """Sustituye el envío HTTP por una lista que acumula lo que recibiría n8n."""
    recibidos = []
    monkeypatch.setattr(events, "send", recibidos.append)
    return recibidos


@contextmanager
def entregar_pendientes(session_factory):
    """Arranca un despachador nuevo ("la API arranca"), espera a que vacíe el outbox y lo para."""
    despachador = events.Dispatcher(session_factory, poll_seconds=0.02)
    despachador.start()
    try:
        assert despachador.drain(timeout=5), "quedaron eventos sin enviar"
        yield despachador
    finally:
        despachador.stop()


def filas(session_factory):
    with session_factory() as db:
        return list(db.scalars(select(OutboxEventModel).order_by(OutboxEventModel.id)))


def esperar(client):
    assert client.app.state.dispatcher.drain(timeout=5), "quedaron eventos sin enviar"


# ---------------------------------------------------------------- ciclo de vida


def test_eventos_del_ciclo_de_vida(client, n8n):
    tarea = crear(client)
    client.patch(f"/api/tasks/{tarea['id']}", json={"status": "done"})
    client.delete(f"/api/tasks/{tarea['id']}")
    esperar(client)

    assert [c["event"] for c in n8n] == ["task.created", "task.completed", "task.deleted"]
    assert n8n[-1]["data"] == {"task_id": tarea["id"], "external_event_id": None}


def test_cambio_de_datos_emite_task_updated_con_los_campos(client, n8n):
    tarea = crear(client)
    client.patch(f"/api/tasks/{tarea['id']}", json={"title": "Nuevo", "priority": 4})
    esperar(client)

    assert [c["event"] for c in n8n] == ["task.created", "task.updated"]
    assert n8n[-1]["data"] == {"task_id": tarea["id"], "changed": ["priority", "title"]}


def test_patch_sin_cambios_no_emite_eventos(client, n8n, session_factory):
    tarea = crear(client, "Igual")
    esperar(client)
    antes = len(filas(session_factory))

    client.patch(f"/api/tasks/{tarea['id']}", json={})
    client.patch(f"/api/tasks/{tarea['id']}", json={"title": "Igual", "status": "todo"})
    client.patch(f"/api/tasks/{tarea['id']}", json={"title": None})

    assert len(filas(session_factory)) == antes


def test_guardar_campos_internos_no_dispara_eventos(client, n8n, session_factory):
    tarea = crear(client)
    esperar(client)
    antes = len(filas(session_factory))

    client.patch(f"/api/tasks/{tarea['id']}", json={"external_event_id": "evt_1"})

    assert len(filas(session_factory)) == antes  # evita el bucle con n8n


def test_sin_url_no_se_anota_nada(client, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", "")
    crear(client)
    assert filas(session_factory) == []


# ---------------------------------------------------------------- orden y datos


def test_los_eventos_salen_en_el_orden_en_que_ocurren(client, n8n):
    for i in range(25):
        tarea = crear(client, f"T{i}")
        client.patch(f"/api/tasks/{tarea['id']}", json={"status": "done"})
    esperar(client)

    assert len(n8n) == 50
    secuencias = [c["sequence"] for c in n8n]
    assert secuencias == sorted(secuencias) and len(set(secuencias)) == 50
    creadas = set()
    for c in n8n:
        if c["event"] == "task.created":
            creadas.add(c["data"]["task_id"])
        else:
            assert c["data"]["task_id"] in creadas


def test_occurred_at_se_fija_al_ocurrir_el_cambio_no_al_enviar(client, n8n, monkeypatch):
    tarea_antes = datetime.now(timezone.utc)
    crear(client)
    tarea_despues = datetime.now(timezone.utc)
    esperar(client)

    ocurrido = datetime.fromisoformat(n8n[0]["occurred_at"])
    assert tarea_antes <= ocurrido <= tarea_despues


def test_la_peticion_no_espera_a_n8n(client, monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", URL)
    monkeypatch.setattr(events, "send", lambda carga: time.sleep(0.4))

    inicio = time.monotonic()
    crear(client)
    assert time.monotonic() - inicio < 0.3  # el envío lento ocurre en segundo plano
    esperar(client)


# ---------------------------------------------------------------- durabilidad (el cambio de P1)


def test_el_evento_queda_guardado_aunque_n8n_este_caido(client, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", URL)
    monkeypatch.setattr(settings, "events_retry_base_seconds", 60)  # sin reintentos en la prueba

    def caido(carga):
        raise ConnectionError("n8n caído")

    monkeypatch.setattr(events, "send", caido)

    tarea = crear(client)
    time.sleep(0.3)

    [fila] = filas(session_factory)
    assert fila.event == "task.created" and fila.data == {"task_id": tarea["id"]}
    assert fila.status == OutboxStatus.PENDING.value
    assert fila.attempts >= 1 and "n8n caído" in fila.last_error


def test_evento_y_tarea_se_confirman_juntos_o_ninguno(db, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", URL)
    task_service.create_task(db, TaskCreate(title="Atómica"))

    def falla_el_commit():
        raise RuntimeError("fallo de la base de datos")

    otra = session_factory()
    monkeypatch.setattr(otra, "commit", falla_el_commit)
    with pytest.raises(RuntimeError):
        task_service.create_task(otra, TaskCreate(title="No se guarda"))
    otra.rollback()
    otra.close()

    with session_factory() as consulta:
        titulos = [t.title for t in consulta.scalars(select(task_service.TaskModel))]
    assert titulos == ["Atómica"]
    assert len(filas(session_factory)) == 1  # solo el evento de la tarea confirmada


def test_los_pendientes_se_envian_al_volver_a_arrancar(db, session_factory, n8n):
    # "La API estaba apagada": se anotan eventos sin ningún despachador en marcha…
    tarea = task_service.create_task(db, TaskCreate(title="Antes del reinicio"))
    task_service.update_task(db, tarea.id, TaskUpdate(status="done"))
    assert n8n == []
    assert len(filas(session_factory)) == 2

    # …y un despachador nuevo ("la API arranca de nuevo") los entrega en orden.
    with entregar_pendientes(session_factory):
        pass

    assert [c["event"] for c in n8n] == ["task.created", "task.completed"]


# ---------------------------------------------------------------- reintentos y límites


def test_reintenta_con_el_mismo_event_id_hasta_conseguirlo(
    db, session_factory, reintentos_rapidos, monkeypatch
):
    intentos = []

    def falla_dos_veces(carga):
        intentos.append(carga)
        if len(intentos) < 3:
            raise ConnectionError("intermitente")

    monkeypatch.setattr(events, "send", falla_dos_veces)
    task_service.create_task(db, TaskCreate(title="x"))

    with entregar_pendientes(session_factory):
        pass

    assert len(intentos) == 3
    assert len({c["event_id"] for c in intentos}) == 1  # misma clave de idempotencia
    [fila] = filas(session_factory)
    assert fila.status == OutboxStatus.SENT.value and fila.attempts == 2 and fila.last_error is None


def test_tras_agotar_los_intentos_pasa_a_dead_y_el_resto_continua(
    db, session_factory, reintentos_rapidos, monkeypatch
):
    monkeypatch.setattr(settings, "events_max_attempts", 3)
    entregados = []

    def rechaza_el_primero(carga):
        if carga["data"]["task_id"] == 1:
            raise ValueError("evento venenoso")
        entregados.append(carga["data"]["task_id"])

    monkeypatch.setattr(events, "send", rechaza_el_primero)
    task_service.create_task(db, TaskCreate(title="Venenosa"))
    task_service.create_task(db, TaskCreate(title="Buena"))

    with entregar_pendientes(session_factory):
        pass

    primera, segunda = filas(session_factory)
    assert primera.status == OutboxStatus.DEAD.value and primera.attempts == 3
    assert "evento venenoso" in primera.last_error
    assert segunda.status == OutboxStatus.SENT.value
    assert entregados == [2]


def test_un_fallo_retrasa_a_los_siguientes_para_conservar_orden(
    db, session_factory, reintentos_rapidos, monkeypatch
):
    orden = []
    intento = {"n": 0}

    def primera_vez_falla(carga):
        intento["n"] += 1
        if intento["n"] == 1:
            raise ConnectionError("fallo puntual")
        orden.append(carga["data"]["task_id"])

    monkeypatch.setattr(events, "send", primera_vez_falla)
    task_service.create_task(db, TaskCreate(title="Primera"))
    task_service.create_task(db, TaskCreate(title="Segunda"))

    with entregar_pendientes(session_factory):
        pass

    assert orden == [1, 2]  # la segunda no se adelantó a la primera


def test_no_envia_nada_si_no_hay_webhook_configurado(db, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", URL)
    task_service.create_task(db, TaskCreate(title="x"))
    monkeypatch.setattr(settings, "n8n_webhook_url", "")  # se quita la configuración
    llamadas = []
    monkeypatch.setattr(events, "send", llamadas.append)

    despachador = events.Dispatcher(session_factory, poll_seconds=0.02)
    despachador.start()
    time.sleep(0.2)
    despachador.stop()

    assert llamadas == []
    assert filas(session_factory)[0].status == OutboxStatus.PENDING.value


# ---------------------------------------------------------------- varios despachadores


def test_varios_despachadores_no_envian_el_mismo_evento_dos_veces(
    db, session_factory, reintentos_rapidos, monkeypatch
):
    """Varios procesos de la API (workers o réplicas) comparten la misma cola de eventos."""
    total = 40
    for i in range(total):
        task_service.create_task(db, TaskCreate(title=f"T{i}"))
    recibidos = []

    def envio_lento(carga):
        time.sleep(0.005)  # latencia de red: da tiempo a que otro despachador intente lo mismo
        recibidos.append(carga["sequence"])

    monkeypatch.setattr(events, "send", envio_lento)
    despachadores = [events.Dispatcher(session_factory, poll_seconds=0.01) for _ in range(3)]
    for d in despachadores:
        d.start()
    try:
        assert despachadores[0].drain(timeout=15), "quedaron eventos sin enviar"
        time.sleep(0.2)  # por si algún despachador estuviera a medio envío
    finally:
        for d in despachadores:
            d.stop()

    assert len(recibidos) == total and len(set(recibidos)) == total  # ninguno repetido
    assert recibidos == sorted(recibidos)  # y en orden


def test_un_evento_reservado_por_otro_despachador_no_se_envia(db, session_factory, n8n):
    task_service.create_task(db, TaskCreate(title="x"))
    with session_factory() as s:
        [fila] = s.scalars(select(OutboxEventModel))
        fila.locked_until = datetime.now(timezone.utc) + timedelta(seconds=60)
        s.commit()

    despachador = events.Dispatcher(session_factory)

    assert despachador.dispatch_next() is False
    assert n8n == []
    assert filas(session_factory)[0].status == OutboxStatus.PENDING.value


def test_una_reserva_vencida_permite_a_otro_despachador_retomar_el_evento(
    db, session_factory, n8n
):
    """Si un proceso muere a mitad de un envío, su reserva caduca y otro entrega el evento."""
    task_service.create_task(db, TaskCreate(title="x"))
    with session_factory() as s:
        [fila] = s.scalars(select(OutboxEventModel))
        fila.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.commit()

    assert events.Dispatcher(session_factory).dispatch_next() is True

    [fila] = filas(session_factory)
    assert len(n8n) == 1
    assert fila.status == OutboxStatus.SENT.value and fila.locked_until is None


def test_el_fallo_libera_la_reserva_para_el_siguiente_intento(
    db, session_factory, reintentos_rapidos, monkeypatch
):
    def caido(carga):
        raise ConnectionError("n8n caído")

    monkeypatch.setattr(events, "send", caido)
    task_service.create_task(db, TaskCreate(title="x"))

    assert events.Dispatcher(session_factory).dispatch_next() is True

    [fila] = filas(session_factory)
    assert fila.status == OutboxStatus.PENDING.value and fila.attempts == 1
    assert fila.locked_until is None  # sin reserva: se podrá reintentar al llegar su turno


# ---------------------------------------------------------------- limpieza y envío HTTP


def test_purga_solo_los_enviados_antiguos(db, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", URL)
    monkeypatch.setattr(settings, "events_retention_days", 7)
    for i in range(3):
        task_service.create_task(db, TaskCreate(title=f"T{i}"))
    viejo, reciente, pendiente = filas(session_factory)
    ahora = datetime.now(timezone.utc)
    with session_factory() as s:
        a, b = s.get(OutboxEventModel, viejo.id), s.get(OutboxEventModel, reciente.id)
        a.status, a.sent_at = OutboxStatus.SENT.value, ahora - timedelta(days=30)
        b.status, b.sent_at = OutboxStatus.SENT.value, ahora - timedelta(days=1)
        s.commit()

    with session_factory() as s:
        assert events.purge_sent(s) == 1

    assert [f.id for f in filas(session_factory)] == [reciente.id, pendiente.id]


def test_la_espera_entre_reintentos_crece_hasta_un_maximo(monkeypatch):
    monkeypatch.setattr(settings, "events_retry_base_seconds", 5)
    monkeypatch.setattr(settings, "events_retry_max_seconds", 60)
    assert [events.retry_delay(n) for n in range(1, 7)] == [5, 10, 20, 40, 60, 60]


def test_send_envia_secreto_y_lanza_excepcion_si_falla(monkeypatch):
    enviados = {}

    def falso_post(url, json, headers, timeout):
        enviados.update(url=url, json=json, headers=headers)
        raise events.httpx.ConnectError("n8n caído")

    monkeypatch.setattr(settings, "n8n_webhook_url", URL)
    monkeypatch.setattr(settings, "n8n_webhook_secret", "s3cr3to")
    monkeypatch.setattr(events.httpx, "post", falso_post)

    with pytest.raises(events.httpx.ConnectError):
        events.send({"event": "task.created", "event_id": "e1", "sequence": 7, "data": {}})

    assert enviados["headers"] == {"X-TaskFlow-Secret": "s3cr3to"}
    assert enviados["json"]["sequence"] == 7


def test_send_trata_una_respuesta_de_error_como_fallo(monkeypatch):
    class Respuesta:
        def raise_for_status(self):
            raise events.httpx.HTTPStatusError("500", request=None, response=None)

    monkeypatch.setattr(settings, "n8n_webhook_url", URL)
    monkeypatch.setattr(events.httpx, "post", lambda *a, **k: Respuesta())

    with pytest.raises(events.httpx.HTTPStatusError):
        events.send({})
