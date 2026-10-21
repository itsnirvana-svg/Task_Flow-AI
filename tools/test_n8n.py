"""Pruebas del flujo de n8n versionado y de la herramienta que lo verifica (tools/check_n8n.py)."""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import check_n8n

RAIZ = Path(__file__).resolve().parent.parent
RUTA_FLUJO = RAIZ / "n8n" / "workflows" / "taskflow-eventos.json"
FLUJO = json.loads(RUTA_FLUJO.read_text(encoding="utf-8"))
NODOS = {n["name"]: n for n in FLUJO["nodes"]}
NOTA = "n8n-nodes-base.stickyNote"
NODOS_DE_FLUJO = {nombre: n for nombre, n in NODOS.items() if n["type"] != NOTA}


def nodo_de_tipo(sufijo: str) -> dict:
    return next(n for n in NODOS_DE_FLUJO.values() if n["type"].endswith(sufijo))


def destinos(nombre: str) -> list[str]:
    salidas = FLUJO["connections"].get(nombre, {}).get("main", [])
    return [enlace["node"] for salida in salidas for enlace in salida]


# ---------------------------------------------------------------- seguridad del webhook


def test_el_webhook_exige_la_cabecera_secreta():
    webhook = nodo_de_tipo(".webhook")
    assert webhook["parameters"]["authentication"] == "headerAuth"
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert "httpHeaderAuth" in webhook["credentials"]


def test_la_ruta_del_webhook_es_la_documentada_para_produccion():
    ejemplo = (RAIZ / ".env.example").read_text(encoding="utf-8")
    ruta = nodo_de_tipo(".webhook")["parameters"]["path"]
    assert f"/webhook/{ruta}" in ejemplo


def test_el_flujo_no_contiene_secretos():
    """Las credenciales se referencian por nombre; sus valores viven solo dentro de n8n."""
    for n in NODOS.values():
        for referencia in n.get("credentials", {}).values():
            assert set(referencia) == {"id", "name"}
    texto = json.dumps(FLUJO)
    assert not re.search(r'"(value|password|apiKey|token)"\s*:', texto)


def test_el_flujo_viene_activo_para_importarlo_listo():
    assert FLUJO["active"] is True and FLUJO["id"]


# ---------------------------------------------------------------- estructura


def test_todas_las_conexiones_apuntan_a_nodos_que_existen():
    for origen, salidas in FLUJO["connections"].items():
        assert origen in NODOS
        for salida in salidas["main"]:
            for enlace in salida:
                assert enlace["node"] in NODOS, f"{origen} -> {enlace['node']} no existe"


def test_todos_los_nodos_se_alcanzan_desde_el_webhook():
    pendientes, vistos = [nodo_de_tipo(".webhook")["name"]], set()
    while pendientes:
        actual = pendientes.pop()
        if actual not in vistos:
            vistos.add(actual)
            pendientes += destinos(actual)
    assert vistos == set(NODOS_DE_FLUJO)


def test_todos_los_caminos_terminan_respondiendo_al_webhook():
    """Con responseMode=responseNode, un camino sin respuesta dejaría la petición colgada."""
    finales = [nombre for nombre in NODOS_DE_FLUJO if not destinos(nombre)]
    assert finales and all(NODOS[n]["type"].endswith(".respondToWebhook") for n in finales)


# ---------------------------------------------------------------- comportamiento


def test_el_duplicado_solo_se_marca_al_terminar_con_exito():
    """Si se marcara al principio, un evento que falla a medias se perdería en el reintento."""
    validar = NODOS["Validar y detectar duplicados"]["parameters"]["jsCode"]
    registrar = NODOS["Registrar evento como procesado"]["parameters"]["jsCode"]
    assert "vistos[" in validar and not re.search(r"vistos\[[^\]]+\]\s*=", validar)
    assert re.search(r"vistos\[[^\]]+\]\s*=", registrar)


def test_la_memoria_de_duplicados_tiene_limite():
    registrar = NODOS["Registrar evento como procesado"]["parameters"]["jsCode"]
    assert "MAX_IDS" in registrar and "SIETE_DIAS" in registrar


def test_la_consulta_a_la_api_usa_ipv4_y_no_oculta_los_fallos():
    http = nodo_de_tipo(".httpRequest")
    assert "localhost" not in http["parameters"]["url"]  # en n8n, localhost puede ser IPv6 (::1)
    assert "127.0.0.1" in http["parameters"]["url"]
    assert "onError" not in http  # un fallo de red debe hacer fallar el evento, no ocultarse
    respuesta = http["parameters"]["options"]["response"]["response"]
    assert respuesta["neverError"] is True and respuesta["fullResponse"] is True
    comprobar = NODOS["Comprobar la respuesta de la API"]["parameters"]["jsCode"]
    assert "404" in comprobar and "throw new Error" in comprobar  # 404 es normal; el resto, fallo


def test_los_marcadores_de_calendar_no_hacen_nada_todavia():
    marcadores = [n for nombre, n in NODOS.items() if nombre.startswith("Calendar:")]
    assert marcadores and all(n["type"].endswith(".noOp") for n in marcadores)


# ---------------------------------------------------------------- la herramienta de verificación


class FalsoN8n(BaseHTTPRequestHandler):
    """Servidor que imita a n8n; `protegido` y `dedupe` permiten fabricar versiones defectuosas."""

    secreto = "secreto-de-prueba"
    protegido = True
    dedupe = True
    vistos: set = set()

    def log_message(self, *args):
        pass

    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.protegido and self.headers.get("X-TaskFlow-Secret") != self.secreto:
            return self.responder(403, {"message": "Authorization data is wrong!"})
        valido = cuerpo.get("event") in ("task.updated",) and re.fullmatch(
            r"[0-9a-f-]{36}", str(cuerpo.get("event_id"))
        )
        if not valido:
            return self.responder(200, {"status": "ignorado", "motivo": "evento no válido"})
        if self.dedupe and cuerpo["event_id"] in self.vistos:
            return self.responder(200, {"status": "ignorado", "motivo": "duplicado"})
        self.vistos.add(cuerpo["event_id"])
        self.responder(200, {"status": "procesado"})

    def responder(self, codigo, datos):
        texto = json.dumps(datos).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(texto)))
        self.end_headers()
        self.wfile.write(texto)


@pytest.fixture()
def servidor():
    FalsoN8n.protegido, FalsoN8n.dedupe, FalsoN8n.vistos = True, True, set()
    http = HTTPServer(("127.0.0.1", 0), FalsoN8n)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{http.server_port}/webhook/taskflow"
    http.shutdown()


def ejecutar(url, monkeypatch, capsys) -> tuple[int, str]:
    monkeypatch.setattr("sys.argv", ["check_n8n.py", url])
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", FalsoN8n.secreto)
    with pytest.raises(SystemExit) as salida:
        check_n8n.main()
    return salida.value.code, capsys.readouterr().out


def test_la_herramienta_aprueba_un_webhook_bien_configurado(servidor, monkeypatch, capsys):
    codigo, salida = ejecutar(servidor, monkeypatch, capsys)
    assert codigo == 0 and "FALLA" not in salida and salida.count("OK") == 6


def test_la_herramienta_detecta_un_webhook_sin_autenticacion(servidor, monkeypatch, capsys):
    """Es el estado de partida del flujo del curso: cualquiera puede enviarle datos."""
    FalsoN8n.protegido = False
    codigo, salida = ejecutar(servidor, monkeypatch, capsys)
    assert codigo == 1
    assert "FALLA  sin secreto se rechaza" in salida
    assert "FALLA  con un secreto incorrecto se rechaza" in salida


def test_la_herramienta_detecta_un_flujo_que_no_descarta_duplicados(servidor, monkeypatch, capsys):
    FalsoN8n.dedupe = False
    codigo, salida = ejecutar(servidor, monkeypatch, capsys)
    assert codigo == 1 and "FALLA  el mismo evento_id otra vez se descarta" in salida


def test_la_herramienta_rechaza_la_direccion_de_pruebas_de_n8n(monkeypatch):
    monkeypatch.setattr("sys.argv", ["check_n8n.py", "http://x/webhook-test/taskflow"])
    with pytest.raises(SystemExit, match="PRUEBAS"):
        check_n8n.main()


def test_la_herramienta_avisa_si_no_hay_servidor(monkeypatch):
    monkeypatch.setattr("sys.argv", ["check_n8n.py", "http://127.0.0.1:1/webhook/taskflow"])
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "x")
    with pytest.raises(SystemExit, match="No se pudo conectar"):
        check_n8n.main()
