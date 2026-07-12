---
type: adr
status: proposed
date: "2026-07-07"
title: "ADR-0022: Shift Defect-Detection Left + OCC Evidence-Only Fast-Lane (WS-E Build-Efficiency)"
adr_id: ADR-0022
topics: [build-efficiency, ci, pre-commit, occ, evidence-only, shift-left]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0022: Shift Defect-Detection Left + OCC Evidence-Only Fast-Lane (WS-E Build-Efficiency)

## Context

Two recurring cost sinks were identified in the 2026-07-06/07 CI-streamlining session.
(1) `onex_change_control` (OCC) evidence/receipt companion PRs were forced through the same
~30-check code gauntlet as real code PRs, producing a ~28-deep companion backlog that "armed
but never converged" (≈30 churning checks × fleet capacity). (2) Defects that codex /
CodeRabbit / the merge-sweep *repeatedly* fix were being caught at the most expensive layer
(CI / review / merge) instead of the cheapest — pattern/static defects reaching CI, logic
defects reaching CodeRabbit.

## Decision

Two operator directives, both under a new **WS-E build-efficiency** lane (P0 #2, directly
after WS-B):

- **(A) OCC evidence-only fast-lane.** Receipt/contract PRs whose paths ⊆ `contracts/` ∪
  `drift/dod_receipts/` get an exemption from the code gauntlet: KEEP only format/round-trip
  validation (Validate-Contract-YAML, occ-preflight/eligibility, OCC-Append-Only,
  verify/receipt-gate, Receipt-Honesty, Doctrine) + secret/leak scan + pr-title; SKIP all
  code analysis (CodeQL, PEP-604, Python↔TS-Null, Kafka-Boundary, node-contract-compliance,
  Compute-Smart-Test-Selection, Tests, Type-Check). Mechanism = an "evidence-only" zone in
  the existing `zone-filter` classifier, code checks gated `if: evidence_only != 'true'` with
  **skip-with-success** so required contexts still report (no branch-protection wedge). Filed
  as a canary-first follow-up.
- **(B) Shift defect-detection left.** Push each recurring defect class to the cheapest
  layer: pattern/static defects (hardcoded IPs/topics, banned constructs, missing error
  handling, skip tokens, secret leaks) → **pre-commit hooks**; logic defects (CodeRabbit-caught
  bugs) → **tests written with the code**. CI / CodeRabbit / merge-sweep become the BACKSTOP,
  not the primary catch. Filed as a follow-up.

## Alternatives Considered

1. Run OCC companions through the full code gauntlet (status quo). Rejected: ~30 code checks on a receipt PR is pure negative-value compute and the direct cause of the ~28-deep companion backlog.
2. Drop required contexts on OCC PRs entirely. Rejected: branch protection would wedge; the fix is **skip-with-success** so required contexts still report green without running the code analysis.
3. Keep relying on CI/CodeRabbit/merge-sweep to catch recurring defects. Rejected: that is the most expensive layer; a hook that exists but is bypassed (`--no-verify`/uninstalled) must be re-closed, and a CodeRabbit-caught logic bug is a test-coverage gap to fill at authoring time.

## Consequences

Positive: OCC evidence PRs converge quickly (durable fix for the companion backlog that
blocks heavy-repo PRs — including external contributors'); recurring defect classes get caught at the
cheapest layer, freeing the merge-sweep to be a backstop. Sharpens the CI "Lever 5" work.
Negative / caveats: the evidence-only classifier must distinguish *ticket-evidence* contracts
from *node/handler* contracts (node-contract checks must not fire on evidence, and generic
`contract.yaml` must be reclassified out of the DOCS zone) — a mis-zone would either wedge or
under-check; shifting checks to pre-commit only helps if hooks are actually installed (a live
audit found the pre-commit hook UNINSTALLED in 7/7 canonical clones — that leak must be closed
first). This is the concrete form of the operator's "pre-PR testing too
weak — the manual merge-sweep shouldn't be the safety net" ask.

## Derived From

`docs/plans/ROLLING_SEVEN_DAY_PLAN.md` §6 (2026-07-07 ~00:4xZ session, "TWO NEW OPERATOR
DIRECTIVES (A) OCC EVIDENCE-ONLY FAST-LANE + (B) SHIFT DEFECT-DETECTION LEFT") and the
2026-07-07 ~03:04Z re-cut (NEW §2 WS-E); full plan
`docs/plans/2026-07-06-ci-streamlining-logjam-reduction-plan.md`.

## Evidence

Hand-driven ADR canary batch (2026-07-06). Source is two dated
operator directives; the uninstalled-hook leak (7/7 clones) and #3632-as-clean-exemplar are
recorded in the same §6 entries as verified findings.
