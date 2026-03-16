"""Main FastAPI application."""

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.engine import dispose_engine, init_engine, run_migrations
from app.middleware.error_handlers import (
    connect_error_handler,
    http_status_error_handler,
    timeout_error_handler,
)
from app.models.responses import HealthResponse
from app.routers import clinical, operational, patients, pipeline, webhooks

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: start DB engine on startup, dispose on shutdown.

    Startup order:
    1. init_engine() — creates the SQLAlchemy engine and session factory.
    2. run_migrations() — applies any pending Alembic migrations so all tables
       exist before the first request arrives.  On a fresh Render deploy the
       DuckDB file is brand-new, so this step is what actually creates the
       tables.  On subsequent deploys it is a no-op if the schema is current.
    """
    import sys
    logger.info("Initializing database engine...")
    print("LIFESPAN: before init_engine", flush=True, file=sys.stderr)
    init_engine()
    print("LIFESPAN: after init_engine", flush=True, file=sys.stderr)
    logger.info("Running database migrations...")
    # run_migrations() is synchronous and can block for several seconds on a
    # fresh DuckDB file.  Running it in the default thread-pool executor keeps
    # the event loop responsive and prevents the async lifespan from deadlocking
    # with DuckDB's internal threading.
    loop = asyncio.get_event_loop()
    print("LIFESPAN: before run_in_executor", flush=True, file=sys.stderr)
    await loop.run_in_executor(None, run_migrations)
    print("LIFESPAN: after run_in_executor", flush=True, file=sys.stderr)
    logger.info("Database ready.")
    print("LIFESPAN: yielding", flush=True, file=sys.stderr)
    yield
    logger.info("Shutting down database engine...")
    dispose_engine()
    logger.info("Database engine disposed.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="RESTful API for interacting with FHIR servers",
    debug=settings.debug,
    lifespan=lifespan,
)

# Parse CORS origins (can be string or list)
cors_origins = settings.cors_origins
if isinstance(cors_origins, str):
    # If it's a string, split by comma or treat as single origin
    cors_origins = [origin.strip() for origin in cors_origins.split(",")] if "," in cors_origins else [cors_origins]

# CORS middleware - using wildcard to fix persistent CORS issues
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(httpx.HTTPStatusError, http_status_error_handler)
app.add_exception_handler(httpx.ConnectError, connect_error_handler)
app.add_exception_handler(httpx.TimeoutException, timeout_error_handler)

# Include routers
app.include_router(patients.router, prefix="/api/patients", tags=["Patients"])
app.include_router(clinical.router, prefix="/api/clinical", tags=["Clinical"])
app.include_router(operational.router, prefix="/api/operational", tags=["Operational"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["Pipeline"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])


@app.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
    )


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Detailed health check endpoint."""
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
    )
