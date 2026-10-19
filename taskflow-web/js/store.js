/* Estado de la aplicación (en memoria) con suscripción a cambios.
   Cuando exista backend, solo hay que sustituir los métodos de este archivo por llamadas a la API. */
(function (TF) {
  "use strict";
  const { STATUS, projectOf, isOverdue } = TF.format;

  const copy = (tasks) => tasks.map((task) => ({ ...task }));

  function createStore(initialTasks) {
    const state = { tasks: copy(initialTasks), filter: "todas", query: "" };
    const listeners = new Set();
    const notify = () => listeners.forEach((listener) => listener(state));

    function visibleTasks() {
      const query = state.query.trim().toLowerCase();
      return state.tasks.filter((task) => {
        const matchesFilter = state.filter === "todas" || task.status === state.filter;
        const matchesQuery =
          !query ||
          task.title.toLowerCase().includes(query) ||
          (task.project || "").toLowerCase().includes(query);
        return matchesFilter && matchesQuery;
      });
    }

    /** Resumen por proyecto: total, recuento por estado y tareas vencidas. */
    function projects() {
      const byName = new Map();
      for (const task of state.tasks) {
        const name = projectOf(task);
        if (!byName.has(name)) {
          const byStatus = Object.fromEntries(Object.values(STATUS).map((s) => [s, 0]));
          byName.set(name, { name, total: 0, byStatus, overdue: 0 });
        }
        const project = byName.get(name);
        project.total += 1;
        project.byStatus[task.status] += 1;
        if (isOverdue(task)) project.overdue += 1;
      }
      return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name, "es"));
    }

    return {
      state,
      visibleTasks,
      projects,
      subscribe(listener) {
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
      setFilter(filter) {
        state.filter = filter;
        notify();
      },
      setQuery(query) {
        state.query = query;
        notify();
      },
      addTask(data) {
        const id = state.tasks.reduce((max, task) => Math.max(max, task.id), 0) + 1;
        state.tasks.unshift({ id, ...data });
        notify();
      },
      updateTask(id, changes) {
        const task = state.tasks.find((t) => t.id === id);
        if (!task) return;
        Object.assign(task, changes);
        notify();
      },
      removeTask(id) {
        state.tasks = state.tasks.filter((task) => task.id !== id);
        notify();
      },
      /** Vuelve a los datos de ejemplo iniciales. */
      reset() {
        state.tasks = copy(initialTasks);
        notify();
      },
    };
  }

  TF.createStore = createStore;
})((window.TaskFlow = window.TaskFlow || {}));
