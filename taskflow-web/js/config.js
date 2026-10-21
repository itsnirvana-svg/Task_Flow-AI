/* Configuración de la interfaz.
   apiUrl vacía = modo DEMOSTRACIÓN: datos de ejemplo en memoria, sin iniciar sesión.
   Con una URL (por ejemplo "https://api.tu-empresa.com") la interfaz exige iniciar sesión y guarda
   las tareas en la API. Se fija al construir con la variable de entorno TASKFLOW_API_URL
   (tools/build_web.py), no desde la dirección de la página: así nadie puede apuntar la interfaz a
   un servidor ajeno para robar contraseñas. En local, puedes escribirla aquí sin subir el cambio. */
(function (TF) {
  "use strict";
  TF.config = { apiUrl: "" /* TASKFLOW_API_URL */ };
})((window.TaskFlow = window.TaskFlow || {}));
