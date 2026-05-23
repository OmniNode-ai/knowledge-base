---
type: adr
status: accepted
date: 2026-04-28
title: "ADR-0007: Canonical Skills Migration Plan"
adr_id: ADR-0007
topics: [skills, migration, planning, canonical-source]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0007: Canonical Skills Migration Plan

## Context

Two same-day plans covered the same skills-to-market migration surface:
- `docs/plans/2026-04-27-skills-to-market-orchestrators-plan.md`
- `docs/plans/2026-04-27-skills-actually-working-plan.md`

The overlap created duplicated guidance and made it too easy for later tasks to cite whichever file was convenient, without a clear authoritative reference. This is the same failure mode that motivated ADR-0005 (dispatch lifecycle canonical source) — ambiguity across concurrent plans allows different work streams to operate against different definitions of the same system.

## Decision

`docs/plans/2026-04-27-skills-to-market-orchestrators-plan.md` is the canonical skills migration plan.

`docs/plans/2026-04-27-skills-actually-working-plan.md` is archived but retained for context. Its unique content must be explicitly migrated into the canonical plan rather than implied away.

## Alternatives Considered

1. **Keeping both plans active** — Rejected: preserves ambiguity. Any work item that could cite either plan now has an implicit loophole to avoid the stricter requirements of whichever plan is inconvenient.

2. **Deleting the duplicate plan** — Rejected: removes historical context and hides what was merged versus dropped. The archived plan must remain readable so reviewers can confirm the canonical plan captured everything important.

## Consequences

- The canonical plan gains a `Subsumes` marker, an explicit `Invariants` section, and a short process retro documenting what was merged in from the archived plan.
- The archived plan gains an archive banner pointing to the canonical file so future readers are not confused.
- A follow-up enforcement ticket should add same-day canonical-plan overlap checking to the `plan_to_tickets` skill to prevent this from recurring.

## Related Doctrine

- When two plans cover the same surface, one must be declared canonical before work proceeds. Citing a convenient plan over the authoritative one is an architectural evasion, not a shortcut.

## Derived From

Plan review identifying two same-day overlapping plans covering the same migration surface.

## Evidence

Both plan files dated the same day with substantially overlapping scope and no cross-references between them.

## Supersedes

## Superseded By
