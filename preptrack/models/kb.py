from pydantic import BaseModel, Field

from preptrack.models.enums import (
    BlockCategory,
    BlockType,
    HeavyLevel,
    MainsPaper,
    Phase,
    Subject,
)


class BlockDefinition(BaseModel):
    block_type: BlockType
    category: BlockCategory
    fatigue: int = Field(ge=1, le=4)
    heavy: HeavyLevel = HeavyLevel.NONE
    min_duration: int = Field(ge=15)
    max_duration: int = Field(ge=15)
    max_per_week: int = Field(ge=1)
    notes: str = ""


class CategoryAllocation(BaseModel):
    category: BlockCategory
    percentage: float = Field(ge=0, le=100)


class PhaseBlueprint(BaseModel):
    phase: Phase
    allocations: list[CategoryAllocation]
    blend_enabled: bool = False
    fatigue_multiplier_standard: float
    fatigue_multiplier_low_hours: float


class SubjectWeight(BaseModel):
    subject: Subject
    prelims_weight: float | None = None  # None for non-prelims subjects
    mains_paper: MainsPaper | None = None


class StreakMilestone(BaseModel):
    streak: int
    bonus: float


class SessionMilestone(BaseModel):
    total_sessions: int
    bonus: float
    one_shot: bool = True  # False means recurring


class SkipPenalty(BaseModel):
    skip_count: int
    penalty: float


class ConfidenceConfig(BaseModel):
    streak_milestones: list[StreakMilestone]
    session_milestones: list[SessionMilestone]
    skip_penalties: list[SkipPenalty]
    decay_per_7_days: float = 0.1
    maintenance_decay_per_7_days: float = 0.05
    maintenance_min_sessions: int = 50
    maintenance_min_streak: int = 10
    streak_reset_days: int = 14
    min_confidence: float = 1.0
    max_confidence: float = 5.0


class Rule(BaseModel):
    rule_id: str
    name: str
    rule_type: str  # "hard", "medium", "low", "deferred"
    description: str
