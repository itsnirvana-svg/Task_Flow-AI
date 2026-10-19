"""Pruebas de la capa de servicios y de la configuración de rendimiento."""

import pytest
from sqlalchemy import inspect, select

from app.config import settings
from app.constants import TaskStatus
from app.models import OutboxEventModel
from app.schemas import TaskCreate, TaskUpdate
from app.services import task_service
from app.services.task_service import TaskNotFoundError


def test_crear_y_leer_sin_pasar_por_http(db):
    tarea = task_service.create_task(db, TaskCreate(title="  Desde el servicio  "))

    leida = task_service.get_task(db, tarea.id)

    assert leida.title == "Desde el servicio"
    assert leida.status == TaskStatus.TODO


def test_tarea_inexistente_lanza_error_de_dominio(db):
    with pytest.raises(TaskNotFoundError):
        task_service.get_task(db, 999)
    with pytest.raises(TaskNotFoundError):
        task_service.update_task(db, 999, TaskUpdate(title="x"))
    with pytest.raises(TaskNotFoundError):
        task_service.delete_task(db, 999)


def test_el_servicio_anota_los_eventos_igual_que_la_api(db, monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", "http://n8n.test/webhook/taskflow")

    tarea = task_service.create_task(db, TaskCreate(title="x"))
    task_service.update_task(db, tarea.id, TaskUpdate(status="done"))
    task_service.delete_task(db, tarea.id)

    anotados = [f.event for f in db.scalars(select(OutboxEventModel).order_by(OutboxEventModel.id))]
    assert anotados == ["task.created", "task.completed", "task.deleted"]


def test_el_modelo_define_los_indices_de_las_consultas_habituales(engine):
    indices = {i["name"] for i in inspect(engine).get_indexes("tasks")}
    assert {"idx_tasks_status", "idx_tasks_due_pending"} <= indices


def test_los_listados_grandes_se_comprimen(client):
    for i in range(30):
        client.post("/api/tasks", json={"title": f"Tarea de ejemplo número {i}"})

    respuesta = client.get("/api/tasks", headers={"Accept-Encoding": "gzip"})

    assert respuesta.headers.get("content-encoding") == "gzip"
    assert len(respuesta.json()) == 30  # el cliente lo descomprime de forma transparente
