"""Webhook router for HAPI FHIR rest-hook subscriptions.

This module handles two concerns:
  1. Receiving inbound webhook POSTs/PUTs from HAPI FHIR when a ServiceRequest changes.
  2. Managing the FHIR Subscription resource on HAPI (create / delete / status).

MVP scope: HAPI FHIR only, rest-hook channel, ServiceRequest resources only.

HAPI delivery modes
-------------------
HAPI FHIR (R4) delivers rest-hook notifications in two ways depending on version:
  - POST /api/webhooks/hapi          — full resource in body (older behaviour)
  - PUT  /api/webhooks/hapi/ServiceRequest/{id} — full resource in body (newer default)

Both routes delegate to _process_service_request() so the upsert logic lives in
one place.
"""

import logging
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import PipelineStage, Referral, StageTransition
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Module-level subscription state
# Stores the HAPI Subscription ID and the FHIR server URL after a successful
# POST /subscribe call.
#
# A plain dict is used instead of a DB table — this is an MVP and the data
# is ephemeral (resets on server restart).
# ---------------------------------------------------------------------------
_subscription_state: dict[str, str | None] = {
    "subscription_id": None,
    # The FHIR server URL this subscription was registered against.
    # Stored here so that status/unsubscribe talk to the same server
    # that subscribe used, even if settings change between calls.
    "fhir_url": None,
}


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
# Shared upsert helper — called by both POST and PUT routes
# ---------------------------------------------------------------------------


def _process_service_request(
    body: dict[str, Any],
    db: Session,
    fhir_server_url: str,
) -> dict[str, str]:
    """Parse a ServiceRequest dict and upsert it into the Referral table.

    This function contains the core upsert logic so it can be shared between the
    legacy POST route and the newer PUT route that HAPI uses by default.

    Args:
        body:            The raw JSON dict from the incoming HAPI request body.
        db:              The active SQLAlchemy database session.
        fhir_server_url: The FHIR server base URL this notification came from.
                         Used as part of the upsert key (fhir_service_request_id,
                         fhir_server) to prevent cross-server collisions.

    Returns:
        A dict with keys "status" and "referral_id":
          {"status": "processed", "referral_id": "<uuid>"}  — new record created
          {"status": "updated",   "referral_id": "<uuid>"}  — existing record updated
          {"status": "skipped",   "referral_id": ""}        — body missing or wrong type
    """
    # Confirm this is a ServiceRequest; HAPI can also send ping/handshake payloads.
    resource_type: str = body.get("resourceType", "")
    if resource_type != "ServiceRequest":
        logger.info(
            "webhook: ignoring resourceType=%s (expected ServiceRequest)", resource_type
        )
        return {"status": "skipped", "referral_id": ""}

    # Extract the flat fields we want to persist.
    fields = _extract_fields_from_service_request(body)
    fhir_id: str | None = fields.get("fhir_service_request_id")

    if not fhir_id:
        logger.warning("webhook: ServiceRequest has no 'id' field, skipping")
        return {"status": "skipped", "referral_id": ""}

    # --- Upsert logic ---
    # Look up an existing Referral by the unique constraint (fhir_service_request_id, fhir_server).
    # Including fhir_server_url in the lookup prevents collisions when the same
    # FHIR ID appears on two different servers.
    existing = db.execute(
        select(Referral).where(
            Referral.fhir_service_request_id == fhir_id,
            Referral.fhir_server == fhir_server_url,
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
    # "Incoming" is the correct direction for referrals arriving via webhook from HAPI.
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

    # Build the new Referral row from the extracted field dict.
    referral = Referral(
        pipeline_type="incoming",
        current_stage_id=first_stage.id,
        fhir_service_request_id=fhir_id,
        # Store which FHIR server this referral came from so we can route
        # follow-up queries (e.g., fetch full resource) to the right server.
        fhir_server=fhir_server_url,
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
    # flush() assigns referral.id so we can reference it in the StageTransition FK.
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
# Webhook receivers — POST (legacy) and PUT (HAPI default)
# ---------------------------------------------------------------------------


@router.post("/hapi", status_code=status.HTTP_200_OK)
async def receive_hapi_webhook(
    request: Request,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Receive a FHIR rest-hook notification from HAPI via POST.

    Some HAPI versions POST the full ServiceRequest JSON body to the bare
    endpoint URL.  This route exists for backward-compat and testing.

    Returns:
        {"status": "processed", "referral_id": "..."} for a new record
        {"status": "updated",   "referral_id": "..."} for an existing record
        {"status": "skipped",   "referral_id": ""} if the body is missing/wrong type
    """
    # We use request.json() rather than a Pydantic body param so we can tolerate
    # any quirky HAPI payload without strict validation.
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        # Malformed JSON — return 200 so HAPI doesn't retry endlessly.
        logger.warning("webhook POST: received non-JSON body, skipping")
        return {"status": "skipped", "referral_id": ""}

    # Pass the configured FHIR server URL so it is stored on the Referral row.
    return _process_service_request(body, db, settings.webhook_fhir_url)


@router.put("/hapi/{resource_type}/{resource_id}", status_code=status.HTTP_200_OK)
async def receive_hapi_webhook_put(
    resource_type: str,
    resource_id: str,
    request: Request,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Receive a FHIR rest-hook notification from HAPI via PUT.

    HAPI (R4, newer versions) delivers notifications as:
        PUT {endpoint}/ServiceRequest/{id}
    with the full FHIR resource JSON in the body.

    Our subscription registers the endpoint as:
        {webhook_base_url}/api/webhooks/hapi
    and HAPI automatically appends /ServiceRequest/{id}, so the full path
    becomes:
        PUT /api/webhooks/hapi/ServiceRequest/{id}

    Path parameters:
        resource_type: FHIR resource type from the URL (e.g. "ServiceRequest").
        resource_id:   FHIR resource ID from the URL (e.g. "sr-hapi-001").

    Returns:
        {"status": "processed", "referral_id": "..."} — new record created
        {"status": "updated",   "referral_id": "..."} — existing record updated
        {"status": "skipped",   "referral_id": ""}    — non-ServiceRequest type or bad body

    NOTE: We always return HTTP 200, even for skipped payloads, because a
    non-200 response causes HAPI to retry the delivery indefinitely.
    """
    # Only handle ServiceRequest resources; skip anything else (e.g. Observation).
    if resource_type != "ServiceRequest":
        logger.info(
            "webhook PUT: ignoring resource_type=%s id=%s (expected ServiceRequest)",
            resource_type,
            resource_id,
        )
        return {"status": "skipped", "referral_id": ""}

    # Parse the request body the same way as the POST handler.
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        # Malformed JSON — return 200 so HAPI doesn't retry endlessly.
        logger.warning(
            "webhook PUT: received non-JSON body for %s/%s, skipping",
            resource_type,
            resource_id,
        )
        return {"status": "skipped", "referral_id": ""}

    # Delegate to the shared upsert helper, passing the configured FHIR server URL.
    return _process_service_request(body, db, settings.webhook_fhir_url)


# ---------------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------------


@router.post("/subscribe", status_code=status.HTTP_200_OK)
async def subscribe(
    # Optional query parameter so the caller can override the FHIR server for
    # this subscription (e.g., a local HAPI Docker instance during development).
    # If omitted, settings.webhook_fhir_url is used.
    fhir_url: str | None = Query(
        None,
        description="Override FHIR server URL for this subscription",
    ),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Register a FHIR rest-hook Subscription on HAPI for ServiceRequest changes.

    POSTs a Subscription resource to HAPI asking it to call our webhook
    endpoint whenever any ServiceRequest is created or modified.

    The resulting HAPI Subscription ID and the target FHIR URL are stored in
    module-level state so the DELETE/status endpoints can use the same server.

    Query parameters:
        fhir_url: Optional override for the FHIR server base URL. When provided,
                  this takes priority over the webhook_fhir_url setting.

    Returns:
        {"subscription_id": "...", "status": "active"}

    Raises:
        HTTPException 502 if HAPI rejects the subscription request.
    """
    # Determine the actual FHIR server URL to target.
    # The caller can pass ?fhir_url=... to point at a different server (e.g.,
    # a local HAPI Docker instance) without changing the persistent config.
    effective_fhir_url = fhir_url or settings.webhook_fhir_url

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

    # POST to the configured FHIR server's Subscription endpoint.
    hapi_url = f"{effective_fhir_url}/Subscription"

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

    # Persist both the subscription ID and the FHIR URL in module state.
    # The URL is stored so that unsubscribe/status always talk to the same
    # server that was used when subscribe was called.
    _subscription_state["subscription_id"] = subscription_id
    _subscription_state["fhir_url"] = effective_fhir_url

    logger.info(
        "subscribe: registered HAPI subscription id=%s on %s",
        subscription_id,
        effective_fhir_url,
    )
    return {"subscription_id": subscription_id, "status": "active"}


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    settings: Settings = Depends(get_settings),
) -> None:
    """Delete the active FHIR Subscription from HAPI.

    Sends a DELETE request to HAPI for the previously registered Subscription
    resource, then clears the local state.

    Uses the FHIR URL that was active when subscribe was called (stored in
    _subscription_state["fhir_url"]), falling back to settings.webhook_fhir_url
    if the state entry is missing (e.g., after a server restart).

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

    # Use the URL stored when the subscription was created so we don't accidentally
    # try to delete from a different server if settings were changed between calls.
    fhir_url = _subscription_state.get("fhir_url") or settings.webhook_fhir_url
    delete_url = f"{fhir_url}/Subscription/{subscription_id}"

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

    # Clear both the subscription ID and the stored FHIR URL.
    _subscription_state["subscription_id"] = None
    _subscription_state["fhir_url"] = None
    logger.info("unsubscribe: deleted HAPI subscription id=%s", subscription_id)


@router.get("/status", status_code=status.HTTP_200_OK)
async def subscription_status(
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Return the current webhook subscription state.

    The fhir_server field reflects whichever URL is actually in use:
      - If a subscription is active, it returns the URL stored when subscribe was called.
      - If no subscription is active, it falls back to settings.webhook_fhir_url.

    Returns:
        {
            "active": bool,
            "subscription_id": str | null,
            "fhir_server": str   # the FHIR server URL being targeted
        }
    """
    sub_id = _subscription_state.get("subscription_id")
    # Return the URL the active subscription is registered against, or the
    # configured default if no subscription exists yet.
    fhir_server = _subscription_state.get("fhir_url") or settings.webhook_fhir_url
    return {
        "active": sub_id is not None,
        "subscription_id": sub_id,
        "fhir_server": fhir_server,
    }
