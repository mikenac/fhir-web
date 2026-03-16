"""Tests for the referral pipeline API endpoints."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, PipelineStage, Referral, StageTransition
from app.db.session import get_db_session
from app.main import app


# --- Test fixtures ---


@pytest.fixture()
def db_session():
    """In-memory SQLite session with tables created and stages seeded.

    Uses StaticPool and check_same_thread=False so the same connection
    can be shared across threads (FastAPI runs sync deps in a threadpool).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _setup_sqlite(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()

    # Seed pipeline stages (same as migration)
    _seed_stages(session)

    yield session
    session.close()
    engine.dispose()


def _seed_stages(session: Session):
    """Seed the incoming and outgoing pipeline stages."""
    incoming = [
        ("validation", "Validation", 1, False),
        ("scheduling", "Scheduling", 2, False),
        ("authorization", "Authorization", 3, False),
        ("qa", "QA", 4, False),
        ("completed", "Completed", 5, True),
        ("cancelled", "Cancelled", 6, True),
    ]
    outgoing = [
        ("validation", "Validation", 1, False),
        ("duplicate_detection", "Duplicate Detection", 2, False),
        ("virtual_consult_eligibility", "Virtual Consult Eligibility", 3, False),
        ("routing", "Routing", 4, False),
        ("completed", "Completed", 5, True),
        ("cancelled", "Cancelled", 6, True),
    ]
    for name, display, order, terminal in incoming:
        session.add(PipelineStage(
            pipeline_type="incoming", name=name, display_name=display,
            sort_order=order, is_terminal=terminal,
        ))
    for name, display, order, terminal in outgoing:
        session.add(PipelineStage(
            pipeline_type="outgoing", name=name, display_name=display,
            sort_order=order, is_terminal=terminal,
        ))
    session.commit()


@pytest.fixture()
def client(db_session: Session):
    """FastAPI test client with DB session overridden to use test SQLite."""
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


def _get_stage_id(db_session: Session, pipeline_type: str, name: str) -> str:
    """Helper to look up a stage UUID by type and name."""
    stage = db_session.query(PipelineStage).filter_by(
        pipeline_type=pipeline_type, name=name,
    ).one()
    return str(stage.id)


# --- Stage endpoint tests ---


class TestStageEndpoints:
    def test_list_incoming_stages(self, client, db_session):
        resp = client.get("/api/pipeline/stages/incoming")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6
        assert data[0]["name"] == "validation"
        assert data[0]["sort_order"] == 1
        assert data[4]["is_terminal"] is True

    def test_list_outgoing_stages(self, client, db_session):
        resp = client.get("/api/pipeline/stages/outgoing")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6
        assert data[1]["name"] == "duplicate_detection"

    def test_invalid_pipeline_type(self, client):
        resp = client.get("/api/pipeline/stages/invalid")
        assert resp.status_code == 422


class TestBoardEndpoint:
    def test_empty_board(self, client, db_session):
        resp = client.get("/api/pipeline/board/incoming")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline_type"] == "incoming"
        assert data["total_active"] == 0
        assert len(data["stages"]) == 6
        assert all(s["active_referral_count"] == 0 for s in data["stages"])

    def test_board_with_referrals(self, client, db_session):
        # Create a referral via API
        client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
            "patient_display": "John Doe",
        })
        resp = client.get("/api/pipeline/board/incoming")
        data = resp.json()
        assert data["total_active"] == 1
        # First stage (validation) should have the count
        assert data["stages"][0]["active_referral_count"] == 1


# --- Referral CRUD tests ---


class TestReferralCreate:
    def test_create_referral(self, client, db_session):
        resp = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
            "patient_id": "p-1",
            "patient_display": "Jane Doe",
            "requester_display": "Dr. Smith",
            "priority": "urgent",
            "source": "manual",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_display"] == "Jane Doe"
        assert data["priority"] == "urgent"
        assert data["status"] == "active"
        assert data["current_stage_name"] == "validation"
        assert data["source"] == "manual"

    def test_create_referral_auto_assigns_first_stage(self, client, db_session):
        resp = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "outgoing",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["current_stage_name"] == "validation"
        assert data["pipeline_type"] == "outgoing"

    def test_create_referral_creates_initial_transition(self, client, db_session):
        resp = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
        })
        referral_id = resp.json()["id"]

        history = client.get(f"/api/pipeline/referrals/{referral_id}/transitions")
        transitions = history.json()["transitions"]
        assert len(transitions) == 1
        assert transitions[0]["from_stage_name"] is None
        assert transitions[0]["to_stage_name"] == "validation"
        assert transitions[0]["outcome"] == "advanced"


class TestReferralGet:
    def test_get_referral(self, client, db_session):
        create_resp = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
            "patient_display": "Test Patient",
        })
        referral_id = create_resp.json()["id"]

        resp = client.get(f"/api/pipeline/referrals/{referral_id}")
        assert resp.status_code == 200
        assert resp.json()["patient_display"] == "Test Patient"

    def test_get_nonexistent_referral(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/pipeline/referrals/{fake_id}")
        assert resp.status_code == 404


class TestReferralUpdate:
    def test_update_referral(self, client, db_session):
        create_resp = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
            "patient_display": "Old Name",
        })
        referral_id = create_resp.json()["id"]

        resp = client.patch(f"/api/pipeline/referrals/{referral_id}", json={
            "patient_display": "New Name",
            "priority": "stat",
        })
        assert resp.status_code == 200
        assert resp.json()["patient_display"] == "New Name"
        assert resp.json()["priority"] == "stat"

    def test_update_nonexistent_referral(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.patch(f"/api/pipeline/referrals/{fake_id}", json={
            "note": "test",
        })
        assert resp.status_code == 404


class TestReferralList:
    def test_list_empty(self, client, db_session):
        resp = client.get("/api/pipeline/referrals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []

    def test_list_with_filters(self, client, db_session):
        # Create referrals in both pipelines
        client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
            "patient_display": "Alice",
        })
        client.post("/api/pipeline/referrals", json={
            "pipeline_type": "outgoing",
            "patient_display": "Bob",
        })

        # Filter by pipeline_type
        resp = client.get("/api/pipeline/referrals?pipeline_type=incoming")
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["patient_display"] == "Alice"

    def test_list_search(self, client, db_session):
        client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
            "patient_display": "Alice Johnson",
        })
        client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
            "patient_display": "Bob Smith",
        })

        resp = client.get("/api/pipeline/referrals?search=alice")
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["patient_display"] == "Alice Johnson"

    def test_list_pagination(self, client, db_session):
        # Create 3 referrals
        for i in range(3):
            client.post("/api/pipeline/referrals", json={
                "pipeline_type": "incoming",
                "patient_display": f"Patient {i}",
            })

        resp = client.get("/api/pipeline/referrals?limit=2&offset=0")
        data = resp.json()
        assert data["total"] == 3
        assert len(data["results"]) == 2

        resp2 = client.get("/api/pipeline/referrals?limit=2&offset=2")
        assert len(resp2.json()["results"]) == 1


# --- Transition tests ---


class TestTransitions:
    def test_advance_stage(self, client, db_session):
        # Create referral (starts in validation)
        create_resp = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
        })
        referral_id = create_resp.json()["id"]
        scheduling_id = _get_stage_id(db_session, "incoming", "scheduling")

        resp = client.post(
            f"/api/pipeline/referrals/{referral_id}/transitions",
            json={
                "to_stage_id": scheduling_id,
                "outcome": "advanced",
                "actor": "user@test.com",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["to_stage_name"] == "scheduling"
        assert data["from_stage_name"] == "validation"
        assert data["duration_seconds"] is not None
        assert data["actor"] == "user@test.com"

        # Verify referral was updated
        referral = client.get(f"/api/pipeline/referrals/{referral_id}").json()
        assert referral["current_stage_name"] == "scheduling"

    def test_terminal_stage_sets_status(self, client, db_session):
        create_resp = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
        })
        referral_id = create_resp.json()["id"]
        completed_id = _get_stage_id(db_session, "incoming", "completed")

        client.post(
            f"/api/pipeline/referrals/{referral_id}/transitions",
            json={"to_stage_id": completed_id, "outcome": "completed"},
        )

        referral = client.get(f"/api/pipeline/referrals/{referral_id}").json()
        assert referral["status"] == "completed"
        assert referral["current_stage_name"] == "completed"

    def test_cancelled_stage_sets_status(self, client, db_session):
        create_resp = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
        })
        referral_id = create_resp.json()["id"]
        cancelled_id = _get_stage_id(db_session, "incoming", "cancelled")

        client.post(
            f"/api/pipeline/referrals/{referral_id}/transitions",
            json={"to_stage_id": cancelled_id, "outcome": "cancelled"},
        )

        referral = client.get(f"/api/pipeline/referrals/{referral_id}").json()
        assert referral["status"] == "cancelled"

    def test_cannot_move_from_terminal(self, client, db_session):
        create_resp = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
        })
        referral_id = create_resp.json()["id"]
        completed_id = _get_stage_id(db_session, "incoming", "completed")
        scheduling_id = _get_stage_id(db_session, "incoming", "scheduling")

        # Move to terminal
        client.post(
            f"/api/pipeline/referrals/{referral_id}/transitions",
            json={"to_stage_id": completed_id, "outcome": "completed"},
        )

        # Try to move again
        resp = client.post(
            f"/api/pipeline/referrals/{referral_id}/transitions",
            json={"to_stage_id": scheduling_id},
        )
        assert resp.status_code == 400
        assert "terminal" in resp.json()["detail"].lower()

    def test_wrong_pipeline_type_rejected(self, client, db_session):
        create_resp = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
        })
        referral_id = create_resp.json()["id"]
        # Get an outgoing stage
        outgoing_stage_id = _get_stage_id(db_session, "outgoing", "routing")

        resp = client.post(
            f"/api/pipeline/referrals/{referral_id}/transitions",
            json={"to_stage_id": outgoing_stage_id},
        )
        assert resp.status_code == 400
        assert "pipeline" in resp.json()["detail"].lower()

    def test_get_history(self, client, db_session):
        create_resp = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
        })
        referral_id = create_resp.json()["id"]
        scheduling_id = _get_stage_id(db_session, "incoming", "scheduling")
        auth_id = _get_stage_id(db_session, "incoming", "authorization")

        # Make two transitions
        client.post(
            f"/api/pipeline/referrals/{referral_id}/transitions",
            json={"to_stage_id": scheduling_id},
        )
        client.post(
            f"/api/pipeline/referrals/{referral_id}/transitions",
            json={"to_stage_id": auth_id},
        )

        resp = client.get(f"/api/pipeline/referrals/{referral_id}/transitions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["referral_id"] == referral_id
        # Initial entry + 2 transitions = 3 total
        assert len(data["transitions"]) == 3
        assert data["transitions"][0]["to_stage_name"] == "validation"
        assert data["transitions"][1]["to_stage_name"] == "scheduling"
        assert data["transitions"][2]["to_stage_name"] == "authorization"


# --- Metrics tests ---


class TestMetrics:
    def test_empty_metrics(self, client, db_session):
        resp = client.get("/api/pipeline/metrics/incoming")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline_type"] == "incoming"
        assert data["total_referrals"] == 0
        assert data["active_referrals"] == 0
        assert data["conversion_rate"] is None
        assert len(data["stage_metrics"]) == 6

    def test_metrics_with_data(self, client, db_session):
        # Create 2 referrals
        resp1 = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
            "patient_display": "Patient 1",
        })
        resp2 = client.post("/api/pipeline/referrals", json={
            "pipeline_type": "incoming",
            "patient_display": "Patient 2",
        })

        # Complete one
        referral_id = resp1.json()["id"]
        completed_id = _get_stage_id(db_session, "incoming", "completed")
        client.post(
            f"/api/pipeline/referrals/{referral_id}/transitions",
            json={"to_stage_id": completed_id, "outcome": "completed"},
        )

        metrics = client.get("/api/pipeline/metrics/incoming").json()
        assert metrics["total_referrals"] == 2
        assert metrics["active_referrals"] == 1
        assert metrics["completed_referrals"] == 1
        assert metrics["cancelled_referrals"] == 0
        assert metrics["conversion_rate"] == 1.0  # 1 completed / (1 completed + 0 cancelled)
