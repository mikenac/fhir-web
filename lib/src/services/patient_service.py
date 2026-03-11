"""Patient demographics service"""

from typing import Optional
from fhir.resources.R4B.patient import Patient

from ..client.fhir_client import FHIRClient
from ..models.patient_demographics import (
    PatientDemographicsInput,
    create_patient_resource,
)


class PatientService:
    """Service for managing patient demographics"""

    def __init__(self, client: FHIRClient):
        self.client = client

    async def create_patient(self, demographics: PatientDemographicsInput) -> Patient:
        """
        Create a new patient

        Args:
            demographics: Patient demographic information

        Returns:
            Created Patient resource
        """
        patient = create_patient_resource(demographics)
        return await self.client.create(patient)

    async def get_patient(self, patient_id: str) -> Patient:
        """
        Get patient by ID

        Args:
            patient_id: FHIR Patient resource ID

        Returns:
            Patient resource
        """
        return await self.client.read("Patient", patient_id, Patient)

    async def get_patient_by_mrn(
        self, mrn: str, mrn_system: str = "http://hospital.example.org/mrn"
    ) -> Optional[Patient]:
        """
        Get patient by Medical Record Number

        Args:
            mrn: Medical Record Number
            mrn_system: MRN identifier system

        Returns:
            Patient resource if found, None otherwise
        """
        patients = await self.client.search_by_identifier("Patient", Patient, mrn_system, mrn)
        return patients[0] if patients else None

    async def update_patient(
        self, patient_id: str, demographics: PatientDemographicsInput
    ) -> Patient:
        """
        Update patient demographics

        Args:
            patient_id: FHIR Patient resource ID
            demographics: Updated demographic information

        Returns:
            Updated Patient resource
        """
        patient = create_patient_resource(demographics)
        patient.id = patient_id
        return await self.client.update(patient)

    async def delete_patient(self, patient_id: str) -> None:
        """Delete a patient by ID"""
        await self.client.delete("Patient", patient_id)

    async def search_patients(
        self, family_name: Optional[str] = None, given_name: Optional[str] = None
    ) -> list[Patient]:
        """
        Search for patients by name

        Args:
            family_name: Family/last name
            given_name: Given/first name

        Returns:
            List of matching patients
        """
        params = {}
        if family_name:
            params["family"] = family_name
        if given_name:
            params["given"] = given_name

        return await self.client.search("Patient", Patient, params)
