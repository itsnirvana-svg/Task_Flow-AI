# TaskFlow AI | Dashboard

Interfaz hecha solo con **HTML5, CSS3 y JavaScript**, sin dependencias. Tiene dos modos:

| Modo | Cuándo | Qué hace |
|---|---|---|
| **Demostración** | Sin dirección de API (por defecto) | Datos de ejemplo en memoria; se reinician al recargar. No pide iniciar sesión |
| **Conectado a la API** | Con `TASKFLOW_API_URL` al construir | Pide iniciar sesión y guarda las tareas en el servidor |

## Cómo ejecutarlo

**Demostración:** abre `index.html` en el navegador (doble clic). No requiere instalar nada: los scripts
son clásicos (no módulos ES) y la navegación usa la parte `#` de la dirección, por eso también funciona
desde `file://` y en cualquier alojamiento estático.

**Conectado a la API (en local):**

1. Arranca la API con la autenticación activa (`AUTH_DISABLED=false`, `ADMIN_USERNAME`,
   `ADMIN_PASSWORD_HASH` y `AUTH_SECRET_KEY` en el `.env`; ver `.env.example`).
2. En el `.env` de la API, define `CORS_ORIGINS` con la dirección desde la que sirves la interfaz,
   por ejemplo `http://localhost:5500`.
3. Escribe la dirección de la API en `js/config.js` (`apiUrl: "http://localhost:8000"`) **sin subir
   ese cambio**, y sirve la carpeta con cualquier servidor estático, por ejemplo
   `python -m http.server 5500` dentro de `taskflow-web/`.

## Publicarla conectada a la API (Vercel)

La dirección de la API se fija **al construir**, no desde la dirección de la página: si se leyera de
la URL, un enlace malicioso podría llevar a un servidor falso y robar contraseñas.

1. En Vercel: *Settings → Environment Variables* → `TASKFLOW_API_URL` = `https://api.tu-empresa.com`
   (solo el origen: sin ruta, sin `/` final y con `https`).
2. En `vercel.json`, añade esa dirección a `connect-src` de la política CSP:
   `connect-src 'self' https://api.tu-empresa.com`. **Si no, la construcción falla** con
   instrucciones, porque el navegador bloquearía todas las llamadas a la API.
3. En la API, `CORS_ORIGINS` debe contener el dominio de la interfaz (`https://tu-proyecto.vercel.app`).

```bash
# Para comprobar la construcción en local
TASKFLOW_API_URL=http://localhost:8000 python tools/build_web.py
```

## Sesión y seguridad

- El inicio de sesión (`POST /api/auth/login`) devuelve un token que **caduca** (60 minutos por
  defecto). Se guarda en `sessionStorage`: se borra al cerrar la pestaña y nunca en `localStorage`.
- Si el servidor rechaza el token (caducado o inválido), la interfaz **vacía los datos de la pantalla**
  y vuelve a pedir la contraseña, con un aviso.
- Al cerrar sesión se descarta el token y se vacían los datos en pantalla.
- Los errores se muestran en una franja bajo la barra superior y sin detalles internos del servidor.
- En el modo conectado, Configuración no ofrece «Restablecer datos de ejemplo»: no se borran datos reales.
- La interfaz nunca recibe ni guarda la contraseña: solo se envía al iniciar sesión.

## Qué incluye

Cinco vistas en el menú lateral (cada una con su dirección, así que funcionan atrás/adelante y los
enlaces directos):

| Vista | Dirección | Qué permite |
|---|---|---|
| **Dashboard** | `#/dashboard` | Tarjetas de estadísticas y tabla de tareas con búsqueda y filtro por estado |
| **Tareas** | `#/tareas` | Lista completa: filtrar por estado, prioridad y proyecto; ordenar; **cambiar el estado** desde la fila; **eliminar** (en dos pasos); crear tareas |
| **Proyectos** | `#/proyectos` | Una tarjeta por proyecto con su progreso, recuento por estado y tareas vencidas; "Ver tareas" abre la lista ya filtrada (`#/tareas?proyecto=…`) |
| **Calendario** | `#/calendario` | Mes con las tareas en su fecha límite; navegar entre meses; pulsar un día crea una tarea con esa fecha; las tareas sin fecha aparecen aparte |
| **Configuración** | `#/configuracion` | Tu nombre (se ve arriba y en el avatar), tema claro / oscuro / según el sistema, mostrar u ocultar las completadas en el calendario, y la sesión (conectado) o restablecer los datos de ejemplo (demostración) |

Las preferencias se guardan en el navegador (`localStorage`). Las tareas, en memoria (demostración) o en
la API (conectado).

## Traducción con la API

La interfaz y la API nombran distinto los mismos datos. La traducción vive solo en `js/lib/api.js`:

| Dato | Interfaz | API |
|---|---|---|
| Estado | `pendiente` · `en-progreso` · `completada` | `todo` · `in_progress` · `done` |
| Prioridad | `alta` · `media` · `baja` | `3` · `2` · `1` (la API admite también `4` = urgente, que se muestra como `alta`) |
| Fecha límite | `due` (`"AAAA-MM-DD"` o `""`) | `due_date` (fecha o `null`) |
| Proyecto | `project` (`""` = sin proyecto) | `project` (texto o `null`) |

## Estructura

```text
taskflow-web/
├── index.html              # estructura, sprite de íconos y orden de carga de scripts
├── css/styles.css          # variables (con tema oscuro), layout, componentes y responsive
├── tests/                  # pruebas de la lógica con Node (node --test)
└── js/
    ├── config.js           # modo: dirección de la API (vacía = demostración)
    ├── data.js             # tareas de ejemplo
    ├── repository.js       # de dónde salen y dónde se guardan las tareas (memoria o API)
    ├── store.js            # estado, filtros, proyectos, carga y errores
    ├── router.js           # rutas por "hash" (#/tareas…) y cambio de vista
    ├── app.js              # arranque: modo, sesión y conexión del estado con las vistas
    ├── lib/
    │   ├── dom.js          # h(): creación segura de elementos
    │   ├── format.js       # estados, prioridades, fechas y tareas vencidas
    │   ├── settings.js     # preferencias guardadas (nombre, tema, calendario)
    │   ├── api.js          # cliente de la API: sesión, peticiones y traducción de vocabulario
    │   └── utils.js        # debounce y botón de confirmación en dos pasos
    └── components/
        ├── badge.js        # insignia de prioridad / estado
        ├── stat-cards.js   # tarjetas de estadísticas
        ├── task-table.js   # tabla del dashboard
        ├── task-dialog.js  # diálogo "Nueva tarea" (admite valores iniciales)
        ├── sidebar.js      # barra lateral y menú móvil
        ├── task-list.js    # vista Tareas
        ├── projects-view.js# vista Proyectos
        ├── calendar-view.js# vista Calendario
        ├── settings-view.js# vista Configuración
        ├── login-view.js   # pantalla de inicio de sesión (modo conectado)
        └── status-bar.js   # franja de «cargando» y errores
```

Todo cuelga de un único objeto global, `window.TaskFlow`, para evitar variables sueltas. No hay
estilos ni manejadores en línea y el DOM se construye con `h()` (nunca con HTML en cadenas): así la
interfaz cumple la política de seguridad (CSP) de `vercel.json`.

## Pruebas

```bash
node --test taskflow-web/tests/*.test.mjs     # sesión, traducción de datos, errores y estado
pytest tools                                  # empaquetado, vercel.json, CSP y menú
```

Los scripts de la interfaz son clásicos (no módulos), así que `tests/helpers.mjs` los carga en un
contexto aislado de Node, sin navegador, con un `fetch` falso.

## Cómo añadir una vista

1. Añade un enlace en el menú de `index.html` (`href="#/nombre"` y `data-nav="nombre"`) y una sección
   `<section data-view="nombre" hidden>` vacía.
2. Registra `nombre` en `ROUTES` de `js/router.js`.
3. Crea `js/components/nombre-view.js` con `init(contenedor, contexto)` que devuelva `{ update }`
   (y, si lo necesita, `applyParams`), añade su `<script>` en `index.html` y regístrala en `app.js`.

Una prueba (`tools/test_build_web.py`) falla si un enlace del menú no tiene su vista o su ruta.
