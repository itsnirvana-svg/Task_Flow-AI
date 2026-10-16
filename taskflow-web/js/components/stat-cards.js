/* Componente: tarjetas de estadísticas (totales y por estado). */
(function (TF) {
  "use strict";
  const { STATUS } = TF.format;

  // Qué tarjeta muestra qué recuento (null = total de tareas).
  const CARDS = [
    { id: "statTotal", status: null },
    { id: "statPending", status: STATUS.PENDING },
    { id: "statProgress", status: STATUS.IN_PROGRESS },
    { id: "statDone", status: STATUS.DONE },
  ];

  function update(tasks) {
    for (const { id, status } of CARDS) {
      const total = status ? tasks.filter((t) => t.status === status).length : tasks.length;
      document.getElementById(id).textContent = total;
    }
  }

  TF.components = TF.components || {};
  TF.components.StatCards = { update };
})((window.TaskFlow = window.TaskFlow || {}));
