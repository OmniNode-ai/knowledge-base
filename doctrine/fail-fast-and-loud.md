---
type: doctrine
status: accepted
date: 2026-05-23
title: "Fail Fast and Loud"
topics: [failure-handling]
refs: [degrade-safely.md, evidence-is-first-class-output.md, truth-must-be-proven.md]
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
