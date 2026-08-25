---
type: architecture
status: accepted
date: "2026-07-21"
title: "Event Bus Integration Guide"
topics: [omnibase-infra, event, bus, integration]
refs: []
---


# Event Bus Integration Guide

## Overview

This guide provides step-by-step instructions for integrating with the ONEX Event Bus infrastructure. The Event Bus supports both production (Kafka) and development (in-memory) implementations with a consistent API.

**Implementation Files**:
- **EventBusKafka**: `src/omnibase_infra/event_bus/kafka_event_bus.py`
- **InMemoryEventBus**: `src/omnibase_infra/event_bus/inmemory_event_bus.py`
- **Models**: `src/omnibase_infra/event_bus/models/`


---

## Quick Start (5 Minutes)

### Choosing Your Event Bus

| Environment | Implementation | Use Case |
|-------------|----------------|----------|
| Production | `EventBusKafka` | Real message streaming with Kafka |
| Development/Testing | `InMemoryEventBus` | Local development, unit tests |

### Basic Setup

```python
import asyncio
from omnibase_infra.event_bus.kafka_event_bus import EventBusKafka
from omnibase_infra.event_bus.inmemory_event_bus import InMemoryEventBus
from omnibase_infra.event_bus.models import ModelEventMessage

# Option A: Production (Kafka)
bus = EventBusKafka.default()

# Option B: Development (In-Memory)
bus = InMemoryEventBus(environment="dev", group="my-service")

async def main():
    # Start the bus
    await bus.start()

    # Subscribe to a topic
    async def handler(msg: ModelEventMessage) -> None:
        print(f"Received: {msg.value.decode('utf-8')}")
        print(f"Topic: {msg.topic}")
        print(f"Correlation ID: {msg.headers.correlation_id}")

    unsubscribe = await bus.subscribe("my-topic", "my-group", handler)

    # Publish a message
    await bus.publish("my-topic", b"key-123", b'{"event": "test"}')

    # Cleanup
    await unsubscribe()
    await bus.close()

asyncio.run(main())
```

### Verifying It Works

```bash
# Set Kafka connection (if using EventBusKafka)
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"

# Run your code
python your_script.py
```

---

## Configuration Reference

### Environment Variables (EventBusKafka)

All environment variables are optional and fall back to defaults if not set.

#### Connection Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker addresses (comma-separated) |
| `KAFKA_ENVIRONMENT` | `local` | Environment identifier for routing (e.g., `dev`, `prod`) |
| `KAFKA_GROUP` | `default` | Consumer group identifier |

**Example**:
```bash
export KAFKA_BOOTSTRAP_SERVERS="kafka1:9092,kafka2:9092,kafka3:9092"
export KAFKA_ENVIRONMENT="prod"
export KAFKA_GROUP="order-service"
```

#### Timeout and Retry Settings

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `KAFKA_TIMEOUT_SECONDS` | `30` | 1-300 | Timeout for Kafka operations (seconds) |
| `KAFKA_MAX_RETRY_ATTEMPTS` | `3` | 0-10 | Maximum publish retry attempts |
| `KAFKA_RETRY_BACKOFF_BASE` | `1.0` | 0.1-60.0 | Base delay for exponential backoff (seconds) |

#### Circuit Breaker Settings

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `KAFKA_CIRCUIT_BREAKER_THRESHOLD` | `5` | 1-100 | Failures before circuit opens |
| `KAFKA_CIRCUIT_BREAKER_RESET_TIMEOUT` | `30.0` | 1.0-3600.0 | Seconds before circuit resets |

#### Consumer Settings

| Variable | Default | Options | Description |
|----------|---------|---------|-------------|
| `KAFKA_AUTO_OFFSET_RESET` | `latest` | `earliest`, `latest` | Offset reset policy |
| `KAFKA_ENABLE_AUTO_COMMIT` | `true` | `true/false` | Auto-commit consumer offsets |
| `KAFKA_CONSUMER_SLEEP_INTERVAL` | `0.1` | 0.01-10.0 | Poll interval (seconds) |

#### Producer Settings

| Variable | Default | Options | Description |
|----------|---------|---------|-------------|
| `KAFKA_ACKS` | `all` | `all`, `1`, `0` | Producer acknowledgment policy |
| `KAFKA_ENABLE_IDEMPOTENCE` | `true` | `true/false` | Enable idempotent producer |

#### Dead Letter Queue Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_DEAD_LETTER_TOPIC` | `None` | Topic name for failed messages (enables DLQ when set) |

### YAML Configuration

Create a YAML configuration file for more complex setups:

```yaml
# kafka_config.yaml
bootstrap_servers: "kafka:9092"
environment: "prod"
group: "order-service"
timeout_seconds: 60
max_retry_attempts: 5
retry_backoff_base: 2.0
circuit_breaker_threshold: 10
circuit_breaker_reset_timeout: 60.0
acks: "all"
enable_idempotence: true
auto_offset_reset: "earliest"
enable_auto_commit: true
dead_letter_topic: "dlq-events"
```

Load it:
```python
from pathlib import Path
from omnibase_infra.event_bus.kafka_event_bus import EventBusKafka

bus = EventBusKafka.from_yaml(Path("kafka_config.yaml"))
```

### Programmatic Configuration

```python
from omnibase_infra.event_bus.models.config import ModelEventBusKafkaConfig

config = ModelEventBusKafkaConfig(
    bootstrap_servers="kafka:9092",
    environment="prod",
    group="order-service",
    timeout_seconds=60,
    max_retry_attempts=5,
    circuit_breaker_threshold=10,
)
bus = EventBusKafka.from_config(config)
```

---

## Publishing Events

### Basic Publishing

```python
from omnibase_infra.event_bus.models import ModelEventHeaders

# Simple publish (auto-generated headers)
await bus.publish(
    topic="orders.events",
    key=b"order-123",
    value=b'{"order_id": "123", "status": "created"}',
)

# Publish with custom headers
headers = ModelEventHeaders(
    source="order-service",
    event_type="order.created",
    priority="high",
    routing_key="orders.us-east",
)
await bus.publish(
    topic="orders.events",
    key=b"order-123",
    value=b'{"order_id": "123", "status": "created"}',
    headers=headers,
)
```

### Publishing Envelopes (Pydantic Models)

For structured message publishing with automatic JSON serialization:

```python
from pydantic import BaseModel

class OrderCreatedEvent(BaseModel):
    order_id: str
    customer_id: str
    amount: float

event = OrderCreatedEvent(
    order_id="ORD-123",
    customer_id="CUST-456",
    amount=99.99,
)

# Envelope is automatically serialized to JSON
await bus.publish_envelope(event, topic="orders.events")
```

### Message Key Partitioning

Use message keys to ensure related messages go to the same partition:

```python
# All messages for the same order go to the same partition
order_id = "ORD-123"
await bus.publish(
    topic="orders.events",
    key=order_id.encode("utf-8"),  # Key determines partition
    value=event_data,
)
```

### Broadcasting to Environment

Send commands to all services in an environment:

```python
await bus.broadcast_to_environment(
    command="refresh_cache",
    payload={"cache_type": "products"},
    target_environment="prod",  # Optional, defaults to current
)
```

### Sending to Specific Group

Send commands to a specific consumer group:

```python
await bus.send_to_group(
    command="process_batch",
    payload={"batch_id": "BATCH-001"},
    target_group="batch-processor",
)
```

---

## Subscribing to Events

### Basic Subscription

```python
from omnibase_infra.event_bus.models import ModelEventMessage

async def order_handler(msg: ModelEventMessage) -> None:
    """Handle incoming order events."""
    # Access message fields
    topic = msg.topic
    value = msg.value  # bytes
    headers = msg.headers

    # Parse JSON payload
    import json
    payload = json.loads(value.decode("utf-8"))

    # Access header metadata
    correlation_id = headers.correlation_id
    event_type = headers.event_type
    source = headers.source

    print(f"Processing {event_type} from {source}")
    print(f"Correlation ID: {correlation_id}")

    # Acknowledge processing (for Kafka offset tracking)
    await msg.ack()

# Subscribe and get unsubscribe function
unsubscribe = await bus.subscribe(
    topic="orders.events",
    group_id="order-processor",
    on_message=order_handler,
)

# Later: unsubscribe when done
await unsubscribe()
```

### Multiple Subscribers

Multiple handlers can subscribe to the same topic:

```python
# Email notification handler
async def email_handler(msg: ModelEventMessage) -> None:
    payload = json.loads(msg.value.decode("utf-8"))
    await send_email(payload["customer_email"], "Order Received")

# Analytics handler
async def analytics_handler(msg: ModelEventMessage) -> None:
    payload = json.loads(msg.value.decode("utf-8"))
    await track_event("order_created", payload)

# Both handlers receive the same messages
unsub_email = await bus.subscribe("orders.events", "email-group", email_handler)
unsub_analytics = await bus.subscribe("orders.events", "analytics-group", analytics_handler)
```

### Blocking Consumer Loop

For long-running services, use `start_consuming()`:

```python
import asyncio
import signal

# Set up subscriptions
await bus.subscribe("orders.events", "processor", order_handler)
await bus.subscribe("payments.events", "processor", payment_handler)

# Handle graceful shutdown
def shutdown_handler(signum, frame):
    asyncio.create_task(bus.shutdown())

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

# Block until shutdown
await bus.start_consuming()  # Blocks here
```

---

## Message Categories (EVENT, COMMAND, INTENT)

ONEX uses three message categories for routing and semantics:

| Category | Purpose | Topic Convention | Example |
|----------|---------|------------------|---------|
| **EVENT** | Facts that occurred (past tense) | `*.events.*` | `UserCreatedEvent` |
| **COMMAND** | Instructions to perform (imperative) | `*.commands.*` | `CreateUserCommand` |
| **INTENT** | User intents requiring interpretation | `*.intents.*` | `UserWantsToCheckoutIntent` |

### Using Message Categories

```python
from omnibase_infra.enums import EnumMessageCategory

# Parse category from topic
category = EnumMessageCategory.from_topic("prod.orders.events.v1")
# Returns: EnumMessageCategory.EVENT

# Get topic suffix for category
suffix = EnumMessageCategory.COMMAND.topic_suffix
# Returns: "commands"

# Category checks
if category.is_event():
    # Handle as domain event
    pass
elif category.is_command():
    # Handle as command
    pass
elif category.is_intent():
    # Route to orchestrator
    pass
```

### Topic Naming Conventions

```
{environment}.{domain}.{category}.{version}

Examples:
- dev.orders.events.v1        -> EVENT category
- prod.payments.commands.v1   -> COMMAND category
- staging.checkout.intents.v1 -> INTENT category
```

---

## Error Handling and Retry Patterns

### Built-in Retry with Exponential Backoff

EventBusKafka automatically retries failed publishes:

```python
# Configuration
bus = EventBusKafka(
    max_retry_attempts=5,      # Max retries
    retry_backoff_base=2.0,    # 2s, 4s, 8s, 16s, 32s
)

# Publish - retries automatically on failure
try:
    await bus.publish("topic", b"key", b"value")
except InfraConnectionError as e:
    # All retries exhausted
    print(f"Failed after retries: {e}")
```

### Handling Subscriber Errors

Subscriber callbacks should handle their own errors:

```python
from omnibase_infra.errors import (
    InfraConnectionError,
    InfraTimeoutError,
    InfraUnavailableError,
)

async def robust_handler(msg: ModelEventMessage) -> None:
    """Handler with comprehensive error handling."""
    try:
        # Process message
        await process_order(msg)

    except InfraTimeoutError as e:
        # External service timeout - may retry
        logger.warning(f"Timeout processing message: {e}")
        raise  # Re-raise to trigger DLQ if configured

    except InfraConnectionError as e:
        # Connection failure - may retry
        logger.error(f"Connection error: {e}")
        raise

    except ValueError as e:
        # Invalid message format - don't retry
        logger.error(f"Invalid message format: {e}")
        # Don't raise - message is unprocessable

    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error: {e}")
        raise  # Let circuit breaker track failures
```

### Error Types

| Error Class | When Raised | Retry? |
|-------------|-------------|--------|
| `InfraConnectionError` | Connection to Kafka failed | Yes |
| `InfraTimeoutError` | Operation timed out | Yes |
| `InfraUnavailableError` | Circuit breaker open / Bus not started | No (wait for reset) |
| `ProtocolConfigurationError` | Invalid configuration | No (fix config) |

### Dead Letter Queue (DLQ)

Enable DLQ to capture failed messages:

```bash
export KAFKA_DEAD_LETTER_TOPIC="dlq-events"
```

Failed messages are published to DLQ with metadata:

```json
{
  "original_topic": "orders.events",
  "original_message": {
    "key": "order-123",
    "value": "{...}",
    "offset": "42",
    "partition": 0
  },
  "failure_reason": "Connection timeout",
  "failure_timestamp": "2025-01-15T10:30:00Z",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "retry_count": 3,
  "error_type": "InfraTimeoutError"
}
```

---

## Circuit Breaker Usage

The EventBusKafka includes a circuit breaker to prevent cascading failures.

### How It Works

```
CLOSED (Normal Operation)
    |
    | failure_count >= threshold (default: 5)
    v
  OPEN (Blocking Requests)
    |
    | reset_timeout elapsed (default: 30s)
    v
HALF_OPEN (Testing Recovery)
   / \
  /   \
 v     v
CLOSED  OPEN
(success) (failure)
```

### Configuration

```bash
# Open circuit after 10 failures
export KAFKA_CIRCUIT_BREAKER_THRESHOLD=10

# Reset after 60 seconds
export KAFKA_CIRCUIT_BREAKER_RESET_TIMEOUT=60.0
```

### Handling Circuit Breaker Errors

```python
from omnibase_infra.errors import InfraUnavailableError

try:
    await bus.publish("topic", b"key", b"value")
except InfraUnavailableError as e:
    # Circuit breaker is open
    print(f"Service unavailable: {e}")
    # Access retry hint
    if hasattr(e, "retry_after_seconds"):
        print(f"Retry after: {e.retry_after_seconds}s")
```

### Monitoring Circuit State

```python
# Check health including circuit state
health = await bus.health_check()
print(f"Healthy: {health['healthy']}")
print(f"Circuit state: {health['circuit_state']}")  # "open" or "closed"
```

---

## Correlation ID Tracking

Every message includes a correlation ID for distributed tracing.

### Automatic Correlation IDs

```python
from omnibase_infra.event_bus.models import ModelEventHeaders

# Auto-generated UUID
headers = ModelEventHeaders(
    source="order-service",
    event_type="order.created",
)
print(headers.correlation_id)  # UUID auto-generated
```

### Propagating Correlation IDs

Pass correlation IDs through the call chain:

```python
from uuid import UUID

async def process_order(msg: ModelEventMessage) -> None:
    # Extract correlation ID from incoming message
    correlation_id = msg.headers.correlation_id

    # Propagate to downstream calls
    downstream_headers = ModelEventHeaders(
        source="order-processor",
        event_type="payment.requested",
        correlation_id=correlation_id,  # Same ID
    )

    await bus.publish(
        "payments.commands",
        b"payment-key",
        payment_payload,
        headers=downstream_headers,
    )
```

### Tracing Integration

Headers support distributed tracing fields:

```python
headers = ModelEventHeaders(
    source="order-service",
    event_type="order.created",
    trace_id="abc123",           # Distributed trace ID
    span_id="def456",            # Current span
    parent_span_id="ghi789",     # Parent span
    operation_name="create_order",
)
```

---

## Testing with InMemoryEventBus

### Unit Test Setup

```python
import pytest
from omnibase_infra.event_bus.inmemory_event_bus import InMemoryEventBus

@pytest.fixture
async def event_bus():
    """Provide a fresh event bus for each test."""
    bus = InMemoryEventBus(environment="test", group="test-group")
    await bus.start()
    yield bus
    await bus.close()

@pytest.mark.asyncio
async def test_order_processing(event_bus):
    # Track received messages
    received = []

    async def handler(msg):
        received.append(msg)

    await event_bus.subscribe("orders.events", "test", handler)

    # Publish test event
    await event_bus.publish(
        "orders.events",
        b"order-123",
        b'{"order_id": "123"}',
    )

    # Verify
    assert len(received) == 1
    assert received[0].topic == "orders.events"
```

### Inspecting Event History

```python
async def test_event_history(event_bus):
    # Publish multiple events
    await event_bus.publish("topic-a", None, b"event-1")
    await event_bus.publish("topic-b", None, b"event-2")
    await event_bus.publish("topic-a", None, b"event-3")

    # Get all history
    history = await event_bus.get_event_history(limit=100)
    assert len(history) == 3

    # Filter by topic
    topic_a_events = await event_bus.get_event_history(limit=100, topic="topic-a")
    assert len(topic_a_events) == 2

    # Clear between tests
    await event_bus.clear_event_history()
```

### Testing Circuit Breaker Behavior

```python
async def test_circuit_breaker(event_bus):
    failure_count = 0

    async def failing_handler(msg):
        nonlocal failure_count
        failure_count += 1
        raise Exception("Simulated failure")

    await event_bus.subscribe("topic", "group", failing_handler)

    # Trigger failures to open circuit
    for _ in range(10):
        await event_bus.publish("topic", None, b"data")

    # Check circuit status
    status = await event_bus.get_circuit_breaker_status()
    assert len(status["open_circuits"]) > 0

    # Reset circuit for next test
    await event_bus.reset_subscriber_circuit("topic", "group")
```

### Debugging Utilities

```python
# Get subscriber count
count = await event_bus.get_subscriber_count("orders.events")
print(f"Subscribers: {count}")

# Get all subscribed topics
topics = await event_bus.get_topics()
print(f"Topics: {topics}")

# Get topic offset (message count)
offset = await event_bus.get_topic_offset("orders.events")
print(f"Messages published: {offset}")
```

---

## Production Deployment Considerations

### High Availability

```yaml
# Recommended production config
bootstrap_servers: "kafka1:9092,kafka2:9092,kafka3:9092"
acks: "all"                          # Wait for all replicas
enable_idempotence: true             # Exactly-once semantics
circuit_breaker_threshold: 10        # Higher tolerance
circuit_breaker_reset_timeout: 120   # Longer recovery window
max_retry_attempts: 5                # More retries
```

### Consumer Groups

- Use meaningful group names: `{service-name}-{function}`
- Example: `order-service-processor`, `payment-service-validator`

### Topic Naming

Follow ONEX conventions:

```
{environment}.{domain}.{category}.{version}

Production examples:
- prod.orders.events.v1
- prod.payments.commands.v1
- prod.inventory.events.v2
```

### Monitoring

```python
# Regular health checks
health = await bus.health_check()

# Log health metrics
logger.info(
    "Event bus health check",
    extra={
        "healthy": health["healthy"],
        "circuit_state": health["circuit_state"],
        "subscriber_count": health["subscriber_count"],
        "topic_count": health["topic_count"],
    },
)
```

### Graceful Shutdown

```python
import asyncio
import signal

async def main():
    bus = EventBusKafka.default()
    await bus.start()

    # Set up subscriptions...

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    async def shutdown():
        logger.info("Shutting down event bus...")
        await bus.close()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(shutdown())
        )

    await bus.start_consuming()
```

### Security

- Never log message values containing PII
- Use TLS for Kafka connections in production
- Rotate consumer group IDs when credentials change

---

## Troubleshooting Common Issues

### Connection Refused

**Symptom**: `InfraConnectionError: Failed to connect to Kafka`

**Solutions**:
1. Verify Kafka is running: `docker ps | grep kafka`
2. Check bootstrap servers: `echo $KAFKA_BOOTSTRAP_SERVERS`
3. Test connectivity: `nc -zv localhost 9092`

### Timeout Errors

**Symptom**: `InfraTimeoutError: Timeout connecting to Kafka after 30s`

**Solutions**:
1. Increase timeout: `export KAFKA_TIMEOUT_SECONDS=60`
2. Check network latency to Kafka brokers
3. Verify Kafka broker health

### Circuit Breaker Open

**Symptom**: `InfraUnavailableError: Circuit breaker is open`

**Solutions**:
1. Check Kafka cluster health
2. Wait for reset timeout (default: 30s)
3. Increase threshold for transient issues: `export KAFKA_CIRCUIT_BREAKER_THRESHOLD=10`

### Messages Not Received

**Symptom**: Subscribers not receiving published messages

**Solutions**:
1. Verify bus is started: `await bus.start()`
2. Check topic name matches exactly
3. Verify subscriber was registered before publishing
4. Check health: `await bus.health_check()`

### Duplicate Messages

**Symptom**: Handler receives same message multiple times

**Solutions**:
1. Enable idempotence: `export KAFKA_ENABLE_IDEMPOTENCE=true`
2. Implement idempotent handlers (check message_id)
3. Use auto-commit for offset management

### Memory Issues (InMemoryEventBus)

**Symptom**: Memory usage grows with InMemoryEventBus

**Solutions**:
1. Reduce history size: `InMemoryEventBus(max_history=100)`
2. Clear history between tests: `await bus.clear_event_history()`
3. Unsubscribe handlers when done

---

## API Reference

### EventBusKafka

```python
class EventBusKafka:
    # Factory methods
    @classmethod
    def default(cls) -> EventBusKafka: ...
    @classmethod
    def from_config(cls, config: ModelEventBusKafkaConfig) -> EventBusKafka: ...
    @classmethod
    def from_yaml(cls, path: Path) -> EventBusKafka: ...

    # Lifecycle
    async def start(self) -> None: ...
    async def close(self) -> None: ...
    async def shutdown(self) -> None: ...

    # Pub/Sub
    async def publish(self, topic: str, key: bytes | None, value: bytes,
                      headers: ModelEventHeaders | None = None) -> None: ...
    async def publish_envelope(self, envelope: object, topic: str) -> None: ...
    async def subscribe(self, topic: str, group_id: str,
                        on_message: Callable[[ModelEventMessage], Awaitable[None]]
                        ) -> Callable[[], Awaitable[None]]: ...
    async def start_consuming(self) -> None: ...

    # Communication helpers
    async def broadcast_to_environment(self, command: str,
                                        payload: dict[str, JsonValue],
                                        target_environment: str | None = None) -> None: ...
    async def send_to_group(self, command: str, payload: dict[str, JsonValue],
                            target_group: str) -> None: ...

    # Health
    async def health_check(self) -> dict[str, JsonValue]: ...

    # Properties
    @property
    def environment(self) -> str: ...
    @property
    def group(self) -> str: ...
    @property
    def config(self) -> ModelEventBusKafkaConfig: ...
```

### InMemoryEventBus

Same interface as EventBusKafka, plus debugging utilities:

```python
class InMemoryEventBus:
    # ... same core API as EventBusKafka ...

    # Debugging utilities
    async def get_event_history(self, limit: int = 100,
                                topic: str | None = None) -> list[ModelEventMessage]: ...
    async def clear_event_history(self) -> None: ...
    async def get_subscriber_count(self, topic: str | None = None) -> int: ...
    async def get_topics(self) -> list[str]: ...
    async def get_topic_offset(self, topic: str) -> int: ...

    # Circuit breaker management
    async def reset_subscriber_circuit(self, topic: str, group_id: str) -> bool: ...
    async def get_circuit_breaker_status(self) -> dict[str, JsonValue]: ...
```

### ModelEventMessage

```python
class ModelEventMessage(BaseModel):
    topic: str
    key: bytes | None
    value: bytes
    headers: ModelEventHeaders
    offset: str | None
    partition: int | None

    async def ack(self) -> None: ...
```

### ModelEventHeaders

```python
class ModelEventHeaders(BaseModel):
    content_type: str = "application/json"
    correlation_id: UUID  # Auto-generated
    message_id: UUID      # Auto-generated
    timestamp: datetime   # Auto-generated
    source: str
    event_type: str
    schema_version: str = "1.0.0"
    destination: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    operation_name: str | None = None
    priority: Literal["low", "normal", "high", "critical"] = "normal"
    routing_key: str | None = None
    partition_key: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    ttl_seconds: int | None = None

    async def validate_headers(self) -> bool: ...
```

---

## AdapterProtocolEventPublisherKafka

Production-grade adapter implementing `ProtocolEventPublisher` from `omnibase_spi`. Bridges the SPI protocol to `EventBusKafka` for production event publishing.

**Module**: `omnibase_infra.event_bus.adapters.adapter_protocol_event_publisher_kafka`

### Purpose

This adapter provides a standard interface for event publishing while delegating resilience (circuit breaker, retry, backoff) to the underlying `EventBusKafka`. It implements the `ProtocolEventPublisher` protocol from `omnibase_spi`, enabling consistent event publishing across the ONEX infrastructure.

### Relationship to ProtocolEventPublisher

| Protocol Method | Adapter Implementation |
|-----------------|------------------------|
| `publish()` | Builds `ModelEventEnvelope`, serializes to JSON, delegates to `EventBusKafka.publish()` |
| `get_metrics()` | Returns `ModelPublisherMetrics` with circuit breaker state from underlying bus |
| `close()` | Marks adapter closed, stops underlying `EventBusKafka` |

### Constructor

```python
def __init__(
    self,
    bus: EventBusKafka,
    service_name: str = "kafka-publisher",
    instance_id: str | None = None,
) -> None
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bus` | `EventBusKafka` | (required) | The EventBusKafka instance to bridge to. Must be started before publishing. |
| `service_name` | `str` | `"kafka-publisher"` | Service name included in envelope metadata for tracing. |
| `instance_id` | `str \| None` | `None` | Instance identifier. Defaults to a generated UUID if not provided. |

### Methods

#### publish()

```python
async def publish(
    self,
    event_type: str,
    payload: JsonType,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    metadata: dict[str, ContextValue] | None = None,
    topic: str | None = None,
    partition_key: str | None = None,
) -> bool
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `event_type` | `str` | (required) | Fully-qualified event type (e.g., `"omninode.user.event.created.v1"`). |
| `payload` | `JsonType` | (required) | Event payload data (dict, list, or primitive JSON types). |
| `correlation_id` | `str \| None` | `None` | Correlation ID for request tracing. Converted to UUID. |
| `causation_id` | `str \| None` | `None` | Causation ID for event sourcing chains. Stored in metadata tags. |
| `metadata` | `dict[str, ContextValue] \| None` | `None` | Additional metadata as context values. |
| `topic` | `str \| None` | `None` | Explicit topic override. When `None`, uses `event_type` as topic. |
| `partition_key` | `str \| None` | `None` | Partition key for message ordering. Encoded to UTF-8 bytes. |

**Returns**: `bool` — `True` if published successfully, `False` otherwise.

**Raises**: `InfraUnavailableError` if adapter has been closed.

#### get_metrics()

```python
async def get_metrics(self) -> JsonType
```

Get publisher metrics including circuit breaker status from underlying bus.

#### reset_metrics()

```python
async def reset_metrics(self) -> None
```

Reset all publisher metrics to initial values. Useful for test isolation. Does NOT affect the closed state of the adapter.

#### close()

```python
async def close(self, timeout_seconds: float = 30.0) -> None
```

Close the publisher and release resources. After closing, any calls to `publish()` will raise `InfraUnavailableError`.

### Usage Example

```python
from omnibase_infra.event_bus import EventBusKafka
from omnibase_infra.event_bus.adapters import AdapterProtocolEventPublisherKafka

bus = EventBusKafka.from_env()
await bus.start()

adapter = AdapterProtocolEventPublisherKafka(
    bus=bus,
    service_name="my-service",
)

success = await adapter.publish(
    event_type="user.created.v1",
    payload={"user_id": "123"},
    correlation_id="corr-abc",
)

# Explicit topic and partition key
success = await adapter.publish(
    event_type="order.placed.v1",
    payload={"order_id": "ord-456", "customer_id": "cust-789"},
    topic="orders.high-priority",
    partition_key="cust-789",
    correlation_id="corr-xyz",
    causation_id="cmd-123",
)

metrics = await adapter.get_metrics()
print(f"Published: {metrics['events_published']}")

await adapter.close()
```

### Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `events_published` | `int` | Total count of successfully published events. |
| `events_failed` | `int` | Total count of failed publish attempts. |
| `events_sent_to_dlq` | `int` | Always 0 — publish path does not use DLQ. |
| `total_publish_time_ms` | `float` | Cumulative publish time in milliseconds. |
| `avg_publish_time_ms` | `float` | Average publish latency. |
| `circuit_breaker_opens` | `int` | Count of circuit breaker open events from underlying bus. |
| `retries_attempted` | `int` | Total retry attempts from underlying bus. |
| `circuit_breaker_status` | `str` | Current state: `"closed"`, `"open"`, `"half_open"`. |
| `current_failures` | `int` | Current consecutive failure count. |

### Design Decisions

- **No double circuit breaker**: The adapter does NOT implement its own circuit breaker. Resilience is delegated to `EventBusKafka`.
- **Publish returns bool**: All exceptions during publish are caught and result in `False`. No exceptions propagate except `InfraUnavailableError` for closed adapter.
- **Topic routing**: Explicit `topic` parameter takes precedence over `event_type`-derived topic.
- **Causation ID in tags**: Since `ModelEventEnvelope` has no dedicated `causation_id` field, the adapter stores it in `metadata.tags["causation_id"]`.
- **Partition key encoding**: The `partition_key` is encoded to UTF-8 bytes per the SPI specification.

### Error Handling

| Scenario | Behavior |
|----------|----------|
| Publish succeeds | Returns `True`, increments `events_published` |
| Publish fails (any exception) | Returns `False`, increments `events_failed`, logs exception |
| Adapter closed | Raises `InfraUnavailableError("Publisher has been closed")` |
| Invalid correlation_id format | Generates new UUID, logs warning with original value |
| Close fails | Logs warning, continues (best-effort cleanup) |

---

## Related Documentation

- **Message Dispatch Engine**: `docs/architecture/MESSAGE_DISPATCH_ENGINE.md`
- **Circuit Breaker Thread Safety**: `docs/architecture/CIRCUIT_BREAKER_THREAD_SAFETY.md`
- **Error Handling Patterns**: `docs/patterns/error_handling_patterns.md`
- **Error Recovery Patterns**: `docs/patterns/error_recovery_patterns.md`
