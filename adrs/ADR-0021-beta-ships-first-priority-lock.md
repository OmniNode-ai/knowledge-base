---
type: adr
status: proposed
date: "2026-07-06"
title: "ADR-0021: Beta Ships First — Priority-Ladder Lock, WS-B Outranks All In-Flight Lanes"
adr_id: ADR-0021
topics: [prioritization, beta-launch, ws-b, planning, roadmap]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0021: Beta Ships First — Priority-Ladder Lock, WS-B Outranks All In-Flight Lanes

## Context

Two 2026-07-06 partner syncs set a beta
launch with a **24–36h hard deadline**. The rolling plan carried many in-flight
workstreams (delegation, CI-streamlining, Steel, ratchet burn-down, SEA), and without an
explicit ranking, beta-critical work would compete with lower-urgency lanes for parallel
agent capacity. The operator locked the priority ladder in the subsequent re-cuts.

## Decision

**Beta ships first.** A new **WS-B (Beta launch)** lane is inserted at the TOP of the work
queue and **outranks every in-flight lane** — it is the nearest hard deadline, is
customer-facing, and gates revenue. The locked priority ladder: WS-B + beta-critical
surfaces (WS-D delegation, WS-P SEA residuals, dashboard/website beta surface) outrank
everything else. WS-B is the Urgent beta-launch epic (platform online with gateway +
delegation; users log in and use it end-to-end; marketing drives beta users) with children
the login experience (what a user sees), the post-login internal experience,
clearing the cloud-deploy blockers, and repointing to managed Postgres.
Wave framing: Wave 1 = beta watches/wires + build-efficiency + manual-sweep merge driving;
Wave 2 = shift-left + selective testing; continuous = ratchet dogfood; post-beta = the 2×2
decomposition experiment + articles-after-IP-review.

## Alternatives Considered

1. Keep all lanes flat / self-ranked by RSD score. Rejected: a hard 24–36h customer deadline requires an explicit top-rank; leaving it to the scorer risks beta work losing capacity to lower-urgency lanes.
2. Elevate Stripe/payments into the beta lane. Rejected: Stripe integration is explicitly post-beta/future (Low), a WS-7 backlog pointer, deliberately NOT in WS-B.
3. Interleave beta with in-flight lanes at equal priority. Rejected: WS-B is placed FIRST; other lanes are placement-only re-ranked below it (no task deleted).

## Consequences

Positive: unambiguous capacity allocation — beta-critical work gets parallel agents first;
the wave framing sequences dependent work (cloud unblock → managed-Postgres repoint
→ signup verification). Negative: non-beta lanes (widget palette, omniweb marketing, most
Steel polish) are deprioritized for the deadline window; other-owner blockers (external
owners: login/signup toggle, waitlist email, analytics; Postgres cutover + cloud
rollout) are tracked as blockers, not in-house agent tasks, so beta ship depends on parties outside
the agent fleet.

## Derived From

`docs/plans/ROLLING_SEVEN_DAY_PLAN.md` §6 (2026-07-06 ~17:0xZ governor roll-in — "NEW §2
WS-B Beta launch (24–36h hard deadline) inserted at the TOP ... outranks every in-flight
lane") and the 2026-07-07 ~03:04Z re-cut ("priority ladder locked — beta ships first").

## Evidence

Hand-driven ADR canary batch (2026-07-06). Source is two dated
partner-sync ledgers folded into the plan as an explicit re-rank; the WS-B tickets were
filed.
