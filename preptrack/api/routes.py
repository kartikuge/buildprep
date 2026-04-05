from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from preptrack.agent.exceptions import PlanGenerationError
from preptrack.agent.planner import generate_plan
from preptrack.agent.rebalancer import rebalance_plan
from preptrack.api.deps import get_storage
from preptrack.api.schemas import (
    CheckInRequest,
    CheckInResponse,
    GeneratePlanRequest,
    OnboardRequest,
    OnboardResponse,
    RebalanceRequest,
    RebalanceResponse,
)
from preptrack.engine.confidence import process_checkin
from preptrack.kb.confidence import CONFIDENCE_CONFIG
from preptrack.models.enums import CheckInStatus, Subject
from preptrack.models.user import (
    ActivityLogEntry,
    DayActivity,
    RecoveryState,
    TopicConfidence,
    UserProfile,
)
from preptrack.storage.base import StorageBackend

router = APIRouter()


@router.post("/users/onboard", response_model=OnboardResponse)
def onboard(req: OnboardRequest, storage: StorageBackend = Depends(get_storage)):
    user_id = str(uuid4())

    profile = UserProfile(
        user_id=user_id,
        display_name=req.display_name,
        optional_subject=req.optional_subject,
        stage=req.stage,
        prelims_date=req.prelims_date,
        mains_date=req.mains_date,
        available_hours_per_day=req.available_hours_per_day,
    )
    storage.save_user_profile(profile)

    confidences: list[TopicConfidence] = []
    for subj_str, conf_val in req.subject_confidences.items():
        try:
            subject = Subject(subj_str)
        except ValueError:
            continue
        tc = TopicConfidence(
            user_id=user_id,
            subject=subject,
            perceived_confidence=conf_val,
        )
        storage.save_topic_confidence(user_id, tc)
        confidences.append(tc)

    plan_dict = None
    plan_error = None
    try:
        plan = generate_plan(
            profile=profile,
            confidences=confidences,
            plan_start=req.debug_date,
        )
        storage.save_weekly_plan(plan)
        plan_dict = plan.model_dump(mode="json")
    except PlanGenerationError as e:
        plan_error = str(e)

    return OnboardResponse(
        user_id=user_id,
        profile=profile.model_dump(mode="json"),
        plan=plan_dict,
        plan_error=plan_error,
    )


@router.get("/users/{user_id}")
def get_user(user_id: str, storage: StorageBackend = Depends(get_storage)):
    profile = storage.get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    confidences = storage.get_topic_confidences(user_id)
    return {
        "profile": profile.model_dump(mode="json"),
        "confidences": [c.model_dump(mode="json") for c in confidences],
    }


@router.get("/users/{user_id}/plan")
def get_plan(
    user_id: str,
    week_start: date = Query(...),
    storage: StorageBackend = Depends(get_storage),
):
    profile = storage.get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    plan = storage.get_weekly_plan(user_id, week_start)
    if not plan:
        raise HTTPException(status_code=404, detail="No plan found for this week")

    return plan.model_dump(mode="json")


@router.post("/users/{user_id}/plan/generate")
def generate_new_plan(
    user_id: str,
    req: GeneratePlanRequest,
    storage: StorageBackend = Depends(get_storage),
):
    profile = storage.get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    confidences = storage.get_topic_confidences(user_id)

    try:
        plan = generate_plan(
            profile=profile,
            confidences=confidences,
            week_start=req.week_start,
            plan_start=req.debug_date,
        )
    except PlanGenerationError as e:
        raise HTTPException(status_code=500, detail=str(e))

    storage.save_weekly_plan(plan)
    return plan.model_dump(mode="json")


@router.post("/users/{user_id}/checkin/{checkin_date}", response_model=CheckInResponse)
def checkin(
    user_id: str,
    checkin_date: date,
    req: CheckInRequest,
    storage: StorageBackend = Depends(get_storage),
):
    profile = storage.get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    # Derive week_start (Monday) from checkin_date
    week_start = checkin_date - timedelta(days=checkin_date.weekday())
    plan = storage.get_weekly_plan(user_id, week_start)
    if not plan:
        raise HTTPException(status_code=404, detail="No plan found for this week")

    # Find the daily plan for checkin_date
    daily = None
    for d in plan.days:
        if d.date == checkin_date:
            daily = d
            break
    if daily is None:
        raise HTTPException(status_code=404, detail="No plan for this date")

    if daily.finalized:
        raise HTTPException(status_code=409, detail="Day already finalized")

    # Build card lookup
    card_map = {c.card_id: c for c in daily.cards}

    # Update card statuses
    cards_updated = 0
    for ci in req.cards:
        card = card_map.get(ci.card_id)
        if not card:
            continue
        card.status = CheckInStatus(ci.status)
        if ci.actual_duration is not None:
            card.actual_duration = ci.actual_duration
        cards_updated += 1

    # Finalize: mark remaining PENDING as SKIPPED
    if req.finalize_day:
        for card in daily.cards:
            if card.status == CheckInStatus.PENDING:
                card.status = CheckInStatus.SKIPPED
        daily.finalized = True
        daily.finalized_at = datetime.now(UTC)

    storage.save_weekly_plan(plan)

    # Update confidence for each checked-in card that has a subject
    confidences_updated: list[str] = []
    existing_confidences = {
        tc.subject: tc for tc in storage.get_topic_confidences(user_id)
    }

    for ci in req.cards:
        card = card_map.get(ci.card_id)
        if not card or not card.subject:
            continue
        status = CheckInStatus(ci.status)
        tc = existing_confidences.get(card.subject)
        if not tc:
            tc = TopicConfidence(
                user_id=user_id,
                subject=card.subject,
                perceived_confidence=2.5,
            )
        updated_tc = process_checkin(tc, status, CONFIDENCE_CONFIG, checkin_date)
        storage.save_topic_confidence(user_id, updated_tc)
        existing_confidences[card.subject] = updated_tc
        if card.subject.value not in confidences_updated:
            confidences_updated.append(card.subject.value)

    # Save activity log
    entries = []
    for card in daily.cards:
        if card.status != CheckInStatus.PENDING:
            entries.append(
                ActivityLogEntry(
                    card_id=card.card_id,
                    block_type=card.block_type,
                    subject=card.subject,
                    topic=card.topic,
                    planned_duration=card.planned_duration,
                    actual_duration=card.actual_duration,
                    status=card.status,
                )
            )
    if entries:
        activity = DayActivity(
            user_id=user_id,
            date=checkin_date,
            entries=entries,
            finalized=daily.finalized,
            finalized_at=daily.finalized_at,
        )
        storage.save_activity_log(activity)

    return CheckInResponse(
        date=checkin_date.isoformat(),
        finalized=daily.finalized,
        cards_updated=cards_updated,
        confidences_updated=confidences_updated,
    )


@router.post("/users/{user_id}/plan/rebalance", response_model=RebalanceResponse)
def rebalance(
    user_id: str,
    req: RebalanceRequest,
    storage: StorageBackend = Depends(get_storage),
):
    profile = storage.get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    plan = storage.get_weekly_plan(user_id, req.week_start)
    if not plan:
        raise HTTPException(status_code=404, detail="No plan found for this week")

    confidences = storage.get_topic_confidences(user_id)

    try:
        updated_plan, missed_dates, recovery_dates, narrative = rebalance_plan(
            plan=plan,
            profile=profile,
            confidences=confidences,
            recovery_window_days=req.recovery_window_days,
            today=req.debug_date,
        )
    except PlanGenerationError as e:
        return RebalanceResponse(
            success=False,
            missed_dates=[],
            recovery_dates=[],
            total_cards_regenerated=0,
            error=str(e),
        )

    storage.save_weekly_plan(updated_plan)

    # Save recovery state for audit trail
    recovery_state = RecoveryState(
        user_id=user_id,
        missed_dates=missed_dates,
        recovery_window_days=req.recovery_window_days,
    )
    storage.save_recovery_state(recovery_state)

    # Count cards in recovery days
    recovery_date_set = set(recovery_dates)
    total_cards = sum(
        len(d.cards)
        for d in updated_plan.days
        if d.date in recovery_date_set
    )

    return RebalanceResponse(
        success=True,
        missed_dates=[d.isoformat() for d in missed_dates],
        recovery_dates=[d.isoformat() for d in recovery_dates],
        total_cards_regenerated=total_cards,
        narrative=narrative,
    )


@router.get("/users/{user_id}/confidence")
def get_confidences(user_id: str, storage: StorageBackend = Depends(get_storage)):
    profile = storage.get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    confidences = storage.get_topic_confidences(user_id)
    return [c.model_dump(mode="json") for c in confidences]
