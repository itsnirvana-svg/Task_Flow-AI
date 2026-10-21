/* Carga los scripts de la interfaz (clásicos, sin módulos) en un contexto aislado, sin navegador. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** Ejecuta los archivos en orden y devuelve el objeto global `TaskFlow` resultante. */
export function loadTaskFlow(files, { apiUrl } = {}) {
  const sandbox = { atob: (text) => Buffer.from(text, "base64").toString("binary") };
  sandbox.window = sandbox;
  const context = vm.createContext(sandbox);
  const run = (file) =>
    vm.runInContext(fs.readFileSync(path.join(WEB, file), "utf8"), context, { filename: file });

  for (const file of files) {
    run(file);
    if (file === "js/config.js" && apiUrl !== undefined) sandbox.TaskFlow.config.apiUrl = apiUrl;
  }
  return sandbox.TaskFlow;
}

/** Respuesta mínima con la forma que usa el cliente (status, ok, headers, json). */
export function respuesta(status, body = null, headers = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: { get: (name) => headers[name] ?? null },
    json: async () => body,
  };
}

/** fetch falso: registra las llamadas y responde con lo que devuelva `responder(url, opciones)`. */
export function fetchFalso(responder) {
  const llamadas = [];
  const fn = async (url, opciones) => {
    llamadas.push({ url, ...opciones });
    return responder(url, opciones);
  };
  fn.llamadas = llamadas;
  return fn;
}

/** Almacén de sesión en memoria, como el que inyecta la interfaz. */
export function almacen(inicial = null) {
  let valor = inicial;
  return { get: () => valor, set: (nuevo) => { valor = nuevo; } };
}

/** Token con la forma de un JWT (cabecera.carga.firma), para probar la lectura del usuario. */
export function tokenDe(usuario) {
  const carga = Buffer.from(JSON.stringify({ sub: usuario })).toString("base64url");
  return `cabecera.${carga}.firma`;
}

/** Compara por valor. Lo creado dentro del contexto aislado tiene otro prototipo de Object, así que
    se normaliza con JSON antes de la comparación estricta. */
export function igual(actual, esperado) {
  assert.deepStrictEqual(JSON.parse(JSON.stringify(actual)), esperado);
}
