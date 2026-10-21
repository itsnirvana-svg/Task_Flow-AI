/* Componente: pantalla de inicio de sesión (solo en el modo conectado a la API). */
(function (TF) {
  "use strict";
  const { h } = TF.dom;

  /**
   * init({ container, onSubmit }) -> { show(message?), hide() }
   * onSubmit(usuario, contraseña) devuelve una promesa; si falla, su mensaje se muestra en el formulario.
   */
  function init({ container, onSubmit }) {
    const userInput = h("input", {
      id: "loginUser", name: "username", type: "text", autocomplete: "username",
      maxlength: "100", required: true,
    });
    const passwordInput = h("input", {
      id: "loginPassword", name: "password", type: "password", autocomplete: "current-password",
      maxlength: "200", required: true,
    });
    const message = h("p", { className: "error", role: "alert", hidden: true });
    const submit = h("button", { type: "submit", className: "btn btn-primary btn-block", text: "Entrar" });
    const heading = h("h2", { tabindex: "-1", text: "Iniciar sesión" });

    const field = (id, label, input) =>
      h("div", { className: "field" }, h("label", { for: id, text: label }), input);

    function setBusy(busy) {
      userInput.disabled = passwordInput.disabled = submit.disabled = busy;
      submit.textContent = busy ? "Entrando…" : "Entrar";
    }

    function say(text) {
      message.textContent = text || "";
      message.hidden = !text;
    }

    const form = h(
      "form",
      {
        className: "login-card panel",
        novalidate: true,
        onsubmit: async (event) => {
          event.preventDefault();
          const username = userInput.value.trim();
          if (!username || !passwordInput.value) {
            say("Escribe tu usuario y tu contraseña.");
            return;
          }
          say("");
          setBusy(true);
          let failed = false;
          try {
            await onSubmit(username, passwordInput.value);
          } catch (error) {
            failed = true;
            say(error.message || "No se pudo iniciar sesión.");
          } finally {
            passwordInput.value = "";
            setBusy(false); // un campo deshabilitado no admite el foco: primero se habilita
          }
          if (failed) passwordInput.focus();
        },
      },
      h("div", { className: "login-brand" }, h("strong", { text: "TaskFlow AI" })),
      heading,
      h("p", { className: "muted", text: "Entra con tu cuenta para ver y gestionar tus tareas." }),
      field("loginUser", "Usuario", userInput),
      field("loginPassword", "Contraseña", passwordInput),
      message,
      submit
    );
    container.append(form);

    return {
      show(notice) {
        container.hidden = false;
        say(notice);
        userInput.focus();
      },
      hide() {
        container.hidden = true;
        say("");
      },
    };
  }

  TF.components.LoginView = { init };
})((window.TaskFlow = window.TaskFlow || {}));
