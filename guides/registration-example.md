---
type: guide
status: current
date: "2026-07-21"
title: "2-Way Registration: A Complete ONEX Example"
topics: [omnibase-infra, registration, example]
refs: []
---


# 2-Way Registration: A Complete ONEX Example

This guide walks through the **2-way node registration flow** - a real-world example of ONEX contract-driven architecture. Understanding this flow demonstrates how all four node archetypes work together.

> **Note**: For authoritative coding rules and standards, see CLAUDE.md. This guide provides detailed explanations and examples that supplement those rules.

## What is 2-Way Registration?

When an ONEX node starts up, it must:

1. **Register** with the ONEX infrastructure (tell the system "I exist")
2. **Acknowledge** the registration (confirm "I'm ready to work")

This two-phase handshake ensures nodes are properly tracked and healthy before receiving work.

The "2-way" refers to **dual-backend registration** - nodes register simultaneously with:
- **Consul** - For service discovery (other nodes can find me)
- **PostgreSQL** - For persistence (my registration survives restarts)

## Architecture Overview

### ASCII Diagram

The following diagram shows the complete 2-way registration flow through all four phases:

**Diagram Description**: This ASCII diagram illustrates the complete 2-way registration flow across four phases. Phase 1 (Node Introspection): An ONEX node starting up publishes to the node-introspection Kafka topic, the Registration Orchestrator receives it, routes to HandlerNodeIntrospected, which emits a NodeRegistrationInitiated event. Phase 2 (Reducer Processing): The Registration Reducer receives the event, transitions from idle to pending state, and emits intents for consul.register and postgres.upsert_registration. Phase 3 (Effect Execution): Consul and Postgres Effects execute in parallel, calling external services. Phase 4 (ACK Flow): The running node sends an ack command to the orchestrator, which publishes a NodeBecameActive event.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      2-WAY REGISTRATION FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: NODE INTROSPECTION                                                 │
│  ───────────────────────────                                                 │
│                                                                              │
│  ┌──────────────┐    publishes    ┌─────────────────────┐                   │
│  │  ONEX Node   │ ──────────────► │  Kafka Topic        │                   │
│  │  (starting)  │                 │  node-introspection │                   │
│  └──────────────┘                 └─────────────────────┘                   │
│                                            │                                 │
│                                            ▼                                 │
│                                   ┌─────────────────────┐                   │
│                                   │ Registration        │                   │
│                                   │ ORCHESTRATOR        │                   │
│                                   └─────────────────────┘                   │
│                                            │                                 │
│                                            │ routes to handler              │
│                                            ▼                                 │
│                                   ┌─────────────────────┐                   │
│                                   │ HandlerNode-        │                   │
│                                   │ Introspected        │                   │
│                                   └─────────────────────┘                   │
│                                            │                                 │
│                                            │ emits                           │
│                                            ▼                                 │
│                                   ┌─────────────────────┐                   │
│                                   │ NodeRegistration-   │                   │
│                                   │ Initiated (event)   │                   │
│                                   └─────────────────────┘                   │
│                                                                              │
│  PHASE 2: REDUCER PROCESSING                                                 │
│  ──────────────────────────────                                              │
│                                                                              │
│  ┌─────────────────────┐                                                    │
│  │ Registration        │  reduce(state, event) → (new_state, intents)       │
│  │ REDUCER (FSM)       │                                                    │
│  └─────────────────────┘                                                    │
│          │                                                                   │
│          │ state: idle → pending                                            │
│          │ emits intents                                                    │
│          ▼                                                                   │
│  ┌───────────────────────────────────────────────────────┐                  │
│  │ Intents:                                              │                  │
│  │  • consul.register → Consul Effect                    │                  │
│  │  • postgres.upsert_registration → Postgres Effect     │                  │
│  └───────────────────────────────────────────────────────┘                  │
│                                                                              │
│  PHASE 3: EFFECT EXECUTION (PARALLEL)                                        │
│  ────────────────────────────────────                                        │
│                                                                              │
│  ┌─────────────────────┐         ┌─────────────────────┐                   │
│  │ Consul EFFECT       │         │ Postgres EFFECT     │                   │
│  │                     │         │                     │                   │
│  │ consul.register()   │         │ upsert_record()     │                   │
│  └─────────────────────┘         └─────────────────────┘                   │
│          │                               │                                   │
│          ▼                               ▼                                   │
│  ┌─────────────────────┐         ┌─────────────────────┐                   │
│  │ Consul Service      │         │ PostgreSQL          │                   │
│  │ (external)          │         │ (external)          │                   │
│  └─────────────────────┘         └─────────────────────┘                   │
│                                                                              │
│  PHASE 4: ACK FLOW (2-WAY HANDSHAKE)                                         │
│  ───────────────────────────────────                                         │
│                                                                              │
│  ┌──────────────┐    ack command   ┌─────────────────────┐                  │
│  │  ONEX Node   │ ───────────────► │ Registration        │                  │
│  │  (running)   │                  │ ORCHESTRATOR        │                  │
│  └──────────────┘                  └─────────────────────┘                  │
│                                            │                                 │
│                                            ▼                                 │
│                                   ┌─────────────────────┐                   │
│                                   │ NodeBecameActive    │                   │
│                                   │ (event published)   │                   │
│                                   └─────────────────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Mermaid Diagram

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e1f5fe'}}}%%
flowchart TB
    accTitle: 2-Way Registration Flow
    accDescr: Complete flow diagram showing all four phases of ONEX node registration: Phase 1 Node Introspection where an ONEX node publishes to Kafka and the orchestrator routes to a handler; Phase 2 Reducer Processing where the FSM transitions state and emits intents; Phase 3 Effect Execution where Consul and PostgreSQL effects run in parallel; and Phase 4 Ack Flow where the node sends acknowledgment and becomes active.

    subgraph Phase1["Phase 1: Node Introspection"]
        N1[ONEX Node<br/>starting] -->|publishes| K1[Kafka Topic<br/>node-introspection]
        K1 --> O1[Registration<br/>ORCHESTRATOR]
        O1 -->|routes to| H1[HandlerNode-<br/>Introspected]
        H1 -->|emits| E1[NodeRegistration-<br/>Initiated event]
    end

    subgraph Phase2["Phase 2: Reducer Processing"]
        E1 --> R1[Registration<br/>REDUCER FSM]
        R1 -->|"state: idle → pending"| I1["Intents:<br/>• consul.register<br/>• postgres.upsert"]
    end

    subgraph Phase3["Phase 3: Effect Execution (Parallel)"]
        I1 --> CE[Consul EFFECT<br/>consul.register]
        I1 --> PE[Postgres EFFECT<br/>upsert_record]
        CE --> CS[(Consul Service)]
        PE --> PG[(PostgreSQL)]
        CS --> CF[Consul Confirmed]
        PG --> PC[Postgres Confirmed]
    end

    subgraph Phase4["Phase 4: Ack Flow"]
        CF --> R2[Reducer:<br/>partial → complete]
        PC --> R2
        R2 --> AE[Accepted Event<br/>published]
        AE --> N2[ONEX Node<br/>running]
        N2 -->|ack command| O2[Registration<br/>ORCHESTRATOR]
        O2 --> BA[NodeBecameActive<br/>event published]
    end
```

## Key Files

| Layer | File | Purpose |
|-------|------|---------|
| **Orchestrator** | `nodes/node_registration_orchestrator/contract.yaml` | Workflow definition, handler routing |
| **Orchestrator** | `nodes/node_registration_orchestrator/node.py` | Declarative orchestrator class |
| **Orchestrator** | `nodes/node_registration_orchestrator/handlers/handler_node_introspected.py` | Processes introspection events |
| **Reducer** | `nodes/node_registration_reducer/contract.yaml` | FSM state machine definition |
| **Reducer** | `nodes/node_registration_reducer/node.py` | Declarative reducer class |
| **Reducer** | `nodes/reducers/registration_reducer.py` | Pure reduce function |
| **Reducer** | `nodes/reducers/models/model_registration_state.py` | Immutable state model |
| **Effect** | `nodes/node_registry_effect/contract.yaml` | Dual-backend handler routing |
| **Effect** | `nodes/node_registry_effect/handlers/handler_consul_register.py` | Consul registration |
| **Effect** | `nodes/node_registry_effect/handlers/handler_postgres_upsert.py` | PostgreSQL persistence |

## Phase 1: Node Introspection

### What Happens

When any ONEX node starts up, it publishes an introspection event to Kafka:

```python
# Somewhere in node startup
event = ModelNodeIntrospectionEvent(
    node_id="abc-123",
    node_type=EnumNodeKind.EFFECT,
    capabilities=["registration.storage"],
    health_endpoint="/health",
    endpoints=["http://localhost:8080"],
)
# Publish to: dev.onex.evt.node-introspection.v1
```

### Orchestrator Receives Event

The Registration Orchestrator subscribes to introspection events:

```yaml
# contract.yaml (orchestrator)
# Topics use realm-agnostic 5-segment ONEX format: onex.<kind>.<producer>.<event-name>.v<version>
consumed_events:
  - topic: "onex.evt.platform.node-introspection.v1"
    event_type: "NodeIntrospectionEvent"
```

### Handler Routing

The orchestrator routes the event to a handler based on payload type:

```yaml
# contract.yaml (orchestrator)
handler_routing:
  routing_strategy: "payload_type_match"
  handlers:
    - event_model:
        name: "ModelNodeIntrospectionEvent"
      handler:
        name: "HandlerNodeIntrospected"
      state_decision_matrix:
        - current_state: null
          action: "emit_registration_initiated"
        - current_state: "ACTIVE"
          action: "no_op"
```

### Handler Logic

The handler (`handler_node_introspected.py`) makes decisions based on current state:

```python
async def handle(
    self,
    envelope: ModelEventEnvelope[ModelNodeIntrospectionEvent],
) -> ModelHandlerOutput[object]:
    event = envelope.payload
    correlation_id = envelope.correlation_id or uuid4()

    # Query current projection state
    projection = await self._projection_reader.get_entity_state(
        entity_id=event.node_id,
        domain="registration",
    )

    # Decision based on state
    if projection is None or projection.current_state in _RETRIABLE_STATES:
        # New or expired node - initiate registration
        initiated_event = ModelNodeRegistrationInitiated(
            entity_id=event.node_id,
            correlation_id=correlation_id,
        )
        return ModelHandlerOutput(events=(initiated_event,))

    # Already active - no-op
    return ModelHandlerOutput(events=())
```

**Key Point**: The handler returns events in `ModelHandlerOutput`. The **orchestrator** publishes them - handlers never publish directly.

## Phase 2: Reducer Processing

### FSM State Machine

The reducer's FSM is defined entirely in contract.yaml:

```yaml
# contract.yaml (reducer)
state_machine:
  state_machine_name: "registration_fsm"
  initial_state: "idle"

  states:
    - state_name: "idle"
    - state_name: "pending"
      entry_actions:
        - "emit_consul_intent"
        - "emit_postgres_intent"
    - state_name: "partial"
    - state_name: "complete"
    - state_name: "failed"

  transitions:
    - from_state: "idle"
      to_state: "pending"
      trigger: "introspection_received"
      conditions:
        - expression: "node_id is_present"
```

### Pure Reduce Function

The reducer implementation is a pure function with no side effects:

```python
# registration_reducer.py
def reduce(
    self,
    state: ModelRegistrationState,
    event: ModelNodeIntrospectionEvent,
) -> ModelReducerOutput[ModelRegistrationState]:
    # Idempotency check
    event_id = event.correlation_id or self._derive_event_id(event)
    if state.is_duplicate_event(event_id):
        return self._build_output(state=state, intents=())

    # Build intents for Effect layer
    consul_intent = self._build_consul_intent(event, event_id)
    postgres_intent = self._build_postgres_intent(event, event_id)

    # State transition: idle → pending
    new_state = state.with_pending_registration(event.node_id, event_id)

    return self._build_output(
        state=new_state,
        intents=(consul_intent, postgres_intent),
    )
```

### Immutable State

State models use `frozen=True` and `with_*` methods:

```python
# model_registration_state.py
class ModelRegistrationState(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str = "idle"
    consul_confirmed: bool = False
    postgres_confirmed: bool = False

    def with_pending_registration(self, node_id: str, event_id: UUID):
        """Return NEW instance in pending state."""
        return ModelRegistrationState(
            status="pending",
            node_id=node_id,
            last_processed_event_id=event_id,
        )
```

### Intent Emission

The reducer emits **intents** - requests for the Effect layer to execute:

```python
# Building a Consul intent
consul_intent = ModelIntent(
    intent_type="extension",
    target="consul://service/onex-effect-abc123",
    payload=ModelPayloadConsulRegister(
        intent_type="consul.register",  # Routing key in payload
        correlation_id=correlation_id,
        service_id="onex-effect-abc123",
        service_name="onex-effect",
        tags=["node_type:effect"],
    ),
)
```

**Two-Layer Intent Structure**:
- Outer `ModelIntent.intent_type = "extension"` (standard envelope)
- Inner `payload.intent_type = "consul.register"` (routing key)

## Phase 3: Effect Execution

Phase 3 is where the actual work happens - EFFECT nodes interact with external systems to persist the registration. This phase demonstrates ONEX's parallel execution capabilities and resilience patterns.

### What Happens During Effect Execution

1. **Intent Routing**: The orchestrator receives intents from the reducer and routes them to appropriate effect nodes
2. **Parallel Dispatch**: Both Consul and PostgreSQL effects execute simultaneously (not sequentially)
3. **External I/O**: Each effect handler performs actual I/O operations against external services
4. **Confirmation Events**: Each handler returns confirmation events upon success
5. **Error Handling**: Failures trigger retry logic, circuit breakers, and potentially DLQ routing

### ASCII Diagram: Effect Execution Detail

**Diagram Description**: This ASCII diagram provides a detailed view of Phase 3 Effect Execution. The Orchestrator receives intents from the reducer and dispatches them in parallel to Consul Effect and Postgres Effect handlers. Each handler checks its circuit breaker state, executes with retry logic, and tracks correlation IDs. The Consul handler calls the Consul API (PUT /v1/agent/service/register), while the Postgres handler performs an INSERT with ON CONFLICT UPDATE. Upon success, each returns confirmation events. The Orchestrator aggregates results: both succeeded means publish acceptance event; one failed means partial state with retry or compensate; both failed means failure state with DLQ routing.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 3: EFFECT EXECUTION (DETAILED)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ORCHESTRATOR receives intents from reducer:                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ intents = (consul_intent, postgres_intent)                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                              │ parallel dispatch                             │
│           ┌──────────────────┴──────────────────┐                           │
│           ▼                                      ▼                           │
│  ┌──────────────────────┐            ┌──────────────────────┐               │
│  │   CONSUL EFFECT      │            │  POSTGRES EFFECT     │               │
│  │   (node_registry_    │            │  (node_registry_     │               │
│  │    effect)           │            │   effect)            │               │
│  └──────────────────────┘            └──────────────────────┘               │
│           │                                      │                           │
│           │ intent_type=                         │ intent_type=              │
│           │ "consul.register"                    │ "postgres.upsert"         │
│           ▼                                      ▼                           │
│  ┌──────────────────────┐            ┌──────────────────────┐               │
│  │ HandlerConsulRegister│            │ HandlerPostgresUpsert│               │
│  │                      │            │                      │               │
│  │ • Check circuit      │            │ • Check circuit      │               │
│  │   breaker state      │            │   breaker state      │               │
│  │ • Execute with       │            │ • Execute with       │               │
│  │   retry logic        │            │   retry logic        │               │
│  │ • Track correlation  │            │ • Track correlation  │               │
│  └──────────────────────┘            └──────────────────────┘               │
│           │                                      │                           │
│           │                                      │                           │
│           ▼                                      ▼                           │
│  ┌──────────────────────┐            ┌──────────────────────┐               │
│  │    CONSUL API        │            │    POSTGRESQL        │               │
│  │    (external)        │            │    (external)        │               │
│  │                      │            │                      │               │
│  │ PUT /v1/agent/       │            │ INSERT INTO          │               │
│  │   service/register   │            │   node_registrations │               │
│  └──────────────────────┘            └──────────────────────┘               │
│           │                                      │                           │
│           │ success                              │ success                   │
│           ▼                                      ▼                           │
│  ┌──────────────────────┐            ┌──────────────────────┐               │
│  │ ModelConsulRegistra- │            │ ModelPostgresRegis-  │               │
│  │ tionConfirmed        │            │ trationConfirmed     │               │
│  │ (event)              │            │ (event)              │               │
│  └──────────────────────┘            └──────────────────────┘               │
│           │                                      │                           │
│           └──────────────────┬───────────────────┘                           │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ORCHESTRATOR aggregates results:                                     │    │
│  │ • Both succeeded → publish acceptance event                          │    │
│  │ • One failed → partial state (retry or compensate)                   │    │
│  │ • Both failed → failure state (DLQ routing)                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Mermaid Diagram: Effect Execution

```mermaid
flowchart TB
    accTitle: Phase 3 Effect Execution Detail
    accDescr: Detailed flow of Phase 3 Effect Execution showing how the orchestrator dispatches intents to Consul and PostgreSQL effect handlers in parallel, each handler checks circuit breaker state, executes with retry logic, performs external I/O operations, and returns confirmation events that are aggregated by the orchestrator.

    ORCH[Orchestrator receives intents] --> |parallel dispatch| SPLIT{Parallel Execution}

    SPLIT --> CONSUL_EFFECT[Consul Effect Handler]
    SPLIT --> PG_EFFECT[Postgres Effect Handler]

    subgraph ConsulPath["Consul Registration Path"]
        CONSUL_EFFECT --> CB1{Circuit Breaker<br/>Open?}
        CB1 -->|No| RETRY1[Execute with Retry]
        CB1 -->|Yes| FAIL1[Fast Fail]
        RETRY1 --> CONSUL_API[(Consul API<br/>PUT /v1/agent/service/register)]
        CONSUL_API --> CONSUL_OK[ConsulRegistrationConfirmed]
    end

    subgraph PGPath["PostgreSQL Persistence Path"]
        PG_EFFECT --> CB2{Circuit Breaker<br/>Open?}
        CB2 -->|No| RETRY2[Execute with Retry]
        CB2 -->|Yes| FAIL2[Fast Fail]
        RETRY2 --> PG_DB[(PostgreSQL<br/>INSERT/ON CONFLICT UPDATE)]
        PG_DB --> PG_OK[PostgresRegistrationConfirmed]
    end

    CONSUL_OK --> AGG[Orchestrator Aggregates Results]
    PG_OK --> AGG
    FAIL1 --> ERR[Error Handling]
    FAIL2 --> ERR

    AGG --> |Both succeeded| ACCEPT[Publish Acceptance Event]
    AGG --> |Partial failure| PARTIAL[Partial State - Retry/Compensate]
    ERR --> |Circuit open| DLQ[DLQ Routing]
```

### Parallel Execution Configuration

The orchestrator routes intents to effects in parallel:

```yaml
# contract.yaml (effect node)
handler_routing:
  execution_mode: "parallel"
  partial_failure_handling: true
  handlers:
    - operation: "register_node"
      handler: { name: "HandlerConsulRegister" }
      backend: "consul"
    - operation: "register_node"
      handler: { name: "HandlerPostgresUpsert" }
      backend: "postgres"
```

### Consul Effect Handler

The Consul handler registers the node as a service with service discovery:

```python
# handler_consul_register.py
async def handle(self, intent: ModelIntent) -> ModelHandlerOutput:
    payload = intent.payload  # ModelPayloadConsulRegister

    # Execute Consul registration
    await self._consul_client.register_service(
        service_id=payload.service_id,
        service_name=payload.service_name,
        tags=payload.tags,
    )

    return ModelHandlerOutput(
        events=(
            ModelConsulRegistrationConfirmed(
                service_id=payload.service_id,
                correlation_id=payload.correlation_id,
            ),
        ),
    )
```

### PostgreSQL Effect Handler

The PostgreSQL handler persists the registration record with upsert semantics:

```python
# handler_postgres_upsert.py
async def handle(self, intent: ModelIntent) -> ModelHandlerOutput:
    payload = intent.payload  # ModelPayloadPostgresUpsertRegistration

    # Execute PostgreSQL upsert
    await self._db.execute(
        """
        INSERT INTO node_registrations (node_id, node_type, endpoints)
        VALUES ($1, $2, $3)
        ON CONFLICT (node_id) DO UPDATE SET
            node_type = EXCLUDED.node_type,
            endpoints = EXCLUDED.endpoints,
            updated_at = NOW()
        """,
        payload.node_id,
        payload.node_type,
        payload.endpoints,
    )

    return ModelHandlerOutput(
        events=(
            ModelPostgresRegistrationConfirmed(
                node_id=payload.node_id,
                correlation_id=payload.correlation_id,
            ),
        ),
    )
```

### Resilience Patterns in Effect Execution

Effect handlers implement several resilience patterns:

| Pattern | Purpose | Implementation |
|---------|---------|----------------|
| **Circuit Breaker** | Prevent cascading failures when external service is down | `MixinAsyncCircuitBreaker` with configurable threshold |
| **Retry with Backoff** | Handle transient failures | Exponential backoff (2^n seconds) with max 3 retries |
| **Correlation Tracking** | Trace requests across services | `correlation_id` propagated through all operations |
| **Partial Failure Handling** | Continue when one backend fails | Aggregate results, track partial state |
| **DLQ Routing** | Handle persistent failures | Route failed intents to dead letter queue |

### Error Scenarios

| Scenario | Consul | PostgreSQL | Result State | Next Action |
|----------|--------|------------|--------------|-------------|
| Both succeed | OK | OK | `complete` | Publish acceptance event |
| Consul fails | FAIL | OK | `partial` | Retry Consul or compensate |
| PostgreSQL fails | OK | FAIL | `partial` | Retry PostgreSQL or compensate |
| Both fail | FAIL | FAIL | `failed` | Route to DLQ, alert operators |
| Circuit open | SKIP | SKIP | `pending` | Wait for circuit reset |

### Capability Naming in Effect Nodes

Effect nodes are named by **capability** (what they do), not by **technology** (how they do it). This enables backend swaps without contract changes.

**Good Capability Names** (used in this example):

| Capability | Purpose | Why Good |
|------------|---------|----------|
| `consul.register` | Register service for discovery | Domain-scoped action |
| `postgres.upsert_registration` | Persist registration record | Action-oriented with context |
| `registration.storage` | Storage operations for registrations | Hierarchical, technology-agnostic |

**Bad Capability Names** (avoid these):

| Bad Name | Problem | Better Alternative |
|----------|---------|-------------------|
| `doStuff` | Meaningless, non-descriptive | `node.registration.create` |
| `handler1` | Numbered handlers indicate poor design | `node.introspection.query` |
| `process` | Too generic, no domain context | `registration.storage.upsert` |
| `run` | Ambiguous without operation type | `workflow.state.checkpoint` |

**Pattern**: `{domain}.{subdomain}.{action}` - e.g., `service.discovery.register`

For the complete capability naming convention, see Contract.yaml Reference - Capability Naming.

## Phase 4: ACK Flow

Phase 4 completes the 2-way handshake. The registering node acknowledges that it received the acceptance, confirming it's ready to receive work. This phase also establishes liveness tracking to ensure nodes remain healthy.

### What Happens During ACK Flow

1. **Acceptance Event Received**: The registering node receives the acceptance event from Phase 3
2. **ACK Command Sent**: The node sends an acknowledgment command back to the orchestrator
3. **State Verification**: The handler verifies the node is in a valid state for ACK
4. **Liveness Deadline Calculation**: A deadline is set for the node's first heartbeat
5. **Activation Events Published**: The orchestrator publishes `NodeBecameActive` event
6. **Node is ACTIVE**: The node can now receive and process work

### ASCII Diagram: ACK Flow Detail

**Diagram Description**: This ASCII diagram provides a detailed view of Phase 4 ACK Flow. Step 1: The ONEX node receives the acceptance event from Kafka. Step 2: The node sends an ACK command to the node-registration-acked topic. Step 3: The Registration Orchestrator consumes the ACK and routes to HandlerNodeRegistrationAcked. Step 4: The handler queries the projection to verify the current_state is ACCEPTED or AWAITING_ACK. Step 5: The handler calculates the liveness_deadline (envelope_timestamp + 30 seconds). Step 6: The Orchestrator publishes ModelNodeRegistrationAckReceived and ModelNodeBecameActive events. Step 7: The node is now ACTIVE, can receive work, must send heartbeats, is visible in Consul, and persisted in PostgreSQL.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PHASE 4: ACK FLOW (DETAILED)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 1: Node receives acceptance event                                      │
│  ┌──────────────────────┐         ┌─────────────────────────────────┐       │
│  │   ONEX Node          │ ◄────── │ Kafka: node-registration-       │       │
│  │   (awaiting ack)     │         │        accepted.v1              │       │
│  └──────────────────────┘         └─────────────────────────────────┘       │
│                                                                              │
│  STEP 2: Node sends ACK command                                              │
│  ┌──────────────────────┐         ┌─────────────────────────────────┐       │
│  │   ONEX Node          │ ──────► │ Kafka: node-registration-       │       │
│  │   (sending ack)      │         │        acked.v1                 │       │
│  └──────────────────────┘         └─────────────────────────────────┘       │
│           │                                       │                          │
│           │                                       ▼                          │
│           │                        ┌─────────────────────────────────┐       │
│           │                        │ Registration ORCHESTRATOR       │       │
│           │                        │ • Consumes ACK command          │       │
│           │                        │ • Routes to handler             │       │
│           │                        └─────────────────────────────────┘       │
│           │                                       │                          │
│           │                                       ▼                          │
│  STEP 3: State verification                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  HandlerNodeRegistrationAcked                                        │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │ Query projection: entity_id=node_id                          │    │    │
│  │  │   ┌───────────────────────────────────────────┐              │    │    │
│  │  │   │ current_state in ("ACCEPTED", "AWAITING_ACK")?           │    │    │
│  │  │   │   YES → Continue to Step 4                               │    │    │
│  │  │   │   NO  → Return empty (no-op)                             │    │    │
│  │  │   └───────────────────────────────────────────┘              │    │    │
│  │  └─────────────────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                       │                                      │
│                                       ▼                                      │
│  STEP 4: Calculate liveness deadline                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  liveness_deadline = envelope_timestamp + LIVENESS_WINDOW (30s)      │    │
│  │  • Node must send heartbeat before deadline                          │    │
│  │  • Missed deadline → LIVENESS_EXPIRED state                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                       │                                      │
│                                       ▼                                      │
│  STEP 5: Publish activation events                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  ORCHESTRATOR publishes:                                             │    │
│  │  ┌─────────────────────────┐  ┌────────────────────────────┐        │    │
│  │  │ ModelNodeRegistration-  │  │ ModelNodeBecameActive      │        │    │
│  │  │ AckReceived             │  │ • node_id                  │        │    │
│  │  │ • Confirms ACK received │  │ • liveness_deadline        │        │    │
│  │  └─────────────────────────┘  │ • activated_at             │        │    │
│  │                               └────────────────────────────┘        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                       │                                      │
│                                       ▼                                      │
│  STEP 6: Node is ACTIVE                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  ┌───────────────────────────────────────────────────────────┐      │    │
│  │  │   ONEX Node (ACTIVE)                                      │      │    │
│  │  │   • Can receive work                                      │      │    │
│  │  │   • Must send heartbeats every HEARTBEAT_INTERVAL         │      │    │
│  │  │   • Visible in service discovery (Consul)                 │      │    │
│  │  │   • Persisted in database (PostgreSQL)                    │      │    │
│  │  └───────────────────────────────────────────────────────────┘      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Mermaid Diagram: ACK Flow

```mermaid
flowchart TB
    accTitle: Phase 4 ACK Flow Detail
    accDescr: Detailed flow of Phase 4 ACK Flow showing how the registering node receives the acceptance event, sends an acknowledgment command, the handler verifies state via projection query, calculates a liveness deadline, and the orchestrator publishes activation events resulting in the node becoming active and ready to receive work.

    subgraph Step1["Step 1: Receive Acceptance"]
        K1[Kafka: node-registration-accepted.v1] --> N1[ONEX Node<br/>awaiting ack]
    end

    subgraph Step2["Step 2: Send ACK"]
        N1 --> |sends| ACK[ACK Command]
        ACK --> K2[Kafka: node-registration-acked.v1]
    end

    subgraph Step3["Step 3: Orchestrator Processing"]
        K2 --> ORCH[Registration Orchestrator]
        ORCH --> H1[HandlerNodeRegistrationAcked]
    end

    subgraph Step4["Step 4: State Verification"]
        H1 --> Q1{Query Projection:<br/>current_state?}
        Q1 -->|ACCEPTED or<br/>AWAITING_ACK| VALID[Valid State]
        Q1 -->|Other| NOOP[No-op Return]
    end

    subgraph Step5["Step 5: Liveness Calculation"]
        VALID --> CALC["Calculate liveness_deadline<br/>= timestamp + 30s"]
    end

    subgraph Step6["Step 6: Publish Events"]
        CALC --> PUB[Orchestrator publishes:]
        PUB --> E1[NodeRegistrationAckReceived]
        PUB --> E2[NodeBecameActive<br/>+ liveness_deadline]
    end

    subgraph Step7["Step 7: Node Active"]
        E2 --> ACTIVE[Node is ACTIVE<br/>Ready for work]
        ACTIVE --> HB[Must send heartbeats<br/>before deadline]
    end
```

### Node Sends Acknowledgment

Once the node receives its registration acceptance, it sends an ACK command:

```python
# Node sends ACK
ack_command = ModelNodeRegistrationAcked(
    node_id="abc-123",
    correlation_id=original_correlation_id,
)
# Publish to: dev.onex.cmd.node-registration-acked.v1
```

### Handler Processes ACK

```yaml
# contract.yaml (orchestrator)
handler_routing:
  handlers:
    - event_model: { name: "ModelNodeRegistrationAcked" }
      handler: { name: "HandlerNodeRegistrationAcked" }
      output_events:
        - "ModelNodeRegistrationAckReceived"
        - "ModelNodeBecameActive"
```

The handler verifies state and emits activation events:

```python
# handler_node_registration_acked.py
async def handle(self, envelope: ModelEventEnvelope) -> ModelHandlerOutput:
    # Verify current state allows ACK
    projection = await self._projection_reader.get_entity_state(
        entity_id=envelope.payload.node_id,
    )

    if projection.current_state not in ("ACCEPTED", "AWAITING_ACK"):
        return ModelHandlerOutput(events=())  # Invalid state - no-op

    # Calculate liveness deadline
    liveness_deadline = envelope.envelope_timestamp + timedelta(seconds=30)

    # Return activation events
    return ModelHandlerOutput(
        events=(
            ModelNodeRegistrationAckReceived(...),
            ModelNodeBecameActive(
                node_id=envelope.payload.node_id,
                liveness_deadline=liveness_deadline,
            ),
        ),
    )
```

### ACK Timeout Handling

If the node fails to send an ACK within the expected window, the system handles it gracefully:

| Scenario | Timeout | Next Action |
|----------|---------|-------------|
| ACK received on time | N/A | Node becomes ACTIVE |
| ACK not received within 30s | ACK_TIMED_OUT | Retry ACK request or re-register |
| Multiple ACK timeouts | After 3 retries | Mark as FAILED, alert operators |

### Liveness Tracking After ACK

Once a node is ACTIVE, it must maintain liveness through heartbeats:

**Diagram Description**: This ASCII diagram shows the liveness tracking timeline after ACK. Starting at T+0 (ACK received), the node must send heartbeats (HB) within the 30-second liveness window. The timeline shows heartbeats expected at T+10s, T+20s, T+30s, and T+40s intervals. The liveness_deadline is at T+30s from the ACK. If no heartbeat is received by T+30s, the node transitions to LIVENESS_EXPIRED terminal state.

```
┌─────────────────────────────────────────────────────────────────┐
│                    LIVENESS TRACKING                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Timeline (starting from ACK):                                   │
│                                                                  │
│  T+0s         T+10s        T+20s        T+30s        T+40s      │
│    │            │            │            │            │         │
│    ▼            ▼            ▼            ▼            ▼         │
│  ┌───┐       ┌───┐       ┌───┐       ┌───┐       ┌───┐         │
│  │ACK│       │ HB│       │ HB│       │ HB│       │ HB│         │
│  └───┘       └───┘       └───┘       └───┘       └───┘         │
│    │                                   │                         │
│    │                                   │ liveness_deadline       │
│    │                                   │                         │
│    │◄──────────────────────────────────┤                         │
│            30 second window                                      │
│                                                                  │
│  If no heartbeat by T+30s → LIVENESS_EXPIRED (terminal state)    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Error Handling in ACK Flow

| Error Condition | Handler Response | System Recovery |
|-----------------|------------------|-----------------|
| Invalid state for ACK | Return empty `ModelHandlerOutput` | No state change, log warning |
| Projection query fails | Raise error, retry | Automatic retry with backoff |
| ACK duplicate | Idempotent no-op | Return existing active state |
| ACK after liveness expired | Reject ACK | Node must re-register |

## FSM State Diagram

The registration flow involves two cooperating finite state machines:

### Registration FSM (Reducer)

Manages the backend registration state tracking whether Consul and PostgreSQL have confirmed.

#### ASCII Version

**Diagram Description**: This ASCII diagram shows the Registration Reducer FSM state machine. States include IDLE (waiting for introspection), PENDING (awaiting backend confirmations), PARTIAL (one backend confirmed), COMPLETE (both backends confirmed), and FAILED (error occurred, retriable). Transitions: IDLE to PENDING on introspection_received, PENDING to PARTIAL on first backend confirmation, PARTIAL to COMPLETE on second backend confirmation. Any state can transition to FAILED on error. Both COMPLETE and FAILED can reset back to IDLE.

```
                    REGISTRATION FSM
═══════════════════════════════════════════════════════

                     RETRIABLE STATES
          ┌────────────────────────────────────┐
          │                                    │
          ▼                                    │
  ┌───────┐  introspection  ┌─────────┐       │
  │ IDLE  │ ──────────────► │ PENDING │       │
  └───────┘                 └─────────┘       │
      ▲                          │            │
      │                          │            │
      │                    first │            │
      │                 backend  │            │
      │                          ▼            │
      │                    ┌─────────┐        │
      │                    │ PARTIAL │        │
      │                    └─────────┘        │
      │                          │            │
      │                   second │            │
      │                 backend  │            │
      │                          ▼            │
      │    reset          ┌──────────┐        │
      └───────────────────│ COMPLETE │        │
      │                   └──────────┘        │
      │                                       │
      │                    ┌────────┐         │
      └────────────────────│ FAILED │─────────┘
                           └────────┘
                          error from *
```

#### Mermaid Version

```mermaid
stateDiagram-v2
    accTitle: Registration FSM State Diagram
    accDescr: State diagram for the Registration Reducer FSM showing transitions from IDLE to PENDING when introspection is received, then to PARTIAL when the first backend confirms, then to COMPLETE when the second backend confirms. FAILED state can be reached from any state on error, and both COMPLETE and FAILED can reset back to IDLE.

    [*] --> IDLE

    IDLE --> PENDING : introspection_received
    PENDING --> PARTIAL : first_backend_confirmed
    PARTIAL --> COMPLETE : second_backend_confirmed

    IDLE --> FAILED : error
    PENDING --> FAILED : error
    PARTIAL --> FAILED : error

    COMPLETE --> IDLE : reset_requested
    FAILED --> IDLE : reset_requested

    note right of IDLE : Waiting for introspection
    note right of PENDING : Awaiting backend confirmations
    note right of PARTIAL : One backend confirmed
    note right of COMPLETE : Both backends confirmed
    note right of FAILED : Error occurred, retriable
```

### Orchestrator FSM

Manages the overall registration workflow state including the ACK handshake.

#### ASCII Version

**Diagram Description**: This ASCII diagram shows the Orchestrator FSM state machine for the registration workflow. States include PENDING_REGISTRATION (awaiting backend results), ACCEPTED (ready for ACK handshake), REJECTED (terminal, registration denied), AWAITING_ACK (waiting for node acknowledgment), ACK_RECEIVED (acknowledgment confirmed), ACK_TIMED_OUT (timeout waiting for ACK), ACTIVE (node ready for work), and LIVENESS_EXPIRED (terminal, must re-register). Key transitions: PENDING_REGISTRATION to ACCEPTED or REJECTED, ACCEPTED to AWAITING_ACK, AWAITING_ACK to ACK_RECEIVED or ACK_TIMED_OUT, then to ACTIVE, and finally ACTIVE to LIVENESS_EXPIRED if heartbeats are missed.

```
                    ORCHESTRATOR FSM
═══════════════════════════════════════════════════════

  ┌──────────────┐  accepted  ┌──────────┐
  │ PENDING_     │ ─────────► │ ACCEPTED │
  │ REGISTRATION │            └──────────┘
  └──────────────┘                 │
         │                         │ ack sent
         │ rejected                ▼
         ▼                   ┌──────────────┐
    ┌──────────┐             │ AWAITING_ACK │
    │ REJECTED │             └──────────────┘
    │(terminal)│                   │
    └──────────┘         ack recv  │  timeout
                                   ▼      ▼
                            ┌────────────┐ ┌────────────┐
                            │ACK_RECEIVED│ │ACK_TIMED_  │
                            └────────────┘ │OUT         │
                                   │       └────────────┘
                             active│            │
                                   ▼            │ retry
                              ┌────────┐        │
                              │ ACTIVE │◄───────┘
                              └────────┘
                                   │
                          liveness │
                          expired  ▼
                            ┌─────────────┐
                            │ LIVENESS_   │
                            │ EXPIRED     │
                            │ (terminal)  │
                            └─────────────┘
```

#### Mermaid Version

```mermaid
stateDiagram-v2
    accTitle: Orchestrator FSM State Diagram
    accDescr: State diagram for the Registration Orchestrator FSM showing the workflow from PENDING_REGISTRATION through ACCEPTED and AWAITING_ACK states. On ACK received, node transitions to ACK_RECEIVED then ACTIVE. On timeout, transitions to ACK_TIMED_OUT which can retry to ACTIVE. ACTIVE nodes that miss liveness deadline transition to terminal LIVENESS_EXPIRED. REJECTED is also a terminal state for denied registrations.

    [*] --> PENDING_REGISTRATION

    PENDING_REGISTRATION --> ACCEPTED : registration_accepted
    PENDING_REGISTRATION --> REJECTED : registration_rejected

    ACCEPTED --> AWAITING_ACK : ack_sent

    AWAITING_ACK --> ACK_RECEIVED : ack_received
    AWAITING_ACK --> ACK_TIMED_OUT : timeout

    ACK_RECEIVED --> ACTIVE : activation_complete
    ACK_TIMED_OUT --> ACTIVE : retry_successful

    ACTIVE --> LIVENESS_EXPIRED : liveness_deadline_missed

    REJECTED --> [*]
    LIVENESS_EXPIRED --> [*]

    note right of PENDING_REGISTRATION : Awaiting backend results
    note right of ACCEPTED : Ready for ACK handshake
    note right of AWAITING_ACK : Waiting for node ACK
    note right of ACTIVE : Node ready for work
    note right of LIVENESS_EXPIRED : Terminal - must re-register
```

## Event Timeline

```
TIME    EVENT/ACTION                           KAFKA TOPIC
────────────────────────────────────────────────────────────────────
T+0     Node starts, publishes introspection   node-introspection.v1
T+1     Orchestrator receives event            (consumed)
T+2     Handler queries projection             (internal)
T+3     Handler returns initiated event        (internal)
T+4     Orchestrator publishes initiated       node-registration-initiated.v1
T+5     Reducer receives initiated event       (consumed)
T+6     Reducer transitions: idle → pending    (state change)
T+7     Reducer emits intents                  (internal)
T+8     Effect executes Consul registration    (external I/O) ─┐
T+8     Effect executes Postgres upsert        (external I/O) ─┴─ parallel
T+9     Effects return confirmation events     (internal)
T+10    Reducer receives confirmations         (consumed)
T+11    Reducer transitions: pending → complete (state change)
T+12    Orchestrator publishes accepted        node-registration-accepted.v1
T+13    Node receives accepted event           (consumed by node)
T+14    Node publishes ACK command             node-registration-acked.v1
T+15    Orchestrator receives ACK              (consumed)
T+16    Handler processes ACK                  (internal)
T+17    Orchestrator publishes active          node-became-active.v1
T+18    Node is now ACTIVE                     (ready for work)
```

## Key Design Patterns Demonstrated

### 1. Contract-Driven Architecture

All behavior is declared in YAML contracts:
- FSM transitions in reducer contract
- Handler routing in orchestrator contract
- Parallel execution in effect contract

### 2. Declarative Nodes

Node classes contain zero logic:
```python
class NodeRegistrationOrchestrator(NodeOrchestrator):
    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)  # That's it!
```

### 3. Pure Reducers

Reducers are pure functions with no side effects:
```python
reduce(state, event) → (new_state, intents)
```

### 4. Intent-Based Effects

Reducers don't call effects directly - they emit intents that the orchestrator routes:
```python
intents = (consul_intent, postgres_intent)  # Reducer returns
# Orchestrator routes to: node_registry_effect
```

### 5. Handler Isolation

Handlers cannot publish events - only return them:
```python
return ModelHandlerOutput(events=(event1, event2))
# Orchestrator does the actual publishing
```

### 6. Parallel Execution

Effects execute in parallel with partial failure handling:
```yaml
execution_mode: "parallel"
partial_failure_handling: true
```

### 7. Immutable State

State transitions create new instances:
```python
new_state = state.with_consul_confirmed(event_id)  # Returns NEW instance
```

### 8. Idempotency

Duplicate events are detected and skipped:
```python
if state.is_duplicate_event(event_id):
    return self._build_output(state=state, intents=())  # No-op
```

## Summary

The 2-way registration flow demonstrates ONEX's key principles:

| Principle | Implementation |
|-----------|----------------|
| Contract-driven | All routing, FSM, workflows in YAML |
| Declarative nodes | Node classes extend base, no custom logic |
| Separation of concerns | Each archetype has one job |
| Pure reducers | No side effects in state management |
| Intent-based I/O | Effects execute what reducers request |
| Parallel execution | Backends registered simultaneously |
| Handler isolation | No direct event bus access |

## Related Documentation

| Topic | Document |
|-------|----------|
| **Coding standards** | CLAUDE.md - **authoritative source** for all rules |
| Quick start | Quick Start Guide |
| Node archetypes | Node Archetypes Reference |
| Contract format | Contract.yaml Reference |
| Capability naming | Capability Naming Convention |
| Architecture | [Architecture Overview](../architecture/onex-runtime-overview.md) |
| All patterns | Pattern Documentation |
