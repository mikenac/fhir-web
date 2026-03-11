"""Clinical data API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

# FHIR library imports
from fhir_client.models.clinical_data import (
    EncounterInput,
    MedicationOrderInput,
    PatientOrderInput,
    ReferralOrderInput,
)
from fhir_client.services.clinical_service import ClinicalService

from app.dependencies import get_clinical_service
from app.models.responses import EncounterSummary, OrderSummary, SearchResultsResponse

router = APIRouter()


def encounter_to_summary(encounter) -> EncounterSummary:
    """Convert FHIR Encounter resource to EncounterSummary."""
    return EncounterSummary(
        id=encounter.id,
        patient_id=encounter.subject.reference.split("/")[-1] if encounter.subject else "",
        status=encounter.status,
        class_code=encounter.class_fhir.code if encounter.class_fhir else "",
        type_display=(
            encounter.type[0].coding[0].display if encounter.type and encounter.type[0].coding else None
        ),
        period_start=encounter.period.start if encounter.period else None,
        period_end=encounter.period.end if encounter.period else None,
        reason_display=(
            encounter.reasonCode[0].coding[0].display
            if encounter.reasonCode and encounter.reasonCode[0].coding
            else None
        ),
    )


def service_request_to_summary(service_request) -> OrderSummary:
    """Convert FHIR ServiceRequest resource to OrderSummary."""
    return OrderSummary(
        id=service_request.id,
        patient_id=(
            service_request.subject.reference.split("/")[-1] if service_request.subject else ""
        ),
        status=service_request.status,
        intent=service_request.intent,
        code_display=(
            service_request.code.coding[0].display
            if service_request.code and service_request.code.coding
            else ""
        ),
        authored_on=service_request.authoredOn if hasattr(service_request, "authoredOn") else None,
        note=(
            service_request.note[0].text if service_request.note and service_request.note[0].text else None
        ),
    )


def medication_request_to_summary(medication_request) -> OrderSummary:
    """Convert FHIR MedicationRequest resource to OrderSummary."""
    return OrderSummary(
        id=medication_request.id,
        patient_id=(
            medication_request.subject.reference.split("/")[-1] if medication_request.subject else ""
        ),
        status=medication_request.status,
        intent=medication_request.intent,
        code_display=(
            medication_request.medicationCodeableConcept.coding[0].display
            if medication_request.medicationCodeableConcept
            and medication_request.medicationCodeableConcept.coding
            else ""
        ),
        authored_on=medication_request.authoredOn if medication_request.authoredOn else None,
        note=(
            medication_request.note[0].text
            if medication_request.note and medication_request.note[0].text
            else None
        ),
    )


# Encounters
@router.post("/encounters", response_model=EncounterSummary, status_code=status.HTTP_201_CREATED)
async def create_encounter(
    encounter: EncounterInput,
    service: ClinicalService = Depends(get_clinical_service),
) -> EncounterSummary:
    """Create a new encounter."""
    result = await service.create_encounter(encounter)
    return encounter_to_summary(result)


@router.get("/encounters/{encounter_id}", response_model=EncounterSummary)
async def get_encounter(
    encounter_id: str,
    service: ClinicalService = Depends(get_clinical_service),
) -> EncounterSummary:
    """Get an encounter by ID."""
    try:
        encounter = await service.get_encounter(encounter_id)
        return encounter_to_summary(encounter)
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail=f"Encounter {encounter_id} not found")
        raise


@router.get("/patients/{patient_id}/encounters", response_model=SearchResultsResponse)
async def get_patient_encounters(
    patient_id: str,
    service: ClinicalService = Depends(get_clinical_service),
) -> SearchResultsResponse:
    """Get all encounters for a patient."""
    encounters = await service.get_patient_encounters(patient_id)
    summaries = [encounter_to_summary(e).model_dump() for e in encounters]
    return SearchResultsResponse(total=len(summaries), results=summaries)


# Patient Orders
@router.post("/orders", response_model=OrderSummary, status_code=status.HTTP_201_CREATED)
async def create_patient_order(
    order: PatientOrderInput,
    service: ClinicalService = Depends(get_clinical_service),
) -> OrderSummary:
    """Create a new patient order (lab, imaging, etc.)."""
    result = await service.create_patient_order(order)
    return service_request_to_summary(result)


@router.get("/patients/{patient_id}/orders", response_model=SearchResultsResponse)
async def get_patient_orders(
    patient_id: str,
    service: ClinicalService = Depends(get_clinical_service),
) -> SearchResultsResponse:
    """Get all orders for a patient."""
    orders = await service.get_patient_orders(patient_id)
    summaries = [service_request_to_summary(o).model_dump() for o in orders]
    return SearchResultsResponse(total=len(summaries), results=summaries)


# Medication Orders
@router.post("/medications", response_model=OrderSummary, status_code=status.HTTP_201_CREATED)
async def create_medication_order(
    order: MedicationOrderInput,
    service: ClinicalService = Depends(get_clinical_service),
) -> OrderSummary:
    """Create a new medication order."""
    result = await service.create_medication_order(order)
    return medication_request_to_summary(result)


@router.get("/patients/{patient_id}/medications", response_model=SearchResultsResponse)
async def get_patient_medications(
    patient_id: str,
    service: ClinicalService = Depends(get_clinical_service),
) -> SearchResultsResponse:
    """Get all medication orders for a patient."""
    medications = await service.get_medication_orders(patient_id)
    summaries = [medication_request_to_summary(m).model_dump() for m in medications]
    return SearchResultsResponse(total=len(summaries), results=summaries)


# Referrals
@router.post("/referrals", response_model=OrderSummary, status_code=status.HTTP_201_CREATED)
async def create_referral(
    referral: ReferralOrderInput,
    service: ClinicalService = Depends(get_clinical_service),
) -> OrderSummary:
    """Create a new referral order."""
    result = await service.create_referral(referral)
    return service_request_to_summary(result)


@router.get("/patients/{patient_id}/referrals", response_model=SearchResultsResponse)
async def get_patient_referrals(
    patient_id: str,
    service: ClinicalService = Depends(get_clinical_service),
) -> SearchResultsResponse:
    """Get all referrals for a patient."""
    referrals = await service.get_patient_referrals(patient_id)
    summaries = [service_request_to_summary(r).model_dump() for r in referrals]
    return SearchResultsResponse(total=len(summaries), results=summaries)
