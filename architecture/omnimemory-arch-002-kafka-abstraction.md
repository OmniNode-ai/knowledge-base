---
type: architecture
status: accepted
date: "2026-08-25"
title: "ARCH-002: Kafka Abstraction Rule (OmniMemory)"
topics:
  - omnimemory
  - kafka
  - event-bus
  - architecture
refs:
  - architecture/omnimemory-four-node-architecture.md
---

# ARCH-002: Kafka Abstraction Rule

> **Version**: 0.1.1
> **Last Updated**: 2026-08-25 — migrated from `omnimemory` to the knowledge base. The illustrative `subscribe_topics` example below previously used `intent_event_consumer_effect`, a node that has since been removed from `omnimemory` (its consumer role was consolidated into `omnimarket`). Reworded the example as an illustrative pattern rather than a still-live file path — the rule and CI enforcement described here are unaffected and remain active.
> **Status**: Active — enforced by CI lint guard

## Overview

ARCH-002 prohibits direct `aiokafka`, `kafka`, or `confluent_kafka` imports
inside `omnimemory/nodes/`. All event bus interaction must go through the
`ProtocolEventBusPublish` protocol defined in `omnimemory.runtime.adapters`.
Concrete transport wiring lives exclusively in the runtime layer.

This rule prevents handler code from coupling to a specific Kafka client
library, making transport swappable and keeping handlers testable in isolation.

---

## The Rule

**No node file may import directly from `aiokafka`, `kafka`,
`confluent_kafka`, or any other transport module.**

| Context | Allowed |
|---------|---------|
| `omnimemory/nodes/**/*.py` | Protocol interfaces only — enforced by CI |
| `omnimemory/runtime/**/*.py` | Direct transport imports allowed |
| `if TYPE_CHECKING:` blocks | Allowed (never executed at runtime) |
| `# omnimemory-kafka-exempt:` annotation | Allowed (explicit bypass with reason) |

> **Note on scope**: The CI lint guard enforces the no-direct-import rule on `omnimemory/nodes/**/*.py` only. The BEFORE/AFTER examples in this document use a file from `omnimemory/handlers/` to illustrate the architectural intent — the same principle (avoid coupling application code to a specific Kafka client) applies broadly to any code outside the runtime layer, even if the CI guard does not cover every such path explicitly.

---

## Pattern: subscribe_topics

Handlers that need to consume from Kafka declare their topics declaratively in
their config model using the `subscribe_topics` list field. This matches the
`event_bus.subscribe_topics` contract format that `EventBusSubcontractWiring`
uses for declarative wiring.

The runtime layer injects a subscribe callback — the handler never imports or
instantiates a Kafka consumer directly.

**Config model** (illustrative — `ModelMyConsumerConfig`):

```python
# src/omnimemory/nodes/my_consumer_effect/models/model_consumer_config.py

from pydantic import BaseModel, ConfigDict, Field

class ModelMyConsumerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    # Topic suffixes — env prefix ("dev.", "staging.") added at runtime
    subscribe_topics: list[str] = Field(
        default=["onex.evt.omniintelligence.intent-classified.v1"],
        description="Topic suffixes to subscribe to (env prefix added at runtime)",
    )
    publish_topics: list[str] = Field(
        default=["onex.evt.omnimemory.intent-stored.v1"],
        description="Topic suffixes to publish to (env prefix added at runtime)",
    )
    dlq_topics: list[str] = Field(
        default=["onex.evt.omniintelligence.intent-classified.v1.dlq"],
        description="Dead letter queue topic suffixes",
    )
```

**Handler initialization** (illustrative — `HandlerMyConsumer`):

```python
# src/omnimemory/nodes/my_consumer_effect/handler_my_consumer.py

async def initialize(
    self,
    subscribe_callback: Callable[
        [str, Callable[[dict[str, object]], None]], Callable[[], None]
    ],
    env_prefix: str = "dev",
    publish_callback: Callable[[str, dict[str, object]], None] | None = None,
) -> None:
    """Initialize event bus subscriptions.

    subscribe_callback is injected by the runtime layer (e.g., EventBusKafka.subscribe).
    The handler never imports aiokafka directly.
    """
    for topic_suffix in self._config.subscribe_topics:
        full_topic = f"{env_prefix}.{topic_suffix}"
        unsubscribe = subscribe_callback(full_topic, self._handle_message_sync)
        self._unsubscribe_fns.append(unsubscribe)
```

The handler receives a callable, not a Kafka client. The runtime provides the
concrete `EventBusKafka.subscribe` at wiring time.

---

## Pattern: ProtocolEventBusPublish

For publishing events, handlers depend on `ProtocolEventBusPublish` from
`omnimemory.runtime.adapters`. They never import `AIOKafkaProducer`.

```python
# src/omnimemory/runtime/adapters.py

from typing import Protocol, runtime_checkable

@runtime_checkable
class ProtocolEventBusPublish(Protocol):
    """Minimal protocol for event bus publish capability."""

    async def publish(
        self,
        topic: str,
        key: bytes | None,
        value: bytes,
    ) -> None: ...
```

`AdapterKafkaPublisher` wraps a `ProtocolEventBusPublish`-conforming event bus
into the higher-level dict-based publish interface used by `HandlerSubscription`:

```python
# src/omnimemory/runtime/adapters.py

from collections.abc import Mapping

class AdapterKafkaPublisher:
    """Thin adapter: Mapping[str, object] -> ProtocolEventBusPublish.publish()."""

    def __init__(self, event_bus: ProtocolEventBusPublish) -> None:
        self._event_bus = event_bus

    async def publish(
        self,
        topic: str,
        key: str | None,
        value: Mapping[str, object],
    ) -> None:
        ...
```

---

## BEFORE and AFTER Examples

### BEFORE (violates ARCH-002)

```python
# src/omnimemory/handlers/handler_subscription.py  -- OLD, WRONG

from aiokafka import AIOKafkaProducer  # VIOLATION: direct transport import

class HandlerSubscription:
    async def initialize(self, config: ModelHandlerSubscriptionConfig) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=config.kafka_bootstrap_servers,
        )
        self._config = config
        await self._producer.start()

    async def notify(self, topic: str, event: ModelNotificationEvent) -> None:
        value = json.dumps(event.model_dump(mode="json")).encode()
        await self._producer.send(self._config.kafka_notification_topic, value=value)
```

Problems:
- `HandlerSubscription` is directly coupled to `aiokafka`.
- Switching to `confluent_kafka` or an in-memory bus requires touching the handler.
- Tests must spin up a real Kafka broker or mock internal `aiokafka` internals.

### AFTER (ARCH-002 compliant)

```python
# src/omnimemory/handlers/handler_subscription.py  -- CORRECT

from typing import cast

from omnimemory.runtime.adapters import (
    AdapterKafkaPublisher,
    ProtocolEventBusPublish,
    create_default_event_bus,
)

class HandlerSubscription:
    async def initialize(
        self,
        config: ModelHandlerSubscriptionConfig,
        event_bus: ProtocolEventBusPublish | None = None,
    ) -> None:
        # ARCH-002 compliant: accept protocol, create via factory if not provided
        if event_bus is None:
            event_bus = await create_default_event_bus(
                bootstrap_servers=config.kafka_bootstrap_servers,
            )
        self._event_bus = event_bus
        self._publisher = AdapterKafkaPublisher(event_bus)
        self._notification_topic = config.kafka_notification_topic

    async def notify(self, topic: str, event: ModelNotificationEvent) -> None:
        event_payload = cast(dict[str, object], event.model_dump(mode="json"))
        # Delegates to protocol adapter -- no aiokafka anywhere in this file
        await self._publisher.publish(
            topic=self._notification_topic,
            key=topic,
            value=event_payload,
        )
```

Benefits:
- `HandlerSubscription` depends on `ProtocolEventBusPublish`, not `aiokafka`.
- Tests inject `EventBusInmemory` or any other conforming implementation.
- Transport is swappable by changing the factory in `runtime/adapters.py`.

---

## CI Enforcement

Two CI lint guards enforce ARCH-002:

### 1. Kafka Import Guard (`scripts/validation/validate_kafka_imports.py`)

Scans all `*.py` files under `omnimemory/nodes/` for direct Kafka imports.
Flags `aiokafka`, `kafka`, `confluent_kafka`. Respects:

- `if TYPE_CHECKING:` blocks (imports not executed at runtime)
- `# omnimemory-kafka-exempt: <reason>` inline annotation (explicit bypass)

Tested in `tests/unit/test_validate_kafka_imports.py`.

### 2. Transport Import Guard (`scripts/validate_no_transport_imports.py`)

AST-based scanner covering a broader set of banned transport modules:
`aiokafka`, `kafka`, `confluent_kafka`, `httpx`, `redis`, `asyncpg`, `grpc`,
`websockets`, `requests`, `aiohttp`, `celery`. This list is not exhaustive —
see the `omnimemory` repository's `docs/ci/CI_MONITORING_GUIDE.md` for the
complete banned module table, which additionally covers `urllib3`, `aioredis`,
`psycopg2`, `psycopg`, `aiomysql`, `pika`, `aio_pika`, `kombu`, and `wsproto`.
Supports a YAML whitelist (`tests/audit/transport_import_whitelist.yaml`) for intentional exceptions.

Tested in `tests/unit/test_validate_no_transport_imports.py`.

For guidance on running these checks locally and triaging failures, see the
`omnimemory` repository's `docs/ci/CI_MONITORING_GUIDE.md` (not yet migrated
to this knowledge base).

---

## Files Migrated to ARCH-002 Compliance

The following files were migrated to ARCH-002 compliance (PR #40):

| File | What changed |
|------|-------------|
| `src/omnimemory/handlers/handler_subscription.py` | Replaced direct `AIOKafkaProducer` with `ProtocolEventBusPublish` protocol injection via `create_default_event_bus` factory |
| `src/omnimemory/runtime/adapters.py` | Created — defines `ProtocolEventBusPublish`, `ProtocolEventBusLifecycle`, `ProtocolEventBusHealthCheck`, `AdapterKafkaPublisher`, and `create_default_event_bus` factory |

The CI lint guard (PR #42) was added as a follow-up to prevent
regressions.

---

## Runtime Wiring Location

The only place in `omnimemory` that may import transport modules directly is
`omnimemory/runtime/`. The `create_default_event_bus` factory in
`omnimemory.runtime.adapters` constructs the concrete `EventBusKafka` from
`omnibase_infra` and returns a `ProtocolEventBusPublish`-conforming object.

```python
# omnimemory/runtime/adapters.py (concrete wiring -- allowed here)

async def create_default_event_bus(
    bootstrap_servers: str,
) -> ProtocolEventBusPublish:
    """Create a default EventBusKafka instance.

    This is the only place in omnimemory that may reference omnibase_infra.event_bus
    directly. All handler code receives the result as ProtocolEventBusPublish.
    """
    from omnibase_infra.event_bus import EventBusKafka  # allowed in runtime only
    bus = EventBusKafka(bootstrap_servers=bootstrap_servers)
    await bus.start()
    return bus
```
