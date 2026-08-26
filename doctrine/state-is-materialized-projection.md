---
type: doctrine
status: accepted
date: "2026-05-23"
title: "State Is a Materialized Projection"
topics: [projection-authority]
refs:
  - doctrine/authoritative-projections-own-truth.md
  - doctrine/reducers-define-state-progression.md
  - doctrine/ingestion-and-interpretation-separate.md
  - adrs/ADR-0003-registration-runtime-registry-boundary.md
  - adrs/ADR-0004-registry-owned-consumer-surface.md
---

# State Is a Materialized Projection

State must be explicitly constructed from source events or contracted inputs.

A projection owns:

- sequencing
- reduction
- aggregation
- shape
- cursor semantics

There is no hidden authoritative state.
