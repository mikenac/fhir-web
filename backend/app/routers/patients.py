"""Patient API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

# FHIR library imports
from src.models.patient_demographics import PatientDemographicsInput, parse_patient_demographics
from src.services.patient_service import PatientService
from src.services.clinical_service import ClinicalService

from app.dependencies import get_patient_service, get_clinical_service
from app.models.responses import PatientSummary, SearchResultsResponse

router = APIRouter()


def patient_to_summary(patient) -> PatientSummary:
    """Convert FHIR Patient resource to PatientSummary."""
    demographics = parse_patient_demographics(patient)
    full_name = f"{' '.join(demographics.given_names)} {demographics.family_name}"
    if demographics.prefix:
        full_name = f"{demographics.prefix} {full_name}"

    return PatientSummary(
        id=patient.id,
        family_name=demographics.family_name,
        given_names=demographics.given_names,
        full_name=full_name,
        birth_date=demographics.birth_date,
        mrn=demographics.mrn,
        gender=demographics.gender,
        phone=demographics.phone,
        email=demographics.email,
    )


@router.post("/", response_model=PatientSummary, status_code=status.HTTP_201_CREATED)
async def create_patient(
    demographics: PatientDemographicsInput,
    service: PatientService = Depends(get_patient_service),
) -> PatientSummary:
    """
    Create a new patient.

    Args:
        demographics: Patient demographic information
        service: Patient service dependency

    Returns:
        Created patient summary
    """
    patient = await service.create_patient(demographics)
    return patient_to_summary(patient)


@router.get("/{patient_id}", response_model=PatientSummary)
async def get_patient(
    patient_id: str,
    service: PatientService = Depends(get_patient_service),
) -> PatientSummary:
    """
    Get a patient by ID.

    Args:
        patient_id: FHIR patient ID
        service: Patient service dependency

    Returns:
        Patient summary

    Raises:
        HTTPException: If patient not found
    """
    try:
        patient = await service.get_patient(patient_id)
        return patient_to_summary(patient)
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        raise


@router.get("/mrn/{mrn}", response_model=PatientSummary)
async def get_patient_by_mrn(
    mrn: str,
    mrn_system: str = Query(default="http://hospital.example.org/mrn"),
    service: PatientService = Depends(get_patient_service),
) -> PatientSummary:
    """
    Get a patient by MRN (Medical Record Number).

    Args:
        mrn: Medical record number
        mrn_system: MRN identifier system
        service: Patient service dependency

    Returns:
        Patient summary

    Raises:
        HTTPException: If patient not found
    """
    patient = await service.get_patient_by_mrn(mrn, mrn_system)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient with MRN {mrn} not found")
    return patient_to_summary(patient)


@router.get("/", response_model=SearchResultsResponse)
async def search_patients(
    family_name: str = Query(None, description="Family (last) name"),
    given_name: str = Query(None, description="Given (first) name"),
    active_visits_only: bool = Query(False, description="Only show patients with active visits"),
    active_orders_only: bool = Query(False, description="Only show patients with active orders"),
    service: PatientService = Depends(get_patient_service),
    clinical_service: ClinicalService = Depends(get_clinical_service),
) -> SearchResultsResponse:
    """
    Search for patients by name.

    Args:
        family_name: Family (last) name to search for
        given_name: Given (first) name to search for
        active_visits_only: Filter to only patients with active encounters
        active_orders_only: Filter to only patients with active orders
        service: Patient service dependency
        clinical_service: Clinical service for checking encounters and orders

    Returns:
        Search results with patient summaries
    """
    if not family_name and not given_name:
        raise HTTPException(
            status_code=400,
            detail="At least one search parameter (family_name or given_name) is required",
        )

    patients = await service.search_patients(
        family_name=family_name or "",
        given_name=given_name or "",
    )

    # Filter for active visits if requested
    if active_visits_only:
        filtered_patients = []
        for patient in patients:
            try:
                encounters = await clinical_service.get_patient_encounters(patient.id)
                # Check if patient has any active encounters (in-progress or arrived)
                has_active = any(
                    enc.status in ["in-progress", "arrived", "triaged", "onleave"]
                    for enc in encounters
                )
                if has_active:
                    filtered_patients.append(patient)
            except:
                # If we can't check encounters, skip this patient
                continue
        patients = filtered_patients

    # Filter for active orders if requested
    if active_orders_only:
        filtered_patients = []
        for patient in patients:
            try:
                orders = await clinical_service.get_patient_orders(patient.id)
                # Check if patient has any active orders
                has_active = any(
                    order.status in ["active", "on-hold", "draft"]
                    for order in orders
                )
                if has_active:
                    filtered_patients.append(patient)
            except:
                # If we can't check orders, skip this patient
                continue
        patients = filtered_patients

    summaries = [patient_to_summary(p).model_dump() for p in patients]

    return SearchResultsResponse(
        total=len(summaries),
        results=summaries,
    )


@router.put("/{patient_id}", response_model=PatientSummary)
async def update_patient(
    patient_id: str,
    demographics: PatientDemographicsInput,
    service: PatientService = Depends(get_patient_service),
) -> PatientSummary:
    """
    Update an existing patient.

    Args:
        patient_id: FHIR patient ID
        demographics: Updated patient demographic information
        service: Patient service dependency

    Returns:
        Updated patient summary
    """
    patient = await service.update_patient(patient_id, demographics)
    return patient_to_summary(patient)
