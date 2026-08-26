---
type: doctrine
status: accepted
date: "2026-05-23"
title: "Contracts Define Reality"
topics: [contract-governance]
refs:
  - doctrine/ordering-must-be-explicit.md
  - doctrine/cursors-represent-projection-progress.md
  - doctrine/ingestion-and-interpretation-separate.md
  - adrs/ADR-0003-registration-runtime-registry-boundary.md
  - adrs/ADR-0006-skill-liveness-validator-home.md
  - adrs/ADR-0007-skills-canonical-plan.md
---

# Contracts Define Reality

Every boundary must be governed by explicit contracts:

- event schemas
- command schemas
- ordering semantics
- projection schemas
- cursor semantics
- API response schemas
- failure behavior

If it crosses a boundary, it must be formally defined.

No implicit assumptions are allowed.
