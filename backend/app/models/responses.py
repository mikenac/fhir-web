"""API response models."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str


class PatientSummary(BaseModel):
    """Simplified patient summary for API responses."""

    id: str
    family_name: str
    given_names: list[str]
    full_name: str
    birth_date: Optional[date] = None
    mrn: str
    gender: str | None = None
    phone: str | None = None
    email: str | None = None


class EncounterSummary(BaseModel):
    """Simplified encounter summary."""

    id: str
    patient_id: str
    status: str
    class_code: str
    type_display: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    reason_display: str | None = None


class OrderSummary(BaseModel):
    """Simplified order summary."""

    id: str
    patient_id: str
    status: str
    intent: str
    code_display: str
    authored_on: datetime | None = None
    note: str | None = None


class PractitionerSummary(BaseModel):
    """Simplified practitioner summary."""

    id: str
    family_name: str
    given_names: list[str]
    full_name: str
    npi: str
    phone: str | None = None
    email: str | None = None


class ReferralSummary(BaseModel):
    """Referral-specific summary for the dashboard."""

    id: str
    patient_id: str
    patient_display: str | None = None
    status: str
    intent: str
    category_display: str | None = None
    code_display: str
    priority: str | None = None
    authored_on: datetime | None = None
    requester_display: str | None = None
    performer_display: str | None = None
    note: str | None = None


class ReferralDashboardResponse(BaseModel):
    """Dashboard response with referrals and summary metrics."""

    total: int
    results: list[ReferralSummary]
    status_counts: dict[str, int]


class SearchResultsResponse(BaseModel):
    """Generic search results response."""

    total: int
    results: list[dict]
