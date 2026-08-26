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

An auto-wiring or dependency-injection engine that discovers and wires handlers from contract declarations must derive every injection and registration decision from the contract fields that exist for that purpose — never from a handler's type, class hierarchy, or a partial read of the contract. Worked example: a projection handler correctly declared its database dependency in the contract YAML's `db_io.db_tables` field. The auto-wiring engine read the contract for topic routing and capability registration but never consulted `db_io.db_tables` to decide whether to inject a database adapter — so the handler was instantiated, registered, and consumed events successfully, while silently never receiving the database adapter its own contract declared it needed. Every write silently failed; the handler's error boundary caught the resulting exception and returned success instead of surfacing it. If a dependency is worth declaring in a contract, the wiring engine must be the thing that reads and acts on that declaration.

**Boot-time invariant.** Where handler discovery is contract-driven, startup must fail hard — not silently — if a contract-declared subscription resolves to zero registered handlers after the full discovery cycle. Silent absence (an entry point that failed to load, a namespace-package layout the discovery mechanism didn't expect) is a worse failure mode than a loud boot failure: a subscribed-but-unhandled topic drops every message published to it with no visible symptom until someone notices the downstream effect is missing.

## Corollary: coordination-signal schemas must be versioned from day one

Where independent participants exchange coordination signals over the event bus — for example, one process announcing "I am working on module Y, do not conflict" so others can avoid stepping on it — the signal schema must carry a version from its first release, not added retroactively once drift is observed. Participants are not guaranteed to start at the same platform version, so a signal schema without day-one versioning has no way to stay mutually legible once one participant's understanding of the schema diverges from another's; retrofitting versioning after the fact means either breaking old participants or silently misreading old messages as new ones.
