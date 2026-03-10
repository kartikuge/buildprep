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
        existing = self.confidences.setdefault(user_id, [])
        for i, c in enumerate(existing):
            if c.subject == confidence.subject:
                existing[i] = confidence
                return
        existing.append(confidence)

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


# ── Check-in Fixtures ────────────────────────────────────────────────


def _setup_checkin_user(memory_storage, user_id="cu1", week_start=date(2026, 3, 2)):
    """Create a user + plan with two cards for check-in tests."""
    profile = UserProfile(
        user_id=user_id,
        display_name="CheckIn User",
        stage="both",
        prelims_date=date(2026, 5, 25),
        mains_date=date(2026, 9, 19),
        available_hours_per_day=6.0,
    )
    memory_storage.save_user_profile(profile)

    card_history = PlanCard(
        card_id="card-history",
        block_type=BlockType.DEEP_STUDY,
        category=BlockCategory.CORE_LEARNING,
        subject=Subject.HISTORY,
        topic="Ancient India",
        planned_duration=90,
        fatigue=2,
        order=0,
    )
    card_news = PlanCard(
        card_id="card-news",
        block_type=BlockType.NEWS_READING,
        category=BlockCategory.INPUT,
        subject=None,
        topic=None,
        planned_duration=30,
        fatigue=0,
        order=1,
    )
    day = DailyPlan(date=week_start, cards=[card_history, card_news])
    plan = WeeklyPlan(
        user_id=user_id,
        week_start=week_start,
        days=[day],
        narrative="Test week.",
    )
    memory_storage.save_weekly_plan(plan)
    return profile, plan


# ── Check-in Tests ────────────────────────────────────────────────────


def test_checkin_single_card_done(client, memory_storage):
    _setup_checkin_user(memory_storage)

    resp = client.post(
        "/api/users/cu1/checkin/2026-03-02",
        json={"cards": [{"card_id": "card-history", "status": "DONE"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cards_updated"] == 1
    assert body["finalized"] is False
    assert "HISTORY" in body["confidences_updated"]

    # Verify confidence was created/updated
    confs = memory_storage.get_topic_confidences("cu1")
    history_conf = next(c for c in confs if c.subject == Subject.HISTORY)
    assert history_conf.streak == 1
    assert history_conf.total_sessions == 1


def test_checkin_partial_with_duration(client, memory_storage):
    _setup_checkin_user(memory_storage)

    resp = client.post(
        "/api/users/cu1/checkin/2026-03-02",
        json={
            "cards": [
                {"card_id": "card-history", "status": "PARTIAL", "actual_duration": 45}
            ]
        },
    )
    assert resp.status_code == 200

    # Verify actual_duration stored on the card
    plan = memory_storage.get_weekly_plan("cu1", date(2026, 3, 2))
    card = next(c for c in plan.days[0].cards if c.card_id == "card-history")
    assert card.actual_duration == 45
    assert card.status == CheckInStatus.PARTIAL


def test_checkin_skip(client, memory_storage):
    _setup_checkin_user(memory_storage)

    resp = client.post(
        "/api/users/cu1/checkin/2026-03-02",
        json={"cards": [{"card_id": "card-history", "status": "SKIPPED"}]},
    )
    assert resp.status_code == 200

    confs = memory_storage.get_topic_confidences("cu1")
    history_conf = next(c for c in confs if c.subject == Subject.HISTORY)
    assert history_conf.skip_count == 1
    assert history_conf.streak == 0


def test_checkin_finalize_day(client, memory_storage):
    _setup_checkin_user(memory_storage)

    resp = client.post(
        "/api/users/cu1/checkin/2026-03-02",
        json={
            "cards": [{"card_id": "card-history", "status": "DONE"}],
            "finalize_day": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["finalized"] is True

    # Remaining PENDING card should be SKIPPED
    plan = memory_storage.get_weekly_plan("cu1", date(2026, 3, 2))
    news_card = next(c for c in plan.days[0].cards if c.card_id == "card-news")
    assert news_card.status == CheckInStatus.SKIPPED
    assert plan.days[0].finalized is True


def test_checkin_already_finalized_409(client, memory_storage):
    _setup_checkin_user(memory_storage)

    # Finalize first
    client.post(
        "/api/users/cu1/checkin/2026-03-02",
        json={
            "cards": [{"card_id": "card-history", "status": "DONE"}],
            "finalize_day": True,
        },
    )
    # Try again
    resp = client.post(
        "/api/users/cu1/checkin/2026-03-02",
        json={"cards": [{"card_id": "card-history", "status": "DONE"}]},
    )
    assert resp.status_code == 409


def test_checkin_user_not_found_404(client):
    resp = client.post(
        "/api/users/nobody/checkin/2026-03-02",
        json={"cards": [{"card_id": "x", "status": "DONE"}]},
    )
    assert resp.status_code == 404


def test_checkin_plan_not_found_404(client, memory_storage):
    profile = UserProfile(
        user_id="cu_noplan",
        display_name="No Plan",
        stage="prelims",
        prelims_date=date(2026, 5, 25),
        available_hours_per_day=4.0,
    )
    memory_storage.save_user_profile(profile)

    resp = client.post(
        "/api/users/cu_noplan/checkin/2026-03-02",
        json={"cards": [{"card_id": "x", "status": "DONE"}]},
    )
    assert resp.status_code == 404


def test_checkin_no_subject_skips_confidence(client, memory_storage):
    _setup_checkin_user(memory_storage)

    resp = client.post(
        "/api/users/cu1/checkin/2026-03-02",
        json={"cards": [{"card_id": "card-news", "status": "DONE"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["confidences_updated"] == []


# ── Confidence Tests ──────────────────────────────────────────────────


def test_get_confidences_success(client, memory_storage):
    profile = UserProfile(
        user_id="conf1",
        display_name="Conf User",
        stage="both",
        prelims_date=date(2026, 5, 25),
        mains_date=date(2026, 9, 19),
        available_hours_per_day=6.0,
    )
    memory_storage.save_user_profile(profile)
    tc = TopicConfidence(user_id="conf1", subject=Subject.POLITY, perceived_confidence=3.5)
    memory_storage.save_topic_confidence("conf1", tc)

    resp = client.get("/api/users/conf1/confidence")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["subject"] == "POLITY"
    assert body[0]["perceived_confidence"] == 3.5


def test_get_confidences_empty(client, memory_storage):
    profile = UserProfile(
        user_id="conf2",
        display_name="No Confs",
        stage="prelims",
        prelims_date=date(2026, 5, 25),
        available_hours_per_day=4.0,
    )
    memory_storage.save_user_profile(profile)

    resp = client.get("/api/users/conf2/confidence")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_confidences_user_not_found_404(client):
    resp = client.get("/api/users/nobody/confidence")
    assert resp.status_code == 404


# ── Check-in Integration Tests (multi-step flows) ────────────────────


def _setup_multi_card_user(memory_storage, user_id="int1"):
    """Create user with a 2-day plan, multiple subjects per day."""
    profile = UserProfile(
        user_id=user_id,
        display_name="Integration User",
        stage="both",
        prelims_date=date(2026, 5, 25),
        mains_date=date(2026, 9, 19),
        available_hours_per_day=6.0,
    )
    memory_storage.save_user_profile(profile)

    day1_cards = [
        PlanCard(
            card_id="d1-history",
            block_type=BlockType.DEEP_STUDY,
            category=BlockCategory.CORE_LEARNING,
            subject=Subject.HISTORY,
            topic="Ancient India",
            planned_duration=90,
            fatigue=2,
            order=0,
        ),
        PlanCard(
            card_id="d1-polity",
            block_type=BlockType.DEEP_STUDY,
            category=BlockCategory.CORE_LEARNING,
            subject=Subject.POLITY,
            topic="Parliament",
            planned_duration=60,
            fatigue=2,
            order=1,
        ),
        PlanCard(
            card_id="d1-news",
            block_type=BlockType.NEWS_READING,
            category=BlockCategory.INPUT,
            subject=None,
            topic=None,
            planned_duration=30,
            fatigue=0,
            order=2,
        ),
    ]
    day2_cards = [
        PlanCard(
            card_id="d2-history",
            block_type=BlockType.REVISION,
            category=BlockCategory.CORE_RETENTION,
            subject=Subject.HISTORY,
            topic="Medieval India",
            planned_duration=45,
            fatigue=1,
            order=0,
        ),
        PlanCard(
            card_id="d2-economy",
            block_type=BlockType.DEEP_STUDY,
            category=BlockCategory.CORE_LEARNING,
            subject=Subject.ECONOMY,
            topic="Fiscal Policy",
            planned_duration=90,
            fatigue=2,
            order=1,
        ),
    ]
    day1 = DailyPlan(date=date(2026, 3, 2), cards=day1_cards)
    day2 = DailyPlan(date=date(2026, 3, 3), cards=day2_cards)
    plan = WeeklyPlan(
        user_id=user_id,
        week_start=date(2026, 3, 2),
        days=[day1, day2],
        narrative="Integration test week.",
    )
    memory_storage.save_weekly_plan(plan)
    return profile


def test_integration_full_day_checkin_flow(client, memory_storage):
    """Full flow: check in cards one by one, then finalize day."""
    _setup_multi_card_user(memory_storage, "flow1")

    # Step 1: Mark history DONE
    resp = client.post(
        "/api/users/flow1/checkin/2026-03-02",
        json={"cards": [{"card_id": "d1-history", "status": "DONE"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["cards_updated"] == 1
    assert resp.json()["finalized"] is False

    # Step 2: Mark polity PARTIAL (40 of 60 minutes)
    resp = client.post(
        "/api/users/flow1/checkin/2026-03-02",
        json={"cards": [{"card_id": "d1-polity", "status": "PARTIAL", "actual_duration": 40}]},
    )
    assert resp.status_code == 200
    assert "POLITY" in resp.json()["confidences_updated"]

    # Step 3: Finalize — news card (PENDING) should auto-SKIP
    resp = client.post(
        "/api/users/flow1/checkin/2026-03-02",
        json={"cards": [], "finalize_day": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["finalized"] is True

    # Verify plan state
    plan = memory_storage.get_weekly_plan("flow1", date(2026, 3, 2))
    day1 = plan.days[0]
    assert day1.finalized is True
    assert day1.finalized_at is not None
    card_statuses = {c.card_id: c.status for c in day1.cards}
    assert card_statuses["d1-history"] == CheckInStatus.DONE
    assert card_statuses["d1-polity"] == CheckInStatus.PARTIAL
    assert card_statuses["d1-news"] == CheckInStatus.SKIPPED

    # Verify polity actual_duration persisted
    polity_card = next(c for c in day1.cards if c.card_id == "d1-polity")
    assert polity_card.actual_duration == 40

    # Step 4: Attempting to check in again should 409
    resp = client.post(
        "/api/users/flow1/checkin/2026-03-02",
        json={"cards": [{"card_id": "d1-history", "status": "DONE"}]},
    )
    assert resp.status_code == 409


def test_integration_confidence_accumulates_across_days(client, memory_storage):
    """Confidence for the same subject accumulates across multiple check-ins."""
    _setup_multi_card_user(memory_storage, "acc1")

    # Day 1: history DONE
    resp = client.post(
        "/api/users/acc1/checkin/2026-03-02",
        json={"cards": [{"card_id": "d1-history", "status": "DONE"}]},
    )
    assert resp.status_code == 200

    confs = memory_storage.get_topic_confidences("acc1")
    h1 = next(c for c in confs if c.subject == Subject.HISTORY)
    assert h1.streak == 1
    assert h1.total_sessions == 1

    # Day 2: history DONE again (different card)
    resp = client.post(
        "/api/users/acc1/checkin/2026-03-03",
        json={"cards": [{"card_id": "d2-history", "status": "DONE"}]},
    )
    assert resp.status_code == 200

    confs = memory_storage.get_topic_confidences("acc1")
    h2 = next(c for c in confs if c.subject == Subject.HISTORY)
    assert h2.streak == 2
    assert h2.total_sessions == 2

    # Verify via GET /confidence endpoint
    resp = client.get("/api/users/acc1/confidence")
    assert resp.status_code == 200
    history_api = next(c for c in resp.json() if c["subject"] == "HISTORY")
    assert history_api["streak"] == 2
    assert history_api["total_sessions"] == 2


def test_integration_skip_then_done_resets_streak(client, memory_storage):
    """Skip resets streak to 0, subsequent DONE starts streak fresh at 1."""
    _setup_multi_card_user(memory_storage, "sr1")

    # Day 1: skip history
    client.post(
        "/api/users/sr1/checkin/2026-03-02",
        json={"cards": [{"card_id": "d1-history", "status": "SKIPPED"}]},
    )
    confs = memory_storage.get_topic_confidences("sr1")
    h = next(c for c in confs if c.subject == Subject.HISTORY)
    assert h.streak == 0
    assert h.skip_count == 1

    # Day 2: do history
    client.post(
        "/api/users/sr1/checkin/2026-03-03",
        json={"cards": [{"card_id": "d2-history", "status": "DONE"}]},
    )
    confs = memory_storage.get_topic_confidences("sr1")
    h = next(c for c in confs if c.subject == Subject.HISTORY)
    assert h.streak == 1
    assert h.skip_count == 0  # reset on completion
    assert h.total_sessions == 1


def test_integration_multi_card_batch_checkin(client, memory_storage):
    """Submit multiple cards in a single request."""
    _setup_multi_card_user(memory_storage, "batch1")

    resp = client.post(
        "/api/users/batch1/checkin/2026-03-02",
        json={
            "cards": [
                {"card_id": "d1-history", "status": "DONE"},
                {"card_id": "d1-polity", "status": "SKIPPED"},
                {"card_id": "d1-news", "status": "DONE"},
            ],
            "finalize_day": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cards_updated"] == 3
    assert body["finalized"] is True
    assert "HISTORY" in body["confidences_updated"]
    assert "POLITY" in body["confidences_updated"]
    # NEWS_READING has no subject, shouldn't appear
    assert len(body["confidences_updated"]) == 2

    # Verify activity log was saved
    activity = memory_storage.get_activity_log("batch1", date(2026, 3, 2))
    assert activity is not None
    assert activity.finalized is True
    assert len(activity.entries) == 3


def test_integration_activity_log_saved_on_checkin(client, memory_storage):
    """Activity log is persisted with correct entries after check-in."""
    _setup_multi_card_user(memory_storage, "alog1")

    client.post(
        "/api/users/alog1/checkin/2026-03-03",
        json={
            "cards": [
                {"card_id": "d2-history", "status": "DONE"},
                {"card_id": "d2-economy", "status": "PARTIAL", "actual_duration": 60},
            ],
        },
    )

    activity = memory_storage.get_activity_log("alog1", date(2026, 3, 3))
    assert activity is not None
    assert len(activity.entries) == 2
    assert activity.finalized is False

    history_entry = next(e for e in activity.entries if e.card_id == "d2-history")
    assert history_entry.status == CheckInStatus.DONE
    assert history_entry.planned_duration == 45

    economy_entry = next(e for e in activity.entries if e.card_id == "d2-economy")
    assert economy_entry.status == CheckInStatus.PARTIAL
    assert economy_entry.actual_duration == 60


def test_integration_confidence_upsert_not_duplicate(client, memory_storage):
    """Multiple check-ins for same subject should upsert, not create duplicates."""
    _setup_multi_card_user(memory_storage, "upsert1")

    # Seed an initial confidence
    tc = TopicConfidence(user_id="upsert1", subject=Subject.HISTORY, perceived_confidence=2.0)
    memory_storage.save_topic_confidence("upsert1", tc)

    # Check in day 1
    client.post(
        "/api/users/upsert1/checkin/2026-03-02",
        json={"cards": [{"card_id": "d1-history", "status": "DONE"}]},
    )
    # Check in day 2
    client.post(
        "/api/users/upsert1/checkin/2026-03-03",
        json={"cards": [{"card_id": "d2-history", "status": "DONE"}]},
    )

    # Should have exactly 1 HISTORY confidence, not 3
    confs = memory_storage.get_topic_confidences("upsert1")
    history_confs = [c for c in confs if c.subject == Subject.HISTORY]
    assert len(history_confs) == 1
    assert history_confs[0].total_sessions == 2


def test_integration_day2_independent_of_day1(client, memory_storage):
    """Day 2 can be checked in without finalizing day 1."""
    _setup_multi_card_user(memory_storage, "indep1")

    # Check in day 2 first, leaving day 1 untouched
    resp = client.post(
        "/api/users/indep1/checkin/2026-03-03",
        json={
            "cards": [{"card_id": "d2-economy", "status": "DONE"}],
            "finalize_day": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["finalized"] is True

    # Day 1 should still be available for check-in
    resp = client.post(
        "/api/users/indep1/checkin/2026-03-02",
        json={"cards": [{"card_id": "d1-history", "status": "DONE"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["finalized"] is False


# ── Rebalance Tests ──────────────────────────────────────────────────


def _setup_rebalance_week(memory_storage, user_id="reb1"):
    """Create a user with a full 7-day plan for rebalance tests."""
    from datetime import timedelta

    profile = UserProfile(
        user_id=user_id,
        display_name="Rebalance User",
        stage="both",
        prelims_date=date(2026, 5, 25),
        mains_date=date(2026, 9, 19),
        available_hours_per_day=6.0,
    )
    memory_storage.save_user_profile(profile)

    week_start = date(2026, 3, 9)  # Monday
    days = []
    for i in range(7):
        day_date = week_start + timedelta(days=i)
        cards = [
            PlanCard(
                card_id=f"d{i}-history",
                block_type=BlockType.DEEP_STUDY,
                category=BlockCategory.CORE_LEARNING,
                subject=Subject.HISTORY,
                topic=f"Topic {i}",
                planned_duration=90,
                fatigue=2,
                order=0,
            ),
            PlanCard(
                card_id=f"d{i}-news",
                block_type=BlockType.NEWS_READING,
                category=BlockCategory.INPUT,
                subject=None,
                topic=None,
                planned_duration=20,
                fatigue=0,
                order=1,
            ),
        ]
        days.append(DailyPlan(date=day_date, cards=cards))

    plan = WeeklyPlan(
        user_id=user_id,
        week_start=week_start,
        days=days,
        narrative="Rebalance test week.",
    )
    memory_storage.save_weekly_plan(plan)
    return profile, plan


def test_rebalance_user_not_found(client):
    resp = client.post(
        "/api/users/nobody/plan/rebalance",
        json={"week_start": "2026-03-09", "recovery_window_days": 3},
    )
    assert resp.status_code == 404


def test_rebalance_plan_not_found(client, memory_storage):
    profile = UserProfile(
        user_id="reb_noplan",
        display_name="No Plan",
        stage="prelims",
        prelims_date=date(2026, 5, 25),
        available_hours_per_day=4.0,
    )
    memory_storage.save_user_profile(profile)

    resp = client.post(
        "/api/users/reb_noplan/plan/rebalance",
        json={"week_start": "2026-03-09", "recovery_window_days": 3},
    )
    assert resp.status_code == 404


def test_rebalance_invalid_window(client, memory_storage):
    """Recovery window outside 1-7 should fail validation."""
    _setup_rebalance_week(memory_storage, "reb_inv")

    resp = client.post(
        "/api/users/reb_inv/plan/rebalance",
        json={"week_start": "2026-03-09", "recovery_window_days": 0},
    )
    assert resp.status_code == 422

    resp = client.post(
        "/api/users/reb_inv/plan/rebalance",
        json={"week_start": "2026-03-09", "recovery_window_days": 8},
    )
    assert resp.status_code == 422


@patch("preptrack.api.routes.rebalance_plan")
def test_rebalance_success(mock_rebalance, client, memory_storage):
    """Successful rebalance returns correct response shape."""
    profile, plan = _setup_rebalance_week(memory_storage, "reb_ok")

    # Mock rebalance_plan to return updated plan with recovery info
    mock_rebalance.return_value = (
        plan,  # return same plan (in real case it'd be modified)
        [date(2026, 3, 10), date(2026, 3, 11)],  # missed dates
        [date(2026, 3, 12), date(2026, 3, 13), date(2026, 3, 14)],  # recovery dates
    )

    resp = client.post(
        "/api/users/reb_ok/plan/rebalance",
        json={"week_start": "2026-03-09", "recovery_window_days": 3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["missed_dates"] == ["2026-03-10", "2026-03-11"]
    assert body["recovery_dates"] == ["2026-03-12", "2026-03-13", "2026-03-14"]
    assert body["error"] is None

    # Recovery state should be saved
    rs = memory_storage.get_recovery_state("reb_ok")
    assert rs is not None
    assert rs.recovery_window_days == 3


@patch("preptrack.api.routes.rebalance_plan")
def test_rebalance_failure_returns_error(mock_rebalance, client, memory_storage):
    """PlanGenerationError during rebalance returns success=false with error message."""
    _setup_rebalance_week(memory_storage, "reb_fail")

    mock_rebalance.side_effect = PlanGenerationError("All retries exhausted")

    resp = client.post(
        "/api/users/reb_fail/plan/rebalance",
        json={"week_start": "2026-03-09", "recovery_window_days": 3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "All retries exhausted" in body["error"]
