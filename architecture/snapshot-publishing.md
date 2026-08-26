---
type: architecture
status: accepted
date: "2026-07-21"
title: "Snapshot Publishing Architecture"
topics: [omnibase-infra, snapshot, publishing]
refs: []
---


# Snapshot Publishing Architecture

## Overview

Snapshots are **compacted, read-optimized views** of entity state derived from projections. They enable fast O(1) state reconstruction for orchestrators and read models without replaying the full event log.

### What are Snapshots?

Snapshots are point-in-time captures of entity state published to Kafka compacted topics. They serve as a read optimization layer that sits above the immutable event log:

- **Events**: Immutable facts that happened (source of truth)
- **Projections**: Materialized views built from events (stored in PostgreSQL)
- **Snapshots**: Compacted views of projections (published to Kafka)

### Why Use Snapshots?

| Benefit | Description |
|---------|-------------|
| **Fast State Queries** | O(1) lookups vs O(n) event replay |
| **Reduced Database Load** | Orchestrators read from Kafka, not PostgreSQL |
| **Compacted Storage** | Only latest state per entity retained after compaction |
| **Service Discovery** | Quick queries for active nodes and capabilities |
| **Status Dashboards** | Current registration states without full projection queries |

### Key Principle: Snapshots are OPTIONAL

```
CRITICAL: Snapshots are a READ OPTIMIZATION and NEVER replace the event log.

- The event log is the authoritative source of truth
- Projections are derived from events and stored in PostgreSQL
- Snapshots are derived from projections for fast reads
- Snapshots can be rebuilt from projections at any time
- If snapshots are lost, rebuild from projections - no data loss
```

## Architecture

### Data Flow

```
                            Source of Truth
                                  |
                                  v
+------------------+        +------------------+        +------------------+
|                  |        |                  |        |                  |
|   Event Log      |  --->  |   Projections    |  --->  |   Snapshots      |
|   (Kafka)        |        |   (PostgreSQL)   |        |   (Kafka)        |
|                  |        |                  |        |                  |
+------------------+        +------------------+        +------------------+
     |                           |                           |
     | cleanup.policy=delete     | Materialized              | cleanup.policy=compact
     | Immutable history         | Read model                | Only latest per entity
     | Time-based retention      | Full state                | Fast reads
     |                           |                           |
     v                           v                           v
  Replay for                 Query for                   Quick state
  full history               workflow decisions          lookups
```

### Component Diagram

```
+------------------------------------------------------------------+
|                     Registration Pipeline                         |
+------------------------------------------------------------------+
|                                                                  |
|   1. Events              2. Projector            3. Publisher    |
|        |                      |                       |          |
|        | NodeRegistered       | Persist               | Publish  |
|        | Heartbeat            | projection            | snapshot |
|        | StateChanged         | to PostgreSQL         | to Kafka |
|        |                      |                       |          |
|        v                      v                       v          |
|   +-----------+         +-----------+          +------------+    |
|   |  Kafka    |  --->   | Projector |  --->    | Snapshot   |    |
|   |  Events   |         | Reducer   |          | Publisher  |    |
|   +-----------+         +-----------+          +------------+    |
|        |                      |                       |          |
|        | RegistrationEvent    | ModelRegistration     | Compacted|
|        | HeartbeatReceived    | Projection            | snapshot |
|        | TimeoutEmitted       |                       | topic    |
|                                                                  |
+------------------------------------------------------------------+
                                                       |
                                                       v
                                              +---------------+
                                              | Orchestrators |
                                              | Read Models   |
                                              | Dashboards    |
                                              +---------------+
```

### Kafka Topic Configuration

Snapshot topics use **log compaction** (`cleanup.policy=compact`) to retain only the latest snapshot per entity. This is fundamentally different from event topics:

| Property | Event Topics | Snapshot Topics |
|----------|--------------|-----------------|
| `cleanup.policy` | `delete` | `compact` |
| Retention | Time-based | Key-based (latest only) |
| History | Full history | Only current state |
| Rebuild | Cannot rebuild | Rebuild from projections |

### Key Format

Snapshot keys are the **node UUID only**, as returned by `ModelRegistrationSnapshot.to_kafka_key()`:

```text
550e8400-e29b-41d4-a716-446655440000
```

This ensures:
- Per-node compaction (only latest snapshot per node survives)
- Consistent ordering within the same entity

## Snapshot Format

### ModelRegistrationSnapshot

The `ModelRegistrationSnapshot` model represents a compacted registration state:

```python
from datetime import datetime
from pydantic import BaseModel

class ModelRegistrationSnapshot(BaseModel):
    """Compacted registration snapshot for read optimization."""

    # Identity (composite key: entity_id + domain)
    entity_id: str                    # Node identifier (partition key)
    domain: str = "registration"      # Domain namespace

    # FSM State
    current_state: EnumRegistrationState  # Current FSM state

    # Node Information
    node_type: str | None             # effect, compute, reducer, orchestrator
    node_name: str | None             # Human-readable node name
    capabilities: ModelNodeCapabilities | None  # Node capabilities

    # State Change Tracking
    last_state_change_at: datetime    # When current_state last changed

    # Snapshot Versioning
    snapshot_version: int             # Monotonic version for compaction
    snapshot_created_at: datetime     # When snapshot was created

    # Traceability
    source_projection_sequence: int | None  # Source projection sequence
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `entity_id` | `str` | Node identifier, used as partition key for ordering |
| `domain` | `str` | Domain namespace for multi-domain support (default: `"registration"`) |
| `current_state` | `EnumRegistrationState` | Current FSM state (ACTIVE, PENDING_REGISTRATION, etc.) |
| `node_type` | `str \| None` | ONEX node type: `effect`, `compute`, `reducer`, `orchestrator` |
| `node_name` | `str \| None` | Human-readable node name from introspection |
| `capabilities` | `ModelNodeCapabilities \| None` | Node capabilities at registration time |
| `last_state_change_at` | `datetime` | Timestamp of most recent state transition |
| `snapshot_version` | `int` | Monotonically increasing version for conflict resolution |
| `snapshot_created_at` | `datetime` | When this snapshot was created |
| `source_projection_sequence` | `int \| None` | Source projection sequence for traceability |

### Registration States

Snapshots capture the following FSM states:

| State | Description | Terminal |
|-------|-------------|----------|
| `pending_registration` | Initial state after registration initiated | No |
| `accepted` | Registration accepted, awaiting acknowledgment | No |
| `awaiting_ack` | Waiting for node to acknowledge | No |
| `ack_received` | Node acknowledged, transitioning to active | No |
| `active` | Node is fully active and healthy | No |
| `ack_timed_out` | Acknowledgment deadline passed (retriable) | No |
| `rejected` | Registration rejected (terminal) | Yes |
| `liveness_expired` | Liveness check failed (terminal) | Yes |

### JSON Example

```json
{
  "entity_id": "550e8400-e29b-41d4-a716-446655440000",
  "domain": "registration",
  "current_state": "active",
  "node_type": "effect",
  "node_name": "PostgresAdapter",
  "capabilities": {
    "supported_operations": ["query", "insert", "update", "delete"],
    "protocols": ["ProtocolDatabaseAdapter", "ProtocolHealthCheck"],
    "max_concurrent_requests": 100
  },
  "last_state_change_at": "2025-01-15T10:30:00Z",
  "snapshot_version": 42,
  "snapshot_created_at": "2025-01-15T10:31:00Z",
  "source_projection_sequence": 12345
}
```

### Key Differences from Projection

| Aspect | Projection | Snapshot |
|--------|------------|----------|
| **Mutability** | Mutable (`frozen=False`) | Immutable (`frozen=True`) |
| **Timeout Fields** | Has `ack_deadline`, `liveness_deadline` | No timeout fields |
| **Event Tracking** | Has `last_applied_event_id`, `last_applied_offset` | Has `source_projection_sequence` |
| **Storage** | PostgreSQL | Kafka (compacted topic) |
| **Purpose** | Workflow decisions with full context | Fast read queries |

## Usage

### Publishing Snapshots

Use `SnapshotPublisherRegistration` to publish snapshots to Kafka:

```python
from aiokafka import AIOKafkaProducer
from omnibase_infra.projectors import SnapshotPublisherRegistration
from omnibase_infra.models.projection import ModelSnapshotTopicConfig

# Create producer and config
producer = AIOKafkaProducer(bootstrap_servers="localhost:19092")
config = ModelSnapshotTopicConfig.default()

# Initialize publisher
publisher = SnapshotPublisherRegistration(producer, config)
await publisher.start()

try:
    # Publish snapshot from projection (recommended - handles versioning)
    snapshot = await publisher.publish_from_projection(
        projection=projection,
        node_name="PostgresAdapter",
    )
    print(f"Published snapshot version {snapshot.snapshot_version}")

    # Batch publish for bulk operations
    count = await publisher.publish_batch(projections)
    print(f"Published {count} snapshots")

    # Delete snapshot (publish tombstone)
    deleted = await publisher.delete_snapshot("entity-123", "registration")
    if deleted:
        print("Snapshot deleted")

finally:
    await publisher.stop()
```

### Consuming Snapshots

To consume snapshots, use a Kafka consumer configured to read from the compacted topic:

```python
from aiokafka import AIOKafkaConsumer
import json

consumer = AIOKafkaConsumer(
    "onex.registration.snapshots",
    bootstrap_servers="localhost:19092",
    auto_offset_reset="earliest",
    group_id="snapshot-reader",
)
await consumer.start()

try:
    async for message in consumer:
        if message.value is None:
            # Tombstone - entity was deleted
            key = message.key.decode("utf-8")
            print(f"Entity deleted: {key}")
            continue

        # Parse snapshot
        snapshot_data = json.loads(message.value.decode("utf-8"))
        snapshot = ModelRegistrationSnapshot(**snapshot_data)

        # Use snapshot for queries
        if snapshot.is_active():
            print(f"Active node: {snapshot.node_name}")

finally:
    await consumer.stop()
```

### Building a Snapshot Cache

For high-performance reads, build an in-memory cache from the compacted topic:

```python
class SnapshotCache:
    """In-memory cache built from Kafka compacted topic."""

    def __init__(self):
        self._cache: dict[str, ModelRegistrationSnapshot] = {}

    async def load_from_topic(
        self,
        consumer: AIOKafkaConsumer,
        timeout_ms: int = 5000,
    ) -> None:
        """Load all snapshots from topic into cache.

        Note: Uses getmany with timeout to avoid infinite waiting.
        The async for pattern would wait indefinitely for new messages
        after reaching the end of the topic.
        """
        # Seek to beginning to load full state
        await consumer.seek_to_beginning()

        while True:
            # Poll with timeout - returns empty dict when no more messages
            messages = await consumer.getmany(timeout_ms=timeout_ms)
            if not messages:
                break  # No more messages within timeout

            for tp, msgs in messages.items():
                for message in msgs:
                    key = message.key.decode("utf-8")

                    if message.value is None:
                        # Tombstone - remove from cache
                        self._cache.pop(key, None)
                    else:
                        # Update cache with latest snapshot
                        data = json.loads(message.value.decode("utf-8"))
                        self._cache[key] = ModelRegistrationSnapshot(**data)

    def get_active_nodes(self) -> list[ModelRegistrationSnapshot]:
        """Query for all active nodes."""
        return [s for s in self._cache.values() if s.is_active()]

    def get_by_type(self, node_type: str) -> list[ModelRegistrationSnapshot]:
        """Query for nodes by type."""
        return [s for s in self._cache.values() if s.node_type == node_type]
```

### When to Publish Snapshots

| Trigger | Description |
|---------|-------------|
| **After Projection Update** | Publish immediately after projector persists state change |
| **On Schedule** | Periodic batch publish (e.g., every 5 minutes) for consistency |
| **On State Transition** | Publish when FSM state changes (ACTIVE, LIVENESS_EXPIRED) |
| **On Demand** | Manual publish for specific entities |

```python
# Example: Publish after projection update
async def on_projection_updated(projection: ModelRegistrationProjection) -> None:
    """Callback after projector persists update."""
    snapshot = await publisher.publish_from_projection(
        projection=projection,
        node_name=await get_node_name(projection.entity_id),
    )
    logger.info(
        "Published snapshot version %d for %s",
        snapshot.snapshot_version,
        projection.entity_id,
    )
```

## Topic Configuration

### ModelSnapshotTopicConfig

Configure Kafka snapshot topics with `ModelSnapshotTopicConfig`:

```python
from omnibase_infra.models.projection import ModelSnapshotTopicConfig

# Use defaults (recommended for development)
config = ModelSnapshotTopicConfig.default()

# Custom configuration for production
config = ModelSnapshotTopicConfig(
    topic="prod.registration.snapshots.v1",
    partition_count=24,
    replication_factor=3,
    cleanup_policy="compact",
    min_compaction_lag_ms=120000,  # 2 minutes
    max_compaction_lag_ms=600000,  # 10 minutes
    segment_bytes=52428800,        # 50MB
    retention_ms=-1,               # Infinite
    min_insync_replicas=2,
)

# Load from YAML
config = ModelSnapshotTopicConfig.from_yaml(Path("config/snapshot_topic.yaml"))
```

### Default Values

| Setting | Default | Description |
|---------|---------|-------------|
| `topic` | `onex.registration.snapshots` | ONEX topic naming |
| `partition_count` | 12 | Match projection partitioning |
| `replication_factor` | 3 | High durability |
| `cleanup_policy` | `compact` | Required for snapshots |
| `min_compaction_lag_ms` | 60000 (1 min) | Minimum before compaction |
| `max_compaction_lag_ms` | 300000 (5 min) | Maximum before forced compaction |
| `segment_bytes` | 104857600 (100MB) | Segment size |
| `retention_ms` | -1 (infinite) | Required for compaction |
| `min_insync_replicas` | 2 | Write durability |

### Compaction Settings Explained

```
Compaction Timeline:
|------ min_compaction_lag_ms ------|------ max_compaction_lag_ms ------|
|<--- Cannot compact here --->|<--- May compact --->|<--- Must compact --->|
```

- **`min_compaction_lag_ms`**: Minimum time before a message can be compacted. Prevents very recent snapshots from being compacted immediately, useful if consumers are slightly behind.

- **`max_compaction_lag_ms`**: Maximum time before compaction is forced. Ensures stale snapshots are cleaned up in a timely manner.

- **`segment_bytes`**: Smaller segments = more frequent compaction but higher I/O. Larger segments = less compaction overhead but more space usage.

### ONEX Topic Naming Convention

Snapshot topics follow ONEX topic taxonomy:

```
Standard:     onex.<domain>.snapshots
Environment:  <env>.<domain>.snapshots.v<version>

Examples:
  - onex.registration.snapshots
  - dev.registration.snapshots.v1
  - prod.discovery.snapshots.v1
```

### Environment Variable Overrides

```bash
# Override topic configuration via environment
export SNAPSHOT_TOPIC="prod.registration.snapshots.v1"
export SNAPSHOT_PARTITION_COUNT="24"
export SNAPSHOT_REPLICATION_FACTOR="3"
export SNAPSHOT_MIN_COMPACTION_LAG_MS="120000"
export SNAPSHOT_MAX_COMPACTION_LAG_MS="600000"
export SNAPSHOT_SEGMENT_BYTES="52428800"
export SNAPSHOT_RETENTION_MS="-1"
export SNAPSHOT_MIN_INSYNC_REPLICAS="2"
```

### Kafka Config Dictionary

Convert to Kafka AdminClient format:

```python
config = ModelSnapshotTopicConfig.default()
kafka_config = config.to_kafka_config()

# Result:
# {
#     "cleanup.policy": "compact",
#     "min.compaction.lag.ms": "60000",
#     "max.compaction.lag.ms": "300000",
#     "segment.bytes": "104857600",
#     "retention.ms": "-1",
#     "min.insync.replicas": "2",
# }
```

## Best Practices

### 1. Always Derive from Projections

Snapshots should always be derived from projections, never directly from events:

```python
# CORRECT: Derive from projection
snapshot = ModelRegistrationSnapshot.from_projection(
    projection=projection,
    snapshot_version=next_version,
    snapshot_created_at=datetime.now(UTC),
    node_name=node_name,
)

# WRONG: Build directly from event (bypasses projection)
# snapshot = ModelRegistrationSnapshot(
#     entity_id=event.entity_id,
#     current_state=event.new_state,  # May be inconsistent
#     ...
# )
```

### 2. Use Version Tracking for Conflict Resolution

Snapshots include `snapshot_version` for ordering and conflict resolution:

```python
# Publisher handles versioning automatically
snapshot = await publisher.publish_from_projection(projection)
print(f"Version: {snapshot.snapshot_version}")  # Monotonically increasing

# For manual versioning
if snapshot_a.is_newer_than(snapshot_b):
    # snapshot_a has higher version
    use_snapshot(snapshot_a)
```

### 3. Handle Tombstones for Entity Deletion

Publish tombstones (null values) to remove entities during compaction:

```python
# Delete snapshot when node deregisters
deleted = await publisher.delete_snapshot(
    entity_id=str(node_id),
    domain="registration",
)

if deleted:
    logger.info(f"Snapshot deleted for {node_id}")
else:
    logger.warning(f"Failed to delete snapshot for {node_id}")
```

### 4. Use Circuit Breaker for Resilience

The `SnapshotPublisherRegistration` includes a circuit breaker:

```python
# Circuit breaker configuration (defaults)
# - threshold: 5 failures before opening
# - reset_timeout: 60 seconds before auto-reset

# When circuit is open, InfraUnavailableError is raised
try:
    await publisher.publish_snapshot(snapshot)
except InfraUnavailableError as e:
    logger.warning(f"Circuit breaker open: {e}")
    # Wait for circuit to reset or use fallback
```

### 5. Batch Operations for Bulk Publishing

Use batch methods for periodic snapshot jobs:

```python
# Efficient batch publishing
projections = await projection_reader.get_all()
count = await publisher.publish_batch(projections)
logger.info(f"Published {count}/{len(projections)} snapshots")
```

### 6. Monitor Compaction Lag

Track compaction metrics to ensure snapshots are being cleaned up:

```bash
# Kafka CLI to check compaction lag
kafka-consumer-groups.sh --bootstrap-server localhost:19092 \
    --describe --group snapshot-reader

# Monitor topic size (should stabilize after compaction)
kafka-log-dirs.sh --bootstrap-server localhost:19092 \
    --describe --topic-list onex.registration.snapshots
```

## Error Handling

The snapshot publisher uses ONEX infrastructure error types:

| Error | Cause | Recovery |
|-------|-------|----------|
| `InfraConnectionError` | Kafka unavailable | Retry with backoff |
| `InfraTimeoutError` | Publish timed out | Retry or skip |
| `InfraUnavailableError` | Circuit breaker open | Wait for reset |

```python
from omnibase_infra.errors import (
    InfraConnectionError,
    InfraTimeoutError,
    InfraUnavailableError,
)

try:
    await publisher.publish_snapshot(snapshot)
except InfraUnavailableError:
    # Circuit open - wait for reset
    logger.warning("Kafka unavailable, snapshot publish deferred")
except InfraTimeoutError:
    # Publish timed out - retry or skip
    logger.warning("Snapshot publish timed out, will retry")
except InfraConnectionError:
    # Connection failed - retry with backoff
    logger.error("Kafka connection failed, applying backoff")
    await asyncio.sleep(backoff_seconds)
```

## Operational Reference

### Topic Name and Config Source

**Topic Name**: `onex.snapshot.platform.registration-snapshots.v1`

**Programmatic Config Source**: `src/omnibase_infra/models/projection/model_snapshot_topic_config.py` (`ModelSnapshotTopicConfig`)

**Infrastructure**: Redpanda (Kafka-compatible) running on `localhost:19092`

### Key Format and Compaction Behavior

Kafka compaction uses the message **key** to determine which records to retain. For this topic, the key is the **node_id as a UUID string only**.

Example key: `550e8400-e29b-41d4-a716-446655440000`

This means compaction retains exactly one record per node. The key format is defined by `ModelRegistrationSnapshot.to_kafka_key()` which returns `str(self.entity_id)`.

### Creating the Topic

**Production (multi-broker cluster)**:

```bash
rpk topic create onex.snapshot.platform.registration-snapshots.v1 \
  --brokers localhost:19092 \
  --partitions 12 \
  --replicas 3 \
  --topic-config cleanup.policy=compact \
  --topic-config min.compaction.lag.ms=60000 \
  --topic-config max.compaction.lag.ms=300000 \
  --topic-config segment.bytes=104857600 \
  --topic-config retention.ms=-1 \
  --topic-config min.insync.replicas=2
```

**Development (single-node Redpanda)**:

```bash
rpk topic create onex.snapshot.platform.registration-snapshots.v1 \
  --brokers localhost:19092 \
  --partitions 12 \
  --replicas 1 \
  --topic-config cleanup.policy=compact \
  --topic-config min.compaction.lag.ms=60000 \
  --topic-config max.compaction.lag.ms=300000 \
  --topic-config segment.bytes=104857600 \
  --topic-config retention.ms=-1 \
  --topic-config min.insync.replicas=1
```

Single-node Redpanda cannot honor `replication_factor > 1` or `min.insync.replicas > 1`. Always use `1` for both when targeting a single-node development instance.

### Development vs Production Settings

| Setting | Development (single-node) | Production (multi-broker) |
|---------|---------------------------|---------------------------|
| `--replicas` | `1` | `3` |
| `min.insync.replicas` | `1` | `2` |
| `--partitions` | `12` | `12` (increase if needed) |
| All other config | Same | Same |

### Verifying Topic Configuration

```bash
# Check that the topic exists
rpk topic list --brokers localhost:19092

# Describe topic configuration (full)
rpk topic describe onex.snapshot.platform.registration-snapshots.v1 \
  --brokers localhost:19092

# Describe topic configuration only
rpk topic describe onex.snapshot.platform.registration-snapshots.v1 \
  --brokers localhost:19092 \
  -c
```

Verify that `cleanup.policy=compact`, `min.compaction.lag.ms=60000`, `max.compaction.lag.ms=300000`, `segment.bytes=104857600`, `retention.ms=-1`, and `min.insync.replicas` matches your environment.

### Debugging: Reading Messages from the Topic

```bash
# Read all current snapshots
rpk topic consume onex.snapshot.platform.registration-snapshots.v1 \
  --brokers localhost:19092 \
  --offset start \
  --format '%k\t%v\n'

# Read a limited number of messages
rpk topic consume onex.snapshot.platform.registration-snapshots.v1 \
  --brokers localhost:19092 \
  --offset start \
  --num 10 \
  --format '%k\t%v\n'

# Read messages with full metadata (partition, offset, timestamp)
rpk topic consume onex.snapshot.platform.registration-snapshots.v1 \
  --brokers localhost:19092 \
  --offset start \
  --num 10 \
  --format 'partition:%p offset:%o timestamp:%d{ms} key:%k value:%v\n'

# Read from a specific partition
rpk topic consume onex.snapshot.platform.registration-snapshots.v1 \
  --brokers localhost:19092 \
  --partitions 0 \
  --offset start \
  --num 10
```

Tombstones appear as a key with an empty value.

### Checking Consumer Group Offsets

```bash
# List all consumer groups
rpk group list --brokers localhost:19092

# Describe a specific consumer group
rpk group describe <group-id> --brokers localhost:19092

# Example: check lag for the snapshot reader group
rpk group describe snapshot-reader --brokers localhost:19092
```

Output columns: `CURRENT-OFFSET` (last committed), `LOG-END-OFFSET` (latest), `LAG` (difference). A lag of 0 means the consumer is fully caught up.

### Environment Variable Overrides

`ModelSnapshotTopicConfig.default()` applies environment variable overrides on top of the compiled defaults:

| Environment Variable | Config Field | Default |
|---------------------|--------------|---------|
| `SNAPSHOT_TOPIC` | `topic` | `onex.snapshot.platform.registration-snapshots.v1` |
| `SNAPSHOT_PARTITION_COUNT` | `partition_count` | `12` |
| `SNAPSHOT_REPLICATION_FACTOR` | `replication_factor` | `3` |
| `SNAPSHOT_MIN_COMPACTION_LAG_MS` | `min_compaction_lag_ms` | `60000` |
| `SNAPSHOT_MAX_COMPACTION_LAG_MS` | `max_compaction_lag_ms` | `300000` |
| `SNAPSHOT_SEGMENT_BYTES` | `segment_bytes` | `104857600` |
| `SNAPSHOT_RETENTION_MS` | `retention_ms` | `-1` |
| `SNAPSHOT_MIN_INSYNC_REPLICAS` | `min_insync_replicas` | `2` |

`cleanup_policy` is intentionally **not overridable** via environment variable because snapshot topics must always use compaction.

**Development .env overrides**:

```bash
SNAPSHOT_REPLICATION_FACTOR=1
SNAPSHOT_MIN_INSYNC_REPLICAS=1
```

### Modifying Topic Configuration After Creation

```bash
# Adjust compaction lag on existing topic
rpk topic alter-config onex.snapshot.platform.registration-snapshots.v1 \
  --brokers localhost:19092 \
  --set min.compaction.lag.ms=120000 \
  --set max.compaction.lag.ms=600000

# Increase partition count (can never be decreased)
rpk topic add-partitions onex.snapshot.platform.registration-snapshots.v1 \
  --brokers localhost:19092 \
  --num 24
```

### Deleting the Topic

```bash
rpk topic delete onex.snapshot.platform.registration-snapshots.v1 \
  --brokers localhost:19092
```

Snapshots can always be rebuilt from projections, so deleting the snapshot topic does not cause data loss.

---

## Related Documentation

### Tickets

- ** (F2)**: Snapshot Publishing (this feature)
- ** (F1)**: Implement Registration Projection Schema
- ** (F0)**: Define Projector Execution Model

### Implementation Files

- **Snapshot Model**: `src/omnibase_infra/models/projection/model_registration_snapshot.py`
- **Topic Config**: `src/omnibase_infra/models/projection/model_snapshot_topic_config.py`
- **Publisher**: `src/omnibase_infra/projectors/snapshot_publisher_registration.py`
- **Projection Model**: `src/omnibase_infra/models/projection/model_registration_projection.py`

### Related Architecture Docs

- **Message Dispatch Engine**: `docs/architecture/MESSAGE_DISPATCH_ENGINE.md`
- **Circuit Breaker Thread Safety**: `docs/architecture/CIRCUIT_BREAKER_THREAD_SAFETY.md`
- **Error Handling Patterns**: `docs/patterns/error_handling_patterns.md`
- **Error Recovery Patterns**: `docs/patterns/error_recovery_patterns.md`

### ONEX Standards

- **Event Envelope**: `omnibase_core.models.events.model_event_envelope`
