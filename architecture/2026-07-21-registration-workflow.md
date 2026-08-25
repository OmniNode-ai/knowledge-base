---
type: architecture
status: accepted
date: "2026-07-21"
title: "REGISTRATION WORKFLOW"
topics: [omnibase-infra, registration, workflow]
refs: []
---


# REGISTRATION WORKFLOW

> **Status**: Current | **Last Updated**: 2026-02-19

## Table of Contents

1. Overview
2. Complete Flow Diagram
3. Node Responsibilities
4. Phase 1: Introspection and Registration Initiation
5. Phase 2: Effect Execution (Consul + PostgreSQL)
6. Phase 3: Node Acknowledgment
7. Phase 4: Heartbeat and Liveness
8. RegistrationReducerService: Decision Methods
9. FSM State Machine
10. ModelIntent Construction
11. Kafka Topics
12. Error Paths
13. E2E Test Coverage

---

## Overview

The ONEX registration system implements a **2-way registration pattern**: nodes announce themselves (introspection), the runtime registers them in Consul and PostgreSQL, and the node must explicitly acknowledge before becoming ACTIVE.

Four ONEX node types participate:

| Node | Type | Role |
|------|------|------|
| `NodeRegistrationOrchestrator` | `ORCHESTRATOR_GENERIC` | Consumes introspection events; drives the workflow |
| `NodeRegistrationReducer` | `REDUCER_GENERIC` | FSM-driven intent computation (contract.yaml state machine) |
| `NodeRegistryEffect` | `EFFECT_GENERIC` | Dual-backend execution: Consul + PostgreSQL in parallel |
| `NodeRegistrationStorageEffect` | `EFFECT_GENERIC` | Capability-oriented storage (pluggable backends) |

The orchestrator does **not** return a `result`; it publishes events and emits intents per the ONEX constraint that ORCHESTRATOR nodes never return values directly.

---

## Complete Flow Diagram

```text
Node Process                   Kafka                  NodeRegistrationOrchestrator         NodeRegistryEffect
    │                            │                              │                                │
    │  publish introspection      │                              │                                │
    │──────────────────────────►  │                              │                                │
    │                            │  onex.evt.platform.           │                                │
    │                            │  node-introspection.v1        │                                │
    │                            │ ────────────────────────────► │                                │
    │                            │                              │                                │
    │                            │                HandlerNodeIntrospected.handle()               │
    │                            │                              │                                │
    │                            │                  ProjectionReaderRegistration                 │
    │                            │                  .get_entity_state(node_id)                   │
    │                            │                      ┌──────────────────┐                    │
    │                            │                      │   PostgreSQL      │                    │
    │                            │                      │   (projection)    │                    │
    │                            │                      └──────────────────┘                    │
    │                            │                              │                                │
    │                            │                  RegistrationReducerService                   │
    │                            │                  .decide_introspection(projection, event)     │
    │                            │                     (pure function, zero I/O)                │
    │                            │                              │                                │
    │                            │                  Returns ModelReducerDecision:                │
    │                            │                    action="emit"                              │
    │                            │                    events=(Initiated, Accepted)               │
    │                            │                    intents=(postgres.upsert, consul.register) │
    │                            │                              │                                │
    │                            │  publish events              │                                │
    │                            │ ◄──────────────────────────  │                                │
    │                            │  node-registration-initiated │                                │
    │                            │  node-registration-accepted  │                                │
    │                            │                              │                                │
    │                            │                    dispatch intents to NodeRegistryEffect     │
    │                            │                              │ ─────────────────────────────► │
    │                            │                              │                                │
    │                            │                              │    asyncio.gather() [parallel] │
    │                            │                              │    ┌────────────────────────┐  │
    │                            │                              │    │  HandlerConsulRegister  │  │
    │                            │                              │    │  HandlerPostgresUpsert  │  │
    │                            │                              │    └────────────────────────┘  │
    │                            │                              │        │           │           │
    │                            │                              │        ▼           ▼           │
    │                            │                              │    ┌───────┐  ┌─────────┐     │
    │                            │                              │    │ Consul│  │Postgres │     │
    │                            │                              │    └───────┘  └─────────┘     │
    │                            │                              │        │           │           │
    │                            │                              │    ModelBackendResult          │
    │                            │                              │ ◄──────────────────────────── │
    │                            │                              │    status: success/partial/    │
    │                            │                              │            failed              │
    │                            │                              │                                │
    │  consume registration       │                              │                                │
    │  events (accepted)          │                              │                                │
    │ ◄───────────────────────── │                              │                                │
    │                            │                              │                                │
    │  publish NodeRegistrationAcked                            │                                │
    │ ─────────────────────────► │                              │                                │
    │                            │  onex.cmd.platform.          │                                │
    │                            │  node-registration-acked.v1  │                                │
    │                            │ ────────────────────────────► │                                │
    │                            │                              │                                │
    │                            │                HandlerNodeRegistrationAcked.handle()          │
    │                            │                              │                                │
    │                            │                  ProjectionReaderRegistration                 │
    │                            │                  .get_entity_state(node_id)                   │
    │                            │                      ┌──────────────────┐                    │
    │                            │                      │   PostgreSQL      │                    │
    │                            │                      └──────────────────┘                    │
    │                            │                              │                                │
    │                            │                  RegistrationReducerService                   │
    │                            │                  .decide_ack(projection, command)             │
    │                            │                              │                                │
    │                            │                  Returns ModelReducerDecision:                │
    │                            │                    events=(AckReceived, BecameActive)         │
    │                            │                    intents=(postgres.update -> ACTIVE)        │
    │                            │                              │                                │
    │                            │  publish events              │                                │
    │                            │ ◄──────────────────────────  │                                │
    │                            │  node-registration-ack-recv  │                                │
    │                            │  node-became-active          │                                │
    │                            │                              │                                │
    │  now ACTIVE                 │                              │                                │
    │ ◄───────────────────────── │                              │                                │
    │                            │                              │                                │
    │  publish heartbeats         │                              │                                │
    │  every ~30s                 │                              │                                │
    │ ─────────────────────────► │                              │                                │
    │                            │  onex.evt.platform.          │                                │
    │                            │  node-heartbeat.v1           │                                │
    │                            │ ────────────────────────────► │                                │
    │                            │                              │                                │
    │                            │                HandlerNodeHeartbeat.handle()                  │
    │                            │                  decide_heartbeat() -> UPDATE intent          │
    │                            │                  extends liveness_deadline                    │
    │                            │                              │                                │
    │                            │                [periodic: RuntimeTick]                        │
    │                            │                HandlerRuntimeTick: checks ack/liveness        │
    │                            │                  deadlines, emits timeout events              │
```

---

## Node Responsibilities

### NodeRegistrationOrchestrator (`ORCHESTRATOR_GENERIC`)

**Location**: `src/omnibase_infra/nodes/node_registration_orchestrator/`

The orchestrator is fully declarative — its `node.py` extends `NodeOrchestrator` with no custom methods. All behavior comes from `contract.yaml`. It subscribes to the following topics and routes each event to a dedicated handler:

| Event/Command | Topic | Handler |
|---------------|-------|---------|
| `ModelNodeIntrospectionEvent` | `onex.evt.platform.node-introspection.v1` | `HandlerNodeIntrospected` |
| `ModelRuntimeTick` | `onex.intent.platform.runtime-tick.v1` | `HandlerRuntimeTick` |
| `ModelNodeRegistrationAcked` | `onex.cmd.platform.node-registration-acked.v1` | `HandlerNodeRegistrationAcked` |
| `ModelNodeHeartbeatEvent` | `onex.evt.platform.node-heartbeat.v1` | `HandlerNodeHeartbeat` |
| `ModelTopicCatalogQuery` | `onex.cmd.platform.topic-catalog-query.v1` | `HandlerTopicCatalogQuery` |

All handlers follow the **Reducer-Authoritative** pattern:
1. Handler reads projection state (direct I/O via `ProjectionReaderRegistration`)
2. Handler delegates decision to `RegistrationReducerService` (pure function, zero I/O)
3. Handler returns `ModelHandlerOutput` with `events` and `intents` from the decision

### NodeRegistryEffect (`EFFECT_GENERIC`)

**Location**: `src/omnibase_infra/nodes/node_registry_effect/`

Executes registration intents against two backends **in parallel** using `asyncio.gather()`:

- `HandlerConsulRegister` - Registers the service with Consul for discovery
- `HandlerPostgresUpsert` - Persists the registration record to PostgreSQL
- `HandlerConsulDeregister` - Removes the service from Consul
- `HandlerPostgresDeactivate` - Marks registration inactive in PostgreSQL
- `HandlerPartialRetry` - Retries a specific backend after partial failure

The node supports **partial failure**: if Consul succeeds but PostgreSQL fails (or vice versa), the response status is `"partial"` with each backend's result recorded independently. Callers can retry the failed backend via `retry_partial_failure`.

Per-backend circuit breakers (threshold: 5 failures, reset: 60s) protect against cascading failures.

### NodeRegistrationReducer (`REDUCER_GENERIC`)

**Location**: `src/omnibase_infra/nodes/node_registration_reducer/`

FSM-driven reducer for ONEX-compliant runtime execution via `RuntimeHostProcess`. All state transition logic is driven by `contract.yaml` FSM configuration, not Python code. The FSM states are:

```text
idle -> pending -> partial -> complete
                           \-> failed -> idle (on reset)
```

This node handles the runtime-execution path. The orchestrator's inline `RegistrationReducerService` handles the high-frequency handler path (see below).

### NodeRegistrationStorageEffect (`EFFECT_GENERIC`)

**Location**: `src/omnibase_infra/nodes/node_registration_storage_effect/`

Capability-oriented storage node named by what it does (`registration.storage`), not by vendor. Supports pluggable backends through `ProtocolRegistrationPersistence`. Used for querying and updating registration records independent of the dual-backend registration flow.

---

## Phase 1: Introspection and Registration Initiation

**Trigger**: A node publishes `ModelNodeIntrospectionEvent` to `onex.evt.platform.node-introspection.v1` on startup.

**Handler**: `HandlerNodeIntrospected`

```text
HandlerNodeIntrospected.handle(envelope):
    1. Extract: event, now, correlation_id from envelope
    2. I/O: ProjectionReaderRegistration.get_entity_state(node_id, "registration")
    3. Pure: RegistrationReducerService.decide_introspection(projection, event, ...)
    4. If decision.action == "no_op": return empty output (idempotent)
    5. Return ModelHandlerOutput(events=decision.events, intents=decision.intents)
```

**State Decision Matrix** (from `RegistrationReducerService.decide_introspection`):

| Current Projection State | Action |
|--------------------------|--------|
| `None` (new node) | Initiate registration |
| `LIVENESS_EXPIRED` | Initiate re-registration |
| `REJECTED` | Initiate retry |
| `ACK_TIMED_OUT` | Initiate retry |
| `PENDING_REGISTRATION` | No-op (already processing) |
| `ACCEPTED` | No-op (waiting for ack) |
| `AWAITING_ACK` | No-op (waiting for ack) |
| `ACK_RECEIVED` | No-op (transitioning) |
| `ACTIVE` | No-op (use heartbeat instead) |

**On initiation**, the reducer emits:

- **Event 1**: `ModelNodeRegistrationInitiated` (registration workflow started)
- **Event 2**: `ModelNodeRegistrationAccepted` (fast-forward; includes `ack_deadline = now + ack_timeout_seconds`)
- **Intent 1**: `postgres.upsert_registration` (upsert projection to `AWAITING_ACK`)
- **Intent 2**: `consul.register` (register service with Consul; omitted if `consul_enabled=False`)

---

## Phase 2: Effect Execution (Consul + PostgreSQL)

The orchestrator dispatches intents from Phase 1 to `NodeRegistryEffect`, which executes both backends in parallel:

```text
NodeRegistryEffect receives ModelRegistryRequest:
    asyncio.gather(
        HandlerConsulRegister.handle(request, correlation_id),
        HandlerPostgresUpsert.handle(request, correlation_id),
    )
```

**Consul registration** (`HandlerConsulRegister`):
- Generates `service_id = onex-{node_type}-{node_id}`
- Generates `service_name = onex-{node_type}` (or from request)
- Calls `ProtocolConsulClient.register_service()`
- Adds MCP tags (`mcp-enabled`, `mcp-tool:{name}`) for orchestrators with MCP exposed

**PostgreSQL upsert** (`HandlerPostgresUpsert`):
- Calls `ProtocolPostgresAdapter.upsert()` with `node_id`, `node_type`, `node_version`, `endpoints`, `metadata`
- Uses upsert semantics (idempotent re-registration)

**Response aggregation** (`aggregation_strategy: "all_or_partial"`):

| consul_result.success | postgres_result.success | Response status |
|-----------------------|------------------------|-----------------|
| `True` | `True` | `"success"` |
| `True` | `False` | `"partial"` |
| `False` | `True` | `"partial"` |
| `False` | `False` | `"failed"` |

---

## Phase 3: Node Acknowledgment

**Trigger**: The registered node consumes `ModelNodeRegistrationAccepted` and publishes `ModelNodeRegistrationAcked` to `onex.cmd.platform.node-registration-acked.v1`.

**Handler**: `HandlerNodeRegistrationAcked`

```text
HandlerNodeRegistrationAcked.handle(envelope):
    1. Extract: command, now, correlation_id from envelope
    2. I/O: ProjectionReaderRegistration.get_entity_state(node_id, "registration")
    3. Pure: RegistrationReducerService.decide_ack(projection, command, ...)
    4. If decision.new_state == ACTIVE and snapshot_publisher:
       await snapshot_publisher.publish_from_projection(active_projection)  # best-effort
    5. Return ModelHandlerOutput(events=decision.events, intents=decision.intents)
```

**State Decision Matrix** (from `RegistrationReducerService.decide_ack`):

| Current State | Action |
|---------------|--------|
| `ACCEPTED` or `AWAITING_ACK` | Emit `AckReceived` + `BecameActive` + UPDATE intent |
| `ACK_RECEIVED` or `ACTIVE` | No-op (duplicate ack) |
| `PENDING_REGISTRATION` | No-op (ack too early) |
| `ACK_TIMED_OUT` | No-op (too late) |
| Terminal (`REJECTED`, `LIVENESS_EXPIRED`) | No-op |
| `None` | No-op (unknown node) |

**On valid ack**, the reducer emits:

- **Event 1**: `ModelNodeRegistrationAckReceived` (includes `liveness_deadline = now + liveness_interval_seconds`)
- **Event 2**: `ModelNodeBecameActive`
- **Intent**: `postgres.update_registration` (UPDATE projection to `ACTIVE`, set `liveness_deadline`)

After the UPDATE intent executes, the node is fully ACTIVE in both Consul and PostgreSQL.

---

## Phase 4: Heartbeat and Liveness

**Heartbeats** maintain liveness for ACTIVE nodes. The node publishes `ModelNodeHeartbeatEvent` to `onex.evt.platform.node-heartbeat.v1` every ~30 seconds.

**Handler**: `HandlerNodeHeartbeat`

```text
HandlerNodeHeartbeat.handle(envelope):
    1. I/O: ProjectionReaderRegistration.get_entity_state(node_id, "registration")
    2. If projection is None: return empty output (unknown node)
    3. If projection.current_state not ACTIVE: log warning, still process
    4. Pure: RegistrationReducerService.decide_heartbeat(projection, node_id, heartbeat_ts, ctx)
    5. Return ModelHandlerOutput(intents=decision.intents)  # no events emitted
```

The heartbeat decision emits one intent:
- `postgres.update_registration` with `ModelRegistrationHeartbeatUpdate`:
  - `last_heartbeat_at = heartbeat_timestamp`
  - `liveness_deadline = heartbeat_timestamp + liveness_window_seconds`
  - `updated_at = now`

**Timeout detection** runs on each `ModelRuntimeTick` via `HandlerRuntimeTick`:

```text
HandlerRuntimeTick.handle(envelope):
    1. I/O: Query projection for overdue ack deadlines (state=AWAITING_ACK)
    2. I/O: Query projection for overdue liveness deadlines (state=ACTIVE)
    3. Pure: RegistrationReducerService.decide_timeout(overdue_ack, overdue_liveness, ctx)
    4. For each NodeLivenessExpired: publish tombstone (best-effort)
    5. Return ModelHandlerOutput(events=decision.events)
```

Timeout events emitted:
- `ModelNodeRegistrationAckTimedOut` — node did not ack within `ack_timeout_seconds`
- `ModelNodeLivenessExpired` — no heartbeat received within `liveness_window_seconds`

Deduplication: the projection stores `ack_timeout_emitted_at` and `liveness_timeout_emitted_at` markers. The projection reader filters already-emitted timeouts; the reducer performs a secondary check via `projection.needs_ack_timeout_event()` / `projection.needs_liveness_timeout_event()`.

---

## RegistrationReducerService: Decision Methods

`RegistrationReducerService` (`src/omnibase_infra/nodes/node_registration_orchestrator/services/registration_reducer_service.py`) is the **authoritative decision-maker** for all registration FSM transitions.

It is a stateless, pure-function service — **zero I/O, zero imports of ProjectorShell or EventBus**. All four `decide_*` methods return a frozen `ModelReducerDecision`.

### Constructor

```python
RegistrationReducerService(
    ack_timeout_seconds: float = 30.0,       # ack deadline window
    liveness_interval_seconds: int = 60,     # initial liveness deadline offset
    liveness_window_seconds: float = 90.0,   # heartbeat deadline extension
    consul_enabled: bool = True,             # whether to emit consul.register intents
)
```

### `decide_introspection(projection, event, correlation_id, now)`

Called by `HandlerNodeIntrospected` when an introspection event arrives.

**Returns** `ModelReducerDecision` with:
- `action="no_op"` if state blocks new registration
- `action="emit"` with:
  - `new_state = AWAITING_ACK`
  - `events = (ModelNodeRegistrationInitiated, ModelNodeRegistrationAccepted)`
  - `intents = (postgres_upsert_intent [, consul_register_intent])`

### `decide_ack(projection, command, correlation_id, now)`

Called by `HandlerNodeRegistrationAcked` when a node sends its acknowledgment.

**Returns** `ModelReducerDecision` with:
- `action="no_op"` for invalid states (unknown, duplicate, too early, too late, terminal)
- `action="emit"` with:
  - `new_state = ACTIVE`
  - `events = (ModelNodeRegistrationAckReceived, ModelNodeBecameActive)`
  - `intents = (postgres_update_intent,)` — sets `current_state=ACTIVE`, `liveness_deadline`

### `decide_heartbeat(projection, node_id, heartbeat_timestamp, ctx)`

Called by `HandlerNodeHeartbeat` for each periodic heartbeat event.

**Returns** `ModelReducerDecision` with:
- `action="no_op"` if projection is `None`
- `action="emit"` with:
  - `new_state = None` (no FSM transition)
  - `events =` (heartbeats emit no domain events)
  - `intents = (postgres_update_intent,)` — sets `last_heartbeat_at`, extends `liveness_deadline`

### `decide_timeout(overdue_ack_projections, overdue_liveness_projections, ctx)`

Called by `HandlerRuntimeTick` on each runtime tick.

**Returns** `ModelReducerDecision` with:
- `action="no_op"` if no timeouts detected
- `action="emit"` with:
  - `events = (ModelNodeRegistrationAckTimedOut*, ModelNodeLivenessExpired*)`
  - `intents =` (timeout events update state via projection, not direct intent)

---

## FSM State Machine

```
                 ┌────────────────────────────────────────────┐
                 │              Registration FSM               │
                 │                                            │
   Introspection │                                            │
   (new/retriable)                                           │
       │         │   ┌──────────────────────────────────────┐│
       │         │   │  PENDING_REGISTRATION (intermediate) ││
       │         │   └──────────────────────────────────────┘│
       ▼         │                                            │
  ┌──────────┐   │                                           │
  │AWAITING  │◄──┤── decide_introspection emits upsert intent│
  │   ACK    │   │                                           │
  └────┬─────┘   │                                           │
       │         │  ┌──────────────┐                         │
       │ valid   │  │ ACK_TIMED_OUT│◄── ack_deadline expired │
       │ ack     │  └──────────────┘                         │
       ▼         │       (retriable: next introspection       │
  ┌──────────┐   │        re-initiates)                      │
  │  ACTIVE  │   │                                           │
  └────┬─────┘   │                                           │
       │         │  ┌─────────────────┐                      │
       │ liveness│  │ LIVENESS_EXPIRED │◄── liveness_deadline│
       │ expires │  └─────────────────┘    expired           │
       │         │       (retriable: next introspection       │
       │         │        re-initiates)                      │
       │         │                                           │
       │  ┌──────────────┐                                   │
       │  │   REJECTED   │ (non-retriable terminal; future use)
       │  └──────────────┘                                   │
       │         └────────────────────────────────────────────┘
       │
       │ Heartbeats (while ACTIVE):
       │   decide_heartbeat -> postgres UPDATE (liveness_deadline extended)
       │
       │ RuntimeTick (periodic):
       │   decide_timeout -> emits AckTimedOut or LivenessExpired events
```

**Retriable states** (node can re-register on next introspection):
- `LIVENESS_EXPIRED`
- `REJECTED`
- `ACK_TIMED_OUT`

**Blocking states** (no-op on introspection):
- `PENDING_REGISTRATION`, `ACCEPTED`, `AWAITING_ACK`, `ACK_RECEIVED`, `ACTIVE`

---

## ModelIntent Construction

All intents are built in `RegistrationReducerService` and returned via `ModelReducerDecision.intents`. The two-layer intent structure:

**Layer 1 — Typed Payload**: Domain-specific Pydantic model with `intent_type` field (a `Literal` string).

**Layer 2 — Outer Container**: `ModelIntent` with `intent_type="extension"` (or the payload's `intent_type`) and a `target` URI.

### Target URI Convention

```
{protocol}://{resource}/{identifier}
```

Examples:
- `postgres://node_registrations/{node_id}` — upsert or update
- `consul://service/{service_name}` — service registration

### PostgreSQL Upsert Intent (Phase 1)

```python
postgres_payload = ModelPayloadPostgresUpsertRegistration(
    correlation_id=correlation_id,
    record=ModelProjectionRecord(
        entity_id=node_id,
        domain="registration",
        current_state=EnumRegistrationState.AWAITING_ACK.value,
        node_type=node_type.value,
        data={
            "ack_deadline": ack_deadline,
            "registered_at": now,
            ...
        },
    ),
)
ModelIntent(
    intent_type=postgres_payload.intent_type,  # "postgres.upsert_registration"
    target=f"postgres://node_registrations/{node_id}",
    payload=postgres_payload,
)
```

### Consul Register Intent (Phase 1)

```python
consul_payload = ModelPayloadConsulRegister(
    correlation_id=correlation_id,
    service_id=f"onex-{node_type.value}-{node_id}",
    service_name=f"onex-{node_type.value}",
    tags=["onex", f"node-type:{node_type.value}", ...],  # + mcp tags if applicable
    address=address,   # extracted from endpoints["health"] or endpoints["api"]
    port=port,
)
ModelIntent(
    intent_type=consul_payload.intent_type,  # "consul.register"
    target=f"consul://service/{service_name}",
    payload=consul_payload,
)
```

### PostgreSQL Update Intent (Phase 3 — Ack)

```python
update_payload = ModelPayloadPostgresUpdateRegistration(
    correlation_id=correlation_id,
    entity_id=node_id,
    domain="registration",
    updates=ModelRegistrationAckUpdate(
        current_state=EnumRegistrationState.ACTIVE.value,
        liveness_deadline=now + timedelta(seconds=liveness_interval_seconds),
        updated_at=now,
    ),
)
ModelIntent(
    intent_type=update_payload.intent_type,  # "postgres.update_registration"
    target=f"postgres://node_registrations/{node_id}",
    payload=update_payload,
)
```

### PostgreSQL Update Intent (Phase 4 — Heartbeat)

```python
update_payload = ModelPayloadPostgresUpdateRegistration(
    correlation_id=correlation_id,
    entity_id=node_id,
    domain="registration",
    updates=ModelRegistrationHeartbeatUpdate(
        last_heartbeat_at=heartbeat_timestamp,
        liveness_deadline=heartbeat_timestamp + timedelta(seconds=liveness_window_seconds),
        updated_at=ctx.now,
    ),
)
ModelIntent(
    intent_type=update_payload.intent_type,  # "postgres.update_registration"
    target=f"postgres://node_registrations/{node_id}",
    payload=update_payload,
)
```

---

## Kafka Topics

### Consumed by NodeRegistrationOrchestrator

| Topic | Format | Purpose |
|-------|--------|---------|
| `onex.evt.platform.node-introspection.v1` | `ModelNodeIntrospectionEvent` | Node startup announcement |
| `onex.evt.platform.registry-request-introspection.v1` | `RegistryRequestIntrospectionEvent` | Explicit re-introspection request |
| `onex.intent.platform.runtime-tick.v1` | `ModelRuntimeTick` | Periodic timeout evaluation |
| `onex.cmd.platform.node-registration-acked.v1` | `ModelNodeRegistrationAcked` | Node acknowledges acceptance |
| `onex.evt.platform.node-heartbeat.v1` | `ModelNodeHeartbeatEvent` | Liveness heartbeat (direct handler) |
| `onex.cmd.platform.topic-catalog-query.v1` | `ModelTopicCatalogQuery` | Dashboard topic catalog request |

Topics use the **realm-agnostic 5-segment ONEX format**: `onex.<kind>.<producer>.<event-name>.v<version>`. Realm/environment is enforced via envelope identity, not topic naming.

### Published by NodeRegistrationOrchestrator

| Topic | Event Type | When Published |
|-------|------------|----------------|
| `onex.evt.platform.node-registration-initiated.v1` | `ModelNodeRegistrationInitiated` | Phase 1: registration started |
| `onex.evt.platform.node-registration-accepted.v1` | `ModelNodeRegistrationAccepted` | Phase 1: fast-forward to AWAITING_ACK |
| `onex.evt.platform.node-registration-ack-received.v1` | `ModelNodeRegistrationAckReceived` | Phase 3: valid ack received |
| `onex.evt.platform.node-became-active.v1` | `ModelNodeBecameActive` | Phase 3: node transitions to ACTIVE |
| `onex.evt.platform.node-registration-ack-timed-out.v1` | `ModelNodeRegistrationAckTimedOut` | Phase 4 (tick): ack deadline expired |
| `onex.evt.platform.node-liveness-expired.v1` | `ModelNodeLivenessExpired` | Phase 4 (tick): heartbeat deadline expired |
| `onex.evt.platform.node-registration-result.v1` | `NodeRegistrationResultEvent` | Aggregate outcome |
| `onex.evt.platform.topic-catalog-response.v1` | `ModelTopicCatalogResponse` | Catalog snapshot |
| `onex.evt.platform.topic-catalog-changed.v1` | `TopicCatalogChanged` | Catalog version changed |
| `onex.evt.platform.node-registration-rejected.v1` | `NodeRegistrationRejected` | Registration rejected |

### Intent Routing Table

Intents emitted by handlers are routed by `intent_type` to `NodeRegistryEffect`:

| `intent_type` | Routes To |
|---------------|-----------|
| `consul.register` | `NodeRegistryEffect` (HandlerConsulRegister) |
| `consul.deregister` | `NodeRegistryEffect` (HandlerConsulDeregister) |
| `postgres.upsert_registration` | `NodeRegistryEffect` (HandlerPostgresUpsert) |
| `postgres.update_registration` | `NodeRegistryEffect` (HandlerPostgresUpsert) |

---

## Error Paths

### Consul Unreachable

`HandlerConsulRegister` catches `InfraConnectionError`, `InfraTimeoutError`, and `InfraAuthenticationError`. It does **not** raise — all errors return `ModelBackendResult(success=False, error_code=...)`. Error messages are sanitized to prevent credential exposure.

Result status in `NodeRegistryEffect` response:
- `"partial"` if PostgreSQL succeeded
- `"failed"` if both failed

The node remains in `AWAITING_ACK` state in PostgreSQL. On the next introspection event, `decide_introspection` will re-initiate (since `AWAITING_ACK` is a blocking state, a re-introspection within the ack window is a no-op; after `ACK_TIMED_OUT` it becomes retriable).

**Circuit breaker**: 5 consecutive Consul failures open the circuit for 60 seconds (`CONSUL_CONNECTION_ERROR`, `CONSUL_TIMEOUT_ERROR` are retriable; `CONSUL_AUTH_ERROR` is not).

### PostgreSQL Fails

Same pattern as Consul. `HandlerPostgresUpsert` returns `ModelBackendResult(success=False)`. The registration projection is not written, so the next introspection event for this node will see `projection=None` (new node) and re-initiate.

**Circuit breaker**: per-backend, same thresholds as Consul.

### Ack Timeout

`HandlerRuntimeTick` is called on each `RuntimeTick`. `RegistrationReducerService.decide_timeout()` checks `projection.needs_ack_timeout_event(now)` for nodes in `AWAITING_ACK`. When expired:
1. `ModelNodeRegistrationAckTimedOut` is emitted
2. The projection is updated to `ACK_TIMED_OUT` (retriable state)
3. Next introspection from the node re-initiates registration

Deduplication via `ack_timeout_emitted_at` marker prevents duplicate timeout events across ticks.

### Liveness Expiry

`HandlerRuntimeTick` checks `projection.needs_liveness_timeout_event(now)` for ACTIVE nodes. When `liveness_deadline` is passed:
1. `ModelNodeLivenessExpired` is emitted
2. The orchestrator publishes a tombstone (best-effort, non-blocking)
3. The projection moves to `LIVENESS_EXPIRED` (retriable state)
4. Next introspection from the node re-initiates registration

### Unknown Ack

If a `ModelNodeRegistrationAcked` arrives for a node with no projection (`projection=None`), `decide_ack` returns `action="no_op"` with reason `"Unknown node"`. The command is silently dropped.

### Snapshot Publish Failure

After a valid ack, `HandlerNodeRegistrationAcked` attempts to publish a compacted ACTIVE snapshot via `ProtocolSnapshotPublisher`. Snapshot publishing is **always best-effort and non-blocking** — exceptions are caught and logged as `WARNING`, but the handler output is unaffected. The node still becomes ACTIVE.

---

## E2E Test Coverage

The E2E test suite covers 53 tests across three files in `tests/integration/registration/e2e/`.

All tests require ALL infrastructure services available (PostgreSQL, Consul, Kafka). The `conftest.py` checks an `ALL_INFRA_AVAILABLE` guard; tests are auto-skipped when infrastructure is absent.

### `test_two_way_registration_e2e.py` — 36 tests

| Suite | Coverage |
|-------|----------|
| Suite 1: Node Startup and Introspection | Introspection publish, event structure, custom endpoints, broadcast latency (<50ms), node types |
| Suite 2: Registry Dual Registration | Consul registration, PostgreSQL registration, dual registration, latency (<300ms), handler idempotency (blocking states), retriable states |
| Suite 3: Re-Introspection | Registry startup triggers re-introspection, nodes respond with fresh events, request-response correlation |
| Suite 4: Heartbeat Publishing | Heartbeat every 30s, uptime/operations fields, overhead threshold, projection liveness update, interval consistency |
| Suite 5: Registry Recovery | Recovery after restart, re-registration after recovery, idempotent upsert |
| Suite 6: Multiple Nodes | Simultaneous registration, no race conditions, all nodes appear in registry |
| Suite 7: Graceful Degradation | Kafka unavailable, Consul unavailable, PostgreSQL unavailable, partial success reporting, partial success timing |
| Suite 8: Registry Self-Registration | Registry registers itself, self-registration in database, introspection data completeness, custom capabilities, discoverable by other nodes |

### `test_full_orchestrator_flow.py` — 9 tests

- `TestFullOrchestratorFlow`: Full pipeline with mocked infrastructure
- `TestFullPipelineWithRealInfrastructure`: Real Kafka/Consul/PostgreSQL integration
- `TestPipelineLifecycle`: Lifecycle management and cleanup

### `test_runtime_e2e.py` — 8 tests

- `TestRuntimeE2EFlow`: Runtime-level E2E flow (auto-enabled when runtime is healthy)
- `TestRuntimeErrorHandling`: Error scenarios at runtime level
- `TestRuntimePerformance`: Performance benchmarks

### Running E2E Tests

```bash
# All E2E tests (requires infrastructure)
uv run pytest tests/integration/registration/e2e/ -m integration

# Specific suite
uv run pytest tests/integration/registration/e2e/test_two_way_registration_e2e.py -m integration -v

# With real runtime (uses .env.docker for local Docker infra)
# See tests/integration/registration/e2e/.env.docker for environment overrides
```

Two-layer environment loading applies to E2E tests:
1. `.env` (base — points to remote infra at `<onex-host>`)
2. `tests/integration/registration/e2e/.env.docker` (override — redirects to local Docker infra at container-internal addresses)

---

## Related Documentation

- [Architecture Overview](2026-07-21-onex-runtime-overview.md) — High-level system architecture
- Handler Protocol-Driven Architecture — Handler system design
- [Snapshot Publishing](2026-07-21-snapshot-publishing.md) — Snapshot publication patterns
- [Event Bus Integration Guide](2026-07-21-event-bus-integration.md) — Kafka event streaming
- 2-Way Registration Walkthrough — Code examples for all 4 phases
- Error Handling Patterns — Error hierarchy and sanitization
- Circuit Breaker Implementation — Circuit breaker details
