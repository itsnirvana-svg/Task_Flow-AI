<div align="center">

# TaskFlow AI

**Gestor de tareas con priorización por inteligencia artificial y automatizaciones.**

![Estado](https://img.shields.io/badge/estado-en%20desarrollo-yellow)
![Versión](https://img.shields.io/badge/versión-0.2.0-informational)
![Licencia](https://img.shields.io/badge/licencia-Apache--2.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![CI](https://github.com/itsnirvana-svg/Task_Flow-AI/actions/workflows/ci.yml/badge.svg)

</div>

## Índice

1. [Descripción del proyecto](#descripción-del-proyecto)
2. [Características principales](#características-principales)
3. [Tecnologías utilizadas](#tecnologías-utilizadas)
4. [Requisitos de instalación](#requisitos-de-instalación)
5. [Pasos para ejecutar el proyecto](#pasos-para-ejecutar-el-proyecto)
6. [Estructura de carpetas](#estructura-de-carpetas)
7. [Integraciones implementadas](#integraciones-implementadas)
8. [Despliegue](#despliegue)
9. [Capturas sugeridas](#capturas-sugeridas)
10. [Contribuir](#contribuir)
11. [Autor](#autor)
12. [Licencia](#licencia)

## Descripción del proyecto

**TaskFlow AI** es una aplicación para organizar tareas. Una API en FastAPI guarda las tareas,
Claude (Anthropic) sugiere en qué orden abordarlas, y n8n ejecuta automatizaciones cuando algo
ocurre (tarea creada, completada, eliminada). Un dashboard web ofrece la vista de trabajo diaria.
Cómo encajan las piezas, con diagramas: [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

### Estado del proyecto

| Componente | Estado |
|---|---|
| API REST de tareas (crear, listar con filtros y paginación, editar, eliminar) | ✅ Funciona; con SQLite en desarrollo |
| Persistencia | ✅ SQLAlchemy; SQLite por defecto, PostgreSQL con `DATABASE_URL` |
| Eventos hacia n8n (`task.created`, `task.updated`, `task.completed`, `task.deleted`) | ✅ Outbox transaccional con reintentos; sobrevive a caídas de n8n y de la API |
| Priorización con IA | 🟡 Implementada; requiere `ANTHROPIC_API_KEY` |
| Dashboard web (`taskflow-web`) | 🟡 Cinco vistas funcionando y desplegado en Vercel; aún con datos de ejemplo, **sin conectar a la API** |
| Integración continua | ✅ GitHub Actions: lint y pruebas, empaquetado de la interfaz y sintaxis SQL |
| Google Calendar | 🔴 Pendiente (las columnas `external_event_id` y `reminded_at` ya existen para él) |
| Autenticación de usuarios | 🔴 Pendiente |

## Características principales

- **API REST de tareas** con filtros, paginación y validación estricta de entrada.
- **Priorización con IA**: Claude ordena las tareas pendientes y explica brevemente el porqué.
- **Eventos fiables hacia n8n**: patrón *outbox* transaccional con reintentos y espera creciente; no
  se pierde ningún evento aunque n8n o la propia API se caigan.
- **Dashboard con cinco vistas** (Dashboard, Tareas, Proyectos, Calendario y Configuración), tema
  claro/oscuro, navegación con atrás/adelante y enlaces directos.
- **Configuración por entorno**: en producción la aplicación **se niega a arrancar** si alguna
  conexión apunta a un entorno de desarrollo o de prueba.
- **Interfaz segura**: política CSP estricta, sin `innerHTML` ni estilos en línea, sin dependencias.
- **Calidad automatizada**: pruebas con pytest, análisis con ruff y CI en GitHub Actions.

## Tecnologías utilizadas

| Capa | Tecnología |
|---|---|
| Interfaz | HTML5, CSS3 y JavaScript sin dependencias (`taskflow-web`) |
| API | Python 3.10+ y FastAPI |
| Datos | SQLAlchemy 2; SQLite (desarrollo) / PostgreSQL con `psycopg` (producción) |
| IA | API de Anthropic (Claude) |
| Automatización | n8n (webhooks) |
| Calidad | pytest, ruff, GitHub Actions |
| Empaquetado de la interfaz | rjsmin y rcssmin (`tools/build_web.py`) |
| Alojamiento de la interfaz | Vercel (sitio estático) |

## Requisitos de instalación

| Requisito | Versión | Para qué |
|---|---|---|
| [Python](https://www.python.org/downloads/) | 3.10 o superior | API, pruebas y empaquetado |
| [Git](https://git-scm.com/downloads) | Cualquiera reciente | Clonar el repositorio |
| Navegador moderno | Chrome, Edge, Firefox o Safari actuales | Dashboard |
| [Node.js](https://nodejs.org/) y n8n | Node 18 o superior | Opcional: automatizaciones (`npm install -g n8n`) |
| Clave de [Anthropic](https://console.anthropic.com/) | | Opcional: priorización con IA |
| PostgreSQL | 14 o superior | Opcional: solo en producción |

## Pasos para ejecutar el proyecto

### 1. Clonar e instalar

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

### 2. Arrancar la API

```bash
# Desde backend/. API en http://localhost:8000 (documentación interactiva en /docs)
uvicorn app.main:app --reload
```

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/tasks` | Lista con filtros y paginación |
| `GET` | `/api/tasks/{id}` | Detalle de una tarea |
| `POST` | `/api/tasks` | Crea una tarea |
| `PATCH` | `/api/tasks/{id}` | Edita una tarea |
| `DELETE` | `/api/tasks/{id}` | Elimina una tarea |
| `POST` | `/api/ai/prioritize` | Prioriza las tareas con Claude |

### 3. Abrir el dashboard

Abre `taskflow-web/index.html` en el navegador (doble clic). No requiere instalar nada.

### 4. Pruebas y análisis de estilo

```bash
# Desde la raíz del proyecto
pytest
ruff check backend/app backend/tests .claude tools
```

### Configuración

Toda la configuración se lee de variables de entorno o del archivo `.env` (plantilla completa y
comentada en `.env.example`). Hay dos perfiles, que se eligen con `APP_ENV`:

| Variable | Desarrollo (por defecto) | Producción (`APP_ENV=production`) |
|---|---|---|
| `DATABASE_URL` | SQLite local (`sqlite:///./taskflow.db`) | PostgreSQL (`postgres://` y `postgresql://` se aceptan) |
| `CORS_ORIGINS` | `http://localhost:5500` | Los dominios reales, solo con `https://` |
| `N8N_WEBHOOK_URL` | Vacío (no se envían eventos) | Opcional; si se define: `https://…/webhook/…`, no local ni `/webhook-test/` |
| `N8N_WEBHOOK_SECRET` | Vacío | Obligatorio si hay `N8N_WEBHOOK_URL` |
| `ANTHROPIC_API_KEY` | Vacía (la IA responde 503) | La clave real |

**En producción la aplicación no arranca si alguna conexión apunta a un entorno de desarrollo o de
prueba** (SQLite, `localhost`, `/webhook-test/`, direcciones sin `https`, secreto ausente) y el
mensaje de error indica qué corregir.

### Versión de producción de la interfaz

El código fuente de `taskflow-web` se mantiene legible (17 scripts, CSS con variables). Para publicar,
`tools/build_web.py` genera `taskflow-web/dist/` con los scripts unidos y minificados, el CSS
minificado y nombres con resumen del contenido (`assets/app.<hash>.js`), de modo que el navegador
los guarda en caché y solo los vuelve a descargar si cambian: **de 19 peticiones a 3**.

```bash
pip install -r tools/requirements.txt
python tools/build_web.py
```

## Estructura de carpetas

```text
Task_Flow-AI/
├── backend/
│   ├── app/
│   │   ├── main.py              # aplicación, CORS, compresión y arranque
│   │   ├── config.py            # variables de entorno y validación por perfil
│   │   ├── constants.py         # estados, límites y tamaños de página
│   │   ├── database.py          # motor, sesión y alias DbSession
│   │   ├── models.py            # modelo de tarea, índices y tabla outbox
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
│   ├── test_build_web.py        # pruebas del empaquetado, vercel.json y el menú
│   ├── requirements.txt         # minificadores
│   └── n8n-test/                # página para probar el webhook a mano
├── docs/ARQUITECTURA.md         # arquitectura: capas, n8n, base de datos y flujos (con diagramas)
├── .claude/hooks/               # guardian, revisión de calidad, patrones comunes y pruebas
├── .github/workflows/ci.yml     # lint, pruebas, hooks, empaquetado de la interfaz y SQL
├── vercel.json                  # despliegue de la interfaz: construcción, CSP y caché
├── pyproject.toml               # configuración común de pytest y ruff
├── .env.example
├── LICENSE
└── README.md
```

### Modelo de datos de una tarea

| Campo | Valores |
|---|---|
| `status` | `todo`, `in_progress`, `done` |
| `priority` | 1 (baja) a 4 (urgente) |
| `completed_at` | Se rellena solo al pasar a `done`, y se limpia al reabrir |

## Integraciones implementadas

| Integración | Estado | Detalle |
|---|---|---|
| **n8n** | ✅ | Eventos de tareas por webhook, con secreto en la cabecera `X-TaskFlow-Secret` |
| **Anthropic (Claude)** | 🟡 | `POST /api/ai/prioritize`; modelo configurable con `ANTHROPIC_MODEL` |
| **PostgreSQL** | ✅ | Controlador `psycopg`; `schema.sql` validado en el CI |
| **GitHub Actions** | ✅ | Tres trabajos: lint y pruebas, empaquetado de la interfaz y sintaxis SQL |
| **Vercel** | ✅ | Solo la interfaz (sitio estático) |
| **Google Calendar** | 🔴 | Pendiente; las columnas necesarias ya existen |

### Conectar con n8n

1. En n8n crea un flujo con un nodo **Webhook** (POST) y actívalo.
2. Define `N8N_WEBHOOK_URL` y `N8N_WEBHOOK_SECRET` en `.env`.
3. En el flujo, verifica la cabecera `X-TaskFlow-Secret` antes de continuar (nodo Webhook →
   *Authentication* → *Header Auth*).

La ruta del webhook debe coincidir con el *Path* del nodo Webhook de n8n y ser la de producción
(`/webhook/...`): la de pruebas (`/webhook-test/...`) solo atiende una petición después de pulsar
*Listen for test event*.

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

| Evento | Cuándo se emite |
|---|---|
| `task.created` | Al crear una tarea |
| `task.completed` | Al pasar a `done` (no se emite además `task.updated`) |
| `task.updated` | Cuando cambian otros datos; `data.changed` lista los campos |
| `task.deleted` | Al eliminar; incluye `external_event_id` para borrar el evento de Calendar |

### Entrega de eventos (outbox)

Cada evento se guarda en la tabla `event_outbox` **en la misma transacción** que el cambio de la
tarea, y un despachador en segundo plano lo envía a n8n:

| Situación | Qué ocurre |
|---|---|
| n8n responde | El evento pasa a `sent` |
| n8n cae, tarda o devuelve error | El evento sigue en la base de datos y se **reintenta** con espera creciente (5 s, 10 s, 20 s…; tope configurable de 15 min) |
| Se agotan los intentos (8 por defecto, unos 10 minutos en total) | Pasa a `dead` (queda como evidencia) y el resto continúa |
| La API se reinicia o se cae | Los pendientes se envían al volver a arrancar: **no se pierde ninguno** |
| n8n colgado | Las peticiones a la API no se ven afectadas |

Los ajustes (`EVENTS_MAX_ATTEMPTS`, `EVENTS_RETRY_BASE_SECONDS`, `EVENTS_RETRY_MAX_SECONDS`,
`EVENTS_RETENTION_DAYS`) están en `.env.example`. Para ver el estado de la cola:

```sql
SELECT status, count(*) FROM event_outbox GROUP BY status;
```

`occurred_at` se fija **cuando ocurre el cambio**, y `sequence` es el identificador creciente del
evento en el outbox (sobrevive a reinicios). La entrega es **al menos una vez** y en orden: tras
un fallo (por ejemplo, n8n recibió el evento pero tardó más de 5 s en responder) el mismo evento
puede llegar **dos veces con el mismo `event_id`**. Por eso los flujos de n8n deben **descartar
los `event_id` ya procesados** y **consultar `GET /api/tasks/{id}`** para conocer el estado
actual en lugar de fiarse solo del evento.

Un `PATCH` que no cambia nada, o que solo guarda `external_event_id` / `reminded_at`
(campos que escriben las automatizaciones), no emite eventos, para evitar bucles.

## Despliegue

### Interfaz en Vercel

La interfaz (`taskflow-web`) es un sitio estático y se publica en Vercel tal cual. `vercel.json` ya
define todo lo necesario:

| Ajuste | Valor |
|---|---|
| Framework | Ninguno (`Other`, sitio estático) |
| Comando de construcción | `python3 tools/build_web.py` (Vercel incluye Python 3.12) |
| Instalación | `pip install -r tools/requirements.txt`; si falla, construye igualmente sin minificar |
| Carpeta de salida | `taskflow-web/dist` |
| Cabeceras | CSP estricta (`script-src 'self'`, `style-src 'self'`, sin marcos), `nosniff`, `Referrer-Policy`, `Permissions-Policy` |
| Caché | `assets/*` (nombres con resumen del contenido) con `immutable` y un año |

Pasos: importa el repositorio en Vercel, elige el *Application Preset* **Other** (Vercel puede
proponer *Services* por detectar `backend/`: no lo uses), deja el directorio raíz en `./` y despliega.
Los comandos salen de `vercel.json` y no hace falta ninguna variable de entorno.

**Cuando la interfaz llame a la API**, hay que tocar dos sitios o el navegador bloqueará las peticiones:

1. En `vercel.json`, añadir el dominio de la API a `connect-src` de la política CSP
   (por ejemplo `connect-src 'self' https://api.tu-empresa.com`).
2. En la API, definir `CORS_ORIGINS` con el dominio de Vercel (`https://tu-proyecto.vercel.app`).

### API y n8n

**La API y n8n no se publican en Vercel.** Las funciones de Vercel se congelan al responder, así que
el despachador de eventos (un hilo en segundo plano) no es fiable allí; SQLite no persiste; y n8n es un
proceso permanente. Usa un servicio de procesos de larga duración (Render, Railway, Fly.io o un
servidor propio) con PostgreSQL.

## Capturas sugeridas

Las imágenes no están incluidas todavía. Guárdalas en `docs/img/` y enlázalas aquí.

| Archivo sugerido | Qué mostrar |
|---|---|
| `docs/img/dashboard.png` | Vista **Dashboard**: tarjetas de estadísticas y tabla de tareas |
| `docs/img/tareas.png` | Vista **Tareas** con filtros de estado, prioridad y proyecto |
| `docs/img/proyectos.png` | Vista **Proyectos**: tarjetas con progreso y tareas vencidas |
| `docs/img/calendario.png` | Vista **Calendario** con tareas en su fecha límite |
| `docs/img/tema-oscuro.png` | La interfaz con el **tema oscuro** (Configuración) |
| `docs/img/movil.png` | La interfaz en **ancho móvil** con el menú lateral abierto |
| `docs/img/api-docs.png` | Documentación interactiva de la API (`/docs`) |
| `docs/img/n8n-flujo.png` | El flujo de n8n con el nodo Webhook y la autenticación |
| `docs/img/ci.png` | El CI de GitHub con los tres trabajos en verde |

Una vez añadidas, se enlazan así: `![Dashboard](docs/img/dashboard.png)`.

## Contribuir

1. Crea una rama: `git switch -c feat/mi-mejora`.
2. Haz commits pequeños y, desde la raíz, ejecuta `pytest` y
   `ruff check backend/app backend/tests .claude tools`.
3. Abre un Pull Request; el CI debe quedar en verde. La rama `main` está protegida: solo recibe
   cambios mediante Pull Request.

## Autor

**itsnirvana-svg** · [github.com/itsnirvana-svg](https://github.com/itsnirvana-svg)

Repositorio: [github.com/itsnirvana-svg/Task_Flow-AI](https://github.com/itsnirvana-svg/Task_Flow-AI)

## Licencia

Distribuido bajo la licencia [Apache-2.0](LICENSE).
