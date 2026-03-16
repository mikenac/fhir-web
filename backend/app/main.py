"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.engine import dispose_engine, init_engine
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
    """Manage application lifespan: start DB engine on startup, dispose on shutdown."""
    logger.info("Initializing database engine...")
    init_engine()
    logger.info("Database engine ready.")
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
