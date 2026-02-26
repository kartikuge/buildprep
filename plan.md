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

### Remaining — Reworked Build Phases

| Phase | What | Est. Days | Dependencies |
|-------|------|-----------|--------------|
| **A** | Data models + Engine — Pydantic models for all schemas. Engine: priority calculator, fatigue checker, constraint validator, rule evaluator. Local JSON storage with abstract interface. | 2-3 | None |
| **B** | KB loader — Parse 6 `knowledgebase/` files into structured Python objects (Pydantic models from Phase A) | 1 | A |
| **C** | Plan generation agent — Strands agent with real system prompt. Engine context packet → LLM → structured plan → engine validates → retry loop | 2-3 | A, B |
| **D** | Onboarding + Calendar UI — React frontend. Onboarding form, daily calendar cards, weekly progress bars | 2-3 | Can start parallel with C |
| **E** | Check-in + Confidence scoring — Done/partial/skip per card. Deterministic confidence updates (arithmetic, no AI) | 1-2 | D |
| **F** | Rebalancing agent — Recovery window selector → Strands agent reprioritizes → engine validates | 2 | A, C, E |
| **G** | Auto-generation — On week completion, fetch learning profile, generate next batch via Phase C pipeline | 1 | C, E |
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

## Resolved

- Strands SDK: `pip install strands-agents strands-agents-tools` (also needs `botocore[crt]`)
- Nova 2 Lite model ID: `us.amazon.nova-2-lite-v1:0` (cross-region) or `amazon.nova-2-lite-v1:0` (direct, us-east-1)
- Bedrock setup: just enable model access in console, everything else is in code via Strands
- Agent init: `BedrockModel(model_id=..., region_name=..., streaming=True)` → `Agent(model=model)`
- System prompt is static (agent personality/rules), user prompt is dynamic (built per request by app code)
- Frontend stack: Vite, React+TS, Tailwind, shadcn/ui, Zustand, TanStack Query
- DB strategy: local JSON first, DynamoDB later via storage abstraction
