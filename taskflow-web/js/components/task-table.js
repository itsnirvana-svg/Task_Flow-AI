/* Componente: tabla de tareas. */
(function (TF) {
  "use strict";
  const { h } = TF.dom;
  const { formatDate, isOverdue } = TF.format;
  const { Badge } = TF.components;

  function dueDate(task) {
    const overdue = isOverdue(task);
    return h("span", {
      className: overdue ? "is-overdue" : null,
      title: overdue ? "Tarea vencida" : null,
      text: formatDate(task.due),
    });
  }

  function row(task) {
    return h(
      "tr",
      {},
      h("td", {}, h("span", { className: "task-title", text: task.title })),
      h("td", { text: task.project || "Sin proyecto" }),
      h("td", {}, Badge("priority", task.priority)),
      h("td", {}, Badge("status", task.status)),
      h("td", {}, dueDate(task))
    );
  }

  /** Dibuja todas las filas en un fragmento y las inserta de una vez (un solo redibujado). */
  function render(tbody, tasks) {
    const fragment = document.createDocumentFragment();
    for (const task of tasks) fragment.append(row(task));
    tbody.replaceChildren(fragment);
  }

  TF.components.TaskTable = { render };
})((window.TaskFlow = window.TaskFlow || {}));
