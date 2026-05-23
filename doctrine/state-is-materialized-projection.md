---
type: doctrine
status: accepted
date: 2026-05-23
title: "State Is a Materialized Projection"
topics: [projection-authority]
refs: [authoritative-projections-own-truth.md, reducers-define-state-progression.md, ingestion-and-interpretation-separate.md]
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
