---
type: doctrine
status: accepted
date: "2026-05-23"
title: "Canonical Reducers Win"
topics: [replay-correctness]
refs: [doctrine/reducers-define-state-progression.md, doctrine/ordering-must-be-explicit.md, doctrine/deterministic-under-replay.md]
---

# Canonical Reducers Win

"Latest wins" is valid only when the projection contract explicitly defines last-write-wins behavior.

Otherwise:

- reducer semantics determine truth

The system must never allow:

- first write wins by accident
- arrival order to determine truth
- UI sort order to determine truth
- undefined conflict behavior

If ordering or reducer semantics are ambiguous, the system is invalid.
