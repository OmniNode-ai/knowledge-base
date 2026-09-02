---
type: guide
status: current
date: "2026-09-01"
title: "omnibase_spi Developer Guide"
topics:
  - omnibase_spi
  - developer-guide
  - protocols
refs: []
---

<!-- Migrated from omnibase_spi:docs/developer-guide/README.md on 2026-09-01 -->

# Developer Guide

## Overview

Complete development workflow and best practices for working with ONEX SPI protocols.

## Development Setup

### Prerequisites

- Python 3.12+
- `uv` (in the omnibase_spi repository) for dependency management
- Git for version control

### Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd omnibase-spi

# Install dependencies
uv sync --group dev

# Run validation
uv run pytest && uv build
```

## Development Workflow

### Protocol Development

1. **Create Protocol Files** - Define new protocols in appropriate domain directories
2. **Follow Naming Conventions** - Use `Protocol*` prefix for all protocols
3. **Add Type Hints** - Ensure all methods have proper type annotations
4. **Document Protocols** - Include comprehensive docstrings

### Validation Requirements

```bash
# Type safety validation
uv run mypy src/ --strict

# Protocol compliance checking
python scripts/validation/validate_spi_protocols.py

# Namespace isolation testing
python scripts/validation/validate_namespace_isolation.py

# Full repo-local validation suite
python scripts/validation/run_all_validations.py
```

### Testing Standards

- **Protocol Compliance** - All protocols must be `@runtime_checkable`
- **Type Safety** - Full mypy compatibility with strict checking
- **Namespace Isolation** - Complete separation from implementation packages
- **Zero Dependencies** - No runtime implementation dependencies

## Best Practices

### Protocol Design

- Use `typing.Protocol` for all interfaces
- Include `@runtime_checkable` decorator
- Provide comprehensive docstrings
- Use type hints for all parameters and return values

### Error Handling

- Define specific exception types
- Provide clear error messages
- Include context information
- Follow consistent error patterns

### Performance

- Use async/await patterns
- Implement efficient data structures
- Consider memory usage
- Optimize for common use cases

## Framework Integration Patterns

This section covers integration patterns for incorporating ONEX SPI protocols into your applications.

### Dependency Injection Integration

#### Service Registration

```python
from omnibase_spi.protocols.container import ProtocolServiceRegistry

# Initialize service registry
registry: ProtocolServiceRegistry = get_service_registry()

# Register services with lifecycle management
await registry.register_service(
    interface=ProtocolLogger,
    implementation=ConsoleLogger,
    lifecycle="singleton",
    scope="global"
)

await registry.register_service(
    interface=ProtocolHttpClient,
    implementation=AsyncHttpClient,
    lifecycle="transient",
    scope="request"
)
```

#### Service Resolution

```python
# Resolve services
logger = await registry.resolve_service(ProtocolLogger)
http_client = await registry.resolve_service(ProtocolHttpClient)

# Resolve with context
context = {"user_id": "12345", "request_id": "req-abc123"}
scoped_service = await registry.resolve_service(
    ProtocolUserService,
    scope="request",
    context=context
)
```

### Event-Driven Architecture Integration

#### Workflow Orchestration

```python
from omnibase_spi.protocols.workflow_orchestration import ProtocolWorkflowOrchestrator

# Initialize orchestrator
orchestrator: ProtocolWorkflowOrchestrator = get_workflow_orchestrator()

# Start workflow
workflow = await orchestrator.start_workflow(
    workflow_type="order-processing",
    instance_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
    initial_data={"order_id": "ORD-12345"}
)

# Monitor workflow state
state = await orchestrator.get_workflow_state(
    "order-processing",
    UUID("123e4567-e89b-12d3-a456-426614174000")
)
```

#### Event Bus Integration

The event bus follows a layered architecture with Core interfaces, SPI providers, and Infra implementations.

```python
from omnibase_spi.protocols.event_bus import (
    ProtocolEventBusProvider,
    ProtocolEventBusContextManager,
)
from omnibase_spi.protocols.types.protocol_event_bus_types import ProtocolEventMessage

# Option 1: Provider pattern (recommended for production)
provider: ProtocolEventBusProvider = get_event_bus_provider()
event_bus = await provider.get_event_bus(environment="prod", group="order-service")

# Publish events
await event_bus.publish(
    topic="user-events",
    key=b"user-12345",
    value=b'{"action": "user_created", "user_id": "12345"}',
    headers={"event_type": "user_created", "correlation_id": str(uuid4())}
)

# Option 2: Context manager pattern (recommended for scoped operations)
context_manager: ProtocolEventBusContextManager = get_event_bus_context_manager()

async with context_manager as event_bus:
    # Connection established on enter
    await event_bus.publish(
        topic="order-events",
        key=None,
        value=b'{"order_id": "ORD-123"}',
        headers={"event_type": "order_created"}
    )
    # Cleanup handled on exit (even if exception occurs)
```

#### Event Bus Provider Implementation

When implementing a custom event bus provider:

```python
from omnibase_spi.protocols.event_bus import (
    ProtocolEventBusProvider,
    ProtocolEventBusService,
)

class KafkaEventBusProvider:
    """Kafka implementation of the event bus provider."""

    def __init__(self, bootstrap_servers: list[str]):
        self._servers = bootstrap_servers
        self._instances: dict[str, ProtocolEventBusService] = {}
        self._default_env = "local"
        self._default_group = "default"

    async def get_event_bus(
        self,
        environment: str | None = None,
        group: str | None = None,
    ) -> ProtocolEventBusService:
        env = environment or self._default_env
        grp = group or self._default_group
        key = f"{env}:{grp}"

        if key not in self._instances:
            self._instances[key] = await self.create_event_bus(env, grp)
        return self._instances[key]

    async def create_event_bus(
        self,
        environment: str,
        group: str,
        config: dict[str, object] | None = None,
    ) -> ProtocolEventBusService:
        # Create new Kafka client with configuration
        return KafkaEventBus(
            bootstrap_servers=self._servers,
            group_id=group,
            environment=environment,
            **(config or {})
        )

    async def close_all(self) -> None:
        for bus in self._instances.values():
            await bus.close()
        self._instances.clear()

    @property
    def default_environment(self) -> str:
        return self._default_env

    @property
    def default_group(self) -> str:
        return self._default_group

# Verify protocol compliance
provider = KafkaEventBusProvider(["kafka:9092"])
assert isinstance(provider, ProtocolEventBusProvider)
```

#### Context Manager Implementation

```python
from omnibase_spi.protocols.event_bus import (
    ProtocolEventBusContextManager,
    ProtocolEventBusService,
)

class KafkaEventBusContextManager:
    """Context manager for Kafka event bus lifecycle."""

    def __init__(self, config: dict[str, str]):
        self._config = config
        self._event_bus: ProtocolEventBusService | None = None

    async def __aenter__(self) -> ProtocolEventBusService:
        # Initialize and connect
        self._event_bus = KafkaEventBus(
            bootstrap_servers=self._config["bootstrap_servers"].split(","),
            group_id=self._config.get("group_id", "default"),
        )
        await self._event_bus.connect()
        return self._event_bus

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        # Cleanup on exit
        if self._event_bus:
            await self._event_bus.close()
            self._event_bus = None

# Verify protocol compliance
cm = KafkaEventBusContextManager({"bootstrap_servers": "kafka:9092"})
assert isinstance(cm, ProtocolEventBusContextManager)
```

#### Event Envelope Pattern

Use the envelope protocol to break circular dependencies:

```python
from omnibase_spi.protocols.event_bus import ProtocolEventEnvelope
from typing import Generic, TypeVar

T = TypeVar("T")

class EventEnvelope(Generic[T]):
    """Envelope implementation for event payloads."""

    def __init__(self, payload: T, metadata: dict[str, str]):
        self._payload = payload
        self._metadata = metadata

    async def get_payload(self) -> T:
        return self._payload

# Handler that works with any envelope type
async def process_envelope(
    envelope: ProtocolEventEnvelope[UserCreatedPayload]
) -> None:
    payload = await envelope.get_payload()
    print(f"Processing user: {payload.user_id}")

# Verify protocol compliance
envelope = EventEnvelope(user_payload, {"correlation_id": "abc"})
assert isinstance(envelope, ProtocolEventEnvelope)
```

### MCP Integration

#### Tool Registration and Execution

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
```

### Memory Management Integration

#### Memory Operations

There is no single `ProtocolMemoryBase` interface — the memory domain
composes from `ProtocolKeyValueStore` plus focused interfaces
(`ProtocolAgentCoordinator`, `ProtocolMemoryCache`, `ProtocolStreamingMemoryNode`,
`ProtocolMemorySecurityNode`). See the
[Memory Protocols Guide](omnibase-spi-memory-protocols-guide.md) for the full
set. Base key-value access:

```python
from omnibase_spi.protocols.memory import ProtocolKeyValueStore

# Initialize a key-value backed memory structure
store: ProtocolKeyValueStore = get_memory_store()

# Read
value = await store.get_value("user:12345")

# Existence check
if store.has_key("user:12345"):
    print("Present")
```

### Validation Integration

#### Input Validation

```python
from omnibase_spi.protocols.schema import ProtocolInputValidator

# Initialize validator
validator: ProtocolInputValidator = get_input_validator()

# Validate a single field
validation_result = await validator.validate_string(
    value="John Doe",
    min_length=1,
    max_length=None,
    pattern=None,
    allow_empty=False,
)
```

## Integration Best Practices

### Protocol Compliance

- Use `isinstance(obj, Protocol)` for runtime validation
- Implement all required protocol methods
- Follow type hints and return types
- Handle errors appropriately

### Performance Optimization

- Use async/await patterns consistently
- Implement connection pooling
- Cache frequently accessed data
- Monitor and profile performance

### Error Handling

- Define specific exception types
- Provide clear error messages
- Include context information
- Implement retry mechanisms

#### Event Bus Error Handling

The event bus provides comprehensive error handling through the DLQ (Dead Letter Queue) protocol:

```python
from omnibase_spi.protocols.event_bus import ProtocolDLQHandler

# Get DLQ handler
dlq_handler: ProtocolDLQHandler = get_dlq_handler()

async def process_event_with_error_handling(
    message: ProtocolEventMessage
) -> None:
    try:
        # Process the event
        await process_business_logic(message)
        await message.ack()

    except ValidationError as e:
        # Non-retryable error - send directly to DLQ
        await dlq_handler.handle_failed_message(
            message=message,
            error=e,
            retry_count=0,  # Skip retries
        )

    except TransientError as e:
        # Retryable error - handle with retry logic
        result = await dlq_handler.handle_failed_message(
            message=message,
            error=e,
            retry_count=message.retry_count or 0,
        )

        if result.retry_eligible:
            # Will be retried automatically
            await message.nack(requeue=True)
        else:
            # Max retries exceeded, sent to DLQ
            await message.ack()

# Analyze failure patterns for monitoring
failure_analysis = await dlq_handler.analyze_failure_patterns(
    topic="order-events",
    time_range_hours=24
)
print(f"Top failure reason: {failure_analysis.top_failure_reason}")
print(f"Failure rate: {failure_analysis.failure_rate}%")
```

#### Retry with Exponential Backoff

```python
from omnibase_spi.protocols.event_bus import ProtocolEventPublisher

publisher: ProtocolEventPublisher = get_event_publisher()

# Publish with automatic retry and exponential backoff
success = await publisher.publish_with_retry(
    topic="critical-events",
    message=critical_message,
    max_retries=5,
    backoff_ms=1000,  # Initial backoff, doubles each retry
)

if not success:
    # All retries exhausted, handle failure
    await handle_publish_failure(critical_message)
```

## API Reference

- **`Core Protocols` (in the omnibase_spi repository)** - System fundamentals
- **`Container Protocols` (in the omnibase_spi repository)** - Dependency injection
- **`Workflow Orchestration` (in the omnibase_spi repository)** - Event-driven FSM
- **`MCP Integration` (in the omnibase_spi repository)** - Multi-subsystem coordination
- **`Event Bus` (in the omnibase_spi repository)** - Distributed messaging
- **`Memory Management` (in the omnibase_spi repository)** - Memory operations

## See Also

- **[Glossary](../reference/omnibase-spi-glossary.md)** - Definitions of SPI-specific terms (Protocol, Handler, Node, Contract, etc.)
- **[Quick Start Guide](omnibase-spi-quick-start.md)** - Get up and running quickly
- **[Architecture Overview](../architecture/omnibase-spi-overview.md)** - Design principles and patterns
- **[Dependency Direction](../architecture/omnibase-spi-dependency-direction.md)** - Import graph and boundary rules
- **`Contributing Guide` (in the omnibase_spi repository)** - How to contribute to the project
- **`Main README` (in the omnibase_spi repository)** - Repository overview

### Common Protocol References

- **`Node Protocols` (in the omnibase_spi repository)** - ONEX 4-node architecture
- **`Handler Protocols` (in the omnibase_spi repository)** - I/O handler interfaces
- **`Contract Compilers` (in the omnibase_spi repository)** - Contract compilation
- **`Registry Protocols` (in the omnibase_spi repository)** - Handler registry
- **`Exception Hierarchy` (in the omnibase_spi repository)** - Error handling

For term definitions, see the [Glossary](../reference/omnibase-spi-glossary.md).

---

*For detailed protocol documentation, see the `API Reference` (in the omnibase_spi repository).*
