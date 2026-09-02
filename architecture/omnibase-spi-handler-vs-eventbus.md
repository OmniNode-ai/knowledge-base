---
type: architecture
status: accepted
date: "2026-09-01"
title: "ProtocolHandler vs ProtocolEventBus"
topics:
  - omnibase_spi
  - architecture
  - handler
  - event-bus
refs: []
---

<!-- Migrated from omnibase_spi:src/omnibase_spi/protocols/README.md on 2026-09-01 -->

# Protocol Patterns: Handler vs Event Bus

This document explains when to use `ProtocolHandler` versus `ProtocolEventBus` patterns in the ONEX SPI.

## Overview

The ONEX platform provides two distinct communication patterns for external interactions:

| Pattern | Purpose | Communication Style |
|---------|---------|---------------------|
| **ProtocolHandler** | Request-response I/O operations | Synchronous, direct response expected |
| **ProtocolEventBus** | Async message passing and pub/sub | Fire-and-forget, decoupled |

### ProtocolHandler

Request-response pattern for direct I/O operations where a response is expected. Used within effect nodes to perform external calls like HTTP requests, database queries, or protocol-specific operations.

**Key Characteristics:**
- Synchronous request-response semantics
- Connection pooling and resource management
- Health checks and retry handling
- Tight request-response coupling

### ProtocolEventBus

Asynchronous publish-subscribe pattern for decoupled inter-service communication. Used for event-driven architectures, event sourcing, and workflows where services communicate without direct coupling.

**Key Characteristics:**
- Fire-and-forget publishing
- Multiple subscribers per topic
- Correlation ID propagation for distributed tracing
- Dead letter queue (DLQ) support for failed messages

## Comparison Table

| Aspect | ProtocolHandler | ProtocolEventBus |
|--------|-----------------|------------------|
| **Use Case** | HTTP/REST, DB queries, API calls | Event sourcing, inter-service messaging |
| **Communication** | Request-response | Publish-subscribe |
| **Coupling** | Direct (caller waits for response) | Decoupled (fire-and-forget) |
| **Response** | Immediate, structured response | No direct response expected |
| **Failure Handling** | Retries, circuit breakers | DLQ routing, reprocessing |
| **Scalability** | Connection pooling | Topic partitioning |
| **Tracing** | Request/response correlation | Envelope correlation IDs |
| **Examples** | `HttpRestHandler`, `PostgresHandler` | `KafkaAdapter`, `RedpandaAdapter` |

## When to Use Each Pattern

### Use ProtocolHandler When:

1. **Direct Response Required** - You need an immediate response from an external system
2. **Synchronous Workflow** - The calling code must wait for the result before continuing
3. **Connection Pooling** - Managing persistent connections to databases or services
4. **Protocol Translation** - Converting between internal models and external protocols
5. **Health Monitoring** - Need real-time health status of external dependencies

**Typical scenarios:**
- REST API calls to external services
- Database CRUD operations
- GraphQL queries
- Cache operations (Redis, Memcached)
- File storage operations (S3, GCS)

### Use ProtocolEventBus When:

1. **Decoupled Services** - Services should not depend on each other's availability
2. **Event Sourcing** - Recording domain events for audit/replay
3. **Async Workflows** - Long-running processes that don't need immediate response
4. **Fan-out Patterns** - One event triggers multiple downstream processes
5. **Cross-Service Communication** - Inter-service messaging in microservices

**Typical scenarios:**
- Domain event publishing (e.g., "OrderCreated", "UserRegistered")
- Audit logging
- Analytics event streaming
- Workflow orchestration
- Change data capture (CDC)

## Code Examples

### ProtocolHandler Example

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from omnibase_core.models.handlers import ModelHandlerDescriptor
    from omnibase_core.models.protocol import (
        ModelConnectionConfig,
        ModelOperationConfig,
        ModelProtocolRequest,
        ModelProtocolResponse,
    )
    from omnibase_core.types import JsonType

@runtime_checkable
class ProtocolHandler(Protocol):
    """Request-response handler for external I/O operations.

    Implementations provide protocol-specific handling for HTTP, databases,
    message queues, and other external systems. Handlers manage connection
    pooling, retries, and resource lifecycle.
    """

    @property
    def handler_type(self) -> str:
        """The type of handler as a string identifier.

        Returns:
            Lowercase string identifier (e.g., "http", "postgresql", "kafka").
        """
        ...

    async def initialize(self, config: ModelConnectionConfig) -> None:
        """Initialize connection pool and resources.

        Args:
            config: Connection configuration including URL, auth, pool settings.

        Raises:
            HandlerInitializationError: If initialization fails.
        """
        ...

    async def shutdown(self, timeout_seconds: float = 30.0) -> None:
        """Release resources and close connections gracefully.

        Args:
            timeout_seconds: Maximum time to wait for shutdown. Defaults to 30.0.

        Raises:
            TimeoutError: If shutdown does not complete within timeout.
        """
        ...

    async def execute(
        self,
        request: ModelProtocolRequest,
        operation_config: ModelOperationConfig,
    ) -> ModelProtocolResponse:
        """Execute a protocol-specific operation.

        Args:
            request: Protocol-agnostic request model.
            operation_config: Operation-specific configuration.

        Returns:
            Protocol-agnostic response model.

        Raises:
            ProtocolHandlerError: If execution fails.
        """
        ...

    def describe(self) -> ModelHandlerDescriptor:
        """Return handler metadata and capabilities.

        Returns:
            Descriptor with handler_type, capabilities, and connection info.

        Raises:
            HandlerNotInitializedError: If called before initialize().
        """
        ...

    async def health_check(self) -> JsonType:
        """Check handler health and connectivity.

        Returns:
            Dictionary with 'healthy' (bool), 'latency_ms' (optional),
            and 'last_error' (optional) fields.

        Raises:
            HandlerNotInitializedError: If called before initialize().
        """
        ...


# Usage in an effect node with proper lifecycle management
class UserServiceEffectNode:
    """Effect node demonstrating handler lifecycle and usage."""

    def __init__(self, http_handler: ProtocolHandler) -> None:
        self._handler = http_handler
        self._config = ModelOperationConfig(timeout_seconds=30.0)

    async def start(self, connection_config: ModelConnectionConfig) -> None:
        """Initialize the handler before use."""
        await self._handler.initialize(connection_config)

    async def stop(self) -> None:
        """Shutdown the handler and release resources."""
        await self._handler.shutdown()

    async def fetch_user(self, user_id: str) -> User:
        """Fetch a user by ID from the external service.

        Args:
            user_id: The unique identifier of the user.

        Returns:
            User model populated from the API response.

        Raises:
            ProtocolHandlerError: If the API call fails.
        """
        request = ModelProtocolRequest(
            method="GET",
            path=f"/users/{user_id}",
        )
        response = await self._handler.execute(request, self._config)
        return User.model_validate(response.data)
```

### ProtocolEventBus Example

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import uuid4

from omnibase_spi.protocols.types.protocol_event_bus_types import ProtocolEventMessage

if TYPE_CHECKING:
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
    from omnibase_core.types import JsonType

@runtime_checkable
class ProtocolEventBusBase(Protocol):
    """Pub/sub event bus for async messaging.

    Provides envelope-based messaging with correlation ID tracking,
    consumer subscriptions, and health monitoring for cross-service
    communication.
    """

    async def publish(self, event: ProtocolEventMessage) -> None:
        """Publish a basic event message.

        Args:
            event: The event message to publish.

        Raises:
            SPIError: If publishing fails.
        """
        ...

    async def publish_envelope(
        self,
        envelope: ModelEventEnvelope,
        topic: str,
    ) -> None:
        """Publish envelope to topic (fire-and-forget).

        Args:
            envelope: The ONEX envelope with payload and metadata.
            topic: The Kafka topic or channel to publish to.

        Raises:
            SPIError: If publishing fails or topic is invalid.
        """
        ...

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[ModelEventEnvelope], Awaitable[None]],
    ) -> None:
        """Subscribe to topic with handler callback.

        Args:
            topic: The Kafka topic or channel to subscribe to.
            handler: Async callback receiving ModelEventEnvelope instances.

        Raises:
            SPIError: If subscription fails or topic is invalid.
        """
        ...

    async def start_consuming(self, timeout_seconds: float | None = None) -> None:
        """Start consuming from subscribed topics.

        Args:
            timeout_seconds: Maximum time to consume before returning.
                If None, runs indefinitely until stop_consuming() is called.

        Raises:
            SPIError: If consumer initialization fails.
        """
        ...

    async def stop_consuming(self, timeout_seconds: float = 30.0) -> None:
        """Stop consuming and gracefully shut down the consumer.

        Args:
            timeout_seconds: Maximum time to wait for shutdown. Defaults to 30.0.

        Raises:
            SPIError: If shutdown fails or times out.
        """
        ...

    async def health_check(self) -> JsonType:
        """Check broker connectivity and health status.

        Returns:
            Dictionary with 'healthy' (bool), 'latency_ms' (optional),
            and 'last_error' (optional) fields.

        Raises:
            SPIError: If health check cannot be performed.
        """
        ...


# Usage for event publishing
class OrderService:
    """Service demonstrating event publishing pattern."""

    def __init__(
        self,
        event_bus: ProtocolEventBusBase,
        repository: OrderRepository,
    ) -> None:
        self._bus = event_bus
        self._repository = repository

    async def create_order(self, order: Order) -> None:
        """Create an order and publish the event.

        Args:
            order: The order to create.
        """
        # Save order to database
        await self._repository.save(order)

        # Publish event (fire-and-forget)
        envelope = ModelEventEnvelope(
            event_type="omninode.orders.event.order_created.v1",
            payload=order.model_dump(),
            correlation_id=uuid4(),
        )
        await self._bus.publish_envelope(envelope, "orders.events")


# Usage for event consumption with lifecycle management
class InventoryService:
    """Service demonstrating event consumption with proper lifecycle."""

    def __init__(self, event_bus: ProtocolEventBusBase) -> None:
        self._bus = event_bus

    async def start(self) -> None:
        """Start consuming events from subscribed topics."""
        await self._bus.subscribe("orders.events", self._handle_order_event)
        await self._bus.start_consuming()

    async def stop(self) -> None:
        """Stop consuming and release resources."""
        await self._bus.stop_consuming()

    async def _handle_order_event(self, envelope: ModelEventEnvelope) -> None:
        """Handle incoming order events.

        Args:
            envelope: The event envelope containing order data.
        """
        if envelope.event_type == "omninode.orders.event.order_created.v1":
            await self._reserve_inventory(envelope.payload)
```

### Combined Usage Pattern

Many systems use both patterns together:

```python
class PaymentService:
    """Uses both handler (for payment gateway) and event bus (for notifications).

    Demonstrates combining request-response pattern (ProtocolHandler) for
    synchronous API calls with fire-and-forget pattern (ProtocolEventBus)
    for async event publishing.
    """

    def __init__(
        self,
        payment_handler: ProtocolHandler,  # Direct calls to payment gateway
        event_bus: ProtocolEventBusBase,   # Publish payment events
    ) -> None:
        self._handler = payment_handler
        self._bus = event_bus
        self._config = ModelOperationConfig(timeout_seconds=30.0)

    async def start(self, connection_config: ModelConnectionConfig) -> None:
        """Initialize the payment handler before processing payments.

        Args:
            connection_config: Configuration for the payment gateway connection.
        """
        await self._handler.initialize(connection_config)

    async def stop(self) -> None:
        """Shutdown the payment handler and release resources."""
        await self._handler.shutdown()

    async def process_payment(self, payment: Payment) -> PaymentResult:
        """Process a payment and publish the result event.

        Args:
            payment: The payment to process.

        Returns:
            PaymentResult with transaction details.

        Raises:
            ProtocolHandlerError: If the payment gateway call fails.
        """
        # 1. Call payment gateway via handler (need response)
        request = ModelProtocolRequest(
            method="POST",
            path="/charges",
            data=payment.model_dump(),
        )
        response = await self._handler.execute(request, self._config)
        result = PaymentResult.model_validate(response.data)

        # 2. Publish event via event bus (notify other services)
        envelope = ModelEventEnvelope(
            event_type="omninode.payments.event.payment_processed.v1",
            payload={"payment_id": payment.id, "status": result.status},
            correlation_id=payment.correlation_id,
        )
        await self._bus.publish_envelope(envelope, "payments.events")

        return result
```

## Cross-References

### ProtocolHandler

- **Definition**: ``handlers/protocol_handler.py`` (in the omnibase_spi repository)
- **Exports**: ``handlers/__init__.py`` (in the omnibase_spi repository)

### ProtocolEventBus

- **Base Protocol**: ``event_bus/protocol_event_bus_mixin.py`` (in the omnibase_spi repository)
- **Event Publisher**: ``event_bus/protocol_event_publisher.py`` (in the omnibase_spi repository)
- **DLQ Handler**: ``event_bus/protocol_dlq_handler.py`` (in the omnibase_spi repository)
- **Kafka Adapter**: ``event_bus/protocol_kafka_adapter.py`` (in the omnibase_spi repository)
- **Redpanda Adapter**: ``event_bus/protocol_redpanda_adapter.py`` (in the omnibase_spi repository)
- **Schema Registry**: ``event_bus/protocol_schema_registry.py`` (in the omnibase_spi repository)
- **Exports**: ``event_bus/__init__.py`` (in the omnibase_spi repository)

### Related Protocols

| Protocol | Location | Purpose |
|----------|----------|---------|
| `ProtocolEventEnvelope` | `event_bus/` | Envelope wrapper for events |
| `ProtocolEventBusProvider` | `event_bus/` | Factory for event bus instances |
| `ProtocolDLQHandler` | `event_bus/` | Dead letter queue management |
| `ProtocolSchemaRegistry` | `event_bus/` | Schema validation for events |

## Decision Flowchart

```
Need external communication?
          |
          v
    Need response? ----YES----> Use ProtocolHandler
          |
          NO
          |
          v
    Fire-and-forget? --YES----> Use ProtocolEventBus
          |
          NO
          |
          v
    Use both patterns
```

## Summary

- **ProtocolHandler**: Use for direct, request-response I/O where you need a result
- **ProtocolEventBus**: Use for decoupled, async messaging where services should not block
- **Combined**: Many real-world systems use both - handlers for external APIs, event bus for internal coordination
