/* Estado de la aplicación (en memoria) con suscripción a cambios.
   Cuando exista backend, solo hay que sustituir los métodos de este archivo por llamadas a la API. */
(function (TF) {
  "use strict";

  function createStore(initialTasks) {
    const state = {
      tasks: initialTasks.map((task) => ({ ...task })),
      filter: "todas",
      query: "",
    };
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

    return {
      state,
      visibleTasks,
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
    };
  }

  TF.createStore = createStore;
})((window.TaskFlow = window.TaskFlow || {}));
