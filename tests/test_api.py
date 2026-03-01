from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from preptrack.api.app import create_app
from preptrack.api.deps import get_storage
from preptrack.agent.exceptions import PlanGenerationError
from preptrack.models.enums import (
    BlockCategory,
    BlockType,
    CheckInStatus,
    Subject,
)
from preptrack.models.plan import DailyPlan, PlanCard, WeeklyPlan
from preptrack.models.user import TopicConfidence, UserProfile
from preptrack.storage.base import StorageBackend


# ── In-memory storage for tests ─────────────────────────────────────


class MemoryStorage(StorageBackend):
    def __init__(self):
        self.users: dict[str, UserProfile] = {}
        self.confidences: dict[str, list[TopicConfidence]] = {}
        self.plans: dict[str, WeeklyPlan] = {}
        self.activities = {}
        self.recovery_states = {}

    def get_user_profile(self, user_id):
        return self.users.get(user_id)

    def save_user_profile(self, profile):
        self.users[profile.user_id] = profile

    def get_topic_confidences(self, user_id):
        return self.confidences.get(user_id, [])

    def save_topic_confidence(self, user_id, confidence):
        self.confidences.setdefault(user_id, []).append(confidence)

    def get_weekly_plan(self, user_id, week_start):
        return self.plans.get(f"{user_id}:{week_start.isoformat()}")

    def save_weekly_plan(self, plan):
        key = f"{plan.user_id}:{plan.week_start.isoformat()}"
        self.plans[key] = plan

    def get_activity_log(self, user_id, log_date):
        return self.activities.get(f"{user_id}:{log_date.isoformat()}")

    def save_activity_log(self, activity):
        key = f"{activity.user_id}:{activity.date.isoformat()}"
        self.activities[key] = activity

    def get_pending_days(self, user_id, since_date):
        return []

    def get_recovery_state(self, user_id):
        return self.recovery_states.get(user_id)

    def save_recovery_state(self, state):
        self.recovery_states[state.user_id] = state


# ── Fixtures ─────────────────────────────────────────────────────────


def _make_fixture_plan(user_id: str, week_start: date) -> WeeklyPlan:
    card = PlanCard(
        block_type=BlockType.DEEP_STUDY,
        category=BlockCategory.CORE_LEARNING,
        subject=Subject.HISTORY,
        topic="Ancient India",
        planned_duration=90,
        fatigue=2,
        order=0,
    )
    day = DailyPlan(date=week_start, cards=[card])
    return WeeklyPlan(
        user_id=user_id,
        week_start=week_start,
        days=[day],
        narrative="Focus on foundation this week.",
    )


@pytest.fixture
def memory_storage():
    return MemoryStorage()


@pytest.fixture
def client(memory_storage):
    app = create_app()
    app.dependency_overrides[get_storage] = lambda: memory_storage
    return TestClient(app)


ONBOARD_PAYLOAD = {
    "display_name": "Test User",
    "optional_subject": "Sociology",
    "stage": "both",
    "prelims_date": "2026-05-25",
    "mains_date": "2026-09-19",
    "available_hours_per_day": 6.0,
    "subject_confidences": {
        "HISTORY": 2.0,
        "ECONOMY": 1.5,
        "POLITY": 3.0,
    },
}


# ── Onboard Tests ────────────────────────────────────────────────────


@patch("preptrack.api.routes.generate_plan")
def test_onboard_success(mock_gen, client, memory_storage):
    mock_gen.side_effect = lambda **kwargs: _make_fixture_plan(
        kwargs["profile"].user_id, date(2026, 3, 2)
    )

    resp = client.post("/api/users/onboard", json=ONBOARD_PAYLOAD)
    assert resp.status_code == 200

    body = resp.json()
    assert body["user_id"]
    assert body["profile"]["display_name"] == "Test User"
    assert body["profile"]["stage"] == "both"
    assert body["plan"] is not None
    assert body["plan"]["narrative"] == "Focus on foundation this week."
    assert body["plan_error"] is None

    # Verify storage was populated
    assert memory_storage.get_user_profile(body["user_id"]) is not None
    assert len(memory_storage.get_topic_confidences(body["user_id"])) == 3


@patch("preptrack.api.routes.generate_plan")
def test_onboard_plan_failure_still_creates_user(mock_gen, client, memory_storage):
    mock_gen.side_effect = PlanGenerationError("LLM unavailable")

    resp = client.post("/api/users/onboard", json=ONBOARD_PAYLOAD)
    assert resp.status_code == 200

    body = resp.json()
    assert body["user_id"]
    assert body["plan"] is None
    assert body["plan_error"] == "LLM unavailable"
    assert memory_storage.get_user_profile(body["user_id"]) is not None


def test_onboard_invalid_stage(client):
    payload = {**ONBOARD_PAYLOAD, "stage": "invalid"}
    resp = client.post("/api/users/onboard", json=payload)
    assert resp.status_code == 422


def test_onboard_missing_name(client):
    payload = {**ONBOARD_PAYLOAD, "display_name": ""}
    resp = client.post("/api/users/onboard", json=payload)
    assert resp.status_code == 422


def test_onboard_hours_too_high(client):
    payload = {**ONBOARD_PAYLOAD, "available_hours_per_day": 20}
    resp = client.post("/api/users/onboard", json=payload)
    assert resp.status_code == 422


# ── Get User Tests ───────────────────────────────────────────────────


def test_get_user_not_found(client):
    resp = client.get("/api/users/nonexistent")
    assert resp.status_code == 404


def test_get_user_success(client, memory_storage):
    profile = UserProfile(
        user_id="u1",
        display_name="Existing",
        stage="prelims",
        prelims_date=date(2026, 5, 25),
        available_hours_per_day=4.0,
    )
    memory_storage.save_user_profile(profile)
    tc = TopicConfidence(user_id="u1", subject=Subject.POLITY, perceived_confidence=3.0)
    memory_storage.save_topic_confidence("u1", tc)

    resp = client.get("/api/users/u1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["profile"]["display_name"] == "Existing"
    assert len(body["confidences"]) == 1
    assert body["confidences"][0]["subject"] == "POLITY"


# ── Get Plan Tests ───────────────────────────────────────────────────


def test_get_plan_user_not_found(client):
    resp = client.get("/api/users/nope/plan", params={"week_start": "2026-03-02"})
    assert resp.status_code == 404


def test_get_plan_not_found(client, memory_storage):
    profile = UserProfile(
        user_id="u2",
        display_name="No Plan",
        stage="prelims",
        prelims_date=date(2026, 5, 25),
        available_hours_per_day=4.0,
    )
    memory_storage.save_user_profile(profile)

    resp = client.get("/api/users/u2/plan", params={"week_start": "2026-03-02"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No plan found for this week"


def test_get_plan_success(client, memory_storage):
    profile = UserProfile(
        user_id="u3",
        display_name="Has Plan",
        stage="both",
        prelims_date=date(2026, 5, 25),
        mains_date=date(2026, 9, 19),
        available_hours_per_day=6.0,
    )
    memory_storage.save_user_profile(profile)
    plan = _make_fixture_plan("u3", date(2026, 3, 2))
    memory_storage.save_weekly_plan(plan)

    resp = client.get("/api/users/u3/plan", params={"week_start": "2026-03-02"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "u3"
    assert body["narrative"] == "Focus on foundation this week."
    assert len(body["days"]) == 1
    assert body["days"][0]["cards"][0]["topic"] == "Ancient India"


def test_get_plan_missing_week_start(client, memory_storage):
    profile = UserProfile(
        user_id="u4",
        display_name="Missing Param",
        stage="prelims",
        prelims_date=date(2026, 5, 25),
        available_hours_per_day=4.0,
    )
    memory_storage.save_user_profile(profile)

    resp = client.get("/api/users/u4/plan")
    assert resp.status_code == 422


# ── Generate Plan Tests ──────────────────────────────────────────────


@patch("preptrack.api.routes.generate_plan")
def test_generate_plan_success(mock_gen, client, memory_storage):
    profile = UserProfile(
        user_id="u5",
        display_name="Gen Plan",
        stage="both",
        prelims_date=date(2026, 5, 25),
        mains_date=date(2026, 9, 19),
        available_hours_per_day=6.0,
    )
    memory_storage.save_user_profile(profile)

    mock_gen.return_value = _make_fixture_plan("u5", date(2026, 3, 9))

    resp = client.post(
        "/api/users/u5/plan/generate",
        json={"week_start": "2026-03-09"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "u5"
    assert body["week_start"] == "2026-03-09"

    # Plan should be stored
    stored = memory_storage.get_weekly_plan("u5", date(2026, 3, 9))
    assert stored is not None


@patch("preptrack.api.routes.generate_plan")
def test_generate_plan_user_not_found(mock_gen, client):
    resp = client.post("/api/users/nope/plan/generate", json={})
    assert resp.status_code == 404
    mock_gen.assert_not_called()


@patch("preptrack.api.routes.generate_plan")
def test_generate_plan_llm_error_propagates(mock_gen, client, memory_storage):
    profile = UserProfile(
        user_id="u6",
        display_name="LLM Fail",
        stage="prelims",
        prelims_date=date(2026, 5, 25),
        available_hours_per_day=4.0,
    )
    memory_storage.save_user_profile(profile)
    mock_gen.side_effect = PlanGenerationError("Max retries exceeded")

    resp = client.post("/api/users/u6/plan/generate", json={})
    assert resp.status_code == 500


# ── Confidence Filtering Tests ───────────────────────────────────────


@patch("preptrack.api.routes.generate_plan")
def test_onboard_ignores_invalid_subjects(mock_gen, client, memory_storage):
    mock_gen.side_effect = lambda **kwargs: _make_fixture_plan(
        kwargs["profile"].user_id, date(2026, 3, 2)
    )

    payload = {
        **ONBOARD_PAYLOAD,
        "subject_confidences": {
            "HISTORY": 2.0,
            "NOT_A_SUBJECT": 3.0,
        },
    }
    resp = client.post("/api/users/onboard", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    # Only valid subject saved
    assert len(memory_storage.get_topic_confidences(body["user_id"])) == 1
