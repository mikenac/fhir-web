"""Tests for the referral dashboard endpoint."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_operational_service


def _make_fhir_bundle(entries):
    """Create a FHIR Bundle response dict from a list of resource dicts."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": e} for e in entries],
    }


def _make_service_request_dict(
    sr_id="sr-1",
    status="active",
    intent="order",
    patient_id="p-1",
    patient_display="John Doe",
    code_display="Cardiology Referral",
    priority="routine",
    authored_on=None,
    requester_display="Dr. Smith",
    performer_display="Heart Center",
    note_text="Follow up in 2 weeks",
    category_display="Patient referral",
):
    """Create a raw FHIR ServiceRequest resource dict."""
    resource = {
        "resourceType": "ServiceRequest",
        "id": sr_id,
        "status": status,
        "intent": intent,
        "subject": {
            "reference": f"Patient/{patient_id}",
            "display": patient_display,
        },
        "code": {
            "coding": [{"display": code_display}],
        },
    }

    if priority:
        resource["priority"] = priority
    if authored_on:
        resource["authoredOn"] = authored_on
    if requester_display:
        resource["requester"] = {"display": requester_display}
    if performer_display:
        resource["performer"] = [{"display": performer_display}]
    if note_text:
        resource["note"] = [{"text": note_text}]
    if category_display:
        resource["category"] = [{"coding": [{"display": category_display}]}]

    return resource


def _mock_service_with_bundle(bundle_dict):
    """Create a mock OperationalService where client.client.get returns a bundle."""
    # Mock the httpx response
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = bundle_dict

    # Mock the httpx client (service.client.client)
    mock_http_client = MagicMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)

    # Mock the FHIRClient (service.client)
    mock_fhir_client = MagicMock()
    mock_fhir_client.client = mock_http_client

    # Mock the OperationalService
    service = MagicMock()
    service.client = mock_fhir_client

    return service


class TestReferralDashboardEndpoint:
    """Tests for GET /api/operational/referrals/dashboard"""

    def test_returns_referrals_with_status_counts(self):
        """Dashboard returns referral summaries and status counts."""
        entries = [
            _make_service_request_dict(sr_id="sr-1", status="active", patient_id="p-1"),
            _make_service_request_dict(sr_id="sr-2", status="active", patient_id="p-2"),
            _make_service_request_dict(sr_id="sr-3", status="completed", patient_id="p-3"),
        ]
        bundle = _make_fhir_bundle(entries)
        service = _mock_service_with_bundle(bundle)
        app.dependency_overrides[get_operational_service] = lambda: service

        client = TestClient(app)
        response = client.get("/api/operational/referrals/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["results"]) == 3
        assert data["status_counts"] == {"active": 2, "completed": 1}

        # Verify first result shape
        r = data["results"][0]
        assert r["id"] == "sr-1"
        assert r["patient_id"] == "p-1"
        assert r["patient_display"] == "John Doe"
        assert r["status"] == "active"
        assert r["code_display"] == "Cardiology Referral"
        assert r["priority"] == "routine"
        assert r["requester_display"] == "Dr. Smith"
        assert r["performer_display"] == "Heart Center"
        assert r["note"] == "Follow up in 2 weeks"

        app.dependency_overrides.clear()

    def test_empty_results(self):
        """Dashboard returns empty response when no referrals exist."""
        bundle = _make_fhir_bundle([])
        service = _mock_service_with_bundle(bundle)
        app.dependency_overrides[get_operational_service] = lambda: service

        client = TestClient(app)
        response = client.get("/api/operational/referrals/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["results"] == []
        assert data["status_counts"] == {}

        app.dependency_overrides.clear()

    def test_status_filter_passed_to_fhir(self):
        """Status filter is passed through to the FHIR search params."""
        bundle = _make_fhir_bundle([])
        service = _mock_service_with_bundle(bundle)
        app.dependency_overrides[get_operational_service] = lambda: service

        client = TestClient(app)
        response = client.get("/api/operational/referrals/dashboard?status=completed")

        assert response.status_code == 200
        # Verify the raw HTTP get was called with status param
        call_args = service.client.client.get.call_args
        params = call_args[1]["params"]  # kwargs
        assert params["status"] == "completed"

        app.dependency_overrides.clear()

    def test_patient_id_filter(self):
        """Patient ID filter is passed as FHIR 'patient' param."""
        bundle = _make_fhir_bundle([])
        service = _mock_service_with_bundle(bundle)
        app.dependency_overrides[get_operational_service] = lambda: service

        client = TestClient(app)
        response = client.get("/api/operational/referrals/dashboard?patient_id=p-123")

        assert response.status_code == 200
        call_args = service.client.client.get.call_args
        params = call_args[1]["params"]
        assert params["patient"] == "p-123"

        app.dependency_overrides.clear()

    def test_date_range_filters(self):
        """Date range filters are passed as FHIR 'date' params."""
        bundle = _make_fhir_bundle([])
        service = _mock_service_with_bundle(bundle)
        app.dependency_overrides[get_operational_service] = lambda: service

        client = TestClient(app)
        response = client.get(
            "/api/operational/referrals/dashboard?authored_after=2024-01-01&authored_before=2024-12-31"
        )

        assert response.status_code == 200
        call_args = service.client.client.get.call_args
        params = call_args[1]["params"]
        assert "date" in params

        app.dependency_overrides.clear()

    def test_count_param(self):
        """The _count param controls max results."""
        bundle = _make_fhir_bundle([])
        service = _mock_service_with_bundle(bundle)
        app.dependency_overrides[get_operational_service] = lambda: service

        client = TestClient(app)
        response = client.get("/api/operational/referrals/dashboard?_count=25")

        assert response.status_code == 200
        call_args = service.client.client.get.call_args
        params = call_args[1]["params"]
        assert params["_count"] == "25"

        app.dependency_overrides.clear()

    def test_handles_missing_optional_fields(self):
        """Dashboard handles ServiceRequests with missing optional fields."""
        minimal = {
            "resourceType": "ServiceRequest",
            "id": "sr-minimal",
            "status": "draft",
            "intent": "proposal",
            "subject": {"reference": "Patient/p-5"},
        }
        bundle = _make_fhir_bundle([minimal])
        service = _mock_service_with_bundle(bundle)
        app.dependency_overrides[get_operational_service] = lambda: service

        client = TestClient(app)
        response = client.get("/api/operational/referrals/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        r = data["results"][0]
        assert r["id"] == "sr-minimal"
        assert r["patient_id"] == "p-5"
        assert r["patient_display"] is None
        assert r["code_display"] == ""
        assert r["priority"] is None
        assert r["requester_display"] is None
        assert r["performer_display"] is None
        assert r["note"] is None

        app.dependency_overrides.clear()

    def test_fhir_server_error_returns_empty(self):
        """When the FHIR server returns 400/403, the dashboard returns empty results."""
        service = MagicMock()
        mock_http_client = MagicMock()
        mock_http_client.get = AsyncMock(side_effect=Exception("HTTP 403 Forbidden"))
        service.client = MagicMock()
        service.client.client = mock_http_client
        app.dependency_overrides[get_operational_service] = lambda: service

        client = TestClient(app)
        response = client.get("/api/operational/referrals/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["results"] == []

        app.dependency_overrides.clear()
