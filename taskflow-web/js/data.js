/* Datos de ejemplo. En esta primera versión no hay base de datos ni backend:
   las tareas viven solo en memoria y se reinician al recargar la página. */

const SAMPLE_TASKS = [
  { id: 1, title: "Diseñar la pantalla de inicio", project: "Sitio web", priority: "alta", status: "en-progreso", due: "2026-10-20" },
  { id: 2, title: "Redactar requisitos del proyecto", project: "Documentación", priority: "media", status: "completada", due: "2026-10-10" },
  { id: 3, title: "Configurar repositorio en GitHub", project: "Infraestructura", priority: "alta", status: "completada", due: "2026-10-12" },
  { id: 4, title: "Preparar presentación del curso", project: "Formación", priority: "media", status: "pendiente", due: "2026-10-25" },
  { id: 5, title: "Probar flujo de n8n", project: "Automatización", priority: "alta", status: "en-progreso", due: "2026-10-18" },
  { id: 6, title: "Revisar paleta de colores", project: "Sitio web", priority: "baja", status: "pendiente", due: "2026-10-30" },
  { id: 7, title: "Escribir README del proyecto", project: "Documentación", priority: "media", status: "pendiente", due: "2026-10-22" },
  { id: 8, title: "Definir estructura de la base de datos", project: "Infraestructura", priority: "alta", status: "pendiente", due: "" },
];
