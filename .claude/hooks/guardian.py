"""Hook PreToolUse de TaskFlow AI: guardián de secretos y comandos peligrosos.

Se ejecuta ANTES de que Claude use Edit, Write, MultiEdit o Bash.
Entrada (stdin): JSON del hook con tool_name y tool_input.
Salida: permitido -> exit 0 en silencio.
        bloqueado -> motivo por stderr y exit 2 (Claude lo recibe y busca otra vía).
"""
import json
import re
import subprocess
import sys

# ---- Archivos que Claude no debe escribir ---------------------------------------------------
ARCHIVOS_PROTEGIDOS = [
    (re.compile(r"(^|[\\/])\.env(\.(?!example$|sample$|template$)[\w.-]+)?$"),
     "archivo de variables de entorno con valores reales (usa .env.example)"),
    (re.compile(r"\.(pem|key|p12|pfx)$", re.I), "clave privada o certificado"),
    (re.compile(r"(^|[\\/])id_(rsa|ed25519|ecdsa)(\.pub)?$"), "clave SSH"),
    (re.compile(r"(^|[\\/])(credentials|secrets)\.json$", re.I), "archivo de credenciales"),
    (re.compile(r"(^|[\\/])\.claude\.json$"), "configuración de Claude con tokens"),
]

# ---- Secretos dentro del contenido que se va a escribir -------------------------------------
SECRETOS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "clave de la API de Anthropic"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{30,}"), "token personal de GitHub"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), "token de GitHub"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "clave de acceso de AWS"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "clave privada"),
    (re.compile(r"\bGOCSPX-[A-Za-z0-9_-]{20,}"), "secreto de cliente de Google"),
]

# ---- Comandos de Bash/PowerShell peligrosos -------------------------------------------------
COMANDOS = [
    (re.compile(r"\bgit\b.*\bpush\b.*(\s--force(?![-\w])|\s-f\b)"),
     "git push --force reescribe el historial remoto (usa --force-with-lease si es imprescindible)"),
    (re.compile(r"\bgit\b.*\bpush\b.*\b(main|master)\b"),
     "push directo a main/master: trabaja en una rama y abre un Pull Request"),
    (re.compile(r"\bgit\b.*\breset\b.*--hard"), "git reset --hard descarta cambios sin posibilidad de recuperarlos"),
    (re.compile(r"\bgit\b.*\bclean\b.*\s-\w*[fd]"), "git clean borra archivos no versionados"),
    (re.compile(r"\brm\s+-[a-zA-Z]*[rR]"), "rm recursivo: borra carpetas completas"),
    (re.compile(r"(?i)\bremove-item\b.*-recurse"), "Remove-Item -Recurse borra carpetas completas"),
    (re.compile(r"(?i)\b(drop\s+(table|database|schema)|truncate\s+(table\s+)?\w+)"),
     "sentencia SQL destructiva (DROP/TRUNCATE)"),
    (re.compile(r"(?i)\b(cat|type|more|less|head|tail|get-content|gc)\b[^|;&\n]*\.env(?!\.(example|sample|template))\b"),
     "leer .env expondría secretos en la conversación"),
    (re.compile(r"(?i)\b(curl|wget|iwr|invoke-webrequest)\b[^\n]*\|\s*(sh|bash|zsh|iex|invoke-expression|python)\b"),
     "descargar y ejecutar código remoto en un solo paso"),
]

RAMAS_PROTEGIDAS = {"main", "master"}


def rama_actual():
    try:
        r = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def textos_a_escribir(entrada):
    """Todo el texto que la herramienta va a escribir en el archivo."""
    partes = [entrada.get("content", ""), entrada.get("new_string", "")]
    for e in entrada.get("edits", []) or []:
        partes.append(e.get("new_string", ""))
    return [p for p in partes if isinstance(p, str)]


def revisar_archivo(entrada):
    ruta = entrada.get("file_path", "")
    for patron, motivo in ARCHIVOS_PROTEGIDOS:
        if patron.search(ruta):
            return f"no se puede modificar '{ruta}': {motivo}."
    for texto in textos_a_escribir(entrada):
        for patron, motivo in SECRETOS:
            if patron.search(texto):
                return f"el contenido incluye una {motivo}. Usa una variable de entorno y .env.example."
    return None


def revisar_comando(entrada):
    comando = entrada.get("command", "")
    for patron, motivo in COMANDOS:
        if patron.search(comando):
            return motivo + "."
    for patron, motivo in SECRETOS:
        if patron.search(comando):
            return f"el comando incluye una {motivo}."
    if re.search(r"\bgit\b.*\bcommit\b", comando) and rama_actual() in RAMAS_PROTEGIDAS:
        return f"commit directo en '{rama_actual()}': crea una rama (git switch -c feat/...)."
    return None


def main():
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        datos = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    herramienta = datos.get("tool_name", "")
    entrada = datos.get("tool_input", {}) or {}

    if herramienta in ("Edit", "Write", "MultiEdit"):
        motivo = revisar_archivo(entrada)
    elif herramienta in ("Bash", "PowerShell"):
        motivo = revisar_comando(entrada)
    else:
        return 0

    if motivo:
        print(f"Guardián de TaskFlow AI: acción bloqueada, {motivo}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
