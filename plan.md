# plan.md — Project Journal

## Overview

Building an adaptive UPSC study planner. Agentic AI at the core. Not a content platform — the orchestration layer for scheduling, personalization, and recovery.

Stack: Strands + Amazon Nova 2 Lite (Bedrock), Nova Act, React, DynamoDB, Cognito, Amplify.

---

## Build Order (Revised 2026-02-25)

### Completed
- [x] Step 1: Strands + Nova 2 Lite hello world — simple agent working end to end
- [x] Step 2: Reference corpus / Knowledge Base — 6 structured KB files created (block_definitions, confidence_model, engine_reference, phase_blueprints, rules, subject_weights). Stress tested with Claude chat mode.
- [x] Step 3: Plan generation logic validated — prompt + KB tested externally via Claude chat
- [x] Phase A: Pydantic models, deterministic engine (6 modules), DynamoDB Local storage, 87 unit tests
- [x] Phase C: Plan generation agent (Strands + engine validation loop), 138 non-integration tests
- [x] Phase D (API): FastAPI layer (4 endpoints, 15 tests)
- [x] Phase D (Frontend base): 6-step onboarding wizard, calendar with WeekOverview + DayDetail + Schedule Insights
- [x] Phase D (Engine tuning): NEWS/CA fixes, fatigue correction, R09 expansion, R21 validator. 193 tests passing
- [x] Phase D (UI polish): Two-column calendar layout, 7-day grid (no scroll), reschedule in header, mark complete inline with date. CSAT added to confidence step.
- [x] Phase E: Check-in + Confidence scoring — card-by-card Done/Partial/Skip, day finalization, deterministic confidence updates, confidence panel. 216 tests passing.
- [x] Phase F.1: Rebalancing agent + mid-week plans + debug dates — rebalancer backend, rebalance UI, narrative/insight panel, debug date system. 237 tests passing.

### Remaining — Reworked Build Phases

| Phase | What | Est. Days | Dependencies |
|-------|------|-----------|--------------|
| **A** | Data models + Engine — Pydantic models for all schemas. Engine: priority calculator, fatigue checker, constraint validator, rule evaluator. Local JSON storage with abstract interface. | 2-3 | None |
| **B** | KB loader — Parse 6 `knowledgebase/` files into structured Python objects (Pydantic models from Phase A) | 1 | A |
| **C** | Plan generation agent — Strands agent with real system prompt. Engine context packet → LLM → structured plan → engine validates → retry loop | 2-3 | A, B |
| **D** | Onboarding + Calendar UI — React frontend. Onboarding form, daily calendar cards, weekly progress bars | 2-3 | Can start parallel with C |
| **E** | Check-in + Confidence scoring — Done/partial/skip per card. Deterministic confidence updates (arithmetic, no AI) | 1-2 | D |
| **F** | Rebalancing agent — Recovery window selector → Strands agent reprioritizes → engine validates | 2 | A, C, E |
| **G** | Multi-week generation + auto-generation + cross-week rebalance (see Phase G Plan below) | 2 | C, E, F |
| **H** | AWS deployment — DynamoStore adapter (swap local JSON → DynamoDB), Lambda functions, Amplify frontend, Cognito auth | 2-3 | All above |
| **I** | Nova Act + Polish — Exam date fetch, loading states, demo flow | 1-2 | Cut if behind |

### Pending External
- [ ] Syllabus topic tree (will be added to `knowledgebase/` by hand)

---

## Frontend Stack (Decided 2026-02-25)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Build tool | Vite | Fast, no SSR needed — this is a SPA |
| Framework | React + TypeScript | Already decided in spec |
| Styling | Tailwind CSS | Fast iteration, no design system overhead |
| Components | shadcn/ui | Cards, buttons, sliders, progress bars — copy-paste, not a dependency |
| State | Zustand | Lightweight, minimal boilerplate for simple state |
| Data fetching | TanStack Query | Loading/error/cache states for slow Bedrock calls, built-in retry |

---

## DB Strategy (Decided 2026-02-25)

**Local-first, swap later.**

- Pydantic models define the schema once
- `LocalStore` (JSON files in `data/`) for development — git-tracked, reproducible
- `DynamoStore` adapter in Phase H — same interface, different backend
- Gives us: version control on test data, fast iteration, no AWS costs during dev, easy debugging

```
data/
  users/           # one JSON per test user
  plans/           # generated plans (versioned by timestamp)
  activity_log/    # check-in records
  confidence/      # per-topic confidence snapshots
```

---

## Session Log

### 2026-02-22 — Project kickoff

Set up repository. Wrote out full product spec covering all 6 features, tech stack, build order, and explicit scope cuts.

Immediate next goal: get a minimal Strands agent running with Amazon Nova 2 Lite on Bedrock. Prove the core AI loop works before touching any product features.

Questions to answer in Step 1:
- How do Strands agents get initialized and invoked?
- What does a simple Nova 2 Lite prompt/response cycle look like via Strands?
- What AWS credentials/region setup is needed for Bedrock access?
- What does a tool call look like in Strands (relevant for later validation hooks)?

### 2026-02-25 — Build planning session

Reviewed all docs (README, CLAUDE.md, architecture.md, all 6 KB files). Steps 2-3 done externally. KB is solid — block definitions, phase blueprints, subject weights, confidence model, rules, engine reference all structured and stress tested.

Reworked build order into 9 phases (A-I). Key decisions:
- Local-first development with JSON storage, swap to DynamoDB at deployment
- Pydantic models as single source of truth for schema (work with both local JSON and DynamoDB)
- Abstract storage interface pattern (LocalStore → DynamoStore)
- Frontend: Vite + React + TS, Tailwind, shadcn/ui, Zustand, TanStack Query
- Starting Phase A: data models + deterministic engine

### 2026-03-01 — Phase D: API + Frontend

FastAPI API layer (4 endpoints, 15 tests). React frontend with 5-step onboarding wizard and basic calendar grid.

### 2026-03-02 — Phase D Revision: Frontend Redesign

Onboarding expanded 5→6 steps: new optional subject page, exam cycle selector (replaces date picker), multi-select time preferences. Calendar redesigned: WeekOverview (compact day cards), DayDetail (selected day view), Schedule Insights (replaces narrative). No red/warning colors — green for progress, gray for pending, amber for selected.

### 2026-03-02 — Engine Tuning: NEWS/CA/Fatigue/R09

Series of engine fixes driven by integration testing across 4h and 10h user profiles:
1. NEWS_READING fatigue → 0, CA_INTEGRATION governed by R21 (hard, max 1/week)
2. `_correct_fatigue()` deterministic post-processor for LLM fatigue mistakes
3. Pre-computed fatigue cap injected into prompt (LLM was miscalculating)
4. R09 expanded for 8h+ users (CL max 3, CR max 5), depth-over-breadth guidance
5. R09 CR violations downgraded to warning on light-only days (all fatigue ≤ 2)

193 tests passing (32 validator, 161 others). Still in Phase D — UI tweaks pending.

### 2026-03-07 — Phase E: Check-in + Confidence Scoring

Backend: 2 new endpoints added to FastAPI.
- `POST /api/users/{user_id}/checkin/{checkin_date}` — card-by-card check-in (DONE/PARTIAL/SKIPPED), optional day finalization (remaining PENDING → SKIPPED), deterministic confidence updates via `process_checkin()`, activity log saving.
- `GET /api/users/{user_id}/confidence` — returns all topic confidence scores for a user.

Schemas: `CardCheckIn`, `CheckInRequest`, `CheckInResponse` added to `schemas.py`.

Bug fix: `MemoryStorage.save_topic_confidence()` was appending duplicates — fixed to upsert by subject.

Frontend:
- `PlanCardItem` — inline check-in controls (Done/Partial/Skip buttons), partial duration slider, status visuals (green/amber/gray left borders + badges).
- `DayDetail` — wired check-in callbacks, "Mark Complete" button enabled when ≥1 card checked in.
- `CalendarView` — orchestrates `useCheckIn` mutation + `useConfidence` query, passes handlers to DayDetail, renders ConfidencePanel in left sidebar.
- `ConfidencePanel` (new) — per-subject confidence bars (1–5 scale), sorted weakest-first, streak counts, trend arrows (↑/→/↓), empty state message.

New files: `api/checkin.ts`, `hooks/useCheckIn.ts`, `hooks/useConfidence.ts`, `components/calendar/ConfidencePanel.tsx`.

Tests: 216 passing (was 193). Breakdown of new tests:
- 11 unit tests in `test_api.py` (single-card DONE/PARTIAL/SKIP, finalize, 409, 404s, no-subject skip, confidence CRUD)
- 7 API-level integration tests (full-day flow, cross-day confidence accumulation, skip→done streak reset, batch check-in, activity log, upsert dedup, day independence)
- 5 DynamoDB integration tests in `test_storage.py` (card status persistence, finalize round-trip, confidence upsert, multi-subject independence, activity log entries)

### 2026-03-10 — Phase F.1: Rebalancing Agent + Mid-Week Plans + Debug Dates

**Rebalancing agent** (`preptrack/agent/rebalancer.py`):
- Day classification: frozen (DONE/PARTIAL engagement), missed (past or finalized with no engagement), eligible (today+ unfrozen).
- Missed content extracted as subject-level summary (not card-by-card) to prevent LLM overstuffing.
- Fatigue carryover: counts consecutive heavy frozen days before recovery window for R13 enforcement.
- CA Integration count from frozen days for R21 enforcement.
- LLM proposes recovery days → deterministic fatigue correction → R13 repair → full-week validation → retry loop (max 3).
- Returns narrative/summary alongside the rebalanced plan.

**Rebalance prompt** (`preptrack/agent/prompt.py`):
- `build_rebalance_prompt()` with recovery-specific context: missed content summary, frozen day constraints, fatigue cap as hard ceiling.
- Output schema includes `"narrative"` field for AI-generated rebalance insight.

**Mid-week plan generation** (`preptrack/agent/planner.py`):
- `generate_plan()` accepts `plan_start: date | None` — generates from that date to Sunday (1-7 days).
- Plans still keyed by Monday in storage for consistent week lookup.

**Debug date system** (`frontend/src/lib/debug.ts`):
- `?debug_date=YYYY-MM-DD` query param overrides "today" throughout the entire stack.
- `getToday()`, `getTodayStr()`, `getDebugDate()` helpers used by all components.
- Debug badge shown in header when active. Flows through API calls to backend.

**API** (`preptrack/api/routes.py`, `schemas.py`):
- `POST /users/{user_id}/plan/rebalance` — accepts `RebalanceRequest(week_start, recovery_window_days, debug_date)`, returns `RebalanceResponse` with `narrative`.
- Onboard + Generate endpoints accept `debug_date` and pass as `plan_start`.

**Frontend**:
- Rebalance button in header (amber theme, dropdown with recovery window slider 1-7 days).
- `RebalanceInsight` component — amber-bordered card with AI badge at top of left sidebar, dismissable.
- `WeekOverview` uses `todayStr` prop for debug-aware today highlighting.
- Rebalance eligibility: `missedCount > 0 && eligibleCount > 0`.

**New files**: `rebalancer.py`, `RebalanceInsight.tsx`, `debug.ts`, `api/rebalance.ts`, `hooks/useRebalance.ts`, `hooks/useConfidence.ts`, `ConfidencePanel.tsx`, `test_rebalancer.py`, `test_rebalancer_integration.py`.

**Tests**: 237 passing (16 rebalancer unit, 5 rebalancer API, 11 integration tests).

### 2026-03-12 — Phase F.1 Polish: Timezone Fix, Auto-Finalization, Rebalance Eligibility

**Timezone fix** (`frontend/src/lib/debug.ts`):
- `getTodayStr()` was using `toISOString().slice(0, 10)` which converts to UTC — could disagree with backend's `date.today()` (local time) near midnight. Fixed to use `getFullYear()/getMonth()/getDate()` (local time). Frontend and backend now consistently use local timezone.

**Rebalance auto-finalization** (`CalendarView.tsx`):
- Before rebalancing, any past unfinalized days are detected — including partially done days (some DONE/PARTIAL cards but not "Mark Complete"d).
- Two-step flow: user clicks "Rebalance" → if unfinalized past days exist, a confirmation step warns which days (e.g. "Mon 9, Tue 10") will be marked as skipped → user clicks "Skip & Rebalance" to confirm → app finalizes each day (PENDING cards → SKIPPED, DONE/PARTIAL untouched) → then triggers rebalance.
- If all past days are already finalized, rebalance triggers directly (no extra step).

**Rebalance eligibility fix** (`CalendarView.tsx`):
- Bug: after a successful rebalance, the "Rebalance Week" button stayed active because finalized-skipped days (e.g. days closed by the auto-finalization) still counted as "missed" in `missedCount`.
- Fix: `missedCount` now only counts **unfinalized** past days with no engagement. Finalized days (whether completed or all-skipped after rebalance) are considered closed — their content has already been dealt with. After a successful rebalance, `missedCount` drops to 0 and the button disables.

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-22 | Agent proposes, deterministic code validates | Keeps AI output quality consistent; bad plans rejected before user sees them |
| 2026-02-22 | Hardcode syllabus RAG, no runtime crawling | UPSC syllabus hasn't changed meaningfully since 2013; complexity not worth it |
| 2026-02-22 | Nova Act only for exam date fetch | Appropriate, focused use; scales to multi-exam expansion later |
| 2026-02-22 | Generate 4-6 weeks at a time, not full plan | Avoids stale long-range plans; learning profile keeps future weeks accurate |
| 2026-02-22 | Confidence scoring is deterministic arithmetic, not AI | Fast, predictable, no latency; AI not needed for simple score updates |
| 2026-02-25 | Local-first with JSON → DynamoDB swap | Fast iteration, git-tracked test data, no deploy cycles during dev |
| 2026-02-25 | Pydantic models as schema source of truth | Same models serialize to JSON locally or DynamoDB — define once, use everywhere |
| 2026-02-25 | Vite + Tailwind + shadcn/ui for frontend | Fastest path to a nice UI without framework overhead |
| 2026-02-25 | Zustand for state, TanStack Query for data | Lightweight, minimal boilerplate, handles slow AI calls gracefully |

---

## Open Questions

- DynamoDB schema design for learning profile cache (defer to Phase H)
- Syllabus topic tree structure (pending user addition)

## Action Items

### NEWS + CA Block Frequency
**Status**: Resolved
**Resolution**: NEWS_READING fatigue → 0 (fixed overhead, not cognitive load). R21 (CA Integration Frequency) added as hard rule — CA_INTEGRATION max 1/week, validator enforced. 4h user now converges on first attempt.

### Duration-Based Fatigue Correction
**Status**: Resolved
**Resolution**: LLM frequently assigned wrong fatigue to duration-sensitive blocks (e.g., 90-min DEEP_STUDY getting fatigue 3 instead of 2). Added `_correct_fatigue()` deterministic post-processor in planner.py that overwrites all card fatigue with correct values from block definitions. Runs before R13 repair and validation.

### R09 Update for 8h+ Users
**Status**: Resolved
**Resolution**: 10h users kept violating R09 (3+ CL subjects, 6+ CR subjects). Root causes: (1) LLM miscalculating fatigue cap — fixed by pre-computing cap in engine and injecting into prompt. (2) LLM defaulting to short blocks across many subjects instead of deeper sessions on fewer — fixed with "depth over breadth" prompting guidance. (3) Hard limits too tight for high-hours users — expanded: CL max 3 (was 2) and CR max 5 (was 4) when `available_hours >= 8`. R10 merged into R09.

### R09 CR Light-Day Severity Downgrade
**Status**: Resolved
**Resolution**: 10h user's review/consolidation days (e.g., Sunday with 6 REVISION blocks at fatigue 1) were rejected for exceeding CR subject cap. These are perfectly valid light days. Fix: CR violations downgraded from "error" to "warning" when ALL blocks on that day have fatigue ≤ 2. `validate_weekly_plan` now only counts error-severity violations for plan rejection — warnings are logged but don't burn retries.

### Low-Hours User Fatigue Convergence
**Status**: Deferred
**Gap**: Users with ≤4 available_hours_per_day occasionally fail to converge within 3 retries due to tight fatigue caps. The LLM struggles to fit meaningful study blocks under a cap of 8 (4h × 2). Not blocking — works most of the time, but needs prompt tuning or a relaxed cap formula for low-hours users in a future pass.

### CSAT Confidence Collection
**Status**: Resolved
**Resolution**: CSAT added to confidence step in onboarding. Initialized to 3 in wizard state, displayed after mains subjects (before optional) with "Prelims" paper tag. R01 (CSAT Bump) now has a real confidence value to work with.

### MemoryStorage Confidence Upsert
**Status**: Resolved
**Resolution**: `MemoryStorage.save_topic_confidence()` was appending blindly, creating duplicate entries per subject. Fixed to upsert by subject — scans existing list, replaces matching entry or appends if new. Verified with integration test (`test_integration_confidence_upsert_not_duplicate`).

## Resolved

- Strands SDK: `pip install strands-agents strands-agents-tools` (also needs `botocore[crt]`)
- Nova 2 Lite model ID: `us.amazon.nova-2-lite-v1:0` (cross-region) or `amazon.nova-2-lite-v1:0` (direct, us-east-1)
- Bedrock setup: just enable model access in console, everything else is in code via Strands
- Agent init: `BedrockModel(model_id=..., region_name=..., streaming=True)` → `Agent(model=model)`
- System prompt is static (agent personality/rules), user prompt is dynamic (built per request by app code)
- Frontend stack: Vite, React+TS, Tailwind, shadcn/ui, Zustand, TanStack Query
- DB strategy: local JSON first, DynamoDB later via storage abstraction

---

## Phase G Plan: Multi-Week Generation + Auto-Generation + Cross-Week Rebalance

### Context

Phases A–F.1 complete. The system generates a single week, supports check-in, confidence tracking, and within-week rebalancing. Phase G adds forward-looking scheduling and cross-week recovery.

### Three Sub-Features

**G.1 — Manual multi-week generation (current + 2 weeks ahead)**
- "Generate Ahead" button in the calendar UI
- User can generate up to 2 additional weeks beyond the current week
- Each week is a separate `WeeklyPlan` in storage, keyed by its Monday
- Generation uses latest confidence scores + completion history from prior weeks
- UI shows how many weeks exist vs available (e.g. "1/3 weeks generated")
- If a week already exists, skip it (don't regenerate)
- Week navigation (prev/next) works as-is — storage lookup by Monday, no changes needed

**G.2 — Auto-generation on second-to-last day**
- Frontend-driven `useEffect` check — no backend cron
- When `todayStr` is the second-to-last day of the current week's plan AND next week doesn't exist → auto-generate
- Show a banner/toast: "Next week is approaching — generating your schedule"
- Uses the same `generate_plan` pipeline with fresh confidence data

**G.3 — Cross-week rebalance**
- Current-week rebalance stays exactly as-is (recovery window within the week)
- New options in the rebalance dropdown:
  - **"Include next week"** — rebalance current week as normal, then generate next week fresh with missed content as priority context
  - **"Include next 2 weeks"** — same, generates up to 2 additional weeks
- Cross-week "rebalance" for next week(s) = **full generation via planner** (not the rebalancer re-slotting cards). The rebalancer only touches the current week.
- Each additional week is validated independently (per-week validation, no cross-week rule merging)
- No partial next-week recovery windows — each added week is generated in full. Partial next-week generation is a future enhancement.

### Key Design Decision: Missed Context

The planner gets a new optional parameter: `missed_context: dict[Subject, int]` (subject → total missed minutes from current week). This flows into the prompt as a priority hint: "the user fell behind on these subjects, prioritize accordingly." The planner weights those subjects higher in generation. This is lighter than passing raw missed cards — just subject-level summary.

### Backend Changes

| File | Change |
|------|--------|
| `planner.py` | `generate_plan()` accepts optional `missed_context: dict[Subject, int]`. Passed to prompt builder. |
| `prompt.py` | `build_plan_prompt()` accepts optional `missed_context`. Adds a "Priority Recovery" section to the prompt listing subjects + missed minutes. |
| `routes.py` | New `POST /users/{user_id}/plan/generate-ahead` — accepts `GenerateAheadRequest(weeks_ahead, debug_date)`. Generates up to N weeks ahead, skipping existing. Returns list of week_starts generated. |
| `routes.py` | Update rebalance endpoint — accept `include_next_weeks: int` (0, 1, or 2). After current-week rebalance, generate next week(s) via planner with `missed_context` extracted from current week's missed days. |
| `schemas.py` | `GenerateAheadRequest(weeks_ahead: int, debug_date?)`, `GenerateAheadResponse(weeks_generated: list[str])` |
| `schemas.py` | Add `include_next_weeks: int = 0` to `RebalanceRequest` |
| `rebalancer.py` | Add helper to extract `missed_context` from missed days (subject → total minutes). Exported for use by routes. |

### Frontend Changes

| File | Change |
|------|--------|
| `types/index.ts` | `GenerateAheadRequest`, `GenerateAheadResponse` types. Add `include_next_weeks` to `RebalanceRequest`. |
| `api/` | New `generateAhead()` API call |
| `hooks/` | New `useGenerateAhead()` mutation hook |
| `CalendarView.tsx` | "Generate Ahead" button. Auto-generation `useEffect` on second-to-last day. Rebalance dropdown gets "Include next week" / "Include next 2 weeks" toggle. Banner for auto-generation. |

### Build Order

| Step | What |
|------|------|
| 1 | Backend: add `missed_context` param to `generate_plan` + `build_plan_prompt` |
| 2 | Backend: add `generate-ahead` endpoint |
| 3 | Backend: update rebalance endpoint for `include_next_weeks` |
| 4 | Backend: extract `missed_context` helper in rebalancer |
| 5 | Tests: generate-ahead, cross-week rebalance |
| 6 | Frontend: "Generate Ahead" button + API hook |
| 7 | Frontend: auto-generation `useEffect` + banner |
| 8 | Frontend: rebalance dropdown cross-week toggle |

---

## Phase D Plan: Onboarding + Calendar UI (FastAPI + React)

### Context

Phases A-C complete. No HTTP layer, no frontend. Phase D adds FastAPI API + React frontend with onboarding and calendar view.

### Architecture

```
Browser (Vite :5173)
  ├─ Onboarding Wizard → POST /api/users/onboard
  │     Creates UserProfile + TopicConfidence → generate_plan() → WeeklyPlan
  └─ Calendar View → GET /api/users/{id}/plan?week_start=...
        Renders 7-day grid of PlanCards

FastAPI (:8080)
  ├─ routes.py → deps.py (StorageBackend via DI)
  │                 └─ DynamoLocalStorage (localhost:8000)
  └─ routes.py → generate_plan() (Bedrock Nova 2 Lite)
```

### Key Decisions

| Decision | Choice | Why |
|---|---|---|
| API port | 8080 | DynamoDB Local on 8000 |
| Plan generation | Synchronous + loading spinner | Hackathon simplicity |
| CORS | FastAPI CORSMiddleware → localhost:5173 | Standard local dev |
| Routing | Conditional render (no React Router) | Only 2 views |
| State persistence | Zustand + localStorage | Keep session on refresh |
| FastAPI deps | Add to existing pyproject.toml | One project |

### Part 1: FastAPI API Layer

**Files:**
- `preptrack/api/__init__.py` — empty
- `preptrack/api/app.py` — FastAPI app + CORS
- `preptrack/api/deps.py` — `get_storage()` → DynamoLocalStorage (lru_cache)
- `preptrack/api/schemas.py` — OnboardRequest, OnboardResponse, GeneratePlanRequest
- `preptrack/api/routes.py` — 4 endpoints
- `tests/test_api.py` — mocked storage + agent

**Endpoints:**

| Endpoint | Method | What |
|---|---|---|
| `/api/users/onboard` | POST | Create profile + confidences, generate plan, return all |
| `/api/users/{user_id}` | GET | Profile + confidences |
| `/api/users/{user_id}/plan` | GET | WeeklyPlan for ?week_start= |
| `/api/users/{user_id}/plan/generate` | POST | Trigger new plan generation |

**pyproject.toml:** Add `fastapi>=0.115.0`, `uvicorn[standard]>=0.30.0`

### Part 2: React Frontend

**Scaffold:** `npm create vite@latest frontend -- --template react-ts` + Tailwind + shadcn/ui + Zustand + TanStack Query + date-fns

**Onboarding (4 steps):**
1. Name, stage (prelims/mains/both), optional subject
2. Exam dates (based on stage)
3. Hours per day (1-16)
4. Confidence sliders per subject (1-5, step 0.5)

Submit → POST /api/users/onboard → LoadingScreen (10-30s) → Calendar

**Calendar:**
- WeekView: 7-column CSS Grid (Mon-Sun), mobile stacks
- DayColumn: date header + stacked PlanCardItems
- PlanCardItem: subject badge (color by category), topic, duration, block type, fatigue dots
- WeekNarrative: AI strategy explanation
- WeekNavigation: prev/next week arrows

**Colors:** CORE_LEARNING=blue, CORE_RETENTION=green, PERFORMANCE=purple, CORRECTIVE=red, INPUT=amber, META=gray

### Build Order

| Step | What | Est. |
|------|------|------|
| 1 | FastAPI skeleton (app, deps, schemas, routes) | ~1h |
| 2 | API tests (test_api.py) | ~30m |
| 3 | Vite + React scaffold + deps + types + store + API client | ~1h |
| 4 | Onboarding wizard (4 steps + loading screen) | ~2-3h |
| 5 | Calendar view (week grid + cards + narrative + navigation) | ~2-3h |
| 6 | Polish (loading skeletons, error states, mobile) | ~1h |

### Verification

```bash
# Backend tests
pytest tests/test_api.py -v
pytest tests/ -v -m "not integration"

# End-to-end (3 terminals)
# T1: java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb
# T2: uvicorn preptrack.api.app:app --reload --port 8080
# T3: cd frontend && npm run dev
# Open http://localhost:5173
```
