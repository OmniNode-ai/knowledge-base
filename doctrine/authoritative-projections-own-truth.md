---
type: doctrine
status: accepted
date: 2026-05-23
title: "Authoritative Projections Own Truth"
topics: [projection-authority]
refs: [state-is-materialized-projection.md, cursors-represent-projection-progress.md, truth-must-be-proven.md]
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
