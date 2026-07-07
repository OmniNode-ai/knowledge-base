---
type: adr
status: proposed
date: "2026-07-06"
title: "ADR-0010: Adaptive Recursive Contract Bisection (Bisect-on-Contract-Failure)"
adr_id: ADR-0010
topics: [rsd, decomposition, delegation, local-first, contracts, micro-factories]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0010: Adaptive Recursive Contract Bisection (Bisect-on-Contract-Failure)

## Context

The platform's standing falsifiable hypothesis (WS-H) is that "decomposing work into
bounded, contract-scoped tasks lets cheaper models work reliably; architecture, not
model size, is the dominant lever." WS-H's Arm D tests this with a *fixed, single-shot*
decomposition. Separately, the delegation layer already has a tier-escalation ladder
whose only lever on a contract failure is "advance to the next, more expensive model
tier on the same whole task" (`LocalDelegationDispatchPort:594-656`,
`HandlerEscalationDecision`). Nothing in the repo splits a failing task and re-invokes
itself on the smaller children; every existing mechanism is split-once, dispatch-flat,
escalate-model-on-failure. The operator captured a mechanism to close that gap.

## Decision

Adopt **adaptive recursive contract bisection** as the constructive form of WS-H's
thesis. The loop: take a problem whose acceptance oracle is a machine-checkable
CONTRACT; attempt it on the LOCAL model tier (qwen35 on the local MLX fleet —
cheapest-capable). If the contract PASSES, done (nearly free). If it FAILS, **bisect**
the problem into two smaller sub-problems, each with its own **derived** sub-contract,
and recurse; siblings run in parallel as "micro code factories" on local models.
Leaves that pass compose back upward, and **each internal node's composition is
re-verified against the PARENT contract**. Frontier spend is reserved for (a) the
fission step (authoring sub-contracts) and (b) irreducible leaves. A learning hook
emits, at each bisection node, `(task features → granularity/tier chosen → contract
outcome)` so the system learns the right decomposition grain per task class.

Because adversarial review showed the broad mechanism is either *not cheap* or *not
correct* if applied naively, the decision is **scoped**: it is defensible ONLY under
all of — (1) bisect **only along pre-existing verified contract seams** (node/handler
boundaries), (2) **hard depth cap ≤ 2**, (3) a **proven tier-discriminating gate**
built first (else the failure trigger never fires or fires on noise), (4) a **wired
execution oracle** so "contract passes" means a green run (not a heuristic shape
check), and (5) a **real full-suite re-verify at the root**. A still-failing leaf
escalates tier (the existing ladder) — it never splits again.

## Alternatives Considered

1. Fixed, single-shot decomposition (WS-H Arm D) — rejected as the *primary* mechanism because it cannot discover the right granularity per task; adaptive bisection is its counterpart, measured as a new WS-H arm, not a replacement.
2. Escalate-tier only (status quo) — rejected: it pays the ceiling on hard tasks a cheaper tier could pass once the task is split; but retained as the terminal action for irreducible leaves.
3. Unbounded recursion with cheap heuristic per-node oracles — rejected: recursion compounds confident false-PASS across ~2^d−1 composes and multiplies frontier-priced fission on exactly the hardest (least-divisible) tasks; the depth cap + seam-aligned split + execution oracle are the mitigations.
4. Reuse the name/lineage of the existing "RSD" intake scorer — rejected as a *duplication* concern; the two compose (intake priority vs build decomposition) but are different systems (see ADR-0011 for the naming resolution).

## Consequences

Positive: turns the delegation failure path into a *second axis* (bisect vs
escalate-tier); reuses existing delegation/swarm/quality-gate/routing machinery rather
than greenfield; generates a verified-decomposition corpus that is the durable moat.
Negative / cost: cold frontier fission can cost as much as solving the task (forbidden
unless split is along a pre-existing seam or a warm learned grain); serial-in-depth
latency; the fission-soundness gap (nothing yet proves C1 ∧ C2 ⟹ P) is only *raised*,
not closed, by seam tests. Prerequisites (a proven tier-discriminating gate; a wired
execution oracle) gate the first line of code; the honest first increment is
narrow and measured, not the full tree.

## Derived From

`docs/plans/2026-07-06-recursive-contract-bisection-micro-factories.md` §1 (the idea
stated crisply, R1–R3), §4 (hard-problem critiques F/E/O), §4.5 (net honest verdict
and the five scoping constraints); and the verbatim operator spec
`docs/plans/2026-07-06-recursive-contract-decomposition-operator-spec.md` (Phases 1–9,
MVP success criteria).

## Evidence

Hand-driven ADR canary batch (2026-07-06), extractor: Claude Opus acting as the
segmentation + decision-extraction stages; NOT an automated pipeline run.
Source decision is operator-authored + orchestrator-synthesized,
same session 2026-07-06. State-of-the-art evidence is file-grounded in the source doc
§2 (delegation/swarm nodes are split-once/flat/escalate-only; no recursion field).

## Related Doctrine

- LOCAL-FIRST MANDATE (`feedback_local_first_mandatory.md`) — the attempt runs on the local tier first; escalate off local only on a graded failure.
- OmniNode deterministic-truth doctrine — the root re-verify and execution oracle keep "contract passes" a proven fact, not a heuristic claim.
