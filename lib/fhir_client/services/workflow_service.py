"""Workflow service - tasks and communications"""

from fhir.resources.R4B.communication import Communication
from fhir.resources.R4B.task import Task

from ..client.fhir_client import FHIRClient
from ..models.workflow_data import (
    CommunicationInput,
    TaskInput,
    create_communication,
    create_task,
)


class WorkflowService:
    """Service for managing workflow resources"""

    def __init__(self, client: FHIRClient):
        self.client = client

    # Tasks
    async def create_task(self, task: TaskInput) -> Task:
        """Create a workflow task"""
        return await self.client.create(create_task(task))

    async def get_task(self, task_id: str) -> Task:
        """Get task by ID"""
        return await self.client.read("Task", task_id, Task)

    async def update_task(self, task_id: str, task: TaskInput) -> Task:
        """Update a workflow task"""
        resource = create_task(task)
        resource.id = task_id
        return await self.client.update(resource)

    async def delete_task(self, task_id: str) -> None:
        """Delete a workflow task"""
        await self.client.delete("Task", task_id)

    async def get_patient_tasks(self, patient_id: str) -> list[Task]:
        """Get all tasks for a patient"""
        return await self.client.search("Task", Task, {"patient": patient_id})

    async def get_tasks_by_owner(self, practitioner_id: str) -> list[Task]:
        """Get all tasks assigned to a practitioner"""
        return await self.client.search("Task", Task, {"owner": practitioner_id})

    # Communications
    async def create_communication(self, comm: CommunicationInput) -> Communication:
        """Create a clinical communication"""
        return await self.client.create(create_communication(comm))

    async def get_communication(self, communication_id: str) -> Communication:
        """Get communication by ID"""
        return await self.client.read("Communication", communication_id, Communication)

    async def update_communication(
        self, communication_id: str, comm: CommunicationInput
    ) -> Communication:
        """Update a clinical communication"""
        resource = create_communication(comm)
        resource.id = communication_id
        return await self.client.update(resource)

    async def delete_communication(self, communication_id: str) -> None:
        """Delete a clinical communication"""
        await self.client.delete("Communication", communication_id)

    async def get_patient_communications(self, patient_id: str) -> list[Communication]:
        """Get all communications for a patient"""
        return await self.client.search("Communication", Communication, {"subject": patient_id})
