---
type: doctrine
status: accepted
date: "2026-05-23"
title: "Systems Must Be Deterministic Under Replay"
topics: [replay-correctness]
refs:
  - doctrine/ordering-must-be-explicit.md
  - doctrine/reducers-define-state-progression.md
  - doctrine/canonical-reducers-win.md
  - adrs/ADR-0005-dispatch-lifecycle-canonical.md
---

# Systems Must Be Deterministic Under Replay

A valid system guarantees:

```text
same canonical input sequence
+ same contract / reducer version
-> same projected state
```

Replay must not depend on:

- wall-clock timing
- consumer arrival order
- process restarts
- transient runtime state

If replay produces different authoritative state, the system is incorrect.
