"""Utilidades compartidas por las pruebas."""


def crear(client, title="Tarea", **campos):
    """Crea una tarea por la API y devuelve su JSON; falla si la API no responde 201."""
    respuesta = client.post("/api/tasks", json={"title": title, **campos})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()
