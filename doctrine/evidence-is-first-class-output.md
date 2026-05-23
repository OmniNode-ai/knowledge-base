---
type: doctrine
status: accepted
date: 2026-05-23
title: "Evidence Is a First-Class Output"
topics: [evidence-systems]
refs: []
---

# Evidence Is a First-Class Output

Every externally visible operation, state transition, deployment, and completion claim must produce durable, inspectable evidence.

Evidence may include:

- projection snapshots
- event receipts
- reducer outcomes
- validation artifacts
- replay verification outputs
- consistency checksums

Approved evidence surfaces include:

- OCC receipts and contracts
- CI checks and pipelines
- pull requests and review records
- Linear comments or attachments
- committed manifests
- approved artifact storage

Evidence must:

- exist outside ephemeral runtime state
- be accessible through approved system boundaries
- support independent verification of completion claims

A task is not complete without durable evidence.
