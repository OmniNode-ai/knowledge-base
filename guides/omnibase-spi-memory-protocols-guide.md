---
type: guide
status: current
date: "2026-09-01"
title: "omnibase_spi Memory Protocols Guide"
topics:
  - omnibase_spi
  - memory
  - protocols
refs: []
---

<!-- Migrated from omnibase_spi:docs/examples/MEMORY_PROTOCOLS_GUIDE.md on 2026-09-01 -->

# Memory Protocols Guide

## Overview

Comprehensive guide to memory system implementation patterns using ONEX SPI memory protocols.

> The memory domain (`omnibase_spi.protocols.memory`) does not export a single
> generic `ProtocolMemoryBase` "do everything" interface. It is decomposed into
> a base key-value protocol (`ProtocolKeyValueStore`), composable focused
> interfaces (agent coordination, workflow management, caching, streaming,
> security), and typed request/response DTOs for the memory node archetypes
> (`ProtocolMemoryComputeNode`, `ProtocolMemoryEffectNode`,
> `ProtocolMemoryReducerNode`, `ProtocolMemoryOrchestratorNode`). This guide
> was rewritten to match that real surface; every import below
> resolves against the live package.

## Memory Architecture

The memory system provides:
- **Key-value storage** via `ProtocolKeyValueStore` and its extensions
- **Agent coordination** via `ProtocolAgentCoordinator`
- **Memory security** via `ProtocolMemorySecurityNode` (PII detection, encryption, audit)
- **Streaming operations** via `ProtocolStreamingMemoryNode`
- **Caching** via `ProtocolMemoryCache`

## Basic Memory Operations

### Key-Value Store Protocol

`ProtocolKeyValueStore` is the base protocol every memory data structure in
the domain composes from (`ProtocolMemoryMetadata`, `ProtocolWorkflowConfiguration`,
`ProtocolAnalysisParameters`, and `ProtocolAggregationCriteria` all extend it).

```python
from omnibase_spi.protocols.memory import ProtocolKeyValueStore

class SimpleKeyValueStore:
    """Concrete implementation of ProtocolKeyValueStore."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    @property
    def keys(self) -> list[str]:
        return list(self._data.keys())

    async def get_value(self, key: str) -> str | None:
        return self._data.get(key)

    def has_key(self, key: str) -> bool:
        return key in self._data

    async def validate_store(self) -> bool:
        return all(isinstance(v, str) for v in self._data.values())


store = SimpleKeyValueStore()
assert isinstance(store, ProtocolKeyValueStore)
```

## Memory Caching

```python
from uuid import uuid4

from omnibase_spi.protocols.memory import ProtocolMemoryCache

memory_cache: ProtocolMemoryCache = get_memory_cache()
memory_id = uuid4()

# Cache a memory record with TTL
await memory_cache.cache_memory(
    memory_id=memory_id,
    cache_ttl_seconds=3600,
    cache_level="hot",
)

# Invalidate on update
await memory_cache.invalidate_cache(
    memory_id=memory_id,
    invalidation_scope="single",
)

# Warm cache for a batch of frequently-accessed records
await memory_cache.warm_cache(
    memory_ids=[memory_id],
    warming_strategy="eager",
)

stats = await memory_cache.get_cache_stats(cache_scope="hot")
```

## Memory Security

`ProtocolMemorySecurityNode` (in `omnibase_spi.protocols.memory`) provides
access validation, PII detection, input validation, rate limiting, audit
trail creation, and encryption — all keyed off a `ProtocolMemorySecurityContext`
(`omnibase_spi.protocols.memory`).

```python
from uuid import uuid4

from omnibase_spi.protocols.memory import (
    ProtocolMemorySecurityContext,
    ProtocolMemorySecurityNode,
)

security_node: ProtocolMemorySecurityNode = get_memory_security_node()
security_context: ProtocolMemorySecurityContext = get_security_context()

# Validate access before an operation
await security_node.validate_access(
    security_context=security_context,
    operation_type="read",
    resource_id=uuid4(),
)

# Detect PII in free-text content before persisting it
pii_result = await security_node.detect_pii(
    content="Contact: jane.doe@example.com, SSN 123-45-6789",  # sanitization-ok: illustrative example content
    detection_threshold=0.8,
)

# Encrypt sensitive data before storage
encrypted = await security_node.encrypt_sensitive_data(
    data=sensitive_metadata,
    encryption_level="aes256",
)

# ... store `encrypted`, then later:
decrypted = await security_node.decrypt_sensitive_data(
    encrypted_data=encrypted,
    security_context=security_context,
)

# Record an audit trail entry for compliance
await security_node.create_audit_trail(
    audit_info=audit_trail_entry,
    security_context=security_context,
)
```

## Memory Streaming

`ProtocolStreamingMemoryNode` handles chunked content transfer, cursor-based
pagination, compression, and streamed embedding-vector batches.

```python
from uuid import uuid4

from omnibase_spi.protocols.memory import (
    ProtocolCursorPagination,
    ProtocolStreamingConfig,
    ProtocolStreamingMemoryNode,
)

streaming_node: ProtocolStreamingMemoryNode = get_streaming_memory_node()
memory_id = uuid4()
streaming_config: ProtocolStreamingConfig = get_streaming_config()

# Stream memory content in chunks
async for chunk in streaming_node.stream_memory_content(
    memory_id=memory_id,
    streaming_config=streaming_config,
):
    print(f"Received chunk: {chunk}")

# Cursor-based pagination over large memory collections
pagination_config: ProtocolCursorPagination = get_cursor_pagination(
    limit=100,
    sort_field="created_at",
)
page = await streaming_node.paginate_memories_cursor(pagination_config)

# Compress a large memory record in place
await streaming_node.compress_memory_content(
    memory_id=memory_id,
    compression_algorithm="zstd",
    compression_level=6,
)
```

## Agent Coordination

`ProtocolAgentCoordinator` (composable interface, `omnibase_spi.protocols.memory`)
is the real agent-coordination surface — there is no `ProtocolAgentManager` or
`ProtocolAgentPool` in the package.

```python
from uuid import uuid4

from omnibase_spi.protocols.memory import (
    ProtocolAgentCoordinationRequest,
    ProtocolAgentCoordinator,
    ProtocolMemoryMetadata,
)

agent_coordinator: ProtocolAgentCoordinator = get_agent_coordinator()
agent_id = uuid4()

# Register an agent
await agent_coordinator.register_agent(
    agent_id=agent_id,
    agent_capabilities=["data_processing", "ml_inference"],
    agent_metadata=agent_metadata,  # ProtocolMemoryMetadata
)

# List agents that can handle a capability
available = await agent_coordinator.list_available_agents(
    capability_filter=["data_processing"],
)

# Coordinate a multi-agent task
coordination_request: ProtocolAgentCoordinationRequest = build_coordination_request()
result = await agent_coordinator.coordinate_agents(coordination_request)

# Query status, then deregister when finished
await agent_coordinator.get_agent_status(agent_id)
await agent_coordinator.unregister_agent(agent_id)
```

## Best Practices

### Memory Management

1. **Compose from `ProtocolKeyValueStore`** — build custom memory data
   structures by extending it, matching `ProtocolMemoryMetadata` and
   `ProtocolWorkflowConfiguration`'s pattern.
2. **Use the security node for anything PII-adjacent** — `detect_pii()` and
   `encrypt_sensitive_data()` are first-class operations, not an afterthought.
3. **Prefer cursor pagination for large collections** — `ProtocolCursorPagination`
   gives stable ordering; do not page with raw offsets.
4. **Cache explicitly, invalidate explicitly** — `ProtocolMemoryCache` has no
   implicit TTL sweep; call `invalidate_cache()` on writes.

### Error Handling

The memory domain has its own error *data* protocols in the same package
(`ProtocolMemoryError`, `ProtocolMemoryNotFoundError`,
`ProtocolMemoryAuthorizationError`, `ProtocolMemoryValidationError`,
`ProtocolMemoryTimeoutError`, `ProtocolMemoryCapacityError`,
`ProtocolMemoryCorruptionError`). These are plain `Protocol` shapes (not
`Exception` subclasses) that describe a standardized error payload —
`error_code`, `error_message`, `error_timestamp`, `correlation_id`,
`error_category` — carried inside a response object, not raised and caught
with `try`/`except`. Actual Python exceptions for handler/SPI-level failures
come from `omnibase_spi.exceptions` (see `EXCEPTIONS.md` (in the omnibase_spi repository)).

```python
from omnibase_spi.protocols.memory import ProtocolMemoryNotFoundError

async def handle_lookup(memory_id: UUID) -> None:
    response = await memory_node.retrieve_memory(memory_id)
    error: ProtocolMemoryNotFoundError | None = response.error
    if error is not None:
        print(f"[{error.error_code}] {error.error_message}")
```

## API Reference

- **`Memory Management` (in the omnibase_spi repository)** - Complete memory protocol documentation
- **`Container Protocols` (in the omnibase_spi repository)** - Dependency injection patterns
- **`Workflow Orchestration` (in the omnibase_spi repository)** - Event-driven FSM

---

*For detailed protocol documentation, see the `API Reference` (in the omnibase_spi repository).*
