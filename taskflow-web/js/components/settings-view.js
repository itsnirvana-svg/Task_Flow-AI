/* Vista "Configuración": nombre, tema y preferencias del calendario. */
(function (TF) {
  "use strict";
  const { h } = TF.dom;
  const { confirmClick } = TF.utils;

  const THEMES = [
    ["system", "Según el sistema"],
    ["light", "Claro"],
    ["dark", "Oscuro"],
  ];

  function field(id, label, input, hint) {
    return h(
      "div",
      { className: "setting" },
      h("label", { for: id, text: label }),
      input,
      hint ? h("small", { className: "muted", text: hint }) : null
    );
  }

  function init(container, { settings, store, onChange }) {
    const current = settings.get();
    const message = h("p", { className: "muted", role: "status" });
    const say = (text) => { message.textContent = text; };
    const save = (changes) => {
      settings.save(changes);
      say("Cambios guardados.");
      onChange();
    };

    const nameInput = h("input", {
      id: "setName", type: "text", maxlength: "40", value: current.name,
      onchange: () => save({ name: nameInput.value }),
    });
    const themeSelect = h(
      "select",
      { id: "setTheme", onchange: () => save({ theme: themeSelect.value }) },
      THEMES.map(([value, label]) => h("option", { value, text: label, selected: value === current.theme }))
    );
    const showDone = h("input", {
      id: "setDone", type: "checkbox", checked: current.calendarShowDone,
      onchange: () => save({ calendarShowDone: showDone.checked }),
    });
    const reset = h("button", { type: "button", className: "btn btn-danger", text: "Restablecer datos de ejemplo" });
    confirmClick(reset, "¿Seguro? Se perderán tus cambios", () => {
      store.reset();
      say("Datos de ejemplo restaurados.");
    });

    container.append(
      h(
        "div",
        { className: "page-head" },
        h(
          "div",
          {},
          h("h2", { tabindex: "-1", text: "Configuración" }),
          h("p", { className: "muted", text: "Tus preferencias se guardan en este navegador." })
        )
      ),
      h(
        "div",
        { className: "panel settings" },
        field("setName", "Tu nombre", nameInput, "Se muestra arriba a la derecha (máx. 40 caracteres)."),
        field("setTheme", "Tema", themeSelect),
        h(
          "div",
          { className: "setting setting-check" },
          showDone,
          h("label", { for: "setDone", text: "Mostrar las tareas completadas en el calendario" })
        ),
        h("div", { className: "setting" }, h("span", { className: "setting-title", text: "Datos" }), reset),
        message
      )
    );

    return { update() {} };
  }

  TF.components.SettingsView = { init };
})((window.TaskFlow = window.TaskFlow || {}));
