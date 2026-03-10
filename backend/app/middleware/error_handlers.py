"""Error handling middleware for FHIR operations."""

import httpx
from fastapi import Request, status
from fastapi.responses import JSONResponse


async def http_status_error_handler(
    request: Request, exc: httpx.HTTPStatusError
) -> JSONResponse:
    """
    Handle HTTPStatusError exceptions from the FHIR client.

    Translates FHIR server HTTP errors into appropriate API responses.
    """
    return JSONResponse(
        status_code=exc.response.status_code,
        content={
            "error": "FHIR server error",
            "detail": str(exc),
            "status_code": exc.response.status_code,
            "path": str(request.url.path),
        },
    )


async def connect_error_handler(request: Request, exc: httpx.ConnectError) -> JSONResponse:
    """
    Handle connection errors to the FHIR server.

    Returns a 503 Service Unavailable response.
    """
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "Cannot connect to FHIR server",
            "detail": str(exc),
            "path": str(request.url.path),
        },
    )


async def timeout_error_handler(request: Request, exc: httpx.TimeoutException) -> JSONResponse:
    """
    Handle timeout errors from the FHIR server.

    Returns a 504 Gateway Timeout response.
    """
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content={
            "error": "FHIR server request timeout",
            "detail": str(exc),
            "path": str(request.url.path),
        },
    )
