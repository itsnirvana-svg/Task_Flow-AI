/* Componente: barra lateral con menú desplegable en pantallas pequeñas. */
(function (TF) {
  "use strict";

  function init({ sidebar, overlay, button }) {
    function setOpen(open) {
      sidebar.classList.toggle("is-open", open);
      overlay.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
    }

    button.addEventListener("click", () => setOpen(!sidebar.classList.contains("is-open")));
    overlay.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") setOpen(false);
    });

    return { setOpen };
  }

  TF.components.Sidebar = { init };
})((window.TaskFlow = window.TaskFlow || {}));
