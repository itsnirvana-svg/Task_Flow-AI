/* Vista "Proyectos": una tarjeta por proyecto con su progreso. */
(function (TF) {
  "use strict";
  const { h } = TF.dom;
  const { STATUS, LABELS } = TF.format;

  function card(project) {
    const done = project.byStatus[STATUS.DONE];
    return h(
      "article",
      { className: "project-card" },
      h("h3", { text: project.name }),
      h("p", { className: "muted", text: `${done} de ${project.total} completadas` }),
      h("progress", { max: project.total, value: done, "aria-label": `Progreso de ${project.name}` }),
      h(
        "div",
        { className: "project-badges" },
        Object.values(STATUS).map((status) =>
          h("span", { className: `badge badge-${status}`, text: `${LABELS.status[status]}: ${project.byStatus[status]}` })
        )
      ),
      project.overdue
        ? h("p", { className: "is-overdue", text: `${project.overdue} vencida${project.overdue > 1 ? "s" : ""}` })
        : null,
      h("a", {
        className: "btn btn-ghost",
        href: TF.router.href("tareas", { proyecto: project.name }),
        text: "Ver tareas",
      })
    );
  }

  function init(container, { store, openDialog }) {
    const grid = h("div", { className: "projects" });
    const empty = h("p", { className: "empty", hidden: true, text: "Aún no hay proyectos: crea una tarea con un proyecto." });

    container.append(
      h(
        "div",
        { className: "page-head" },
        h(
          "div",
          {},
          h("h2", { tabindex: "-1", text: "Proyectos" }),
          h("p", { className: "muted", text: "Los proyectos salen de las tareas que los nombran." })
        ),
        h("button", { type: "button", className: "btn btn-primary", text: "Nueva tarea", onclick: () => openDialog() })
      ),
      grid,
      empty
    );

    function update() {
      const projects = store.projects();
      grid.replaceChildren(...projects.map(card));
      empty.hidden = projects.length > 0;
    }

    return { update };
  }

  TF.components.ProjectsView = { init };
})((window.TaskFlow = window.TaskFlow || {}));
