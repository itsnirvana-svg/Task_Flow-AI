"""Inicio de sesión de personas: `POST /api/auth/login` devuelve un token de sesión."""

import hmac
import math

from fastapi import APIRouter, HTTPException, Request

from ..config import settings
from ..ratelimit import RateLimiter
from ..schemas import LoginRequest, TokenResponse
from ..security import create_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Frena la fuerza bruta: intentos por minuto y por dirección IP.
login_limiter = RateLimiter(lambda: settings.login_max_attempts_per_minute)


def _too_many(wait: float) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail="Demasiados intentos; espera un momento",
        headers={"Retry-After": str(math.ceil(wait))},
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request) -> TokenResponse:
    """Cambia usuario y contraseña por un token que caduca. Úsalo como `Authorization: Bearer`."""
    if not settings.login_configured:
        raise HTTPException(status_code=503, detail="El inicio de sesión no está configurado")

    wait = login_limiter.retry_after(request.client.host if request.client else "desconocido")
    if wait is not None:
        raise _too_many(wait)

    # Se comprueban SIEMPRE usuario y contraseña (sin parar en el primer fallo) y el error es el
    # mismo en ambos casos: así no se sabe si el usuario existe ni por el tiempo de respuesta.
    user_ok = hmac.compare_digest(body.username.encode(), settings.admin_username.encode())
    password_ok = verify_password(body.password, settings.admin_password_hash)
    if not (user_ok and password_ok):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    token, expires_in = create_token(body.username)
    return TokenResponse(access_token=token, expires_in=expires_in)
