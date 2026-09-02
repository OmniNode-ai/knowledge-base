<!-- Migrated from omnibase_spi:docs/examples/README.md on 2026-09-01 -->

# Examples

## Overview

Practical examples demonstrating ONEX SPI protocol usage patterns.

> **Note**: Examples use implementation-specific factory functions like `get_service_registry()`, `get_workflow_orchestrator()`, etc. These are not part of the SPI protocols themselves but are provided by concrete implementations to demonstrate usage patterns.

## Available Examples

- **[Implementation Examples](../omnibase-spi-implementation-examples.md)** - How to implement SPI protocols in omnibase_infra
- **[Memory Protocols Guide](../omnibase-spi-memory-protocols-guide.md)** - Comprehensive memory system implementation patterns

## Basic Examples

### Service Registration and Resolution

```python
from omnibase_spi.protocols.container import ProtocolServiceRegistry
from omnibase_spi.protocols.core import ProtocolLogger

# Initialize service registry
# Note: get_service_registry() is an implementation-specific factory function
# that returns a concrete implementation of ProtocolServiceRegistry
registry: ProtocolServiceRegistry = get_service_registry()

# Register logger service
await registry.register_service(
    interface=ProtocolLogger,
    implementation=ConsoleLogger,
    lifecycle="singleton",
    scope="global"
)

# Resolve and use logger
logger = await registry.resolve_service(ProtocolLogger)
await logger.log("INFO", "Service registered successfully")
```

### Workflow Orchestration

```python
from omnibase_spi.protocols.workflow_orchestration import ProtocolWorkflowOrchestrator

# Initialize orchestrator
orchestrator: ProtocolWorkflowOrchestrator = get_workflow_orchestrator()

# Start workflow
workflow = await orchestrator.start_workflow(
    workflow_type="order-processing",
    instance_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
    initial_data={"order_id": "ORD-12345", "amount": 99.99}
)

# Monitor workflow state
state = await orchestrator.get_workflow_state(
    "order-processing",
    UUID("123e4567-e89b-12d3-a456-426614174000")
)
print(f"Workflow state: {state.current_state}")
```

### Event Bus Integration

The event bus provides multiple integration patterns for different use cases.

#### Basic Event Publishing with Provider

```python
from omnibase_spi.protocols.event_bus import ProtocolEventBusProvider
from omnibase_spi.protocols.types.protocol_event_bus_types import ProtocolEventMessage
from uuid import uuid4

# Get event bus from provider
provider: ProtocolEventBusProvider = get_event_bus_provider()
event_bus = await provider.get_event_bus(environment="prod", group="user-service")

# Publish event with full headers
await event_bus.publish(
    topic="user-events",
    key=b"user-12345",
    value=b'{"action": "user_created", "user_id": "12345", "email": "user@example.com"}',  # sanitization-ok: illustrative example payload
    headers={
        "event_type": "user_created",
        "correlation_id": str(uuid4()),
        "source": "user-service",
        "content_type": "application/json"
    }
)

# Clean shutdown
await provider.close_all()
```

#### Context Manager Pattern

```python
from omnibase_spi.protocols.event_bus import ProtocolEventBusContextManager

# Context manager handles connection lifecycle
context_manager: ProtocolEventBusContextManager = get_event_bus_context_manager()

async with context_manager as event_bus:
    # Connection established automatically
    await event_bus.publish(
        topic="order-events",
        key=b"order-ORD-123",
        value=b'{"order_id": "ORD-123", "status": "created"}',
        headers={"event_type": "order_created"}
    )

    # Publish multiple events
    for item in order_items:
        await event_bus.publish(
            topic="order-item-events",
            key=b"order-ORD-123",
            value=json.dumps(item).encode(),
            headers={"event_type": "order_item_added"}
        )
# Connection closed automatically on exit
```

#### Event Handler with Acknowledgment

```python
from omnibase_spi.protocols.types.protocol_event_bus_types import (
    ProtocolEventMessage,
    ContextValue,
)

async def user_event_handler(
    message: ProtocolEventMessage,
    context: dict[str, ContextValue]
) -> None:
    """Handle user events with proper acknowledgment."""
    try:
        # Parse event data
        event_data = json.loads(message.value.decode())
        user_id = event_data.get("user_id")

        print(f"Processing user event: {message.headers.event_type}")
        print(f"User ID: {user_id}")
        print(f"Correlation ID: {message.headers.correlation_id}")

        # Process the event
        await process_user_event(event_data)

        # Acknowledge successful processing
        await message.ack()

    except json.JSONDecodeError as e:
        print(f"Invalid JSON in message: {e}")
        # Don't requeue malformed messages
        await message.ack()

    except Exception as e:
        print(f"Error processing event: {e}")
        # Requeue for retry
        await message.nack(requeue=True)
```

#### Event Envelope Usage

```python
from omnibase_spi.protocols.event_bus import ProtocolEventEnvelope
from typing import Generic, TypeVar

T = TypeVar("T")

# Define payload type
@dataclass
class UserCreatedPayload:
    user_id: str
    email: str
    created_at: datetime

# Handler using envelope pattern
async def handle_user_created_envelope(
    envelope: ProtocolEventEnvelope[UserCreatedPayload]
) -> None:
    # Extract typed payload from envelope
    payload = await envelope.get_payload()

    print(f"User created: {payload.user_id}")
    print(f"Email: {payload.email}")
    print(f"Created at: {payload.created_at}")

    await create_user_profile(payload)
```

#### Batch Publishing

```python
from omnibase_spi.protocols.event_bus import ProtocolEventPublisher

publisher: ProtocolEventPublisher = get_event_publisher()

# Create batch of messages
messages = [
    create_event_message(
        topic="analytics-events",
        value=json.dumps({"event": "page_view", "user_id": user_id}).encode()
    )
    for user_id in active_users
]

# Publish batch with compression
batch_result = await publisher.publish_batch(
    topic="analytics-events",
    messages=messages,
    compression="snappy"  # Options: "none", "gzip", "snappy", "lz4", "zstd"
)

print(f"Published: {batch_result.success_count}")
print(f"Failed: {batch_result.failure_count}")
```

#### Dead Letter Queue Handling

```python
from omnibase_spi.protocols.event_bus import ProtocolDLQHandler

dlq_handler: ProtocolDLQHandler = get_dlq_handler()

# Get failed messages from DLQ
dlq_messages = await dlq_handler.get_dlq_messages(
    topic="order-events",
    limit=50
)

for dlq_msg in dlq_messages:
    print(f"Failed message ID: {dlq_msg.message_id}")
    print(f"Original topic: {dlq_msg.original_topic}")
    print(f"Failure reason: {dlq_msg.failure_reason}")
    print(f"Retry count: {dlq_msg.retry_count}")

    # Attempt to retry if transient error
    if dlq_msg.is_retriable:
        success = await dlq_handler.retry_failed_message(dlq_msg.message_id)
        if success:
            print(f"Successfully retried message {dlq_msg.message_id}")

# Clean up old DLQ messages (older than 7 days)
cleared_count = await dlq_handler.clear_dlq_messages(
    topic="order-events",
    older_than_hours=168  # 7 days
)
print(f"Cleared {cleared_count} old messages from DLQ")

# Analyze failure patterns
analysis = await dlq_handler.analyze_failure_patterns(
    topic="order-events",
    time_range_hours=24
)
print(f"Top failure reason: {analysis.top_failure_reason}")
print(f"Failure rate: {analysis.failure_rate:.2f}%")
```

#### Kafka Adapter Integration

```python
from omnibase_spi.protocols.event_bus import ProtocolKafkaAdapter

kafka_adapter: ProtocolKafkaAdapter = get_kafka_adapter()

# Connect to Kafka cluster
await kafka_adapter.connect_to_cluster([
    "kafka-1:9092",
    "kafka-2:9092",
    "kafka-3:9092"
])

# Create topic with replication
await kafka_adapter.create_kafka_topic(
    topic="user-events",
    partitions=6,
    replication_factor=3
)

# Get cluster metadata
metadata = await kafka_adapter.get_kafka_metadata()
print(f"Cluster ID: {metadata.cluster_id}")
print(f"Brokers: {[b.host for b in metadata.brokers]}")

# Get consumer group info
group_info = await kafka_adapter.get_consumer_group_info("user-service")
print(f"Group state: {group_info.state}")
print(f"Members: {len(group_info.members)}")

# Reset consumer group offset (for reprocessing)
await kafka_adapter.reset_consumer_group_offset(
    group_id="user-service",
    topic="user-events",
    offset=0  # Reset to beginning
)

# Disconnect when done
await kafka_adapter.disconnect_from_cluster()
```

#### Schema Registry Integration

```python
from omnibase_spi.protocols.event_bus import ProtocolSchemaRegistry

schema_registry: ProtocolSchemaRegistry = get_schema_registry()

# Register Avro schema
user_schema = {
    "type": "record",
    "name": "UserCreated",
    "namespace": "com.example.events",
    "fields": [
        {"name": "user_id", "type": "string"},
        {"name": "email", "type": "string"},
        {"name": "created_at", "type": "long", "logicalType": "timestamp-millis"}
    ]
}

schema_version = await schema_registry.register_schema(
    subject="user-events-value",
    schema=user_schema,
    schema_type="AVRO"
)
print(f"Registered schema version: {schema_version}")

# Check compatibility before updating
new_schema = {**user_schema}
new_schema["fields"].append({"name": "full_name", "type": ["null", "string"], "default": None})

compatibility = await schema_registry.check_compatibility(
    subject="user-events-value",
    schema=new_schema
)

if compatibility.compatible:
    print("Schema is backward compatible")
    await schema_registry.register_schema("user-events-value", new_schema)
else:
    print(f"Schema incompatible: {compatibility.reason}")

# Get all schema versions
versions = await schema_registry.get_schema_versions("user-events-value")
print(f"Available versions: {versions}")
```

## Advanced Examples

### MCP Integration

```python
from omnibase_spi.protocols.mcp import ProtocolMCPRegistry

# Initialize MCP registry
mcp_registry: ProtocolMCPRegistry = get_mcp_registry()

# Register subsystem
registration_id = await mcp_registry.register_subsystem(
    subsystem_metadata=ProtocolMCPSubsystemMetadata(
        subsystem_id="llm-subsystem-1",
        subsystem_type="llm",
        host="<onex-host>",
        port=8080
    ),
    tools=[
        ProtocolMCPToolDefinition(
            tool_name="text_generation",
            tool_type="function",
            description="Generate text using LLM"
        )
    ],
    api_key="mcp-api-key-12345"
)

# Execute tool
result = await mcp_registry.execute_tool(
    tool_name="text_generation",
    parameters={"prompt": "Hello world"},
    correlation_id=UUID("req-abc123")
)
print(f"Tool result: {result}")
```

### Memory Operations

> There is no single `ProtocolMemoryBase` protocol in the package — the
> memory domain is decomposed into `ProtocolKeyValueStore` (base key-value
> shape) plus focused interfaces. See the
> [Memory Protocols Guide](../omnibase-spi-memory-protocols-guide.md) for the full surface.

```python
from omnibase_spi.protocols.memory import ProtocolKeyValueStore

# Initialize a key-value backed memory structure
memory: ProtocolKeyValueStore = get_memory()

# Read a value
user_data = await memory.get_value("user:12345")
print(f"User data: {user_data}")

# Check existence
if memory.has_key("user:12345"):
    print("User exists")
```

### Validation

```python
from omnibase_spi.protocols.schema import ProtocolInputValidator

# Initialize validator
validator: ProtocolInputValidator = get_input_validator()

# Validate a field
validation_result = await validator.validate_string(
    value="john@example.com",  # sanitization-ok: illustrative example payload
    min_length=1,
    max_length=254,
    pattern=None,
    allow_empty=False,
)

if validation_result.is_valid:
    print("Data is valid")
else:
    print(f"Validation errors: {validation_result.errors}")
```

## Integration Examples

### Complete Service Integration

```python
from omnibase_spi.protocols.container import ProtocolServiceRegistry
from omnibase_spi.protocols.workflow_orchestration import ProtocolWorkflowOrchestrator
from omnibase_spi.protocols.event_bus import ProtocolEventBusProvider
from omnibase_spi.protocols.memory import ProtocolMemoryCache

class OrderProcessingService:
    """Complete order processing service."""

    def __init__(
        self,
        registry: ProtocolServiceRegistry,
        orchestrator: ProtocolWorkflowOrchestrator,
        event_bus: ProtocolEventBusProvider,
        memory: ProtocolMemoryCache
    ):
        self.registry = registry
        self.orchestrator = orchestrator
        self.event_bus = event_bus
        self.memory = memory

    async def process_order(self, order_data: dict[str, ContextValue]) -> str:
        """Process order with full integration."""
        # Start workflow
        workflow = await self.orchestrator.start_workflow(
            workflow_type="order-processing",
            instance_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            initial_data=order_data
        )

        # Cache the existing workflow record for hot follow-up reads.
        # The workflow service owns persistence of initial_data; this cache
        # API only takes the existing memory/workflow identifier.
        await self.memory.cache_memory(
            memory_id=workflow.instance_id,
            cache_ttl_seconds=86400,
            cache_level="hot",
        )

        # Publish event
        await self.event_bus.publish_event(
            topic="order-events",
            message=ProtocolEventMessage(
                topic="order-events",
                value=json.dumps(order_data).encode(),
                headers={"event_type": "order_created"}
            )
        )

        return str(workflow.instance_id)

# Initialize service
service = OrderProcessingService(
    registry=await get_service_registry(),
    orchestrator=await get_workflow_orchestrator(),
    event_bus=await get_event_bus(),
    memory=await get_memory()
)

# Process order
order_id = await service.process_order({
    "order_id": "ORD-12345",
    "amount": 99.99,
    "customer_id": "12345"
})
print(f"Order processed: {order_id}")
```

### Health Monitoring Integration

```python
from omnibase_spi.protocols.core import ProtocolHealthMonitor
from omnibase_spi.protocols.container import ProtocolServiceRegistry

class HealthAwareService:
    """Service with health monitoring."""

    def __init__(
        self,
        health_monitor: ProtocolHealthMonitor,
        registry: ProtocolServiceRegistry
    ):
        self.health_monitor = health_monitor
        self.registry = registry

    async def perform_operation(self, data: ContextValue) -> ContextValue:
        """Perform operation with health checking."""
        # Check service health
        health_status = await self.health_monitor.get_current_health_status()
        if health_status != "healthy":
            raise ServiceUnavailableError("Service unhealthy")

        # Perform operation
        result = await self._execute_operation(data)

        # Record health metrics
        await self.health_monitor.record_health_metric(
            metric_name="operation_success",
            value=1.0,
            tags={"service": "health_aware_service"}
        )

        return result

    async def _execute_operation(self, data: ContextValue) -> ContextValue:
        """Execute the actual operation."""
        # Implementation here
        return data

# Initialize service
service = HealthAwareService(
    health_monitor=await get_health_monitor(),
    registry=await get_service_registry()
)

# Use service
result = await service.perform_operation({"test": "data"})
print(f"Operation result: {result}")
```

## Best Practices

### Error Handling

```python
try:
    result = await service.perform_operation(data)
    return result
except ServiceUnavailableError as e:
    logger.error(f"Service unavailable: {e}")
    raise
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

### Performance Optimization

```python
# Use async/await patterns
async def process_data(data: list[ContextValue]) -> list[ContextValue]:
    """Process data efficiently."""
    tasks = []
    for item in data:
        task = asyncio.create_task(process_item(item))
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results
```

### Monitoring and Logging

```python
# Include comprehensive logging
async def process_workflow(workflow_data: dict[str, ContextValue]) -> str:
    """Process workflow with monitoring."""
    logger.info(f"Starting workflow: {workflow_data}")

    try:
        result = await orchestrator.start_workflow(
            workflow_type="data-processing",
            instance_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            initial_data=workflow_data
        )

        logger.info(f"Workflow started: {result.instance_id}")
        return str(result.instance_id)

    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise
```

## API Reference

- **`Core Protocols` (in the omnibase_spi repository)** - System fundamentals
- **`Container Protocols` (in the omnibase_spi repository)** - Dependency injection
- **`Workflow Orchestration` (in the omnibase_spi repository)** - Event-driven FSM
- **`MCP Integration` (in the omnibase_spi repository)** - Multi-subsystem coordination
- **`Event Bus` (in the omnibase_spi repository)** - Distributed messaging
- **`Memory Management` (in the omnibase_spi repository)** - Memory operations

---

*For detailed protocol documentation, see the `API Reference` (in the omnibase_spi repository).*
