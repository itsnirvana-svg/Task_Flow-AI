/* Vista "Calendario": un mes con las tareas colocadas en su fecha límite. */
(function (TF) {
  "use strict";
  const { h } = TF.dom;
  const { STATUS, LABELS, dateKey, isOverdue } = TF.format;

  const WEEKDAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
  const MAX_VISIBLE = 3; // tareas mostradas por día; el resto, "+N más"

  const startOfMonth = (date) => new Date(date.getFullYear(), date.getMonth(), 1);
  const addMonths = (date, n) => new Date(date.getFullYear(), date.getMonth() + n, 1);

  function taskChip(task) {
    const classes = ["cal-task", `badge-${task.priority}`];
    if (task.status === STATUS.DONE) classes.push("is-done");
    if (isOverdue(task)) classes.push("is-late");
    return h("span", {
      className: classes.join(" "),
      title: `${task.title} (${LABELS.status[task.status]})`,
      text: task.title,
    });
  }

  function init(container, { store, settings, openDialog }) {
    let month = startOfMonth(new Date());

    const title = h("p", { className: "cal-title", "aria-live": "polite" });
    const grid = h("div", { className: "calendar", "aria-label": "Calendario del mes" });
    const undatedList = h("ul", { className: "undated-list" });
    const undated = h("section", { className: "panel undated" }, h("h3", { text: "Sin fecha límite" }), undatedList);

    const go = (delta) => {
      month = delta === 0 ? startOfMonth(new Date()) : addMonths(month, delta);
      update();
    };

    container.append(
      h(
        "div",
        { className: "page-head" },
        h(
          "div",
          {},
          h("h2", { tabindex: "-1", text: "Calendario" }),
          h("p", { className: "muted", text: "Pulsa el número de un día para añadir una tarea con esa fecha." })
        )
      ),
      h(
        "div",
        { className: "cal-head" },
        h("button", { type: "button", className: "icon-btn", "aria-label": "Mes anterior", text: "‹", onclick: () => go(-1) }),
        title,
        h("button", { type: "button", className: "icon-btn", "aria-label": "Mes siguiente", text: "›", onclick: () => go(1) }),
        h("button", { type: "button", className: "btn btn-ghost", text: "Hoy", onclick: () => go(0) })
      ),
      grid,
      undated
    );

    function dayCell(date, tasks, { outside, today }) {
      const label = date.toLocaleDateString("es-PE", { day: "numeric", month: "long" });
      const extra = tasks.length - MAX_VISIBLE;
      return h(
        "div",
        { className: ["cal-day", outside && "is-outside", today && "is-today"].filter(Boolean).join(" ") },
        h("button", {
          type: "button",
          className: "cal-add",
          "aria-label": `Añadir tarea el ${label}`,
          text: String(date.getDate()),
          onclick: () => openDialog({ due: dateKey(date) }),
        }),
        tasks.slice(0, MAX_VISIBLE).map(taskChip),
        extra > 0 ? h("span", { className: "cal-more", text: `+${extra} más` }) : null
      );
    }

    function update() {
      title.textContent = month.toLocaleDateString("es-PE", { month: "long", year: "numeric" });
      const showDone = settings.get().calendarShowDone;
      const visible = store.state.tasks.filter((t) => showDone || t.status !== STATUS.DONE);

      const byDay = new Map();
      for (const task of visible.filter((t) => t.due)) {
        if (!byDay.has(task.due)) byDay.set(task.due, []);
        byDay.get(task.due).push(task);
      }

      const offset = (month.getDay() + 6) % 7; // la semana empieza en lunes
      const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
      const weeks = Math.ceil((offset + daysInMonth) / 7);
      const todayKey = dateKey(new Date());

      const cells = [];
      for (let i = 0; i < weeks * 7; i++) {
        const date = new Date(month.getFullYear(), month.getMonth(), 1 - offset + i);
        const key = dateKey(date);
        cells.push(
          dayCell(date, byDay.get(key) || [], {
            outside: date.getMonth() !== month.getMonth(),
            today: key === todayKey,
          })
        );
      }
      grid.replaceChildren(...WEEKDAYS.map((d) => h("div", { className: "cal-weekday", text: d })), ...cells);

      const withoutDate = visible.filter((t) => !t.due);
      undatedList.replaceChildren(...withoutDate.map((t) => h("li", {}, taskChip(t))));
      undated.hidden = withoutDate.length === 0;
    }

    return { update };
  }

  TF.components.CalendarView = { init };
})((window.TaskFlow = window.TaskFlow || {}));
