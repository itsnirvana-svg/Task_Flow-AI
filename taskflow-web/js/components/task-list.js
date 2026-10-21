/* Vista "Tareas": lista completa con filtros, orden, cambio de estado y eliminación. */
(function (TF) {
  "use strict";
  const { h } = TF.dom;
  const { STATUS, LABELS, projectOf } = TF.format;
  const { Badge, TaskTable } = TF.components;
  const { confirmClick } = TF.utils;

  const ALL = "todas";
  const PRIORITY_RANK = { alta: 0, media: 1, baja: 2 };
  const NO_DATE = "9999-12-31"; // las tareas sin fecha van al final al ordenar por fecha

  const sorters = {
    due: (a, b) => (a.due || NO_DATE).localeCompare(b.due || NO_DATE) || b.id - a.id,
    priority: (a, b) => PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority] || sorters.due(a, b),
    recent: (a, b) => b.id - a.id,
  };

  const option = (value, label, selected) => h("option", { value, selected, text: label });

  const control = (label, select) =>
    h("label", { className: "control" }, h("span", { text: label }), select);

  function init(container, { store, openDialog }) {
    const filters = { status: ALL, priority: ALL, project: ALL, order: "due" };
    const tbody = h("tbody");
    const empty = h("p", { className: "empty", hidden: true, text: "No hay tareas con estos filtros." });

    const chips = [
      [ALL, "Todas"],
      [STATUS.PENDING, "Pendientes"],
      [STATUS.IN_PROGRESS, "En progreso"],
      [STATUS.DONE, "Completadas"],
    ].map(([value, label]) =>
      h("button", {
        type: "button",
        className: "chip",
        text: label,
        dataset: { value },
        onclick: () => {
          filters.status = value;
          update();
        },
      })
    );

    const prioritySelect = h(
      "select",
      { onchange: (e) => { filters.priority = e.target.value; update(); } },
      option(ALL, "Todas"),
      ...Object.entries(LABELS.priority).map(([value, label]) => option(value, label))
    );
    const projectSelect = h("select", {
      onchange: (e) => { filters.project = e.target.value; update(); },
    });
    const orderSelect = h(
      "select",
      { onchange: (e) => { filters.order = e.target.value; update(); } },
      option("due", "Fecha límite", true),
      option("priority", "Prioridad"),
      option("recent", "Más recientes")
    );

    container.append(
      h(
        "div",
        { className: "page-head" },
        h(
          "div",
          {},
          h("h2", { tabindex: "-1", text: "Tareas" }),
          h("p", { className: "muted", text: "Cambia el estado, filtra y elimina tus tareas." })
        ),
        h("button", { type: "button", className: "btn btn-primary", text: "Nueva tarea", onclick: () => openDialog() })
      ),
      h(
        "div",
        { className: "panel" },
        h(
          "div",
          { className: "toolbar" },
          h("div", { className: "filters", role: "group", "aria-label": "Filtrar por estado" }, chips),
          control("Prioridad", prioritySelect),
          control("Proyecto", projectSelect),
          control("Ordenar por", orderSelect)
        ),
        h(
          "div",
          { className: "table-wrap" },
          h(
            "table",
            { className: "table table-wide" },
            h(
              "thead",
              {},
              h(
                "tr",
                {},
                ["Tarea", "Proyecto", "Prioridad", "Estado", "Fecha límite", "Acciones"].map((name) =>
                  h("th", { scope: "col", text: name })
                )
              )
            ),
            tbody
          )
        ),
        empty
      )
    );

    function visibleTasks() {
      const query = store.state.query.trim().toLowerCase();
      return store.state.tasks
        .filter(
          (t) =>
            (filters.status === ALL || t.status === filters.status) &&
            (filters.priority === ALL || t.priority === filters.priority) &&
            (filters.project === ALL || projectOf(t) === filters.project) &&
            (!query || t.title.toLowerCase().includes(query) || projectOf(t).toLowerCase().includes(query))
        )
        .sort(sorters[filters.order]);
    }

    function row(task) {
      const statusSelect = h(
        "select",
        {
          className: "cell-select",
          "aria-label": `Estado de ${task.title}`,
          onchange: (e) => store.updateTask(task.id, { status: e.target.value }),
        },
        Object.values(STATUS).map((s) => option(s, LABELS.status[s], s === task.status))
      );
      const remove = h("button", {
        type: "button",
        className: "btn btn-danger btn-sm",
        "aria-label": `Eliminar ${task.title}`,
        text: "Eliminar",
      });
      confirmClick(remove, "¿Seguro?", () => store.removeTask(task.id));

      return h(
        "tr",
        {},
        h("td", {}, h("span", { className: "task-title", text: task.title })),
        h("td", { text: projectOf(task) }),
        h("td", {}, Badge("priority", task.priority)),
        h("td", {}, statusSelect),
        h("td", {}, TaskTable.dueDate(task)),
        h("td", { className: "actions" }, remove)
      );
    }

    function refreshProjectOptions() {
      const names = store.projects().map((p) => p.name);
      if (filters.project !== ALL && !names.includes(filters.project)) filters.project = ALL;
      projectSelect.replaceChildren(
        option(ALL, "Todos", filters.project === ALL),
        ...names.map((name) => option(name, name, name === filters.project))
      );
    }

    function update() {
      refreshProjectOptions();
      prioritySelect.value = filters.priority;
      orderSelect.value = filters.order;
      chips.forEach((chip) => {
        const active = chip.dataset.value === filters.status;
        chip.classList.toggle("is-active", active);
        chip.setAttribute("aria-pressed", String(active));
      });
      const tasks = visibleTasks();
      tbody.replaceChildren(...tasks.map(row));
      empty.hidden = tasks.length > 0 || store.state.loading;
    }

    /** Desde la dirección: #/tareas?proyecto=Sitio%20web filtra por ese proyecto. */
    function applyParams(params) {
      filters.project = params.get("proyecto") || ALL;
    }

    return { update, applyParams };
  }

  TF.components.TaskList = { init };
})((window.TaskFlow = window.TaskFlow || {}));
