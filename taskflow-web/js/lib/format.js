/* Vocabulario de estados y formato de datos de tareas (única fuente de verdad). */
(function (TF) {
  "use strict";

  const STATUS = { PENDING: "pendiente", IN_PROGRESS: "en-progreso", DONE: "completada" };
  const PRIORITY = { HIGH: "alta", MEDIUM: "media", LOW: "baja" };
  const NO_PROJECT = "Sin proyecto";

  const LABELS = {
    status: {
      [STATUS.PENDING]: "Pendiente",
      [STATUS.IN_PROGRESS]: "En progreso",
      [STATUS.DONE]: "Completada",
    },
    priority: {
      [PRIORITY.HIGH]: "Alta",
      [PRIORITY.MEDIUM]: "Media",
      [PRIORITY.LOW]: "Baja",
    },
  };

  const projectOf = (task) => task.project || NO_PROJECT;

  /** Convierte "AAAA-MM-DD" en una fecha local (evita el desfase de zona horaria de Date.parse). */
  function parseDate(iso) {
    const [year, month, day] = iso.split("-").map(Number);
    return new Date(year, month - 1, day);
  }

  /** Fecha local -> "AAAA-MM-DD" (la inversa de parseDate). */
  function dateKey(date) {
    const two = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${two(date.getMonth() + 1)}-${two(date.getDate())}`;
  }

  function formatDate(iso) {
    if (!iso) return "Sin fecha";
    return parseDate(iso).toLocaleDateString("es-PE", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  /** Vencida: tiene fecha anterior a hoy y no está completada (vence al terminar su día). */
  function isOverdue(task) {
    if (!task.due || task.status === STATUS.DONE) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return parseDate(task.due) < today;
  }

  TF.format = {
    STATUS, PRIORITY, NO_PROJECT, LABELS, projectOf, parseDate, dateKey, formatDate, isOverdue,
  };
})((window.TaskFlow = window.TaskFlow || {}));
