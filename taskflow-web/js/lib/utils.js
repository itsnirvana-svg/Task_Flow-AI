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

  TF.utils = { debounce };
})((window.TaskFlow = window.TaskFlow || {}));
