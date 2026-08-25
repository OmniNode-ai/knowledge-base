---
type: reference
status: current
date: "2026-08-25"
title: "ONEX Core Terminology"
topics: [onex, terminology, four-node-architecture, handlers, runtime, projections]
refs: []
---

# ONEX Core Terminology

> **Source**: omnibase_core `docs/standards/onex_terminology.md`. Single authoritative document
> defining the core ONEX concepts. Originally authored 2025-12-19; migrated to the knowledge
> base 2026-08-25 with the HANDLER and RUNTIME sections corrected against live source (see the
> migration note before those two sections).

The ONEX (OmniNode eXecution) framework defines a structured vocabulary for building
distributed, event-driven systems. This document provides canonical definitions for the core
concepts that form the foundation of the ONEX architecture.

**Core Design Principles**:
- **Unidirectional Data Flow**: EFFECT → COMPUTE → REDUCER → ORCHESTRATOR
- **Separation of Concerns**: each node type has a single, well-defined responsibility
- **Declarative Configuration**: YAML contracts define behavior without custom code
- **Purity Preservation**: reducers emit Intents instead of performing side effects

> **Python Version**: 3.12+. Code examples use modern Python features including `datetime.UTC` and PEP 604 union syntax (`X | None`).

---

## Architectural Diagram

```text
                          ONEX Four-Node Architecture

    +-----------+     +-----------+     +-----------+     +---------------+
    |  EFFECT   |---->|  COMPUTE  |---->|  REDUCER  |---->| ORCHESTRATOR  |
    | External  |     |   Pure    |     | FSM State |     |   Workflow    |
    |    I/O    |     | Transform |     | + Intents |     | + Actions     |
    +-----------+     +-----------+     +-----------+     +---------------+
          |                                   |                   |
          |                                   v                   v
          |                            +-----------+       +-----------+
          |                            |  INTENT   |       |  ACTION   |
          |                            | (emitted) |       | (emitted) |
          +<---------------------------+-----------+       +-----------+
                   (executed by Effect)

    +---------------------------------------------------------------------------+
    |                              RUNTIME HOST                                  |
    |  +-------------+  +-------------+  +---------------+  +-----------------+ |
    |  |  Handler    |  |  Handler    |  |   Message     |  |    Projection   | |
    |  |  (HTTP)     |  |  (Kafka)    |  |   Dispatch    |  |      Store      | |
    |  +-------------+  +-------------+  +---------------+  +-----------------+ |
    +---------------------------------------------------------------------------+
```

---

## Core Concepts

### 1. EVENT

**Formal Definition**: A structured message wrapped in `ModelEventEnvelope` for inter-service
communication, providing standardized metadata, correlation tracking, security context, QoS
features, and distributed tracing.

**Key Model**: `ModelEventEnvelope[T]`
**File Location**: `src/omnibase_core/models/events/model_event_envelope.py`

**Key Features**: generic payload support, correlation-ID tracking, distributed tracing
(trace_id, span_id, request_id), QoS (priority 1–10, timeout, retry count), security context,
ONEX version compliance.

```python
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from uuid import uuid4

envelope = ModelEventEnvelope.create_broadcast(
    payload={"order_id": "12345", "status": "created"},
    source_node_id=uuid4(),
    correlation_id=uuid4(),
    priority=7,
)

if envelope.is_correlated():
    print(f"Correlation ID: {envelope.correlation_id}")
if envelope.is_high_priority():  # priority >= 8
    print("Processing high-priority event")
```

**Disambiguation**: "Event (Envelope)" — inter-service message wrapper, `ModelEventEnvelope[T]`.
"Event (FSM trigger)" — state-machine transition trigger, a plain string in the FSM contract.
"Event (messaging)" — generic message on the event bus, the payload inside the envelope.

---

### 2. ACTION

**Formal Definition**: An Orchestrator-issued command with lease-based ownership for
coordinating distributed workflows with single-writer semantics.

**Key Model**: `ModelAction`
**File Location**: `src/omnibase_core/models/orchestrator/model_action.py`

**Key Features**: lease-based ownership (`lease_id` proves Orchestrator authority),
epoch-based optimistic concurrency control, dependency tracking, priority-based scheduling,
timeout enforcement.

```python
from omnibase_core.models.orchestrator.model_action import ModelAction
from omnibase_core.nodes import EnumActionType  # Public API export
from uuid import uuid4

# NOTE: internal Orchestrator implementation detail. Application developers
# typically define actions in YAML contracts; direct instantiation shown for
# educational purposes only.
action = ModelAction(
    action_id=uuid4(),
    action_type=EnumActionType.COMPUTE,
    target_node_type="NodeDataTransformerCompute",
    payload={"transformation": "normalize"},
    lease_id=orchestrator_lease_id,
    epoch=current_epoch,
    priority=5,
    timeout_ms=10000,
)
```

**Important Clarification**: "Command" is NOT a formal ONEX concept. Use "Action" for
Orchestrator-issued commands. `ModelAction` is the canonical model; "command" may appear in
prose as the English noun describing what an Action represents.

---

### 3. INTENT

**Formal Definition**: A declarative side-effect specification emitted by a pure Reducer, to
be executed by an Effect node. Intents maintain Reducer purity by separating the decision of
"what should happen" from the execution of "how it happens": `delta(state, action) ->
(new_state, intents[])`.

**Key Models**: `ModelIntent` (Extension — open set for plugins/experiments, defined in
`src/omnibase_core/models/reducer/model_intent.py`) and `ModelCoreIntent` (Core — discriminated
union for core infrastructure, defined in `src/omnibase_core/models/intents/model_core_intent_base.py`).

| Tier | Model | Purpose | Use When |
|------|-------|---------|----------|
| **Core Intents** | `ModelCoreIntent` | Discriminated union with compile-time safety | Registration, persistence, lifecycle |
| **Extension Intents** | `ModelIntent` | Open set with runtime validation | Plugins, experiments, third-party integrations |

```python
from omnibase_core.models.reducer.model_intent import ModelIntent
from uuid import uuid4

intent = ModelIntent(
    intent_id=uuid4(),
    intent_type="database_write",
    target="orders_table",
    payload={"operation": "insert", "data": {"order_id": "12345", "status": "pending"}},
    priority=5,
    lease_id=workflow_lease_id,
    epoch=current_epoch,
)

return ModelReducerOutput(result=new_state, intents=[intent])  # Effect node executes these
```

---

### 4. REDUCER

**Formal Definition**: An FSM-driven node for pure state management that processes inputs and
emits state transitions plus Intents for side effects, without performing I/O directly.

**Key Class**: `NodeReducer` — `src/omnibase_core/nodes/node_reducer.py`
**Role**: third node in the pipeline (EFFECT → COMPUTE → REDUCER → ORCHESTRATOR).

**Key Features**: pure FSM pattern (`delta(state, action) -> (new_state, intents[])`),
YAML-driven state-machine definitions, no direct side effects, state-history tracking,
terminal-state detection.

```python
from omnibase_core.nodes import (
    NodeReducer, ModelReducerInput, ModelReducerOutput, EnumReductionType,
)
from omnibase_core.models.container.model_onex_container import ModelONEXContainer

class NodeOrderProcessingReducer(NodeReducer):
    """FSM-driven reducer for order state management (states in the YAML contract)."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)

node = NodeOrderProcessingReducer(container)
input_data = ModelReducerInput(
    data=[{"order_id": "12345"}],
    reduction_type=EnumReductionType.AGGREGATE,
    metadata={"trigger": "start_processing"},
)
result = await node.process(input_data)
```

---

### 5. ORCHESTRATOR

**Formal Definition**: A workflow-driven node for coordinating multi-step workflows across
distributed nodes, using Actions with lease-based single-writer semantics.

**Key Class**: `NodeOrchestrator` — `src/omnibase_core/nodes/node_orchestrator.py`
**Role**: fourth (final) node in the pipeline.

**Key Features**: YAML-driven workflow definitions, Action emission for deferred execution,
dependency-aware topological ordering, sequential/parallel/batch execution modes,
lease-based single-writer semantics, cycle detection.

```python
from omnibase_core.nodes import NodeOrchestrator, ModelOrchestratorInput, EnumExecutionMode
from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from uuid import uuid4

class NodeDataPipelineOrchestrator(NodeOrchestrator):
    """Workflow: 1. fetch_data (EFFECT) -> 2. validate (COMPUTE) -> 3. store (EFFECT)."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)

node = NodeDataPipelineOrchestrator(container)
input_data = ModelOrchestratorInput(
    workflow_id=uuid4(),
    steps=[
        {"step_id": uuid4(), "step_name": "Fetch", "step_type": "effect"},
        {"step_id": uuid4(), "step_name": "Validate", "step_type": "compute"},
    ],
    execution_mode=EnumExecutionMode.PARALLEL,
)
result = await node.process(input_data)
```

---

### 6. EFFECT

**Formal Definition**: A contract-driven node for executing external I/O operations including
database access, API calls, file operations, and event emission.

**Key Class**: `NodeEffect` — `src/omnibase_core/nodes/node_effect.py`
**Role**: first node in the pipeline.

**Key Features**: external I/O execution, transaction support with rollback, retry policies
with exponential backoff, circuit-breaker integration, Intent execution.

```python
from omnibase_core.nodes import NodeEffect, ModelEffectInput, ModelEffectOutput
from omnibase_core.models.container.model_onex_container import ModelONEXContainer

class NodeDatabaseWriterEffect(NodeEffect):
    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)
        self.db_pool = container.get_service("ProtocolDatabasePool")

    async def execute_effect(self, input_data: ModelEffectInput) -> ModelEffectOutput:
        async with self.transaction_context() as tx:
            result = await self.db_pool.execute(
                input_data.operation_config.query,
                input_data.operation_config.parameters,
            )
            tx.add_operation("write", input_data.operation_config, rollback_fn=lambda: self.db_pool.rollback())
        return ModelEffectOutput(
            correlation_id=input_data.correlation_id, operation_result=result, success=True,
        )
```

---

### 7. HANDLER

> **2026-08-25 migration correction**: the original section described a `ProtocolHandler`
> interface at `protocols/runtime/protocol_handler.py`, routed by a `RuntimeMessageDispatch`
> class. Neither exists in omnibase_core@dev — verified by a repo-wide search. The section
> below is rewritten against the real, currently-defined protocol. This is a genuine
> architectural rename/evolution, not a cosmetic path fix: see also the omnibase_core
> `CLAUDE.md` "Compute is a `NodeCompute` archetype" section, which documents that the
> pre-canonical envelope-in/envelope-out handler signature this section describes is distinct
> from (and not to be confused with) the canonical def-B `handle(request) -> response` signature
> used by COMPUTE-node handlers.

**Formal Definition**: An execution unit classified by message category (EVENT, COMMAND,
INTENT) and node kind (REDUCER, ORCHESTRATOR, EFFECT), implementing the `ProtocolMessageHandler`
protocol so the dispatch engine can route work to it without tight coupling to a concrete
implementation.

**Key Protocol**: `ProtocolMessageHandler`
**File Location**: `src/omnibase_core/protocols/runtime/protocol_message_handler.py`

**Role in Architecture**: message handlers receive a `ModelEventEnvelope`, process it
according to their category and node kind, and return a `ModelHandlerOutput` containing any
events, intents, or projections produced.

**Three Handler Sub-Patterns** (the sub-pattern names are unchanged from the original
document; only the concrete protocol/class identifiers were wrong):

| Pattern | Description | Example |
|---------|-------------|---------|
| **Protocol Handler** | I/O execution (implements `ProtocolMessageHandler`) | HTTP, Database, Kafka handlers |
| **Event Handler** | Pub/sub event handling (via `MixinEventHandler`) | Subscription-based event processing |
| **CLI Handler** | Command-line interface (via `MixinCLIHandler`) | CLI command processing |

```python
from omnibase_core.protocols.runtime import ProtocolMessageHandler
from omnibase_core.enums import EnumMessageCategory, EnumNodeKind
from omnibase_core.models.dispatch import ModelHandlerOutput

class UserEventHandler:
    """Handler for user-related events."""

    @property
    def handler_id(self) -> str:
        return "user-event-handler"

    @property
    def category(self) -> EnumMessageCategory:
        return EnumMessageCategory.EVENT

    # ... category/node_kind-appropriate handle(envelope) -> ModelHandlerOutput follows;
    # see protocol_message_handler.py's own module docstring for the full contract.
```

For the separate, canonical **COMPUTE**-node handler signature (`handle(request: ModelX) ->
ModelY`, no envelope, no `ModelHandlerOutput`), see the omnibase_core `CLAUDE.md` "Compute is
a `NodeCompute` archetype" section — that signature is not the one this HANDLER concept
describes.

---

### 8. PROJECTION

**Formal Definition**: Read-optimized materialized views for CQRS patterns, providing
eventual consistency via watermark tracking and version gating.

**Key Model**: `ModelProjectionBase` — `src/omnibase_core/models/projection/model_projection_base.py`

**Key Features**: key-version mapping to canonical state, watermark tracking, version gating
for read operations, fallback to canonical state when a projection lags.

```python
from omnibase_core.models.projection.model_projection_base import ModelProjectionBase
from pydantic import Field
from datetime import datetime, UTC
from typing import Any

class ModelWorkflowProjection(ModelProjectionBase):
    """Projection for workflow state, optimized for queries."""

    tag: str = Field(..., description="Workflow status (PENDING, PROCESSING, COMPLETED)")
    namespace: str = Field(..., description="Multi-tenant isolation namespace")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    indices: dict[str, Any] | None = Field(default=None, description="Custom query indices")

projection = await proj_store.get_state(key=workflow_key, required_version=5, max_wait_ms=100)
if projection is None:
    canonical = await canonical_store.get_state(key=workflow_key)  # projection lagging
```

**Note**: there is no explicit "Projector" class in omnibase_core. Projection materialization
is handled by application-level components that subscribe to state-change events.

---

### 9. RUNTIME

> **2026-08-25 migration correction**: the original section named `RuntimeMessageDispatch`,
> `RuntimeHandlerRegistry`, and `ModelRuntimeNodeInstance` as the runtime's key components.
> None of the three exist as class names in omnibase_core@dev. The verified live component
> that plays this role is `RuntimeLocal` (`src/omnibase_core/runtime/runtime_local.py`); handler
> registration lives on `ServiceHandlerRegistry` (`src/omnibase_core/services/service_handler_registry.py`,
> re-exported for convenience from `src/omnibase_core/runtime/runtime_handler_registry.py`).
> The code example below was rewritten rather than left with fabricated class names.

**Formal Definition**: the execution environment that hosts ONEX nodes, managing envelope
routing, handler registration, and service lifecycle.

**Key Components** (corrected against live source):

| Component | Description | Location |
|-----------|-------------|----------|
| `RuntimeLocal` | Local runtime — envelope routing and single-handler/event-driven dispatch | `src/omnibase_core/runtime/runtime_local.py` |
| `ServiceHandlerRegistry` | Handler registration and lookup | `src/omnibase_core/services/service_handler_registry.py` |
| `ProtocolMessageHandler` | Handler protocol (see HANDLER above) | `src/omnibase_core/protocols/runtime/protocol_message_handler.py` |
| `ModelONEXContainer` | DI container for services | `src/omnibase_core/models/container/model_onex_container.py` |

**Disambiguation** (unchanged from the original — this distinction is a design principle, not
a specific class name, and was not falsified):

| Type | Description | Characteristics |
|------|-------------|-----------------|
| **NodeRuntime** (Core) | Pure runtime logic | No event loop, deterministic |
| **RuntimeHostProcess** (Infrastructure) | Process with event loop | Manages lifecycle, I/O multiplexing |

For the exact dispatch entry points and the runtime-synthesized-terminal-event behavior, see
the omnibase_core `CLAUDE.md` "Runtime-synthesized terminal events" section and the
`_publish_synthesized_terminal` docstring in `runtime_local.py` directly, rather than a
reproduced code sample here — the original section's `RuntimeMessageDispatch(...).route(...)`
example does not correspond to any live API and was removed rather than replaced with an
unverified guess.

---

## Quick Reference Table

| Concept | Model/Class | File Location | Pipeline Position |
|---------|-------------|---------------|-------------------|
| **EVENT** | `ModelEventEnvelope[T]` | `models/events/model_event_envelope.py` | Transport layer |
| **ACTION** | `ModelAction` | `models/orchestrator/model_action.py` | Emitted by ORCHESTRATOR |
| **INTENT** | `ModelIntent` | `models/reducer/model_intent.py` | Emitted by REDUCER |
| **REDUCER** | `NodeReducer` | `nodes/node_reducer.py` | Position 3 |
| **ORCHESTRATOR** | `NodeOrchestrator` | `nodes/node_orchestrator.py` | Position 4 (final) |
| **EFFECT** | `NodeEffect` | `nodes/node_effect.py` | Position 1 |
| **HANDLER** | `ProtocolMessageHandler` | `protocols/runtime/protocol_message_handler.py` | Runtime layer |
| **PROJECTION** | `ModelProjectionBase` | `models/projection/model_projection_base.py` | CQRS read side |
| **RUNTIME** | `RuntimeLocal` | `runtime/runtime_local.py` | Infrastructure |

---

## When to Use Each Node Type

| If you need to... | Use | Example |
|-------------------|-----|---------|
| Read/write external data (DB, API, files) | **EFFECT** | Database queries, HTTP calls, file I/O |
| Transform data without side effects | **COMPUTE** | Data validation, format conversion, calculations |
| Manage state with FSM transitions | **REDUCER** | Order status workflow, user session state |
| Coordinate multi-step workflows | **ORCHESTRATOR** | ETL pipelines, saga patterns, batch processing |

### Decision Flowchart

```text
Start
  |
  +-- Does it involve external I/O? --Yes--> EFFECT
  |
  +-- Is it pure data transformation? --Yes--> COMPUTE
  |
  +-- Does it manage state transitions? --Yes--> REDUCER
  |
  +-- Does it coordinate multiple nodes? --Yes--> ORCHESTRATOR
```

### Common Patterns

| Pattern | Node Combination | Description |
|---------|------------------|-------------|
| **Read-Transform-Write** | EFFECT → COMPUTE → EFFECT | Fetch data, transform, persist |
| **Event-Sourced State** | EFFECT → REDUCER | Event ingestion with FSM state |
| **Orchestrated Pipeline** | ORCHESTRATOR → (EFFECT, COMPUTE, REDUCER) | Workflow-driven processing |
| **Pure Transformation** | COMPUTE only | Stateless data processing |

---

## Disambiguation Guide

**Event Variations**: `ModelEventEnvelope` (inter-service transport wrapper) vs. an FSM
event/trigger (a plain string for Reducer state transitions) vs. a domain event
(application-specific payload inside the envelope).

**Command vs Action**: "Action" is canonical (`ModelAction`); "Command" is informal prose
describing what an Action represents. Always use "Action" in code and formal documentation.

**Handler Variations** (corrected — see the HANDLER section above):

| Type | Interface | Purpose |
|------|-----------|---------|
| **Protocol Handler** | `ProtocolMessageHandler` | I/O execution (HTTP, DB, Kafka) |
| **Event Handler** | `MixinEventHandler` | Pub/sub event processing |
| **CLI Handler** | `MixinCLIHandler` | Command-line processing |

**Runtime Variations**: `NodeRuntime` (Core — pure, no event loop, for logic testing and
deterministic execution) vs. `RuntimeHostProcess` (Infrastructure — event loop, lifecycle
management, production deployment).

---

## Common Pitfalls

**Terminology**: using "Command" as a formal term (use "Action"); confusing
`ModelEventEnvelope` with FSM events (the envelope is transport, FSM events are state
triggers); calling Reducers directly for I/O (Reducers emit Intents, Effects execute I/O);
using `ModelContainer` for DI (use `ModelONEXContainer` — different types).

**Implementation**: skipping `super().__init__(container)` in node constructors; sharing node
instances across threads (create thread-local or separate instances); `isinstance` checks
against protocols instead of relying on structural/duck typing.

---

## Related Documentation

Cross-references in the original document point to omnibase_core-internal paths
(`docs/architecture/ONEX_FOUR_NODE_ARCHITECTURE.md`, `docs/architecture/MODEL_INTENT_ARCHITECTURE.md`,
`docs/architecture/MODEL_ACTION_ARCHITECTURE.md`, `docs/guides/node-building/README.md`,
`docs/patterns/PURE_FSM_REDUCER_PATTERN.md`, `docs/patterns/LEASE_MANAGEMENT_PATTERN.md`,
`docs/guides/THREADING.md`) that were not individually migrated as part of this pass — they
remain in the omnibase_core repository. Consult that repository's `docs/INDEX.md` for current
locations.

---

**Original Document Version**: 1.0.0 (2025-12-19), ONEX Framework Team
**Migration**: 2026-08-25 — HANDLER and RUNTIME sections (and the corresponding Quick
Reference Table rows and Disambiguation Guide row) rewritten against live omnibase_core@dev
source; sections 1–6 and 8 verified accurate with no changes needed.
