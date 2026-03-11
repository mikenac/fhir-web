"""Operational data service - coverage, authorization, practitioners"""

from fhir.resources.R4B.coverage import Coverage
from fhir.resources.R4B.coverageeligibilityresponse import CoverageEligibilityResponse
from fhir.resources.R4B.practitioner import Practitioner
from fhir.resources.R4B.practitionerrole import PractitionerRole

from ..client.fhir_client import FHIRClient
from ..models.operational_data import (
    AuthorizationStatusInput,
    CoverageInput,
    PractitionerInput,
    PractitionerRoleInput,
    create_coverage,
    create_coverage_eligibility_response,
    create_practitioner,
    create_practitioner_role,
)


class OperationalService:
    """Service for managing operational data"""

    def __init__(self, client: FHIRClient):
        self.client = client

    # Coverage (Insurance/Registration)
    async def create_coverage(self, coverage: CoverageInput) -> Coverage:
        """Create patient insurance coverage"""
        return await self.client.create(create_coverage(coverage))

    async def get_coverage(self, coverage_id: str) -> Coverage:
        """Get coverage by ID"""
        return await self.client.read("Coverage", coverage_id, Coverage)

    async def update_coverage(self, coverage_id: str, coverage: CoverageInput) -> Coverage:
        """Update patient insurance coverage"""
        resource = create_coverage(coverage)
        resource.id = coverage_id
        return await self.client.update(resource)

    async def delete_coverage(self, coverage_id: str) -> None:
        """Delete patient insurance coverage"""
        await self.client.delete("Coverage", coverage_id)

    async def get_patient_coverage(self, patient_id: str) -> list[Coverage]:
        """Get all coverage for a patient"""
        return await self.client.search("Coverage", Coverage, {"beneficiary": patient_id})

    # Prior Authorization
    async def create_authorization_status(
        self, auth: AuthorizationStatusInput
    ) -> CoverageEligibilityResponse:
        """Create authorization status response"""
        return await self.client.create(create_coverage_eligibility_response(auth))

    async def get_authorization_status(self, response_id: str) -> CoverageEligibilityResponse:
        """Get authorization status by ID"""
        return await self.client.read(
            "CoverageEligibilityResponse", response_id, CoverageEligibilityResponse
        )

    async def delete_authorization_status(self, response_id: str) -> None:
        """Delete an authorization status response"""
        await self.client.delete("CoverageEligibilityResponse", response_id)

    # Practitioners
    async def create_practitioner(self, practitioner: PractitionerInput) -> Practitioner:
        """Create a practitioner"""
        return await self.client.create(create_practitioner(practitioner))

    async def get_practitioner(self, practitioner_id: str) -> Practitioner:
        """Get practitioner by ID"""
        return await self.client.read("Practitioner", practitioner_id, Practitioner)

    async def update_practitioner(
        self, practitioner_id: str, practitioner: PractitionerInput
    ) -> Practitioner:
        """Update a practitioner"""
        resource = create_practitioner(practitioner)
        resource.id = practitioner_id
        return await self.client.update(resource)

    async def delete_practitioner(self, practitioner_id: str) -> None:
        """Delete a practitioner"""
        await self.client.delete("Practitioner", practitioner_id)

    async def get_practitioner_by_npi(self, npi: str) -> list[Practitioner]:
        """Get practitioner by NPI"""
        return await self.client.search_by_identifier(
            "Practitioner", Practitioner, "http://hl7.org/fhir/sid/us-npi", npi
        )

    # Practitioner Roles
    async def create_practitioner_role(self, role: PractitionerRoleInput) -> PractitionerRole:
        """Create a practitioner role"""
        return await self.client.create(create_practitioner_role(role))

    async def get_practitioner_role(self, role_id: str) -> PractitionerRole:
        """Get practitioner role by ID"""
        return await self.client.read("PractitionerRole", role_id, PractitionerRole)

    async def update_practitioner_role(
        self, role_id: str, role: PractitionerRoleInput
    ) -> PractitionerRole:
        """Update a practitioner role"""
        resource = create_practitioner_role(role)
        resource.id = role_id
        return await self.client.update(resource)

    async def delete_practitioner_role(self, role_id: str) -> None:
        """Delete a practitioner role"""
        await self.client.delete("PractitionerRole", role_id)

    async def get_practitioner_roles(self, practitioner_id: str) -> list[PractitionerRole]:
        """Get all roles for a practitioner"""
        return await self.client.search(
            "PractitionerRole", PractitionerRole, {"practitioner": practitioner_id}
        )
