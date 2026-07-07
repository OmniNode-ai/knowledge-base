---
type: adr
status: proposed
date: "2026-07-06"
title: "ADR-0020: Branch-Preview Verification (proof_class=branch-preview)"
adr_id: ADR-0020
topics: [verification, dev-lane, proof-class, pre-merge, evidence]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0020: Branch-Preview Verification (proof_class=branch-preview)

## Context

Runtime readbacks (proving a behavior change actually works on a live lane) were being
parked behind the merge wall-clock — a change had to merge to `dev`, then the lane had to
redeploy, before anyone could observe it working. With a slow merge queue and runner
backlog, that pushed verification hours-to-days after the code was written, and left
several readbacks owed and blocked on merge timing.

## Decision

**Verify from branch-built dev-lane deploys PRE-merge**, tagged **`proof_class=branch-preview`**.
A branch can be built into the dev lane and its behavior observed and recorded as evidence
*before* it merges. Only **Done-closure** requires merged + redeployed evidence
(`proof_class` upgraded accordingly). This makes pre-merge branch-preview readbacks legal
and first-class; they are not a substitute for the final merged+redeployed proof at closure,
but they unblock verification from the merge wall-clock.

## Alternatives Considered

1. Park all runtime readbacks behind merge + redeploy (status quo). Rejected: it couples verification latency to merge-queue latency; readbacks sat owed for hours-to-days behind the queue.
2. Accept CI-green as sufficient runtime proof. Rejected: CI watch is not a substitute for a live-lane observation of the changed behavior; branch-preview provides a real live-lane readback pre-merge.
3. Treat branch-preview evidence as equivalent to Done-closure evidence. Rejected: Done-closure still requires merged + redeployed proof; branch-preview is an explicitly weaker, honestly-labeled proof_class for pre-merge confidence.

## Consequences

Positive: verification decouples from the merge queue; a behavior can be proven working on
the dev lane while the PR is still open; the three owed readbacks
become legal pre-merge. Negative / discipline: every readback must carry an honest
`proof_class` (`branch-preview` vs merged+redeployed) so evidence is never overclaimed;
branch-preview builds mutate the dev lane state (must re-probe lane state before reuse — an
interrupted branch-preview integration build left the dev-lane state UNKNOWN at one
close). Done-closure is not satisfied until the merged+redeployed proof exists.

## Derived From

`docs/plans/ROLLING_SEVEN_DAY_PLAN.md` §6 (2026-07-06 ~20:15Z governor re-cut, item 6 "FOUR
NEW OPERATOR POLICIES ... branch-preview verification (`proof_class=branch-preview` — verify
from branch-built dev-lane deploys PRE-merge; only Done-closure needs merged+redeployed)"
and item 7 on the owed readbacks now legal pre-merge).

## Evidence

Hand-driven ADR canary batch (2026-07-06). Source is a dated
operator policy in the revision log; aligns with project memory
`feedback_branch_preview_verification.md`.

## Related Doctrine

- OmniNode deterministic-truth doctrine — a task is not Done without durable evidence; branch-preview is an interim, honestly-graded proof, not the closure proof.
