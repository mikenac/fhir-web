"""Tests for the referral pipeline ORM models.

These tests verify model construction, defaults, constraints, and relationships
without requiring a live database — they use SQLite in-memory for speed.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Base,
    Organization,
    PipelineStage,
    Referral,
    StageTransition,
)


@pytest.fixture()
def db_session():
    """Create an in-memory SQLite database with all tables for testing.

    Models use generic SQLAlchemy types (Uuid, Text, etc.) so they work
    with SQLite directly. Python-side defaults handle UUID and timestamp
    generation.
    """
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _setup_sqlite(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def sample_stages(db_session: Session) -> dict[str, PipelineStage]:
    """Seed incoming pipeline stages and return them keyed by name."""
    stages = {}
    for i, (name, display, terminal) in enumerate(
        [
            ("validation", "Validation", False),
            ("scheduling", "Scheduling", False),
            ("authorization", "Authorization", False),
            ("qa", "QA", False),
            ("completed", "Completed", True),
            ("cancelled", "Cancelled", True),
        ],
        start=1,
    ):
        stage = PipelineStage(
            pipeline_type="incoming",
            name=name,
            display_name=display,
            sort_order=i,
            is_terminal=terminal,
        )
        db_session.add(stage)
        stages[name] = stage
    db_session.flush()
    return stages


@pytest.fixture()
def sample_org(db_session: Session) -> Organization:
    """Create a sample organization."""
    org = Organization(name="Test Health System", is_self=True)
    db_session.add(org)
    db_session.flush()
    return org


# --- Organization tests ---


class TestOrganization:
    def test_create_organization(self, db_session: Session):
        org = Organization(name="Acme Hospital", fhir_id="org-123", fhir_server="hapi")
        db_session.add(org)
        db_session.flush()

        assert org.id is not None
        assert org.name == "Acme Hospital"
        assert org.fhir_id == "org-123"
        assert org.fhir_server == "hapi"
        assert org.is_self is False

    def test_organization_defaults(self, db_session: Session):
        org = Organization(name="Minimal Org")
        db_session.add(org)
        db_session.flush()

        assert org.is_self is False
        assert org.fhir_id is None
        assert org.fhir_server is None
        assert org.created_at is not None
        assert org.updated_at is not None

    def test_organization_is_self(self, db_session: Session):
        org = Organization(name="Our Org", is_self=True)
        db_session.add(org)
        db_session.flush()

        assert org.is_self is True


# --- PipelineStage tests ---


class TestPipelineStage:
    def test_create_stage(self, db_session: Session):
        stage = PipelineStage(
            pipeline_type="incoming",
            name="validation",
            display_name="Validation",
            sort_order=1,
        )
        db_session.add(stage)
        db_session.flush()

        assert stage.id is not None
        assert stage.pipeline_type == "incoming"
        assert stage.name == "validation"
        assert stage.is_terminal is False
        assert stage.is_active is True

    def test_terminal_stage(self, db_session: Session):
        stage = PipelineStage(
            pipeline_type="outgoing",
            name="completed",
            display_name="Completed",
            sort_order=5,
            is_terminal=True,
        )
        db_session.add(stage)
        db_session.flush()

        assert stage.is_terminal is True

    def test_seed_stages(self, sample_stages):
        assert len(sample_stages) == 6
        assert sample_stages["validation"].sort_order == 1
        assert sample_stages["completed"].is_terminal is True
        assert sample_stages["cancelled"].is_terminal is True
        assert sample_stages["scheduling"].is_terminal is False


# --- Referral tests ---


class TestReferral:
    def test_create_referral(self, db_session: Session, sample_stages, sample_org):
        referral = Referral(
            pipeline_type="incoming",
            current_stage_id=sample_stages["validation"].id,
            patient_id="patient-1",
            patient_display="John Doe",
            requester_display="Dr. Smith",
            requesting_org_id=sample_org.id,
            priority="routine",
            source="manual",
        )
        db_session.add(referral)
        db_session.flush()

        assert referral.id is not None
        assert referral.status == "active"
        assert referral.source == "manual"
        assert referral.pipeline_type == "incoming"
        assert referral.patient_display == "John Doe"

    def test_referral_defaults(self, db_session: Session, sample_stages):
        referral = Referral(
            pipeline_type="incoming",
            current_stage_id=sample_stages["validation"].id,
        )
        db_session.add(referral)
        db_session.flush()

        assert referral.status == "active"
        assert referral.source == "manual"
        assert referral.patient_id is None
        assert referral.fhir_service_request_id is None
        assert referral.priority is None
        assert referral.appointment_scheduled_at is None

    def test_referral_fhir_linked(self, db_session: Session, sample_stages):
        referral = Referral(
            pipeline_type="incoming",
            current_stage_id=sample_stages["validation"].id,
            fhir_service_request_id="sr-456",
            fhir_server="hapi",
            fhir_status="active",
            source="fhir_sync",
        )
        db_session.add(referral)
        db_session.flush()

        assert referral.fhir_service_request_id == "sr-456"
        assert referral.source == "fhir_sync"

    def test_referral_stage_relationship(self, db_session: Session, sample_stages):
        referral = Referral(
            pipeline_type="incoming",
            current_stage_id=sample_stages["scheduling"].id,
        )
        db_session.add(referral)
        db_session.flush()

        assert referral.current_stage.name == "scheduling"
        assert referral.current_stage.display_name == "Scheduling"

    def test_referral_org_relationships(self, db_session: Session, sample_stages):
        req_org = Organization(name="Requesting Hospital")
        perf_org = Organization(name="Performing Clinic")
        db_session.add_all([req_org, perf_org])
        db_session.flush()

        referral = Referral(
            pipeline_type="incoming",
            current_stage_id=sample_stages["validation"].id,
            requesting_org_id=req_org.id,
            performing_org_id=perf_org.id,
        )
        db_session.add(referral)
        db_session.flush()

        assert referral.requesting_org.name == "Requesting Hospital"
        assert referral.performing_org.name == "Performing Clinic"

    def test_referral_with_appointment(self, db_session: Session, sample_stages):
        now = datetime.now(timezone.utc)
        referral = Referral(
            pipeline_type="incoming",
            current_stage_id=sample_stages["scheduling"].id,
            appointment_scheduled_at=now,
            appointment_datetime=now,
        )
        db_session.add(referral)
        db_session.flush()

        assert referral.appointment_scheduled_at == now
        assert referral.appointment_datetime == now


# --- StageTransition tests ---


class TestStageTransition:
    def test_create_initial_transition(self, db_session: Session, sample_stages):
        """First transition has no from_stage (entry into pipeline)."""
        referral = Referral(
            pipeline_type="incoming",
            current_stage_id=sample_stages["validation"].id,
        )
        db_session.add(referral)
        db_session.flush()

        transition = StageTransition(
            referral_id=referral.id,
            from_stage_id=None,
            to_stage_id=sample_stages["validation"].id,
            outcome="advanced",
            pipeline_type="incoming",
            actor="system",
        )
        db_session.add(transition)
        db_session.flush()

        assert transition.id is not None
        assert transition.from_stage_id is None
        assert transition.to_stage.name == "validation"
        assert transition.outcome == "advanced"
        assert transition.actor == "system"

    def test_create_stage_advance(self, db_session: Session, sample_stages):
        """Transition from one stage to the next."""
        referral = Referral(
            pipeline_type="incoming",
            current_stage_id=sample_stages["scheduling"].id,
        )
        db_session.add(referral)
        db_session.flush()

        transition = StageTransition(
            referral_id=referral.id,
            from_stage_id=sample_stages["validation"].id,
            to_stage_id=sample_stages["scheduling"].id,
            outcome="advanced",
            pipeline_type="incoming",
            duration_seconds=3600,
            actor="user@example.com",
        )
        db_session.add(transition)
        db_session.flush()

        assert transition.from_stage.name == "validation"
        assert transition.to_stage.name == "scheduling"
        assert transition.duration_seconds == 3600

    def test_transition_outcomes(self, db_session: Session, sample_stages):
        """Test different transition outcomes."""
        referral = Referral(
            pipeline_type="incoming",
            current_stage_id=sample_stages["cancelled"].id,
        )
        db_session.add(referral)
        db_session.flush()

        for outcome in ("advanced", "returned", "escalated", "cancelled", "completed"):
            t = StageTransition(
                referral_id=referral.id,
                from_stage_id=sample_stages["validation"].id,
                to_stage_id=sample_stages["scheduling"].id,
                outcome=outcome,
                pipeline_type="incoming",
            )
            db_session.add(t)
            db_session.flush()
            assert t.outcome == outcome

    def test_referral_transitions_relationship(self, db_session: Session, sample_stages):
        """Referral.transitions returns ordered list of transitions."""
        referral = Referral(
            pipeline_type="incoming",
            current_stage_id=sample_stages["authorization"].id,
        )
        db_session.add(referral)
        db_session.flush()

        for from_stage, to_stage in [
            (None, "validation"),
            ("validation", "scheduling"),
            ("scheduling", "authorization"),
        ]:
            t = StageTransition(
                referral_id=referral.id,
                from_stage_id=sample_stages[from_stage].id if from_stage else None,
                to_stage_id=sample_stages[to_stage].id,
                outcome="advanced",
                pipeline_type="incoming",
            )
            db_session.add(t)

        db_session.flush()
        db_session.refresh(referral)

        assert len(referral.transitions) == 3
        assert referral.transitions[0].to_stage.name == "validation"
        assert referral.transitions[2].to_stage.name == "authorization"

    def test_cascade_delete(self, db_session: Session, sample_stages):
        """Deleting a referral cascades to its transitions."""
        referral = Referral(
            pipeline_type="incoming",
            current_stage_id=sample_stages["validation"].id,
        )
        db_session.add(referral)
        db_session.flush()

        transition = StageTransition(
            referral_id=referral.id,
            to_stage_id=sample_stages["validation"].id,
            outcome="advanced",
            pipeline_type="incoming",
        )
        db_session.add(transition)
        db_session.flush()

        transition_id = transition.id
        db_session.delete(referral)
        db_session.flush()

        result = db_session.get(StageTransition, transition_id)
        assert result is None
