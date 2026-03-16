"""Create referral pipeline tables and seed pipeline stages.

Revision ID: 001
Revises:
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- organization ---
    op.create_table(
        "organization",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("fhir_id", sa.Text(), nullable=True),
        sa.Column("fhir_server", sa.Text(), nullable=True),
        sa.Column("is_self", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("current_timestamp")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("current_timestamp")),
        sa.UniqueConstraint("fhir_id", "fhir_server", name="uq_org_fhir"),
    )

    # --- pipeline_stage ---
    op.create_table(
        "pipeline_stage",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("pipeline_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("current_timestamp")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("current_timestamp")),
        sa.UniqueConstraint("pipeline_type", "name", name="uq_stage_type_name"),
        sa.UniqueConstraint("pipeline_type", "sort_order", name="uq_stage_type_order"),
        sa.CheckConstraint("pipeline_type IN ('incoming', 'outgoing')", name="ck_stage_pipeline_type"),
    )

    # --- referral ---
    op.create_table(
        "referral",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("pipeline_type", sa.Text(), nullable=False),
        sa.Column("current_stage_id", sa.Uuid(), sa.ForeignKey("pipeline_stage.id"), nullable=False),
        sa.Column("fhir_service_request_id", sa.Text(), nullable=True),
        sa.Column("fhir_server", sa.Text(), nullable=True),
        sa.Column("fhir_status", sa.Text(), nullable=True),
        sa.Column("patient_id", sa.Text(), nullable=True),
        sa.Column("patient_display", sa.Text(), nullable=True),
        sa.Column("requester_display", sa.Text(), nullable=True),
        sa.Column("performer_display", sa.Text(), nullable=True),
        sa.Column("requesting_org_id", sa.Uuid(), sa.ForeignKey("organization.id"), nullable=True),
        sa.Column("performing_org_id", sa.Uuid(), sa.ForeignKey("organization.id"), nullable=True),
        sa.Column("specialty_display", sa.Text(), nullable=True),
        sa.Column("priority", sa.Text(), nullable=True),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column("authored_on", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("category_display", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("appointment_scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("appointment_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("current_timestamp")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("current_timestamp")),
        sa.UniqueConstraint("fhir_service_request_id", "fhir_server", name="uq_referral_fhir"),
        sa.CheckConstraint("pipeline_type IN ('incoming', 'outgoing')", name="ck_referral_pipeline_type"),
        sa.CheckConstraint("status IN ('active', 'completed', 'cancelled', 'on_hold')", name="ck_referral_status"),
        sa.CheckConstraint(
            "priority IS NULL OR priority IN ('routine', 'urgent', 'asap', 'stat')",
            name="ck_referral_priority",
        ),
        sa.CheckConstraint("source IN ('fhir_sync', 'manual')", name="ck_referral_source"),
    )

    # Referral indexes
    op.create_index("idx_referral_active_stage", "referral", ["pipeline_type", "current_stage_id"])
    op.create_index("idx_referral_fhir_lookup", "referral", ["fhir_server", "fhir_service_request_id"])
    op.create_index("idx_referral_created", "referral", ["created_at"])
    op.create_index("idx_referral_authored", "referral", ["authored_on"])
    op.create_index("idx_referral_patient", "referral", ["patient_id"])

    # --- stage_transition ---
    op.create_table(
        "stage_transition",
        sa.Column("id", sa.Uuid(), primary_key=True),
        # NOTE: FK constraints omitted — DuckDB's FK implementation blocks
        # UPDATEs on rows referenced by other tables. App logic ensures integrity.
        sa.Column("referral_id", sa.Uuid(), nullable=False),
        sa.Column("from_stage_id", sa.Uuid(), nullable=True),
        sa.Column("to_stage_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False, server_default=sa.text("'advanced'")),
        sa.Column("actor", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("pipeline_type", sa.Text(), nullable=False),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("current_timestamp")),
        sa.CheckConstraint(
            "outcome IN ('advanced', 'returned', 'escalated', 'cancelled', 'completed')",
            name="ck_transition_outcome",
        ),
        sa.CheckConstraint("pipeline_type IN ('incoming', 'outgoing')", name="ck_transition_pipeline_type"),
    )

    # Stage transition indexes
    op.create_index("idx_transition_to_stage", "stage_transition", ["to_stage_id", "transitioned_at"])
    op.create_index("idx_transition_from_stage", "stage_transition", ["from_stage_id", "transitioned_at"])
    op.create_index("idx_transition_referral_timeline", "stage_transition", ["referral_id", "transitioned_at"])
    op.create_index("idx_transition_pipeline_time", "stage_transition", ["pipeline_type", "transitioned_at"])

    # --- Seed pipeline stages ---
    pipeline_stage = sa.table(
        "pipeline_stage",
        sa.column("id", sa.Uuid),
        sa.column("pipeline_type", sa.Text),
        sa.column("name", sa.Text),
        sa.column("display_name", sa.Text),
        sa.column("sort_order", sa.Integer),
        sa.column("is_terminal", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # Incoming pipeline stages
    op.bulk_insert(
        pipeline_stage,
        [
            {"id": str(uuid.uuid4()), "pipeline_type": "incoming", "name": "validation", "display_name": "Validation", "sort_order": 1, "is_terminal": False, "created_at": now, "updated_at": now},
            {"id": str(uuid.uuid4()), "pipeline_type": "incoming", "name": "scheduling", "display_name": "Scheduling", "sort_order": 2, "is_terminal": False, "created_at": now, "updated_at": now},
            {"id": str(uuid.uuid4()), "pipeline_type": "incoming", "name": "authorization", "display_name": "Authorization", "sort_order": 3, "is_terminal": False, "created_at": now, "updated_at": now},
            {"id": str(uuid.uuid4()), "pipeline_type": "incoming", "name": "qa", "display_name": "QA", "sort_order": 4, "is_terminal": False, "created_at": now, "updated_at": now},
            {"id": str(uuid.uuid4()), "pipeline_type": "incoming", "name": "completed", "display_name": "Completed", "sort_order": 5, "is_terminal": True, "created_at": now, "updated_at": now},
            {"id": str(uuid.uuid4()), "pipeline_type": "incoming", "name": "cancelled", "display_name": "Cancelled", "sort_order": 6, "is_terminal": True, "created_at": now, "updated_at": now},
        ],
    )

    # Outgoing pipeline stages
    op.bulk_insert(
        pipeline_stage,
        [
            {"id": str(uuid.uuid4()), "pipeline_type": "outgoing", "name": "validation", "display_name": "Validation", "sort_order": 1, "is_terminal": False, "created_at": now, "updated_at": now},
            {"id": str(uuid.uuid4()), "pipeline_type": "outgoing", "name": "duplicate_detection", "display_name": "Duplicate Detection", "sort_order": 2, "is_terminal": False, "created_at": now, "updated_at": now},
            {"id": str(uuid.uuid4()), "pipeline_type": "outgoing", "name": "virtual_consult_eligibility", "display_name": "Virtual Consult Eligibility", "sort_order": 3, "is_terminal": False, "created_at": now, "updated_at": now},
            {"id": str(uuid.uuid4()), "pipeline_type": "outgoing", "name": "routing", "display_name": "Routing", "sort_order": 4, "is_terminal": False, "created_at": now, "updated_at": now},
            {"id": str(uuid.uuid4()), "pipeline_type": "outgoing", "name": "completed", "display_name": "Completed", "sort_order": 5, "is_terminal": True, "created_at": now, "updated_at": now},
            {"id": str(uuid.uuid4()), "pipeline_type": "outgoing", "name": "cancelled", "display_name": "Cancelled", "sort_order": 6, "is_terminal": True, "created_at": now, "updated_at": now},
        ],
    )


def downgrade() -> None:
    op.drop_table("stage_transition")
    op.drop_table("referral")
    op.drop_table("pipeline_stage")
    op.drop_table("organization")
