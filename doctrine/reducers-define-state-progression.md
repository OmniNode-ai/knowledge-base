---
type: doctrine
status: accepted
date: 2026-05-23
title: "Reducers Define State Progression"
topics: [replay-correctness]
refs: [deterministic-under-replay.md, canonical-reducers-win.md, state-is-materialized-projection.md]
---

# Reducers Define State Progression

State progression is defined by the projection's reducer contract.

For last-write-wins projections:

- newer sequence or version supersedes older

For FSMs, aggregates, counters, and lifecycle projections:

- reducer semantics define valid transitions

Old or out-of-order events must be handled according to contract:

- ignored
- quarantined
- treated as no-op
- explicitly rejected

They must never silently corrupt state.
