"""Operational data API endpoints."""

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

# FHIR library imports
from fhir_client.models.operational_data import CoverageInput, PractitionerInput  # ScheduleInput, SlotInput not yet in library
from fhir_client.services.operational_service import OperationalService
from app.dependencies import get_operational_service
from app.models.responses import (
    PractitionerSummary,
    ReferralDashboardResponse,
    ReferralSummary,
    SearchResultsResponse,
)

router = APIRouter()


# Server configuration models
class FHIRServerInfo(BaseModel):
    """Information about a FHIR server option."""
    id: str
    name: str
    description: str
    base_url: str
    requires_auth: bool


class AvailableServersResponse(BaseModel):
    """Response containing available FHIR servers."""
    servers: list[FHIRServerInfo]


# Server configuration endpoints
@router.get("/servers", response_model=AvailableServersResponse)
async def get_available_servers() -> AvailableServersResponse:
    """Get list of available FHIR servers."""
    servers = [
        FHIRServerInfo(
            id="smart",
            name="SMART Health IT",
            description="Public test server for healthcare app development",
            base_url="https://launch.smarthealthit.org/v/r4/fhir",
            requires_auth=False,
        ),
        FHIRServerInfo(
            id="hapi",
            name="HAPI FHIR",
            description="Open source FHIR test server with large dataset",
            base_url="https://hapi.fhir.org/baseR4",
            requires_auth=False,
        ),
        FHIRServerInfo(
            id="epic",
            name="Epic Sandbox",
            description="Epic FHIR sandbox (requires authentication)",
            base_url="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/",
            requires_auth=True,
        ),
    ]
    return AvailableServersResponse(servers=servers)


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


def service_request_to_referral_summary(sr) -> ReferralSummary:
    """Convert a FHIR ServiceRequest resource to a ReferralSummary."""
    # Extract patient reference and display name
    patient_id = ""
    patient_display = None
    if sr.subject:
        patient_id = sr.subject.reference.split("/")[-1] if sr.subject.reference else ""
        patient_display = sr.subject.display

    # Extract category display (e.g., "Patient referral")
    category_display = None
    if sr.category and sr.category[0].coding:
        category_display = sr.category[0].coding[0].display

    # Extract code display (specialty/referral type)
    code_display = ""
    if sr.code and sr.code.coding:
        code_display = sr.code.coding[0].display or ""

    # Extract requester display
    requester_display = None
    if sr.requester:
        requester_display = sr.requester.display

    # Extract first performer display
    performer_display = None
    if sr.performer and len(sr.performer) > 0:
        performer_display = sr.performer[0].display

    # Extract first note text
    note = None
    if sr.note and sr.note[0].text:
        note = sr.note[0].text

    return ReferralSummary(
        id=sr.id,
        patient_id=patient_id,
        patient_display=patient_display,
        status=sr.status,
        intent=sr.intent,
        category_display=category_display,
        code_display=code_display,
        priority=sr.priority,
        authored_on=sr.authoredOn if hasattr(sr, "authoredOn") else None,
        requester_display=requester_display,
        performer_display=performer_display,
        note=note,
    )


def _raw_dict_to_referral_summary(resource: dict) -> ReferralSummary:
    """Convert a raw FHIR ServiceRequest dict to a ReferralSummary.

    Used instead of model_validate to tolerate malformed resources
    that are missing required FHIR fields (e.g., intent=None).
    """
    # Extract patient reference and display name
    subject = resource.get("subject", {}) or {}
    ref = subject.get("reference", "")
    patient_id = ref.split("/")[-1] if ref else ""
    patient_display = subject.get("display")

    # Extract category display
    category_display = None
    categories = resource.get("category", []) or []
    if categories and categories[0].get("coding"):
        category_display = categories[0]["coding"][0].get("display")

    # Extract code display (specialty/referral type)
    code_display = ""
    code = resource.get("code", {}) or {}
    if code.get("coding"):
        code_display = code["coding"][0].get("display", "")

    # Extract requester display
    requester = resource.get("requester", {}) or {}
    requester_display = requester.get("display")

    # Extract first performer display
    performer_display = None
    performers = resource.get("performer", []) or []
    if performers:
        performer_display = performers[0].get("display")

    # Extract first note text
    note = None
    notes = resource.get("note", []) or []
    if notes and notes[0].get("text"):
        note = notes[0]["text"]

    return ReferralSummary(
        id=resource.get("id", ""),
        patient_id=patient_id,
        patient_display=patient_display,
        status=resource.get("status", "unknown"),
        intent=resource.get("intent", "unknown"),
        category_display=category_display,
        code_display=code_display,
        priority=resource.get("priority"),
        authored_on=resource.get("authoredOn"),
        requester_display=requester_display,
        performer_display=performer_display,
        note=note,
    )


# Referral Dashboard
@router.get("/referrals/dashboard", response_model=ReferralDashboardResponse)
async def get_referral_dashboard(
    request_status: str | None = Query(None, alias="status", description="FHIR status filter"),
    patient_id: str | None = Query(None, description="Filter by patient ID"),
    authored_after: str | None = Query(None, description="Filter referrals authored after this date (YYYY-MM-DD)"),
    authored_before: str | None = Query(None, description="Filter referrals authored before this date (YYYY-MM-DD)"),
    count: int = Query(default=50, alias="_count", ge=1, le=200, description="Max results to return"),
    service: OperationalService = Depends(get_operational_service),
) -> ReferralDashboardResponse:
    """
    Get referral dashboard data with optional filters.

    Returns referrals (ServiceRequests with category=referral) along with
    status counts for the metrics bar.
    """
    # Build FHIR search params
    # Search by intent=order to find referral-type ServiceRequests.
    # We don't filter by category since many FHIR servers store referral
    # codes in the 'code' field rather than 'category'.
    params: dict[str, str] = {
        "_count": str(count),
    }

    if request_status:
        params["status"] = request_status
    if patient_id:
        params["patient"] = patient_id
    if authored_after:
        params["date"] = f"ge{authored_after}"
    if authored_before:
        # FHIR supports multiple date params for range queries
        if "date" in params:
            # Can't use two 'date' keys in a dict; use comma-separated for the range
            params["date"] = f"ge{authored_after}&date=le{authored_before}"
        else:
            params["date"] = f"le{authored_before}"

    try:
        # Use raw HTTP search to avoid strict FHIR model validation failures.
        # Some FHIR servers return ServiceRequests with missing required fields
        # (e.g., intent=None) which fail pydantic model_validate.
        response = await service.client.client.get("ServiceRequest", params=params)
        response.raise_for_status()
        bundle = response.json()
        raw_entries = []
        if bundle.get("resourceType") == "Bundle":
            for entry in bundle.get("entry", []):
                if "resource" in entry:
                    raw_entries.append(entry["resource"])
    except Exception as e:
        # Some servers (e.g., Epic) may reject cross-patient queries
        error_msg = str(e)
        if "400" in error_msg or "403" in error_msg or "401" in error_msg:
            return ReferralDashboardResponse(
                total=0,
                results=[],
                status_counts={},
            )
        raise

    # Convert raw dicts to summaries, skipping any that fail parsing
    summaries = []
    for resource in raw_entries:
        try:
            summaries.append(_raw_dict_to_referral_summary(resource))
        except (KeyError, TypeError, IndexError):
            continue

    # Compute status counts
    status_counts = dict(Counter(s.status for s in summaries))

    return ReferralDashboardResponse(
        total=len(summaries),
        results=summaries,
        status_counts=status_counts,
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


# Service Requests (Orders/Referrals)
@router.get("/service-requests/{request_id}")
async def get_service_request(
    request_id: str,
    service: OperationalService = Depends(get_operational_service),
):
    """Get a service request by ID."""
    try:
        request = await service.get_service_request(request_id)
        return request.dict()
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail=f"ServiceRequest {request_id} not found")
        raise


@router.get("/service-requests")
async def search_service_requests(
    patient_id: str | None = None,
    status: str | None = None,
    service: OperationalService = Depends(get_operational_service),
):
    """Search service requests with optional filters."""
    requests = await service.search_service_requests(patient_id=patient_id, status=status)
    return {
        "total": len(requests),
        "results": [r.dict() for r in requests],
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
