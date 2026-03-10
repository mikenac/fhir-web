"""Scheduling service - appointments, schedules, slots"""

from fhir.resources.R4B.appointment import Appointment
from fhir.resources.R4B.schedule import Schedule
from fhir.resources.R4B.slot import Slot

from ..client.fhir_client import FHIRClient
from ..models.scheduling_data import (
    AppointmentInput,
    ScheduleInput,
    SlotInput,
    create_appointment,
    create_schedule,
    create_slot,
)


class SchedulingService:
    """Service for managing scheduling resources"""

    def __init__(self, client: FHIRClient):
        self.client = client

    # Appointments
    async def create_appointment(self, appt: AppointmentInput) -> Appointment:
        """Create a patient appointment"""
        return await self.client.create(create_appointment(appt))

    async def get_appointment(self, appointment_id: str) -> Appointment:
        """Get appointment by ID"""
        return await self.client.read("Appointment", appointment_id, Appointment)

    async def update_appointment(self, appointment_id: str, appt: AppointmentInput) -> Appointment:
        """Update a patient appointment"""
        resource = create_appointment(appt)
        resource.id = appointment_id
        return await self.client.update(resource)

    async def delete_appointment(self, appointment_id: str) -> None:
        """Delete a patient appointment"""
        await self.client.delete("Appointment", appointment_id)

    async def get_patient_appointments(self, patient_id: str) -> list[Appointment]:
        """Get all appointments for a patient"""
        return await self.client.search("Appointment", Appointment, {"patient": patient_id})

    async def get_practitioner_appointments(self, practitioner_id: str) -> list[Appointment]:
        """Get all appointments for a practitioner"""
        return await self.client.search(
            "Appointment", Appointment, {"practitioner": practitioner_id}
        )

    # Schedules
    async def create_schedule(self, schedule: ScheduleInput) -> Schedule:
        """Create a schedule template"""
        return await self.client.create(create_schedule(schedule))

    async def get_schedule(self, schedule_id: str) -> Schedule:
        """Get schedule by ID"""
        return await self.client.read("Schedule", schedule_id, Schedule)

    async def update_schedule(self, schedule_id: str, schedule: ScheduleInput) -> Schedule:
        """Update a schedule"""
        resource = create_schedule(schedule)
        resource.id = schedule_id
        return await self.client.update(resource)

    async def delete_schedule(self, schedule_id: str) -> None:
        """Delete a schedule"""
        await self.client.delete("Schedule", schedule_id)

    async def get_practitioner_schedules(self, practitioner_id: str) -> list[Schedule]:
        """Get all schedules for a practitioner"""
        return await self.client.search(
            "Schedule", Schedule, {"actor": f"Practitioner/{practitioner_id}"}
        )

    # Slots
    async def create_slot(self, slot: SlotInput) -> Slot:
        """Create an appointment slot"""
        return await self.client.create(create_slot(slot))

    async def get_slot(self, slot_id: str) -> Slot:
        """Get slot by ID"""
        return await self.client.read("Slot", slot_id, Slot)

    async def update_slot(self, slot_id: str, slot: SlotInput) -> Slot:
        """Update an appointment slot"""
        resource = create_slot(slot)
        resource.id = slot_id
        return await self.client.update(resource)

    async def delete_slot(self, slot_id: str) -> None:
        """Delete an appointment slot"""
        await self.client.delete("Slot", slot_id)

    async def get_available_slots(self, schedule_id: str) -> list[Slot]:
        """Get available (free) slots for a schedule"""
        return await self.client.search("Slot", Slot, {"schedule": schedule_id, "status": "free"})
