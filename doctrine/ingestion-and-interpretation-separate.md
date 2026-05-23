---
type: doctrine
status: accepted
date: 2026-05-23
title: "Ingestion and Interpretation Are Separate"
topics: [ingestion-boundaries]
refs: []
---

# Ingestion and Interpretation Are Separate

Transport is not state logic.

Event consumers may:

- validate envelope integrity
- validate schema compatibility
- deduplicate by message identity where defined
- route malformed messages to dead-letter or quarantine
- deliver events

Event consumers must not:

- apply projection reducers
- infer authoritative system state
- encode view-specific truth semantics

Projection services:

- sequence events
- apply reducers
- materialize state

Mixing transport and projection semantics creates nondeterminism.
