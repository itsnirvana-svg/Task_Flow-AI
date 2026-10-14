from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401  (registra las tablas en Base.metadata)
from .config import settings
from .database import Base, engine
from .routers import ai, tasks


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Desarrollo: crea las tablas si no existen. En producción se usarán migraciones.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="TaskFlow AI", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)
app.include_router(ai.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
