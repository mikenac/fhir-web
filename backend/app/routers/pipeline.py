"""Referral pipeline API router.

Provides endpoints for managing referral pipeline stages, referrals,
stage transitions (workflow moves), and dashboard metrics.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import PipelineStage, Referral, StageTransition
from app.db.session import get_db_session
from app.models.pipeline import (
    PipelineBoardResponse,
    PipelineMetricsResponse,
    PipelineStageResponse,
    PipelineType,
    ReferralCreateRequest,
    ReferralHistoryResponse,
    ReferralListResponse,
    ReferralPriority,
    ReferralResponse,
    ReferralStatus,
    ReferralUpdateRequest,
    StageMetric,
    StageWithCountResponse,
    TransitionCreateRequest,
    TransitionResponse,
)

router = APIRouter()


# --- Helper functions ---


def _referral_to_response(referral: Referral) -> ReferralResponse:
    """Convert an ORM Referral (with current_stage loaded) to a response model."""
    return ReferralResponse(
        id=referral.id,
        pipeline_type=referral.pipeline_type,
        current_stage_id=referral.current_stage_id,
        current_stage_name=referral.current_stage.name,
        current_stage_display_name=referral.current_stage.display_name,
        fhir_service_request_id=referral.fhir_service_request_id,
        fhir_server=referral.fhir_server,
        fhir_status=referral.fhir_status,
        patient_id=referral.patient_id,
        patient_display=referral.patient_display,
        requester_display=referral.requester_display,
        performer_display=referral.performer_display,
        specialty_display=referral.specialty_display,
        priority=referral.priority,
        intent=referral.intent,
        authored_on=referral.authored_on,
        note=referral.note,
        category_display=referral.category_display,
        status=referral.status,
        appointment_scheduled_at=referral.appointment_scheduled_at,
        appointment_datetime=referral.appointment_datetime,
        source=referral.source,
        created_at=referral.created_at,
        updated_at=referral.updated_at,
    )


def _transition_to_response(t: StageTransition) -> TransitionResponse:
    """Convert an ORM StageTransition (with stages loaded) to a response model."""
    return TransitionResponse(
        id=t.id,
        referral_id=t.referral_id,
        from_stage_name=t.from_stage.name if t.from_stage else None,
        from_stage_display_name=t.from_stage.display_name if t.from_stage else None,
        to_stage_name=t.to_stage.name,
        to_stage_display_name=t.to_stage.display_name,
        outcome=t.outcome,
        actor=t.actor,
        reason=t.reason,
        duration_seconds=t.duration_seconds,
        transitioned_at=t.transitioned_at,
    )


# --- Pipeline Stages ---


@router.get(
    "/stages/{pipeline_type}",
    response_model=list[PipelineStageResponse],
)
def list_stages(
    pipeline_type: PipelineType,
    db: Session = Depends(get_db_session),
) -> list[PipelineStageResponse]:
    """Get all active stages for a pipeline type, ordered by sort_order."""
    stmt = (
        select(PipelineStage)
        .where(PipelineStage.pipeline_type == pipeline_type.value)
        .where(PipelineStage.is_active.is_(True))
        .order_by(PipelineStage.sort_order)
    )
    stages = db.execute(stmt).scalars().all()
    return [
        PipelineStageResponse(
            id=s.id,
            pipeline_type=s.pipeline_type,
            name=s.name,
            display_name=s.display_name,
            sort_order=s.sort_order,
            is_terminal=s.is_terminal,
            is_active=s.is_active,
        )
        for s in stages
    ]


@router.get(
    "/board/{pipeline_type}",
    response_model=PipelineBoardResponse,
)
def get_board(
    pipeline_type: PipelineType,
    db: Session = Depends(get_db_session),
) -> PipelineBoardResponse:
    """Get the Kanban board view — stages with active referral counts."""
    # Two-query approach: DuckDB requires all columns in GROUP BY,
    # so fetch stages first, then count referrals per stage separately.
    stage_stmt = (
        select(PipelineStage)
        .where(PipelineStage.pipeline_type == pipeline_type.value)
        .where(PipelineStage.is_active.is_(True))
        .order_by(PipelineStage.sort_order)
    )
    stage_rows = db.execute(stage_stmt).scalars().all()

    # Get active referral counts grouped by stage
    count_stmt = (
        select(
            Referral.current_stage_id,
            func.count(Referral.id).label("active_count"),
        )
        .where(Referral.status == "active")
        .where(Referral.current_stage_id.in_([s.id for s in stage_rows]))
        .group_by(Referral.current_stage_id)
    )
    count_map = {
        row.current_stage_id: row.active_count
        for row in db.execute(count_stmt).all()
    }

    stages = []
    total_active = 0
    for stage in stage_rows:
        count = count_map.get(stage.id, 0)
        stages.append(
            StageWithCountResponse(
                id=stage.id,
                pipeline_type=stage.pipeline_type,
                name=stage.name,
                display_name=stage.display_name,
                sort_order=stage.sort_order,
                is_terminal=stage.is_terminal,
                is_active=stage.is_active,
                active_referral_count=count,
            )
        )
        total_active += count

    return PipelineBoardResponse(
        pipeline_type=pipeline_type,
        stages=stages,
        total_active=total_active,
    )


# --- Referrals CRUD ---


@router.post(
    "/referrals",
    response_model=ReferralResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_referral(
    body: ReferralCreateRequest,
    db: Session = Depends(get_db_session),
) -> ReferralResponse:
    """Create a new referral, auto-assigning it to the first pipeline stage."""
    # Find the first non-terminal stage for the pipeline type
    first_stage = db.execute(
        select(PipelineStage)
        .where(PipelineStage.pipeline_type == body.pipeline_type.value)
        .where(PipelineStage.is_terminal.is_(False))
        .where(PipelineStage.is_active.is_(True))
        .order_by(PipelineStage.sort_order)
        .limit(1)
    ).scalar_one_or_none()

    if not first_stage:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No active stages found for pipeline type '{body.pipeline_type.value}'",
        )

    # Create the referral
    referral = Referral(
        pipeline_type=body.pipeline_type.value,
        current_stage_id=first_stage.id,
        patient_id=body.patient_id,
        patient_display=body.patient_display,
        requester_display=body.requester_display,
        performer_display=body.performer_display,
        requesting_org_id=body.requesting_org_id,
        performing_org_id=body.performing_org_id,
        specialty_display=body.specialty_display,
        priority=body.priority.value if body.priority else None,
        intent=body.intent,
        authored_on=body.authored_on,
        note=body.note,
        category_display=body.category_display,
        fhir_service_request_id=body.fhir_service_request_id,
        fhir_server=body.fhir_server,
        fhir_status=body.fhir_status,
        source=body.source.value,
    )
    db.add(referral)
    db.flush()

    # Create the initial transition (entry into pipeline)
    transition = StageTransition(
        referral_id=referral.id,
        from_stage_id=None,
        to_stage_id=first_stage.id,
        outcome="advanced",
        pipeline_type=body.pipeline_type.value,
        actor="system",
    )
    db.add(transition)
    db.commit()

    # Reload with relationship
    db.refresh(referral)
    referral.current_stage  # ensure loaded
    return _referral_to_response(referral)


@router.get(
    "/referrals/{referral_id}",
    response_model=ReferralResponse,
)
def get_referral(
    referral_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> ReferralResponse:
    """Get a single referral by ID."""
    referral = db.execute(
        select(Referral)
        .options(joinedload(Referral.current_stage))
        .where(Referral.id == referral_id)
    ).scalar_one_or_none()

    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Referral {referral_id} not found",
        )
    return _referral_to_response(referral)


@router.patch(
    "/referrals/{referral_id}",
    response_model=ReferralResponse,
)
def update_referral(
    referral_id: uuid.UUID,
    body: ReferralUpdateRequest,
    db: Session = Depends(get_db_session),
) -> ReferralResponse:
    """Update referral metadata. Stage moves must go through transitions."""
    referral = db.execute(
        select(Referral)
        .options(joinedload(Referral.current_stage))
        .where(Referral.id == referral_id)
    ).scalar_one_or_none()

    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Referral {referral_id} not found",
        )

    # Apply only the fields that were explicitly set
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        # Convert enums to their string values for the ORM
        if isinstance(value, (ReferralStatus, ReferralPriority)):
            value = value.value
        setattr(referral, field, value)

    db.commit()
    db.refresh(referral)
    return _referral_to_response(referral)


@router.get(
    "/referrals",
    response_model=ReferralListResponse,
)
def list_referrals(
    pipeline_type: PipelineType | None = None,
    stage_id: uuid.UUID | None = None,
    referral_status: ReferralStatus | None = Query(None, alias="status"),
    priority: ReferralPriority | None = None,
    patient_id: str | None = None,
    search: str | None = Query(None, description="Search patient, requester, or performer names"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_dir: str = Query("desc", description="Sort direction: asc or desc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db_session),
) -> ReferralListResponse:
    """List referrals with filtering, search, sorting, and pagination."""
    stmt = select(Referral).options(joinedload(Referral.current_stage))
    count_stmt = select(func.count(Referral.id))

    # Apply filters to both queries
    if pipeline_type is not None:
        stmt = stmt.where(Referral.pipeline_type == pipeline_type.value)
        count_stmt = count_stmt.where(Referral.pipeline_type == pipeline_type.value)
    if stage_id is not None:
        stmt = stmt.where(Referral.current_stage_id == stage_id)
        count_stmt = count_stmt.where(Referral.current_stage_id == stage_id)
    if referral_status is not None:
        stmt = stmt.where(Referral.status == referral_status.value)
        count_stmt = count_stmt.where(Referral.status == referral_status.value)
    if priority is not None:
        stmt = stmt.where(Referral.priority == priority.value)
        count_stmt = count_stmt.where(Referral.priority == priority.value)
    if patient_id is not None:
        stmt = stmt.where(Referral.patient_id == patient_id)
        count_stmt = count_stmt.where(Referral.patient_id == patient_id)
    if search:
        search_filter = or_(
            Referral.patient_display.ilike(f"%{search}%"),
            Referral.requester_display.ilike(f"%{search}%"),
            Referral.performer_display.ilike(f"%{search}%"),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    # Sorting
    sort_column = getattr(Referral, sort_by, Referral.created_at)
    if sort_dir.lower() == "asc":
        stmt = stmt.order_by(sort_column.asc())
    else:
        stmt = stmt.order_by(sort_column.desc())

    # Pagination
    stmt = stmt.offset(offset).limit(limit)

    total = db.execute(count_stmt).scalar() or 0
    referrals = db.execute(stmt).scalars().unique().all()

    return ReferralListResponse(
        total=total,
        results=[_referral_to_response(r) for r in referrals],
    )


# --- Stage Transitions ---


@router.post(
    "/referrals/{referral_id}/transitions",
    response_model=TransitionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transition(
    referral_id: uuid.UUID,
    body: TransitionCreateRequest,
    db: Session = Depends(get_db_session),
) -> TransitionResponse:
    """Move a referral to a new pipeline stage.

    Creates an audit trail entry and updates the referral's current stage.
    If the target stage is terminal, the referral status is auto-updated.
    """
    # Load referral with current stage
    referral = db.execute(
        select(Referral)
        .options(joinedload(Referral.current_stage))
        .where(Referral.id == referral_id)
    ).scalar_one_or_none()

    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Referral {referral_id} not found",
        )

    # Check if referral is already in a terminal stage
    if referral.current_stage.is_terminal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Referral is in terminal stage '{referral.current_stage.display_name}' and cannot be moved",
        )

    # Validate target stage
    target_stage = db.get(PipelineStage, body.to_stage_id)
    if not target_stage:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target stage {body.to_stage_id} not found",
        )
    if target_stage.pipeline_type != referral.pipeline_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target stage belongs to '{target_stage.pipeline_type}' pipeline, but referral is in '{referral.pipeline_type}'",
        )

    # Compute duration since last transition
    now = datetime.now(timezone.utc)
    last_transition = db.execute(
        select(StageTransition)
        .where(StageTransition.referral_id == referral_id)
        .order_by(StageTransition.transitioned_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    # Compare timestamps, ensuring both are tz-aware (SQLite may strip tzinfo)
    if last_transition:
        prev_time = last_transition.transitioned_at
        if prev_time.tzinfo is None:
            prev_time = prev_time.replace(tzinfo=timezone.utc)
        duration = int((now - prev_time).total_seconds())
    else:
        prev_time = referral.created_at
        if prev_time.tzinfo is None:
            prev_time = prev_time.replace(tzinfo=timezone.utc)
        duration = int((now - prev_time).total_seconds())

    # Create the transition
    transition = StageTransition(
        referral_id=referral.id,
        from_stage_id=referral.current_stage_id,
        to_stage_id=body.to_stage_id,
        outcome=body.outcome.value,
        actor=body.actor,
        reason=body.reason,
        duration_seconds=duration,
        pipeline_type=referral.pipeline_type,
        transitioned_at=now,
    )
    db.add(transition)

    # Update referral's current stage
    referral.current_stage_id = body.to_stage_id

    # Auto-set status if moving to terminal stage
    if target_stage.is_terminal:
        if target_stage.name == "completed":
            referral.status = "completed"
        elif target_stage.name == "cancelled":
            referral.status = "cancelled"

    db.commit()

    # Reload transition with relationships for response
    db.refresh(transition)
    transition.from_stage  # ensure loaded
    transition.to_stage  # ensure loaded
    return _transition_to_response(transition)


@router.get(
    "/referrals/{referral_id}/transitions",
    response_model=ReferralHistoryResponse,
)
def get_referral_history(
    referral_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> ReferralHistoryResponse:
    """Get the full transition history for a referral."""
    # Verify referral exists
    referral = db.get(Referral, referral_id)
    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Referral {referral_id} not found",
        )

    transitions = db.execute(
        select(StageTransition)
        .options(
            joinedload(StageTransition.from_stage),
            joinedload(StageTransition.to_stage),
        )
        .where(StageTransition.referral_id == referral_id)
        .order_by(StageTransition.transitioned_at.asc())
    ).scalars().unique().all()

    return ReferralHistoryResponse(
        referral_id=referral_id,
        transitions=[_transition_to_response(t) for t in transitions],
    )


# --- Dashboard Metrics ---


@router.get(
    "/metrics/{pipeline_type}",
    response_model=PipelineMetricsResponse,
)
def get_metrics(
    pipeline_type: PipelineType,
    since: datetime | None = Query(None, description="Filter referrals created after this time"),
    until: datetime | None = Query(None, description="Filter referrals created before this time"),
    db: Session = Depends(get_db_session),
) -> PipelineMetricsResponse:
    """Get dashboard KPI metrics for a pipeline type."""
    pt = pipeline_type.value

    # Base filter for referrals in this pipeline
    base_filter = [Referral.pipeline_type == pt]
    if since:
        base_filter.append(Referral.created_at >= since)
    if until:
        base_filter.append(Referral.created_at <= until)

    # 1. Status counts
    status_rows = db.execute(
        select(Referral.status, func.count(Referral.id))
        .where(*base_filter)
        .group_by(Referral.status)
    ).all()
    status_counts = {row[0]: row[1] for row in status_rows}

    total = sum(status_counts.values())
    active = status_counts.get("active", 0)
    completed = status_counts.get("completed", 0)
    cancelled = status_counts.get("cancelled", 0)

    # Conversion rate
    denominator = completed + cancelled
    conversion_rate = (completed / denominator) if denominator > 0 else None

    # 2. Per-stage active counts
    stage_rows = db.execute(
        select(
            PipelineStage.id,
            PipelineStage.name,
            PipelineStage.display_name,
            PipelineStage.sort_order,
            func.count(
                case(
                    (Referral.status == "active", Referral.id),
                    else_=None,
                )
            ).label("active_count"),
        )
        .outerjoin(
            Referral,
            (Referral.current_stage_id == PipelineStage.id)
            & (Referral.status == "active"),
        )
        .where(PipelineStage.pipeline_type == pt)
        .where(PipelineStage.is_active.is_(True))
        .group_by(PipelineStage.id, PipelineStage.name, PipelineStage.display_name, PipelineStage.sort_order)
        .order_by(PipelineStage.sort_order)
    ).all()

    # 3. Avg duration and completed count per stage (from transitions leaving each stage)
    duration_rows = db.execute(
        select(
            StageTransition.from_stage_id,
            func.avg(StageTransition.duration_seconds).label("avg_dur"),
            func.count().label("completed_count"),
        )
        .where(StageTransition.pipeline_type == pt)
        .where(StageTransition.from_stage_id.isnot(None))
        .group_by(StageTransition.from_stage_id)
    ).all()
    duration_map = {
        row[0]: {"avg_dur": float(row[1]) if row[1] else None, "completed_count": row[2]}
        for row in duration_rows
    }

    # Build stage metrics
    stage_metrics = []
    for stage_id, name, display_name, _sort_order, active_count in stage_rows:
        dur_info = duration_map.get(stage_id, {})
        stage_metrics.append(
            StageMetric(
                stage_id=stage_id,
                stage_name=name,
                stage_display_name=display_name,
                active_count=active_count,
                completed_count=dur_info.get("completed_count", 0),
                avg_duration_seconds=dur_info.get("avg_dur"),
            )
        )

    # 4. Avg total duration (sum of all duration_seconds per referral, for completed referrals)
    avg_total_subq = (
        select(
            StageTransition.referral_id,
            func.sum(StageTransition.duration_seconds).label("total_dur"),
        )
        .join(Referral, Referral.id == StageTransition.referral_id)
        .where(StageTransition.pipeline_type == pt)
        .where(Referral.status.in_(["completed", "cancelled"]))
        .group_by(StageTransition.referral_id)
        .subquery()
    )
    avg_total_result = db.execute(
        select(func.avg(avg_total_subq.c.total_dur))
    ).scalar()

    return PipelineMetricsResponse(
        pipeline_type=pipeline_type,
        total_referrals=total,
        active_referrals=active,
        completed_referrals=completed,
        cancelled_referrals=cancelled,
        conversion_rate=conversion_rate,
        avg_total_duration_seconds=float(avg_total_result) if avg_total_result else None,
        stage_metrics=stage_metrics,
    )
