import assert from "node:assert/strict";
import { test } from "node:test";
import { igual, almacen, fetchFalso, loadTaskFlow, respuesta, tokenDe } from "./helpers.mjs";

const ARCHIVOS = ["js/config.js", "js/lib/format.js", "js/lib/api.js"];
const TF = loadTaskFlow(ARCHIVOS);
const { fromApi, toApi, ApiError } = TF.apiMapping;

const tareaApi = (extra = {}) => ({
  id: 1, title: "Tarea", project: "Sitio web", priority: 3, status: "in_progress",
  due_date: "2026-10-20", ...extra,
});

function crearApi(responder, token = null) {
  const fetch = fetchFalso(responder);
  const storage = almacen(token);
  return { api: TF.createApi({ baseUrl: "https://api.test", fetch, storage }), fetch, storage };
}

// ---------------------------------------------------------------- vocabulario

test("una tarea de la API se traduce al vocabulario de la interfaz", () => {
  igual(fromApi(tareaApi()), {
    id: 1, title: "Tarea", project: "Sitio web", priority: "alta", status: "en-progreso",
    due: "2026-10-20",
  });
});

test("sin proyecto ni fecha, la interfaz recibe textos vacíos", () => {
  const tarea = fromApi(tareaApi({ project: null, due_date: null }));
  assert.equal(tarea.project, "");
  assert.equal(tarea.due, "");
});

test("las prioridades de la API se agrupan en tres niveles", () => {
  const nivel = (priority) => fromApi(tareaApi({ priority })).priority;
  igual([1, 2, 3, 4].map(nivel), ["baja", "media", "alta", "alta"]);
});

test("los tres estados se traducen en los dos sentidos", () => {
  for (const [ui, api] of [["pendiente", "todo"], ["en-progreso", "in_progress"], ["completada", "done"]]) {
    assert.equal(toApi({ status: ui }).status, api);
    assert.equal(fromApi(tareaApi({ status: api })).status, ui);
  }
});

test("hacia la API solo viajan los campos que cambian", () => {
  igual(toApi({ status: "completada" }), { status: "done" });
  igual(toApi({ title: "Nuevo", priority: "baja" }), { title: "Nuevo", priority: 1 });
});

test("proyecto y fecha vacíos se envían como null para poder quitarlos", () => {
  igual(toApi({ project: "", due: "" }), { project: null, due_date: null });
});

// ---------------------------------------------------------------- sesión

test("iniciar sesión guarda el token y lo envía en las peticiones siguientes", async () => {
  const { api, fetch, storage } = crearApi((url) =>
    url.endsWith("/login") ? respuesta(200, { access_token: "T0KEN" }) : respuesta(200, []));

  await api.login("ana", "secreta");
  await api.listTasks();

  assert.equal(storage.get(), "T0KEN");
  assert.equal(fetch.llamadas[0].headers.Authorization, undefined); // el login va sin token
  assert.equal(fetch.llamadas[1].headers.Authorization, "Bearer T0KEN");
  igual(JSON.parse(fetch.llamadas[0].body), { username: "ana", password: "secreta" });
});

test("un login incorrecto no guarda nada ni cuenta como sesión caducada", async () => {
  const { api, storage } = crearApi(() => respuesta(401, { detail: "x" }));
  let caducadas = 0;
  api.setUnauthorizedHandler(() => caducadas++);

  await assert.rejects(api.login("ana", "mala"), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.message, "Usuario o contraseña incorrectos.");
    return true;
  });
  assert.equal(storage.get(), null);
  assert.equal(caducadas, 0);
});

test("si el servidor rechaza el token, se descarta y se avisa para pedir la contraseña", async () => {
  const { api, storage } = crearApi(() => respuesta(401, { detail: "x" }), "VIEJO");
  let caducadas = 0;
  api.setUnauthorizedHandler(() => caducadas++);

  await assert.rejects(api.listTasks(), /sesión ha caducado/);

  assert.equal(storage.get(), null);
  assert.equal(caducadas, 1);
});

test("cerrar sesión borra el token", () => {
  const { api, storage } = crearApi(() => respuesta(200, []), "T0KEN");
  assert.equal(api.hasToken(), true);
  api.logout();
  assert.equal(storage.get(), null);
  assert.equal(api.hasToken(), false);
});

test("el usuario de la sesión se lee del token, y un token roto no da error", () => {
  assert.equal(crearApi(() => null, tokenDe("ana")).api.currentUser(), "ana");
  assert.equal(crearApi(() => null, "no-es-un-token").api.currentUser(), null);
  assert.equal(crearApi(() => null, null).api.currentUser(), null);
});

// ---------------------------------------------------------------- errores

test("sin conexión se explica en lugar de fallar en silencio", async () => {
  const { api } = crearApi(() => { throw new TypeError("fetch failed"); }, "T");
  await assert.rejects(api.listTasks(), (error) => error.status === 0 && /No se pudo conectar/.test(error.message));
});

test("el límite de intentos indica cuánto esperar", async () => {
  const { api } = crearApi(() => respuesta(429, {}, { "Retry-After": "42" }));
  await assert.rejects(api.login("ana", "x"), /Espera 42 s/);
});

test("un error del servidor no enseña detalles internos", async () => {
  const { api } = crearApi(() => respuesta(500, { detail: "Traceback secreto" }), "T");
  await assert.rejects(api.listTasks(), (error) => !/Traceback/.test(error.message) && error.status === 500);
});

test("una tarea que ya no existe da un mensaje claro", async () => {
  const { api } = crearApi(() => respuesta(404, {}), "T");
  await assert.rejects(api.updateTask(9, { status: "completada" }), /ya no existe/);
});

// ---------------------------------------------------------------- tareas

test("las tareas se cargan página a página hasta agotarlas", async () => {
  const pagina = (n) => Array.from({ length: n }, (_, i) => tareaApi({ id: i + 1 }));
  const { api, fetch } = crearApi((url) => respuesta(200, url.includes("offset=0") ? pagina(200) : pagina(5)), "T");

  const tareas = await api.listTasks();

  assert.equal(tareas.length, 205);
  igual(fetch.llamadas.map((c) => c.url.split("?")[1]), [
    "limit=200&offset=0", "limit=200&offset=200",
  ]);
});

test("crear envía el cuerpo traducido y devuelve la tarea ya en el vocabulario de la interfaz", async () => {
  const { api, fetch } = crearApi(() => respuesta(201, tareaApi({ id: 7 })), "T");

  const tarea = await api.createTask({
    title: "Nueva", project: "", priority: "alta", status: "pendiente", due: "",
  });

  assert.equal(fetch.llamadas[0].method, "POST");
  igual(JSON.parse(fetch.llamadas[0].body), {
    title: "Nueva", project: null, priority: 3, status: "todo", due_date: null,
  });
  assert.equal(tarea.id, 7);
});

test("editar usa PATCH solo con lo que cambió y borrar acepta la respuesta vacía", async () => {
  const { api, fetch } = crearApi((url, op) =>
    op.method === "DELETE" ? respuesta(204) : respuesta(200, tareaApi({ status: "done" })), "T");

  const editada = await api.updateTask(3, { status: "completada" });
  await api.deleteTask(3);

  assert.equal(fetch.llamadas[0].method, "PATCH");
  assert.equal(fetch.llamadas[0].url, "https://api.test/api/tasks/3");
  igual(JSON.parse(fetch.llamadas[0].body), { status: "done" });
  assert.equal(editada.status, "completada");
  assert.equal(fetch.llamadas[1].method, "DELETE");
});

// ---------------------------------------------------------------- modos

test("sin dirección de API la interfaz es una demostración; con ella hay un cliente", () => {
  assert.equal(loadTaskFlow(ARCHIVOS).api, null);
  const conectada = loadTaskFlow(ARCHIVOS, { apiUrl: "https://api.test/" });
  assert.equal(conectada.api.baseUrl, "https://api.test"); // sin barra final
});
