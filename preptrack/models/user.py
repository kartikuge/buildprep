from datetime import UTC, date, datetime

from pydantic import BaseModel, Field

from preptrack.models.enums import BlockType, CheckInStatus, Subject


class UserProfile(BaseModel):
    user_id: str
    display_name: str
    optional_subject: str | None = None
    stage: str = Field(pattern=r"^(prelims|mains|both)$")
    prelims_date: date | None = None
    mains_date: date | None = None
    prelims_cleared: bool = False
    available_hours_per_day: float = Field(gt=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TopicConfidence(BaseModel):
    user_id: str
    subject: Subject
    perceived_confidence: float = Field(ge=1.0, le=5.0)
    streak: int = Field(default=0, ge=0)
    skip_count: int = Field(default=0, ge=0)
    total_sessions: int = Field(default=0, ge=0)
    last_practiced_date: date | None = None
    milestones_awarded: list[str] = Field(default_factory=list)


class ActivityLogEntry(BaseModel):
    card_id: str
    block_type: BlockType
    subject: Subject | None = None
    topic: str | None = None
    planned_duration: int
    actual_duration: int | None = None
    status: CheckInStatus


class DayActivity(BaseModel):
    user_id: str
    date: date
    entries: list[ActivityLogEntry] = Field(default_factory=list)
    finalized: bool = False
    finalized_at: datetime | None = None


class RecoveryState(BaseModel):
    user_id: str
    missed_dates: list[date] = Field(default_factory=list)
    recovery_window_days: int = Field(ge=1, le=7)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
