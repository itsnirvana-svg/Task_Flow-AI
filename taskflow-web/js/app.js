/* Arranque: conecta el estado con los componentes. */
(function (TF) {
  "use strict";
  const { StatCards, TaskTable, TaskDialog, Sidebar } = TF.components;
  const $ = (id) => document.getElementById(id);

  const store = TF.createStore(SAMPLE_TASKS);

  const body = $("taskBody");
  const empty = $("emptyState");
  const chips = document.querySelectorAll(".chip");

  function render(state) {
    const tasks = store.visibleTasks();
    StatCards.update(state.tasks); // las tarjetas siempre reflejan el total, no el filtro
    TaskTable.render(body, tasks);
    empty.hidden = tasks.length > 0;
  }
  store.subscribe(render);

  // Búsqueda: espera a que el usuario deje de escribir antes de redibujar.
  $("searchInput").addEventListener(
    "input",
    TF.utils.debounce((event) => store.setQuery(event.target.value), 150)
  );

  // Filtros por estado.
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      chips.forEach((c) => c.classList.toggle("is-active", c === chip));
      store.setFilter(chip.dataset.filter);
    });
  });

  TaskDialog.init({
    dialog: $("taskDialog"),
    form: $("taskForm"),
    titleInput: $("fTitle"),
    titleError: $("titleError"),
    openButton: $("newTaskBtn"),
    cancelButton: $("cancelBtn"),
    onSubmit: (data) => store.addTask(data),
  });

  Sidebar.init({ sidebar: $("sidebar"), overlay: $("overlay"), button: $("menuBtn") });

  render(store.state);
})((window.TaskFlow = window.TaskFlow || {}));
