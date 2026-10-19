/* Enrutador por "hash" (#/tareas, #/proyectos?proyecto=Sitio%20web…).
   Funciona en cualquier alojamiento estático y desde file://, sin reglas de reescritura. */
(function (TF) {
  "use strict";

  const ROUTES = {
    dashboard: "Dashboard",
    tareas: "Tareas",
    proyectos: "Proyectos",
    calendario: "Calendario",
    configuracion: "Configuración",
  };
  const DEFAULT = "dashboard";

  /** "#/tareas?proyecto=X" -> { name: "tareas", params: URLSearchParams } (rutas desconocidas -> inicio). */
  function parse(hash) {
    const [path, query = ""] = hash.replace(/^#\/?/, "").split("?");
    return { name: Object.hasOwn(ROUTES, path) ? path : DEFAULT, params: new URLSearchParams(query) };
  }

  function href(name, params) {
    const query = params ? `?${new URLSearchParams(params)}` : "";
    return `#/${name}${query}`;
  }

  function show(route, moveFocus) {
    document.querySelectorAll("[data-view]").forEach((view) => {
      view.hidden = view.dataset.view !== route.name;
    });
    document.querySelectorAll(".nav-link").forEach((link) => {
      const active = link.dataset.nav === route.name;
      link.classList.toggle("is-active", active);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    document.getElementById("topbarTitle").textContent = ROUTES[route.name];
    document.title = `TaskFlow AI | ${ROUTES[route.name]}`;
    // Tras navegar, el foco pasa al título de la vista (lectores de pantalla y teclado).
    if (moveFocus) document.querySelector(`[data-view="${route.name}"] h2`)?.focus({ preventScroll: true });
  }

  /** Llama a onChange(route) al cargar y cada vez que cambia la dirección. */
  function init(onChange) {
    const apply = (moveFocus) => {
      const route = parse(window.location.hash);
      show(route, moveFocus);
      onChange(route);
    };
    window.addEventListener("hashchange", () => apply(true));
    apply(false);
  }

  TF.router = { ROUTES, parse, href, init };
})((window.TaskFlow = window.TaskFlow || {}));
