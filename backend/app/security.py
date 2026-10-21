"""Autenticación de la API.

Dos tipos de credencial, pensados para quien las usa:
- **Clave de API** (cabecera `X-API-Key`): para servicios como n8n o scripts. Se define una por
  cliente en `API_KEYS`, así se puede revocar una sin afectar a las demás.
- **Token de sesión** (cabecera `Authorization: Bearer ...`): para personas. Se obtiene con
  `POST /api/auth/login` y caduca. Es lo que debe usar el navegador: una clave de API metida en
  el JavaScript de una web estática sería pública.

Las contraseñas se guardan solo como hash `scrypt` con sal; nunca en claro.
"""

import base64
import hashlib
import hmac
import secrets
import time
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

ALGORITHM = "HS256"  # se fija al decodificar: así un token con otro algoritmo (o "none") se rechaza
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
SALT_BYTES = 16

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------- contraseñas


def hash_password(password: str) -> str:
    """Hash `scrypt$N$r$p$sal$hash` (sal y hash en base64), listo para `ADMIN_PASSWORD_HASH`."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
    )
    return "$".join(
        ["scrypt", str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P), _b64(salt), _b64(digest)]
    )


def verify_password(password: str, stored: str) -> bool:
    """¿Coincide la contraseña con el hash guardado? Un hash mal formado devuelve False."""
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(),
            salt=_unb64(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_unb64(expected)),
        )
        return hmac.compare_digest(digest, _unb64(expected))
    except (ValueError, TypeError):
        return False


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode(), validate=True)


# ---------------------------------------------------------------- tokens de sesión


def create_token(subject: str) -> tuple[str, int]:
    """Token firmado para `subject` y sus segundos de validez."""
    now = int(time.time())
    seconds = settings.auth_token_minutes * 60
    claims = {"sub": subject, "iat": now, "exp": now + seconds}
    return jwt.encode(claims, settings.auth_secret_key, algorithm=ALGORITHM), seconds


def decode_token(token: str) -> str | None:
    """Usuario del token, o None si está caducado, manipulado o firmado con otra clave."""
    if not settings.auth_secret_key:
        return None
    try:
        claims = jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
    subject = claims.get("sub")
    return subject if isinstance(subject, str) and subject else None


# ---------------------------------------------------------------- dependencia de las rutas


def _match_api_key(candidate: str) -> str | None:
    """Nombre del cliente cuya clave coincide. Se recorren todas, sin parar en la primera, y se
    compara en tiempo constante para no revelar por el tiempo cuánto se parece la clave."""
    found = None
    for name, key in settings.api_key_map.items():
        if hmac.compare_digest(candidate.encode(), key.encode()):
            found = name
    return found


def current_principal(
    api_key: Annotated[str | None, Depends(api_key_header)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    """Identifica a quien llama (`key:n8n`, `user:admin`) o responde 401.

    Es la dependencia que protege las rutas; el identificador sirve también para limitar el uso.
    """
    if settings.auth_disabled:
        return "dev:sin-autenticacion"
    if api_key and (name := _match_api_key(api_key)):
        return f"key:{name}"
    if credentials and (user := decode_token(credentials.credentials)):
        return f"user:{user}"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales no válidas o ausentes",
        headers={"WWW-Authenticate": "Bearer"},
    )


Principal = Annotated[str, Depends(current_principal)]
