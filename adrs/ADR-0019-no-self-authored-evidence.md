---
type: adr
status: proposed
date: "2026-07-06"
title: "ADR-0019: No Self-Authored Evidence — OCC Companions From Autogen or Independent Verifier Only"
adr_id: ADR-0019
topics: [evidence, occ, verification, doctrine, receipt-gate]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0019: No Self-Authored Evidence — OCC Companions From Autogen or Independent Verifier Only

## Context

Heavy-repo PRs require a companion `onex_change_control` (OCC) evidence receipt to pass the
receipt gate. In practice the implementing agent was authoring its own OCC evidence
companion, which defeats the gate: agents lie, and self-attestation is not proof. An
instance (an OCC evidence companion) was authored by the implementing agent pre-rule and had
to be re-verified. The platform's whole verification posture (Rule #3: verify via
`gh pr checks`, never trust agent self-reports) is undermined if the evidence itself is
self-authored.

## Decision

**No self-authored evidence.** The implementing agent must NOT author its own OCC evidence
companion. Companions come **only** from the autogen tick or an **independent verifier**.
Codified as a standing operator policy (memorialized in orchestrator
memory 2026-07-06). Any companion found to be self-authored by the implementer is re-verified
(or regenerated) by an independent party before the work is accepted.

## Alternatives Considered

1. Let the implementing agent author its own OCC companion (status quo). Rejected: self-attestation defeats the gate; agents lie; an OCC receipt written by the party it certifies is not evidence.
2. Drop the OCC companion requirement to remove the friction. Rejected: the receipt gate is load-bearing durable evidence; the fix is independent authorship, not removal (the friction is separately addressed by OCC evidence-only fast-lane + autogen — see ADR-0022).

## Consequences

Positive: OCC evidence regains its integrity as independent proof; aligns with Rule #3
(never trust agent self-reports) and the deterministic-truth doctrine (truth is proven, not
asserted). Negative / dependency: it requires the OCC-companion autogen tick or
an independent verifier to be available so the companion can be produced without the
implementer — otherwise heavy-repo PRs stall waiting on independent evidence; this is the
motivation for automating OCC companion generation (WS-M / ADR-0022). Practically, agents
now note "owed-from-autogen" rather than hand-authoring the companion.

## Derived From

`docs/plans/ROLLING_SEVEN_DAY_PLAN.md` §6 (2026-07-06 ~20:15Z governor re-cut, item 6
"FOUR NEW OPERATOR POLICIES ... NO self-authored evidence (autogen/
independent-verifier companions only)"; and item 5's caveat that an early OCC companion was
self-authored pre-rule → re-verify).

## Evidence

Hand-driven ADR canary batch (2026-07-06). Source is a dated
operator policy recorded in the revision log; aligns with project memory
`feedback_no_self_authored_evidence.md` and CLAUDE.md Rule #3.

## Related Doctrine

- CLAUDE.md Rule #3 — verify via `gh pr checks`, never trust agent self-reports.
- OmniNode deterministic-truth doctrine — durable evidence in approved control-plane surfaces; clients render truth, they do not create it.
