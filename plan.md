# plan.md — Project Journal

## Overview

Building an adaptive UPSC study planner. Agentic AI at the core. Not a content platform — the orchestration layer for scheduling, personalization, and recovery.

Stack: Strands + Amazon Nova 2 Lite (Bedrock), Nova Act, React, DynamoDB, Cognito, Amplify.

---

## Build Order

- [x] Step 1: Strands + Nova 2 Lite hello world — get a simple agent working end to end
- [ ] Step 2: Reference corpus research + syllabus structuring (no RAG — full context injection)
- [ ] Step 3: Plan generation agent from hardcoded inputs (prove AI works)
- [ ] Step 4: Onboarding UI + calendar view
- [ ] Step 5: Check-in + rebalancing agent with deterministic validation
- [ ] Step 6: Learning profile cache + confidence scoring
- [ ] Step 7: Auto-generation of next weeks
- [ ] Step 8: Cognito auth
- [ ] Step 9: Nova Act exam date fetching
- [ ] Step 10: Polish, loading states, demo flow

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

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-22 | Agent proposes, deterministic code validates | Keeps AI output quality consistent; bad plans rejected before user sees them |
| 2026-02-22 | Hardcode syllabus RAG, no runtime crawling | UPSC syllabus hasn't changed meaningfully since 2013; complexity not worth it |
| 2026-02-22 | Nova Act only for exam date fetch | Appropriate, focused use; scales to multi-exam expansion later |
| 2026-02-22 | Generate 4-6 weeks at a time, not full plan | Avoids stale long-range plans; learning profile keeps future weeks accurate |
| 2026-02-22 | Confidence scoring is deterministic arithmetic, not AI | Fast, predictable, no latency; AI not needed for simple score updates |

---

## Open Questions

- DynamoDB schema design for learning profile cache (defer to Step 6)

## Resolved

- Strands SDK: `pip install strands-agents strands-agents-tools` (also needs `botocore[crt]`)
- Nova 2 Lite model ID: `us.amazon.nova-2-lite-v1:0` (cross-region) or `amazon.nova-2-lite-v1:0` (direct, us-east-1)
- Bedrock setup: just enable model access in console, everything else is in code via Strands
- Agent init: `BedrockModel(model_id=..., region_name=..., streaming=True)` → `Agent(model=model)`
- System prompt is static (agent personality/rules), user prompt is dynamic (built per request by app code)
