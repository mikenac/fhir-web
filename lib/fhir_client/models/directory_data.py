"""Directory FHIR models - Location, Organization, HealthcareService"""

from typing import Optional, cast

from pydantic import BaseModel

from fhir.resources.R4B.address import Address
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.contactpoint import ContactPoint
from fhir.resources.R4B.healthcareservice import HealthcareService
from fhir.resources.R4B.identifier import Identifier
from fhir.resources.R4B.location import Location
from fhir.resources.R4B.organization import Organization
from fhir.resources.R4B.reference import Reference


# Location
class LocationInput(BaseModel):
    """Input for a physical location"""

    name: str
    status: str = "active"
    type_code: Optional[str] = None  # e.g., HOSP, CLINIC
    type_display: Optional[str] = None
    type_system: str = "http://terminology.hl7.org/CodeSystem/v3-RoleCode"
    phone: Optional[str] = None
    address_line: Optional[list[str]] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    managing_organization_id: Optional[str] = None
    description: Optional[str] = None


def create_location(location: LocationInput) -> Location:
    """Create FHIR Location resource"""
    fhir_location = Location(name=location.name, status=location.status)

    if location.type_code:
        fhir_location.type = [
            CodeableConcept(
                coding=[
                    Coding(
                        system=location.type_system,
                        code=location.type_code,
                        display=location.type_display,
                    )
                ]
            )
        ]

    if location.phone:
        fhir_location.telecom = [ContactPoint(system="phone", value=location.phone, use="work")]

    if any(
        [
            location.address_line,
            location.city,
            location.state,
            location.postal_code,
            location.country,
        ]
    ):
        fhir_location.address = Address(
            line=cast(list[str | None], location.address_line),
            city=location.city,
            state=location.state,
            postalCode=location.postal_code,
            country=location.country,
        )

    if location.managing_organization_id:
        fhir_location.managingOrganization = Reference(
            reference=f"Organization/{location.managing_organization_id}"
        )

    if location.description:
        fhir_location.description = location.description

    return fhir_location


# Organization
class OrganizationInput(BaseModel):
    """Input for an organization"""

    name: str
    active: bool = True
    type_code: Optional[str] = None  # e.g., prov, dept, ins
    type_display: Optional[str] = None
    type_system: str = "http://terminology.hl7.org/CodeSystem/organization-type"
    npi: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address_line: Optional[list[str]] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    part_of_id: Optional[str] = None  # parent organization


def create_organization(org: OrganizationInput) -> Organization:
    """Create FHIR Organization resource"""
    fhir_org = Organization(name=org.name, active=org.active)

    if org.type_code:
        fhir_org.type = [
            CodeableConcept(
                coding=[
                    Coding(
                        system=org.type_system,
                        code=org.type_code,
                        display=org.type_display,
                    )
                ]
            )
        ]

    if org.npi:
        fhir_org.identifier = [
            Identifier(
                system="http://hl7.org/fhir/sid/us-npi",
                value=org.npi,
            )
        ]

    telecom = []
    if org.phone:
        telecom.append(ContactPoint(system="phone", value=org.phone, use="work"))
    if org.email:
        telecom.append(ContactPoint(system="email", value=org.email, use="work"))
    if telecom:
        fhir_org.telecom = telecom

    if any([org.address_line, org.city, org.state, org.postal_code, org.country]):
        fhir_org.address = [
            Address(
                line=cast(list[str | None], org.address_line),
                city=org.city,
                state=org.state,
                postalCode=org.postal_code,
                country=org.country,
            )
        ]

    if org.part_of_id:
        fhir_org.partOf = Reference(reference=f"Organization/{org.part_of_id}")

    return fhir_org


# HealthcareService
class HealthcareServiceInput(BaseModel):
    """Input for a healthcare service offering"""

    name: str
    active: bool = True
    provided_by_id: Optional[str] = None  # Organization
    category_code: Optional[str] = None
    category_display: Optional[str] = None
    type_code: Optional[str] = None
    type_display: Optional[str] = None
    location_ids: Optional[list[str]] = None
    phone: Optional[str] = None
    comment: Optional[str] = None


def create_healthcare_service(svc: HealthcareServiceInput) -> HealthcareService:
    """Create FHIR HealthcareService resource"""
    fhir_svc = HealthcareService(active=svc.active)
    fhir_svc.name = svc.name

    if svc.provided_by_id:
        fhir_svc.providedBy = Reference(reference=f"Organization/{svc.provided_by_id}")

    if svc.category_code:
        fhir_svc.category = [
            CodeableConcept(coding=[Coding(code=svc.category_code, display=svc.category_display)])
        ]

    if svc.type_code:
        fhir_svc.type = [
            CodeableConcept(coding=[Coding(code=svc.type_code, display=svc.type_display)])
        ]

    if svc.location_ids:
        fhir_svc.location = [
            Reference(reference=f"Location/{loc_id}") for loc_id in svc.location_ids
        ]

    if svc.phone:
        fhir_svc.telecom = [ContactPoint(system="phone", value=svc.phone, use="work")]

    if svc.comment:
        fhir_svc.comment = svc.comment

    return fhir_svc
