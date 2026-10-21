/* De dónde salen y dónde se guardan las tareas. El estado (store.js) solo conoce esta interfaz:
     list() · create(data) · update(id, changes) · remove(id) · reset?()
   y todas devuelven promesas. Hay dos implementaciones:
   - memoria: datos de ejemplo, se pierden al recargar (modo demostración);
   - API: guarda en el servidor (modo conectado). */
(function (TF) {
  "use strict";

  const copy = (tasks) => tasks.map((task) => ({ ...task }));

  /** Modo demostración: las tareas viven en memoria y `reset()` vuelve a los datos de ejemplo. */
  function createMemoryRepository(initialTasks) {
    let tasks = copy(initialTasks);
    return {
      async list() {
        return copy(tasks);
      },
      async create(data) {
        const id = tasks.reduce((max, task) => Math.max(max, task.id), 0) + 1;
        const task = { id, ...data };
        tasks.unshift(task);
        return { ...task };
      },
      async update(id, changes) {
        const task = tasks.find((t) => t.id === id);
        if (!task) throw new Error("Esa tarea ya no existe.");
        Object.assign(task, changes);
        return { ...task };
      },
      async remove(id) {
        tasks = tasks.filter((task) => task.id !== id);
      },
      async reset() {
        tasks = copy(initialTasks);
      },
    };
  }

  /** Modo conectado: cada operación se guarda en la API. No tiene `reset`: no se borran datos reales. */
  function createApiRepository(api) {
    return {
      list: () => api.listTasks(),
      create: (data) => api.createTask(data),
      update: (id, changes) => api.updateTask(id, changes),
      remove: (id) => api.deleteTask(id),
    };
  }

  TF.createMemoryRepository = createMemoryRepository;
  TF.createApiRepository = createApiRepository;
})((window.TaskFlow = window.TaskFlow || {}));
