# TaskFlow AI | Dashboard (versión 0.1)

Primera versión del proyecto, hecha solo con **HTML5, CSS3 y JavaScript**.
No tiene autenticación, base de datos ni backend: las tareas viven en memoria y se reinician al recargar.

## Cómo ejecutarlo

Abre `index.html` en el navegador (doble clic). No requiere instalar nada.

## Estructura

```text
taskflow-web/
├── index.html          # estructura de la página
├── css/
│   └── styles.css      # variables, layout, componentes y responsive
├── js/
│   ├── data.js         # tareas de ejemplo
│   ├── ui.js           # funciones que dibujan tabla y tarjetas
│   └── app.js          # estado, filtros, búsqueda y diálogo
└── assets/             # imágenes e iconos (vacía por ahora)
```

## Qué incluye

- Barra lateral de navegación (se oculta en móvil con botón de menú)
- Encabezado superior con búsqueda
- Tarjetas: Tareas totales, Pendientes, En progreso, Completadas
- Tabla de tareas con prioridad, estado y fecha límite (vencidas en rojo)
- Filtros por estado y búsqueda por título o proyecto
- Botón "Nueva tarea" con formulario
- Diseño responsive

## Próximos pasos del curso

Persistencia, backend, base de datos, autenticación y automatizaciones con n8n.
