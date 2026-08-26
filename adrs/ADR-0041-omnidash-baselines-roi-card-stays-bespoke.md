---
type: adr
status: accepted
date: "2026-04-29"
title: "ADR-0041: BaselinesROICard Stays Bespoke, Outside the Generic Widget Primitives"
adr_id: ADR-0041
topics: [omnidash, widgets, component-primitives, abstraction-timing]
refs: [adrs/ADR-0040-omnidash-storybook-widget-coverage.md, reference/omnidash-component-manifest.md]
supersedes: []
superseded_by: []
---

# ADR-0041: BaselinesROICard Stays Bespoke, Outside the Generic Widget Primitives

**Status**: Accepted
**Date**: 2026-04-29
**Source**: omnidash `docs/adr/003-baselines-roi-card-stay-bespoke.md` (filed in-repo as "ADR-003"; renumbered on migration into the platform-wide decision ledger)

---

## Context

The generic-widget-primitives effort (iteration 1) introduces generic widget primitives (`<KPITileCluster>`, `<TrendChart>`, `<BarChart>`, `<DataTable>`) to replace hand-rolled dashboard layouts. As part of the audit phase, every existing bespoke component is evaluated for migration eligibility.

`BaselinesROICard` (`src/components/dashboard/baselines/BaselinesROICard.tsx`) renders two distinct layout sections in a single card:

1. A 3-column KPI grid of numeric deltas (`tokenDelta`, `timeDeltaMs`, `retryDelta`) with conditional colour coding (improved vs regressed).
2. A horizontal recommendation list (`promote`, `shadow`, `suppress`, `fork` counts) separated by a rule, with its own heading.

## Decision

**STAY-BESPOKE.** `BaselinesROICard` is not migrated to `<KPITileCluster>` in iteration 1.

## Rationale

`IKPITileClusterAdapter` models a flat array of uniformly structured KPI tiles. It has no slot for a secondary heterogeneous section (the recommendation list). Mapping this component to `<KPITileCluster>` would require either:

- (a) Stuffing the recommendation list into KPI tiles — semantically wrong and visually inconsistent with the rest of the cluster usage.
- (b) Adding a `secondarySlot` or `listSection` prop to `IKPITileClusterAdapter` — a premature abstraction driven by a single edge case before the primitive has any other adopters.

Neither option is acceptable at this stage. The bespoke layout is correct and tested.

## Alternatives Considered

| Option | Why rejected |
|---|---|
| Migrate delta grid to `<KPITileCluster>` + keep list bespoke | Splits one cohesive card across two rendering strategies; harder to reason about than a single bespoke component. |
| Add `listSection` slot to `IKPITileClusterAdapter` | Premature abstraction — no other widget needs this pattern today. |
| Full migration with flat tiles including recommendation counts | Semantically incorrect — recommendations are not the same kind of metric as delta measurements. |

## Re-evaluate Criteria

Revisit this decision **after iteration 1 ships** and `<KPITileCluster>` has at least two production adopters. At that point:

- If a recurring pattern of "KPI cluster + secondary list section" emerges in another widget, add the `listSection` slot to the adapter and migrate both.
- If no such pattern emerges, keep `BaselinesROICard` bespoke indefinitely.

The registry manifest entry for `baselines-roi-card` is left unchanged.

## Evidence

Verified against the live omnidash tree at migration time: `BaselinesROICard.tsx` still exists at `src/components/dashboard/baselines/` and has not been migrated to a generic primitive — the STAY-BESPOKE decision still holds.
