---
type: doctrine
status: accepted
date: "2026-05-23"
title: "Cursors Represent Projection Progress"
topics: [projection-authority]
refs: [doctrine/authoritative-projections-own-truth.md, doctrine/state-is-materialized-projection.md, doctrine/contracts-define-reality.md]
---

# Cursors Represent Projection Progress

A cursor is not pagination.

A cursor represents the maximum known truth boundary for a projection.

A cursor must be:

- monotonic
- projection-scoped
- comparable within its scope
- derived from canonical sequence or projection progress

Ambiguous or inconsistent cursors are invalid.
