/* Componente: diálogo "Nueva tarea" (formulario con validación). */
(function (TF) {
  "use strict";

  /**
   * init({ dialog, form, titleInput, titleError, openButton, cancelButton, onSubmit })
   * onSubmit recibe { title, project, priority, status, due } con valores ya limpios.
   * open({ due: "2026-10-20", project: "Sitio web" }) abre el diálogo con esos campos rellenos.
   */
  function init({ dialog, form, titleInput, titleError, openButton, cancelButton, onSubmit }) {
    function open(defaults = {}) {
      form.reset();
      titleError.hidden = true;
      for (const [name, value] of Object.entries(defaults)) {
        const field = form.elements[name];
        if (field && value) field.value = value;
      }
      dialog.showModal();
      titleInput.focus();
    }

    openButton.addEventListener("click", () => open());
    cancelButton.addEventListener("click", () => dialog.close());

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const title = String(data.get("title") || "").trim();

      if (!title) {
        titleError.hidden = false;
        titleInput.focus();
        return;
      }

      onSubmit({
        title,
        project: String(data.get("project") || "").trim(),
        priority: String(data.get("priority")),
        status: String(data.get("status")),
        due: String(data.get("due") || ""),
      });
      dialog.close();
    });

    return { open };
  }

  TF.components.TaskDialog = { init };
})((window.TaskFlow = window.TaskFlow || {}));
