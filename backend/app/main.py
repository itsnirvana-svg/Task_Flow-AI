from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from . import models  # noqa: F401  (registra las tablas en Base.metadata)
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import ai, tasks
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


app = FastAPI(title="TaskFlow AI", version="0.2.0", lifespan=lifespan)

app.add_middleware(GZipMiddleware, minimum_size=1000)  # listados grandes: menos bytes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)
app.include_router(ai.router)


@app.exception_handler(TaskNotFoundError)
async def task_not_found_handler(_: Request, __: TaskNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Tarea no encontrada"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
