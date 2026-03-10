"""Scheduling FHIR models - Appointment, Schedule, Slot"""

from datetime import datetime, timezone
from typing import Literal, Optional, TypeAlias

from pydantic import BaseModel

from fhir.resources.R4B.appointment import Appointment, AppointmentParticipant
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.schedule import Schedule
from fhir.resources.R4B.slot import Slot

# FHIR R4B value-set type aliases
AppointmentStatus: TypeAlias = Literal[
    "proposed",
    "pending",
    "booked",
    "arrived",
    "fulfilled",
    "cancelled",
    "noshow",
    "entered-in-error",
    "checked-in",
    "waitlist",
]
ParticipantStatus: TypeAlias = Literal["accepted", "declined", "tentative", "needs-action"]
SlotStatus: TypeAlias = Literal[
    "busy", "free", "busy-unavailable", "busy-tentative", "entered-in-error"
]


# Appointment
class AppointmentInput(BaseModel):
    """Input for a patient appointment"""

    patient_id: str
    practitioner_id: Optional[str] = None
    location_id: Optional[str] = None
    slot_id: Optional[str] = None
    status: AppointmentStatus = "booked"
    service_type_code: Optional[str] = None
    service_type_display: Optional[str] = None
    specialty_code: Optional[str] = None
    specialty_display: Optional[str] = None
    reason_code: Optional[str] = None
    reason_display: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    comment: Optional[str] = None


def create_appointment(appt: AppointmentInput) -> Appointment:
    """Create FHIR Appointment resource"""
    participants: list[AppointmentParticipant] = [
        AppointmentParticipant(
            actor=Reference(reference=f"Patient/{appt.patient_id}"),
            status="accepted",
        )
    ]

    if appt.practitioner_id:
        participants.append(
            AppointmentParticipant(
                actor=Reference(reference=f"Practitioner/{appt.practitioner_id}"),
                status="accepted",
            )
        )

    if appt.location_id:
        participants.append(
            AppointmentParticipant(
                actor=Reference(reference=f"Location/{appt.location_id}"),
                status="accepted",
            )
        )

    fhir_appt = Appointment(
        status=appt.status,
        participant=participants,
    )

    if appt.service_type_code:
        fhir_appt.serviceType = [
            CodeableConcept(
                coding=[Coding(code=appt.service_type_code, display=appt.service_type_display)]
            )
        ]

    if appt.specialty_code:
        fhir_appt.specialty = [
            CodeableConcept(
                coding=[Coding(code=appt.specialty_code, display=appt.specialty_display)]
            )
        ]

    if appt.reason_code:
        fhir_appt.reasonCode = [
            CodeableConcept(coding=[Coding(code=appt.reason_code, display=appt.reason_display)])
        ]

    if appt.start:
        fhir_appt.start = (
            appt.start if appt.start.tzinfo else appt.start.replace(tzinfo=timezone.utc)
        )
    if appt.end:
        fhir_appt.end = appt.end if appt.end.tzinfo else appt.end.replace(tzinfo=timezone.utc)

    if appt.slot_id:
        fhir_appt.slot = [Reference(reference=f"Slot/{appt.slot_id}")]

    if appt.comment:
        fhir_appt.comment = appt.comment

    return fhir_appt


# Schedule Templates
class ScheduleInput(BaseModel):
    """Input for schedule template"""

    practitioner_id: Optional[str] = None
    location_id: Optional[str] = None
    service_type: str
    service_display: str
    active: bool = True
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    comment: Optional[str] = None


def create_schedule(schedule: ScheduleInput) -> Schedule:
    """Create FHIR Schedule resource"""
    actors = []
    if schedule.practitioner_id:
        actors.append(Reference(reference=f"Practitioner/{schedule.practitioner_id}"))
    if schedule.location_id:
        actors.append(Reference(reference=f"Location/{schedule.location_id}"))

    fhir_schedule = Schedule(
        active=schedule.active,
        serviceType=[
            CodeableConcept(
                coding=[Coding(code=schedule.service_type, display=schedule.service_display)]
            )
        ],
        actor=actors,
    )

    if schedule.period_start or schedule.period_end:
        start = (
            schedule.period_start.replace(tzinfo=timezone.utc)
            if schedule.period_start and not schedule.period_start.tzinfo
            else schedule.period_start
        )
        end = (
            schedule.period_end.replace(tzinfo=timezone.utc)
            if schedule.period_end and not schedule.period_end.tzinfo
            else schedule.period_end
        )
        fhir_schedule.planningHorizon = Period(start=start, end=end)

    if schedule.comment:
        fhir_schedule.comment = schedule.comment

    return fhir_schedule


class SlotInput(BaseModel):
    """Input for appointment slot"""

    schedule_id: str
    status: SlotStatus = "free"
    start: datetime
    end: datetime
    service_type: Optional[str] = None
    service_display: Optional[str] = None
    comment: Optional[str] = None


def create_slot(slot: SlotInput) -> Slot:
    """Create FHIR Slot resource"""
    start = slot.start if slot.start.tzinfo else slot.start.replace(tzinfo=timezone.utc)
    end = slot.end if slot.end.tzinfo else slot.end.replace(tzinfo=timezone.utc)
    fhir_slot = Slot(
        schedule=Reference(reference=f"Schedule/{slot.schedule_id}"),
        status=slot.status,
        start=start,
        end=end,
    )

    if slot.service_type:
        fhir_slot.serviceType = [
            CodeableConcept(coding=[Coding(code=slot.service_type, display=slot.service_display)])
        ]

    if slot.comment:
        fhir_slot.comment = slot.comment

    return fhir_slot
