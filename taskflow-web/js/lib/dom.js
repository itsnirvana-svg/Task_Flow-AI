/* Utilidad para crear elementos del DOM de forma segura y legible.
   Todo el texto se inserta como nodo de texto (nunca como HTML), así que el contenido
   escrito por el usuario no puede ejecutarse. */
(function (TF) {
  "use strict";

  /**
   * h("tr", { className: "fila", title: "Ayuda" }, hijo1, [hijo2, hijo3], "texto")
   * Props especiales: className, text (textContent), dataset (objeto) y onEvento (función).
   * Cualquier otra prop se escribe como atributo; null, undefined y false se omiten.
   */
  function h(tag, props, ...children) {
    const el = document.createElement(tag);

    for (const [key, value] of Object.entries(props || {})) {
      if (value == null || value === false) continue;
      if (key === "className") el.className = value;
      else if (key === "text") el.textContent = value;
      else if (key === "dataset") Object.assign(el.dataset, value);
      else if (key.startsWith("on") && typeof value === "function") {
        el.addEventListener(key.slice(2).toLowerCase(), value);
      } else el.setAttribute(key, value === true ? "" : value);
    }

    for (const child of children.flat()) {
      if (child == null || child === false) continue;
      el.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
  }

  TF.dom = { h };
})((window.TaskFlow = window.TaskFlow || {}));
