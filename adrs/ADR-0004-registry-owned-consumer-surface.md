---
type: adr
status: accepted
date: 2026-04-23
title: "ADR-0004: Registry-Owned Consumer Surface"
adr_id: ADR-0004
topics: [registry, projections, consumer-surface, api, architecture-boundary]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0004: Registry-Owned Consumer Surface

## Context

Following the registration/runtime/registry boundary definition in ADR-0003, the supported consumer surface remained too implicit.

Evidence showed:
- `registration_projections` is the only live, fresh registry projection in the running infrastructure
- `node_registrations` behaves like a storage/effect table, not canonical read truth
- `node_service_registry` is a downstream compatibility read model that does not exist in the live infrastructure database

This ADR names the supported registry-owned consumer surfaces so follow-on API and verification work can proceed against one explicit target.

## Decision

### 1. Canonical registry source

`registration_projections` is the canonical current registry truth surface for node registration state.

- Registry-owned reads must trace back to `registration_projections`
- Projection freshness and correctness are judged at `registration_projections`
- No new canonical projection layer should be introduced for this workstream

### 2. Supported synchronous consumer surface

The supported query surface is the registry API backed by `ProjectionReaderRegistration`. This includes:
- Registry node list/detail reads
- Registry discovery summaries derived from those projection-backed node results
- Future synchronous consumers that need registry state without reading tables directly

This does **not** authorize direct downstream reads from `registration_projections` as the default integration contract. The supported contract is the registry-owned API surface built on that projection.

### 3. Snapshot surface stance

Registration snapshot publication remains an existing registry-owned capability, but it is **not** the primary supported consumer boundary in this tranche. Query-time registry API is the primary supported consumer surface. Any future decision to promote snapshots into a supported consumer contract must explicitly define payload, topic, intended consumers, and verification.

### 4. Non-canonical surfaces

The following are not canonical registry truth:
- `node_service_registry`
- Runtime memory or startup state
- Legacy compatibility surfaces
- Ad hoc direct table reads by downstream consumers

`node_service_registry` may continue to exist as a downstream adapter or legacy consumer artifact, but it is not the source this workstream will harden.

## Alternatives Considered

1. **`node_service_registry` as canonical** — Rejected: does not exist in the live infrastructure database; cannot be the target for hardening work.
2. **Direct table reads as the consumer contract** — Rejected: leaks projection implementation details to consumers and prevents safe projection evolution.
3. **Snapshot publication as the primary surface** — Deferred rather than rejected: valid long-term path but requires explicit payload/topic/consumer/verification definition before it can be a supported contract.

## Consequences

**What this enables:**
1. Registry API hardening can proceed against one named source: `registration_projections`.
2. Identity and field-exposure decisions can be judged against projection truth instead of legacy discovery semantics.
3. Focused verification can assert the projection → reader → API path directly.

**What this defers:**
- Snapshot promotion into a supported public consumer contract
- Dashboard implementation work
- Any revival of `node_service_registry` as canonical truth

**Completeness note:**
This ADR names the target supported consumer surface. It does not claim every existing registry API payload is already semantically correct or complete. Canonical source correctness does not imply current API identity semantics are correct, and follow-on tickets may still simplify discovery payloads carrying legacy compatibility residue.

## Related Doctrine

- Deterministic truth doctrine: clients render truth from materialized projections; they do not create it or pull from runtime memory.

## Derived From

Registry consumer surface audit following the registration boundary definition work.

## Evidence

Live infrastructure inspection confirming `registration_projections` as the only fresh, populated registry projection; `node_service_registry` confirmed absent from the live database.

## Supersedes

## Superseded By
