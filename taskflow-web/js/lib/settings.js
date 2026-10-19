/* Preferencias del usuario (nombre, tema, calendario), guardadas en el navegador.
   Si el almacenamiento no está disponible (modo privado, file://), la aplicación sigue funcionando. */
(function (TF) {
  "use strict";

  const KEY = "taskflow.settings";
  const THEMES = ["system", "light", "dark"];
  // El tema por defecto es claro (el aspecto de siempre); "Según el sistema" y "Oscuro" se eligen.
  const DEFAULTS = { name: "Usuario demo", theme: "light", calendarShowDone: true };
  const NAME_MAX = 40;

  let current = { ...DEFAULTS };

  function sanitize(values) {
    const name = String(values.name ?? "").trim().slice(0, NAME_MAX);
    return {
      name: name || DEFAULTS.name,
      theme: THEMES.includes(values.theme) ? values.theme : DEFAULTS.theme,
      calendarShowDone: values.calendarShowDone !== false,
    };
  }

  function load() {
    try {
      current = sanitize({ ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || "{}") });
    } catch {
      current = { ...DEFAULTS };
    }
    return current;
  }

  /** "Ana Pérez" -> "AP"; un solo nombre -> sus dos primeras letras. */
  function initials(name) {
    const words = name.split(/\s+/).filter(Boolean);
    const letters = words.length > 1 ? words[0][0] + words[1][0] : (words[0] || "?").slice(0, 2);
    return letters.toUpperCase();
  }

  function applyTheme() {
    const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const dark = current.theme === "dark" || (current.theme === "system" && systemDark);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }

  /** Refleja las preferencias en la página (tema, nombre y avatar). */
  function apply() {
    applyTheme();
    document.querySelector(".user-name").textContent = current.name;
    document.querySelector(".avatar").textContent = initials(current.name);
  }

  function save(changes) {
    current = sanitize({ ...current, ...changes });
    try {
      localStorage.setItem(KEY, JSON.stringify(current));
    } catch {
      /* sin almacenamiento: los cambios valen hasta recargar */
    }
    apply();
    return current;
  }

  // Con el tema "Según el sistema", se sigue el cambio claro/oscuro del equipo.
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (current.theme === "system") applyTheme();
  });

  TF.settings = { DEFAULTS, get: () => current, load, save, apply, initials };
})((window.TaskFlow = window.TaskFlow || {}));
