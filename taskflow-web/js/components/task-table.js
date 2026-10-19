/* Componente: tabla de tareas del dashboard (solo lectura). */
(function (TF) {
  "use strict";
  const { h } = TF.dom;
  const { projectOf, formatDate, isOverdue } = TF.format;
  const { Badge } = TF.components;

  /** Fecha límite; en rojo y con aviso si la tarea está vencida. */
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
      h("td", { text: projectOf(task) }),
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

  TF.components.TaskTable = { render, dueDate };
})((window.TaskFlow = window.TaskFlow || {}));
