/* Lógica principal: estado en memoria, filtros, búsqueda, diálogo y menú móvil. */

const state = {
  tasks: SAMPLE_TASKS.map((t) => ({ ...t })),
  filter: "todas",
  query: "",
};

const els = {
  body: document.getElementById("taskBody"),
  empty: document.getElementById("emptyState"),
  search: document.getElementById("searchInput"),
  chips: document.querySelectorAll(".chip"),
  dialog: document.getElementById("taskDialog"),
  form: document.getElementById("taskForm"),
  titleError: document.getElementById("titleError"),
  sidebar: document.getElementById("sidebar"),
  overlay: document.getElementById("overlay"),
  menuBtn: document.getElementById("menuBtn"),
};

function visibleTasks() {
  const q = state.query.trim().toLowerCase();
  return state.tasks.filter((t) => {
    const matchesFilter = state.filter === "todas" || t.status === state.filter;
    const matchesQuery =
      !q || t.title.toLowerCase().includes(q) || (t.project || "").toLowerCase().includes(q);
    return matchesFilter && matchesQuery;
  });
}

function render() {
  const tasks = visibleTasks();
  renderStats(state.tasks); // las tarjetas siempre reflejan el total, no el filtro
  renderTasks(els.body, tasks);
  els.empty.hidden = tasks.length > 0;
}

/* ---- Búsqueda y filtros ---- */
els.search.addEventListener("input", (e) => {
  state.query = e.target.value;
  render();
});

els.chips.forEach((chip) => {
  chip.addEventListener("click", () => {
    state.filter = chip.dataset.filter;
    els.chips.forEach((c) => c.classList.toggle("is-active", c === chip));
    render();
  });
});

/* ---- Diálogo: nueva tarea ---- */
function openDialog() {
  els.form.reset();
  els.titleError.hidden = true;
  els.dialog.showModal();
  document.getElementById("fTitle").focus();
}

document.getElementById("newTaskBtn").addEventListener("click", openDialog);
document.getElementById("cancelBtn").addEventListener("click", () => els.dialog.close());

els.form.addEventListener("submit", (e) => {
  e.preventDefault();
  const data = new FormData(els.form);
  const title = String(data.get("title") || "").trim();

  if (!title) {
    els.titleError.hidden = false;
    document.getElementById("fTitle").focus();
    return;
  }

  const nextId = state.tasks.reduce((max, t) => Math.max(max, t.id), 0) + 1;
  state.tasks.unshift({
    id: nextId,
    title,
    project: String(data.get("project") || "").trim(),
    priority: String(data.get("priority")),
    status: String(data.get("status")),
    due: String(data.get("due") || ""),
  });

  els.dialog.close();
  render();
});

/* ---- Menú lateral en móvil ---- */
function setMenu(open) {
  els.sidebar.classList.toggle("is-open", open);
  els.overlay.hidden = !open;
  els.menuBtn.setAttribute("aria-expanded", String(open));
}

els.menuBtn.addEventListener("click", () => setMenu(!els.sidebar.classList.contains("is-open")));
els.overlay.addEventListener("click", () => setMenu(false));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") setMenu(false);
});

render();
