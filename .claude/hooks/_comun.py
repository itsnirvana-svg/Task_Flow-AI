"""Utilidades compartidas por los hooks de TaskFlow AI (una sola definición, sin duplicados)."""

import re

# Secretos con formato reconocible. Si aparece un formato nuevo, se añade aquí y lo usan todos.
SECRETOS_CONOCIDOS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "clave de la API de Anthropic"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{30,}"), "token personal de GitHub"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), "token de GitHub"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "clave de acceso de AWS"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "clave privada"),
    (re.compile(r"\bGOCSPX-[A-Za-z0-9_-]{20,}"), "secreto de cliente de Google"),
]
