/* Componente: franja de estado bajo la barra superior (cargando y errores de la API). */
(function (TF) {
  "use strict";
  const { h } = TF.dom;

  /** init({ element, onDismiss }) -> { update(state) } */
  function init({ element, onDismiss }) {
    function update(state) {
      if (state.error) {
        element.className = "status-bar is-error";
        element.setAttribute("role", "alert");
        element.replaceChildren(
          h("span", { text: state.error }),
          h("button", {
            type: "button", className: "btn btn-ghost btn-sm", text: "Cerrar", onclick: onDismiss,
          })
        );
        element.hidden = false;
      } else if (state.loading) {
        element.className = "status-bar";
        element.setAttribute("role", "status");
        element.replaceChildren(h("span", { text: "Cargando tareas…" }));
        element.hidden = false;
      } else {
        element.hidden = true;
        element.replaceChildren();
      }
    }
    return { update };
  }

  TF.components.StatusBar = { init };
})((window.TaskFlow = window.TaskFlow || {}));
