from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from . import models  # noqa: F401  (registra las tablas en Base.metadata)
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import ai, auth, tasks
from .security import current_principal
from .services import events
from .services.task_service import TaskNotFoundError


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Desarrollo: crea las tablas si no existen. En producción se usarán migraciones.
    Base.metadata.create_all(engine)
    dispatcher = events.Dispatcher(SessionLocal)
    app.state.dispatcher = dispatcher
    dispatcher.start()
    yield
    # Los eventos aún sin enviar quedan en la base de datos y salen al volver a arrancar.
    dispatcher.stop(timeout=5.0)


def docs_urls(app_env: str) -> dict[str, str | None]:
    """La documentación interactiva (/docs) solo se publica en desarrollo: en producción
    describiría toda la API a cualquiera."""
    if app_env == "production":
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


app = FastAPI(
    title="TaskFlow AI", version="0.2.0", lifespan=lifespan, **docs_urls(settings.app_env)
)


@app.middleware("http")
async def api_security_headers(request: Request, call_next):
    """Las respuestas de la API no se interpretan como otro tipo ni se guardan en cachés."""
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
    return response


app.add_middleware(GZipMiddleware, minimum_size=1000)  # listados grandes: menos bytes
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# El inicio de sesión es público (es lo que da acceso); el resto exige credenciales.
# /health queda abierto para que el alojamiento compruebe que la API responde.
app.include_router(auth.router)
protected = [Depends(current_principal)]
app.include_router(tasks.router, dependencies=protected)
app.include_router(ai.router, dependencies=protected)


@app.exception_handler(TaskNotFoundError)
async def task_not_found_handler(_: Request, __: TaskNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Tarea no encontrada"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
