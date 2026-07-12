---
type: adr
status: proposed
date: "2026-07-06"
title: "ADR-0015: Steel Onslaught Live Play Is LLM-Driven and Non-Deterministic"
adr_id: ADR-0015
topics: [steel-onslaught, llm, non-determinism, local-first, golden-fixtures]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0015: Steel Onslaught Live Play Is LLM-Driven and Non-Deterministic

## Context

Steel Onslaught is a real-time tactical mech game in which each pilot seat is driven by a
live LLM running on the local model fleet (qwen35, MLX-capable). It is
two products in one: a spectacle (watch two local AI models genuinely compete in real
time) and a game (a human plays against an AI pilot). A recurring regression had the
"live" watch path replaying a *recorded, already-finished* match (the `?live=1` flag
dumps to the buffer end; timed snapshots were byte-identical because the served match had
already ended before the browser attached). The operator's repeated verdict — "cards
never change" — traced partly to the watch path never running a live match at all.

## Decision

**Live play is LLM-driven and NON-deterministic** — real local-model inference, paced by
inference latency, never a scripted / stub / canned / precomputed path. The ONLY
deterministic surface in the whole system is the **CI golden/replay fixtures** (recorded
model outputs, for test reproducibility). A spectator or player must always experience
LIVE local-LLM play. Any design that treats the game itself as "a deterministic sim" is
wrong and is rejected. Local-first per the rolling-plan §0 mandate: escalate off local
only on a *graded* failure. The Start action must actually launch and stream a live
local-LLM-driven match — making frames advance is necessary but not sufficient if the
underlying match is a recording.

## Alternatives Considered

1. Treat the game as a deterministic simulation (scripted/precomputed play). Rejected outright — it defeats the product's entire premise (demonstrating that local models can drive interesting, competitive, agentic play).
2. Keep the `?live=1` buffer-end dump as the watch path. Rejected: it renders one static terminal frame of an already-ended match; the JON-18 silent-fixture-fallback removal exists precisely to enforce live play.
3. Deterministic fixtures in live play for stability. Rejected for live play; deterministic fixtures are confined to CI golden/replay for test reproducibility only.

## Consequences

Positive: the spectacle is honest (viewers watch genuine live local-model competition);
pacing is governed by real inference latency. Negative: live matches are subject to
inference latency and non-determinism (variance handled with more samples, never fake
seeds); the watch/stream path must be built to launch and stream a live match rather than
pace out a recording; any silent fixture fallback is a defect to remove. This invariant is
the paired opposite of the control-plane determinism in ADR-0013: non-determinism where
you want emergence (the game), determinism where you need truth (control + CI).

## Derived From

`docs/plans/2026-07-06-steel-onslaught-redesign-plan.md` §0 ("What we're building — the
premise") and the explicit INVARIANT block ("live play is LLM-driven and
NON-deterministic ... the ONLY deterministic surface is the CI golden/replay fixtures"),
plus §1 problem-statement root cause 1 (the watch path was replaying a finished match).

## Evidence

Hand-driven ADR canary batch (2026-07-06). The recorded-match
root cause is file-grounded in §1 (byte-identical snapshots; `App.tsx:41-45` `?live=1`
buffer-end behavior; `event_stream.ts:90` WebSocket-closed console log).

## Related Doctrine

- LOCAL-FIRST MANDATE (`feedback_local_first_mandatory.md`) — games run on the local model fleet; escalate only on a graded failure.
