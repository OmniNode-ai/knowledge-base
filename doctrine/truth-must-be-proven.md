---
type: doctrine
status: accepted
date: "2026-05-23"
title: "Truth Must Be Proven, Not Claimed"
topics: [truth-verification]
refs:
  - doctrine/evidence-is-first-class-output.md
  - doctrine/authoritative-projections-own-truth.md
  - adrs/ADR-0002-data-verification-invocation.md
  - adrs/ADR-0005-dispatch-lifecycle-canonical.md
---

# Truth Must Be Proven, Not Claimed

Status is not truth.
Logs are not truth.
Completion signals are not truth.

Truth is established only when:

- authoritative downstream state reflects the result
- outputs are observable through approved boundaries
- results survive replay, restart, and reprocessing
- durable evidence exists outside the originating workstation

Local artifacts, scratch files, and ephemeral logs are not completion evidence.
