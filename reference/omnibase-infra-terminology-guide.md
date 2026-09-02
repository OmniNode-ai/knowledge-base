---
type: reference
status: current
date: "2026-09-02"
title: "Terminology Guide"
topics: [omnibase-infra, terminology, guide]
refs: []
---

<!-- Migrated from omnibase_infra:docs/conventions/TERMINOLOGY_GUIDE.md on 2026-09-02. -->

# Terminology Guide

> **Status**: Current | **Last Updated**: 2026-02-19

Canonical definitions for ONEX architectural terms as used in `omnibase_infra`. These are not dictionary definitions — each entry explains what the term means architecturally: its role in the data flow, its invariants, and how it differs from related terms.

For capitalization rules in prose vs. code contexts, see the quick-reference table at the top of this document. For naming file and class conventions, see `NAMING_CONVENTIONS.md`.

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Four-Node Architecture Terms](#four-node-architecture-terms)
3. [Cross-Cutting Infrastructure Terms](#cross-cutting-infrastructure-terms)
4. [Event Bus and Messaging Terms](#event-bus-and-messaging-terms)
5. [Data Flow Terms](#data-flow-terms)
6. [DI Container Terms](#di-container-terms)
7. [Common Confusions](#common-confusions)

---

## Quick Reference

| Term | Code Context | Prose Context | Class Prefix | Not This |
|------|-------------|---------------|--------------|----------|
| Effect node | `EFFECT` (ALL CAPS in constants) | "effect node" (lowercase) | `NodeXxxEffect` | "Effect Node", "EffectNode" |
| Compute node | `COMPUTE` | "compute node" | `NodeXxxCompute` | "ComputeNode", "COMPUTE" alone |
| Reducer node | `REDUCER` | "reducer node" | `NodeXxxReducer` | "ReducerNode" |
| Orchestrator node | `ORCHESTRATOR` | "orchestrator node" | `NodeXxxOrchestrator` | "OrchestratorNode" |
| DI container | `ModelONEXContainer` | "DI container" or "service container" | — | "container" alone (ambiguous) |
| Value wrapper | `ModelContainer[T]` | "value wrapper" | — | "DI container" (wrong type) |
| Side-effect request | `ModelIntent` | "intent" | `ModelPayload*` (payload) | "action", "command", "thunk" |
| State snapshot | `ModelProjection` / projection | "projection" | `Model*Projection` | "snapshot" (use only for point-in-time reads) |
| Message envelope | `ModelEventEnvelope[T]` | "envelope" | — | "message", "event" alone |
| Event payload | varies | "event" or "payload" | `Model*Event` | "message" (too generic) |
| FSM transition fn | `delta(state, event) -> (state, intents[])` | "delta function" | — | "reducer function" alone |

---

## Four-Node Architecture Terms

### Effect

**Architectural meaning**: An effect node handles all external I/O — database reads and writes, HTTP calls, Kafka publish/consume, Consul registration, Vault secret fetch, filesystem operations. It is the only node type that crosses system boundaries.

**Invariants**:
- Accepts external I/O results and converts them into internal events
- Cannot emit `result` — it emits `events[]`
- May emit `error` if the I/O fails
- Must not perform pure computation — delegate to a compute node

**Code context**: `EFFECT_GENERIC` in contract `node_type`; `NodeEffect` base class; class suffix `Effect` (e.g., `NodeRegistrationStorageEffect`).

**Prose context**: "the effect node", "an effect node", "effect nodes".

**When writing about effect nodes**: Emphasize the boundary crossing. "The registration storage effect node writes the node registration record to PostgreSQL."

---

### Compute

**Architectural meaning**: A compute node performs pure data transformation. It receives input, applies deterministic logic, and returns `result`. It does not perform I/O, read from the database, or publish events.

**Invariants**:
- `result` is **required** (the only node type where `result` must be populated)
- No external I/O — any I/O requirement must be delegated to an effect node
- Deterministic: same input always produces same output
- No side effects — no publishing, no writing

**Code context**: `COMPUTE_GENERIC`; `NodeCompute` base class; class suffix `Compute`.

**Prose context**: "the compute node", "a compute node".

**Common example**: Validating a node registration request, computing a baseline comparison, projecting ledger entries.

---

### Reducer

**Architectural meaning**: A reducer node manages FSM (Finite State Machine) state transitions. It receives an event, applies the delta function, and produces a new state plus zero or more intents that describe side effects to be executed.

**Delta function signature**: `delta(state, event) -> (new_state, intents[])`

**Invariants**:
- **Pure** — no I/O inside the delta function
- State transitions are explicit and auditable
- Emits `projections[]` (state snapshots) and `intents[]` (side-effect requests)
- Never performs direct I/O — intents are routed to effect nodes by the orchestrator
- Does not use `asyncio`, databases, or network calls internally

**Code context**: `REDUCER_GENERIC`; `NodeReducer` base class; class suffix `Reducer`.

**Prose context**: "the reducer node", "a reducer node", "the registration reducer".

**The term "FSM" is preferred over "state machine" alone.** Write "the registration reducer uses a pure FSM pattern" rather than "uses a state machine."

---

### Orchestrator

**Architectural meaning**: An orchestrator node coordinates workflow execution. It receives events (typically from the event bus), routes them to the appropriate handler, and emits output events and intents. It is the only node type that may publish events.

**Invariants**:
- **Cannot return `result`** — this raises a `ValueError` at runtime
- Emits `events[]` and/or `intents[]`
- Receives intents from reducers and routes them to the effect layer
- Does not perform computation or hold state itself
- Handler routing is declared in `contract.yaml`, not in `node.py`

**Code context**: `ORCHESTRATOR_GENERIC`; `NodeOrchestrator` base class; class suffix `Orchestrator`.

**Prose context**: "the orchestrator node", "the registration orchestrator".

---

## Cross-Cutting Infrastructure Terms

### Handler

**Architectural meaning**: A handler is a unit of business logic invoked by a node to process a single event or request. Handlers encapsulate the "what" — they compute results, call services, and return output. They do not emit events directly.

**Two protocols**:
- `ProtocolHandler` — request/response I/O; used for HTTP, DB, and Kafka handlers. Input is `ModelProtocolRequest`, output is `ModelProtocolResponse`.
- `ProtocolMessageHandler` — category-based; used by the dispatch engine. Input is `ModelEventEnvelope`, output is `ModelHandlerOutput`.

**Handler No-Publish Rule**: Handlers must not hold a reference to the event bus or call any publish method. Only orchestrators publish events. This constraint is enforced by the architecture validator.

**Code naming**: `handler_<name>.py` / `Handler<Name>`.

---

### Dispatcher

**Architectural meaning**: A dispatcher is an adapter that sits between a handler and the event bus. After a handler produces `ModelHandlerOutput`, the corresponding dispatcher translates that output into one or more event bus publications.

Dispatchers own their own resilience via `MixinAsyncCircuitBreaker`. The `MessageDispatchEngine` does not wrap them.

**Code naming**: `dispatcher_<name>.py` / `Dispatcher<Name>`. Each dispatcher mirrors its handler in name.

---

### Intent

**Architectural meaning**: An intent is a declarative side-effect request emitted by a reducer. It describes *what should happen* without doing it. The orchestrator receives intents from reducer output and routes them to the appropriate effect node.

**Two-layer structure**:
1. `ModelIntent` — the outer envelope. `intent_type` is always `"extension"` for infrastructure intents. `target` is a URI like `consul://service/onex-effect`.
2. Typed payload — a Pydantic model extending `BaseModel` directly with its own `intent_type` discriminator (e.g., `Literal["consul.register"]`).

**Do not call intents**: "actions", "commands", "thunks", or "side effects" (the latter describes their effect, not the object).

**Example**: A reducer emits a `ModelPayloadConsulRegister` wrapped in `ModelIntent` to request Consul service registration without performing that registration itself.

---

### Projection

**Architectural meaning**: A projection is a read-optimized view of state derived from events. Reducers emit `projections[]` — these are state snapshots written to the projection store (e.g., PostgreSQL) for downstream queries.

Projections are distinct from the FSM state held in the reducer: the FSM state drives transitions; projections enable external reads without querying the FSM.

**Code naming**: `Model*Projection` for projection models (e.g., `ModelRegistrationProjection`).

**Not the same as "snapshot"**: A snapshot is a point-in-time capture of the full state, typically used for event sourcing replay optimization. A projection is a derived query-optimized view.

---

### Envelope

**Architectural meaning**: An envelope is the transport wrapper for all events on the ONEX event bus. It carries metadata (correlation ID, causation ID, timestamps, node identity) alongside the event payload.

- `ModelEventEnvelope[T]` — the canonical runtime envelope used by the dispatch engine and `ProtocolMessageHandler`.

Envelopes are always frozen (`frozen=True`). They cross node boundaries and must be immutable.

**Do not confuse envelope with payload**: The envelope is the wrapper; the payload is the domain data inside.

---

## Event Bus and Messaging Terms

### Event Bus

**Architectural meaning**: The event bus is the pub/sub backbone of the ONEX platform. It decouples nodes by routing events between them. The bus is accessed only through `ProtocolEventBus` — never directly.

**Two implementations**:
- `EventBusKafka` — production; backed by Redpanda/Kafka at `localhost:19092` (external) or `redpanda:9092` (Docker-internal).
- `EventBusInmemory` — testing; all events remain in process.

**Wire format**: `EventBusKafka.publish_envelope()` wraps events in `ModelEventEnvelope`. Consumer callbacks must unwrap `data.get("payload", data)` to access the actual event data.

---

### Topic

**Architectural meaning**: A topic is a named channel on the event bus. Topics follow the hierarchical naming pattern `onex.<domain>.<entity>.<event-type>`. All topics use the `onex.` prefix.

**Topics must exist before use.** The `RuntimeHostProcess` runs `TopicProvisioner` at startup to create topics declared in contracts. Integration tests that bypass the runtime must pre-create their topics.

---

### DLQ (Dead Letter Queue)

**Architectural meaning**: A DLQ is the destination for events that fail processing after all retry attempts. DLQ topics follow the `onex.dlq.*` reserved prefix. Error messages written to the DLQ must have secrets sanitized before serialization.

---

## Data Flow Terms

### Contract

**Architectural meaning**: A `contract.yaml` file is the source of truth for a node's behavior. It declares the node type, I/O models, handler routing strategy, dependencies, and version. Code in `node.py` is declarative — it extends a base class and calls `super().__init__(container)`. All behavior is driven by the contract.

**Fail-fast rule**: When both `contract.yaml` and `handler_contract.yaml` exist in the same directory, the handler plugin loader raises `AMBIGUOUS_CONTRACT_CONFIGURATION` (error code `HANDLER_LOADER_040`).

---

### Node Identity

**Term**: `ModelNodeIdentity`

**Architectural meaning**: A model carrying the stable identity of a running node instance: node ID, node name, node type, version. Used as the source for Consul service registration, Kafka consumer group derivation, and observability labeling.

---

## DI Container Terms

### ModelONEXContainer (DI Container)

**Architectural meaning**: The dependency injection container that every node receives in its constructor. Services are registered and resolved by protocol name (a string). Nodes call `container.get_service("ProtocolEventBus")` — they do not construct services directly.

**Constructor pattern** (mandatory):

```python
from omnibase_core.models.container.model_onex_container import ModelONEXContainer

class NodeRegistrationOrchestrator(NodeOrchestrator):
    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)
```

**Do not confuse with `ModelContainer[T]`** — that is an unrelated value-wrapper model for carrying typed values with metadata.

### ProtocolEventBus

**Architectural meaning**: The protocol interface for the event bus. Orchestrators resolve it via the DI container. It is never injected into handlers.

```python
bus = container.get_service("ProtocolEventBus")
```

---

## Common Confusions

### Intent vs. Action

- **Intent** (`ModelIntent`): A reducer's declarative request for a side effect. No I/O occurs inside the reducer; the orchestrator routes intents to effect nodes.
- **Action**: Used in `omnibase_core` to describe orchestrator-issued commands with lease semantics. Do not use "action" to mean "intent" in `omnibase_infra` without qualification.

### Projection vs. Snapshot

- **Projection**: A live, query-optimized view derived from events. Written by reducers as `projections[]`.
- **Snapshot**: A point-in-time capture of full state, used for event-sourcing replay optimization. Snapshots are stored in the checkpoint system (`node_checkpoint_effect`).

### Handler vs. Dispatcher

- **Handler**: Computes the result. Knows nothing about the event bus.
- **Dispatcher**: Publishes the result to the event bus. Mirrors the handler name.

### ModelONEXContainer vs. ModelContainer[T]

- `ModelONEXContainer`: The DI container. Pass to node constructors. Resolves services by protocol name.
- `ModelContainer[T]`: A generic value-wrapper model. Wraps a typed value with metadata. Has nothing to do with dependency injection.

### Effect Node vs. "Side Effect"

- **Effect node**: A node type in the four-node architecture. Handles external I/O.
- **Side effect**: The consequence of an intent being executed by an effect node. Do not use "side effect" to refer to the node itself.

---

## Related Documentation

- `CLAUDE.md` — Four-node pattern diagram, handler system, intent model architecture
- `docs/conventions/NAMING_CONVENTIONS.md` — File and class naming for all terms above
- `docs/patterns/container_dependency_injection.md` — DI container patterns
- `docs/patterns/protocol_patterns.md` — Protocol interface patterns
- `omnibase_core/docs/conventions/TERMINOLOGY_GUIDE.md` — Core-level terminology (node type capitalization, version references, FSM vs. state machine)
