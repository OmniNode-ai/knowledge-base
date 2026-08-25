---
type: guide
status: current
date: "2026-07-21"
title: "Handler Authoring Guide"
topics: [omnibase-infra, handler, authoring]
refs: []
---

# Handler Authoring Guide

> **Status**: Current | **Last Updated**: 2026-02-19

This guide walks through creating a new handler for an existing ONEX node — from deciding the right handler type to registering it in the contract YAML. It uses a concrete Postgres-reading handler as the running example.

---

## Table of Contents

1. When to Create a Handler
2. Handler Classification
3. Step 1 — Create the Handler File
4. Step 2 — Implement handler_type and handler_category
5. Step 3 — Implement initialize, execute, and shutdown
6. Step 4 — Handle Errors Correctly
7. Step 5 — Enforce the No-Publish Constraint
8. Step 6 — Register in contract.yaml
9. Step 7 — Configure Namespace Allowlisting
10. Step 8 — Write Tests
11. Complete Handler Example
12. Common Mistakes

---

## When to Create a Handler

Handlers are where business logic lives. A node's `node.py` is declarative — it extends a base class with no custom Python. Everything the node does at runtime passes through one or more handlers loaded from its `contract.yaml`.

Create a new handler when:
- An existing node needs a new operation (e.g., a new query against a database table)
- A node must integrate with a transport it does not yet use
- A projection or read-model needs its own dedicated update path

Do **not** create a handler when:
- The logic could belong in a COMPUTE node (pure transformation with no I/O)
- The behavior is only needed in tests (use fixtures instead)
- You are tempted to add the logic directly to `node.py` (that is always wrong)

---

## Handler Classification

Every handler exposes two classification properties. Choosing them correctly matters because the runtime uses them to enforce security rules and replay guarantees.

### handler_type — Architectural Role

`EnumHandlerType` answers: "What role does this handler play in the architecture?"

| Value | Description |
|-------|-------------|
| `INFRA_HANDLER` | Transport/protocol handlers (database, HTTP, Kafka, Consul, MCP) |
| `NODE_HANDLER` | Event processing handlers on ORCHESTRATOR or EFFECT nodes |
| `PROJECTION_HANDLER` | Read-model projection update handlers (REDUCER nodes) |

Almost all new handlers are `INFRA_HANDLER`. Use `NODE_HANDLER` only when the handler processes domain events on an ORCHESTRATOR. Use `PROJECTION_HANDLER` only when the handler writes to a read-model projection.

### handler_category — Behavioral Classification

`EnumHandlerTypeCategory` answers: "How does this handler behave at runtime?"

| Value | Description |
|-------|-------------|
| `EFFECT` | Side-effecting I/O — database, HTTP calls, external API writes |
| `COMPUTE` | Pure, deterministic transformation — no side effects, safe to replay |
| `NONDETERMINISTIC_COMPUTE` | Pure but not deterministic — UUID generation, timestamps, random values |

When in doubt between `EFFECT` and `COMPUTE`: if the handler reads from or writes to anything external (database, API, file), it is `EFFECT`. If it only transforms data in memory, it is `COMPUTE`.

---

## Step 1 — Create the Handler File

Place the handler inside the node's `handlers/` directory:

```
nodes/node_audit_effect/
├── contract.yaml
├── node.py
└── handlers/
    ├── __init__.py
    └── handler_audit_query.py    # <-- new file
```

File naming convention: `handler_<operation_name>.py`. Class naming convention: `Handler<OperationName>`.

---

## Step 2 — Implement handler_type and handler_category

Both properties are required on every handler. They must be `@property` definitions (not class attributes).

```python
from omnibase_infra.enums import EnumHandlerType, EnumHandlerTypeCategory

class HandlerAuditQuery:

    @property
    def handler_type(self) -> EnumHandlerType:
        """Architectural role: infrastructure transport handler."""
        return EnumHandlerType.INFRA_HANDLER

    @property
    def handler_category(self) -> EnumHandlerTypeCategory:
        """Behavioral classification: side-effecting database read."""
        return EnumHandlerTypeCategory.EFFECT
```

---

## Step 3 — Implement initialize, execute, and shutdown

Handlers follow a three-phase lifecycle that mirrors the node lifecycle.

**initialize(config)** — Called once on startup. Parse configuration, open connections, start circuit breaker.

**execute(envelope)** — Called per-request. Extract operation and payload from the envelope, run the business logic, return `ModelHandlerOutput`.

**shutdown()** — Called on graceful exit. Close connections, reset state.

```python
from __future__ import annotations

import logging
from uuid import uuid4

from omnibase_core.container import ModelONEXContainer
from omnibase_core.models.dispatch import ModelHandlerOutput
from omnibase_infra.enums import (
    EnumHandlerType,
    EnumHandlerTypeCategory,
    EnumInfraTransportType,
)
from omnibase_infra.errors import (
    InfraConnectionError,
    ModelInfraErrorContext,
    RuntimeHostError,
)
from omnibase_infra.mixins import MixinAsyncCircuitBreaker, MixinEnvelopeExtraction

logger = logging.getLogger(__name__)

HANDLER_ID: str = "audit-query-handler"


class HandlerAuditQuery(MixinAsyncCircuitBreaker, MixinEnvelopeExtraction):
    """Reads audit records from PostgreSQL via HandlerDb."""

    def __init__(self, container: ModelONEXContainer) -> None:
        self._container = container
        self._db_handler = None
        self._initialized = False

    @property
    def handler_type(self) -> EnumHandlerType:
        return EnumHandlerType.INFRA_HANDLER

    @property
    def handler_category(self) -> EnumHandlerTypeCategory:
        return EnumHandlerTypeCategory.EFFECT

    async def initialize(self, config: dict[str, object]) -> None:
        init_cid = uuid4()
        dsn = config.get("dsn")
        if not isinstance(dsn, str) or not dsn:
            ctx = ModelInfraErrorContext.with_correlation(
                correlation_id=init_cid,
                transport_type=EnumInfraTransportType.DATABASE,
                operation="initialize",
            )
            raise RuntimeHostError("Missing 'dsn' in config", context=ctx)

        # Resolve HandlerDb from container; initialize it with the DSN.
        from omnibase_infra.handlers.handler_db import HandlerDb

        self._db_handler = HandlerDb(self._container)
        await self._db_handler.initialize({"dsn": dsn})
        self._initialized = True
        logger.info("HandlerAuditQuery initialized", extra={"correlation_id": str(init_cid)})

    async def shutdown(self) -> None:
        if self._db_handler is not None:
            await self._db_handler.shutdown()
            self._db_handler = None
        self._initialized = False

    async def execute(self, envelope: dict[str, object]) -> ModelHandlerOutput[dict[str, object]]:
        correlation_id = self._extract_correlation_id(envelope)
        input_envelope_id = self._extract_envelope_id(envelope)

        if not self._initialized or self._db_handler is None:
            ctx = ModelInfraErrorContext.with_correlation(
                correlation_id=correlation_id,
                transport_type=EnumInfraTransportType.DATABASE,
                operation="execute",
            )
            raise RuntimeHostError("HandlerAuditQuery not initialized", context=ctx)

        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            ctx = ModelInfraErrorContext.with_correlation(
                correlation_id=correlation_id,
                transport_type=EnumInfraTransportType.DATABASE,
                operation="execute",
            )
            raise RuntimeHostError("Missing or invalid 'payload' in envelope", context=ctx)

        node_id = payload.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            ctx = ModelInfraErrorContext.with_correlation(
                correlation_id=correlation_id,
                transport_type=EnumInfraTransportType.DATABASE,
                operation="execute",
            )
            raise RuntimeHostError("Missing 'node_id' in payload", context=ctx)

        db_envelope = {
            "operation": "db.query",
            "correlation_id": str(correlation_id),
            "payload": {
                "sql": "SELECT id, event_type, created_at FROM audit_events WHERE node_id = $1 ORDER BY created_at DESC LIMIT 100",
                "parameters": [node_id],
            },
        }
        db_result = await self._db_handler.execute(db_envelope)

        rows: list[dict[str, object]] = []
        if db_result.result is not None:
            rows = db_result.result.payload.rows  # type: ignore[union-attr]

        return ModelHandlerOutput.for_compute(
            input_envelope_id=input_envelope_id,
            correlation_id=correlation_id,
            handler_id=HANDLER_ID,
            result={"rows": rows, "count": len(rows)},
        )


__all__: list[str] = ["HandlerAuditQuery"]
```

---

## Step 4 — Handle Errors Correctly

Every error must carry a `ModelInfraErrorContext`. Never raise bare exceptions; never include credentials or raw argument values in messages.

```python
from omnibase_infra.errors import (
    InfraConnectionError,
    InfraTimeoutError,
    ModelInfraErrorContext,
    RuntimeHostError,
)
from omnibase_infra.enums import EnumInfraTransportType

# Pattern A: auto-generate correlation_id (no existing ID)
ctx = ModelInfraErrorContext.with_correlation(
    transport_type=EnumInfraTransportType.DATABASE,
    operation="my_operation",
)

# Pattern B: propagate existing correlation_id (preserve trace)
ctx = ModelInfraErrorContext.with_correlation(
    correlation_id=correlation_id,
    transport_type=EnumInfraTransportType.DATABASE,
    operation="my_operation",
)

# Raise an appropriate error class
raise InfraConnectionError("Database unavailable", context=ctx) from original_exc
```

### Error class selection

| Scenario | Correct class |
|----------|---------------|
| Connection to external service failed | `InfraConnectionError` |
| Request timed out | `InfraTimeoutError` |
| Bad credentials / auth failure | `InfraAuthenticationError` |
| Circuit breaker open | `InfraUnavailableError` |
| Rate limit hit | `InfraRateLimitedError` |
| Invalid config / missing required key | `ProtocolConfigurationError` |
| Secret could not be resolved | `SecretResolutionError` |
| Everything else | `RuntimeHostError` |

### What is safe to include in error messages

Safe: service names, operation names, correlation IDs, table names, port numbers.

Never include: passwords, API keys, DSN strings, secret values, raw user input.

---

## Step 5 — Enforce the No-Publish Constraint

Handlers **must not** have access to the event bus. This is a hard architectural constraint. Only ORCHESTRATOR nodes may publish events.

Violations will fail code review. The verification checks are:

1. `__init__` and `execute` signatures must not accept `bus`, `event_bus`, or `publisher` parameters.
2. The class must have no `_bus`, `_event_bus`, or `_publisher` attributes.
3. The class must not define `publish()`, `emit()`, or `send_event()` methods.
4. The class must not import from `omnibase_infra.adapters.adapter_protocol_event_publisher_kafka` or similar event publishing modules.

If the operation genuinely requires publishing events (for example, a successful write should notify downstream consumers), the correct pattern is:

1. The handler returns its result in `ModelHandlerOutput.for_compute(result=...)`.
2. The ORCHESTRATOR that called the handler reads the result and emits the downstream event.

---

## Step 6 — Register in contract.yaml

The handler plugin loader reads the `handler_routing` section of the node's `contract.yaml`. Two routing strategies are available.

### operation_match (recommended for EFFECT and INFRA handlers)

Routes incoming envelope operations to handlers by operation string match. Use this when different envelope operations (`"audit.query"`, `"audit.delete"`) should route to different handlers.

```yaml
handler_routing:
  routing_strategy: "operation_match"
  handlers:
    - operation: "audit.query"
      handler:
        name: "HandlerAuditQuery"
        module: "omnibase_infra.nodes.node_audit_effect.handlers.handler_audit_query"
      handler_type: "db"        # transport type (used by config discovery)
```

### payload_type_match (for ORCHESTRATOR handlers)

Routes based on the Pydantic model type of the event payload. Use this on ORCHESTRATOR nodes where different domain events arrive with different payload models.

```yaml
handler_routing:
  routing_strategy: "payload_type_match"
  handlers:
    - event_model:
        name: "ModelAuditRequestedEvent"
        module: "omnibase_infra.models.audit.model_audit_requested_event"
      handler:
        name: "HandlerAuditRequested"
        module: "omnibase_infra.nodes.node_audit_orchestrator.handlers.handler_audit_requested"
```

### Dedicated handler_contract.yaml

For nodes with many handlers, you may create a separate `handler_contract.yaml` alongside `contract.yaml`. The loader detects it automatically. However, if **both** files exist and both contain `handler_routing`, the loader raises `HANDLER_LOADER_040` (`AMBIGUOUS_CONTRACT_CONFIGURATION`). Keep handler routing in exactly one file per node directory.

---

## Step 7 — Configure Namespace Allowlisting

The handler plugin loader restricts which Python namespaces it will load handlers from. This prevents arbitrary code injection via malformed contract files.

In production, configure `HandlerPluginLoader` with an explicit allowlist:

```python
from omnibase_infra.runtime.handler_plugin_loader import HandlerPluginLoader

loader = HandlerPluginLoader(
    allowed_namespaces=[
        "omnibase_infra.",
        "omnibase_core.",
        # Add your application namespace here:
        "myapp.handlers.",
    ]
)
```

If a handler module is outside an allowed namespace, the loader raises `HANDLER_LOADER_013` (`NAMESPACE_NOT_ALLOWED`). The fix is to either move the handler into a listed namespace or add your namespace to the allowlist.

During development (`dev_mode=True`), the loader may use a broader allowlist. Never use dev mode in production.

---

## Step 8 — Write Tests

Tests for handlers go in `tests/unit/` (isolated, with mocks) and optionally `tests/integration/` (with real infrastructure).

Unit tests should mock the container and any external services:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from omnibase_infra.nodes.node_audit_effect.handlers.handler_audit_query import HandlerAuditQuery


@pytest.mark.unit
class TestHandlerAuditQuery:
    def test_handler_type_and_category(self) -> None:
        from omnibase_infra.enums import EnumHandlerType, EnumHandlerTypeCategory

        container = MagicMock()
        handler = HandlerAuditQuery(container)
        assert handler.handler_type == EnumHandlerType.INFRA_HANDLER
        assert handler.handler_category == EnumHandlerTypeCategory.EFFECT

    @pytest.mark.asyncio
    async def test_raises_when_not_initialized(self) -> None:
        from omnibase_infra.errors import RuntimeHostError

        container = MagicMock()
        handler = HandlerAuditQuery(container)
        with pytest.raises(RuntimeHostError, match="not initialized"):
            await handler.execute(
                {"operation": "audit.query", "payload": {"node_id": "abc"}}
            )

    @pytest.mark.asyncio
    async def test_execute_returns_rows(self) -> None:
        from omnibase_infra.handlers.handler_db import HandlerDb

        container = MagicMock()
        handler = HandlerAuditQuery(container)
        handler._initialized = True

        # Mock HandlerDb execute to return fake rows
        mock_payload = MagicMock()
        mock_payload.rows = [{"id": "1", "event_type": "created"}]
        mock_db_result = MagicMock()
        mock_db_result.result.payload = mock_payload

        mock_db = AsyncMock(spec=HandlerDb)
        mock_db.execute.return_value = mock_db_result
        handler._db_handler = mock_db

        envelope = {
            "operation": "audit.query",
            "correlation_id": str(uuid4()),
            "payload": {"node_id": "node-123"},
        }
        output = await handler.execute(envelope)
        assert output.result["count"] == 1
        mock_db.execute.assert_called_once()
```

---

## Complete Handler Example

This is the minimal correct form of a database-reading INFRA handler. It includes all required elements: classification properties, lifecycle methods, error context, and the no-publish constraint.

```python
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Audit query handler — reads audit events from PostgreSQL."""

from __future__ import annotations

import logging
from uuid import uuid4

from omnibase_core.container import ModelONEXContainer
from omnibase_core.models.dispatch import ModelHandlerOutput
from omnibase_infra.enums import (
    EnumHandlerType,
    EnumHandlerTypeCategory,
    EnumInfraTransportType,
)
from omnibase_infra.errors import ModelInfraErrorContext, RuntimeHostError
from omnibase_infra.mixins import MixinEnvelopeExtraction

logger = logging.getLogger(__name__)
HANDLER_ID: str = "audit-query-handler"


class HandlerAuditQuery(MixinEnvelopeExtraction):

    def __init__(self, container: ModelONEXContainer) -> None:
        self._container = container
        self._db_handler = None
        self._initialized = False

    # ---- Classification (required on every handler) ----

    @property
    def handler_type(self) -> EnumHandlerType:
        return EnumHandlerType.INFRA_HANDLER

    @property
    def handler_category(self) -> EnumHandlerTypeCategory:
        return EnumHandlerTypeCategory.EFFECT

    # ---- Lifecycle ----

    async def initialize(self, config: dict[str, object]) -> None:
        from omnibase_infra.handlers.handler_db import HandlerDb

        dsn = config.get("dsn")
        if not isinstance(dsn, str) or not dsn:
            ctx = ModelInfraErrorContext.with_correlation(
                transport_type=EnumInfraTransportType.DATABASE,
                operation="initialize",
            )
            raise RuntimeHostError("Missing 'dsn' in handler config", context=ctx)

        self._db_handler = HandlerDb(self._container)
        await self._db_handler.initialize({"dsn": dsn})
        self._initialized = True

    async def shutdown(self) -> None:
        if self._db_handler is not None:
            await self._db_handler.shutdown()
            self._db_handler = None
        self._initialized = False

    # ---- Business logic ----

    async def execute(
        self, envelope: dict[str, object]
    ) -> ModelHandlerOutput[dict[str, object]]:
        correlation_id = self._extract_correlation_id(envelope)
        input_envelope_id = self._extract_envelope_id(envelope)

        if not self._initialized or self._db_handler is None:
            ctx = ModelInfraErrorContext.with_correlation(
                correlation_id=correlation_id,
                transport_type=EnumInfraTransportType.DATABASE,
                operation="execute",
            )
            raise RuntimeHostError("HandlerAuditQuery not initialized", context=ctx)

        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            ctx = ModelInfraErrorContext.with_correlation(
                correlation_id=correlation_id,
                transport_type=EnumInfraTransportType.DATABASE,
                operation="execute",
            )
            raise RuntimeHostError("Missing 'payload' in envelope", context=ctx)

        node_id = payload.get("node_id")
        if not isinstance(node_id, str):
            ctx = ModelInfraErrorContext.with_correlation(
                correlation_id=correlation_id,
                transport_type=EnumInfraTransportType.DATABASE,
                operation="execute",
            )
            raise RuntimeHostError("Missing 'node_id' in payload", context=ctx)

        db_result = await self._db_handler.execute({
            "operation": "db.query",
            "correlation_id": str(correlation_id),
            "payload": {
                "sql": "SELECT id, event_type, created_at FROM audit_events WHERE node_id = $1 ORDER BY created_at DESC LIMIT 100",
                "parameters": [node_id],
            },
        })

        rows = db_result.result.payload.rows if db_result.result else []  # type: ignore[union-attr]
        return ModelHandlerOutput.for_compute(
            input_envelope_id=input_envelope_id,
            correlation_id=correlation_id,
            handler_id=HANDLER_ID,
            result={"rows": rows, "count": len(rows)},
        )


__all__: list[str] = ["HandlerAuditQuery"]
```

Corresponding `contract.yaml` registration:

```yaml
handler_routing:
  routing_strategy: "operation_match"
  handlers:
    - operation: "audit.query"
      handler:
        name: "HandlerAuditQuery"
        module: "omnibase_infra.nodes.node_audit_effect.handlers.handler_audit_query"
      handler_type: "db"
```

---

## Common Mistakes

### 1. Adding logic to node.py

```python
# WRONG — nodes are declarative only
class NodeAuditEffect(NodeEffect):
    async def run_query(self, node_id: str) -> list[dict]:  # never do this
        ...
```

All logic belongs in handlers. `node.py` must only call `super().__init__(container)`.

### 2. Returning result from an ORCHESTRATOR handler

```python
# WRONG — orchestrators cannot return result
return ModelHandlerOutput.for_orchestrator(result={"status": "done"})  # raises ValueError
```

Orchestrator handlers return events and intents, not results. Use `ModelHandlerOutput.for_effect(events=[...])`.

### 3. Accepting an event bus in the handler

```python
# WRONG — violates the no-publish constraint
class HandlerAuditQuery:
    def __init__(self, container, bus):  # bus parameter is forbidden
        self._bus = bus

    async def execute(self, envelope):
        await self._bus.publish(some_event)  # handlers never publish
```

If downstream notification is required, return data in `result` and let the orchestrator publish.

### 4. Skipping `super().__init__()` in the node

```python
# WRONG — the base class wires container, registry, and contract loading
class NodeAuditEffect(NodeEffect):
    def __init__(self, container):
        pass  # missing super().__init__(container)
```

Always call `super().__init__(container)`.

### 5. Raising bare exceptions without error context

```python
# WRONG — no error context, no chain
raise RuntimeError("Query failed")

# CORRECT — context + exception chaining
ctx = ModelInfraErrorContext.with_correlation(
    correlation_id=correlation_id,
    transport_type=EnumInfraTransportType.DATABASE,
    operation="execute",
)
raise RuntimeHostError("Query failed", context=ctx) from original_exc
```

### 6. Ambiguous contract files

If `contract.yaml` and `handler_contract.yaml` both exist in the same node directory and both contain `handler_routing`, the loader raises `HANDLER_LOADER_040`. Pick one file and remove `handler_routing` from the other.

---

## See Also

- `docs/patterns/handler_plugin_loader.md` — loader internals and error codes
- `docs/patterns/error_handling_patterns.md` — full error class reference
- `docs/patterns/circuit_breaker_implementation.md` — MixinAsyncCircuitBreaker usage
- `src/omnibase_infra/handlers/handler_db.py` — canonical INFRA_HANDLER/EFFECT example
- The secrets-manager handler (see `src/omnibase_infra/handlers/`) — caching and circuit breaker pattern
- `CLAUDE.md` Handler System section — routing strategy reference
