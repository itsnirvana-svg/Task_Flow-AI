# TaskFlow AI | Dashboard (versión 0.1)

Interfaz hecha solo con **HTML5, CSS3 y JavaScript**, sin dependencias. Por ahora trabaja con datos
de ejemplo en memoria (se reinician al recargar) y **no está conectada a la API**.

## Cómo ejecutarlo

Abre `index.html` en el navegador (doble clic). No requiere instalar nada: los scripts son clásicos
(no módulos ES) y la navegación usa la parte `#` de la dirección, por eso también funciona desde
`file://` y en cualquier alojamiento estático.

## Qué incluye

Cinco vistas en el menú lateral (cada una con su dirección, así que funcionan atrás/adelante y los
enlaces directos):

| Vista | Dirección | Qué permite |
|---|---|---|
| **Dashboard** | `#/dashboard` | Tarjetas de estadísticas y tabla de tareas con búsqueda y filtro por estado |
| **Tareas** | `#/tareas` | Lista completa: filtrar por estado, prioridad y proyecto; ordenar; **cambiar el estado** desde la fila; **eliminar** (en dos pasos); crear tareas |
| **Proyectos** | `#/proyectos` | Una tarjeta por proyecto con su progreso, recuento por estado y tareas vencidas; "Ver tareas" abre la lista ya filtrada (`#/tareas?proyecto=…`) |
| **Calendario** | `#/calendario` | Mes con las tareas en su fecha límite; navegar entre meses; pulsar un día crea una tarea con esa fecha; las tareas sin fecha aparecen aparte |
| **Configuración** | `#/configuracion` | Tu nombre (se ve arriba y en el avatar), tema claro / oscuro / según el sistema, mostrar u ocultar las completadas en el calendario, y restablecer los datos de ejemplo |

Las preferencias se guardan en el navegador (`localStorage`); las tareas, de momento, solo en memoria.

## Estructura

```text
taskflow-web/
├── index.html              # estructura, sprite de íconos y orden de carga de scripts
├── css/styles.css          # variables (con tema oscuro), layout, componentes y responsive
└── js/
    ├── data.js             # tareas de ejemplo
    ├── store.js            # estado, filtros, proyectos y suscripción a cambios
    ├── router.js           # rutas por "hash" (#/tareas…) y cambio de vista
    ├── app.js              # arranque: conecta el estado con las vistas
    ├── lib/
    │   ├── dom.js          # h(): creación segura de elementos
    │   ├── format.js       # estados, prioridades, fechas y tareas vencidas
    │   ├── settings.js     # preferencias guardadas (nombre, tema, calendario)
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
        └── settings-view.js# vista Configuración
```

Todo cuelga de un único objeto global, `window.TaskFlow`, para evitar variables sueltas. No hay
estilos ni manejadores en línea y el DOM se construye con `h()` (nunca con `innerHTML`): así la
interfaz cumple la política de seguridad (CSP) de `vercel.json`.

## Cómo añadir una vista

1. Añade un enlace en el menú de `index.html` (`href="#/nombre"` y `data-nav="nombre"`) y una sección
   `<section data-view="nombre" hidden>` vacía.
2. Registra `nombre` en `ROUTES` de `js/router.js`.
3. Crea `js/components/nombre-view.js` con `init(contenedor, contexto)` que devuelva `{ update }`
   (y, si lo necesita, `applyParams`), añade su `<script>` en `index.html` y regístrala en `app.js`.

Una prueba (`tools/test_build_web.py`) falla si un enlace del menú no tiene su vista o su ruta.

## Próximos pasos

Conectar `store.js` a la API (`/api/tasks`), alineando el vocabulario (`todo/in_progress/done`,
prioridad 1-4), y guardar las tareas.
