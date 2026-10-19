/* Utilidades generales. */
(function (TF) {
  "use strict";

  /** Retrasa `fn` hasta que pasen `ms` milisegundos sin nuevas llamadas (útil en búsquedas). */
  function debounce(fn, ms) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), ms);
    };
  }

  /**
   * Botón de acción destructiva en dos pasos: el primer clic lo "arma" (cambia su texto) y el
   * segundo, dado antes de `ms`, ejecuta la acción. Si no hay segundo clic, vuelve a su estado.
   */
  function confirmClick(button, armedText, action, ms = 3000) {
    const original = button.textContent;
    let timer = null;
    const disarm = () => {
      timer = null;
      button.textContent = original;
      button.classList.remove("is-armed");
    };
    button.addEventListener("click", () => {
      if (timer) {
        clearTimeout(timer);
        disarm();
        action();
        return;
      }
      button.textContent = armedText;
      button.classList.add("is-armed");
      timer = setTimeout(disarm, ms);
    });
  }

  TF.utils = { debounce, confirmClick };
})((window.TaskFlow = window.TaskFlow || {}));
