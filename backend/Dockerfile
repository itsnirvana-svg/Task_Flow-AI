# Imagen de la API de TaskFlow AI (producción).
# Se construye desde la carpeta backend/:  docker build -t taskflow-api backend
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Primero las dependencias: así la capa se reutiliza mientras no cambie requirements.txt.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# La aplicación no necesita privilegios: se ejecuta con un usuario sin permisos especiales.
RUN useradd --system --uid 10001 --no-create-home taskflow
USER 10001

EXPOSE 8000

# --proxy-headers: detrás de Caddy, la dirección IP real del cliente llega en X-Forwarded-For
# (la usa el límite de intentos de inicio de sesión). "*" es seguro porque el puerto 8000 no se
# publica fuera de la red de Docker: solo lo alcanzan Caddy y n8n.
# Un solo proceso: los límites de uso se cuentan por proceso (ver app/ratelimit.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
