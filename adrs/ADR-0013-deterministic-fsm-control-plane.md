---
type: adr
status: proposed
date: "2026-07-06"
title: "ADR-0013: No Driver Seat — Deterministic FSM Control Plane, LLMs as Gated Candidate Generators"
adr_id: ADR-0013
topics: [rsd, fsm, control-plane, determinism, gates, archetypes]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0013: No Driver Seat — Deterministic FSM Control Plane, LLMs as Gated Candidate Generators

## Context

An autonomous factory that decomposes, generates, verifies, and composes software could
be designed as an LLM "driving" the process — deciding next steps from model judgement.
That collides with the OmniNode deterministic-truth doctrine (truth is proven, replay is
deterministic) and with this week's incidents where model/agent claims were trusted
(the silent merge-sweep hang; the runaway watch-loop worker that exhausted the
shared `gh` identity). The operator's framing: "there is no driver seat; it's all a
finite state machine; something either works or it doesn't."

## Decision

The factory control plane is a **deterministic finite state machine** whose transition
function consumes **only verified facts** (gate pass/fail). **LLMs are quarantined as
CANDIDATE GENERATORS** — their output cannot enter state except through a gate; the FSM
transitions on what the oracle said, never on what the model claims. Mapping onto the
three ONEX archetypes: REDUCER = the problem-graph FSM (the event list is its input
alphabet); ORCHESTRATOR = the loop driver (precedent: `node_redeploy`,
`node_pr_lifecycle`); COMPUTE = fission/classification/grading; EFFECT = gates,
`onex delegate`, PRs, evidence. Consequences that fall out: the governance surface **is
the transition table itself** (data — versioned, diffable, contract-reviewed); the whole
factory history replays deterministically; the control plane is binary pass/fail only
(thresholds compiled into the table, never decided mid-run); **learning tunes table
PARAMETERS via projections** (the `roi_overlay` read-at-decision-time pattern) and never
acquires a steering wheel. Scar-tissue requirements are baked in: per-worker rate budgets
and fail-loud stall detection (the swept-but-zero-output
guard). Doctrine symmetry: games must be live non-deterministic LLMs (ADR-0015);
control must be deterministic state flow — non-determinism where you want emergence,
determinism where you need truth.

## Alternatives Considered

1. LLM-in-the-driver-seat (model decides next control action from judgement). Rejected: non-replayable, un-auditable, and lets model claims mutate state directly — the exact failure the merge-sweep-hang and runaway-worker incidents exemplify.
2. Threshold decisions made mid-run by the controller. Rejected: thresholds are compiled into the versioned transition table so the control plane stays binary pass/fail and replayable.
3. Let the learning loop steer control directly. Rejected: learning may tune table *parameters* through projections only; it never gets a steering wheel (keeps the control plane deterministic).

## Consequences

Positive: the entire factory inherits every existing governance gate unchanged (merge
queues, receipt gates, no-self-authored-evidence (ADR-0019), prod grants, WIP throttle);
runs 24/7 on the existing tick/bus substrate; control-plane properties become provable by
query over the transition table (see the graph-invariants refinement). Negative: all
factory logic must be expressed as typed states/transitions + gate EFFECTs (no imperative
"just call the model and branch on its answer"); building the transition table and its
gates is up-front work; generated FSM subgraphs must pass graph invariants before
admission.

## Derived From

`docs/plans/2026-07-06-recursive-contract-bisection-micro-factories.md` §8 R10 ("No
driver seat: deterministic state flow"), with supporting scar-tissue references to
recent operational incidents.

## Evidence

Hand-driven ADR canary batch (2026-07-06). Source is an explicit
operator statement ("there is no driver seat...") synthesized into the archetype mapping
in-session.

## Related Doctrine

- OmniNode deterministic-truth doctrine — the FSM transitions only on proven gate facts and replays deterministically.
- No self-authored evidence (ADR-0019) — inherited unchanged by the factory control plane.
