from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from preptrack.agent.exceptions import PlanGenerationError
from preptrack.agent.planner import generate_plan
from preptrack.api.deps import get_storage
from preptrack.api.schemas import GeneratePlanRequest, OnboardRequest, OnboardResponse
from preptrack.models.enums import Subject
from preptrack.models.user import TopicConfidence, UserProfile
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
        plan = generate_plan(profile=profile, confidences=confidences)
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
        )
    except PlanGenerationError as e:
        raise HTTPException(status_code=500, detail=str(e))

    storage.save_weekly_plan(plan)
    return plan.model_dump(mode="json")
