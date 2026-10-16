/* Etiquetas y formato de datos de tareas. */
(function (TF) {
  "use strict";

  const LABELS = {
    status: { "pendiente": "Pendiente", "en-progreso": "En progreso", "completada": "Completada" },
    priority: { alta: "Alta", media: "Media", baja: "Baja" },
  };

  /** Convierte "AAAA-MM-DD" en una fecha local (evita el desfase de zona horaria de Date.parse). */
  function parseDate(iso) {
    const [year, month, day] = iso.split("-").map(Number);
    return new Date(year, month - 1, day);
  }

  function formatDate(iso) {
    if (!iso) return "Sin fecha";
    return parseDate(iso).toLocaleDateString("es-PE", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  function isOverdue(task) {
    if (!task.due || task.status === "completada") return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return parseDate(task.due) < today;
  }

  TF.format = { LABELS, formatDate, isOverdue };
})((window.TaskFlow = window.TaskFlow || {}));
