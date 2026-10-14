import { useEffect, useState } from "react";

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Error ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

export default function App() {
  const [tasks, setTasks] = useState([]);
  const [title, setTitle] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const [error, setError] = useState("");

  const load = () => api("/api/tasks").then(setTasks).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const run = async (fn) => {
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const add = (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    run(() => api("/api/tasks", { method: "POST", body: JSON.stringify({ title }) }));
    setTitle("");
  };

  const toggle = (t) =>
    run(() => api(`/api/tasks/${t.id}`, { method: "PATCH", body: JSON.stringify({ done: !t.done }) }));

  const remove = (t) => run(() => api(`/api/tasks/${t.id}`, { method: "DELETE" }));

  const prioritize = async () => {
    setError("");
    try {
      const data = await api("/api/ai/prioritize", { method: "POST" });
      setSuggestion(data.suggestion);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <main style={{ maxWidth: 560, margin: "2rem auto", fontFamily: "system-ui, sans-serif" }}>
      <h1>TaskFlow AI</h1>

      <form onSubmit={add} style={{ display: "flex", gap: 8 }}>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Nueva tarea"
          style={{ flex: 1, padding: 8 }}
        />
        <button type="submit">Añadir</button>
      </form>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      <ul style={{ listStyle: "none", padding: 0 }}>
        {tasks.map((t) => (
          <li key={t.id} style={{ display: "flex", gap: 8, alignItems: "center", padding: "6px 0" }}>
            <input type="checkbox" checked={t.done} onChange={() => toggle(t)} />
            <span style={{ flex: 1, textDecoration: t.done ? "line-through" : "none" }}>{t.title}</span>
            <button onClick={() => remove(t)}>Eliminar</button>
          </li>
        ))}
      </ul>

      <button onClick={prioritize}>Priorizar con IA</button>
      {suggestion && <pre style={{ whiteSpace: "pre-wrap" }}>{suggestion}</pre>}
    </main>
  );
}
