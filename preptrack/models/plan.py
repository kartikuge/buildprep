from datetime import UTC, date, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from preptrack.models.enums import (
    BlockCategory,
    BlockType,
    CheckInStatus,
    Subject,
)


class PlanCard(BaseModel):
    card_id: str = Field(default_factory=lambda: str(uuid4()))
    block_type: BlockType
    category: BlockCategory
    subject: Subject | None = None
    topic: str | None = None
    planned_duration: int = Field(gt=0)
    actual_duration: int | None = None
    fatigue: int = Field(ge=1, le=4)
    order: int = Field(ge=0)
    status: CheckInStatus = CheckInStatus.PENDING


class DailyPlan(BaseModel):
    date: date
    cards: list[PlanCard] = Field(default_factory=list)
    finalized: bool = False
    finalized_at: datetime | None = None

    @property
    def total_planned_minutes(self) -> int:
        return sum(c.planned_duration for c in self.cards)

    @property
    def total_fatigue(self) -> int:
        return sum(c.fatigue for c in self.cards)


class WeeklyPlan(BaseModel):
    user_id: str
    week_start: date  # Monday
    days: list[DailyPlan] = Field(default_factory=list)
    narrative: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ValidationViolation(BaseModel):
    rule_id: str
    message: str
    day: date | None = None
    severity: str = "error"  # "error" or "warning"


class ValidationResult(BaseModel):
    valid: bool
    violations: list[ValidationViolation] = Field(default_factory=list)


class SubjectPriority(BaseModel):
    subject: Subject
    raw_priority: float
    normalized_confidence: float
    weight: float
    recency_penalty: float
