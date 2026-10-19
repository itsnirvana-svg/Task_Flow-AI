/* Componente: insignia de color para prioridad o estado. */
(function (TF) {
  "use strict";
  const { h } = TF.dom;
  const { LABELS } = TF.format;

  /** Badge("priority", "alta") | Badge("status", "en-progreso") */
  function Badge(kind, value) {
    return h("span", { className: `badge badge-${value}`, text: LABELS[kind][value] });
  }

  TF.components = TF.components || {};
  TF.components.Badge = Badge;
})((window.TaskFlow = window.TaskFlow || {}));
