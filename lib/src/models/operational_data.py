"""Operational data FHIR models - Coverage, Authorization, Practitioners"""

from datetime import datetime, timezone
from typing import Literal, Optional, TypeAlias, cast

from pydantic import BaseModel

from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.contactpoint import ContactPoint
from fhir.resources.R4B.coverage import Coverage, CoverageClass
from fhir.resources.R4B.coverageeligibilityresponse import (
    CoverageEligibilityResponse,
    CoverageEligibilityResponseInsurance,
    CoverageEligibilityResponseInsuranceItem,
)
from fhir.resources.R4B.humanname import HumanName
from fhir.resources.R4B.identifier import Identifier
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.practitioner import Practitioner
from fhir.resources.R4B.practitionerrole import PractitionerRole
from fhir.resources.R4B.reference import Reference

# FHIR R4B value-set type aliases
CoverageStatus: TypeAlias = Literal["active", "cancelled", "draft", "entered-in-error"]
EligibilityOutcome: TypeAlias = Literal["complete", "error", "partial"]
AdministrativeGender: TypeAlias = Literal["male", "female", "other", "unknown"]


# Registration Data (Patient Coverage/Insurance)
class CoverageInput(BaseModel):
    """Input for patient insurance coverage"""

    patient_id: str
    subscriber_id: str
    payor_id: str  # Insurance organization
    payor_name: str
    member_id: str
    group_id: Optional[str] = None
    status: CoverageStatus = "active"
    type_code: Optional[str] = None  # e.g., EHCPOL for extended healthcare
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


def create_coverage(coverage: CoverageInput) -> Coverage:
    """Create FHIR Coverage resource"""
    fhir_coverage = Coverage(
        status=coverage.status,
        beneficiary=Reference(reference=f"Patient/{coverage.patient_id}"),
        subscriber=Reference(reference=f"Patient/{coverage.subscriber_id}"),
        subscriberId=coverage.member_id,
        payor=[
            Reference(reference=f"Organization/{coverage.payor_id}", display=coverage.payor_name)
        ],
    )

    if coverage.type_code:
        fhir_coverage.type = CodeableConcept(
            coding=[
                Coding(
                    system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
                    code=coverage.type_code,
                )
            ]
        )

    if coverage.group_id:
        fhir_coverage.class_fhir = [
            CoverageClass(
                type=CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/coverage-class",
                            code="group",
                        )
                    ]
                ),
                value=coverage.group_id,
            )
        ]

    if coverage.period_start or coverage.period_end:
        start = (
            coverage.period_start.replace(tzinfo=timezone.utc)
            if coverage.period_start and not coverage.period_start.tzinfo
            else coverage.period_start
        )
        end = (
            coverage.period_end.replace(tzinfo=timezone.utc)
            if coverage.period_end and not coverage.period_end.tzinfo
            else coverage.period_end
        )
        fhir_coverage.period = Period(start=start, end=end)

    return fhir_coverage


# Prior Authorization Status
class AuthorizationStatusInput(BaseModel):
    """Input for authorization status check"""

    patient_id: str
    coverage_id: str
    status: CoverageStatus = "active"
    outcome: EligibilityOutcome
    disposition: Optional[str] = None
    service_code: Optional[str] = None
    service_display: Optional[str] = None


def create_coverage_eligibility_response(
    auth: AuthorizationStatusInput,
) -> CoverageEligibilityResponse:
    """Create FHIR CoverageEligibilityResponse"""
    response = CoverageEligibilityResponse(
        status=auth.status,
        purpose=["validation"],
        patient=Reference(reference=f"Patient/{auth.patient_id}"),
        created=datetime.now(timezone.utc),
        outcome=auth.outcome,
        disposition=auth.disposition,
        insurer=Reference(reference="Organization/unknown"),
        request=Reference(reference="CoverageEligibilityRequest/unknown"),
        insurance=[
            CoverageEligibilityResponseInsurance(
                coverage=Reference(reference=f"Coverage/{auth.coverage_id}"),
                inforce=auth.outcome == "complete",
            )
        ],
    )

    if auth.service_code and response.insurance:
        response.insurance[0].item = [
            CoverageEligibilityResponseInsuranceItem(
                category=CodeableConcept(
                    coding=[Coding(code=auth.service_code, display=auth.service_display)]
                )
            )
        ]

    return response


# Provider Personnel Data
class PractitionerInput(BaseModel):
    """Input for practitioner"""

    family_name: str
    given_names: list[str]
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    npi: Optional[str] = None  # National Provider Identifier
    gender: Optional[AdministrativeGender] = None
    phone: Optional[str] = None
    email: Optional[str] = None


def create_practitioner(practitioner: PractitionerInput) -> Practitioner:
    """Create FHIR Practitioner resource"""
    name = HumanName(
        family=practitioner.family_name,
        given=cast(list[str | None], practitioner.given_names),
        prefix=[practitioner.prefix] if practitioner.prefix else None,
        suffix=[practitioner.suffix] if practitioner.suffix else None,
        use="official",
    )

    fhir_practitioner = Practitioner(name=[name], active=True)

    # NPI identifier
    if practitioner.npi:
        fhir_practitioner.identifier = [
            Identifier(
                system="http://hl7.org/fhir/sid/us-npi",
                value=practitioner.npi,
                type=CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/v2-0203",
                            code="NPI",
                        )
                    ]
                ),
            )
        ]

    # Gender
    if practitioner.gender:
        fhir_practitioner.gender = practitioner.gender

    # Telecom
    telecom = []
    if practitioner.phone:
        telecom.append(ContactPoint(system="phone", value=practitioner.phone, use="work"))
    if practitioner.email:
        telecom.append(ContactPoint(system="email", value=practitioner.email, use="work"))
    if telecom:
        fhir_practitioner.telecom = telecom

    return fhir_practitioner


class PractitionerRoleInput(BaseModel):
    """Input for practitioner role"""

    practitioner_id: str
    organization_id: Optional[str] = None
    role_code: str
    role_display: str
    specialty_code: Optional[str] = None
    specialty_display: Optional[str] = None
    location_ids: Optional[list[str]] = None
    active: bool = True


def create_practitioner_role(role: PractitionerRoleInput) -> PractitionerRole:
    """Create FHIR PractitionerRole resource"""
    fhir_role = PractitionerRole(
        active=role.active,
        practitioner=Reference(reference=f"Practitioner/{role.practitioner_id}"),
        code=[CodeableConcept(coding=[Coding(code=role.role_code, display=role.role_display)])],
    )

    if role.organization_id:
        fhir_role.organization = Reference(reference=f"Organization/{role.organization_id}")

    if role.specialty_code:
        fhir_role.specialty = [
            CodeableConcept(
                coding=[Coding(code=role.specialty_code, display=role.specialty_display)]
            )
        ]

    if role.location_ids:
        fhir_role.location = [
            Reference(reference=f"Location/{loc_id}") for loc_id in role.location_ids
        ]

    return fhir_role
