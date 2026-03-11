"""Patient demographics FHIR models"""

from datetime import date
from typing import Literal, Optional, TypeAlias, cast

from pydantic import BaseModel

from fhir.resources.R4B.address import Address
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.contactpoint import ContactPoint
from fhir.resources.R4B.humanname import HumanName
from fhir.resources.R4B.identifier import Identifier
from fhir.resources.R4B.patient import Patient

AdministrativeGender: TypeAlias = Literal["male", "female", "other", "unknown"]


class PatientDemographicsInput(BaseModel):
    """Input model for patient demographics"""

    # Name
    family_name: str
    given_names: list[str]
    prefix: Optional[str] = None
    suffix: Optional[str] = None

    # DOB
    birth_date: Optional[date] = None

    # MRN
    mrn: str
    mrn_system: str = "http://hospital.example.org/mrn"

    # Contact
    phone: Optional[str] = None
    email: Optional[str] = None

    # Address
    address_line: Optional[list[str]] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

    # Demographics
    gender: Optional[AdministrativeGender] = None


def create_patient_resource(demographics: PatientDemographicsInput) -> Patient:
    """
    Create a FHIR Patient resource from demographics input

    Args:
        demographics: Patient demographic data

    Returns:
        FHIR Patient resource
    """
    # Build name
    name = HumanName(
        family=demographics.family_name,
        given=cast(list[str | None], demographics.given_names),
        prefix=[demographics.prefix] if demographics.prefix else None,
        suffix=[demographics.suffix] if demographics.suffix else None,
        use="official",
    )

    # Build identifiers (MRN)
    identifiers = [
        Identifier(
            system=demographics.mrn_system,
            value=demographics.mrn,
            type=CodeableConcept(
                coding=[
                    Coding(
                        system="http://terminology.hl7.org/CodeSystem/v2-0203",
                        code="MR",
                        display="Medical Record Number",
                    )
                ]
            ),
        )
    ]

    # Build telecom (phone/email)
    telecom = []
    if demographics.phone:
        telecom.append(ContactPoint(system="phone", value=demographics.phone, use="mobile"))
    if demographics.email:
        telecom.append(ContactPoint(system="email", value=demographics.email, use="home"))

    # Build address
    address = None
    if any(
        [
            demographics.address_line,
            demographics.city,
            demographics.state,
            demographics.postal_code,
        ]
    ):
        address = [
            Address(
                line=(
                    cast(list[str | None], demographics.address_line)
                    if demographics.address_line
                    else None
                ),
                city=demographics.city,
                state=demographics.state,
                postalCode=demographics.postal_code,
                country=demographics.country,
                use="home",
            )
        ]

    # Create Patient resource
    patient = Patient(
        name=[name],
        identifier=identifiers,
        birthDate=demographics.birth_date,
        gender=demographics.gender,
        telecom=telecom if telecom else None,
        address=address,
    )

    return patient


def parse_patient_demographics(patient: Patient) -> PatientDemographicsInput:
    """
    Parse a FHIR Patient resource into demographics input

    Args:
        patient: FHIR Patient resource

    Returns:
        Patient demographics data
    """
    # Extract name
    name = patient.name[0] if patient.name else None
    family_name: str = name.family or "" if name else ""
    given_names: list[str] = cast(list[str], name.given if name and name.given else [])
    prefix: Optional[str] = str(name.prefix[0]) if name and name.prefix else None
    suffix: Optional[str] = str(name.suffix[0]) if name and name.suffix else None

    # Extract MRN
    mrn = ""
    mrn_system = ""
    if patient.identifier:
        for identifier in patient.identifier:
            if identifier.type and identifier.type.coding:
                for coding in identifier.type.coding:
                    if coding.code == "MR":
                        mrn = str(identifier.value or "")
                        mrn_system = str(identifier.system or "")
                        break

    # Extract contact
    phone = None
    email = None
    if patient.telecom:
        for contact in patient.telecom:
            if contact.system == "phone":
                phone = contact.value
            elif contact.system == "email":
                email = contact.value

    # Extract address
    address_line = None
    city = None
    state = None
    postal_code = None
    country = None
    if patient.address and len(patient.address) > 0:
        addr = patient.address[0]
        address_line = cast(list[str], addr.line) if addr.line else None
        city = str(addr.city) if addr.city else None
        state = str(addr.state) if addr.state else None
        postal_code = str(addr.postalCode) if addr.postalCode else None
        country = str(addr.country) if addr.country else None

    # birthDate is a date object in fhir.resources 8.x; handle older string form defensively
    birth_date = None
    if isinstance(patient.birthDate, date):
        birth_date = patient.birthDate
    elif patient.birthDate is not None:
        birth_date = date.fromisoformat(str(patient.birthDate))

    return PatientDemographicsInput(
        family_name=family_name,
        given_names=given_names,
        prefix=prefix,
        suffix=suffix,
        birth_date=birth_date,
        mrn=mrn,
        mrn_system=mrn_system,
        phone=str(phone) if phone else None,
        email=str(email) if email else None,
        address_line=address_line,
        city=city,
        state=state,
        postal_code=postal_code,
        country=country,
        gender=cast(Optional[AdministrativeGender], patient.gender),
    )
