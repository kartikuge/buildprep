# buildprep

**Adaptive UPSC Study Planner**

> You bring your goals. We build your plan from real topper strategies. We rebuild it every time life gets in the way.

## Problem

UPSC aspirants spend 8-12 months preparing across a massive syllabus using multiple resources. They find generic plans that assume the same starting point, follow one for two weeks, miss a few days, and the plan is dead. Content platforms deliver lessons and questions but don't solve scheduling, personalization, or recovery.

## What This Is

Not a content platform. The orchestration layer — plans what you study, when, and what happens when you fall behind, regardless of which resources you use.

Category: Agentic AI. Core: Amazon Nova 2 Lite via Strands. Supporting: Nova Act.

## Features

- **Personalized plan generation** from real topper strategies and UPSC syllabus RAG, calibrated to your confidence levels per subject
- **Daily calendar view** with task cards showing exact subtopic + duration
- **Check-in and agentic rebalancing** — mark tasks done/partial/skipped, pick a recovery window, get a regenerated plan for those days
- **Adaptive learning profile** — confidence scores update with every check-in, future plans weight accordingly
- **Auto-generation** of upcoming weeks as you progress
- **Exam date pre-population** via Nova Act fetching from upsc.gov.in

## Tech Stack

- AWS Strands (Amazon Nova 2 Lite on Bedrock) — plan generation and rebalancing
- Nova Act — exam date fetching
- React — frontend
- DynamoDB — user profiles, plans, check-in history, learning profile cache
- Cognito — auth
- AWS Lambda / Amplify — hosting

## Status

Early development. See `plan.md` for project journal and current progress.
