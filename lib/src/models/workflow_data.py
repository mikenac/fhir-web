"""Workflow FHIR models - Task, Communication"""

from datetime import datetime, timezone
from typing import Literal, Optional, TypeAlias

from pydantic import BaseModel

from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.communication import Communication, CommunicationPayload
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.task import Task

# FHIR R4B value-set type aliases
TaskStatus: TypeAlias = Literal[
    "draft",
    "requested",
    "received",
    "accepted",
    "rejected",
    "ready",
    "cancelled",
    "in-progress",
    "on-hold",
    "failed",
    "completed",
    "entered-in-error",
]
TaskIntent: TypeAlias = Literal[
    "unknown",
    "proposal",
    "plan",
    "order",
    "original-order",
    "reflex-order",
    "filler-order",
    "instance-order",
    "option",
]
TaskPriority: TypeAlias = Literal["routine", "urgent", "asap", "stat"]
CommunicationStatus: TypeAlias = Literal[
    "preparation",
    "in-progress",
    "not-done",
    "on-hold",
    "stopped",
    "completed",
    "entered-in-error",
    "unknown",
]


# Task
class TaskInput(BaseModel):
    """Input for a workflow task"""

    status: TaskStatus = "requested"
    intent: TaskIntent = "order"
    priority: Optional[TaskPriority] = None
    code_code: Optional[str] = None
    code_display: Optional[str] = None
    description: Optional[str] = None
    patient_id: Optional[str] = None  # for (subject of the task)
    focus_resource_type: Optional[str] = None  # e.g., "ServiceRequest"
    focus_resource_id: Optional[str] = None
    owner_id: Optional[str] = None  # Practitioner responsible
    requester_id: Optional[str] = None
    authored_on: Optional[datetime] = None
    note: Optional[str] = None


def create_task(task: TaskInput) -> Task:
    """Create FHIR Task resource"""
    fhir_task = Task(
        status=task.status,
        intent=task.intent,
    )

    if task.priority:
        fhir_task.priority = task.priority

    if task.code_code:
        fhir_task.code = CodeableConcept(
            coding=[Coding(code=task.code_code, display=task.code_display)]
        )

    if task.description:
        fhir_task.description = task.description

    if task.patient_id:
        fhir_task.for_fhir = Reference(reference=f"Patient/{task.patient_id}")

    if task.focus_resource_type and task.focus_resource_id:
        fhir_task.focus = Reference(
            reference=f"{task.focus_resource_type}/{task.focus_resource_id}"
        )

    if task.owner_id:
        fhir_task.owner = Reference(reference=f"Practitioner/{task.owner_id}")

    if task.requester_id:
        fhir_task.requester = Reference(reference=f"Practitioner/{task.requester_id}")

    if task.authored_on:
        dt = (
            task.authored_on.replace(tzinfo=timezone.utc)
            if not task.authored_on.tzinfo
            else task.authored_on
        )
        fhir_task.authoredOn = dt

    return fhir_task


# Communication
class CommunicationInput(BaseModel):
    """Input for a clinical communication"""

    status: CommunicationStatus = "completed"
    patient_id: Optional[str] = None
    sender_id: Optional[str] = None  # Practitioner
    recipient_ids: Optional[list[str]] = None  # Practitioner IDs
    category_code: Optional[str] = None
    category_display: Optional[str] = None
    message: Optional[str] = None
    sent: Optional[datetime] = None
    encounter_id: Optional[str] = None


def create_communication(comm: CommunicationInput) -> Communication:
    """Create FHIR Communication resource"""
    fhir_comm = Communication(status=comm.status)

    if comm.patient_id:
        fhir_comm.subject = Reference(reference=f"Patient/{comm.patient_id}")

    if comm.sender_id:
        fhir_comm.sender = Reference(reference=f"Practitioner/{comm.sender_id}")

    if comm.recipient_ids:
        fhir_comm.recipient = [
            Reference(reference=f"Practitioner/{r_id}") for r_id in comm.recipient_ids
        ]

    if comm.category_code:
        fhir_comm.category = [
            CodeableConcept(coding=[Coding(code=comm.category_code, display=comm.category_display)])
        ]

    if comm.message:
        fhir_comm.payload = [CommunicationPayload(contentString=comm.message)]

    if comm.sent:
        dt = comm.sent.replace(tzinfo=timezone.utc) if not comm.sent.tzinfo else comm.sent
        fhir_comm.sent = dt

    if comm.encounter_id:
        fhir_comm.encounter = Reference(reference=f"Encounter/{comm.encounter_id}")

    return fhir_comm
