---
type: adr
status: proposed
date: "2026-07-03"
title: "ADR-0025: OCC Validator Redesign = Option A (Per-Entry Hashing + Append-Only + Supersession/Tombstones)"
adr_id: ADR-0025
topics: [occ, validator, evidence, receipts, supersession, dod-verify]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0025: OCC Validator Redesign = Option A (Per-Entry Hashing + Append-Only + Supersession/Tombstones)

## Context

The `onex_change_control` (OCC) evidence/receipt validator needed a redesign.
The prior model relied on whole-file receipts, which made supersession and incremental
evidence updates awkward and produced friction in the dod_verify → Done path. An interim
child-ticket pattern was being used as a workaround. The operator had to choose a redesign
option.

## Decision

Adopt **Option A** for the OCC validator: **per-entry hashing + append-only evidence +
supersession/tombstones + merge-time PR-binding validation + grandfathered whole-file
receipts + `dod_verify` resolves OCC contracts from `dev`.** This is the decision-of-record
on the redesign. The acceptance case is a supersession → `dod_verify` PASS → Done
through the guard. The interim child-ticket pattern stays
sanctioned until the redesign lands.

## Alternatives Considered

1. Keep whole-file receipts as the only model. Rejected: it makes supersession and incremental evidence awkward; Option A grandfathers existing whole-file receipts but adds per-entry hashing + append-only semantics for new evidence.
2. Continue relying on the interim child-ticket workaround indefinitely. Rejected: it is sanctioned only until Option A lands; the redesign replaces it with first-class supersession/tombstones.
3. Resolve OCC contracts from the PR branch. Rejected: `dod_verify` resolves OCC contracts from `dev` (the merged base), so evidence binding is validated against the promoted state, and PR-binding is validated at merge time.

## Consequences

Positive: evidence becomes append-only with per-entry hashing (incremental updates without
rewriting the whole file), supersession/tombstones make replaced evidence explicit,
merge-time PR-binding validation ties receipts to the PR that produced them, and
`dod_verify` resolving from `dev` validates against the promoted base; existing whole-file
receipts are grandfathered (no forced migration). Negative: it is a validator redesign with
an implementation lane and a specific acceptance case (a supersession → PASS → Done);
until it lands the interim child-ticket pattern persists. The redesign was moved to Urgent/In
Progress on decision.

## Derived From

`docs/plans/ROLLING_SEVEN_DAY_PLAN.md` §3 item 4 ("OCC validator redesign approval
— DECIDED 2026-07-03 ~17:10Z: Option A (per-entry hashing + append-only evidence +
supersession/tombstones + merge-time PR-binding validation + grandfathered whole-file
receipts + dod_verify resolves OCC contracts from dev)").

## Evidence

Hand-driven ADR canary batch (2026-07-06). Source is a dated operator
decision-of-record with a named acceptance case (a supersession → dod_verify PASS → Done, also
satisfying the dod-verify guard).
