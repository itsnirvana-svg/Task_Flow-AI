/* Funciones de interfaz: crean el DOM de la tabla y actualizan las tarjetas.
   Se usa textContent (no innerHTML) para que el texto del usuario nunca se interprete como HTML. */

const LABELS = {
  status: { "pendiente": "Pendiente", "en-progreso": "En progreso", "completada": "Completada" },
  priority: { alta: "Alta", media: "Media", baja: "Baja" },
};

function formatDate(iso) {
  if (!iso) return "Sin fecha";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-PE", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function isOverdue(task) {
  if (!task.due || task.status === "completada") return false;
  const [y, m, d] = task.due.split("-").map(Number);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return new Date(y, m - 1, d) < today;
}

function createBadge(kind, value) {
  const span = document.createElement("span");
  span.className = `badge badge-${value}`;
  span.textContent = LABELS[kind][value];
  return span;
}

function createCell(content) {
  const td = document.createElement("td");
  if (content instanceof Node) td.appendChild(content);
  else td.textContent = content;
  return td;
}

function renderTasks(tbody, tasks) {
  tbody.replaceChildren();

  tasks.forEach((task) => {
    const tr = document.createElement("tr");

    const title = document.createElement("span");
    title.className = "task-title";
    title.textContent = task.title;

    const due = document.createElement("span");
    due.textContent = formatDate(task.due);
    if (isOverdue(task)) {
      due.className = "is-overdue";
      due.title = "Tarea vencida";
    }

    tr.append(
      createCell(title),
      createCell(task.project || "Sin proyecto"),
      createCell(createBadge("priority", task.priority)),
      createCell(createBadge("status", task.status)),
      createCell(due)
    );
    tbody.appendChild(tr);
  });
}

function renderStats(tasks) {
  const count = (status) => tasks.filter((t) => t.status === status).length;
  document.getElementById("statTotal").textContent = tasks.length;
  document.getElementById("statPending").textContent = count("pendiente");
  document.getElementById("statProgress").textContent = count("en-progreso");
  document.getElementById("statDone").textContent = count("completada");
}
