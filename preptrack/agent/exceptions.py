from __future__ import annotations

from preptrack.models.plan import ValidationViolation


class PlanGenerationError(Exception):
    """Raised when plan generation fails after all retries."""

    def __init__(
        self, message: str, violations: list[ValidationViolation] | None = None
    ):
        super().__init__(message)
        self.violations = violations or []
