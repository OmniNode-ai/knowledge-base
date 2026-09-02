---
type: guide
status: current
date: "2026-09-02"
title: "Circuit Breaker Implementation Guide"
topics: [omnibase-infra, circuit, breaker, implementation]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/circuit_breaker_implementation.md on 2026-09-02. -->

# Circuit Breaker Implementation Guide

## Overview

Circuit breakers prevent cascading failures in distributed systems by detecting failures and stopping requests to unhealthy services. This guide provides a complete, production-ready implementation for ONEX infrastructure.

## Circuit Breaker States

The circuit breaker operates in three states:

### ASCII Diagram

```
┌─────────┐
│ CLOSED  │ ─── failures >= threshold ──→ ┌──────┐
└─────────┘                                │ OPEN │
     ↑                                     └──────┘
     │                                        │
     │                                        │ timeout elapsed
     │                                        ↓
     │                                   ┌───────────┐
     └── successes >= threshold ──────  │ HALF_OPEN │
                                         └───────────┘
```

### Mermaid Diagram

```mermaid
stateDiagram-v2
    accTitle: Circuit Breaker State Machine
    accDescr: State diagram showing circuit breaker transitions between three states. CLOSED is normal operation where requests pass through. When failures reach the threshold, it transitions to OPEN which rejects all requests immediately. After a timeout period, it moves to HALF_OPEN which allows limited test requests. Successful tests transition back to CLOSED, while any failure returns to OPEN.

    [*] --> CLOSED

    CLOSED --> OPEN : failures >= threshold
    OPEN --> HALF_OPEN : timeout elapsed
    HALF_OPEN --> CLOSED : successes >= threshold
    HALF_OPEN --> OPEN : any failure

    note right of CLOSED : Normal operation\nRequests allowed
    note right of OPEN : Failing state\nRequests rejected
    note right of HALF_OPEN : Testing recovery\nLimited requests
```

### State Descriptions

| State | Behavior | Transitions |
|-------|----------|-------------|
| **CLOSED** | Normal operation, requests allowed | → OPEN when failures >= threshold |
| **OPEN** | Failing state, requests rejected immediately | → HALF_OPEN after timeout |
| **HALF_OPEN** | Testing recovery, limited requests allowed | → CLOSED on success threshold<br>→ OPEN on any failure |

## Complete Implementation

### State Machine

```python
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, TypeVar, Generic
from omnibase_infra.errors import InfraUnavailableError
import asyncio

T = TypeVar("T")

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery
```

### Configuration

```python
@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration.

    Attributes:
        failure_threshold: Consecutive failures before opening circuit
        success_threshold: Consecutive successes to close from half-open
        timeout: Duration to wait before attempting half-open
        half_open_max_calls: Maximum concurrent calls in half-open state
    """
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: timedelta = timedelta(seconds=60)
    half_open_max_calls: int = 1  # Limit concurrent half-open tests
```

### Core Implementation

```python
@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker operational metrics."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_transitions: dict[str, int] = field(default_factory=dict)
    last_failure_time: datetime | None = None
    last_state_change: datetime = field(default_factory=datetime.utcnow)

class CircuitBreaker(Generic[T]):
    """Production-ready circuit breaker implementation.

    Prevents cascading failures by tracking service health and
    rejecting requests to unhealthy services.

    Example:
        >>> breaker = CircuitBreaker(
        ...     name="kafka-publisher",
        ...     config=CircuitBreakerConfig(failure_threshold=5)
        ... )
        >>> result = await breaker.call(publish_message)
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig,
    ):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.metrics = CircuitBreakerMetrics()
        self._lock = asyncio.Lock()
        self._half_open_calls = 0

    def _should_attempt_call(self) -> bool:
        """Determine if call should be attempted based on state.

        Returns:
            True if call should proceed, False to reject
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if (self.metrics.last_failure_time and
                datetime.utcnow() - self.metrics.last_failure_time >= self.config.timeout):
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False

        # HALF_OPEN: Allow limited concurrent calls
        return self._half_open_calls < self.config.half_open_max_calls

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state with metrics tracking.

        Args:
            new_state: Target state
        """
        old_state = self.state
        self.state = new_state
        self.metrics.last_state_change = datetime.utcnow()

        # Track state transitions
        transition_key = f"{old_state.value}_to_{new_state.value}"
        self.metrics.state_transitions[transition_key] = (
            self.metrics.state_transitions.get(transition_key, 0) + 1
        )

        # Reset counters on state change
        if new_state == CircuitState.HALF_OPEN:
            self.success_count = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0

    def _record_success(self) -> None:
        """Record successful operation and update state."""
        self.metrics.total_calls += 1
        self.metrics.successful_calls += 1

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def _record_failure(self) -> None:
        """Record failed operation and update state."""
        self.metrics.total_calls += 1
        self.metrics.failed_calls += 1
        self.metrics.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open immediately reopens circuit
            self._transition_to(CircuitState.OPEN)
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    async def call(self, operation: Callable[[], T]) -> T:
        """Execute operation with circuit breaker protection.

        Args:
            operation: Async callable to protect

        Returns:
            Operation result

        Raises:
            InfraUnavailableError: Circuit is open, service unavailable
            Exception: From operation execution
        """
        async with self._lock:
            if not self._should_attempt_call():
                self.metrics.rejected_calls += 1
                raise InfraUnavailableError(
                    f"Circuit breaker '{self.name}' is {self.state.value.upper()}, "
                    f"rejecting call"
                )

            if self.state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1

        try:
            result = await operation()
            async with self._lock:
                self._record_success()
                if self.state == CircuitState.HALF_OPEN:
                    self._half_open_calls -= 1
            return result
        except Exception as e:
            async with self._lock:
                self._record_failure()
                if self.state == CircuitState.HALF_OPEN:
                    self._half_open_calls -= 1
            raise

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current circuit breaker metrics.

        Returns:
            Current metrics snapshot
        """
        return self.metrics

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state.

        Use with caution - typically for administrative intervention.
        """
        self._transition_to(CircuitState.CLOSED)
        self.failure_count = 0
        self.success_count = 0
```

## Usage Examples

### Database Connection Protection

```python
from omnibase_infra.errors import InfraConnectionError, ModelInfraErrorContext
from omnibase_infra.enums import EnumInfraTransportType
from uuid import UUID

# Initialize circuit breaker for database
db_circuit_breaker = CircuitBreaker(
    name="postgresql-primary",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout=timedelta(seconds=30),
    )
)

async def query_database(
    query: str,
    correlation_id: UUID,
) -> list[dict[str, object]]:
    """Execute database query with circuit breaker protection."""

    async def _execute_query() -> list[dict[str, object]]:
        try:
            conn = await asyncpg.connect(
                host=config.db_host,
                port=config.db_port,
            )
            results = await conn.fetch(query)
            return [dict(row) for row in results]
        except asyncpg.PostgresConnectionError as e:
            context = ModelInfraErrorContext(
                transport_type=EnumInfraTransportType.DATABASE,
                operation="execute_query",
                target_name="postgresql-primary",
                correlation_id=correlation_id,
            )
            raise InfraConnectionError(
                "Database connection failed",
                context=context
            ) from e

    return await db_circuit_breaker.call(_execute_query)
```

### Kafka Publisher Protection

```python
from kafka.errors import KafkaConnectionError
from omnibase_infra.errors import InfraUnavailableError, ModelInfraErrorContext
from omnibase_infra.enums import EnumInfraTransportType

# Circuit breaker per Kafka topic
kafka_circuit_breakers: dict[str, CircuitBreaker] = {}

def get_topic_circuit_breaker(topic: str) -> CircuitBreaker:
    """Get or create circuit breaker for Kafka topic."""
    if topic not in kafka_circuit_breakers:
        kafka_circuit_breakers[topic] = CircuitBreaker(
            name=f"kafka-topic-{topic}",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout=timedelta(seconds=20),
            )
        )
    return kafka_circuit_breakers[topic]

async def publish_message(
    topic: str,
    message: bytes,
    correlation_id: UUID,
) -> None:
    """Publish Kafka message with circuit breaker protection."""

    breaker = get_topic_circuit_breaker(topic)

    async def _publish() -> None:
        try:
            await kafka_producer.send(topic, message)
        except KafkaConnectionError as e:
            context = ModelInfraErrorContext(
                transport_type=EnumInfraTransportType.KAFKA,
                operation="publish_message",
                target_name=f"kafka-topic-{topic}",
                correlation_id=correlation_id,
            )
            raise InfraUnavailableError(
                f"Kafka broker unavailable for topic {topic}",
                context=context
            ) from e

    await breaker.call(_publish)
```

### HTTP API Protection

```python
import httpx
from omnibase_infra.errors import InfraConnectionError, ModelInfraErrorContext
from omnibase_infra.enums import EnumInfraTransportType

# Circuit breaker for external API
api_circuit_breaker = CircuitBreaker(
    name="external-api",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=3,
        timeout=timedelta(minutes=2),
        half_open_max_calls=2,  # Allow 2 test calls in half-open
    )
)

async def call_external_api(
    endpoint: str,
    correlation_id: UUID,
) -> dict[str, object]:
    """Call external API with circuit breaker protection."""

    async def _api_call() -> dict[str, object]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.example.com/{endpoint}",
                    timeout=10.0,
                )
                response.raise_for_status()
                return response.json()
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            context = ModelInfraErrorContext(
                transport_type=EnumInfraTransportType.HTTP,
                operation="api_call",
                target_name="external-api",
                correlation_id=correlation_id,
            )
            raise InfraConnectionError(
                "External API unavailable",
                context=context
            ) from e

    return await api_circuit_breaker.call(_api_call)
```

## Monitoring and Metrics

### Metrics Collection

```python
from prometheus_client import Counter, Gauge, Histogram

# Circuit breaker metrics
circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Current circuit breaker state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)",
    ["name"],
)

circuit_breaker_calls = Counter(
    "circuit_breaker_calls_total",
    "Total circuit breaker calls",
    ["name", "result"],  # result: success, failure, rejected
)

circuit_breaker_transitions = Counter(
    "circuit_breaker_transitions_total",
    "Circuit breaker state transitions",
    ["name", "from_state", "to_state"],
)

def update_circuit_breaker_metrics(breaker: CircuitBreaker) -> None:
    """Update Prometheus metrics from circuit breaker."""
    # State gauge
    state_value = {
        CircuitState.CLOSED: 0,
        CircuitState.HALF_OPEN: 1,
        CircuitState.OPEN: 2,
    }[breaker.state]
    circuit_breaker_state.labels(name=breaker.name).set(state_value)

    # Metrics
    metrics = breaker.get_metrics()
    circuit_breaker_calls.labels(name=breaker.name, result="success").inc(
        metrics.successful_calls
    )
    circuit_breaker_calls.labels(name=breaker.name, result="failure").inc(
        metrics.failed_calls
    )
    circuit_breaker_calls.labels(name=breaker.name, result="rejected").inc(
        metrics.rejected_calls
    )
```

### Health Checks

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health/circuit-breakers")
async def circuit_breaker_health() -> dict[str, object]:
    """Report circuit breaker health status."""
    status = {}

    for topic, breaker in kafka_circuit_breakers.items():
        metrics = breaker.get_metrics()
        status[topic] = {
            "state": breaker.state.value,
            "failure_count": breaker.failure_count,
            "success_count": breaker.success_count,
            "total_calls": metrics.total_calls,
            "rejected_calls": metrics.rejected_calls,
            "last_state_change": metrics.last_state_change.isoformat(),
        }

    return status
```

## Best Practices

### Configuration Tuning

| Service Type | Failure Threshold | Success Threshold | Timeout |
|--------------|------------------|------------------|---------|
| Database | 5 | 2 | 30s |
| Message Broker | 3 | 2 | 20s |
| Internal API | 5 | 3 | 60s |
| External API | 10 | 5 | 2-5min |

### DO

✅ **Per-service breakers**: One circuit breaker per dependency
✅ **Monitor state changes**: Alert on OPEN state
✅ **Tune thresholds**: Adjust based on service characteristics
✅ **Combine with retries**: Exponential backoff before circuit breaker
✅ **Track metrics**: Monitor success/failure rates

### DON'T

❌ **Share breakers**: Don't use same breaker for different services
❌ **Set timeout too short**: Allow time for recovery
❌ **Ignore HALF_OPEN**: Critical for testing recovery
❌ **Open manually**: Let state machine handle transitions
❌ **Skip monitoring**: Circuit state changes indicate problems

## Related Patterns

- Error Recovery Patterns (internal knowledge base) - Comprehensive recovery strategies
- Error Handling Patterns (internal knowledge base) - Error classification and context
- Correlation ID Tracking (`../architecture/omnibase-infra-correlation-id-tracking.md`) - Request tracing
