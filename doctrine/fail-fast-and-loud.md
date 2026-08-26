---
type: doctrine
status: accepted
date: "2026-05-23"
title: "Fail Fast and Loud"
topics: [failure-handling]
refs:
  - doctrine/degrade-safely.md
  - doctrine/evidence-is-first-class-output.md
  - doctrine/truth-must-be-proven.md
  - adrs/ADR-0006-skill-liveness-validator-home.md
---

# Fail Fast and Loud

The system must:

- detect violations immediately
- surface errors clearly and aggressively
- prevent invalid state transitions

The system must never:

- silently accept invalid data
- mask ordering violations
- fabricate state
- hide projection inconsistency
- mark work complete without durable evidence

Acceptable:

- delayed updates
- quarantined events
- explicitly degraded projections

Unacceptable:

- incorrect state
- silent regression
- hidden inconsistency

## Corollary: error boundaries must not manufacture success

An error boundary is permitted to catch an exception and stop it from propagating. It is not permitted to then report success without having logged what it caught. A boundary that swallows an exception and returns a normal-looking result converts a real failure (a missing dependency, a failed write) into a false positive that every downstream observer — health checks, dashboards, orchestration logic — now treats as evidence the operation worked. If a boundary catches an error, it must emit a structured error signal before it returns; catching is allowed, silencing is not.
