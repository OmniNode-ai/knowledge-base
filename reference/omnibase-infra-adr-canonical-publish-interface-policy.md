---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Canonical Publish Interface Policy"
topics: [omnibase-infra, adr, canonical, publish]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-canonical-publish-interface-policy.md on 2026-09-02. -->

# ADR: Canonical Publish Interface Policy

**Status**: Accepted
**Date**: 2026-01-27
**Category**: Architecture

## Context

The ONEX platform uses an event-driven architecture where handlers publish events to an event bus (Kafka/Redpanda). As the codebase grew, multiple publish interface patterns emerged:

1. **SPI-defined protocol**: `omnibase_spi.ProtocolEventPublisher` - semantic publishing with retry, circuit breaker, and DLQ
2. **Handler-local protocols**: Ad-hoc `ProtocolKafkaPublisher` or similar interfaces defined within handler modules
3. **Direct transport access**: Handlers importing Kafka producer classes directly

This interface proliferation creates several problems:

### Problems with Handler-Local Publish Protocols

| Problem | Impact |
|---------|--------|
| **Interface drift** | Each handler defines slightly different publish signatures, making composition impossible |
| **Duplicated reliability logic** | Every handler reinvents retry, circuit breaker, and error handling |
| **Tight transport coupling** | Handlers become Kafka-specific instead of transport-agnostic |
| **Testing complexity** | Each custom protocol requires its own mock implementation |
| **Unclear layer boundaries** | Blurs the line between handler logic and infrastructure concerns |

### Example of Interface Drift

```python
# Handler A's local protocol
class ProtocolKafkaPublisher(Protocol):
    async def publish(self, topic: str, message: bytes) -> None: ...

# Handler B's local protocol
class ProtocolEventSender(Protocol):
    async def send(self, event_type: str, payload: dict) -> bool: ...

# Handler C's local protocol
class ProtocolMessageBus(Protocol):
    async def emit(self, topic: str, key: str, value: str) -> str: ...
```

These three protocols cannot be satisfied by a single implementation, forcing handler-specific adapters.

### The Layering Question

The ONEX architecture defines clear layers:

```
┌─────────────────────────────────────────────────────────┐
│                      HANDLERS                            │
│  Business logic, orchestration, event processing         │
│  Depends on: omnibase_spi.ProtocolEventPublisher        │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Semantic publish interface
                          ▼
┌─────────────────────────────────────────────────────────┐
│                      INFRA LAYER                         │
│  Transport adapters, connection pools, bytes encoding    │
│  Implements: ProtocolEventPublisher                      │
│  Owns: Kafka producer, retry logic, circuit breaker      │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Wire protocol (bytes)
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   KAFKA/REDPANDA                         │
│  Message broker, partitions, topics                      │
└─────────────────────────────────────────────────────────┘
```

## Decision

**The `omnibase_spi.ProtocolEventPublisher` is the ONLY publish interface that handlers may depend on.**

### Rule 1: Handlers Use ProtocolEventPublisher

All handler classes that need to publish events MUST depend on `ProtocolEventPublisher` from `omnibase_spi`:

```python
from omnibase_spi.protocols.event_bus import ProtocolEventPublisher

class MyHandler:
    def __init__(self, publisher: ProtocolEventPublisher) -> None:
        self._publisher = publisher

    async def handle(self, event: ModelSomeEvent) -> None:
        # Semantic publishing - transport-agnostic
        await self._publisher.publish(
            event_type="omninode.mydomain.event.something_happened.v1",
            payload={"entity_id": str(event.entity_id)},
            correlation_id=event.correlation_id,
        )
```

### Rule 2: Handler-Local Publish Protocols Are Forbidden

**No new `Protocol*Publisher` or `Protocol*Sender` definitions outside `omnibase_spi`.**

The following patterns are prohibited in handler code:

```python
# FORBIDDEN: Handler-local publish protocol
class ProtocolKafkaPublisher(Protocol):
    async def publish(self, topic: str, message: bytes) -> None: ...

# FORBIDDEN: Handler-specific event sender
class ProtocolEventSender(Protocol):
    async def send_event(self, event: ModelEvent) -> bool: ...

# FORBIDDEN: Direct transport protocol in handler
class ProtocolMessageBusClient(Protocol):
    async def produce(self, topic: str, key: bytes, value: bytes) -> None: ...
```

### Rule 3: Infra Layer Owns Transport Adapters

The infrastructure layer (`omnibase_infra`) is responsible for:

1. **Transport adapters**: Kafka producer wrappers, connection pooling
2. **Byte encoding**: UTF-8 partition key encoding, serialization
3. **Connection lifecycle**: Producer initialization, shutdown, reconnection
4. **Reliability features**: Retry logic, circuit breakers, DLQ routing

```python
# In omnibase_infra - implements the SPI protocol
from omnibase_spi.protocols.event_bus import ProtocolEventPublisher

class KafkaEventPublisher:
    """Infra implementation of ProtocolEventPublisher."""

    async def publish(
        self,
        event_type: str,
        payload: JsonType,
        correlation_id: str | None = None,
        # ... full ProtocolEventPublisher signature
    ) -> bool:
        # Infra owns: serialization, key encoding, transport
        key_bytes = partition_key.encode("utf-8") if partition_key else None
        value_bytes = json.dumps(payload).encode("utf-8")
        await self._kafka_producer.send(topic, key=key_bytes, value=value_bytes)
        return True
```

### Rule 4: Raw Kafka Access Means You ARE Infrastructure

If a handler truly needs raw Kafka byte-level access (direct producer, custom partitioner, transactional semantics), that handler is performing infrastructure work and MUST be placed in `omnibase_infra`:

```python
# This code belongs in omnibase_infra, NOT in a handler module
from aiokafka import AIOKafkaProducer

class TransactionalEventPublisher:
    """Low-level transactional publisher - lives in omnibase_infra."""

    async def publish_transactional(
        self,
        events: list[tuple[str, bytes, bytes]],  # topic, key, value
    ) -> None:
        async with self._producer.transaction():
            for topic, key, value in events:
                await self._producer.send(topic, key=key, value=value)
```

### Protocol Reference

The canonical protocol is defined in:

```
omnibase_spi/src/omnibase_spi/protocols/event_bus/protocol_event_publisher.py
```

Key interface methods:

| Method | Purpose |
|--------|---------|
| `publish()` | Publish single event with retry and circuit breaker |
| `get_metrics()` | Retrieve publisher metrics (events published, failed, DLQ) |
| `close()` | Graceful shutdown with message flush |

Key features provided by the protocol:

| Feature | Handler Responsibility | Infra Responsibility |
|---------|----------------------|---------------------|
| **Retry logic** | None - just call `publish()` | Exponential backoff, max retries |
| **Circuit breaker** | Handle `RuntimeError` if open | State management, reset timeout |
| **DLQ routing** | None - automatic | Route failed events to DLQ topic |
| **Correlation tracking** | Pass `correlation_id` | Include in event metadata |
| **Serialization** | Pass `JsonType` payload | JSON/Avro encoding to bytes |
| **Partition key encoding** | Pass string key | UTF-8 byte encoding |

## Consequences

### Positive

- **Single canonical interface**: All handlers use the same publish contract
- **Transport-agnostic handlers**: Handlers work with any `ProtocolEventPublisher` implementation (Kafka, in-memory, mock)
- **Centralized reliability**: Retry, circuit breaker, and DLQ logic implemented once in infra
- **Simplified testing**: One mock implementation satisfies all handlers
- **Clear layer boundaries**: Handlers do business logic, infra does transport
- **Prevents interface drift**: No proliferation of similar-but-incompatible protocols

### Negative

- **Less handler flexibility**: Handlers cannot customize transport behavior
- **SPI dependency**: Handlers must depend on `omnibase_spi` (already a required dependency)
- **Migration effort**: Existing handler-local protocols must be refactored

### Neutral

- **Infra as extension point**: Truly transport-specific handlers become infra components
- **Protocol stability pressure**: Changes to `ProtocolEventPublisher` affect all handlers

## Compliance

### Verification via Grep

To verify compliance, run these grep patterns:

```bash
# Find forbidden handler-local publish protocols
# Should return ZERO results outside omnibase_spi and omnibase_infra
rg "class Protocol.*Publisher" --type py \
  --glob '!**/omnibase_spi/**' \
  --glob '!**/omnibase_infra/**'

# Find forbidden direct Kafka imports in handlers
# Should return ZERO results in handler modules
rg "from (aiokafka|kafka|confluent_kafka)" --type py \
  --glob '**/handlers/**' \
  --glob '**/nodes/**/handler_*.py'

# Find proper SPI protocol usage
# Should show handlers importing from omnibase_spi
rg "from omnibase_spi.protocols.event_bus import ProtocolEventPublisher" --type py
```

### CI Integration

Add to pre-commit or CI validation:

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: no-handler-local-publish-protocols
      name: No handler-local publish protocols
      entry: bash -c 'rg "class Protocol.*Publisher" --type py --glob "!**/omnibase_spi/**" --glob "!**/omnibase_infra/**" && exit 1 || exit 0'
      language: system
      pass_filenames: false
```

### Migration Checklist

For existing handler-local protocols:

- [ ] Identify all `Protocol*Publisher` definitions outside SPI/infra
- [ ] Refactor handlers to depend on `ProtocolEventPublisher`
- [ ] Move transport-specific code to `omnibase_infra`
- [ ] Update tests to use SPI protocol mocks
- [ ] Delete handler-local protocol definitions

## References

- **Parent Ticket**:  - Publish Interface Consolidation
- **This Ticket**:  - Write ADR for Canonical Publish Interface Policy
- **SPI Protocol**: `omnibase_spi/src/omnibase_spi/protocols/event_bus/protocol_event_publisher.py`
- **Related ADR**: Handler No-Publish Constraint (handlers cannot have direct bus access)
- **Related Pattern**: Dispatcher Resilience (dispatchers own their own resilience)
