---
type: adr
status: proposed
date: "2026-07-06"
title: "ADR-0012: Seams Are First-Class — Seam-Tests-First, Tree-Shaped PRs, Seam-Scoped Testing"
adr_id: ADR-0012
topics: [rsd, seams, tdd, tree-pr-composition, selective-testing, ws-t]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0012: Seams Are First-Class — Seam-Tests-First, Tree-Shaped PRs, Seam-Scoped Testing

## Context

The central failure mode of recursive decomposition (ADR-0010) is the **composition
fallacy**: two separately-correct halves with a broken seam (mismatched types,
encoding, or error semantics) pass their individual checks yet fail when joined,
because nothing executes the seam. Today composition is literal `join()`
(`handler_swarm_aggregator.py:125`), grading applies one contract once on the
concatenation, and the only real execute-and-check path is SKIPPED. Parallel siblings
cannot observe each other's realized output shape. The operator spec's Phase 6 (Seam
Generation and Testing) placed seam tests late in the loop.

## Decision

Make **seams (boundaries) first-class** via three load-bearing refinements to the
operator spec:

- **R1 — Seam-tests-first.** Every boundary gets its seam/interface/compatibility tests
  generated **before any implementation code exists** (TDD at the graph edges). The
  fission step emits child contracts **and** their seam tests together; the pre-written
  seam tests **are** the compose-and-reverify oracle. Phase 6 therefore moves to the
  FRONT of the execution loop.
- **R2 — Tree-shaped PR composition.** Leaf implementations do NOT each open a PR
  against `dev`. Child branches merge into **parent** branches that mirror the
  decomposition tree; each merge level runs the incremental seam/integration tests for
  exactly the boundaries it joins; **only the root PR lands on `dev`**. Integration is
  incremental and tree-wise; human review surface stays human-scale.
- **R3 — Seam-scoped structural test selection.** Because seams define every module's
  interface, test selection becomes **structural, not heuristic**: a change to module X
  runs X's unit tests + the seam tests on X's boundaries and nothing else; an unchanged
  seam contract + green seam tests is *proof* downstream modules need no re-run. This is
  the provable end-state of WS-T's governed adjacency selector
  (`scripts/ci/detect_test_paths.py`, the governed adjacency selector), which approximates the same thing
  heuristically today.

## Alternatives Considered

1. Keep Phase 6 (seam testing) after implementation, per the original spec ordering. Rejected: it leaves the composition fallacy unmitigated during fan-out; the seam must be frozen before siblings code to it (attacks interface-drift F3).
2. One PR per leaf against `dev`. Rejected: explodes the human review surface and defers integration to the end; tree-PRs give the root re-verify a natural home (mitigates F5).
3. Continue heuristic changed-files→module→adjacency test selection as the end state. Rejected as the *target*: R3 makes it a proof; but WS-T's selector remains the interim, fail-closed approximation until seams are structural — R3 is a WS-T refinement, not a parallel track.

## Consequences

Positive: pre-written seam tests are exactly the seam-executing oracle that `join()`
+ one-contract-on-concatenation lacks — a real improvement over the status quo; freezing
one typed seam DTO before fan-out makes both children code to the same I/O; the root PR
is the single `dev`-landing gate. Negative / residual: seam tests are only as complete
as the fission step that authored them — an under-specified seam test suite re-opens the
composition hole (the fallacy moves up one level from code to test-authoring); running
real seam/integration tests at every internal node reintroduces CI-minute cost — R1
makes the oracle *real*, not *cheap*.

## Derived From

`docs/plans/2026-07-06-recursive-contract-bisection-micro-factories.md` §1 ("Three
load-bearing refinements R1–R3" and the phase-by-phase reconciliation table), §3 (items
1, 3, 4, 5 — the genuinely-new pieces), §4.1 (F1–F4 composition-fallacy analysis).

## Evidence

Hand-driven ADR canary batch (2026-07-06). State-of-the-art
claims (`join()` aggregation, skipped `passes_existing_tests`, heuristic WS-T selector)
are file-grounded in the source doc §2 table.

## Related Doctrine

- WS-T selective-testing (the governed adjacency selector) — R3 is the provable form of the same cost-attack the governed selector approximates.
