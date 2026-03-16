"""Tests for the HAPI FHIR webhook endpoints.

Covers:
  - POST /api/webhooks/hapi with a valid ServiceRequest → creates Referral + StageTransition
  - POST /api/webhooks/hapi with same FHIR ID → updates, no duplicate
  - POST /api/webhooks/hapi with malformed / empty body → graceful handling
  - POST /api/webhooks/subscribe → mock httpx, check subscription_id stored
  - GET  /api/webhooks/status → reflects current state
  - DELETE /api/webhooks/subscribe → mock httpx, clears state

Test infrastructure mirrors test_pipeline.py: in-memory SQLite, seeded stages.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, PipelineStage, Referral, StageTransition
from app.db.session import get_db_session
from app.main import app
from app.routers import webhooks as webhooks_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """In-memory SQLite session with tables created and stages seeded."""
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

    # Seed pipeline stages (same shape as the real migration)
    _seed_stages(session)

    yield session
    session.close()
    engine.dispose()


def _seed_stages(session: Session) -> None:
    """Insert the standard incoming and outgoing pipeline stages."""
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
        session.add(
            PipelineStage(
                pipeline_type="incoming",
                name=name,
                display_name=display,
                sort_order=order,
                is_terminal=terminal,
            )
        )
    for name, display, order, terminal in outgoing:
        session.add(
            PipelineStage(
                pipeline_type="outgoing",
                name=name,
                display_name=display,
                sort_order=order,
                is_terminal=terminal,
            )
        )
    session.commit()


@pytest.fixture()
def client(db_session: Session):
    """FastAPI test client with the DB dependency overridden to use test SQLite.

    Also resets module-level subscription state before each test so tests
    do not bleed into each other.
    """
    # Override the DB dependency so the test DB is used instead of DuckDB.
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = _override

    # Reset subscription state so tests are isolated.
    webhooks_module._subscription_state["subscription_id"] = None

    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

VALID_SERVICE_REQUEST: dict[str, Any] = {
    "resourceType": "ServiceRequest",
    "id": "sr-hapi-001",
    "status": "active",
    "intent": "order",
    "priority": "routine",
    "subject": {
        "reference": "Patient/p-123",
        "display": "Jane Doe",
    },
    "requester": {
        "display": "Dr. Smith",
    },
    "performer": [
        {"display": "Dr. Jones"},
    ],
    "note": [
        {"text": "Urgent cardiology follow-up needed"},
    ],
    "category": [
        {
            "coding": [
                {"display": "Referral"},
            ]
        }
    ],
    "code": {
        "coding": [
            {"display": "Cardiology"},
        ]
    },
    "authoredOn": "2026-03-01T10:00:00Z",
}


# ---------------------------------------------------------------------------
# Webhook receiver tests
# ---------------------------------------------------------------------------


class TestWebhookReceiver:
    def test_new_service_request_creates_referral(
        self, client: TestClient, db_session: Session
    ) -> None:
        """A first-time ServiceRequest should create a Referral + StageTransition."""
        resp = client.post("/api/webhooks/hapi", json=VALID_SERVICE_REQUEST)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processed"
        referral_id = data["referral_id"]
        assert referral_id  # non-empty UUID string

        # Verify Referral was written to DB with correct fields.
        # db_session.get() needs a native uuid.UUID, not the JSON string.
        referral = db_session.get(Referral, uuid.UUID(referral_id))
        assert referral is not None
        assert referral.fhir_service_request_id == "sr-hapi-001"
        assert referral.fhir_server == webhooks_module.HAPI_FHIR_BASE_URL
        assert referral.patient_id == "p-123"
        assert referral.patient_display == "Jane Doe"
        assert referral.requester_display == "Dr. Smith"
        assert referral.performer_display == "Dr. Jones"
        assert referral.priority == "routine"
        assert referral.note == "Urgent cardiology follow-up needed"
        assert referral.pipeline_type == "incoming"
        assert referral.source == "fhir_sync"
        assert referral.status == "active"

        # Verify the initial StageTransition audit entry exists.
        transitions = db_session.execute(
            select(StageTransition).where(
                StageTransition.referral_id == referral.id
            )
        ).scalars().all()
        assert len(transitions) == 1
        assert transitions[0].from_stage_id is None
        assert transitions[0].actor == "fhir_webhook"
        assert transitions[0].outcome == "advanced"

    def test_new_service_request_lands_in_first_stage(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Referral created by webhook should be in the first non-terminal incoming stage."""
        resp = client.post("/api/webhooks/hapi", json=VALID_SERVICE_REQUEST)
        referral_id = resp.json()["referral_id"]

        referral = db_session.get(Referral, uuid.UUID(referral_id))
        assert referral is not None

        # Look up the expected first stage.
        first_stage = db_session.execute(
            select(PipelineStage)
            .where(PipelineStage.pipeline_type == "incoming")
            .where(PipelineStage.is_terminal.is_(False))
            .order_by(PipelineStage.sort_order)
            .limit(1)
        ).scalar_one()

        assert referral.current_stage_id == first_stage.id

    def test_duplicate_service_request_updates_not_duplicates(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Sending the same FHIR ID twice should update the row, not create a second."""
        # First call creates the referral.
        resp1 = client.post("/api/webhooks/hapi", json=VALID_SERVICE_REQUEST)
        assert resp1.json()["status"] == "processed"

        # Second call with updated fields should update.
        updated_payload = {**VALID_SERVICE_REQUEST, "priority": "urgent"}
        resp2 = client.post("/api/webhooks/hapi", json=updated_payload)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "updated"
        # Same referral ID returned.
        assert resp2.json()["referral_id"] == resp1.json()["referral_id"]

        # Only one Referral row should exist.
        count = db_session.execute(
            select(Referral).where(
                Referral.fhir_service_request_id == "sr-hapi-001"
            )
        ).scalars().all()
        assert len(count) == 1

        # The priority field should have been updated.
        referral = count[0]
        assert referral.priority == "urgent"

        # Still only the original StageTransition (no second one created).
        transitions = db_session.execute(
            select(StageTransition).where(
                StageTransition.referral_id == referral.id
            )
        ).scalars().all()
        assert len(transitions) == 1

    def test_malformed_json_body_returns_skipped(
        self, client: TestClient
    ) -> None:
        """Non-JSON body should return 200 with status=skipped, not crash."""
        resp = client.post(
            "/api/webhooks/hapi",
            content=b"not json at all!!!",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped"

    def test_non_service_request_resource_type_returns_skipped(
        self, client: TestClient
    ) -> None:
        """HAPI may send ping/handshake payloads — we should silently ignore them."""
        ping_payload = {"resourceType": "Bundle", "id": "ping-001"}
        resp = client.post("/api/webhooks/hapi", json=ping_payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped"

    def test_service_request_without_id_returns_skipped(
        self, client: TestClient
    ) -> None:
        """A ServiceRequest missing the 'id' field should be gracefully skipped."""
        minimal = {"resourceType": "ServiceRequest", "status": "active"}
        resp = client.post("/api/webhooks/hapi", json=minimal)
        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped"

    def test_minimal_service_request_does_not_crash(
        self, client: TestClient, db_session: Session
    ) -> None:
        """A ServiceRequest with only the required id field should succeed."""
        minimal = {"resourceType": "ServiceRequest", "id": "sr-minimal-999"}
        resp = client.post("/api/webhooks/hapi", json=minimal)
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"

        # A referral row should exist with all optional fields null.
        referral = db_session.execute(
            select(Referral).where(
                Referral.fhir_service_request_id == "sr-minimal-999"
            )
        ).scalar_one()
        assert referral.patient_display is None
        assert referral.note is None
        assert referral.priority is None


# ---------------------------------------------------------------------------
# Subscription management tests
# ---------------------------------------------------------------------------


class TestSubscribe:
    def test_subscribe_stores_subscription_id(self, client: TestClient) -> None:
        """POST /subscribe should call HAPI and store the returned subscription ID."""
        # Mock httpx.AsyncClient so we don't make real network calls.
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "resourceType": "Subscription",
            "id": "sub-hapi-42",
            "status": "active",
        }
        mock_response.raise_for_status = MagicMock()  # no-op

        with patch("app.routers.webhooks.httpx.AsyncClient") as mock_client_cls:
            # httpx.AsyncClient is used as an async context manager.
            mock_async_ctx = AsyncMock()
            mock_async_ctx.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            mock_client_cls.return_value = mock_async_ctx

            resp = client.post("/api/webhooks/subscribe")

        assert resp.status_code == 200
        data = resp.json()
        assert data["subscription_id"] == "sub-hapi-42"
        assert data["status"] == "active"

        # Module state should be updated.
        assert webhooks_module._subscription_state["subscription_id"] == "sub-hapi-42"

    def test_subscribe_uses_webhook_base_url_setting(
        self, client: TestClient
    ) -> None:
        """The HAPI Subscription endpoint value should contain the configured base URL."""
        captured_body: dict[str, Any] = {}

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "sub-999"}
        mock_response.raise_for_status = MagicMock()

        async def _capture_post(url, json, headers):  # type: ignore[no-untyped-def]
            captured_body.update(json)
            return mock_response

        with patch("app.routers.webhooks.httpx.AsyncClient") as mock_client_cls:
            mock_async_ctx = AsyncMock()
            mock_async_ctx.__aenter__.return_value.post = _capture_post
            mock_client_cls.return_value = mock_async_ctx

            client.post("/api/webhooks/subscribe")

        # The channel endpoint should contain our webhook path.
        channel_endpoint: str = captured_body["channel"]["endpoint"]
        assert channel_endpoint.endswith("/api/webhooks/hapi")


class TestStatus:
    def test_status_inactive_by_default(self, client: TestClient) -> None:
        """Status endpoint should report inactive when no subscription is registered."""
        resp = client.get("/api/webhooks/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False
        assert data["subscription_id"] is None
        assert data["fhir_server"] == webhooks_module.HAPI_FHIR_BASE_URL

    def test_status_active_after_subscribe(self, client: TestClient) -> None:
        """Status endpoint should report active once a subscription ID is stored."""
        # Directly inject state rather than going through the full subscribe flow.
        webhooks_module._subscription_state["subscription_id"] = "sub-direct-99"

        resp = client.get("/api/webhooks/status")
        data = resp.json()
        assert data["active"] is True
        assert data["subscription_id"] == "sub-direct-99"


class TestUnsubscribe:
    def test_unsubscribe_clears_state(self, client: TestClient) -> None:
        """DELETE /subscribe should call HAPI DELETE and clear module state."""
        # Pre-seed state as if subscribe was already called.
        webhooks_module._subscription_state["subscription_id"] = "sub-to-delete"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("app.routers.webhooks.httpx.AsyncClient") as mock_client_cls:
            mock_async_ctx = AsyncMock()
            mock_async_ctx.__aenter__.return_value.delete = AsyncMock(
                return_value=mock_response
            )
            mock_client_cls.return_value = mock_async_ctx

            resp = client.delete("/api/webhooks/subscribe")

        assert resp.status_code == 204
        assert webhooks_module._subscription_state["subscription_id"] is None

    def test_unsubscribe_without_active_subscription_returns_404(
        self, client: TestClient
    ) -> None:
        """Attempting to delete when no subscription is active should return 404."""
        resp = client.delete("/api/webhooks/subscribe")
        assert resp.status_code == 404
