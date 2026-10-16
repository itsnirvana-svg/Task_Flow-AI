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
| Eventos hacia n8n (`task.created`, `task.updated`, `task.completed`, `task.deleted`) | ✅ Outbox transaccional con reintentos; sobrevive a caídas de n8n y de la API |
| Priorización con IA | 🟡 Implementada; requiere `ANTHROPIC_API_KEY` |
| Dashboard web (`taskflow-web`) | 🟡 Interfaz lista; aún con datos de ejemplo, **sin conectar a la API** |
| Google Calendar | 🔴 Pendiente (las columnas `external_event_id` y `reminded_at` ya existen para él) |
| Autenticación de usuarios, proyectos | 🔴 Pendiente |

## Tecnologías

| Capa | Tecnología |
|---|---|
| Interfaz | HTML5, CSS3 y JavaScript (`taskflow-web`) |
| API | Python 3.10+ y FastAPI |
| Datos | SQLAlchemy 2; SQLite (desarrollo) / PostgreSQL |
| IA | API de Anthropic (Claude) |
| Automatización | n8n (webhooks) |
| Calidad | pytest, ruff, GitHub Actions |
| Empaquetado de la interfaz | rjsmin y rcssmin (`tools/build_web.py`) |

## Instalación

```bash
git clone https://github.com/itsnirvana-svg/Task_Flow-AI.git
cd Task_Flow-AI

cp .env.example .env        # en Windows: copy .env.example .env
# Edita .env. Nunca subas este archivo.

cd backend
python -m venv .venv
.venv\Scripts\activate      # en Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt   # solo producción: requirements.txt
```

## Ejecución

```bash
# API en http://localhost:8000 (documentación interactiva en /docs)
cd backend
uvicorn app.main:app --reload

# Pruebas del backend y de los hooks (desde la raíz del proyecto)
pytest

# Análisis de estilo
ruff check backend/app backend/tests .claude tools
```

Dashboard: abre `taskflow-web/index.html` en el navegador.

### Versión de producción de la interfaz

El código fuente de `taskflow-web` se mantiene legible (11 scripts, CSS con variables). Para publicar,
`tools/build_web.py` genera `taskflow-web/dist/` con los scripts unidos y minificados, el CSS
minificado y nombres con resumen del contenido (`app.<hash>.js`), de modo que el navegador los
guarda en caché y solo los vuelve a descargar si cambian: **de 13 peticiones a 3 y ~36 % menos
bytes comprimidos**.

```bash
pip install -r tools/requirements.txt
python tools/build_web.py
```

### Conectar con n8n

1. En n8n crea un flujo con un nodo **Webhook** (POST) y actívalo.
2. Define `N8N_WEBHOOK_URL` y `N8N_WEBHOOK_SECRET` en `.env`.
3. En el flujo, verifica la cabecera `X-TaskFlow-Secret` antes de continuar.

Cada evento llega con esta forma:

```json
{
  "event": "task.created",
  "event_id": "uuid",
  "sequence": 42,
  "occurred_at": "2026-10-14T17:42:02+00:00",
  "data": { "task_id": 12 }
}
```

### Entrega de eventos (outbox)

Cada evento se guarda en la tabla `event_outbox` **en la misma transacción** que el cambio de la
tarea, y un despachador en segundo plano lo envía a n8n:

| Situación | Qué ocurre |
|---|---|
| n8n responde | El evento pasa a `sent` |
| n8n cae, tarda o devuelve error | El evento sigue en la base de datos y se **reintenta** con espera creciente (5 s, 10 s, 20 s… hasta 15 min) |
| Se agotan los intentos (8 por defecto) | Pasa a `dead` (queda como evidencia) y el resto continúa |
| La API se reinicia o se cae | Los pendientes se envían al volver a arrancar: **no se pierde ninguno** |
| n8n colgado | Las peticiones a la API no se ven afectadas |

Los ajustes (`EVENTS_MAX_ATTEMPTS`, `EVENTS_RETRY_BASE_SECONDS`, `EVENTS_RETRY_MAX_SECONDS`,
`EVENTS_RETENTION_DAYS`) están en `.env.example`. Para ver el estado de la cola:

```sql
SELECT status, count(*) FROM event_outbox GROUP BY status;
```

| Evento | Cuándo se emite |
|---|---|
| `task.created` | Al crear una tarea |
| `task.completed` | Al pasar a `done` (no se emite además `task.updated`) |
| `task.updated` | Cuando cambian otros datos; `data.changed` lista los campos |
| `task.deleted` | Al eliminar; incluye `external_event_id` para borrar el evento de Calendar |

`occurred_at` se fija **cuando ocurre el cambio**, y `sequence` es el identificador creciente del
evento en el outbox (sobrevive a reinicios). La entrega es **al menos una vez** y en orden: tras
un fallo (por ejemplo, n8n recibió el evento pero tardó más de 5 s en responder) el mismo evento
puede llegar **dos veces con el mismo `event_id`**. Por eso los flujos de n8n deben **descartar
los `event_id` ya procesados** y **consultar `GET /api/tasks/{id}`** para conocer el estado
actual en lugar de fiarse solo del evento.

Un `PATCH` que no cambia nada, o que solo guarda `external_event_id` / `reminded_at`
(campos que escriben las automatizaciones), no emite eventos, para evitar bucles.

## Estructura

```text
Task_Flow-AI/
├── backend/
│   ├── app/
│   │   ├── main.py              # aplicación, CORS, compresión y arranque
│   │   ├── config.py            # variables de entorno
│   │   ├── constants.py         # estados, límites y tamaños de página
│   │   ├── database.py          # motor, sesión y alias DbSession
│   │   ├── models.py            # modelo de tarea e índices
│   │   ├── schemas.py           # validación de entrada y salida
│   │   ├── routers/             # capa HTTP, fina: tasks.py, ai.py
│   │   └── services/            # lógica reutilizable
│   │       ├── task_service.py  #   reglas de las tareas (estado, eventos)
│   │       └── events.py        #   outbox: registro y despachador de eventos a n8n
│   ├── db/
│   │   ├── schema.sql           # esquema completo (PostgreSQL)
│   │   └── migrations/          # migraciones para bases existentes
│   ├── tests/                   # pruebas (helpers.py y conftest.py son comunes)
│   ├── requirements.txt         # producción
│   └── requirements-dev.txt     # pruebas y lint
├── taskflow-web/                # dashboard HTML/CSS/JS (ver su README)
│   └── js/{lib,components}/     #   utilidades y componentes reutilizables
├── tools/
│   ├── build_web.py             # genera taskflow-web/dist (unir, minificar, caché)
│   ├── requirements.txt         # minificadores
│   └── n8n-test/                # página para probar el webhook a mano
├── .claude/hooks/               # guardian, revisión de calidad, patrones comunes y pruebas
├── .github/workflows/ci.yml     # lint, pruebas, hooks, empaquetado de la interfaz y SQL
├── pyproject.toml               # configuración común de pytest y ruff
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
2. Haz commits pequeños y, desde la raíz, ejecuta `pytest` y
   `ruff check backend/app backend/tests .claude tools`.
3. Abre un Pull Request; el CI debe quedar en verde.

## Licencia

[Apache-2.0](LICENSE)
