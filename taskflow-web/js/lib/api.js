/* Cliente de la API de TaskFlow: sesión, peticiones y traducción de vocabulario.
   La interfaz y la API nombran distinto los mismos datos; esa traducción vive SOLO aquí:
     estado    pendiente | en-progreso | completada   <->  todo | in_progress | done
     prioridad alta | media | baja                      <->  3 | 2 | 1   (la API admite 4 = urgente)
     fecha     due "AAAA-MM-DD" o ""                    <->  due_date "AAAA-MM-DD" o null
     proyecto  project "" (sin proyecto)                <->  project null */
(function (TF) {
  "use strict";
  const { STATUS, PRIORITY } = TF.format;

  const TOKEN_KEY = "taskflow.token";
  const PAGE_SIZE = 200; // el máximo que admite la API por página
  const MAX_TASKS = 5000; // tope de seguridad al cargar todas las tareas

  const STATUS_TO_API = {
    [STATUS.PENDING]: "todo",
    [STATUS.IN_PROGRESS]: "in_progress",
    [STATUS.DONE]: "done",
  };
  const STATUS_FROM_API = Object.fromEntries(Object.entries(STATUS_TO_API).map(([k, v]) => [v, k]));
  const PRIORITY_TO_API = { [PRIORITY.LOW]: 1, [PRIORITY.MEDIUM]: 2, [PRIORITY.HIGH]: 3 };

  /** 4 (urgente) y 3 se muestran como "alta"; 1 como "baja"; el resto, "media". */
  function priorityFromApi(value) {
    if (value >= 3) return PRIORITY.HIGH;
    return value <= 1 ? PRIORITY.LOW : PRIORITY.MEDIUM;
  }

  /** Tarea de la API -> tarea de la interfaz. */
  function fromApi(task) {
    return {
      id: task.id,
      title: task.title,
      project: task.project || "",
      priority: priorityFromApi(task.priority),
      status: STATUS_FROM_API[task.status] || STATUS.PENDING,
      due: task.due_date || "",
    };
  }

  /** Cambios de la interfaz -> cuerpo de la API. Solo incluye los campos recibidos. */
  function toApi(changes) {
    const body = {};
    if ("title" in changes) body.title = changes.title;
    if ("project" in changes) body.project = changes.project || null;
    if ("priority" in changes) body.priority = PRIORITY_TO_API[changes.priority];
    if ("status" in changes) body.status = STATUS_TO_API[changes.status];
    if ("due" in changes) body.due_date = changes.due || null;
    return body;
  }

  class ApiError extends Error {
    constructor(status, message) {
      super(message);
      this.name = "ApiError";
      this.status = status;
    }
  }

  /** Mensaje para la persona usuaria según lo que respondió el servidor. */
  function messageFor(status, isLogin, retryAfter) {
    if (status === 401) {
      return isLogin ? "Usuario o contraseña incorrectos." : "Tu sesión ha caducado. Inicia sesión de nuevo.";
    }
    if (status === 429) {
      const wait = Number(retryAfter);
      return wait > 0 ? `Demasiados intentos. Espera ${wait} s e inténtalo de nuevo.` : "Demasiados intentos. Espera un momento.";
    }
    if (status === 404) return "Esa tarea ya no existe. Recarga la página.";
    if (status === 422) return "Los datos no son válidos. Revísalos e inténtalo de nuevo.";
    if (status === 503) return "El servicio no está disponible o no está configurado.";
    return "El servidor tuvo un problema. Inténtalo de nuevo en unos minutos.";
  }

  /** Almacén de la sesión: se borra al cerrar la pestaña. Sin él (modo privado), vale hasta recargar. */
  function sessionStore() {
    let memory = null;
    return {
      get() {
        try {
          return window.sessionStorage.getItem(TOKEN_KEY) || memory;
        } catch {
          return memory;
        }
      },
      set(value) {
        memory = value;
        try {
          if (value) window.sessionStorage.setItem(TOKEN_KEY, value);
          else window.sessionStorage.removeItem(TOKEN_KEY);
        } catch {
          /* sin almacenamiento: la sesión vale hasta recargar */
        }
      },
    };
  }

  /**
   * createApi({ baseUrl, fetch, storage }) -> cliente. Los parámetros se inyectan para poder
   * probarlo sin navegador ni servidor.
   */
  function createApi({ baseUrl, fetch: doFetch, storage }) {
    let onUnauthorized = () => {};

    async function request(method, path, body, { isLogin = false } = {}) {
      const headers = { Accept: "application/json" };
      if (body !== undefined) headers["Content-Type"] = "application/json";
      const token = storage.get();
      if (token) headers.Authorization = `Bearer ${token}`;

      let response;
      try {
        response = await doFetch(baseUrl + path, {
          method,
          headers,
          body: body === undefined ? undefined : JSON.stringify(body),
          cache: "no-store",
        });
      } catch {
        throw new ApiError(0, "No se pudo conectar con el servidor. Comprueba tu conexión.");
      }

      if (response.status === 204) return null;
      if (!response.ok) {
        if (response.status === 401 && !isLogin) {
          storage.set(null); // el token ya no vale: se descarta y se pide iniciar sesión
          onUnauthorized();
        }
        const retryAfter = response.headers && response.headers.get ? response.headers.get("Retry-After") : null;
        throw new ApiError(response.status, messageFor(response.status, isLogin, retryAfter));
      }
      try {
        return await response.json();
      } catch {
        throw new ApiError(response.status, "La respuesta del servidor no es válida.");
      }
    }

    return {
      baseUrl,
      hasToken: () => Boolean(storage.get()),
      /** Usuario de la sesión, leído del token (solo para mostrarlo; el servidor es quien lo valida). */
      currentUser() {
        try {
          const payload = storage.get().split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
          return JSON.parse(atob(payload)).sub || null;
        } catch {
          return null;
        }
      },
      /** Se llama cuando el servidor rechaza el token (caducado o inválido). */
      setUnauthorizedHandler(handler) {
        onUnauthorized = handler;
      },

      async login(username, password) {
        const data = await request("POST", "/api/auth/login", { username, password }, { isLogin: true });
        storage.set(data.access_token);
        return username;
      },
      logout() {
        storage.set(null);
      },

      /** Todas las tareas, página a página. */
      async listTasks() {
        const tasks = [];
        while (tasks.length < MAX_TASKS) {
          const page = await request("GET", `/api/tasks?limit=${PAGE_SIZE}&offset=${tasks.length}`);
          tasks.push(...page);
          if (page.length < PAGE_SIZE) break;
        }
        return tasks.map(fromApi);
      },
      async createTask(data) {
        return fromApi(await request("POST", "/api/tasks", toApi(data)));
      },
      async updateTask(id, changes) {
        return fromApi(await request("PATCH", `/api/tasks/${id}`, toApi(changes)));
      },
      async deleteTask(id) {
        await request("DELETE", `/api/tasks/${id}`);
      },
    };
  }

  TF.createApi = createApi;
  TF.apiMapping = { fromApi, toApi, ApiError };
  // En modo API (config.apiUrl) hay un cliente listo; en modo demostración, no hay ninguno.
  TF.api = TF.config.apiUrl
    ? createApi({
        baseUrl: TF.config.apiUrl.replace(/\/+$/, ""),
        fetch: (...args) => window.fetch(...args),
        storage: sessionStore(),
      })
    : null;
})((window.TaskFlow = window.TaskFlow || {}));
