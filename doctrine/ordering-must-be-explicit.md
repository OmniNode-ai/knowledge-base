---
type: doctrine
status: accepted
date: 2026-05-23
title: "Ordering Must Be Explicit and Contracted"
topics: [replay-correctness]
refs: [deterministic-under-replay.md, contracts-define-reality.md]
---

# Ordering Must Be Explicit and Contracted

Every projection must declare its ordering contract.

Canonical ordering must be based on:

- ingest-assigned sequence
- projection version
- another explicitly contracted monotonic value

`event_time_ms`:

- may be used only when its clock authority is explicitly defined by contract
- must not be assumed globally reliable

No component may rely on incidental arrival order.

Cross-source global ordering is valid only when a shared ingest ledger, or equivalent authority, assigns comparable sequence values.
