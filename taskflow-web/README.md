# TaskFlow AI | Dashboard (versión 0.1)

Interfaz hecha solo con **HTML5, CSS3 y JavaScript**, sin dependencias. Por ahora trabaja con datos
de ejemplo en memoria (se reinician al recargar) y **no está conectada a la API**.

## Cómo ejecutarlo

Abre `index.html` en el navegador (doble clic). No requiere instalar nada: los scripts son clásicos
(no módulos ES), por eso también funciona desde `file://`.

## Estructura

```text
taskflow-web/
├── index.html              # estructura, sprite de íconos y orden de carga de scripts
├── css/styles.css          # variables, layout, componentes y responsive
└── js/
    ├── data.js             # tareas de ejemplo
    ├── store.js            # estado, filtros y suscripción a cambios
    ├── app.js              # arranque: conecta el estado con los componentes
    ├── lib/
    │   ├── dom.js          # h(): creación segura de elementos
    │   ├── format.js       # etiquetas, fechas y tareas vencidas
    │   └── utils.js        # debounce
    └── components/
        ├── badge.js        # insignia de prioridad / estado
        ├── stat-cards.js   # tarjetas de estadísticas
        ├── task-table.js   # tabla de tareas
        ├── task-dialog.js  # diálogo "Nueva tarea"
        └── sidebar.js      # barra lateral y menú móvil
```

Todo cuelga de un único objeto global, `window.TaskFlow`, para evitar variables sueltas.

## Cómo añadir un componente

1. Crea `js/components/mi-componente.js` con la forma de los existentes (IIFE que asigna a
   `TaskFlow.components`).
2. Añade su `<script>` en `index.html`, antes de `store.js`.
3. Úsalo desde `app.js`.

## Próximos pasos

Conectar `store.js` a la API (`/api/tasks`), alineando el vocabulario (`todo/in_progress/done`,
prioridad 1-4), y añadir editar, completar y eliminar.
