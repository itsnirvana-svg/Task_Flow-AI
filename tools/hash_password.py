"""Genera el hash de contraseña para `ADMIN_PASSWORD_HASH` (la contraseña no se guarda).

Uso, desde la raíz del proyecto:
    python tools/hash_password.py

Pide la contraseña sin mostrarla en pantalla y escribe el hash, que se pega en el `.env`.
Para generar una clave de API o `AUTH_SECRET_KEY`:
    python -c "import secrets; print(secrets.token_urlsafe(32))"
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.security import hash_password  # noqa: E402  (el import necesita la ruta de arriba)

MIN_LENGTH = 12


def main() -> None:
    password = getpass.getpass("Contraseña: ")
    if len(password) < MIN_LENGTH:
        sys.exit(f"Usa al menos {MIN_LENGTH} caracteres.")
    if password != getpass.getpass("Repite la contraseña: "):
        sys.exit("No coinciden.")
    print("\nADMIN_PASSWORD_HASH=" + hash_password(password))


if __name__ == "__main__":
    main()
