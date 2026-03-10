"""Main FastAPI application."""

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.middleware.error_handlers import (
    connect_error_handler,
    http_status_error_handler,
    timeout_error_handler,
)
from app.models.responses import HealthResponse
from app.routers import clinical, operational, patients

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="RESTful API for interacting with FHIR servers",
    debug=settings.debug,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
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
