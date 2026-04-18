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
    debug_date: date | None = None


class OnboardResponse(BaseModel):
    user_id: str
    profile: dict[str, Any]
    plan: dict[str, Any] | None = None
    plan_error: str | None = None


class GeneratePlanRequest(BaseModel):
    week_start: date | None = None
    debug_date: date | None = None


class CardCheckIn(BaseModel):
    card_id: str
    status: str = Field(pattern=r"^(DONE|PARTIAL|SKIPPED)$")
    actual_duration: int | None = None


class CheckInRequest(BaseModel):
    cards: list[CardCheckIn]
    finalize_day: bool = False


class CheckInResponse(BaseModel):
    date: str
    finalized: bool
    cards_updated: int
    confidences_updated: list[str]


class RebalanceRequest(BaseModel):
    week_start: date
    recovery_window_days: int = Field(ge=1, le=7)
    debug_date: date | None = None
    include_next_weeks: int = Field(default=0, ge=0, le=2)


class RebalanceResponse(BaseModel):
    success: bool
    missed_dates: list[str]
    recovery_dates: list[str]
    total_cards_regenerated: int
    narrative: str | None = None
    error: str | None = None
    next_weeks_generated: list[str] = Field(default_factory=list)


class GenerateAheadRequest(BaseModel):
    weeks_ahead: int = Field(ge=1, le=2)
    debug_date: date | None = None


class GenerateAheadResponse(BaseModel):
    weeks_generated: list[str]
    weeks_skipped: list[str] = Field(default_factory=list)
