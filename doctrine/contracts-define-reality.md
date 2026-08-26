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

## Corollary: auto-wiring must read the whole contract

An auto-wiring or dependency-injection engine that discovers and wires handlers from contract declarations must derive every injection and registration decision from the contract fields that exist for that purpose — never from a handler's type, class hierarchy, or a partial read of the contract. A contract can correctly declare a dependency (a required service, a database table) while the engine that wires handlers only reads a subset of contract fields for a different purpose (routing, capability registration). The result is a handler that is instantiated, registered, and appears healthy, while silently never receiving the dependency it declared — because the contract was correct and the engine's read of it was not. If a dependency is worth declaring in a contract, the wiring engine must be the thing that reads and acts on that declaration.

**Boot-time invariant.** Where handler discovery is contract-driven, startup must fail hard — not silently — if a contract-declared subscription resolves to zero registered handlers after the full discovery cycle. Silent absence (an entry point that failed to load, a namespace-package layout the discovery mechanism didn't expect) is a worse failure mode than a loud boot failure: a subscribed-but-unhandled topic drops every message published to it with no visible symptom until someone notices the downstream effect is missing.
