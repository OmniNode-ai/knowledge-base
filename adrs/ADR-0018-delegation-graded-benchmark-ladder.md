---
type: adr
status: proposed
date: "2026-07-04"
title: "ADR-0018: Delegation Ladder Acceptance = Escalating-Complexity Graded Benchmark, Local Floor to Paid-Cloud Ceiling"
adr_id: ADR-0018
topics: [delegation, benchmark, graded-eval, local-first, tier-separation]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0018: Delegation Ladder Acceptance = Escalating-Complexity Graded Benchmark, Local Floor to Paid-Cloud Ceiling

## Context

The delegation ladder needed an acceptance test proving that the tier ladder actually
separates capability across rungs. The prior landed artifact was a
tautological fixture-content replay with zero real rungs — a flat smoke test that proved
nothing about tier separation. The open decision (rolling-plan §3.6) was whether to add a
distinct stronger cloud ceiling or use an "Option B" forced-tier harness, and whether to
include a paid-cloud rung at all.

## Decision

The delegation-ladder acceptance test is an **escalating-complexity graded benchmark
across the existing local ladder including the 5090/4090 AI-PC rungs**, replacing the smoke
test. **Tier separation (floor < ceiling) is the acceptance criterion** — the benchmark
passes only if graded results genuinely separate the rungs. The **paid-cloud ceiling is
INCLUDED, not deferred**: the ladder tops out at a paid-cloud rung = **GLM (Zhipu, paid API
key) + OpenRouter FREE models only** (no paid OpenRouter spend), above the local 27B (4090)
/ 35B (5090) / 284B rungs. Separation must span local-floor → paid-cloud-ceiling.

## Alternatives Considered

1. Flat smoke test (fixture-content replay). Rejected: tautological, zero real rungs, no separation signal — the exact failure this decision corrects.
2. "Option B" forced-tier harness (force each tier, compare) as the acceptance mechanism. Not chosen: the graded escalating-complexity benchmark across the real ladder is the acceptance vehicle; separation is the criterion.
3. Defer the paid-cloud ceiling (local-only ladder). Rejected by operator correction 2026-07-04 — an earlier session wrongly recorded "deferred, not chosen"; that was never the operator's call. The ceiling is a paid rung (GLM + OpenRouter-free), included.

## Consequences

Positive: the benchmark measures real capability separation, not fixture replay; it
exercises the AI-PC rungs (4090/5090) and the 284B rung; it establishes a falsifiable
pass/fail (separation). Negative / follow-ups: the ladder can saturate at the top — a later
finding showed 35B (5090) / 284B / cloud-GLM all scoring 1.0 with the
corpus failing to separate the frontier, requiring a harder corpus for frontier separation
and re-recording the `qwen/qwen3-coder:free` rung once the upstream 429 throttle clears.
Local-first stays binding (escalate off local only on a graded failure); paid spend is
capped (GLM paid key + OpenRouter free only).

## Derived From

`docs/plans/ROLLING_SEVEN_DAY_PLAN.md` §3 item 6 ("Delegation ladder ... DECIDED
2026-07-03 ... escalating-complexity graded benchmark ... CORRECTION 2026-07-04: paid-cloud
ceiling is INCLUDED"), with the frontier-saturation follow-up in §3 item 10.

## Evidence

Hand-driven ADR canary batch (2026-07-06). Source is a dated
operator decision + explicit 2026-07-04 operator correction; aligns with project memory
`feedback_delegation_graded_benchmarks.md` (escalating tiers that separate rungs; flat
smoke tests are worthless).

## Related Doctrine

- LOCAL-FIRST MANDATE (`feedback_local_first_mandatory.md`) — local models run everything they can; escalate only on a graded failure.
