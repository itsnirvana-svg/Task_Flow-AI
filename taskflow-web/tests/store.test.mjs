import assert from "node:assert/strict";
import { test } from "node:test";
import { igual, loadTaskFlow } from "./helpers.mjs";

const TF = loadTaskFlow(["js/config.js", "js/lib/format.js", "js/repository.js", "js/store.js"]);

const tarea = (id, extra = {}) => ({
  id, title: `T${id}`, project: "", priority: "media", status: "pendiente", due: "", ...extra,
});

/** Repositorio falso: guarda lo que se le pide y puede fallar a demanda. */
function repositorio(tareas = [], { falla = null, conReset = false } = {}) {
  const repo = {
    tareas: [...tareas],
    async list() {
      if (falla) throw new Error(falla);
      return [...repo.tareas];
    },
    async create(datos) {
      if (falla) throw new Error(falla);
      return { id: 99, ...datos };
    },
    async update(id, cambios) {
      if (falla) throw new Error(falla);
      return { ...repo.tareas.find((t) => t.id === id), ...cambios };
    },
    async remove(id) {
      if (falla) throw new Error(falla);
      repo.tareas = repo.tareas.filter((t) => t.id !== id);
    },
  };
  if (conReset) {
    repo.reset = async () => {
      repo.tareas = [tarea(1)];
    };
  }
  return repo;
}

test("cargar deja las tareas en el estado y avisa mientras carga", async () => {
  const store = TF.createStore(repositorio([tarea(1), tarea(2)]));
  const vistos = [];
  store.subscribe((estado) => vistos.push(estado.loading));

  await store.load();

  assert.equal(store.state.tasks.length, 2);
  assert.equal(store.state.loading, false);
  igual(vistos, [true, false]); // se avisó de que cargaba y luego de que terminó
});

test("si cargar falla, el error queda en el estado y no se rompe nada", async () => {
  const store = TF.createStore(repositorio([], { falla: "El servidor no responde" }));
  await store.load();
  assert.equal(store.state.error, "El servidor no responde");
  assert.equal(store.state.loading, false);
  igual(store.state.tasks, []);
});

test("crear añade la tarea al principio con lo que devolvió el repositorio", async () => {
  const store = TF.createStore(repositorio([tarea(1)]));
  await store.load();
  await store.addTask({ title: "Nueva" });
  igual(store.state.tasks.map((t) => t.id), [99, 1]);
});

test("editar sustituye la tarea y eliminar la quita", async () => {
  const store = TF.createStore(repositorio([tarea(1), tarea(2)]));
  await store.load();

  await store.updateTask(1, { status: "completada" });
  assert.equal(store.state.tasks.find((t) => t.id === 1).status, "completada");

  await store.removeTask(2);
  igual(store.state.tasks.map((t) => t.id), [1]);
});

test("si guardar falla, el estado no cambia y se muestra el motivo", async () => {
  const repo = repositorio([tarea(1)]);
  const store = TF.createStore(repo);
  await store.load();
  repo.update = async () => {
    throw new Error("Sin conexión");
  };

  await store.updateTask(1, { status: "completada" });

  assert.equal(store.state.tasks[0].status, "pendiente"); // sigue como estaba
  assert.equal(store.state.error, "Sin conexión");
  store.dismissError();
  assert.equal(store.state.error, null);
});

test("al cerrar sesión se vacían los datos en pantalla", async () => {
  const store = TF.createStore(repositorio([tarea(1)]));
  await store.load();
  store.clear();
  igual(store.state.tasks, []);
});

test("restablecer solo existe si el repositorio lo permite (demostración)", async () => {
  assert.equal(TF.createStore(repositorio()).canReset, false);

  const store = TF.createStore(repositorio([tarea(5), tarea(6)], { conReset: true }));
  assert.equal(store.canReset, true);
  await store.reset();
  igual(store.state.tasks.map((t) => t.id), [1]);
});

test("el filtro y la búsqueda siguen funcionando sobre las tareas cargadas", async () => {
  const store = TF.createStore(
    repositorio([
      tarea(1, { title: "Diseñar portada", status: "completada" }),
      tarea(2, { title: "Escribir informe", project: "Docs" }),
    ])
  );
  await store.load();

  store.setFilter("completada");
  igual(store.visibleTasks().map((t) => t.id), [1]);
  store.setFilter("todas");
  store.setQuery("docs");
  igual(store.visibleTasks().map((t) => t.id), [2]);
});

// ---------------------------------------------------------------- repositorio en memoria (demostración)

test("el repositorio en memoria crea con id nuevo, edita, elimina y vuelve a los datos de ejemplo", async () => {
  const repo = TF.createMemoryRepository([tarea(1), tarea(2)]);

  const creada = await repo.create({ title: "Otra" });
  assert.equal(creada.id, 3);
  await repo.update(3, { status: "completada" });
  await repo.remove(1);
  igual((await repo.list()).map((t) => t.id), [3, 2]);

  await repo.reset();
  igual((await repo.list()).map((t) => t.id), [1, 2]);
});

test("el repositorio en memoria no comparte objetos con quien lo consulta", async () => {
  const repo = TF.createMemoryRepository([tarea(1)]);
  (await repo.list())[0].title = "manipulada";
  assert.equal((await repo.list())[0].title, "T1");
});
