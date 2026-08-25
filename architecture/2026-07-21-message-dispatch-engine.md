---
type: architecture
status: accepted
date: "2026-07-21"
title: "Message Dispatch Engine Architecture"
topics: [omnibase-infra, message, dispatch, engine]
refs: []
---


# Message Dispatch Engine Architecture

## Overview

The Message Dispatch Engine (`MessageDispatchEngine`) is a runtime routing engine for
message dispatching based on topic category and message type. It routes incoming messages
to registered dispatchers and collects dispatcher outputs for publishing.

**Implementation**: `src/omnibase_infra/runtime/message_dispatch_engine.py`

## Design Principles

| Principle | Description |
|-----------|-------------|
| **Pure Routing** | Routes messages to dispatchers, no workflow inference |
| **Deterministic** | Same input always produces same dispatcher selection |
| **Fan-out Support** | Multiple dispatchers can process the same message type |
| **Freeze-After-Init** | Thread-safe after registration phase completes |
| **Observable** | Structured logging and comprehensive metrics |

## Architecture Diagram

### ASCII Version

**Diagram Description**: This ASCII diagram shows the six-step processing pipeline within the Message Dispatch Engine. Step 1 (Parse Topic) extracts the topic string and determines the EnumMessageCategory. Step 2 (Validate) performs category matching on the envelope. Step 3 (Match Dispatchers) finds all dispatchers matching the category and returns a dispatchers array. Step 4 (Execute Dispatchers) runs all matched dispatchers and collects their outputs. Step 5 (Collect Outputs) aggregates all dispatcher outputs. Step 6 (Return Result) constructs and returns the ModelDispatchResult containing all outputs and any errors.

```
+------------------------------------------------------------------+
|                   Message Dispatch Engine                         |
+------------------------------------------------------------------+
|                                                                  |
|   1. Parse Topic       2. Validate          3. Match Dispatchers |
|        |                   |                       |             |
|        |  topic string     |  category match       |             |
|        |-------------------|----------------------|             |
|        |                   |                       |             |
|        | EnumMessageCategory                       | dispatchers[]|
|        |<------------------|                       |------------>|
|        |                   |                       |             |
|   4. Execute Dispatchers 5. Collect Outputs  6. Return Result    |
|        |                   |                       |             |
|        | dispatcher outputs|  aggregate           |             |
|        |-------------------|----------------------|             |
|        |                   |                       |             |
|        |                   |  ModelDispatchResult  |             |
|        |<------------------|<---------------------|             |
|                                                                  |
+------------------------------------------------------------------+
```

### Mermaid Version

```mermaid
flowchart LR
    accTitle: Message Dispatch Engine Processing Pipeline
    accDescr: Six-step processing pipeline showing how the Message Dispatch Engine routes messages. Parse Topic extracts the category from the topic string. Validate checks the envelope against the category. Match Dispatchers finds all matching dispatchers. Execute Dispatchers runs each dispatcher. Collect Outputs aggregates results. Return Result builds the final ModelDispatchResult.

    subgraph Engine["Message Dispatch Engine"]
        S1[1. Parse Topic<br/>topic string → EnumMessageCategory]
        S2[2. Validate<br/>category match]
        S3[3. Match Dispatchers<br/>→ dispatchers array]
        S4[4. Execute Dispatchers<br/>run all matched]
        S5[5. Collect Outputs<br/>aggregate results]
        S6[6. Return Result<br/>ModelDispatchResult]
    end

    S1 --> S2 --> S3 --> S4 --> S5 --> S6
```

## Dispatch Sequence Diagram

### ASCII Version

**Diagram Description**: This ASCII sequence diagram shows the interaction between three participants: User/Caller, MessageDispatchEngine, and Dispatcher(s). The User calls dispatch(topic, envelope) on the engine. The engine then performs five internal steps: (1) parse topic category, (2) validate envelope, (3) find matching dispatchers, (4) execute each dispatcher and receive DispatcherOutput (repeated for fan-out scenarios), and (5) aggregate all outputs. Finally, the engine returns the ModelDispatchResult to the caller.

```
User/Caller          MessageDispatchEngine         Dispatcher(s)
     |                        |                         |
     | dispatch(topic, env)   |                         |
     |----------------------->|                         |
     |                        |                         |
     |                        | 1. Parse topic category |
     |                        |------------------------>|
     |                        |                         |
     |                        | 2. Validate envelope    |
     |                        |------------------------>|
     |                        |                         |
     |                        | 3. Find matching        |
     |                        |    dispatchers          |
     |                        |------------------------>|
     |                        |                         |
     |                        | 4. Execute dispatcher   |
     |                        |------------------------>|
     |                        |                         |
     |                        |    DispatcherOutput     |
     |                        |<------------------------|
     |                        |                         |
     |                        | (repeat for fan-out)    |
     |                        |                         |
     |                        | 5. Aggregate outputs    |
     |                        |------------------------>|
     |                        |                         |
     | ModelDispatchResult    |                         |
     |<-----------------------|                         |
     |                        |                         |
```

### Mermaid Version

```mermaid
sequenceDiagram
    accTitle: Message Dispatch Engine Sequence
    accDescr: Sequence diagram showing the dispatch flow. User calls dispatch on the engine with topic and envelope. Engine parses the topic category, validates the envelope, finds matching dispatchers, executes each dispatcher receiving outputs (repeated for fan-out), aggregates all outputs, and returns a ModelDispatchResult to the caller.

    participant Caller as User/Caller
    participant Engine as MessageDispatchEngine
    participant Dispatcher as Dispatcher(s)

    Caller->>Engine: dispatch(topic, envelope)
    Engine->>Engine: 1. Parse topic category
    Engine->>Engine: 2. Validate envelope
    Engine->>Engine: 3. Find matching dispatchers
    loop For each matching dispatcher (fan-out)
        Engine->>Dispatcher: 4. Execute dispatcher
        Dispatcher-->>Engine: DispatcherOutput
    end
    Engine->>Engine: 5. Aggregate outputs
    Engine-->>Caller: ModelDispatchResult
```

## Registration Phase

### Route Registration

Routes define how messages are matched to dispatchers based on topic pattern,
message category, and optionally message type.

```python
engine.register_route(ModelDispatchRoute(
    route_id="order-events",
    topic_pattern="*.order.events.*",
    message_category=EnumMessageCategory.EVENT,
    dispatcher_id="order-dispatcher",
))
```

### Dispatcher Registration

Dispatchers process messages that match their category and (optionally) message type.

```python
async def process_user_event(envelope: ModelEventEnvelope[object]) -> str | None:
    user_data = envelope.payload
    # Process the event
    return "dev.user.processed.v1"  # Output topic

engine.register_dispatcher(
    dispatcher_id="user-event-dispatcher",
    dispatcher=process_user_event,
    category=EnumMessageCategory.EVENT,
    message_types={"UserCreated", "UserUpdated"},
)
```

#### Envelope Typing Pattern

Dispatchers use `ModelEventEnvelope[object]` instead of `Any` for envelope parameters:

- **`ModelEventEnvelope[object]`**: For generic dispatchers that accept any payload type.
  The dispatch engine routes based on topic/category/message_type, not payload shape.
- **`ModelEventEnvelope[SpecificType]`**: For concrete implementations that know the
  exact payload type (e.g., `ModelEventEnvelope[UserCreatedEvent]`).

Using `object` instead of `Any`:
- Satisfies ONEX "no Any types" coding guideline
- Explicitly states "any Python object" with clearer intent
- Same runtime behavior as `Any` but with documented semantics

See `CLAUDE.md` section "Envelope Typing" for the complete typing guidelines.

### Freeze Pattern

The engine follows a **freeze-after-init** pattern for thread safety:

1. **Registration Phase** (single-threaded): Register routes and dispatchers
2. **Freeze**: Call `freeze()` to prevent further modifications
3. **Dispatch Phase** (multi-threaded safe): Route messages to dispatchers

```python
engine = MessageDispatchEngine()
engine.register_dispatcher("d1", dispatcher, EnumMessageCategory.EVENT)
engine.register_route(route)
engine.freeze()  # Validates and freezes
# Now thread-safe for concurrent dispatch
```

## Dispatch Phase

### Dispatch Flow

1. **Parse Topic**: Extract message category from topic string
2. **Validate**: Ensure envelope is valid
3. **Match**: Find all dispatchers matching category + message type
4. **Execute**: Run dispatchers (fan-out for multiple matches)
5. **Collect**: Aggregate outputs and errors
6. **Return**: Build `ModelDispatchResult`

### Dispatcher Output Types

Dispatchers can return:
- `str`: A single output topic
- `list[str]`: Multiple output topics
- `None`: No output topics to publish

### Error Handling

- Dispatcher exceptions are caught and sanitized (no credential leakage)
- Dispatch continues to other dispatchers even if one fails
- Errors are aggregated in `ModelDispatchResult.error_message`

## Thread Safety

### Metrics Lock

Structured metrics updates are protected by `_metrics_lock`:

```python
with self._metrics_lock:
    self._structured_metrics = self._structured_metrics.record_dispatch(
        duration_ms=duration_ms,
        success=True,
        category=topic_category,
        topic=topic,
    )
```

### Lock Hold Time Minimization

The engine minimizes lock hold time by:
1. Reading existing metrics under lock
2. Computing updates outside lock
3. Updating atomically with `model_copy()` under lock

### Sync Dispatcher Execution

Sync dispatchers execute via `run_in_executor()`:

```
WARNING: Sync dispatchers MUST be non-blocking (< 100ms execution).
Blocking dispatchers can exhaust the thread pool, causing:
- Starvation of other sync dispatchers
- Delayed async dispatcher scheduling
- Potential deadlocks under high load

For blocking I/O operations, use async dispatchers instead.
```

## Observability

### Structured Logging

| Level | Events |
|-------|--------|
| **INFO** | Dispatch start/complete with topic, category, dispatcher count |
| **DEBUG** | Dispatcher execution details, routing decisions |
| **WARNING** | No dispatchers found, category mismatches |
| **ERROR** | Dispatcher exceptions, validation failures |

### Structured Metrics

Access via `get_structured_metrics()`:

```python
metrics = engine.get_structured_metrics()
print(f"Success rate: {metrics.success_rate:.1%}")
print(f"Avg latency: {metrics.avg_latency_ms:.2f} ms")
```

### Per-Dispatcher Metrics

```python
metrics = engine.get_dispatcher_metrics("user-event-dispatcher")
if metrics:
    print(f"Executions: {metrics.execution_count}")
    print(f"Error rate: {metrics.error_rate:.1%}")
```

## Fan-out Pattern

Fan-out allows multiple dispatchers to process the same message type. This is a core
capability for implementing event-driven architectures where a single event triggers
multiple independent dispatchers.

### When to Use Fan-out

| Use Case | Description |
|----------|-------------|
| **Event Sourcing** | Multiple projections from single event stream |
| **Notification System** | Email, SMS, push dispatchers from single notification event |
| **Analytics** | Multiple analytics processors from activity events |
| **Audit Trail** | Separate audit logger alongside business logic |

### Fan-out Registration

Register multiple dispatchers and routes that match the same topic pattern:

```python
# Two independent dispatchers for user events
async def send_welcome_email(envelope: ModelEventEnvelope[object]) -> str:
    user = envelope.payload
    await email_service.send_welcome(user.email)
    return "dev.email.sent.v1"

async def update_analytics(envelope: ModelEventEnvelope[object]) -> str:
    user = envelope.payload
    await analytics.track_signup(user.user_id)
    return "dev.analytics.tracked.v1"

# Register both dispatchers
engine.register_dispatcher(
    dispatcher_id="email-dispatcher",
    dispatcher=send_welcome_email,
    category=EnumMessageCategory.EVENT,
    message_types={"UserCreated"},
)
engine.register_dispatcher(
    dispatcher_id="analytics-dispatcher",
    dispatcher=update_analytics,
    category=EnumMessageCategory.EVENT,
    message_types={"UserCreated"},
)

# Register routes - both match the same topic pattern
engine.register_route(ModelDispatchRoute(
    route_id="email-route",
    topic_pattern="*.user.events.*",
    message_category=EnumMessageCategory.EVENT,
    dispatcher_id="email-dispatcher",
))
engine.register_route(ModelDispatchRoute(
    route_id="analytics-route",
    topic_pattern="*.user.events.*",
    message_category=EnumMessageCategory.EVENT,
    dispatcher_id="analytics-dispatcher",
))
engine.freeze()

# Dispatch triggers BOTH dispatchers
result = await engine.dispatch("dev.user.events.v1", user_created_envelope)
assert result.output_count == 2  # Both dispatchers produced outputs
```

### Fan-out Execution Semantics

- **All matching dispatchers execute**: Every dispatcher matching category + message type runs
- **Independent execution**: Dispatcher failures don't prevent other dispatchers from running
- **Output aggregation**: All dispatcher outputs are collected in `ModelDispatchResult.outputs`
- **Error aggregation**: Individual failures are captured in `error_message`, dispatch continues

### Fan-out Metrics

Track fan-out behavior via structured metrics:

```python
metrics = engine.get_structured_metrics()
# dispatcher_execution_count may exceed dispatch_count for fan-out
print(f"Dispatches: {metrics.dispatch_count}")
print(f"Dispatcher executions: {metrics.dispatcher_execution_count}")  # Higher with fan-out
print(f"Fan-out ratio: {metrics.dispatcher_execution_count / metrics.dispatch_count:.1f}")
```

## Resilience Patterns

### Dispatcher-Owned Resilience

**Dispatchers own their own resilience** - the `MessageDispatchEngine` does NOT wrap
dispatchers with circuit breakers.

**Rationale**:
- Separation of concerns: Each dispatcher knows its specific failure modes
- Transport-specific tuning: Kafka dispatchers need different thresholds than HTTP
- No hidden behavior: Engine users see exactly what resilience each dispatcher provides
- Composability: Dispatchers can combine circuit breakers with retry, backoff, degradation

### Circuit Breaker Integration Example

Dispatchers that call external services should implement `MixinAsyncCircuitBreaker`:

```python
from omnibase_infra.mixins import MixinAsyncCircuitBreaker
from omnibase_infra.enums import EnumInfraTransportType

class EmailDispatcher(MixinAsyncCircuitBreaker):
    """Dispatcher with built-in circuit breaker for external email service."""

    def __init__(self, config: EmailConfig):
        self._init_circuit_breaker(
            threshold=5,
            reset_timeout=60.0,
            service_name="email-service",
            transport_type=EnumInfraTransportType.HTTP,
        )

    async def handle(self, envelope: ModelEventEnvelope[object]) -> str | None:
        """Handle message with circuit breaker protection."""
        async with self._circuit_breaker_lock:
            await self._check_circuit_breaker("send_email", envelope.correlation_id)

        try:
            await self._send_email(envelope.payload)
            async with self._circuit_breaker_lock:
                await self._reset_circuit_breaker()
            return "dev.email.sent.v1"
        except Exception as e:
            async with self._circuit_breaker_lock:
                await self._record_circuit_failure("send_email", envelope.correlation_id)
            raise
```

For complete circuit breaker implementation details, see:
- `CLAUDE.md` section "Dispatcher Resilience Pattern"
- `docs/architecture/CIRCUIT_BREAKER_THREAD_SAFETY.md`
- `docs/patterns/circuit_breaker_implementation.md`

### Error Sanitization

Exception messages are sanitized before storage to prevent credential leakage:

```python
# Sensitive patterns that trigger redaction
_SENSITIVE_PATTERNS = (
    "password", "secret", "token", "api_key",
    "credential", "bearer", "private_key",
    "connection_string", "postgres://", "kafka://", ...
)
```

## Validation Thresholds

The Message Dispatch Engine models contribute to infrastructure validation thresholds:

| Metric | Current | Target | Notes |
|--------|---------|--------|-------|
| Union violations (INFRA_MAX_UNION_VIOLATIONS) | 0 | 0 | Counts violations, not total unions |
| Total unions (informational) | ~490 | <200 | Valid X \| None not counted |
| Pattern violations | Exempted | Strict | See exempted_patterns list |

### Documented Exemptions

The following pattern exemptions are documented in `infra_validators.py`:

1. **KafkaEventBus** (14 methods, 10 __init__ params)
   - Event bus pattern: lifecycle, pub/sub, circuit breaker, protocol compatibility

2. **RuntimeHostProcess** (11+ methods, 6+ params)
   - Central coordinator: lifecycle, message handling, graceful shutdown

3. **PolicyRegistry** (many methods)
   - Domain registry pattern: CRUD, query, lifecycle operations

4. **MixinNodeIntrospection** (many methods)
   - Introspection mixin: capability discovery, caching, publishing

5. **ExecutionShapeValidator** (many methods)
   - AST analysis: dispatcher detection, return analysis, violation detection

### Strict Mode Timeline

```
Status: ENABLED (INFRA_PATTERNS_STRICT = True per )

Enabled as of: 2025-12-20
- All violations must be fixed or added to exempted_patterns with documented rationale
- See validate_infra_patterns() in infra_validators.py for exemption list

Union Validation:
- Now counts VIOLATIONS, not total unions
- INFRA_MAX_UNION_VIOLATIONS = 10 (threshold for actual problems)
- Valid X | None patterns are NOT counted
- Total unions (~490) tracked for informational purposes only

Remaining Targets:
1. Reduce total unions to <200 through dict[str, object] → JsonValue migration
2. Complete H1 Legacy Migration
```

## Terminal Correlator Pattern

Some EFFECT handlers drive a request/response interaction over the bus: they publish a command, then block until the correlated terminal event arrives on a reply topic (correlating by `correlation_id`). The `HandlerContextRoiRunner` is the motivating case: per (task x arm x trial) it publishes `node-generation-requested.v1` and must wait for `node-generation-completed.v1` or `node-generation-failed.v1` before recording an attempt-reduction row.

### Why per-trial ephemeral consumers fail

The earlier design built a brand-new OS thread + asyncio event loop + `AIOKafkaConsumer` + `AIOKafkaClient` (full bootstrap / metadata fetch / partition coordination) for EVERY trial, and tore each down right after. Five offset/subscription patches (#1969–#1972) tuned this per-trial-ephemeral substrate and all failed the live K>=10 battery gate with the same wedge: a new client per trial races its own bootstrap and teardown against the fast terminal, so the COMPLETED leg silently never delivers while only the empty-set FAILED leg times out.

### Long-lived correlator (Tier B)

**Implementation**: `src/omnibase_infra/runtime/service_terminal_event_consumer.py`

One `TerminalEventConsumer` instance lives for the full process lifetime. It owns:

- **One dedicated worker thread** with its own asyncio event loop (separate from the runtime dispatch loop to avoid deadlock).
- **One `AIOKafkaConsumer` subscribed once** to both terminal topics for the lifetime of the batch, eliminating per-trial bootstrap/teardown races.
- **A `correlation_id → asyncio.Future` registry**: a trial registers its `correlation_id` BEFORE publishing its command (preserving the subscribe-before-publish guarantee from prior patches), then calls `session.wait(correlation_id, timeout)` which blocks the calling thread on the future resolved by the correlator's poll loop.

The design eliminates the entire timing-bug class structurally rather than tuning around it.

### Key behavioral details

| Behavior | Detail |
|----------|--------|
| Subscribe-before-publish | Trial registers `correlation_id` in the future registry, then publishes its command. The correlator already has its subscription open; no subscribe/assign window between publish and subscribe. |
| Synchronous partition-offset pinning | The correlator performs a synchronous `seek-to-end` after subscription to ensure it does not replay stale terminals from before the batch started. |
| Partition-less reply topics | Some reply topics may have no committed partitions at startup. The correlator tolerates this by using manual assignment only after the topic exists, rather than failing at subscribe time. |
| Worker thread isolation | `handle()` runs synchronously on the runtime dispatch loop. The correlator runs on its own dedicated loop to avoid deadlock. `session.wait()` blocks the calling thread via `concurrent.futures.Future` resolved across loops. |
| Fan-out safe | Multiple trials may await different `correlation_id`s concurrently. The registry is keyed by `correlation_id`; the poll loop demuxes each terminal to its waiting trial. |

### Architecture constraint (ARCH-002)

Nodes and handlers never touch the Kafka client directly. The `TerminalEventConsumer` is the contract-declared consume dependency materialized by runtime auto-wiring (`handler_wiring.py`). Handlers call the injected `event_consumer`; the runtime owns all Kafka plumbing.

---

## Related Documentation

### Implementation

- **Dispatch Engine**: `src/omnibase_infra/runtime/message_dispatch_engine.py`
- **Terminal Correlator**: `src/omnibase_infra/runtime/service_terminal_event_consumer.py`
- **Dispatcher Registry**: `src/omnibase_infra/runtime/dispatcher_registry.py`
- **Runtime Host**: `src/omnibase_infra/runtime/runtime_host_process.py`
- **Dispatch Models**: `src/omnibase_infra/models/dispatch/`
- **Validation**: `src/omnibase_infra/validation/infra_validators.py`

### Resilience Patterns

- **Circuit Breaker Thread Safety**: `docs/architecture/CIRCUIT_BREAKER_THREAD_SAFETY.md`
- **Circuit Breaker Implementation Guide**: `docs/patterns/circuit_breaker_implementation.md`
- **Error Recovery Patterns**: `docs/patterns/error_recovery_patterns.md`
- **Error Handling Patterns**: `docs/patterns/error_handling_patterns.md`
- **Dispatcher Resilience Pattern**: `CLAUDE.md` - "Dispatcher Resilience Pattern" section

### Testing

- **Unit Tests**: `tests/unit/runtime/test_message_dispatch_engine.py`
  - Fan-out dispatch tests: `test_dispatch_multiple_handlers_fan_out`
  - Concurrent dispatch tests: `test_concurrent_dispatch_with_multiple_handlers`
  - Thread safety tests: `TestConcurrentDispatchAdvanced` class

## Models Reference

### ModelDispatchRoute

```python
ModelDispatchRoute(
    route_id: str,           # Unique identifier
    topic_pattern: str,      # Glob pattern (e.g., "*.user.events.*")
    message_category: EnumMessageCategory,
    dispatcher_id: str,      # Reference to registered dispatcher
    message_type: str | None = None,  # Optional type filter
    enabled: bool = True,
)
```

### ModelDispatchResult

```python
ModelDispatchResult(
    dispatch_id: UUID,
    status: EnumDispatchStatus,
    topic: str,
    message_category: EnumMessageCategory | None,
    message_type: str | None,
    duration_ms: float,
    outputs: list[str] | None,  # Output topics from dispatchers
    output_count: int,
    error_message: str | None,
    error_code: EnumCoreErrorCode | None,
    correlation_id: UUID | None,
    trace_id: UUID | None,
    span_id: UUID | None,
)
```

### EnumDispatchStatus

```python
class EnumDispatchStatus(str, Enum):
    SUCCESS = "success"
    """Message was successfully routed, dispatched, and outputs published."""

    ROUTED = "routed"
    """Message was successfully routed to a dispatcher (pending execution)."""

    NO_DISPATCHER = "no_dispatcher"
    """No dispatcher was registered for the message type/topic."""

    HANDLER_ERROR = "handler_error"
    """Dispatcher execution failed with an exception."""

    TIMEOUT = "timeout"
    """Dispatcher execution exceeded the configured timeout."""

    INVALID_MESSAGE = "invalid_message"
    """Message failed validation before dispatch."""

    PUBLISH_FAILED = "publish_failed"
    """Dispatcher succeeded but output publishing failed."""

    SKIPPED = "skipped"
    """Message was intentionally skipped (e.g., filtered, deduplicated)."""
```

The enum also provides helper methods:
- `is_terminal()` - Returns `True` for all statuses except `ROUTED`
- `is_successful()` - Returns `True` only for `SUCCESS`
- `is_error()` - Returns `True` for `NO_DISPATCHER`, `HANDLER_ERROR`, `TIMEOUT`, `INVALID_MESSAGE`, `PUBLISH_FAILED`
- `requires_retry()` - Returns `True` for transient failures: `TIMEOUT`, `PUBLISH_FAILED`
