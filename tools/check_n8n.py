"""Comprueba que el webhook de n8n está protegido y que descarta eventos repetidos.

Envía unas pocas peticiones de prueba y dice si cada comprobación pasa. Sirve para verificar el
flujo `n8n/workflows/taskflow-eventos.json` tras importarlo, o cualquier cambio posterior.

Uso, desde la raíz del proyecto:
    python tools/check_n8n.py https://n8n.tu-empresa.com/webhook/taskflow

El secreto se lee de la variable N8N_WEBHOOK_SECRET; si no existe, se pide sin mostrarlo en
pantalla. Sin dirección como argumento se usa N8N_WEBHOOK_URL.

Los eventos de prueba son `task.updated` de una tarea que no existe (id 2147483647): el flujo no
toca ningún dato real, pero SÍ queda registrado en el historial de ejecuciones de n8n.
"""

import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from uuid import uuid4

SECRET_HEADER = "X-TaskFlow-Secret"
TAREA_INEXISTENTE = 2147483647
TIMEOUT = 15


def enviar(url: str, cuerpo: dict, secreto: str | None) -> tuple[int, dict | None]:
    """POST del evento. Devuelve (código HTTP, JSON de la respuesta o None)."""
    cabeceras = {"Content-Type": "application/json"}
    if secreto is not None:
        cabeceras[SECRET_HEADER] = secreto
    peticion = urllib.request.Request(
        url, data=json.dumps(cuerpo).encode(), headers=cabeceras, method="POST"
    )
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
            codigo, texto = respuesta.status, respuesta.read().decode()
    except urllib.error.HTTPError as error:
        codigo, texto = error.code, error.read().decode(errors="replace")
    except (urllib.error.URLError, TimeoutError) as error:
        sys.exit(f"No se pudo conectar con {url}: {error}")
    try:
        return codigo, json.loads(texto)
    except ValueError:
        return codigo, None


def evento(**cambios) -> dict:
    base = {
        "event": "task.updated",
        "event_id": str(uuid4()),
        "sequence": 1,
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "data": {"task_id": TAREA_INEXISTENTE, "changed": ["title"]},
    }
    return {**base, **cambios}


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("N8N_WEBHOOK_URL", "")
    if not url:
        sys.exit("Indica la dirección del webhook: python tools/check_n8n.py https://.../webhook/taskflow")
    if "/webhook-test/" in url:
        sys.exit("Esa es la dirección de PRUEBAS de n8n: usa la de producción (/webhook/...).")
    secreto = os.environ.get("N8N_WEBHOOK_SECRET") or getpass.getpass("Secreto del webhook: ")

    repetido = evento()
    pruebas = [
        ("sin secreto se rechaza (401/403)",
         lambda: enviar(url, evento(), None), lambda c, r: c in (401, 403)),
        ("con un secreto incorrecto se rechaza (401/403)",
         lambda: enviar(url, evento(), "secreto-incorrecto"), lambda c, r: c in (401, 403)),
        ("con el secreto correcto se procesa",
         lambda: enviar(url, repetido, secreto),
         lambda c, r: c == 200 and r and r.get("status") == "procesado"),
        ("el mismo evento_id otra vez se descarta como duplicado",
         lambda: enviar(url, repetido, secreto),
         lambda c, r: c == 200 and r and r.get("motivo") == "duplicado"),
        ("un evento desconocido se ignora sin error",
         lambda: enviar(url, evento(event="task.inventado"), secreto),
         lambda c, r: c == 200 and r and r.get("status") == "ignorado"),
        ("un evento sin identificadores válidos se ignora sin error",
         lambda: enviar(url, evento(event_id="no-es-un-uuid"), secreto),
         lambda c, r: c == 200 and r and r.get("status") == "ignorado"),
    ]

    fallos = 0
    for nombre, ejecutar, esperado in pruebas:
        codigo, respuesta = ejecutar()
        correcto = bool(esperado(codigo, respuesta))
        fallos += not correcto
        print(f"{'OK    ' if correcto else 'FALLA '} {nombre}  (HTTP {codigo})")
    print("\nTodo correcto." if not fallos else f"\n{fallos} comprobación(es) fallaron.")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
