# PrepTrack

**Adaptive UPSC Study Planner**

> You bring your goals. We build your plan from real topper strategies. We rebuild it every time life gets in the way.

**Mission:** Optimising AI so it does not lead your prep astray.

---

## Problem

UPSC aspirants spend 8–12 months preparing across a massive syllabus using multiple resources. They find a generic plan that assumes the same starting point as everyone else, follow it for two weeks, miss a few days — and the plan is dead. There is no mechanism to adapt.

Content platforms deliver lessons and questions. Nobody solves **scheduling, personalization, and recovery**.

## What This Is

Not a content platform. Not a question bank. The **orchestration layer** — it plans *what* you study, *when*, and *what happens when you fall behind*, regardless of which resources you use.

Category: Agentic AI · Core model: Amazon Nova 2 Lite via Strands · Supporting: Nova Act

---

## The Core Idea

Letting an LLM freestyle a 6-month study plan produces something that looks plausible and falls apart on contact with reality — overloaded days, the same subtopic twice, three heavy sessions back to back, a "revision" phase that never revises.

PrepTrack splits the job in two:

> **The agent proposes. Deterministic code validates.**

Strategy is genuinely hard and contextual — that's the LLM's job. Constraint satisfaction is arithmetic — that's the engine's job. Nothing reaches the user until it has passed every rule.

| Layer | Role | Implementation |
|-------|------|----------------|
| **Knowledge Base** | The playbook — strategic logic encoded as structure | Static config, hand-structured |
| **Engine** | The referee — does the math, enforces the rules, rejects bad output | Deterministic Python, no AI |
| **Agent** | The coach — makes judgment calls within the rules | Nova 2 Lite via Strands |
| **User State** | The player's stats — confidence, history, behaviour | DynamoDB |

### What the engine decides (deterministic)

Current phase from days-to-exam · weekly minute budget · per-subject priority scores `(1 − confidence/5) × subject_weight × recency_penalty` · daily fatigue caps · block compatibility · subtopic de-duplication · topic diversity · GS/optional floors · confidence updates.

### What the agent decides (strategic)

Which subjects get which *kind* of session — a subject at low confidence needs deep study, one that's nearly there needs timed practice, and that mapping is coaching logic, not a formula. Also: the GS-to-optional ratio each week, what to sacrifice when a week has to be compressed, and a short weekly narrative explaining *why* the plan changed.

### The validation loop

```
Engine builds context packet  (phase, priorities, budget, constraints, history)
        │
        ▼
Nova 2 Lite proposes a week
        │
        ▼
Deterministic post-processors  (fatigue correction, consecutive-heavy-day repair)
        │
        ▼
Validator ──── violations? ──► back to the LLM with the exact rule IDs it broke
        │                       (up to 3 attempts)
        ▼
    Clean plan ──► user
```

Two classes of failure are handled differently. Things the LLM reliably gets *wrong but mechanically* — assigning the wrong fatigue weight to a 90-minute block, for example — are simply overwritten by the engine rather than sent back for a retry. Things that need re-planning go back as a targeted list of violated rules. Same validator runs on first generation, on rebalancing, and on auto-generated future weeks.

---

## Architecture

```
┌──────────────────────────── React + TypeScript (Vite) ────────────────────────────┐
│  Onboarding wizard (6 steps)          Calendar (week overview → day detail)       │
│  Confidence panel                     Check-in · Rebalance · Generate Ahead       │
└───────────────────────────────────────┬───────────────────────────────────────────┘
                                        │  REST
┌───────────────────────────────────────▼───────────────────────────────────────────┐
│                                FastAPI                                            │
│   onboard · get plan · generate · generate-ahead · check-in · rebalance · confid. │
└───────┬───────────────────────────────────────────────────────┬───────────────────┘
        │                                                       │
┌───────▼─────────────────────┐                     ┌───────────▼───────────────────┐
│  ENGINE (deterministic)     │                     │  AGENTS (Strands / Nova 2)    │
│  ─────────────────────────  │◄────validates───────│  ───────────────────────────  │
│  phase      priority        │                     │  planner    (generation)      │
│  allocator  fatigue         │─────context────────►│  rebalancer (recovery)        │
│  validator  confidence      │                     │  prompt assembly              │
└───────┬─────────────────────┘                     └───────────────────────────────┘
        │                                                       ▲
┌───────▼─────────────────────┐                     ┌───────────┴───────────────────┐
│  STORAGE (abstract backend) │                     │  KNOWLEDGE BASE (static)      │
│  Users · Plans · Activity   │                     │  block definitions            │
│  TopicConfidence            │                     │  phase blueprints             │
│  LearningProfile · Recovery │                     │  subject weights · rules      │
│  → DynamoDB Local → DynamoDB│                     │  confidence model             │
└─────────────────────────────┘                     └───────────────────────────────┘
```

### Knowledge Base

Strategy logic encoded as *structure*, not content. It does not say "study Polity on Monday at 8 PM." It says things like "in this phase, revision dominates and deep study is capped" and "only N subjects may be in a learning block on the same day." The schedule is generated *from* the rules.

Four pieces, each hand-structured from real topper and institute study plans:

- **Block definitions** — ~20 atomic session types (deep study, revision, PYQ analysis, timed MCQ, answer writing, error analysis, weak-area drill, full mock, consolidation…) each carrying a fatigue weight, duration range, ordering requirements, incompatibilities, and which phases allow it.
- **Phase blueprints** — five phases (foundation → consolidation → prelims sprint → mains sprint → interview), each with a block-mix distribution and its own constraint set. Phase transition is time-based and computed by the engine.
- **Subject weights** — static exam importance per subject, separately for prelims and mains, so niche topics can't be over-allocated.
- **Rules registry** — numbered hard and soft rules (R01…R22) covering fatigue, sequencing, isolation of mocks, per-day subject caps, current-affairs cadence, and mock frequency. Hard rules are validator-enforced; the rule IDs are what the retry loop hands back to the LLM.

*The KB parameters themselves — exact distributions, caps and thresholds — are the product. They live in `knowledgebase/` and aren't reproduced here.*

### Confidence: deterministic, not AI

Every check-in updates a per-subject confidence score (1.0–5.0) with pure arithmetic — streak milestones, cumulative-session milestones, escalating skip penalties, and inactivity decay with a maintenance floor for well-established subjects. No model call, no latency, fully predictable, and testable to the decimal.

That score feeds straight back into the priority formula, which closes the loop: complete a subject consistently → confidence rises → it earns less time next week. Skip it → it gets more. Plans get sharper with use instead of repeating themselves.

---

## Features

| # | Feature | AI? | Status |
|---|---------|-----|--------|
| 1 | **Onboarding** — optional subject, stage, exam cycle, hours/day, preferred time blocks, self-assessed confidence per subject | No | ✅ |
| 2 | **Plan generation** — context packet → Nova 2 Lite → validation loop → a week of calendar cards with subtopic + duration + rationale | Nova 2 Lite | ✅ |
| 3 | **Calendar UI** — week overview with completion bars, day detail with per-card actions, weekly narrative, schedule insights | No | ✅ |
| 4 | **Check-in** — per-card done / partial (minutes) / skipped, day finalization, live confidence panel | No | ✅ |
| 5 | **Agentic rebalancing** — pick a recovery window, agent re-slots missed content inside a hard boundary while respecting fatigue carried over from days already spent | Nova 2 Lite | ✅ |
| 6 | **Multi-week + auto-generation** — generate up to 2 weeks ahead, auto-trigger near week's end, cross-week recovery that carries net-missed content forward | Nova 2 Lite | ✅ |
| 7 | **Exam date fetch** — UPSC CSE dates from upsc.gov.in, cached | Nova Act | ⬜ |
| 8 | **Auth + AWS deployment** — Cognito, Lambda, Amplify, managed DynamoDB | — | ⬜ |

### Rebalancing, in detail

The interesting part isn't "redistribute the missed work." It's everything that has to stay true afterwards.

When you miss days, the rebalancer first **classifies** every day in the week: *frozen* (already happened — untouchable), *missed* (no engagement, needs recovery), *eligible* (still ahead of you, fair game). Then it computes what the frozen days already cost you in fatigue, so the recovery days can't stack four heavy sessions on top of a week that was already heavy. Missed content is extracted, the agent re-plans **only** the eligible days inside your chosen window, and the **whole week** — frozen days included — is re-validated before anything is saved.

Cross-week recovery goes one step further. When the overflow can't fit in the current week, future weeks are regenerated with a priority hint for what you're behind on — computed as *net* missed work: raw missed minus whatever the rebalancer already re-slotted into this week's recovery days. Subjects you've genuinely caught up on drop out of the hint entirely, so next week doesn't re-teach material you just covered.

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Agents | AWS Strands SDK + **Amazon Nova 2 Lite** (Bedrock) | Large context window means the KB and syllabus load directly into the prompt — no RAG infrastructure needed |
| Backend | Python, FastAPI, Pydantic | Pydantic models are the single schema source of truth — same models serialize to local JSON or DynamoDB |
| Frontend | Vite + React + TypeScript, Tailwind, shadcn/ui | SPA, no SSR needed; fast iteration without design-system overhead |
| State | Zustand + TanStack Query | Minimal boilerplate; Query handles the slow Bedrock round-trips with real loading/retry states |
| Database | DynamoDB (local for dev) | Behind an abstract `StorageBackend` — swapping to managed DynamoDB is an endpoint change |
| Browser automation | Nova Act | One focused job: exam date fetching |
| Hosting | Lambda + Amplify, Cognito auth | Planned |

## Project Structure

```
preptrack/
  models/     Pydantic schemas — enums, KB, plan, user (schema source of truth)
  kb/         Structured knowledge base registries + markdown loader for prompt context
  engine/     Deterministic core — phase, priority, allocator, fatigue, validator, confidence
  agent/      Strands agents — planner, rebalancer, prompt assembly
  api/        FastAPI app, routes, request/response schemas
  storage/    Abstract StorageBackend + DynamoDB Local implementation
frontend/     React SPA — onboarding wizard, calendar, check-in, rebalance
knowledgebase/  The playbook (block definitions, phase blueprints, weights, rules)
tests/        262 tests — 235 deterministic + 27 integration
```

## Testing

```bash
pytest tests/ -q -m "not integration"     # 235 deterministic tests, offline, ~1.5s
pytest tests/ -q                          # all 262 — adds live Bedrock + DynamoDB Local
```

**262 tests, two tiers.**

**235 deterministic** — the engine rule-by-rule, the agent's validation and repair loop against recorded LLM output, confidence arithmetic at every milestone boundary, storage round-trips, and the full API surface. No network, runs in ~1.5 seconds.

**27 integration, all passing** — 15 drive the real Strands agents against live Nova 2 Lite on Bedrock and assert the output survives the constraint checks end to end: a generated week is well-formed and within block duration limits; a rebalanced week leaves already-completed days intact, hits the minimum-utilization floor on recovery days, and still satisfies the fatigue cap, the current-affairs cadence rule, and the consecutive-heavy-day limit. The remaining 12 exercise storage against a real DynamoDB Local instance, including check-in persistence and confidence upsert behaviour.

They're marked rather than skipped: excluded from the default run for speed and Bedrock cost, not because they're unreliable. Run them with credentials and DynamoDB Local up.

## Local Development

Three terminals — DynamoDB Local, the API, and the Vite dev server. See `SETUP.txt` for exact commands. A `?debug_date=YYYY-MM-DD` query parameter overrides "today" across the entire stack, which makes multi-week behaviour (auto-generation, frozen-day classification, cross-week recovery) testable without waiting a week.

## Status

Phases A–G complete: data models, deterministic engine, knowledge base, plan generation agent, onboarding + calendar UI, check-in + confidence scoring, rebalancing agent, and multi-week generation. All 262 tests green, including live-Bedrock agent runs.

Remaining: AWS deployment (DynamoDB, Lambda, Amplify, Cognito), Nova Act exam-date fetch, polish.

See `plan.md` for the full project journal, decisions log, and tech debt register, and `architecture.md` for the complete design.

## Out of Scope

PYQ trend analysis, current affairs content, resource recommendations, content delivery, PDF upload, mock score parsing, any exam beyond UPSC CSE.
