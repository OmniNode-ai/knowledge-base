---
type: reference
status: current
date: "2026-09-02"
title: "ADR-006: MessageDispatchEngine as Canonical Consumer Routing Pattern"
topics: [omnibase-infra, adr, message, dispatch]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-006-message-dispatch-engine-canonical-routing.md on 2026-09-02. -->

# ADR-006: MessageDispatchEngine as Canonical Consumer Routing Pattern

## Status

Accepted

## Date

2026-02-08

## Context

The ONEX runtime has two patterns for routing Kafka messages to handlers:

**Pattern A (plugin-direct):** Each plugin subscribes directly to Kafka
topics via `EventBusKafka.subscribe()` and routes messages through a custom
event router. Used by `PluginRegistration` with `IntrospectionEventRouter`.

**Pattern B (dispatch engine):** Plugins register dispatchers with
`MessageDispatchEngine`, which owns the subscription lifecycle and routes
messages based on `message_type` (and, in future, `event_type`). Used by
`EventBusSubcontractWiring` for contract-driven subscriptions.

When `PluginIntelligence` needed to wire its three Kafka topics to real
handlers (replacing the `_noop_handler` placeholder), the question was:
follow Pattern A (matching the existing `PluginRegistration` template) or
Pattern B (the dispatch engine)?

### Why this matters

At two consumers, maintaining parallel patterns is manageable. At three or
more, direct subscription per plugin creates:

- **Fragmented invariants**: Each plugin implements its own retry policy,
  ordering semantics, dead-letter handling, and envelope parsing.
- **No global guarantees**: Cannot enforce platform-wide rules like
  "partition key is `run_id`" or "all consumers enforce the same
  `schema_version` policy."
- **Architectural drift**: The runtime's role as centralized subscriber
  (transport spec invariant #1) is undermined by each plugin owning its
  own consumer lifecycle.

## Decision

**MessageDispatchEngine is the default wiring pattern for all new
consumers.** Direct subscription patterns are legacy exceptions.

### Rules

1. New plugins wire consumers through `MessageDispatchEngine.register_dispatcher()`.
2. `PluginRegistration`'s direct subscription (`IntrospectionEventRouter`)
   is a legacy exception. It stays as-is but is documented as legacy.
3. Migration target for `PluginRegistration`: move `IntrospectionEventRouter`
   registrations into `MessageDispatchEngine` dispatchers.
4. `PluginIntelligence` is the first plugin implementing Pattern B
   end-to-end. It serves as the reference implementation.

### Phase 1 Independence Invariant

Phase 1 (intelligence dispatcher wiring) uses existing envelope fields and
`message_type` inference for routing. The `event_type` field is a Phase 2
concern. No Phase 1 work depends on envelope evolution.

## Consequences

### Positive

- **Single routing enforcement point**: retry, DLQ, ordering, schema
  validation, and backpressure policies are enforced once in the dispatch
  engine, not per-plugin.
- **Global guarantees possible**: partition key policy, schema version
  enforcement, and dead-letter routing are centralized.
- **Intelligence establishes the pattern**: future plugins have a working
  template to follow.

### Negative

- **PluginRegistration diverges**: it continues using direct subscription
  until migrated, creating a known inconsistency.
- **Dispatch engine becomes a bottleneck risk**: all message routing flows
  through one component. Must ensure it remains performant under load.

### Neutral

- Phase 2 (envelope evolution with `event_type`, `payload_type`,
  `payload_schema_version`) is a separate concern tracked in
  through . It enhances routing but is not required for Phase 1.

## Open Decisions (resolve before or during Phase 2)

These decisions are referenced in the transport envelope specification and
affect Phase 2 ticket scope.

| # | Decision | Recommendation | Rationale |
|---|----------|----------------|-----------|
| 1 | Routing key format: dot-path string vs enum vs topic segment | Dot-path string | Extensible without code changes; matches topic naming convention |
| 2 | Payload discriminator: dot-path string vs enum member | Dot-path string | Enums require code changes for each new type; strings allow dynamic registration |
| 3 | Dead-letter policy: single DLQ vs per-category vs per-source | Per-category DLQ | Already implemented in `topic_constants.py`; category derived from `event_type` domain prefix (`intelligence.*` -> `onex.dlq.intelligence.v1`) |
| 4 | Spool format: JSON lines vs one file per event vs SQLite WAL | JSON lines | Simplest; append-only; easy to replay with standard tools |
| 5 | Ordering guarantee: none vs per-topic vs per-partition-key | Partition key = `run_id` | Reducers need per-run ordering for FSM correctness; Kafka partition keys provide this naturally |

## References

- **Epic**:  — Intelligence Domain Routing + Envelope Evolution
- **Phase 1 tickets**:  through
- **Phase 2 tickets**:  through
- **Measurement work**:  (Workstream M — separate scope)
- **PluginRegistration template**: `src/omnibase_infra/nodes/node_registration_orchestrator/plugin.py`
- **MessageDispatchEngine**: `src/omnibase_infra/runtime/service_message_dispatch_engine.py`
- **EventBusSubcontractWiring**: `src/omnibase_infra/runtime/event_bus_subcontract_wiring.py`
- **PluginIntelligence (blocker)**: `omniintelligence/src/omniintelligence/runtime/plugin.py`
