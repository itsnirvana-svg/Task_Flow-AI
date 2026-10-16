"""Hook PostToolUse de TaskFlow AI: revisa calidad del archivo que Claude acaba de modificar.

Entrada (stdin): JSON del hook con tool_input.file_path.
Salida: sin hallazgos -> exit 0 en silencio.
        con hallazgos -> informe breve por stderr y exit 2 (Claude lo recibe y puede corregir).
Además añade el informe a .claude/reports/calidad.md.
"""
import ast
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comun import SECRETOS_CONOCIDOS  # noqa: E402  (lista única compartida)

IGNORAR = ("node_modules", ".venv", "venv", "__pycache__", ".git", ".claude", "dist")
EXTENSIONES = {".py", ".js", ".sql"}
MAX_LINEA = 100

# Formatos conocidos (compartidos con el guardián) más una regla genérica propia de este hook.
SECRETOS = [
    *SECRETOS_CONOCIDOS,
    (re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
     "posible credencial escrita en el código"),
]


def hallazgo(nivel, linea, texto):
    return {"nivel": nivel, "linea": linea, "texto": texto}


def revisar_comunes(lineas):
    out = []
    for n, l in enumerate(lineas, 1):
        for patron, desc in SECRETOS:
            if patron.search(l):
                out.append(hallazgo("ERROR", n, desc))
        if len(l) > MAX_LINEA:
            out.append(hallazgo("AVISO", n, f"línea de {len(l)} caracteres (máx. {MAX_LINEA})"))
        if re.search(r"\b(TODO|FIXME|XXX)\b", l):
            out.append(hallazgo("AVISO", n, "marcador pendiente (TODO/FIXME)"))
    return out


def revisar_python(ruta, texto):
    out = []
    try:
        arbol = ast.parse(texto)
    except SyntaxError as e:
        return [hallazgo("ERROR", e.lineno or 0, f"error de sintaxis: {e.msg}")]

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ExceptHandler) and nodo.type is None:
            out.append(hallazgo("AVISO", nodo.lineno, "'except:' sin tipo; captura también interrupciones"))
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in nodo.args.defaults + nodo.args.kw_defaults:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    out.append(hallazgo("AVISO", nodo.lineno, f"'{nodo.name}': valor por defecto mutable"))
            if not ast.get_docstring(nodo) and not nodo.name.startswith("_") and "tests" not in ruta.parts:
                out.append(hallazgo("INFO", nodo.lineno, f"'{nodo.name}' sin docstring"))
        if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", "") == "print" and "tests" not in ruta.parts:
            out.append(hallazgo("AVISO", nodo.lineno, "uso de print(); preferible logging"))

    ruff = shutil.which("ruff")
    if ruff:
        r = subprocess.run([ruff, "check", "--output-format=concise", str(ruta)],
                           capture_output=True, text=True, timeout=20)
        for linea in r.stdout.splitlines():
            if re.match(r".+:\d+:\d+:", linea):
                out.append(hallazgo("AVISO", 0, "ruff: " + linea.split(":", 3)[-1].strip()))
    return out


def revisar_js(ruta, lineas):
    out = []
    node = shutil.which("node")
    if node:
        r = subprocess.run([node, "--check", str(ruta)], capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            out.append(hallazgo("ERROR", 0, "error de sintaxis: " + r.stderr.strip().splitlines()[-1]))
    for n, l in enumerate(lineas, 1):
        if re.search(r"\bconsole\.log\(", l):
            out.append(hallazgo("AVISO", n, "console.log olvidado"))
        if re.search(r"\bvar\s+\w", l):
            out.append(hallazgo("AVISO", n, "usa let/const en lugar de var"))
        if re.search(r"[^=!<>]==[^=]", l) and "//" not in l.split("==")[0]:
            out.append(hallazgo("AVISO", n, "usa === en lugar de =="))
        if re.search(r"\.innerHTML\s*=", l) or re.search(r"\beval\(", l):
            out.append(hallazgo("ERROR", n, "innerHTML/eval: riesgo de XSS"))
    return out


def revisar_sql(lineas):
    out = []
    texto = "\n".join(lineas).upper()
    if re.search(r"\bSELECT\s+\*", texto):
        out.append(hallazgo("AVISO", 0, "SELECT *: lista las columnas necesarias"))
    if re.search(r"\bDELETE\s+FROM\s+\w+\s*;", texto) or re.search(r"\bUPDATE\s+\w+\s+SET\s[^;]*;", texto) and "WHERE" not in texto:
        out.append(hallazgo("ERROR", 0, "DELETE/UPDATE sin WHERE"))
    return out


def main():
    # Evita caracteres rotos en la consola de Windows
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        datos = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    ruta = Path(datos.get("tool_input", {}).get("file_path", ""))
    if not ruta.name or ruta.suffix not in EXTENSIONES or any(p in IGNORAR for p in ruta.parts):
        return 0
    if not ruta.is_file():
        return 0

    texto = ruta.read_text(encoding="utf-8", errors="replace")
    lineas = texto.splitlines()

    hallazgos = revisar_comunes(lineas)
    if ruta.suffix == ".py":
        hallazgos += revisar_python(ruta, texto)
    elif ruta.suffix == ".js":
        hallazgos += revisar_js(ruta, lineas)
    elif ruta.suffix == ".sql":
        hallazgos += revisar_sql(lineas)

    # INFO no interrumpe a Claude; solo queda en el informe
    importantes = [h for h in hallazgos if h["nivel"] != "INFO"]
    if not hallazgos:
        return 0

    orden = {"ERROR": 0, "AVISO": 1, "INFO": 2}
    hallazgos.sort(key=lambda h: (orden[h["nivel"]], h["linea"]))
    cuenta = {n: sum(1 for h in hallazgos if h["nivel"] == n) for n in orden}
    cabecera = (f"Revisión de calidad: {ruta.name} - {cuenta['ERROR']} errores, "
                f"{cuenta['AVISO']} avisos, {cuenta['INFO']} info")
    cuerpo = [f"  [{h['nivel']}] {'L' + str(h['linea']) if h['linea'] else '-'}: {h['texto']}"
              for h in hallazgos[:15]]
    if len(hallazgos) > 15:
        cuerpo.append(f"  ... y {len(hallazgos) - 15} más (ver .claude/reports/calidad.md)")
    informe = "\n".join([cabecera] + cuerpo)

    try:
        carpeta = Path(".claude/reports")
        carpeta.mkdir(parents=True, exist_ok=True)
        with (carpeta / "calidad.md").open("a", encoding="utf-8") as f:
            f.write(f"\n### {datetime.now():%Y-%m-%d %H:%M:%S}\n```\n{informe}\n```\n")
    except OSError:
        pass

    if importantes:
        print(informe, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
