/* Arranque: conecta el estado, las vistas del menú y los componentes.
   Dos modos (ver config.js): sin API es una demostración con datos de ejemplo; con API exige
   iniciar sesión y guarda las tareas en el servidor. */
(function (TF) {
  "use strict";
  const {
    StatCards, TaskTable, TaskDialog, Sidebar, TaskList, ProjectsView, CalendarView, SettingsView,
    LoginView, StatusBar,
  } = TF.components;
  const $ = (id) => document.getElementById(id);

  const api = TF.api; // null en el modo demostración
  const repository = api ? TF.createApiRepository(api) : TF.createMemoryRepository(SAMPLE_TASKS);

  TF.settings.load();
  const store = TF.createStore(repository);

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

  const statusBar = StatusBar.init({ element: $("statusBar"), onDismiss: () => store.dismissError() });

  // --- Vista "Dashboard" (la original) ---
  const body = $("taskBody");
  const empty = $("emptyState");
  const chips = document.querySelectorAll(".chip[data-filter]");

  const dashboard = {
    update() {
      const tasks = store.visibleTasks();
      StatCards.update(store.state.tasks); // las tarjetas siempre reflejan el total, no el filtro
      TaskTable.render(body, tasks);
      empty.hidden = tasks.length > 0 || store.state.loading; // mientras carga, aún no se sabe
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

  // --- Sesión (solo en el modo conectado) ---
  const shell = $("appShell");
  const login = api
    ? LoginView.init({
        container: $("loginView"),
        onSubmit: async (username, password) => {
          await api.login(username, password);
          await enter();
        },
      })
    : null;

  /** Con el nombre por defecto, se muestra el usuario de la sesión en lugar de "Usuario demo". */
  function showSessionUser() {
    const user = api.currentUser();
    if (user && TF.settings.get().name === TF.settings.DEFAULTS.name) TF.settings.save({ name: user });
  }

  function showLogin(notice) {
    shell.hidden = true;
    login.show(notice);
  }

  /** Muestra la aplicación y carga las tareas del servidor. */
  async function enter() {
    showSessionUser();
    login.hide();
    shell.hidden = false;
    await store.load();
  }

  function logout() {
    api.logout();
    store.clear();
    store.setQuery("");
    $("searchInput").value = "";
    location.hash = "#/dashboard";
    showLogin();
  }

  const session = api ? { user: () => api.currentUser(), logout } : null;

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
    configuracion: SettingsView.init($("viewConfiguracion"), { ...context, onChange: render, session }),
  };

  store.subscribe(render);
  store.subscribe(statusBar.update);

  TF.settings.apply();
  TF.router.init((route) => {
    current = route.name;
    views[current].applyParams?.(route.params);
    sidebar.setOpen(false); // en móvil, el menú se cierra al navegar
    render();
  });

  // --- Puesta en marcha ---
  if (!api) {
    store.load();
  } else {
    // Si el servidor rechaza el token (caducó), se vuelve a pedir la contraseña.
    api.setUnauthorizedHandler(() => {
      store.clear();
      showLogin("Tu sesión ha caducado. Inicia sesión de nuevo.");
    });
    if (api.hasToken()) enter();
    else showLogin();
  }
})((window.TaskFlow = window.TaskFlow || {}));
