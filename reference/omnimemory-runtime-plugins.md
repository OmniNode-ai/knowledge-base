---
type: reference
status: current
date: "2026-08-25"
title: "OmniMemory Runtime Plugin System"
topics:
  - omnimemory
  - runtime
  - kafka
  - plugin-lifecycle
refs:
  - architecture/omnimemory-four-node-architecture.md
  - architecture/omnimemory-arch-002-kafka-abstraction.md
---

# Runtime Plugin System

> **Last verified:** 2026-08-25, migrated from `omnimemory` to the knowledge base. Two corrections applied during migration (both confirmed directly against `src/omnimemory/runtime/` source): the activation-condition description below, and the event-bus node-package list example. Other specific counts in this document (wire-model count, dispatch-route count, introspected-node count) were not independently re-verified this pass — treat them as carried forward, not freshly confirmed.

## Overview

The runtime plugin system wires the OmniMemory domain into the ONEX kernel without coupling the kernel to domain-specific initialization code. At bootstrap time the kernel discovers registered `ProtocolDomainPlugin` implementations via the `onex.domain_plugins` entry point group, calls their lifecycle methods in order, and receives standardized `ModelDomainPluginResult` values that describe what was created or why a step was skipped.

For OmniMemory, the plugin (`PluginMemory`) performs five sequential steps:

1. Register memory wire models with `RegistryMessageType`.
2. Verify that domain handler classes are importable (`wire_handlers`).
3. Create and freeze a `MessageDispatchEngine` for topic-based routing (`wire_dispatchers`).
4. Publish node introspection events so the platform registration orchestrator can discover each memory node.
5. Subscribe to all Kafka input topics declared in node `contract.yaml` files (`start_consumers`).

The plugin activates when `OMNIMEMORY_MEMGRAPH_HOST` is set (its presence signals memory-domain connection config), with the older `OMNIMEMORY_ENABLED` flag honored as a legacy fallback if the host variable is absent — this enables graceful degradation in kernels that do not require the memory domain. See the `omnimemory` repository's environment-variables reference for configuration details and expected values.

---

## Module Map

All runtime modules live under `src/omnimemory/runtime/`:

| File | Purpose |
|------|---------|
| `plugin.py` | `PluginMemory` — kernel lifecycle entrypoint |
| `wiring.py` | `wire_memory_handlers` — import verification |
| `message_type_registration.py` | `register_memory_message_types` — wire model registry |
| `dispatch_handlers.py` | `create_memory_dispatch_engine`, bridge handlers |
| `contract_topics.py` | Contract-driven topic discovery |
| `adapters.py` | `AdapterKafkaPublisher`, event bus protocols |
| `introspection.py` | `publish_memory_introspection`, `MemoryNodeIntrospectionProxy`, dynamic node discovery |
| `handler_lifecycle.py` | Lifecycle handler for runtime tick and shutdown signals |

---

## PluginMemory

**Class**: `PluginMemory`
**File**: `src/omnimemory/runtime/plugin.py`

`PluginMemory` implements `ProtocolDomainPlugin` (from `omnibase_infra.runtime.protocol_domain_plugin`; verified against omnibase-infra 0.7.x). The kernel calls its methods sequentially during bootstrap.

### Lifecycle Methods

| Method | What it does |
|--------|-------------|
| `should_activate(config)` | Returns `True` if `OMNIMEMORY_MEMGRAPH_HOST` is set, or (legacy fallback) `OMNIMEMORY_ENABLED` is set |
| `initialize(config)` | Registers wire models; freezes `RegistryMessageType` |
| `wire_handlers(config)` | Verifies handler classes are importable |
| `wire_dispatchers(config)` | Creates `MessageDispatchEngine`; publishes node introspection |
| `start_consumers(config)` | Subscribes to all memory Kafka topics |
| `shutdown(config)` | Unsubscribes from topics; publishes shutdown introspection |

### State Managed by the Plugin

```
_unsubscribe_callbacks   -- cleanup handles returned by event_bus.subscribe()
_services_registered     -- handler names confirmed importable during wire_handlers
_dispatch_engine         -- frozen MessageDispatchEngine (set in wire_dispatchers)
_message_type_registry   -- frozen RegistryMessageType (set in initialize)
_event_bus               -- event bus reference captured for shutdown introspection
_introspection_proxies   -- effect-node proxies running heartbeat background tasks
```

### Registration with the Kernel

```python
from omnimemory.runtime.plugin import PluginMemory
from omnibase_infra.runtime.protocol_domain_plugin import (
    ModelDomainPluginConfig,
    RegistryDomainPlugin,
)

# Registration (done once at kernel startup)
registry = RegistryDomainPlugin()
registry.register(PluginMemory())

# Bootstrap sequence (kernel calls in this order)
config = ModelDomainPluginConfig(
    container=container,
    event_bus=event_bus,
    correlation_id=correlation_id,
    consumer_group="my-service",
)
plugin = registry.get("memory")  # plugin_id == "memory"

if plugin and plugin.should_activate(config):
    await plugin.initialize(config)
    await plugin.wire_handlers(config)
    await plugin.wire_dispatchers(config)
    await plugin.start_consumers(config)
```

### Entry Point Declaration

The plugin is declared in `pyproject.toml` so ONEX kernels can discover it automatically via `importlib.metadata`:

```toml
[project.entry-points."onex.domain_plugins"]
memory = "omnimemory.runtime.plugin:PluginMemory"
```

The entry point group `onex.domain_plugins` is the shared discovery namespace. The key `memory` matches `PluginMemory.plugin_id`. This uses the hatchling build backend (`[project.entry-points]`), not the legacy Poetry plugin table.

---

## Wire Model Registration

**Function**: `register_memory_message_types`
**File**: `src/omnimemory/runtime/message_type_registration.py`

During `PluginMemory.initialize()`, a fresh `RegistryMessageType` instance is created and populated with all 10 memory wire models, then frozen. The frozen registry is stored as `_message_type_registry` and exposed via the `message_type_registry` property for external health checks.

### Registered Types

| # | Message Type | Handler | Category | Description |
|---|-------------|---------|----------|-------------|
| 1 | `ModelIntentClassifiedEvent` | `intent_event_consumer_effect` | EVENT | Consumed from omniintelligence |
| 2 | `ModelIntentStorageRequest` | `intent_storage_effect` | COMMAND | Intent storage command input |
| 3 | `ModelIntentStorageResponse` | `intent_storage_effect` | EVENT | Intent storage response output |
| 4 | `ModelMemoryRetrievalRequest` | `memory_retrieval_effect` | COMMAND | Memory retrieval command input |
| 5 | `ModelMemoryRetrievalResponse` | `memory_retrieval_effect` | EVENT | Memory retrieval response output |
| 6 | `ModelMemoryStorageRequest` | `memory_storage_effect` | COMMAND | Memory storage CRUD command input |
| 7 | `ModelMemoryStorageResponse` | `memory_storage_effect` | EVENT | Memory storage CRUD response output |
| 8 | `ModelAgentCoordinatorRequest` | `agent_coordinator_orchestrator` | COMMAND | Coordinator request command input |
| 9 | `ModelAgentCoordinatorResponse` | `agent_coordinator_orchestrator` | EVENT | Coordinator response event output |
| 10 | `ModelNotificationEvent` | `agent_coordinator_orchestrator` | EVENT | Cross-agent notification event |

All types are registered with `domain="memory"`. The `handler_id` matches the node directory name under `src/omnimemory/nodes/`.

### Readiness and Observability

```python
from omnimemory.runtime.message_type_registration import (
    is_registry_ready,
    get_registration_metrics,
    EXPECTED_MESSAGE_TYPE_COUNT,  # 10
    MEMORY_DOMAIN,                # "memory"
)

# Health check integration
if is_registry_ready():
    metrics = get_registration_metrics()
    # {"registered_count": 10, "failure_count": 0, "expected_count": 10}
```

### Adding a New Wire Model

1. Create the Pydantic model in the appropriate node's `models.py`.
2. Add a `registry.register_simple(...)` call in `register_memory_message_types`.
3. Increment `EXPECTED_MESSAGE_TYPE_COUNT`.
4. Update `__all__` if the model is part of the public API.

Example:

```python
registry.register_simple(
    message_type="ModelNewCommandRequest",
    handler_id="new_node_effect",
    category=EnumMessageCategory.COMMAND,
    domain=MEMORY_DOMAIN,
    description="New node command request",
)
registered.append("ModelNewCommandRequest")
```

---

## MessageDispatchEngine Integration

**Factory**: `create_memory_dispatch_engine`
**File**: `src/omnimemory/runtime/dispatch_handlers.py`

`PluginMemory.wire_dispatchers()` calls `create_memory_dispatch_engine()` to build a frozen `MessageDispatchEngine` (from `omnibase_core.runtime.runtime_message_dispatch`) that routes all memory Kafka topics to their respective bridge handlers.

### Dispatch Routes

The engine is frozen with 4 handlers covering 6 routes:

| Handler ID | Route(s) | Topic Alias | Category | Status |
|------------|---------|-------------|----------|--------|
| `memory-intent-classified-handler` | `memory-intent-classified-route` | `onex.events.omniintelligence.intent-classified.v1` | EVENT | Active |
| `memory-intent-query-handler` | `memory-intent-query-route` | `onex.commands.omnimemory.intent-query-requested.v1` | COMMAND | Active |
| `memory-retrieval-handler` | `memory-retrieval-route` | `onex.commands.omnimemory.memory-retrieval-requested.v1` | COMMAND | Fail-fast |
| `memory-lifecycle-handler` | `memory-lifecycle-tick-route` | `onex.commands.omnimemory.runtime-tick.v1` | COMMAND | Fail-fast |
| `memory-lifecycle-handler` | `memory-lifecycle-archive-route` | `onex.commands.omnimemory.archive-memory.v1` | COMMAND | Fail-fast |
| `memory-lifecycle-handler` | `memory-lifecycle-expire-route` | `onex.commands.omnimemory.expire-memory.v1` | COMMAND | Fail-fast |

Routes marked "Fail-fast" raise `RuntimeError` on receipt to prevent silent data loss until the full handler wiring is complete.

### Topic Alias Convention

ONEX canonical topic naming uses `.cmd.` for commands and `.evt.` for events. `MessageDispatchEngine.dispatch()` calls `EnumMessageCategory.from_topic()`, which currently expects `.commands.` and `.events.`. The `canonical_topic_to_dispatch_alias` function in `contract_topics.py` bridges the gap:

```python
from omnimemory.runtime.contract_topics import canonical_topic_to_dispatch_alias

# "onex.cmd.omnimemory.intent-query-requested.v1"
# -> "onex.commands.omnimemory.intent-query-requested.v1"
alias = canonical_topic_to_dispatch_alias(topic)
```

Pre-computed aliases are defined as module-level constants in `dispatch_handlers.py`:

```python
DISPATCH_ALIAS_INTENT_CLASSIFIED         = "onex.events.omniintelligence.intent-classified.v1"
DISPATCH_ALIAS_INTENT_QUERY_REQUESTED    = "onex.commands.omnimemory.intent-query-requested.v1"
DISPATCH_ALIAS_RUNTIME_TICK              = "onex.commands.omnimemory.runtime-tick.v1"
DISPATCH_ALIAS_ARCHIVE_MEMORY            = "onex.commands.omnimemory.archive-memory.v1"
DISPATCH_ALIAS_EXPIRE_MEMORY             = "onex.commands.omnimemory.expire-memory.v1"
DISPATCH_ALIAS_MEMORY_RETRIEVAL_REQUESTED = "onex.commands.omnimemory.memory-retrieval-requested.v1"
```

### Dispatch Flow

```
Kafka message arrives on topic
        |
        v
create_dispatch_callback()    <-- per-topic, created in start_consumers
        |
        | deserializes bytes -> dict
        | extracts correlation_id from payload
        | wraps in ModelEventEnvelope
        |
        v
engine.dispatch(alias_topic, envelope)
        |
        | matches route by topic_pattern
        | calls registered bridge handler
        |
        v
Bridge handler (e.g., create_intent_classified_dispatch_handler)
        |
        | extracts payload from envelope
        | delegates to domain handler
        |
        v
ack or nack the original Kafka message
```

### Creating the Engine Directly (for testing)

```python
from omnimemory.runtime.dispatch_handlers import create_memory_dispatch_engine

engine = create_memory_dispatch_engine(
    intent_consumer=my_consumer,       # ProtocolIntentEventConsumer
    intent_query_handler=my_handler,   # ProtocolIntentQueryHandler
    publish_callback=my_publish_fn,    # optional: async (topic, dict) -> None
    publish_topics={                   # optional: from collect_publish_topics_for_dispatch()
        "intent_query": "onex.evt.omnimemory.intent-query-response.v1",
    },
)
# engine is already frozen; call engine.dispatch(topic, envelope) directly
```

---

## Contract-Driven Topic Discovery

**Module**: `src/omnimemory/runtime/contract_topics.py`

Topics are declared as the source of truth in each node's `contract.yaml` under the `event_bus` section. The `contract_topics` module reads those files at plugin startup using `importlib.resources` (ONEX I/O audit compliant) and returns the aggregate topic lists. There are no hardcoded topic lists anywhere in the runtime layer.

### The `subscribe_topics` Convention

Any node that participates in Kafka event routing must include an `event_bus` section in its `contract.yaml` with `event_bus_enabled: true`:

```yaml
# src/omnimemory/nodes/node_intent_query_effect/contract.yaml (excerpt)
event_bus:
  version:
    major: 1
    minor: 0
    patch: 0

  subscribe_topics:
    - "onex.cmd.omnimemory.intent-query-requested.v1"

  publish_topics:
    - "onex.evt.omnimemory.intent-query-response.v1"
```

An orchestrator node may declare multiple subscribe topics:

```yaml
# src/omnimemory/nodes/node_memory_lifecycle_orchestrator/contract.yaml (excerpt)
event_bus:
  subscribe_topics:
    - "onex.cmd.omnimemory.runtime-tick.v1"
    - "onex.cmd.omnimemory.archive-memory.v1"
    - "onex.cmd.omnimemory.expire-memory.v1"
```

### Scanned Node Packages

`contract_topics.py` scans these node packages (in order) to build the complete subscribe list:

```python
_OMNIMEMORY_EVENT_BUS_NODE_PACKAGES = [
    "omnimemory.nodes.node_intent_query_effect",
    "omnimemory.nodes.node_intent_storage_effect",
    "omnimemory.nodes.node_memory_retrieval_effect",
    "omnimemory.nodes.node_memory_storage_effect",
    "omnimemory.nodes.node_memory_lifecycle_orchestrator",
]
```

> Verified against `src/omnimemory/runtime/contract_topics.py` on 2026-08-25: 5
> packages, all `node_`-prefixed. A prior revision of this document listed 6
> packages including `intent_event_consumer_effect`, which no longer exists in
> this repository — corrected during migration.

### Public API

```python
from omnimemory.runtime.contract_topics import (
    collect_subscribe_topics_from_contracts,   # -> list[str]
    collect_publish_topics_for_dispatch,       # -> dict[str, str]  (key -> first topic)
    collect_all_publish_topics,                # -> list[str]
    canonical_topic_to_dispatch_alias,         # str -> str
)

# Used by PluginMemory at module import time:
MEMORY_SUBSCRIBE_TOPICS: list[str] = collect_subscribe_topics_from_contracts()

# Used by wire_dispatchers (run in asyncio.to_thread for sync filesystem I/O):
publish_topics = await asyncio.to_thread(collect_publish_topics_for_dispatch)
```

> **Note on module-level discovery**: `MEMORY_SUBSCRIBE_TOPICS` is computed at import time (synchronous filesystem I/O via `importlib.resources`). This is intentional: plugins are loaded during kernel startup before the async event loop begins, so synchronous discovery at import time is safe and avoids the need for an `asyncio.to_thread` wrapper. The publish variant (`collect_publish_topics_for_dispatch`) is called later inside `wire_dispatchers` — at that point the event loop is already running, so it is wrapped in `asyncio.to_thread` to keep the async handler non-blocking.

If a `contract.yaml` is missing, contains invalid YAML, or belongs to a package that is not installed, that package is skipped with a warning log. A single broken contract does not prevent discovery from all other contracts.

### How Topics Are Discovered at Startup

1. `PluginMemory` is imported. The module-level statement `MEMORY_SUBSCRIBE_TOPICS = collect_subscribe_topics_from_contracts()` executes immediately.
2. `collect_subscribe_topics_from_contracts` iterates `_OMNIMEMORY_EVENT_BUS_NODE_PACKAGES`, reads each `contract.yaml` via `importlib.resources.files(package).joinpath("contract.yaml")`, parses YAML, and extracts `event_bus.subscribe_topics`.
3. The aggregate list is stored as `MEMORY_SUBSCRIBE_TOPICS`.
4. In `start_consumers`, the plugin iterates `MEMORY_SUBSCRIBE_TOPICS` and calls `event_bus.subscribe(topic=topic, ...)` for each entry.

### Adding a New Subscribing Node

1. Add `event_bus_enabled: true` and `subscribe_topics` to the node's `contract.yaml`.
2. Add the node's Python package path to `_OMNIMEMORY_EVENT_BUS_NODE_PACKAGES` in `contract_topics.py`.
3. Register a dispatch route in `create_memory_dispatch_engine` (`dispatch_handlers.py`).
4. Define the dispatch alias constant and call `canonical_topic_to_dispatch_alias` in the plugin's `_build_topic_handlers`.

---

## Protocol Adapters

**File**: `src/omnimemory/runtime/adapters.py`

Per ARCH-002, no handler or node file may import directly from transport modules (`aiokafka`, `omnibase_infra.event_bus`). All event bus interaction goes through the protocol interfaces defined in `adapters.py`.

### Protocols

| Protocol | Purpose |
|----------|---------|
| `ProtocolEventBusPublish` | `async publish(topic, key, value: bytes)` |
| `ProtocolEventBusHealthCheck` | `async health_check() -> dict` |
| `ProtocolEventBusLifecycle` | `async initialize(config)` / `async shutdown()` |

### AdapterKafkaPublisher

`AdapterKafkaPublisher` wraps a `ProtocolEventBusPublish` event bus and provides a handler-friendly interface that accepts `Mapping[str, object]` values (serialized to compact JSON bytes internally):

```python
from omnimemory.runtime.adapters import AdapterKafkaPublisher

publisher = AdapterKafkaPublisher(event_bus)

# Handlers call this interface -- no direct aiokafka imports
await publisher.publish(
    topic="onex.evt.omnimemory.intent-query-response.v1",
    key=None,
    value={"query_id": "abc", "status": "success"},
)
```

The factory `create_default_event_bus(bootstrap_servers)` constructs an `EventBusKafka` instance from `omnibase_infra` without exposing the concrete class to domain code.

---

## Node Introspection

**File**: `src/omnimemory/runtime/introspection.py`

During `wire_dispatchers`, the plugin publishes STARTUP introspection events for all 9 memory nodes so the platform registration orchestrator can discover them. Effect nodes additionally start heartbeat background tasks (every 30 seconds by default). During shutdown, the plugin publishes SHUTDOWN events and stops heartbeat tasks.

### Registered Memory Nodes

`MEMORY_NODES` is no longer a hardcoded tuple. It is built dynamically at module import time via contract discovery:

```python
MEMORY_NODES: tuple[_NodeDescriptor, ...] = discover_memory_nodes()
```

`discover_memory_nodes()` calls `_discover_nodes_from_contracts(base_package="omnimemory.nodes")`, which scans every `node_*/contract.yaml` under the `omnimemory.nodes` package using `importlib.resources`. Each contract's `node_type` field determines the `EnumNodeKind`. Nodes without a `contract.yaml` are skipped automatically.

This means the registered set reflects the actual on-disk contracts at import time. As of 2026-08-25, 13 nodes with `contract.yaml` are discovered (verified via `git ls-files src/omnimemory/nodes/`; see [ONEX Four-Node Architecture](../architecture/omnimemory-four-node-architecture.md) for the full inventory).

Node IDs are deterministic: `uuid5(NAMESPACE_DNS, f"omnimemory.{node_name}")`. This ensures STARTUP and SHUTDOWN events for the same logical node always carry the same `node_id`, regardless of which proxy object published them.
