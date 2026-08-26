---
type: doctrine
status: accepted
date: "2026-05-23"
title: "Authoritative Projections Own Truth"
topics: [projection-authority]
refs:
  - doctrine/state-is-materialized-projection.md
  - doctrine/cursors-represent-projection-progress.md
  - doctrine/truth-must-be-proven.md
  - adrs/ADR-0003-registration-runtime-registry-boundary.md
  - adrs/ADR-0004-registry-owned-consumer-surface.md
---

# Authoritative Projections Own Truth

Truth is owned by:

- the event log
- contracted inputs
- materialized projections

Clients must:

- request or subscribe to authoritative data
- render data
- invalidate and refetch from approved surfaces

Clients must not:

- infer authoritative system state
- merge event streams into truth
- deduplicate authoritative records
- read backend databases directly
- fabricate consistency

Dashboard v2 must consume event-bus, projection, or API surfaces only.

Client-side state is allowed strictly for presentation, not truth.

## Corollary: table-per-projection-handler ownership

Each projection handler exclusively owns the table(s) it writes. Other components may read those tables but never write to them. When a shared table is written by more than one handler, schema drift between the write paths produces silent inconsistency — a field written as one name by one path and queried under a different assumption by another looks like a bug in the reader, not a boundary violation. Scoping write ownership to a single handler per table means a schema change requires coordination only between that handler and its readers, not an unbounded set of writers.

## Corollary: mock-fallback as a first-class shipping pattern

A client surface (a dashboard page, a UI panel) may ship ahead of its backing projection handler by rendering clearly-labeled placeholder data when the authoritative surface returns an empty result, rather than blocking the page on pipeline completion. This is compatible with this doctrine only when the placeholder state is explicitly and visibly labeled as non-authoritative — the point of the label is that its disappearance becomes an observable, verifiable signal that real data has started flowing. An unlabeled placeholder is a truth violation; a labeled one is a legitimate way to decouple UI shipping from backend completion.
