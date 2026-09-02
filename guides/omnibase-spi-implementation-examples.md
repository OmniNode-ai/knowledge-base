---
type: guide
status: current
date: "2026-09-01"
title: "omnibase_spi Implementation Examples"
topics:
  - omnibase_spi
  - examples
  - protocols
  - omnibase_infra
refs: []
---

<!-- Migrated from omnibase_spi:docs/examples/IMPLEMENTATION-EXAMPLES.md on 2026-09-01 -->

# Protocol Implementation Examples

This guide shows how to implement ONEX SPI protocols in `omnibase_infra`. These examples demonstrate the contract that implementations must satisfy.

> **Architecture Note**: SPI protocols define interfaces; implementations live in `omnibase_infra` and must import models from `omnibase_core`.

## Table of Contents

- [Implementing ProtocolEventBusProvider](#implementing-protocoleventbusprovider)
- [Implementing ProtocolComputeNode](#implementing-protocolcomputenode)
- [Implementing ProtocolHandler](#implementing-protocolhandler)
- [Implementation Checklist](#implementation-checklist)

---

## Implementing ProtocolEventBusProvider

**Protocol Location**: `omnibase_spi.protocols.event_bus.protocol_event_bus_provider`

The `ProtocolEventBusProvider` is a factory pattern for creating and managing event bus instances. Implementations must handle connection pooling, environment isolation, and graceful shutdown.

### Protocol Contract

```python
from typing import Protocol, runtime_checkable
from omnibase_spi.protocols.event_bus.protocol_event_bus_mixin import ProtocolEventBusBase

@runtime_checkable
class ProtocolEventBusProvider(Protocol):
    """Provider interface for obtaining event bus instances."""

    async def get_event_bus(
        self,
        environment: str | None = None,
        group: str | None = None,
    ) -> ProtocolEventBusBase:
        """Get or create an event bus instance (may return cached)."""
        ...

    async def create_event_bus(
        self,
        environment: str,
        group: str,
        config: dict[str, object] | None = None,
    ) -> ProtocolEventBusBase:
        """Create a new event bus instance (no caching)."""
        ...

    async def close_all(self) -> None:
        """Close all managed event bus instances."""
        ...

    @property
    def default_environment(self) -> str:
        """Get the default environment."""
        ...

    @property
    def default_group(self) -> str:
        """Get the default consumer group."""
        ...
```

### Minimal Implementation

```python
# omnibase_infra/event_bus/in_memory_provider.py
"""In-memory event bus provider for testing and development."""

from omnibase_spi.protocols.event_bus import (
    ProtocolEventBusBase,
    ProtocolEventBusProvider,
)


class InMemoryEventBusProvider:
    """Simple in-memory provider for testing.

    Implements ProtocolEventBusProvider for local development
    and unit testing scenarios.
    """

    def __init__(
        self,
        default_environment: str = "local",
        default_group: str = "default",
    ) -> None:
        self._default_environment = default_environment
        self._default_group = default_group
        self._bus: InMemoryEventBus | None = None

    async def get_event_bus(
        self,
        environment: str | None = None,
        group: str | None = None,
    ) -> ProtocolEventBusBase:
        """Return the shared in-memory bus instance."""
        if self._bus is None:
            self._bus = InMemoryEventBus()
        return self._bus

    async def create_event_bus(
        self,
        environment: str,
        group: str,
        config: dict[str, object] | None = None,
    ) -> ProtocolEventBusBase:
        """Create a fresh in-memory bus (no caching)."""
        return InMemoryEventBus()

    async def close_all(self) -> None:
        """Clear the cached bus."""
        self._bus = None

    @property
    def default_environment(self) -> str:
        return self._default_environment

    @property
    def default_group(self) -> str:
        return self._default_group


# Verify protocol compliance at module load
assert isinstance(InMemoryEventBusProvider(), ProtocolEventBusProvider)
```

### Full Implementation with Caching

```python
# omnibase_infra/event_bus/kafka_provider.py
"""Kafka event bus provider for production use."""

import asyncio
import logging
from typing import TYPE_CHECKING

from omnibase_spi.protocols.event_bus import (
    ProtocolEventBusBase,
    ProtocolEventBusProvider,
)
from omnibase_spi.exceptions import (
    HandlerInitializationError,
    InvalidProtocolStateError,
)

if TYPE_CHECKING:
    from omnibase_core.models.event_bus import ModelEventBusConfig

logger = logging.getLogger(__name__)


class KafkaEventBusProvider:
    """Production Kafka/Redpanda event bus provider.

    Implements ProtocolEventBusProvider with:
    - Connection pooling per environment/group
    - Graceful shutdown with flush
    - Configuration validation
    - Health checking
    """

    def __init__(
        self,
        bootstrap_servers: list[str],
        default_environment: str = "dev",
        default_group: str = "default-consumer",
        connection_timeout_ms: int = 30000,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._default_environment = default_environment
        self._default_group = default_group
        self._connection_timeout_ms = connection_timeout_ms

        # Cache: (environment, group) -> event_bus
        self._cache: dict[tuple[str, str], ProtocolEventBusBase] = {}
        self._lock = asyncio.Lock()

    async def get_event_bus(
        self,
        environment: str | None = None,
        group: str | None = None,
    ) -> ProtocolEventBusBase:
        """Get or create a cached event bus instance.

        Thread-safe caching ensures only one connection per
        environment/group combination.

        Args:
            environment: Environment identifier. Defaults to default_environment.
            group: Consumer group. Defaults to default_group.

        Returns:
            Cached or newly created event bus.

        Raises:
            HandlerInitializationError: If connection fails.
        """
        env = environment or self._default_environment
        grp = group or self._default_group
        cache_key = (env, grp)

        async with self._lock:
            if cache_key not in self._cache:
                logger.info(
                    "Creating new event bus",
                    extra={"environment": env, "group": grp},
                )
                self._cache[cache_key] = await self._create_bus(env, grp, None)

            return self._cache[cache_key]

    async def create_event_bus(
        self,
        environment: str,
        group: str,
        config: dict[str, object] | None = None,
    ) -> ProtocolEventBusBase:
        """Create a new event bus instance without caching.

        Useful for isolated test scenarios or when you need
        independent consumer groups.

        Args:
            environment: Environment identifier.
            group: Consumer group identifier.
            config: Optional configuration overrides.

        Returns:
            New event bus instance.

        Raises:
            HandlerInitializationError: If connection fails.
            ValueError: If environment or group is empty.
        """
        if not environment:
            raise ValueError("environment cannot be empty")
        if not group:
            raise ValueError("group cannot be empty")

        return await self._create_bus(environment, group, config)

    async def _create_bus(
        self,
        environment: str,
        group: str,
        config: dict[str, object] | None,
    ) -> ProtocolEventBusBase:
        """Internal: Create and connect a Kafka event bus."""
        try:
            # Build Kafka configuration
            kafka_config = {
                "bootstrap.servers": ",".join(self._bootstrap_servers),
                "group.id": f"{environment}-{group}",
                "client.id": f"onex-{environment}-{group}",
                "socket.timeout.ms": self._connection_timeout_ms,
                **(config or {}),
            }

            bus = KafkaEventBus(kafka_config)
            await bus.connect()
            return bus

        except ConnectionError as e:
            # Translate to SPI error; original error preserved via chaining
            raise HandlerInitializationError(
                "Failed to connect to Kafka"
            ) from e

    async def close_all(self) -> None:
        """Close all managed event bus instances.

        Flushes pending messages and closes connections gracefully.
        Safe to call multiple times.
        """
        async with self._lock:
            for cache_key, bus in self._cache.items():
                env, grp = cache_key
                logger.info(
                    "Closing event bus",
                    extra={"environment": env, "group": grp},
                )
                try:
                    await bus.flush()
                    await bus.close()
                except Exception as e:
                    logger.warning(
                        "Error closing event bus",
                        extra={"environment": env, "group": grp, "error": str(e)},
                    )

            self._cache.clear()
            logger.info("All event buses closed")

    @property
    def default_environment(self) -> str:
        return self._default_environment

    @property
    def default_group(self) -> str:
        return self._default_group


# Verify protocol compliance at module load
assert isinstance(
    KafkaEventBusProvider(bootstrap_servers=["localhost:9092"]),
    ProtocolEventBusProvider,
)
```

### Usage Example

```python
# Application startup
from omnibase_infra.event_bus import KafkaEventBusProvider

provider = KafkaEventBusProvider(
    bootstrap_servers=["kafka-1:9092", "kafka-2:9092"],
    default_environment="prod",
    default_group="order-service",
)

# Get event bus (cached)
bus = await provider.get_event_bus(environment="prod", group="order-service")
await bus.publish(event)

# Create isolated bus for testing
test_bus = await provider.create_event_bus(
    environment="test",
    group="test-consumer",
    config={"auto.offset.reset": "earliest"},
)

# Shutdown
await provider.close_all()
```

---

## Implementing ProtocolComputeNode

**Protocol Location**: `omnibase_spi.protocols.nodes.compute`

Compute nodes perform pure, deterministic transformations. They must not have side effects and should produce the same output for the same input.

### Protocol Contract

```python
from typing import Protocol, runtime_checkable
from omnibase_spi.protocols.nodes.base import ProtocolNode
from omnibase_core.models.compute import ModelComputeInput, ModelComputeOutput

@runtime_checkable
class ProtocolComputeNode(ProtocolNode, Protocol):
    """Protocol for pure compute nodes."""

    async def execute(
        self,
        input_data: ModelComputeInput,
    ) -> ModelComputeOutput:
        """Execute pure computation."""
        ...

    @property
    def is_deterministic(self) -> bool:
        """Whether the node produces deterministic output."""
        ...
```

The base `ProtocolNode` requires:

```python
@runtime_checkable
class ProtocolNode(Protocol):
    """Base protocol for all nodes."""

    @property
    def node_id(self) -> str:
        """Globally unique node identifier (e.g., 'vectorization.v1')."""
        ...

    @property
    def node_type(self) -> str:
        """Node type: 'compute', 'effect', 'reducer', 'orchestrator'."""
        ...

    @property
    def version(self) -> str:
        """Semantic version of this node implementation."""
        ...
```

### Minimal Implementation

```python
# omnibase_infra/nodes/compute/json_transform_node.py
"""JSON transformation compute node."""

from typing import TYPE_CHECKING

from omnibase_spi.protocols.nodes import ProtocolComputeNode

if TYPE_CHECKING:
    from omnibase_core.models.compute import ModelComputeInput, ModelComputeOutput


class JsonTransformNode:
    """Simple JSON transformation node.

    Implements ProtocolComputeNode for basic JSON transformations.
    Pure and deterministic - same input always produces same output.
    """

    @property
    def node_id(self) -> str:
        return "json-transform.v1"

    @property
    def node_type(self) -> str:
        return "compute"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def is_deterministic(self) -> bool:
        return True

    async def execute(
        self,
        input_data: "ModelComputeInput",
    ) -> "ModelComputeOutput":
        """Transform JSON according to mapping rules."""
        from omnibase_core.models.compute import ModelComputeOutput

        # Extract transformation rules and data
        rules = input_data.parameters.get("rules", {})
        data = input_data.data

        # Apply transformations (pure function)
        result = self._apply_rules(data, rules)

        return ModelComputeOutput(
            node_id=self.node_id,
            data=result,
            metadata={"rules_applied": len(rules)},
        )

    def _apply_rules(
        self,
        data: dict,
        rules: dict,
    ) -> dict:
        """Apply transformation rules to data (pure function)."""
        result = {}
        for target_key, source_path in rules.items():
            value = self._get_nested(data, source_path)
            result[target_key] = value
        return result

    def _get_nested(self, data: dict, path: str) -> object:
        """Get nested value from dict using dot notation."""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value


# Verify protocol compliance
assert isinstance(JsonTransformNode(), ProtocolComputeNode)
```

### Full Implementation with Validation

```python
# omnibase_infra/nodes/compute/vectorization_node.py
"""Text vectorization compute node for embedding generation."""

import hashlib
import logging
from typing import TYPE_CHECKING

from omnibase_spi.protocols.nodes import ProtocolComputeNode
from omnibase_spi.exceptions import SPIError

if TYPE_CHECKING:
    from omnibase_core.models.compute import ModelComputeInput, ModelComputeOutput

logger = logging.getLogger(__name__)


class VectorizationNode:
    """Text vectorization node for generating embeddings.

    Implements ProtocolComputeNode with:
    - Input validation
    - Deterministic hashing for cache keys
    - Comprehensive error handling
    - Execution metrics

    Note: This node wraps an embedding model but remains
    deterministic because the same text always produces
    the same embedding vector.
    """

    def __init__(
        self,
        model_name: str = "text-embedding-ada-002",
        dimensions: int = 1536,
    ) -> None:
        self._model_name = model_name
        self._dimensions = dimensions
        self._node_id = f"vectorization.{model_name}.v1"

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def node_type(self) -> str:
        return "compute"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def is_deterministic(self) -> bool:
        """Embedding models produce deterministic output."""
        return True

    async def execute(
        self,
        input_data: "ModelComputeInput",
    ) -> "ModelComputeOutput":
        """Generate embeddings for input text.

        Args:
            input_data: Must contain 'text' or 'texts' in data.

        Returns:
            ModelComputeOutput with embedding vectors.

        Raises:
            SPIError: If input validation fails or computation errors.
        """
        from omnibase_core.models.compute import ModelComputeOutput

        # Validate input
        texts = self._extract_texts(input_data)
        if not texts:
            raise SPIError(
                "Input must contain 'text' (str) or 'texts' (list[str])"
            )

        # Generate cache key for determinism verification
        cache_key = self._compute_cache_key(texts)

        try:
            # Generate embeddings (pure computation)
            embeddings = await self._generate_embeddings(texts)

            return ModelComputeOutput(
                node_id=self.node_id,
                data={
                    "embeddings": embeddings,
                    "model": self._model_name,
                    "dimensions": self._dimensions,
                },
                metadata={
                    "text_count": len(texts),
                    "cache_key": cache_key,
                    "total_tokens": sum(len(t.split()) for t in texts),
                },
            )

        except Exception as e:
            logger.error(
                "Vectorization failed",
                extra={"node_id": self.node_id, "error": str(e)},
            )
            # Chain with 'from e' to preserve the original exception as the cause
            raise SPIError("Vectorization failed") from e

    def _extract_texts(
        self,
        input_data: "ModelComputeInput",
    ) -> list[str]:
        """Extract text(s) from input data."""
        data = input_data.data

        if "texts" in data and isinstance(data["texts"], list):
            return [str(t) for t in data["texts"]]

        if "text" in data:
            return [str(data["text"])]

        return []

    def _compute_cache_key(self, texts: list[str]) -> str:
        """Compute deterministic cache key for input texts."""
        combined = "|".join(sorted(texts))
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    async def _generate_embeddings(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Generate embeddings using the configured model.

        This is a placeholder - real implementation would call
        an embedding service or local model.
        """
        # Placeholder: generate mock embeddings
        embeddings = []
        for text in texts:
            # Deterministic mock based on text hash
            seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
            embedding = [
                (seed >> i) % 1000 / 1000.0
                for i in range(self._dimensions)
            ]
            embeddings.append(embedding)
        return embeddings


# Verify protocol compliance
assert isinstance(VectorizationNode(), ProtocolComputeNode)
```

### Usage Example

```python
from omnibase_infra.nodes.compute import VectorizationNode
from omnibase_core.models.compute import ModelComputeInput

node = VectorizationNode(model_name="text-embedding-ada-002")

# Execute vectorization
input_data = ModelComputeInput(
    node_id="vectorization.text-embedding-ada-002.v1",
    data={"texts": ["Hello world", "ONEX platform"]},
    parameters={},
)

output = await node.execute(input_data)
print(f"Generated {len(output.data['embeddings'])} embeddings")
print(f"Dimensions: {output.data['dimensions']}")
```

---

## Implementing ProtocolHandler

**Protocol Location**: `omnibase_spi.protocols.handlers.protocol_handler`

Protocol handlers provide dependency-injected I/O capabilities for effect nodes. Each handler manages a specific protocol (HTTP, Kafka, PostgreSQL, etc.).

### Protocol Contract

```python
from typing import Protocol, runtime_checkable
from omnibase_core.models.protocol import (
    ModelConnectionConfig,
    ModelOperationConfig,
    ModelProtocolRequest,
    ModelProtocolResponse,
)

@runtime_checkable
class ProtocolHandler(Protocol):
    """Protocol for protocol-specific handlers."""

    async def initialize(
        self,
        config: ModelConnectionConfig,
    ) -> None:
        """Initialize clients or connection pools."""
        ...

    async def shutdown(self) -> None:
        """Release resources and close connections."""
        ...

    async def execute(
        self,
        request: ModelProtocolRequest,
        operation_config: ModelOperationConfig,
    ) -> ModelProtocolResponse:
        """Execute a protocol-specific operation."""
        ...
```

### Minimal Implementation

```python
# omnibase_infra/handlers/http_handler.py
"""HTTP REST handler for API calls."""

from typing import TYPE_CHECKING

from omnibase_spi.protocols.handlers import ProtocolHandler

if TYPE_CHECKING:
    from omnibase_core.models.protocol import (
        ModelConnectionConfig,
        ModelOperationConfig,
        ModelProtocolRequest,
        ModelProtocolResponse,
    )


class HttpHandler:
    """Simple HTTP handler for REST API calls.

    Implements ProtocolHandler for HTTP/HTTPS requests.
    """

    def __init__(self) -> None:
        self._session = None
        self._base_url: str | None = None

    async def initialize(
        self,
        config: "ModelConnectionConfig",
    ) -> None:
        """Initialize HTTP session with connection config."""
        import aiohttp

        self._base_url = config.url
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=config.timeout_seconds),
        )

    async def shutdown(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def execute(
        self,
        request: "ModelProtocolRequest",
        operation_config: "ModelOperationConfig",
    ) -> "ModelProtocolResponse":
        """Execute HTTP request."""
        from omnibase_core.models.protocol import ModelProtocolResponse

        url = f"{self._base_url}{request.path}"

        async with self._session.request(
            method=operation_config.method,
            url=url,
            headers=request.headers,
            json=request.body,
        ) as response:
            body = await response.json()
            return ModelProtocolResponse(
                status_code=response.status,
                headers=dict(response.headers),
                body=body,
            )


# Verify protocol compliance
assert isinstance(HttpHandler(), ProtocolHandler)
```

### Full Implementation with Retry and Circuit Breaker

```python
# omnibase_infra/handlers/postgres_handler.py
"""PostgreSQL handler with connection pooling and resilience."""

import asyncio
import logging
from typing import TYPE_CHECKING

from omnibase_spi.protocols.handlers import ProtocolHandler
from omnibase_spi.exceptions import (
    HandlerInitializationError,
    ProtocolHandlerError,
)

if TYPE_CHECKING:
    from omnibase_core.models.protocol import (
        ModelConnectionConfig,
        ModelOperationConfig,
        ModelProtocolRequest,
        ModelProtocolResponse,
    )

logger = logging.getLogger(__name__)


class PostgresHandler:
    """PostgreSQL handler with connection pooling.

    Implements ProtocolHandler with:
    - Connection pooling via asyncpg
    - Automatic retry with exponential backoff
    - Circuit breaker for failure isolation
    - Query parameterization (SQL injection prevention)
    - Comprehensive error handling
    """

    def __init__(
        self,
        min_pool_size: int = 5,
        max_pool_size: int = 20,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        self._pool = None
        self._config: ModelConnectionConfig | None = None
        self._min_pool_size = min_pool_size
        self._max_pool_size = max_pool_size
        self._max_retries = max_retries
        self._retry_delay = retry_delay_seconds

        # Circuit breaker state
        self._failure_count = 0
        self._circuit_open = False
        self._circuit_open_until: float = 0

    async def initialize(
        self,
        config: "ModelConnectionConfig",
    ) -> None:
        """Initialize PostgreSQL connection pool.

        Args:
            config: Connection configuration with DSN, auth, and pool settings.

        Raises:
            HandlerInitializationError: If pool creation fails.
        """
        import asyncpg

        self._config = config

        try:
            self._pool = await asyncpg.create_pool(
                dsn=config.url,
                min_size=self._min_pool_size,
                max_size=self._max_pool_size,
                timeout=config.timeout_seconds,
            )
            logger.info(
                "PostgreSQL pool initialized",
                extra={
                    "min_size": self._min_pool_size,
                    "max_size": self._max_pool_size,
                },
            )

        except Exception as e:
            raise HandlerInitializationError(
                f"Failed to create PostgreSQL pool: {e}"
            ) from e

    async def shutdown(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL pool closed")

    async def execute(
        self,
        request: "ModelProtocolRequest",
        operation_config: "ModelOperationConfig",
    ) -> "ModelProtocolResponse":
        """Execute SQL query with retry and circuit breaker.

        Args:
            request: Contains 'query' and optional 'params' in body.
            operation_config: Contains operation type and timeout.

        Returns:
            Response with query results or affected row count.

        Raises:
            ProtocolHandlerError: If execution fails after retries.
        """
        from omnibase_core.models.protocol import ModelProtocolResponse

        # Check circuit breaker
        if self._is_circuit_open():
            raise ProtocolHandlerError(
                "Circuit breaker open - PostgreSQL unavailable"
            )

        query = request.body.get("query", "")
        params = request.body.get("params", [])

        for attempt in range(self._max_retries):
            try:
                result = await self._execute_query(
                    query=query,
                    params=params,
                    operation_type=operation_config.operation_type,
                )

                # Reset circuit breaker on success
                self._failure_count = 0
                self._circuit_open = False

                return ModelProtocolResponse(
                    status_code=200,
                    headers={"x-db-operation": operation_config.operation_type},
                    body=result,
                )

            except Exception as e:
                logger.warning(
                    "PostgreSQL query failed",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "error": str(e),
                    },
                )

                self._failure_count += 1
                if self._failure_count >= 5:
                    self._open_circuit()

                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    raise ProtocolHandlerError(
                        f"PostgreSQL query failed after {self._max_retries} attempts: {e}"
                    ) from e

    async def _execute_query(
        self,
        query: str,
        params: list,
        operation_type: str,
    ) -> dict:
        """Execute the actual database query."""
        async with self._pool.acquire() as conn:
            if operation_type == "SELECT":
                rows = await conn.fetch(query, *params)
                return {
                    "rows": [dict(row) for row in rows],
                    "row_count": len(rows),
                }
            else:
                result = await conn.execute(query, *params)
                return {
                    "affected_rows": int(result.split()[-1]),
                }

    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self._circuit_open:
            return False

        import time
        if time.time() > self._circuit_open_until:
            # Half-open: allow one request through
            self._circuit_open = False
            return False

        return True

    def _open_circuit(self) -> None:
        """Open the circuit breaker."""
        import time
        self._circuit_open = True
        self._circuit_open_until = time.time() + 30  # 30 second cooldown
        logger.warning("Circuit breaker opened for PostgreSQL")


# Verify protocol compliance
assert isinstance(PostgresHandler(), ProtocolHandler)
```

### Usage Example

```python
from omnibase_infra.handlers import PostgresHandler
from omnibase_core.models.protocol import (
    ModelConnectionConfig,
    ModelOperationConfig,
    ModelProtocolRequest,
)

# Initialize handler
handler = PostgresHandler(max_pool_size=10)
await handler.initialize(
    ModelConnectionConfig(
        url="postgresql://user:pass@localhost:5432/mydb",
        timeout_seconds=30,
    )
)

# Execute query
request = ModelProtocolRequest(
    path="/query",
    headers={},
    body={
        "query": "SELECT * FROM users WHERE status = $1",
        "params": ["active"],
    },
)

response = await handler.execute(
    request=request,
    operation_config=ModelOperationConfig(
        operation_type="SELECT",
        timeout_seconds=10,
    ),
)

print(f"Found {response.body['row_count']} users")

# Shutdown
await handler.shutdown()
```

---

## Implementation Checklist

When implementing any SPI protocol, verify:

### Protocol Compliance

- [ ] Class implements all required methods from the protocol
- [ ] Method signatures match exactly (parameter names and types)
- [ ] Properties are implemented with `@property` decorator
- [ ] Runtime check passes: `isinstance(MyImpl(), ProtocolXxx)`

### Type Safety

- [ ] Use `TYPE_CHECKING` block for model imports to avoid circular imports
- [ ] Return types match protocol specification
- [ ] Use `TYPE_CHECKING` blocks for forward references (do not use `from __future__ import annotations`)

### Error Handling

- [ ] Raise appropriate SPI exceptions (`SPIError`, `HandlerInitializationError`, etc.)
- [ ] Include error context in exception messages
- [ ] Log errors with structured metadata

### Resource Management

- [ ] Implement proper cleanup in `shutdown()` or `close_all()`
- [ ] Handle partial initialization failures
- [ ] Use connection pooling where appropriate

### Testing

- [ ] Add protocol compliance assertion at module level
- [ ] Test error paths and edge cases
- [ ] Verify thread safety for concurrent access

### Documentation

- [ ] Add module-level docstring explaining purpose
- [ ] Document all public methods with Args/Returns/Raises
- [ ] Include usage examples

---

## See Also

- **`Protocol Definitions` (in the omnibase_spi repository)** - Source protocol files
- **`Exception Hierarchy` (in the omnibase_spi repository)** - SPI exception types
- **[Examples README](omnibase-spi-examples/README.md)** - Protocol usage patterns
- **`API Reference` (in the omnibase_spi repository)** - Complete protocol documentation
