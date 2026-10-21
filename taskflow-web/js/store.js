/* Estado de la aplicación con suscripción a cambios.
   Las tareas se leen y se guardan a través de un repositorio (repository.js): en memoria en el modo
   demostración, en la API en el modo conectado. Las operaciones son asíncronas: el estado cambia
   cuando el repositorio confirma, y si falla queda el mensaje en `state.error`.

   Una tarea tiene esta forma:
     { id, title, project, priority: "alta"|"media"|"baja",
       status: "pendiente"|"en-progreso"|"completada", due: "AAAA-MM-DD" o "" }
   La traducción al vocabulario de la API (todo/in_progress/done, prioridad 1 a 4) está en lib/api.js. */
(function (TF) {
  "use strict";
  const { STATUS, projectOf, isOverdue } = TF.format;

  function createStore(repository) {
    const state = { tasks: [], filter: "todas", query: "", loading: false, error: null };
    const listeners = new Set();
    const notify = () => listeners.forEach((listener) => listener(state));

    /** Ejecuta una operación del repositorio: avisa mientras carga y recoge el error si falla. */
    async function run(operation, { loading = false } = {}) {
      state.error = null;
      if (loading) {
        state.loading = true;
        notify();
      }
      try {
        await operation();
      } catch (error) {
        state.error = (error && error.message) || "No se pudo completar la operación.";
      } finally {
        state.loading = false;
        notify();
      }
    }

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
      /** ¿El repositorio permite volver a los datos de ejemplo? (solo en el modo demostración) */
      canReset: typeof repository.reset === "function",
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
      dismissError() {
        state.error = null;
        notify();
      },
      /** Carga las tareas desde el repositorio (al arrancar y tras iniciar sesión). */
      load() {
        return run(async () => {
          state.tasks = await repository.list();
        }, { loading: true });
      },
      /** Vacía los datos en pantalla (al cerrar sesión): no deben verse tras salir. */
      clear() {
        state.tasks = [];
        state.error = null;
        notify();
      },
      addTask(data) {
        return run(async () => {
          state.tasks.unshift(await repository.create(data));
        });
      },
      updateTask(id, changes) {
        return run(async () => {
          const saved = await repository.update(id, changes);
          const index = state.tasks.findIndex((task) => task.id === id);
          if (index !== -1) state.tasks[index] = saved;
        });
      },
      removeTask(id) {
        return run(async () => {
          await repository.remove(id);
          state.tasks = state.tasks.filter((task) => task.id !== id);
        });
      },
      /** Vuelve a los datos de ejemplo (solo modo demostración). */
      reset() {
        return run(async () => {
          await repository.reset();
          state.tasks = await repository.list();
        });
      },
    };
  }

  TF.createStore = createStore;
})((window.TaskFlow = window.TaskFlow || {}));
