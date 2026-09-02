---
type: architecture
status: accepted
date: "2026-09-02"
title: "Correlation ID Tracking"
topics: [omnibase-infra, correlation, id, tracking]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/correlation_id_tracking.md on 2026-09-02. -->

# Correlation ID Tracking

## Overview

Correlation IDs enable distributed request tracing across services, making debugging and observability significantly easier in microservice architectures. This document describes the ONEX infrastructure approach to correlation ID management.

## Purpose

Correlation IDs serve multiple critical functions:

1. **Distributed Tracing** - Track requests across multiple services
2. **Error Context** - Link errors to originating requests
3. **Performance Analysis** - Measure end-to-end latency
4. **Debugging** - Follow request flow through system
5. **Audit Trails** - Track who did what and when

## Type Safety

**CRITICAL**: Correlation IDs must remain as `UUID` objects throughout the system to maintain strong typing.

```python
from uuid import UUID, uuid4

# ✅ CORRECT - UUID type preserved
correlation_id: UUID = uuid4()

# ❌ WRONG - loses type safety
correlation_id: str = str(uuid4())
```

## Correlation ID Flow

### Request Envelope Pattern

All ONEX messages use envelope pattern with embedded correlation ID:

```python
from omnibase_core.models import ModelEventEnvelope
from uuid import UUID, uuid4

@dataclass
class ModelEventEnvelope:
    """Standard event envelope."""

    correlation_id: UUID
    event_type: str
    timestamp: datetime
    payload: dict[str, object]  # Event data (use specific type in production)
    source_service: str
    target_service: str | None = None

# Create envelope with new correlation ID
envelope = ModelEventEnvelope(
    correlation_id=uuid4(),
    event_type="user.created",
    timestamp=datetime.utcnow(),
    payload=user_data,
    source_service="user-service",
)
```

### Propagation Rules

1. **New Requests**: Generate new correlation ID at entry point
2. **Downstream Calls**: Preserve correlation ID from incoming request
3. **Async Operations**: Pass correlation ID to background tasks
4. **External APIs**: Include in headers/metadata

## Implementation Patterns

### HTTP Request Handling

```python
from fastapi import Request, HTTPException
from uuid import UUID, uuid4

async def extract_correlation_id(request: Request) -> UUID:
    """Extract correlation ID from HTTP request headers.

    Checks X-Correlation-ID header, generates new UUID if not present.
    """
    correlation_header = request.headers.get("X-Correlation-ID")

    if correlation_header:
        try:
            return UUID(correlation_header)
        except ValueError:
            # Invalid UUID format, generate new one
            pass

    return uuid4()

# FastAPI endpoint
@app.post("/users")
async def create_user(request: Request, user_data: dict[str, str]):
    correlation_id = await extract_correlation_id(request)

    try:
        result = await user_service.create_user(
            data=user_data,
            correlation_id=correlation_id,
        )
        return result
    except InfraConnectionError as e:
        # Error context includes correlation ID automatically
        raise HTTPException(status_code=503, detail=str(e))
```

### Kafka Message Handling

```python
from omnibase_core.models import ModelEventEnvelope
from omnibase_infra.errors import InfraConnectionError, ModelInfraErrorContext
from omnibase_infra.enums import EnumInfraTransportType
from uuid import UUID

async def process_kafka_message(message_bytes: bytes) -> None:
    """Process Kafka message with correlation tracking."""

    # Deserialize envelope
    envelope = ModelEventEnvelope.model_validate_json(message_bytes)

    # Extract correlation ID from envelope
    correlation_id: UUID = envelope.correlation_id

    try:
        # Process with correlation context
        await process_event(
            event=envelope.payload,
            correlation_id=correlation_id,
        )
    except Exception as e:
        context = ModelInfraErrorContext(
            transport_type=EnumInfraTransportType.KAFKA,
            operation="process_message",
            target_name=f"topic-{envelope.event_type}",
            correlation_id=correlation_id,  # Preserved for error tracking
        )
        raise InfraConnectionError(
            "Message processing failed",
            context=context
        ) from e
```

### Database Operations

```python
from uuid import UUID
from omnibase_infra.errors import InfraConnectionError, ModelInfraErrorContext
from omnibase_infra.enums import EnumInfraTransportType

async def execute_transaction(
    operations: list[str],
    correlation_id: UUID,
) -> None:
    """Execute database transaction with correlation tracking.

    Args:
        operations: SQL statements to execute
        correlation_id: Request correlation ID
    """
    async with db.transaction():
        try:
            for operation in operations:
                await db.execute(operation)
        except asyncpg.PostgresError as e:
            context = ModelInfraErrorContext(
                transport_type=EnumInfraTransportType.DATABASE,
                operation="execute_transaction",
                target_name="postgresql-primary",
                correlation_id=correlation_id,
            )
            raise InfraConnectionError(
                "Transaction failed",
                context=context
            ) from e
```

### Background Tasks

```python
import asyncio
from uuid import UUID

async def schedule_background_task(
    task_fn: Callable,
    correlation_id: UUID,
) -> None:
    """Schedule background task with correlation context.

    Args:
        task_fn: Async task function
        correlation_id: Request correlation ID to propagate
    """
    # Propagate correlation ID to background task
    asyncio.create_task(
        task_fn(correlation_id=correlation_id)
    )

async def send_notification_email(
    user_id: str,
    correlation_id: UUID,
) -> None:
    """Background task with correlation tracking."""
    try:
        # Task has access to originating request's correlation ID
        await email_service.send(
            user_id=user_id,
            correlation_id=correlation_id,
        )
    except Exception as e:
        # Log with correlation context
        logger.error(
            "Email notification failed",
            extra={
                "user_id": user_id,
                "correlation_id": correlation_id,
                "error": str(e),
            }
        )
```

## Logging Integration

### Structured Logging with Correlation ID

```python
import structlog
from uuid import UUID

# Configure structured logger
logger = structlog.get_logger()

async def process_request(
    request_data: dict[str, object],
    correlation_id: UUID,
) -> None:
    """Process request with correlation logging."""

    # Bind correlation ID to logger context
    log = logger.bind(correlation_id=correlation_id)

    log.info("Processing request", request_data=request_data)

    try:
        result = await perform_operation(request_data, correlation_id)
        log.info("Request completed", result=result)
    except Exception as e:
        log.error("Request failed", error=str(e), exc_info=True)
        raise
```

### Log Aggregation Query

With correlation IDs in logs, you can trace entire request flows:

```bash
# Find all logs for specific request
grep "correlation_id=550e8400-e29b-41d4-a716-446655440000" app.log

# In structured logging systems (e.g., Elasticsearch)
{
  "query": {
    "term": {
      "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  }
}
```

## Error Context Integration

Correlation IDs are automatically included in all infrastructure errors:

```python
from omnibase_infra.errors import InfraConnectionError, ModelInfraErrorContext
from omnibase_infra.enums import EnumInfraTransportType
from uuid import UUID

def raise_connection_error(correlation_id: UUID) -> None:
    """Example error with correlation context."""
    context = ModelInfraErrorContext(
        transport_type=EnumInfraTransportType.KAFKA,
        operation="publish_message",
        target_name="kafka-broker-1",
        correlation_id=correlation_id,  # ✅ UUID type preserved
    )
    raise InfraConnectionError("Connection failed", context=context)
```

## Service Mesh Integration

### Envoy/Istio Headers

```python
from fastapi import Request
from uuid import UUID, uuid4

async def extract_trace_headers(request: Request) -> UUID:
    """Extract correlation ID from service mesh headers.

    Checks multiple header variants:
    - X-Correlation-ID (custom)
    - X-Request-ID (Envoy/Istio)
    - X-B3-TraceId (Zipkin)
    """
    headers_to_check = [
        "X-Correlation-ID",
        "X-Request-ID",
        "X-B3-TraceId",
    ]

    for header in headers_to_check:
        value = request.headers.get(header)
        if value:
            try:
                # Zipkin trace IDs may be 16 or 32 hex chars
                if len(value) == 32:
                    return UUID(value)
                elif len(value) == 16:
                    # Pad to full UUID
                    return UUID(value.zfill(32))
            except ValueError:
                continue

    # No valid correlation ID found, generate new
    return uuid4()
```

## Best Practices

### DO

✅ **Generate at entry points**: Create correlation ID when request enters system
✅ **Preserve type safety**: Keep as `UUID` object throughout
✅ **Include in all errors**: Add to `ModelInfraErrorContext`
✅ **Propagate to downstream**: Pass to all called services
✅ **Log with context**: Include in structured logs
✅ **Return to client**: Include in HTTP response headers

### DON'T

❌ **Convert to string prematurely**: Loses type safety
❌ **Generate multiple IDs**: One request = one correlation ID
❌ **Skip background tasks**: Propagate to async operations
❌ **Expose in user-facing errors**: Internal tracking only
❌ **Use for authorization**: Not a security token

## Observability Integration

### Metrics with Correlation

```python
from prometheus_client import Histogram
from uuid import UUID

request_duration = Histogram(
    "request_duration_seconds",
    "Request duration in seconds",
    ["endpoint", "status"],
)

async def tracked_request(
    endpoint: str,
    correlation_id: UUID,
) -> None:
    """Execute request with metrics tracking."""
    with request_duration.labels(endpoint=endpoint, status="success").time():
        try:
            await process_request(endpoint, correlation_id)
        except Exception as e:
            request_duration.labels(endpoint=endpoint, status="error").observe(0)
            logger.error(
                "Request failed",
                extra={
                    "endpoint": endpoint,
                    "correlation_id": correlation_id,
                    "error": str(e),
                }
            )
            raise
```

### Distributed Tracing (OpenTelemetry)

```python
from opentelemetry import trace
from uuid import UUID

tracer = trace.get_tracer(__name__)

async def traced_operation(
    operation_name: str,
    correlation_id: UUID,
) -> None:
    """Execute operation with distributed tracing."""
    with tracer.start_as_current_span(operation_name) as span:
        # Add correlation ID as span attribute
        span.set_attribute("correlation_id", str(correlation_id))

        await perform_operation(correlation_id)
```

## Related Patterns

- Error Handling Patterns (internal knowledge base) - Error context with correlation IDs
- Error Recovery Patterns (internal knowledge base) - Retry logic with correlation tracking
- Container Dependency Injection (`../architecture/omnibase-infra-container-dependency-injection.md`) - Service resolution patterns
