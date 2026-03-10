"""Directory service - locations, organizations, healthcare services"""

from typing import Optional

from fhir.resources.R4B.healthcareservice import HealthcareService
from fhir.resources.R4B.location import Location
from fhir.resources.R4B.organization import Organization

from ..client.fhir_client import FHIRClient
from ..models.directory_data import (
    HealthcareServiceInput,
    LocationInput,
    OrganizationInput,
    create_healthcare_service,
    create_location,
    create_organization,
)


class DirectoryService:
    """Service for managing directory resources"""

    def __init__(self, client: FHIRClient):
        self.client = client

    # Locations
    async def create_location(self, location: LocationInput) -> Location:
        """Create a physical location"""
        return await self.client.create(create_location(location))

    async def get_location(self, location_id: str) -> Location:
        """Get location by ID"""
        return await self.client.read("Location", location_id, Location)

    async def update_location(self, location_id: str, location: LocationInput) -> Location:
        """Update a physical location"""
        resource = create_location(location)
        resource.id = location_id
        return await self.client.update(resource)

    async def delete_location(self, location_id: str) -> None:
        """Delete a physical location"""
        await self.client.delete("Location", location_id)

    async def search_locations(
        self, name: Optional[str] = None, organization_id: Optional[str] = None
    ) -> list[Location]:
        """Search locations by name or managing organization"""
        params: dict[str, str] = {}
        if name:
            params["name"] = name
        if organization_id:
            params["organization"] = organization_id
        return await self.client.search("Location", Location, params)

    # Organizations
    async def create_organization(self, org: OrganizationInput) -> Organization:
        """Create an organization"""
        return await self.client.create(create_organization(org))

    async def get_organization(self, organization_id: str) -> Organization:
        """Get organization by ID"""
        return await self.client.read("Organization", organization_id, Organization)

    async def update_organization(
        self, organization_id: str, org: OrganizationInput
    ) -> Organization:
        """Update an organization"""
        resource = create_organization(org)
        resource.id = organization_id
        return await self.client.update(resource)

    async def delete_organization(self, organization_id: str) -> None:
        """Delete an organization"""
        await self.client.delete("Organization", organization_id)

    async def search_organizations(self, name: Optional[str] = None) -> list[Organization]:
        """Search organizations by name"""
        params: dict[str, str] = {}
        if name:
            params["name"] = name
        return await self.client.search("Organization", Organization, params)

    # HealthcareServices
    async def create_healthcare_service(self, svc: HealthcareServiceInput) -> HealthcareService:
        """Create a healthcare service"""
        return await self.client.create(create_healthcare_service(svc))

    async def get_healthcare_service(self, service_id: str) -> HealthcareService:
        """Get healthcare service by ID"""
        return await self.client.read("HealthcareService", service_id, HealthcareService)

    async def update_healthcare_service(
        self, service_id: str, svc: HealthcareServiceInput
    ) -> HealthcareService:
        """Update a healthcare service"""
        resource = create_healthcare_service(svc)
        resource.id = service_id
        return await self.client.update(resource)

    async def delete_healthcare_service(self, service_id: str) -> None:
        """Delete a healthcare service"""
        await self.client.delete("HealthcareService", service_id)

    async def get_organization_services(self, organization_id: str) -> list[HealthcareService]:
        """Get all healthcare services for an organization"""
        return await self.client.search(
            "HealthcareService", HealthcareService, {"organization": organization_id}
        )
