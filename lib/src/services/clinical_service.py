"""Clinical data service - orders, referrals, encounters, conditions, procedures"""

from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.encounter import Encounter
from fhir.resources.R4B.medicationrequest import MedicationRequest
from fhir.resources.R4B.procedure import Procedure
from fhir.resources.R4B.servicerequest import ServiceRequest

from ..client.fhir_client import FHIRClient
from ..models.clinical_data import (
    ConditionInput,
    EncounterInput,
    MedicationOrderInput,
    PatientOrderInput,
    ProcedureInput,
    ReferralOrderInput,
    create_condition,
    create_encounter,
    create_medication_request,
    create_procedure,
    create_referral_request,
    create_service_request,
)


class ClinicalService:
    """Service for managing clinical data"""

    def __init__(self, client: FHIRClient):
        self.client = client

    # Patient Orders
    async def create_patient_order(self, order: PatientOrderInput) -> ServiceRequest:
        """Create a patient service order"""
        return await self.client.create(create_service_request(order))

    async def get_patient_order(self, order_id: str) -> ServiceRequest:
        """Get service order by ID"""
        return await self.client.read("ServiceRequest", order_id, ServiceRequest)

    async def update_patient_order(self, order_id: str, order: PatientOrderInput) -> ServiceRequest:
        """Update a patient service order"""
        resource = create_service_request(order)
        resource.id = order_id
        return await self.client.update(resource)

    async def delete_patient_order(self, order_id: str) -> None:
        """Delete a patient service order"""
        await self.client.delete("ServiceRequest", order_id)

    async def get_patient_orders(self, patient_id: str) -> list[ServiceRequest]:
        """Get all service orders for a patient"""
        return await self.client.search("ServiceRequest", ServiceRequest, {"patient": patient_id})

    # Medication Orders
    async def create_medication_order(self, order: MedicationOrderInput) -> MedicationRequest:
        """Create a medication order"""
        return await self.client.create(create_medication_request(order))

    async def get_medication_order(self, order_id: str) -> MedicationRequest:
        """Get medication order by ID"""
        return await self.client.read("MedicationRequest", order_id, MedicationRequest)

    async def update_medication_order(
        self, order_id: str, order: MedicationOrderInput
    ) -> MedicationRequest:
        """Update a medication order"""
        resource = create_medication_request(order)
        resource.id = order_id
        return await self.client.update(resource)

    async def delete_medication_order(self, order_id: str) -> None:
        """Delete a medication order"""
        await self.client.delete("MedicationRequest", order_id)

    async def get_medication_orders(self, patient_id: str) -> list[MedicationRequest]:
        """Get all medication orders for a patient"""
        return await self.client.search(
            "MedicationRequest", MedicationRequest, {"patient": patient_id}
        )

    # Referral Orders
    async def create_referral(self, referral: ReferralOrderInput) -> ServiceRequest:
        """Create a referral order"""
        return await self.client.create(create_referral_request(referral))

    async def get_referral(self, referral_id: str) -> ServiceRequest:
        """Get referral by ID"""
        return await self.client.read("ServiceRequest", referral_id, ServiceRequest)

    async def update_referral(
        self, referral_id: str, referral: ReferralOrderInput
    ) -> ServiceRequest:
        """Update a referral order"""
        resource = create_referral_request(referral)
        resource.id = referral_id
        return await self.client.update(resource)

    async def delete_referral(self, referral_id: str) -> None:
        """Delete a referral order"""
        await self.client.delete("ServiceRequest", referral_id)

    async def get_patient_referrals(self, patient_id: str) -> list[ServiceRequest]:
        """Get all referrals for a patient"""
        return await self.client.search(
            "ServiceRequest", ServiceRequest, {"patient": patient_id, "category": "3457005"}
        )

    # Encounters
    async def create_encounter(self, encounter: EncounterInput) -> Encounter:
        """Create an ambulatory encounter"""
        return await self.client.create(create_encounter(encounter))

    async def get_encounter(self, encounter_id: str) -> Encounter:
        """Get encounter by ID"""
        return await self.client.read("Encounter", encounter_id, Encounter)

    async def update_encounter(self, encounter_id: str, encounter: EncounterInput) -> Encounter:
        """Update an encounter"""
        resource = create_encounter(encounter)
        resource.id = encounter_id
        return await self.client.update(resource)

    async def delete_encounter(self, encounter_id: str) -> None:
        """Delete an encounter"""
        await self.client.delete("Encounter", encounter_id)

    async def get_patient_encounters(self, patient_id: str) -> list[Encounter]:
        """Get all encounters for a patient"""
        return await self.client.search(
            "Encounter", Encounter, {"patient": patient_id, "class": "AMB"}
        )

    # Conditions
    async def create_condition(self, condition: ConditionInput) -> Condition:
        """Create a patient condition/diagnosis"""
        return await self.client.create(create_condition(condition))

    async def get_condition(self, condition_id: str) -> Condition:
        """Get condition by ID"""
        return await self.client.read("Condition", condition_id, Condition)

    async def update_condition(self, condition_id: str, condition: ConditionInput) -> Condition:
        """Update a condition"""
        resource = create_condition(condition)
        resource.id = condition_id
        return await self.client.update(resource)

    async def delete_condition(self, condition_id: str) -> None:
        """Delete a condition"""
        await self.client.delete("Condition", condition_id)

    async def get_patient_conditions(self, patient_id: str) -> list[Condition]:
        """Get all conditions for a patient"""
        return await self.client.search("Condition", Condition, {"patient": patient_id})

    # Procedures
    async def create_procedure(self, procedure: ProcedureInput) -> Procedure:
        """Create a clinical procedure"""
        return await self.client.create(create_procedure(procedure))

    async def get_procedure(self, procedure_id: str) -> Procedure:
        """Get procedure by ID"""
        return await self.client.read("Procedure", procedure_id, Procedure)

    async def update_procedure(self, procedure_id: str, procedure: ProcedureInput) -> Procedure:
        """Update a procedure"""
        resource = create_procedure(procedure)
        resource.id = procedure_id
        return await self.client.update(resource)

    async def delete_procedure(self, procedure_id: str) -> None:
        """Delete a procedure"""
        await self.client.delete("Procedure", procedure_id)

    async def get_patient_procedures(self, patient_id: str) -> list[Procedure]:
        """Get all procedures for a patient"""
        return await self.client.search("Procedure", Procedure, {"patient": patient_id})
