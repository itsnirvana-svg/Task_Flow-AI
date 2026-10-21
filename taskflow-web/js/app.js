/* Arranque: conecta el estado, las vistas del menú y los componentes. */
(function (TF) {
  "use strict";
  const { StatCards, TaskTable, TaskDialog, Sidebar, TaskList, ProjectsView, CalendarView, SettingsView } =
    TF.components;
  const $ = (id) => document.getElementById(id);

  TF.settings.load();
  const store = TF.createStore(SAMPLE_TASKS);

  const sidebar = Sidebar.init({ sidebar: $("sidebar"), overlay: $("overlay"), button: $("menuBtn") });

  const dialog = TaskDialog.init({
    dialog: $("taskDialog"),
    form: $("taskForm"),
    titleInput: $("fTitle"),
    titleError: $("titleError"),
    openButton: $("newTaskBtn"),
    cancelButton: $("cancelBtn"),
    onSubmit: (data) => store.addTask(data),
  });

  // --- Vista "Dashboard" (la original) ---
  const body = $("taskBody");
  const empty = $("emptyState");
  const chips = document.querySelectorAll(".chip[data-filter]");

  const dashboard = {
    update() {
      const tasks = store.visibleTasks();
      StatCards.update(store.state.tasks); // las tarjetas siempre reflejan el total, no el filtro
      TaskTable.render(body, tasks);
      empty.hidden = tasks.length > 0;
    },
  };

  // Búsqueda: espera a que el usuario deje de escribir antes de redibujar.
  $("searchInput").addEventListener(
    "input",
    TF.utils.debounce((event) => store.setQuery(event.target.value), 150)
  );

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      chips.forEach((c) => c.classList.toggle("is-active", c === chip));
      store.setFilter(chip.dataset.filter);
    });
  });

  // --- Vistas del menú ---
  let current = "dashboard";
  const render = () => views[current].update();
  const context = { store, settings: TF.settings, openDialog: dialog.open };

  // Cada vista es { update(), applyParams?(params) }: `update` la redibuja cuando cambia el estado
  // y `applyParams` (opcional) recibe los parámetros de la dirección, como #/tareas?proyecto=X.
  const views = {
    dashboard,
    tareas: TaskList.init($("viewTareas"), context),
    proyectos: ProjectsView.init($("viewProyectos"), context),
    calendario: CalendarView.init($("viewCalendario"), context),
    configuracion: SettingsView.init($("viewConfiguracion"), { ...context, onChange: render }),
  };

  store.subscribe(render);

  TF.settings.apply();
  TF.router.init((route) => {
    current = route.name;
    views[current].applyParams?.(route.params);
    sidebar.setOpen(false); // en móvil, el menú se cierra al navegar
    render();
  });
})((window.TaskFlow = window.TaskFlow || {}));
