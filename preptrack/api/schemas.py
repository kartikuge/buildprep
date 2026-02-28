from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class OnboardRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    optional_subject: str | None = None
    stage: str = Field(pattern=r"^(prelims|mains|both)$")
    prelims_date: date | None = None
    mains_date: date | None = None
    available_hours_per_day: float = Field(gt=0, le=16)
    subject_confidences: dict[str, float] = Field(default_factory=dict)


class OnboardResponse(BaseModel):
    user_id: str
    profile: dict[str, Any]
    plan: dict[str, Any] | None = None
    plan_error: str | None = None


class GeneratePlanRequest(BaseModel):
    week_start: date | None = None
