from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from . import crud
from .api.v1.api import api_router
from .core.config import settings
from .core.observability import RequestLogMiddleware, gauge_loop, setup_logging
from .database import ensure_indexes, get_database

setup_logging(settings.LOG_LEVEL, settings.LOG_JSON)
logger = logging.getLogger("calaro")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db = get_database()
    await ensure_indexes(db)
    await crud.ensure_superadmin(db)
    if settings.SECRET_KEY in ("change-me-in-production", "your-secret-key-change-this-for-production"):
        logger.error("SECRET_KEY is still the default. Set a long random value in backend/.env before going live.")
    task = asyncio.create_task(gauge_loop(get_database, settings.METRICS_REFRESH_SECONDS))
    logger.info("calaro started", extra={"event": "startup"})
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(RequestLogMiddleware)

# HTTP traffic metrics at /metrics (only reachable inside the Docker network; Caddy doesn't route it)
Instrumentator(
    excluded_handlers=["/metrics", "/health"],
    should_group_untemplated=True,
).instrument(app, latency_lowr_buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)).expose(app, include_in_schema=False)


app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "CALARO API", "docs": "/docs"}


@app.get("/health")
async def health():
    await get_database().command("ping")
    return {"status": "ok", "database": "mongodb"}

