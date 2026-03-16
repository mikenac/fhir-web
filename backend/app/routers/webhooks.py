"""Webhook router for HAPI FHIR rest-hook subscriptions.

This module handles two concerns:
  1. Receiving inbound webhook POSTs from HAPI FHIR when a ServiceRequest changes.
  2. Managing the FHIR Subscription resource on HAPI (create / delete / status).

MVP scope: HAPI FHIR only, rest-hook channel, ServiceRequest resources only.
"""

import logging
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import PipelineStage, Referral, StageTransition
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Module-level subscription state
# Stores the HAPI Subscription ID after a successful POST /subscribe call.
# A plain dict is used instead of a DB table — this is an MVP and the data
# is ephemeral (resets on server restart).
# ---------------------------------------------------------------------------
_subscription_state: dict[str, str | None] = {
    "subscription_id": None,
}

# The HAPI FHIR base URL we sync from.
HAPI_FHIR_BASE_URL = "https://hapi.fhir.org/baseR4"


# ---------------------------------------------------------------------------
# Field extraction helper
# ---------------------------------------------------------------------------


def _extract_fields_from_service_request(resource: dict[str, Any]) -> dict[str, Any]:
    """Extract the fields we care about from a raw FHIR ServiceRequest dict.

    This mirrors the _raw_dict_to_referral_summary pattern in operational.py:
    we do NOT call model_validate because HAPI resources can be malformed
    (e.g., missing required fields like 'intent').  We use .get() with safe
    defaults throughout.

    Args:
        resource: Raw dict parsed from the HAPI webhook JSON body.

    Returns:
        A flat dict of fields ready to be applied to a Referral ORM row.
    """
    # --- subject / patient ---
    subject = resource.get("subject") or {}
    subject_ref: str = subject.get("reference", "")
    # Reference format is typically "Patient/abc123" — grab the last segment
    patient_id = subject_ref.split("/")[-1] if subject_ref else None
    patient_display: str | None = subject.get("display")

    # --- requester ---
    requester = resource.get("requester") or {}
    requester_display: str | None = requester.get("display")

    # --- performer (first entry only) ---
    performers: list[dict] = resource.get("performer") or []
    performer_display: str | None = performers[0].get("display") if performers else None

    # --- note (first entry only) ---
    notes: list[dict] = resource.get("note") or []
    note: str | None = notes[0].get("text") if notes else None

    # --- category display (first coding of first category) ---
    category_display: str | None = None
    categories: list[dict] = resource.get("category") or []
    if categories:
        codings: list[dict] = categories[0].get("coding") or []
        if codings:
            category_display = codings[0].get("display")

    # --- specialty / code display ---
    code = resource.get("code") or {}
    code_codings: list[dict] = code.get("coding") or []
    specialty_display: str | None = code_codings[0].get("display") if code_codings else None

    # --- authored date ---
    # FHIR sends this as an ISO 8601 string (e.g. "2026-03-01T10:00:00Z").
    # SQLAlchemy's DateTime column requires a Python datetime object, so we
    # parse it here.  fromisoformat() handles most ISO 8601 variants in
    # Python 3.11+; the trailing "Z" is replaced with "+00:00" for compat.
    authored_on_raw: str | None = resource.get("authoredOn")
    authored_on: datetime | None = None
    if authored_on_raw:
        try:
            authored_on = datetime.fromisoformat(
                authored_on_raw.replace("Z", "+00:00")
            )
        except ValueError:
            # Non-parseable date string — store None rather than crashing.
            pass

    return {
        "fhir_service_request_id": resource.get("id"),
        "fhir_status": resource.get("status"),
        "patient_id": patient_id,
        "patient_display": patient_display,
        "requester_display": requester_display,
        "performer_display": performer_display,
        "note": note,
        "category_display": category_display,
        "specialty_display": specialty_display,
        "priority": resource.get("priority"),
        "intent": resource.get("intent"),
        "authored_on": authored_on,  # datetime | None
    }


# ---------------------------------------------------------------------------
# Webhook receiver
# ---------------------------------------------------------------------------


@router.post("/hapi", status_code=status.HTTP_200_OK)
async def receive_hapi_webhook(
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict[str, str]:
    """Receive a FHIR rest-hook notification from HAPI.

    HAPI POSTs the full ServiceRequest JSON body to this endpoint whenever a
    ServiceRequest is created or updated.  We parse the payload, then either
    create a new Referral (if this FHIR resource hasn't been seen before) or
    update the existing one.

    Returns:
        {"status": "processed", "referral_id": "..."} for a new record
        {"status": "updated",   "referral_id": "..."} for an existing record
        {"status": "skipped",   "referral_id": ""} if the body is missing/wrong type
    """
    # --- Parse body ---
    # We use request.json() rather than a Pydantic body parameter so we can
    # tolerate any quirky HAPI payload without strict validation.
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        # Malformed JSON — log and return a safe 200 so HAPI doesn't retry forever.
        logger.warning("webhook: received non-JSON body, skipping")
        return {"status": "skipped", "referral_id": ""}

    # Confirm this is a ServiceRequest; HAPI can also send ping/handshake payloads.
    resource_type: str = body.get("resourceType", "")
    if resource_type != "ServiceRequest":
        logger.info(
            "webhook: ignoring resourceType=%s (expected ServiceRequest)", resource_type
        )
        return {"status": "skipped", "referral_id": ""}

    # --- Extract fields ---
    fields = _extract_fields_from_service_request(body)
    fhir_id: str | None = fields.get("fhir_service_request_id")

    if not fhir_id:
        logger.warning("webhook: ServiceRequest has no 'id' field, skipping")
        return {"status": "skipped", "referral_id": ""}

    # --- Upsert logic ---
    # Look up an existing Referral by the unique constraint (fhir_service_request_id, fhir_server).
    existing = db.execute(
        select(Referral).where(
            Referral.fhir_service_request_id == fhir_id,
            Referral.fhir_server == HAPI_FHIR_BASE_URL,
        )
    ).scalar_one_or_none()

    if existing:
        # --- UPDATE path ---
        # Refresh only the mutable clinical fields; do not touch pipeline state.
        existing.fhir_status = fields.get("fhir_status")
        existing.patient_display = fields.get("patient_display")
        existing.requester_display = fields.get("requester_display")
        existing.performer_display = fields.get("performer_display")
        existing.priority = fields.get("priority")
        existing.note = fields.get("note")
        db.commit()

        logger.info(
            "webhook: updated referral id=%s fhir_id=%s", existing.id, fhir_id
        )
        return {"status": "updated", "referral_id": str(existing.id)}

    # --- CREATE path ---
    # Find the first non-terminal stage for the incoming pipeline.
    # Incoming is the correct direction for referrals arriving via webhook from HAPI.
    first_stage = db.execute(
        select(PipelineStage)
        .where(PipelineStage.pipeline_type == "incoming")
        .where(PipelineStage.is_terminal.is_(False))
        .where(PipelineStage.is_active.is_(True))
        .order_by(PipelineStage.sort_order)
        .limit(1)
    ).scalar_one_or_none()

    if not first_stage:
        # This is a configuration error — raise 500 so the operator knows.
        logger.error("webhook: no active incoming pipeline stages found")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No active stages configured for incoming pipeline",
        )

    # Build the new Referral row from extracted fields.
    referral = Referral(
        pipeline_type="incoming",
        current_stage_id=first_stage.id,
        fhir_service_request_id=fhir_id,
        fhir_server=HAPI_FHIR_BASE_URL,
        fhir_status=fields.get("fhir_status"),
        patient_id=fields.get("patient_id"),
        patient_display=fields.get("patient_display"),
        requester_display=fields.get("requester_display"),
        performer_display=fields.get("performer_display"),
        specialty_display=fields.get("specialty_display"),
        priority=fields.get("priority"),
        intent=fields.get("intent"),
        authored_on=fields.get("authored_on"),
        note=fields.get("note"),
        category_display=fields.get("category_display"),
        source="fhir_sync",
    )
    db.add(referral)
    # flush assigns referral.id before the StageTransition FK is set
    db.flush()

    # Create the initial audit-trail entry (entry into pipeline — no from_stage).
    transition = StageTransition(
        referral_id=referral.id,
        from_stage_id=None,
        to_stage_id=first_stage.id,
        outcome="advanced",
        pipeline_type="incoming",
        actor="fhir_webhook",
    )
    db.add(transition)
    db.commit()

    logger.info(
        "webhook: created referral id=%s fhir_id=%s", referral.id, fhir_id
    )
    return {"status": "processed", "referral_id": str(referral.id)}


# ---------------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------------


@router.post("/subscribe", status_code=status.HTTP_200_OK)
async def subscribe(
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Register a FHIR rest-hook Subscription on HAPI for ServiceRequest changes.

    POSTs a Subscription resource to HAPI asking it to call our webhook
    endpoint whenever any ServiceRequest is created or modified.

    The resulting HAPI Subscription ID is stored in module-level state so
    the DELETE endpoint can tear it down later.

    Returns:
        {"subscription_id": "...", "status": "active"}

    Raises:
        HTTPException 502 if HAPI rejects the subscription request.
    """
    # Build the callback URL from settings so Render / ngrok URLs work in prod.
    endpoint_url = f"{settings.webhook_base_url}/api/webhooks/hapi"

    subscription_resource: dict[str, Any] = {
        "resourceType": "Subscription",
        "status": "requested",
        "reason": "Monitor ServiceRequest changes for referral pipeline",
        "criteria": "ServiceRequest?",
        "channel": {
            "type": "rest-hook",
            "endpoint": endpoint_url,
            "payload": "application/fhir+json",
        },
    }

    hapi_url = f"{HAPI_FHIR_BASE_URL}/Subscription"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                hapi_url,
                json=subscription_resource,
                headers={"Content-Type": "application/fhir+json"},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "subscribe: HAPI returned %s — %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"HAPI rejected subscription: {exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            logger.error("subscribe: could not reach HAPI — %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not connect to HAPI FHIR server",
            ) from exc

    created: dict[str, Any] = response.json()
    subscription_id: str = created.get("id", "")

    # Persist ID in module state for later teardown.
    _subscription_state["subscription_id"] = subscription_id

    logger.info("subscribe: registered HAPI subscription id=%s", subscription_id)
    return {"subscription_id": subscription_id, "status": "active"}


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe() -> None:
    """Delete the active FHIR Subscription from HAPI.

    Sends a DELETE request to HAPI for the previously registered Subscription
    resource, then clears the local state.

    Raises:
        HTTPException 404 if no subscription is currently active.
        HTTPException 502 if HAPI rejects the DELETE.
    """
    subscription_id = _subscription_state.get("subscription_id")

    if not subscription_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription to delete",
        )

    delete_url = f"{HAPI_FHIR_BASE_URL}/Subscription/{subscription_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.delete(delete_url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "unsubscribe: HAPI returned %s — %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"HAPI rejected delete: {exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            logger.error("unsubscribe: could not reach HAPI — %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not connect to HAPI FHIR server",
            ) from exc

    # Clear local state regardless of HAPI's response body.
    _subscription_state["subscription_id"] = None
    logger.info("unsubscribe: deleted HAPI subscription id=%s", subscription_id)


@router.get("/status", status_code=status.HTTP_200_OK)
async def subscription_status() -> dict[str, Any]:
    """Return the current webhook subscription state.

    Returns:
        {
            "active": bool,
            "subscription_id": str | null,
            "fhir_server": "https://hapi.fhir.org/baseR4"
        }
    """
    sub_id = _subscription_state.get("subscription_id")
    return {
        "active": sub_id is not None,
        "subscription_id": sub_id,
        "fhir_server": HAPI_FHIR_BASE_URL,
    }
