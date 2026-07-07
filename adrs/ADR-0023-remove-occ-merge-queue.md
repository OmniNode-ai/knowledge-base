---
type: adr
status: proposed
date: "2026-07-07"
title: "ADR-0023: Remove the onex_change_control Merge Queue"
adr_id: ADR-0023
topics: [merge-queue, occ, ci, throughput, branch-protection]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0023: Remove the onex_change_control Merge Queue

## Context

The `onex_change_control` (OCC) repo carried a GitHub merge queue on `dev`. Because OCC PRs
are almost all evidence/receipt companions and were running the full check gauntlet, the
queue accumulated ~13 stuck companion PRs and a large volume of zombie `merge_group` runs.
The queue mechanics were adding latency and wedge risk to a repo whose PRs are mostly
low-risk evidence artifacts, not runtime code.

## Decision

**Remove the OCC merge queue**. The queue ruleset was disabled so
`mergeQueue(dev)` resolves to `null`, while keeping the **7 required status contexts intact**.
The 13 stuck companions were drained via direct squash merges. The change is **reversible**
(re-enable enforcement=active). CLAUDE.md merge-policy guidance is updated: OCC is now a
**non-queue** repo, so `gh pr merge` uses **`--squash --auto`** (an explicit method), not the
bare `--auto` used on queue repos.

## Alternatives Considered

1. Keep the OCC merge queue and drain the backlog through it. Rejected: the queue was the source of the wedge + zombie `merge_group` accumulation on a repo of mostly low-risk evidence PRs; the OCC evidence-only fast-lane (ADR-0022) reduces per-PR checks but the queue mechanics themselves added no safety here.
2. Remove required status checks along with the queue. Rejected: the 7 required contexts are kept intact — only the queue is removed, so protection is preserved.
3. Make the change irreversibly. Rejected: the ruleset is merely disabled (enforcement=active re-enables it), keeping the decision reversible.

## Consequences

Positive: OCC PRs merge via direct squash without queue latency; ~7,125 dead `merge_group`
runs were cancelled as part of the same cleanup (zombie CI queue flushed −76%, 7,533→~1,833,
zero live runs touched); the 13 stuck companions drained. Non-queue merge method for OCC is
now `--squash --auto`. Negative / operational: OCC no longer serializes merges through a
queue (acceptable given the low-risk evidence nature of its PRs and the intact required
contexts); merge-method guidance must be remembered per-repo (OCC diverges from the
queue-repo bare-`--auto` convention); reversal requires re-enabling the ruleset.

## Derived From

`docs/plans/ROLLING_SEVEN_DAY_PLAN.md` §6 (2026-07-07 ~00:4xZ CI-streamlining + OCC-autogen
session: "OCC merge queue REMOVED (queue ruleset disabled → mergeQueue(dev)=null,
7 required contexts intact, 13 stuck companions drained via direct squash, reversible ...;
CLAUDE.md #198 → OCC non-queue `--squash --auto`").

## Evidence

Hand-driven ADR canary batch (2026-07-06). Source records the concrete
ruleset id (16846914), the drained-companion count (13), the zombie-queue flush (−76%), and the
reversal path — a dated, executed change under standing operator approval.
