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
  - deep-dives/2026-02-18-dashboard-mock-to-live-authority-shift.md
  - deep-dives/2026-04-14-silent-projection-failure-autowiring-gap.md
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
