"""SQLAlchemy ORM models for the referral pipeline schema."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def _utcnow() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class Organization(Base):
    """Lightweight organization registry.

    Identifies "who we are" (is_self=True) for determining incoming vs outgoing
    referral direction. Referral requesters and performers reference orgs.
    """

    __tablename__ = "organization"
    __table_args__ = (
        UniqueConstraint("fhir_id", "fhir_server", name="uq_org_fhir"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    fhir_id: Mapped[str | None] = mapped_column(Text)
    fhir_server: Mapped[str | None] = mapped_column(Text)
    is_self: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )


class PipelineStage(Base):
    """DB-driven pipeline stage configuration.

    Stages are seeded by the initial migration and can be configured at runtime.
    Each pipeline type (incoming/outgoing) has its own ordered set of stages.
    """

    __tablename__ = "pipeline_stage"
    __table_args__ = (
        UniqueConstraint("pipeline_type", "name", name="uq_stage_type_name"),
        UniqueConstraint("pipeline_type", "sort_order", name="uq_stage_type_order"),
        CheckConstraint(
            "pipeline_type IN ('incoming', 'outgoing')",
            name="ck_stage_pipeline_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    pipeline_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )

    # Relationships
    referrals_in_stage: Mapped[list["Referral"]] = relationship(
        back_populates="current_stage", foreign_keys="Referral.current_stage_id",
    )


class Referral(Base):
    """Core referral record tracking a referral through the pipeline.

    Links to a FHIR ServiceRequest (for FHIR-synced referrals) and tracks
    pipeline state locally. Clinical data fields are denormalized from FHIR
    at sync time or entered manually.
    """

    __tablename__ = "referral"
    __table_args__ = (
        UniqueConstraint(
            "fhir_service_request_id", "fhir_server",
            name="uq_referral_fhir",
        ),
        CheckConstraint(
            "pipeline_type IN ('incoming', 'outgoing')",
            name="ck_referral_pipeline_type",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'cancelled', 'on_hold')",
            name="ck_referral_status",
        ),
        CheckConstraint(
            "priority IS NULL OR priority IN ('routine', 'urgent', 'asap', 'stat')",
            name="ck_referral_priority",
        ),
        CheckConstraint(
            "source IN ('fhir_sync', 'manual')",
            name="ck_referral_source",
        ),
        # Dashboard query: active referrals grouped by stage
        Index("idx_referral_active_stage", "pipeline_type", "current_stage_id"),
        # FHIR sync lookups
        Index("idx_referral_fhir_lookup", "fhir_server", "fhir_service_request_id"),
        # Time-range KPI queries
        Index("idx_referral_created", "created_at"),
        Index("idx_referral_authored", "authored_on"),
        # Patient lookup
        Index("idx_referral_patient", "patient_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    pipeline_type: Mapped[str] = mapped_column(Text, nullable=False)
    current_stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("pipeline_stage.id"), nullable=False,
    )

    # FHIR linkage (nullable for manual entry)
    fhir_service_request_id: Mapped[str | None] = mapped_column(Text)
    fhir_server: Mapped[str | None] = mapped_column(Text)
    fhir_status: Mapped[str | None] = mapped_column(Text)

    # Clinical data (denormalized from FHIR or entered manually)
    patient_id: Mapped[str | None] = mapped_column(Text)
    patient_display: Mapped[str | None] = mapped_column(Text)
    requester_display: Mapped[str | None] = mapped_column(Text)
    performer_display: Mapped[str | None] = mapped_column(Text)
    requesting_org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("organization.id"),
    )
    performing_org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("organization.id"),
    )
    specialty_display: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(Text)
    authored_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    category_display: Mapped[str | None] = mapped_column(Text)

    # Pipeline state
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")

    # Scheduling outcome (for conversion/lag metrics)
    appointment_scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    appointment_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    # Source tracking
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )

    # Relationships
    current_stage: Mapped["PipelineStage"] = relationship(
        back_populates="referrals_in_stage", foreign_keys=[current_stage_id],
    )
    requesting_org: Mapped["Organization | None"] = relationship(
        foreign_keys=[requesting_org_id],
    )
    performing_org: Mapped["Organization | None"] = relationship(
        foreign_keys=[performing_org_id],
    )
    transitions: Mapped[list["StageTransition"]] = relationship(
        back_populates="referral", cascade="all, delete-orphan",
        order_by="StageTransition.transitioned_at",
        primaryjoin="Referral.id == foreign(StageTransition.referral_id)",
    )


class StageTransition(Base):
    """Audit trail for every referral stage change.

    Each row represents a referral moving from one stage to another.
    The duration_seconds field is pre-computed at transition time for
    efficient avg-wait queries.
    """

    __tablename__ = "stage_transition"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('advanced', 'returned', 'escalated', 'cancelled', 'completed')",
            name="ck_transition_outcome",
        ),
        CheckConstraint(
            "pipeline_type IN ('incoming', 'outgoing')",
            name="ck_transition_pipeline_type",
        ),
        # Per-stage metrics: transitions into a stage
        Index("idx_transition_to_stage", "to_stage_id", "transitioned_at"),
        # Per-stage metrics: transitions out (completion rate)
        Index("idx_transition_from_stage", "from_stage_id", "transitioned_at"),
        # Referral history timeline
        Index("idx_transition_referral_timeline", "referral_id", "transitioned_at"),
        # Pipeline-scoped time queries
        Index("idx_transition_pipeline_time", "pipeline_type", "transitioned_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    # NOTE: ForeignKey constraints omitted on referral_id, from_stage_id,
    # to_stage_id because DuckDB's FK implementation blocks UPDATEs on
    # referenced rows. Referential integrity is enforced by application logic.
    referral_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False,
    )
    from_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
    )
    to_stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False,
    )

    # Transition metadata
    outcome: Mapped[str] = mapped_column(Text, nullable=False, default="advanced")
    actor: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    # Denormalized for query performance
    pipeline_type: Mapped[str] = mapped_column(Text, nullable=False)

    transitioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )

    # Relationships (primaryjoin explicit since FK constraints are omitted for DuckDB)
    referral: Mapped["Referral"] = relationship(
        back_populates="transitions",
        primaryjoin="foreign(StageTransition.referral_id) == Referral.id",
    )
    from_stage: Mapped["PipelineStage | None"] = relationship(
        primaryjoin="foreign(StageTransition.from_stage_id) == PipelineStage.id",
    )
    to_stage: Mapped["PipelineStage"] = relationship(
        primaryjoin="foreign(StageTransition.to_stage_id) == PipelineStage.id",
    )
