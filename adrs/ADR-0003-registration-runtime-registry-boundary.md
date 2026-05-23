---
type: adr
status: accepted
date: 2026-04-23
title: "ADR-0003: Registration Runtime / Registry Boundary"
adr_id: ADR-0003
topics: [registration, runtime, registry, projections, architecture-boundary]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0003: Registration Runtime / Registry Boundary

## Context

Registration spanned four mixed concerns with no clear ownership boundaries:

1. Runtime contract discovery and wiring
2. Registration workflow orchestration
3. Durable registry projection state
4. Downstream registry consumers

That mixing was visible in live verification failures, contract/runtime mismatches, and projection freshness issues. Without explicit ownership, follow-on work was patching symptoms rather than the structural cause. This ADR defines the target ownership boundaries.

## Decision

### 1. Runtime owns discovery and wiring

`RuntimeHostProcess` is the authority for:
- Discovering contracts from package and market surfaces
- Wiring handlers, dispatchers, and subscriptions
- Starting consumers
- Emitting normalized lifecycle facts about runtime-managed nodes

Runtime does **not** own durable registry truth or dashboard/API read semantics.

### 2. Registration owns registration orchestration

The registration orchestrator node is the authority for:
- Consuming normalized runtime lifecycle facts and explicit registry events
- Orchestrating acceptance, acknowledgment, liveness, expiry, and recovery
- Producing registration-domain outputs that feed registry projections

Registration does **not** decide what contracts exist and does **not** bootstrap runtime discovery.

### 3. Registry projections own durable read truth

Registry projections are the sole durable dashboard/API truth for node registration state. This means:
- Downstream consumers treat registry projections as authoritative
- Runtime memory, startup logs, and compatibility paths are not read truth
- If multiple registry-adjacent tables or views exist, one must be declared canonical and the rest treated as adapters, legacy surfaces, or deletion targets

### 4. Downstream consumers read projections only

Future dashboard/API consumers must read registry truth from registry projections only. This boundary is established so future consumers can rely on the correct projection surface once it is hardened.

## Alternatives Considered

The alternative — allowing runtime and registration to continue sharing mixed responsibilities — was rejected because it produces exactly the drift and verification failures that motivated this ADR. Local fixes that treat registration as a hidden runtime bootstrap mechanism were explicitly ruled out.

## Consequences

**What happens next:**
1. Lock the canonical projection choice with evidence.
2. Reconcile contract declarations, runtime behavior, and verification expectations against the target boundary.
3. Prove projection freshness and contamination status under the chosen canonical projection.
4. Update golden-chain baselines to reflect the chosen lifecycle facts and canonical projection.

**What does not happen next:**
- No more local fixes that treat registration as a hidden runtime bootstrap mechanism
- No dashboard implementation work in this stream
- No verification patches that hide contract/runtime mismatches before ownership is adjudicated

**Done means:**
- One canonical registry projection is explicitly named
- Runtime and registration ownership are reflected in code and verification
- No unresolved contradiction remains between live runtime behavior, contract declarations, and verification expectations
- Registry projections are proven fit for durable dashboard/API reads

## Lifecycle Fact Contract

Runtime-to-registration traffic should be normalized into explicit lifecycle facts, not inferred from raw startup internals. Initial fact set:

- `contract_discovered`
- `consumer_started`
- `runtime_node_announced`
- `node_accepted`
- `heartbeat_seen`
- `node_expired`
- `recovery_requested`

These facts are boundary objects between runtime execution and registration orchestration. Verification should assert against them or their derived registration outputs, not against accidental side effects of mixed startup paths.

## Related Doctrine

- Deterministic truth doctrine: clients render truth; they do not create it. Truth flows through contracts and materialized projections.

## Derived From

Live verification failures and projection freshness investigations revealing mixed ownership across the runtime/registration/registry boundary.

## Evidence

Observable projection staleness, contract/runtime mismatches, and the resulting verification gaps that motivated the boundary audit.

## Supersedes

## Superseded By
