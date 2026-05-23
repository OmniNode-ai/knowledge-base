---
type: doctrine
status: accepted
date: 2026-05-23
title: "Degrade Safely"
topics: [failure-handling]
refs: [fail-fast-and-loud.md, authoritative-projections-own-truth.md]
---

# Degrade Safely

When failure occurs, correctness takes priority over availability.

The system may:

- delay processing
- quarantine invalid events
- dead-letter malformed inputs
- mark projections as degraded explicitly

The system must not:

- silently drop events
- guess missing state
- reorder without authority
- present degraded data as complete truth
