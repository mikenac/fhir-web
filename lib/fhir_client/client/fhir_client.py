"""Async FHIR client using httpx"""

import os
from types import TracebackType
from typing import Any, Optional, Self, Type, TypeVar

import httpx
from dotenv import load_dotenv
from fhir.resources.R4B.resource import Resource

load_dotenv()

T = TypeVar("T", bound=Resource)


class FHIRClient:
    """Async FHIR R4 client for interacting with FHIR servers"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: int = 30,
        oauth2_token_manager: Optional[Any] = None,
    ):
        """
        Initialize FHIR client

        Args:
            base_url: FHIR server base URL (defaults to env FHIR_BASE_URL)
            auth_token: Authentication token (defaults to env FHIR_AUTH_TOKEN)
            timeout: Request timeout in seconds
            oauth2_token_manager: Optional OAuth2TokenManager for automatic token refresh
        """
        self.base_url = base_url or os.getenv("FHIR_BASE_URL", "")
        self.auth_token = auth_token or os.getenv("FHIR_AUTH_TOKEN")
        self.timeout = timeout
        self.oauth2_token_manager = oauth2_token_manager

        if not self.base_url:
            raise ValueError("FHIR_BASE_URL must be set in environment or passed to constructor")

        # Ensure base URL ends with /
        if not self.base_url.endswith("/"):
            self.base_url += "/"

        # Setup headers
        self.headers = {
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
        }

        # Add auth token if provided
        if self.auth_token:
            self.headers["Authorization"] = f"Bearer {self.auth_token}"
        elif self.oauth2_token_manager:
            # Get token from OAuth2 manager
            token = self.oauth2_token_manager.get_token()
            if token:
                self.headers["Authorization"] = f"Bearer {token}"

        # Create async client
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=timeout,
        )

    def set_access_token(self, token: str) -> None:
        """
        Update access token (useful for OAuth2 flows)

        Args:
            token: New access token
        """
        self.auth_token = token
        self.headers["Authorization"] = f"Bearer {token}"
        # Update client headers
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    async def close(self) -> None:
        """Close the HTTP client"""
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        """Context manager entry"""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Context manager exit"""
        await self.close()

    async def read(self, resource_type: str, resource_id: str, resource_class: Type[T]) -> T:
        """
        Read a resource by ID

        Args:
            resource_type: FHIR resource type (e.g., 'Patient')
            resource_id: Resource ID
            resource_class: FHIR resource class to parse response into

        Returns:
            Parsed FHIR resource
        """
        url = f"{resource_type}/{resource_id}"
        response = await self.client.get(url)
        response.raise_for_status()

        # Handle both parse_obj() and model_validate() methods
        if hasattr(resource_class, "model_validate"):
            return resource_class.model_validate(response.json())
        else:
            return resource_class.parse_obj(response.json())

    async def create(self, resource: T) -> T:
        """
        Create a new resource

        Args:
            resource: FHIR resource to create

        Returns:
            Created resource with server-assigned ID
        """
        # Handle both old and new fhir.resources API
        resource_type = getattr(resource, "resource_type", None) or getattr(
            resource, "__resource_type__", None
        )
        if not resource_type:
            resource_type = resource.__class__.__name__

        url = resource_type

        # Handle both dict() and model_dump() methods
        if hasattr(resource, "model_dump"):
            data = resource.model_dump(mode="json", exclude_none=True)
        else:
            data = resource.dict(exclude_none=True)

        response = await self.client.post(url, json=data)
        response.raise_for_status()

        # Handle both parse_obj() and model_validate() methods
        if hasattr(type(resource), "model_validate"):
            return type(resource).model_validate(response.json())
        else:
            return type(resource).parse_obj(response.json())

    async def update(self, resource: T) -> T:
        """
        Update an existing resource

        Args:
            resource: FHIR resource to update (must have ID)

        Returns:
            Updated resource
        """
        if not resource.id:
            raise ValueError("Resource must have an ID to update")

        # Handle both old and new fhir.resources API
        resource_type = getattr(resource, "resource_type", None) or getattr(
            resource, "__resource_type__", None
        )
        if not resource_type:
            resource_type = resource.__class__.__name__

        url = f"{resource_type}/{resource.id}"

        # Handle both dict() and model_dump() methods
        if hasattr(resource, "model_dump"):
            data = resource.model_dump(mode="json", exclude_none=True)
        else:
            data = resource.dict(exclude_none=True)

        response = await self.client.put(url, json=data)
        response.raise_for_status()

        # Handle both parse_obj() and model_validate() methods
        if hasattr(type(resource), "model_validate"):
            return type(resource).model_validate(response.json())
        else:
            return type(resource).parse_obj(response.json())

    async def delete(self, resource_type: str, resource_id: str) -> None:
        """
        Delete a resource

        Args:
            resource_type: FHIR resource type
            resource_id: Resource ID
        """
        url = f"{resource_type}/{resource_id}"
        response = await self.client.delete(url)
        response.raise_for_status()

    async def search(
        self,
        resource_type: str,
        resource_class: Type[T],
        params: Optional[dict[str, Any]] = None,
    ) -> list[T]:
        """
        Search for resources

        Args:
            resource_type: FHIR resource type to search
            resource_class: FHIR resource class to parse results into
            params: Search parameters

        Returns:
            List of matching resources
        """
        url = resource_type
        response = await self.client.get(url, params=params or {})
        response.raise_for_status()

        bundle = response.json()
        resources = []

        if bundle.get("resourceType") == "Bundle":
            for entry in bundle.get("entry", []):
                if "resource" in entry:
                    # Handle both parse_obj() and model_validate() methods
                    if hasattr(resource_class, "model_validate"):
                        resources.append(resource_class.model_validate(entry["resource"]))
                    else:
                        resources.append(resource_class.parse_obj(entry["resource"]))

        return resources

    async def search_by_identifier(
        self,
        resource_type: str,
        resource_class: Type[T],
        identifier_system: str,
        identifier_value: str,
    ) -> list[T]:
        """
        Search for resources by identifier

        Args:
            resource_type: FHIR resource type
            resource_class: FHIR resource class
            identifier_system: Identifier system (e.g., MRN system)
            identifier_value: Identifier value

        Returns:
            List of matching resources
        """
        params = {"identifier": f"{identifier_system}|{identifier_value}"}
        return await self.search(resource_type, resource_class, params)
