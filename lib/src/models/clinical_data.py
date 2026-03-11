"""Clinical data FHIR models - Orders, Referrals, Encounters, Conditions, Procedures"""

from datetime import datetime, timezone
from typing import Literal, Optional, TypeAlias

from pydantic import BaseModel

from fhir.resources.R4B.annotation import Annotation
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.dosage import Dosage
from fhir.resources.R4B.encounter import Encounter, EncounterParticipant
from fhir.resources.R4B.medicationrequest import MedicationRequest
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.procedure import Procedure, ProcedurePerformer
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.servicerequest import ServiceRequest

# FHIR R4B value-set type aliases
ServiceRequestStatus: TypeAlias = Literal[
    "draft", "active", "on-hold", "revoked", "completed", "entered-in-error", "unknown"
]
ServiceRequestIntent: TypeAlias = Literal[
    "proposal",
    "plan",
    "directive",
    "order",
    "original-order",
    "reflex-order",
    "filler-order",
    "instance-order",
    "option",
]
MedicationRequestIntent: TypeAlias = Literal[
    "proposal",
    "plan",
    "order",
    "original-order",
    "reflex-order",
    "filler-order",
    "instance-order",
]
RequestPriority: TypeAlias = Literal["routine", "urgent", "asap", "stat"]
EncounterStatus: TypeAlias = Literal[
    "planned",
    "arrived",
    "triaged",
    "in-progress",
    "onleave",
    "finished",
    "cancelled",
    "entered-in-error",
    "unknown",
]
ConditionClinicalStatus: TypeAlias = Literal[
    "active", "recurrence", "relapse", "inactive", "remission", "resolved"
]
ConditionVerificationStatus: TypeAlias = Literal[
    "unconfirmed", "provisional", "differential", "confirmed", "refuted", "entered-in-error"
]
ProcedureStatus: TypeAlias = Literal[
    "preparation",
    "in-progress",
    "not-done",
    "on-hold",
    "stopped",
    "completed",
    "entered-in-error",
    "unknown",
]


# Patient Orders (ServiceRequest, MedicationRequest)
class PatientOrderInput(BaseModel):
    """Input for patient service orders"""

    patient_id: str
    requester_id: Optional[str] = None
    code: str  # LOINC, SNOMED, etc.
    code_system: str
    code_display: str
    status: ServiceRequestStatus = "active"
    intent: ServiceRequestIntent = "order"
    priority: Optional[RequestPriority] = None
    occurrence_datetime: Optional[datetime] = None
    note: Optional[str] = None


def create_service_request(order: PatientOrderInput) -> ServiceRequest:
    """Create FHIR ServiceRequest from order input"""
    code_concept = CodeableConcept(
        coding=[
            Coding(
                system=order.code_system,
                code=order.code,
                display=order.code_display,
            )
        ]
    )

    occurrence_dt = None
    if order.occurrence_datetime:
        occurrence_dt = (
            order.occurrence_datetime.replace(tzinfo=timezone.utc)
            if not order.occurrence_datetime.tzinfo
            else order.occurrence_datetime
        )

    service_request = ServiceRequest(
        status=order.status,
        intent=order.intent,
        code=code_concept,
        subject=Reference(reference=f"Patient/{order.patient_id}"),
        requester=(
            Reference(reference=f"Practitioner/{order.requester_id}")
            if order.requester_id
            else None
        ),
        priority=order.priority,
        occurrenceDateTime=occurrence_dt,
    )

    if order.note:
        service_request.note = [Annotation(text=order.note)]

    return service_request


class MedicationOrderInput(BaseModel):
    """Input for medication orders"""

    patient_id: str
    prescriber_id: Optional[str] = None
    medication_code: str
    medication_system: str  # e.g., RxNorm
    medication_display: str
    status: ServiceRequestStatus = "active"
    intent: MedicationRequestIntent = "order"
    dosage_instruction: Optional[str] = None
    authored_on: Optional[datetime] = None


def create_medication_request(order: MedicationOrderInput) -> MedicationRequest:
    """Create FHIR MedicationRequest from order input"""
    medication = CodeableConcept(
        coding=[
            Coding(
                system=order.medication_system,
                code=order.medication_code,
                display=order.medication_display,
            )
        ]
    )

    authored_on = None
    if order.authored_on:
        authored_on = (
            order.authored_on.replace(tzinfo=timezone.utc)
            if not order.authored_on.tzinfo
            else order.authored_on
        )

    med_request = MedicationRequest(
        status=order.status,
        intent=order.intent,
        medicationCodeableConcept=medication,
        subject=Reference(reference=f"Patient/{order.patient_id}"),
        requester=(
            Reference(reference=f"Practitioner/{order.prescriber_id}")
            if order.prescriber_id
            else None
        ),
        authoredOn=authored_on,
    )

    if order.dosage_instruction:
        med_request.dosageInstruction = [Dosage(text=order.dosage_instruction)]

    return med_request


# Referral Orders (ServiceRequest with referral intent)
class ReferralOrderInput(BaseModel):
    """Input for referral orders"""

    patient_id: str
    requester_id: str
    performer_id: Optional[str] = None  # Receiving practitioner/organization
    specialty_code: str
    specialty_system: str = "http://snomed.info/sct"
    specialty_display: str
    reason_code: Optional[str] = None
    reason_display: Optional[str] = None
    status: ServiceRequestStatus = "active"
    priority: Optional[RequestPriority] = "routine"


def create_referral_request(referral: ReferralOrderInput) -> ServiceRequest:
    """Create FHIR ServiceRequest for referral"""
    specialty = CodeableConcept(
        coding=[
            Coding(
                system=referral.specialty_system,
                code=referral.specialty_code,
                display=referral.specialty_display,
            )
        ]
    )

    referral_request = ServiceRequest(
        status=referral.status,
        intent="order",
        category=[
            CodeableConcept(
                coding=[
                    Coding(
                        system="http://snomed.info/sct",
                        code="3457005",
                        display="Patient referral",
                    )
                ]
            )
        ],
        code=specialty,
        subject=Reference(reference=f"Patient/{referral.patient_id}"),
        requester=Reference(reference=f"Practitioner/{referral.requester_id}"),
        performer=(
            [Reference(reference=f"Practitioner/{referral.performer_id}")]
            if referral.performer_id
            else None
        ),
        priority=referral.priority,
    )

    if referral.reason_code:
        referral_request.reasonCode = [
            CodeableConcept(
                coding=[Coding(code=referral.reason_code, display=referral.reason_display)]
            )
        ]

    return referral_request


# Encounter Data (Ambulatory Visits)
class EncounterInput(BaseModel):
    """Input for ambulatory encounter"""

    patient_id: str
    practitioner_id: Optional[str] = None
    status: EncounterStatus = "finished"
    class_code: str = "AMB"  # AMB = ambulatory
    type_code: Optional[str] = None
    type_system: Optional[str] = "http://snomed.info/sct"
    type_display: Optional[str] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    reason_code: Optional[str] = None
    reason_display: Optional[str] = None


def create_encounter(encounter: EncounterInput) -> Encounter:
    """Create FHIR Encounter for ambulatory visit"""
    encounter_class = Coding(
        system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
        code=encounter.class_code,
        display="ambulatory",
    )

    # 'class' is a reserved keyword; construct without it then assign via validated attribute
    fhir_encounter = Encounter.model_construct(
        status=encounter.status,
        subject=Reference(reference=f"Patient/{encounter.patient_id}"),
    )
    fhir_encounter.class_fhir = encounter_class

    # Type
    if encounter.type_code:
        fhir_encounter.type = [
            CodeableConcept(
                coding=[
                    Coding(
                        system=encounter.type_system,
                        code=encounter.type_code,
                        display=encounter.type_display,
                    )
                ]
            )
        ]

    # Participant (practitioner)
    if encounter.practitioner_id:
        fhir_encounter.participant = [
            EncounterParticipant(
                individual=Reference(reference=f"Practitioner/{encounter.practitioner_id}")
            )
        ]

    # Period
    if encounter.period_start or encounter.period_end:
        start = (
            encounter.period_start.replace(tzinfo=timezone.utc)
            if encounter.period_start and not encounter.period_start.tzinfo
            else encounter.period_start
        )
        end = (
            encounter.period_end.replace(tzinfo=timezone.utc)
            if encounter.period_end and not encounter.period_end.tzinfo
            else encounter.period_end
        )
        fhir_encounter.period = Period(start=start, end=end)

    # Reason
    if encounter.reason_code:
        fhir_encounter.reasonCode = [
            CodeableConcept(
                coding=[Coding(code=encounter.reason_code, display=encounter.reason_display)]
            )
        ]

    return fhir_encounter


# Conditions (Diagnoses)
class ConditionInput(BaseModel):
    """Input for a patient condition/diagnosis"""

    patient_id: str
    code: str  # SNOMED CT, ICD-10, etc.
    code_system: str
    code_display: str
    clinical_status: ConditionClinicalStatus = "active"
    verification_status: ConditionVerificationStatus = "confirmed"
    category_code: Optional[str] = None  # e.g., encounter-diagnosis, problem-list-item
    severity_code: Optional[str] = None
    severity_display: Optional[str] = None
    onset_datetime: Optional[datetime] = None
    recorder_id: Optional[str] = None
    encounter_id: Optional[str] = None
    note: Optional[str] = None


def create_condition(condition: ConditionInput) -> Condition:
    """Create FHIR Condition resource"""
    fhir_condition = Condition(
        subject=Reference(reference=f"Patient/{condition.patient_id}"),
        code=CodeableConcept(
            coding=[
                Coding(
                    system=condition.code_system,
                    code=condition.code,
                    display=condition.code_display,
                )
            ]
        ),
        clinicalStatus=CodeableConcept(
            coding=[
                Coding(
                    system="http://terminology.hl7.org/CodeSystem/condition-clinical",
                    code=condition.clinical_status,
                )
            ]
        ),
        verificationStatus=CodeableConcept(
            coding=[
                Coding(
                    system="http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    code=condition.verification_status,
                )
            ]
        ),
    )

    if condition.category_code:
        fhir_condition.category = [
            CodeableConcept(
                coding=[
                    Coding(
                        system="http://terminology.hl7.org/CodeSystem/condition-category",
                        code=condition.category_code,
                    )
                ]
            )
        ]

    if condition.severity_code:
        fhir_condition.severity = CodeableConcept(
            coding=[Coding(code=condition.severity_code, display=condition.severity_display)]
        )

    if condition.onset_datetime:
        onset = (
            condition.onset_datetime.replace(tzinfo=timezone.utc)
            if not condition.onset_datetime.tzinfo
            else condition.onset_datetime
        )
        fhir_condition.onsetDateTime = onset

    if condition.recorder_id:
        fhir_condition.recorder = Reference(reference=f"Practitioner/{condition.recorder_id}")

    if condition.encounter_id:
        fhir_condition.encounter = Reference(reference=f"Encounter/{condition.encounter_id}")

    if condition.note:
        fhir_condition.note = [Annotation(text=condition.note)]

    return fhir_condition


# Procedures
class ProcedureInput(BaseModel):
    """Input for a clinical procedure"""

    patient_id: str
    code: str  # SNOMED CT, CPT, etc.
    code_system: str
    code_display: str
    status: ProcedureStatus = "completed"
    performer_id: Optional[str] = None
    encounter_id: Optional[str] = None
    performed_datetime: Optional[datetime] = None
    performed_start: Optional[datetime] = None
    performed_end: Optional[datetime] = None
    reason_code: Optional[str] = None
    reason_display: Optional[str] = None
    note: Optional[str] = None


def create_procedure(procedure: ProcedureInput) -> Procedure:
    """Create FHIR Procedure resource"""
    fhir_procedure = Procedure(
        subject=Reference(reference=f"Patient/{procedure.patient_id}"),
        status=procedure.status,
        code=CodeableConcept(
            coding=[
                Coding(
                    system=procedure.code_system,
                    code=procedure.code,
                    display=procedure.code_display,
                )
            ]
        ),
    )

    if procedure.performer_id:
        fhir_procedure.performer = [
            ProcedurePerformer(actor=Reference(reference=f"Practitioner/{procedure.performer_id}"))
        ]

    if procedure.encounter_id:
        fhir_procedure.encounter = Reference(reference=f"Encounter/{procedure.encounter_id}")

    if procedure.performed_datetime:
        dt = (
            procedure.performed_datetime.replace(tzinfo=timezone.utc)
            if not procedure.performed_datetime.tzinfo
            else procedure.performed_datetime
        )
        fhir_procedure.performedDateTime = dt
    elif procedure.performed_start or procedure.performed_end:
        start = (
            procedure.performed_start.replace(tzinfo=timezone.utc)
            if procedure.performed_start and not procedure.performed_start.tzinfo
            else procedure.performed_start
        )
        end = (
            procedure.performed_end.replace(tzinfo=timezone.utc)
            if procedure.performed_end and not procedure.performed_end.tzinfo
            else procedure.performed_end
        )
        fhir_procedure.performedPeriod = Period(start=start, end=end)

    if procedure.reason_code:
        fhir_procedure.reasonCode = [
            CodeableConcept(
                coding=[Coding(code=procedure.reason_code, display=procedure.reason_display)]
            )
        ]

    if procedure.note:
        fhir_procedure.note = [Annotation(text=procedure.note)]

    return fhir_procedure
