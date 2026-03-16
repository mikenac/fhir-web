"""Pydantic models for the referral pipeline API."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# --- Enums ---


class PipelineType(str, Enum):
    incoming = "incoming"
    outgoing = "outgoing"


class ReferralStatus(str, Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    on_hold = "on_hold"


class ReferralPriority(str, Enum):
    routine = "routine"
    urgent = "urgent"
    asap = "asap"
    stat = "stat"


class TransitionOutcome(str, Enum):
    advanced = "advanced"
    returned = "returned"
    escalated = "escalated"
    cancelled = "cancelled"
    completed = "completed"


class ReferralSource(str, Enum):
    fhir_sync = "fhir_sync"
    manual = "manual"


# --- Stage responses ---


class PipelineStageResponse(BaseModel):
    """A single pipeline stage configuration."""

    id: uuid.UUID
    pipeline_type: PipelineType
    name: str
    display_name: str
    sort_order: int
    is_terminal: bool
    is_active: bool


class StageWithCountResponse(PipelineStageResponse):
    """Stage with count of active referrals currently in it."""

    active_referral_count: int = 0


class PipelineBoardResponse(BaseModel):
    """Full Kanban board view: all stages with counts for one pipeline type."""

    pipeline_type: PipelineType
    stages: list[StageWithCountResponse]
    total_active: int


# --- Referral responses ---


class ReferralResponse(BaseModel):
    """Full referral detail."""

    id: uuid.UUID
    pipeline_type: PipelineType
    current_stage_id: uuid.UUID
    current_stage_name: str
    current_stage_display_name: str
    fhir_service_request_id: str | None = None
    fhir_server: str | None = None
    fhir_status: str | None = None
    patient_id: str | None = None
    patient_display: str | None = None
    requester_display: str | None = None
    performer_display: str | None = None
    specialty_display: str | None = None
    priority: str | None = None
    intent: str | None = None
    authored_on: datetime | None = None
    note: str | None = None
    category_display: str | None = None
    status: ReferralStatus
    appointment_scheduled_at: datetime | None = None
    appointment_datetime: datetime | None = None
    source: ReferralSource
    created_at: datetime
    updated_at: datetime


class ReferralListResponse(BaseModel):
    """Paginated list of referrals."""

    total: int
    results: list[ReferralResponse]


# --- Transition responses ---


class TransitionResponse(BaseModel):
    """A single stage transition in the audit trail."""

    id: uuid.UUID
    referral_id: uuid.UUID
    from_stage_name: str | None = None
    from_stage_display_name: str | None = None
    to_stage_name: str
    to_stage_display_name: str
    outcome: TransitionOutcome
    actor: str | None = None
    reason: str | None = None
    duration_seconds: int | None = None
    transitioned_at: datetime


class ReferralHistoryResponse(BaseModel):
    """Full transition history for one referral."""

    referral_id: uuid.UUID
    transitions: list[TransitionResponse]


# --- Metrics responses ---


class StageMetric(BaseModel):
    """KPI metrics for a single stage."""

    stage_id: uuid.UUID
    stage_name: str
    stage_display_name: str
    active_count: int = 0
    completed_count: int = 0
    avg_duration_seconds: float | None = None


class PipelineMetricsResponse(BaseModel):
    """Dashboard KPI metrics for a pipeline type."""

    pipeline_type: PipelineType
    total_referrals: int
    active_referrals: int
    completed_referrals: int
    cancelled_referrals: int
    conversion_rate: float | None = None
    avg_total_duration_seconds: float | None = None
    stage_metrics: list[StageMetric]


# --- Request models ---


class ReferralCreateRequest(BaseModel):
    """Create a new referral (manual entry or FHIR sync)."""

    pipeline_type: PipelineType
    patient_id: str | None = None
    patient_display: str | None = None
    requester_display: str | None = None
    performer_display: str | None = None
    requesting_org_id: uuid.UUID | None = None
    performing_org_id: uuid.UUID | None = None
    specialty_display: str | None = None
    priority: ReferralPriority | None = None
    intent: str | None = None
    authored_on: datetime | None = None
    note: str | None = None
    category_display: str | None = None
    fhir_service_request_id: str | None = None
    fhir_server: str | None = None
    fhir_status: str | None = None
    source: ReferralSource = ReferralSource.manual


class ReferralUpdateRequest(BaseModel):
    """Partial update for referral metadata (not stage moves)."""

    patient_display: str | None = None
    requester_display: str | None = None
    performer_display: str | None = None
    specialty_display: str | None = None
    priority: ReferralPriority | None = None
    note: str | None = None
    status: ReferralStatus | None = None
    appointment_scheduled_at: datetime | None = None
    appointment_datetime: datetime | None = None


class TransitionCreateRequest(BaseModel):
    """Move a referral to a different stage."""

    to_stage_id: uuid.UUID
    outcome: TransitionOutcome = TransitionOutcome.advanced
    actor: str | None = None
    reason: str | None = None
