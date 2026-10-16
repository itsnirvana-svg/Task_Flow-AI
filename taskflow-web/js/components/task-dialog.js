/* Componente: diálogo "Nueva tarea" (formulario con validación). */
(function (TF) {
  "use strict";

  /**
   * init({ dialog, form, titleInput, titleError, openButton, cancelButton, onSubmit })
   * onSubmit recibe { title, project, priority, status, due } con valores ya limpios.
   */
  function init({ dialog, form, titleInput, titleError, openButton, cancelButton, onSubmit }) {
    function open() {
      form.reset();
      titleError.hidden = true;
      dialog.showModal();
      titleInput.focus();
    }

    openButton.addEventListener("click", open);
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
