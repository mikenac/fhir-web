"""Operational data API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

# FHIR library imports
from src.models.operational_data import CoverageInput, PractitionerInput  # ScheduleInput, SlotInput not yet in library
from src.services.operational_service import OperationalService

from app.dependencies import get_operational_service
from app.models.responses import PractitionerSummary, SearchResultsResponse

router = APIRouter()


def practitioner_to_summary(practitioner) -> PractitionerSummary:
    """Convert FHIR Practitioner resource to PractitionerSummary."""
    name = practitioner.name[0] if practitioner.name else None
    family_name = name.family if name else ""
    given_names = name.given if name else []
    full_name = f"{' '.join(given_names)} {family_name}"
    if name and name.prefix:
        full_name = f"{' '.join(name.prefix)} {full_name}"

    npi = ""
    phone = None
    email = None

    if practitioner.identifier:
        for identifier in practitioner.identifier:
            if identifier.system and "npi" in identifier.system.lower():
                npi = identifier.value
                break

    if practitioner.telecom:
        for telecom in practitioner.telecom:
            if telecom.system == "phone":
                phone = telecom.value
            elif telecom.system == "email":
                email = telecom.value

    return PractitionerSummary(
        id=practitioner.id,
        family_name=family_name,
        given_names=given_names,
        full_name=full_name,
        npi=npi,
        phone=phone,
        email=email,
    )


# Practitioners
@router.post("/practitioners", response_model=PractitionerSummary, status_code=status.HTTP_201_CREATED)
async def create_practitioner(
    practitioner: PractitionerInput,
    service: OperationalService = Depends(get_operational_service),
) -> PractitionerSummary:
    """Create a new practitioner."""
    result = await service.create_practitioner(practitioner)
    return practitioner_to_summary(result)


@router.get("/practitioners/{practitioner_id}", response_model=PractitionerSummary)
async def get_practitioner(
    practitioner_id: str,
    service: OperationalService = Depends(get_operational_service),
) -> PractitionerSummary:
    """Get a practitioner by ID."""
    try:
        practitioner = await service.get_practitioner(practitioner_id)
        return practitioner_to_summary(practitioner)
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail=f"Practitioner {practitioner_id} not found")
        raise


@router.get("/practitioners/npi/{npi}", response_model=SearchResultsResponse)
async def get_practitioner_by_npi(
    npi: str,
    service: OperationalService = Depends(get_operational_service),
) -> SearchResultsResponse:
    """Get practitioners by NPI."""
    practitioners = await service.get_practitioner_by_npi(npi)
    summaries = [practitioner_to_summary(p).model_dump() for p in practitioners]
    return SearchResultsResponse(total=len(summaries), results=summaries)


# Coverage
@router.post("/coverage", status_code=status.HTTP_201_CREATED)
async def create_coverage(
    coverage: CoverageInput,
    service: OperationalService = Depends(get_operational_service),
):
    """Create a new coverage record."""
    result = await service.create_coverage(coverage)
    return {"id": result.id, "status": "created"}


@router.get("/patients/{patient_id}/coverage")
async def get_patient_coverage(
    patient_id: str,
    service: OperationalService = Depends(get_operational_service),
):
    """Get all coverage records for a patient."""
    coverage_list = await service.get_patient_coverage(patient_id)
    return {
        "total": len(coverage_list),
        "results": [c.dict() for c in coverage_list],
    }


# Scheduling - Commented out until ScheduleInput and SlotInput are added to FHIR library
# @router.post("/schedules", status_code=status.HTTP_201_CREATED)
# async def create_schedule(
#     schedule: ScheduleInput,
#     service: OperationalService = Depends(get_operational_service),
# ):
#     """Create a new schedule for a practitioner."""
#     result = await service.create_schedule(schedule)
#     return {"id": result.id, "status": "created"}


# @router.get("/practitioners/{practitioner_id}/schedules")
# async def get_practitioner_schedules(
#     practitioner_id: str,
#     service: OperationalService = Depends(get_operational_service),
# ):
#     """Get all schedules for a practitioner."""
#     schedules = await service.get_practitioner_schedules(practitioner_id)
#     return {
#         "total": len(schedules),
#         "results": [s.dict() for s in schedules],
#     }


# @router.post("/slots", status_code=status.HTTP_201_CREATED)
# async def create_slot(
#     slot: SlotInput,
#     service: OperationalService = Depends(get_operational_service),
# ):
#     """Create a new appointment slot."""
#     result = await service.create_slot(slot)
#     return {"id": result.id, "status": "created"}


# @router.get("/schedules/{schedule_id}/slots")
# async def get_schedule_slots(
#     schedule_id: str,
#     service: OperationalService = Depends(get_operational_service),
# ):
#     """Get available slots for a schedule."""
#     slots = await service.get_available_slots(schedule_id)
#     return {
#         "total": len(slots),
#         "results": [s.dict() for s in slots],
#     }
