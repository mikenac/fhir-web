"""FastAPI dependencies for dependency injection."""

from typing import AsyncGenerator, Optional

from fastapi import Depends, Query

# FHIR library installed from ../fhir
from fhir_client.client.fhir_client import FHIRClient
from fhir_client.services.clinical_service import ClinicalService
from fhir_client.services.operational_service import OperationalService
from fhir_client.services.patient_service import PatientService
from fhir_client.utils.backend_services import BackendServicesAuth

from app.config import Settings, get_settings


# Server configuration mapping
SERVER_CONFIGS = {
    "smart": {
        "base_url": "https://launch.smarthealthit.org/v/r4/fhir",
        "requires_auth": False,
    },
    "hapi": {
        "base_url": "https://hapi.fhir.org/baseR4",
        "requires_auth": False,
    },
    "epic": {
        "base_url": "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/",
        "requires_auth": True,
    },
}


async def get_fhir_client(
    server: Optional[str] = Query(None, description="FHIR server to use (smart, hapi, epic)"),
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[FHIRClient, None]:
    """
    Dependency that provides a FHIR client instance.

    The client is created with a context manager to ensure proper cleanup.
    Supports dynamic server selection and Epic Backend Services authentication.

    Args:
        server: Optional server identifier (smart, hapi, epic). If not provided,
                uses settings from environment variables.
        settings: Application settings from environment.
    """
    # Determine server configuration
    if server and server in SERVER_CONFIGS:
        # Use specified server
        server_config = SERVER_CONFIGS[server]
        base_url = server_config["base_url"]
        requires_auth = server_config["requires_auth"]
    else:
        # Default to SMART Health IT when no server is specified
        server_config = SERVER_CONFIGS["smart"]
        base_url = server_config["base_url"]
        requires_auth = server_config["requires_auth"]

    # Check if Epic Backend Services authentication is needed
    if requires_auth or (server == "epic"):
        # Load private key from environment or file
        import os

        private_key = os.getenv("EPIC_PRIVATE_KEY")

        if not private_key:
            # Fall back to file path
            if not settings.epic_private_key_path:
                raise ValueError("Either EPIC_PRIVATE_KEY env var or epic_private_key_path must be set")

            if not os.path.exists(settings.epic_private_key_path):
                raise ValueError(f"Private key file not found: {settings.epic_private_key_path}")

            with open(settings.epic_private_key_path, "r") as f:
                private_key = f.read()

        # Create backend services auth
        backend_auth = BackendServicesAuth(
            token_url=settings.epic_token_url or "",
            client_id=settings.epic_client_id or "",
            private_key=private_key,
            key_id=settings.epic_key_id,
            scopes=settings.epic_scopes.split(),
            algorithm=settings.epic_jwt_algorithm,
        )

        # Get access token
        access_token = await backend_auth.get_access_token()

        # Create client with access token
        async with FHIRClient(
            base_url=base_url,
            auth_token=access_token,
            timeout=settings.fhir_timeout,
        ) as client:
            yield client
    else:
        # Use simple auth token or no auth
        async with FHIRClient(
            base_url=base_url,
            auth_token=settings.fhir_auth_token if not server else None,
            timeout=settings.fhir_timeout,
        ) as client:
            yield client


def get_patient_service(
    client: FHIRClient = Depends(get_fhir_client),
) -> PatientService:
    """Dependency that provides a PatientService instance."""
    return PatientService(client)


def get_clinical_service(
    client: FHIRClient = Depends(get_fhir_client),
) -> ClinicalService:
    """Dependency that provides a ClinicalService instance."""
    return ClinicalService(client)


def get_operational_service(
    client: FHIRClient = Depends(get_fhir_client),
) -> OperationalService:
    """Dependency that provides an OperationalService instance."""
    return OperationalService(client)
