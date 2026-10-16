# TaskFlow AI

> Gestor de tareas con asistencia de inteligencia artificial y automatizaciones.

![Estado](https://img.shields.io/badge/estado-en%20desarrollo-yellow)
![Licencia](https://img.shields.io/badge/licencia-Apache--2.0-blue)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)

## Descripción

**TaskFlow AI** es una aplicación para organizar tareas. Una API en FastAPI guarda las tareas,
Claude (Anthropic) sugiere en qué orden abordarlas, y n8n ejecuta automatizaciones cuando algo
ocurre (tarea creada, completada, eliminada).

## Estado del proyecto

| Componente | Estado |
|---|---|
| API REST de tareas (crear, listar con filtros y paginación, editar, eliminar) | ✅ Funciona; con SQLite en desarrollo |
| Persistencia | ✅ SQLAlchemy; SQLite por defecto, PostgreSQL con `DATABASE_URL` |
| Eventos hacia n8n (`task.created`, `task.updated`, `task.completed`, `task.deleted`) | ✅ Implementado y probado con simulación |
| Priorización con IA | 🟡 Implementada; requiere `ANTHROPIC_API_KEY` |
| Dashboard web (`taskflow-web`) | 🟡 Interfaz lista; aún con datos de ejemplo, **sin conectar a la API** |
| Google Calendar | 🔴 Esqueleto (`CalendarService`) |
| Autenticación de usuarios, proyectos | 🔴 Pendiente |

## Tecnologías

| Capa | Tecnología |
|---|---|
| Interfaz | HTML5, CSS3 y JavaScript (`taskflow-web`) |
| API | Python 3.10+ y FastAPI |
| Datos | SQLAlchemy 2; SQLite (desarrollo) / PostgreSQL |
| IA | API de Anthropic (Claude) |
| Automatización | n8n (webhooks) |
| Calidad | pytest, GitHub Actions |

## Instalación

```bash
git clone https://github.com/itsnirvana-svg/Task_Flow-AI.git
cd Task_Flow-AI

cp .env.example .env        # en Windows: copy .env.example .env
# Edita .env. Nunca subas este archivo.

cd backend
python -m venv .venv
.venv\Scripts\activate      # en Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecución

```bash
# API en http://localhost:8000 (documentación interactiva en /docs)
cd backend
uvicorn app.main:app --reload

# Pruebas
pytest
```

Dashboard: abre `taskflow-web/index.html` en el navegador.

### Conectar con n8n

1. En n8n crea un flujo con un nodo **Webhook** (POST) y actívalo.
2. Define `N8N_WEBHOOK_URL` y `N8N_WEBHOOK_SECRET` en `.env`.
3. En el flujo, verifica la cabecera `X-TaskFlow-Secret` antes de continuar.

Cada evento llega con esta forma:

```json
{
  "event": "task.created",
  "event_id": "uuid",
  "occurred_at": "2026-10-14T17:42:02+00:00",
  "data": { "task_id": 12 }
}
```

El envío es en segundo plano: si n8n no responde, la API no se ve afectada.

| Evento | Cuándo se emite |
|---|---|
| `task.created` | Al crear una tarea |
| `task.completed` | Al pasar a `done` (no se emite además `task.updated`) |
| `task.updated` | Cuando cambian otros datos; `data.changed` lista los campos |
| `task.deleted` | Al eliminar; incluye `external_event_id` para borrar el evento de Calendar |

Un `PATCH` que no cambia nada, o que solo guarda `external_event_id` / `reminded_at`
(campos que escriben las automatizaciones), no emite eventos, para evitar bucles.

## Estructura

```text
Task_Flow-AI/
├── backend/
│   ├── app/
│   │   ├── main.py              # aplicación, CORS y arranque
│   │   ├── config.py            # variables de entorno
│   │   ├── database.py          # motor y sesión de SQLAlchemy
│   │   ├── models.py            # modelo de tarea
│   │   ├── schemas.py           # validación de entrada y salida
│   │   ├── routers/             # tasks.py, ai.py
│   │   └── services/            # events.py (n8n), calendar_service.py
│   ├── db/
│   │   ├── schema.sql           # esquema completo (PostgreSQL)
│   │   └── migrations/          # migraciones para bases existentes
│   └── tests/
├── taskflow-web/                # dashboard HTML/CSS/JS
├── n8n-test/                    # página para probar el webhook
├── .claude/hooks/               # guardian.py, revisar_calidad.py (opcionales)
├── .github/workflows/ci.yml     # tests y validación del SQL
├── _archivo/                    # material descartado, conservado por si acaso
├── .env.example
├── LICENSE
└── README.md
```

## Modelo de datos de una tarea

| Campo | Valores |
|---|---|
| `status` | `todo`, `in_progress`, `done` |
| `priority` | 1 (baja) a 4 (urgente) |
| `completed_at` | Se rellena solo al pasar a `done`, y se limpia al reabrir |

## Contribuir

1. Crea una rama: `git switch -c feat/mi-mejora`.
2. Haz commits pequeños y ejecuta `pytest`.
3. Abre un Pull Request; el CI debe quedar en verde.

## Licencia

[Apache-2.0](LICENSE)
