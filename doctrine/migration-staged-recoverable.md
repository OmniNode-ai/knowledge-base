---
type: doctrine
status: accepted
date: "2026-05-23"
title: "Migration Must Be Staged and Recoverable"
topics: [migration-safety]
refs: [doctrine/evidence-is-first-class-output.md, doctrine/fail-fast-and-loud.md, doctrine/deterministic-under-replay.md]
---

# Migration Must Be Staged and Recoverable

No system is replaced without proof.

Required approach:

- parallel or shadow validation where practical
- staged rollout
- explicit deprecation
- rollback or forward-repair plan
- observable comparison between old and new paths
- durable evidence before deletion

A new system must match or exceed the correctness guarantees of the system it replaces.
