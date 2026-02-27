from abc import ABC, abstractmethod
from datetime import date

from preptrack.models.plan import WeeklyPlan
from preptrack.models.user import DayActivity, RecoveryState, TopicConfidence, UserProfile


class StorageBackend(ABC):
    @abstractmethod
    def get_user_profile(self, user_id: str) -> UserProfile | None: ...

    @abstractmethod
    def save_user_profile(self, profile: UserProfile) -> None: ...

    @abstractmethod
    def get_topic_confidences(self, user_id: str) -> list[TopicConfidence]: ...

    @abstractmethod
    def save_topic_confidence(self, user_id: str, confidence: TopicConfidence) -> None: ...

    @abstractmethod
    def get_weekly_plan(self, user_id: str, week_start: date) -> WeeklyPlan | None: ...

    @abstractmethod
    def save_weekly_plan(self, plan: WeeklyPlan) -> None: ...

    @abstractmethod
    def get_activity_log(self, user_id: str, log_date: date) -> DayActivity | None: ...

    @abstractmethod
    def save_activity_log(self, activity: DayActivity) -> None: ...

    @abstractmethod
    def get_pending_days(self, user_id: str, since_date: date) -> list[DayActivity]: ...

    @abstractmethod
    def get_recovery_state(self, user_id: str) -> RecoveryState | None: ...

    @abstractmethod
    def save_recovery_state(self, state: RecoveryState) -> None: ...
