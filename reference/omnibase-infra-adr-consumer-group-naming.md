---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Kafka Consumer Group Naming Convention"
topics: [omnibase-infra, adr, consumer, group]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-consumer-group-naming.md on 2026-09-02. -->

# ADR: Kafka Consumer Group Naming Convention

## Status

Accepted

## Date

2026-01-27

## Context

ONEX infrastructure services use Kafka consumer groups for event-driven communication. Each service subscribes to topics using consumer groups that determine how Kafka partitions are assigned across consumers.

**Problem Statement**: Without a systematic naming convention, services using hardcoded or ad-hoc consumer group IDs can cause:

1. **Partition stealing**: Two services using the same group ID on the same topic will compete for partitions, causing one to receive messages intended for the other
2. **Non-deterministic behavior**: Restarting services could result in different partition assignments
3. **Debugging difficulty**: Generic group IDs like `"onex-runtime"` provide no context about which service owns the consumer
4. **Purpose confusion**: Different consumption patterns (real-time vs replay vs audit) require different offset policies but have no way to express this semantically

**Use Cases Requiring Distinct Consumer Groups**:

1. **Multiple services on shared topic**: Registration events consumed by both orchestrators and projectors
2. **Introspection consumers**: Node discovery queries that should not interfere with normal event processing
3. **Replay consumers**: Reprocessing historical data from the beginning of a topic
4. **Audit consumers**: Compliance logging that requires full topic capture
5. **Backfill consumers**: One-shot bounded consumers for populating derived state

**Kafka Consumer Group Constraints**:

- Maximum length: 255 characters
- Valid characters: alphanumeric, period (`.`), underscore (`_`), hyphen (`-`)
- Cannot be empty

## Decision

We implemented a **derived consumer group naming convention** that generates deterministic, semantically meaningful group IDs from node identity and purpose.

### 1. Canonical Format

```
{env}.{service}.{node_name}.{purpose}.{version}
```

**Components**:

| Component | Description | Example |
|-----------|-------------|---------|
| `env` | Environment identifier | `dev`, `staging`, `prod` |
| `service` | Service name from contract | `omniintelligence`, `omnibridge` |
| `node_name` | Node name from contract | `claude_hook_event_effect` |
| `purpose` | Consumer purpose classification | `consume`, `introspection`, `replay` |
| `version` | Node version string | `v1`, `v2.0.0` |

**Example Group IDs**:

```
dev.omniintelligence.claude_hook_event_effect.consume.v1
prod.omnibridge.registration_orchestrator.introspection.v1
staging.omnidash.metrics_projector.replay.v2
```

### 2. Purpose Classification

Consumer purposes are defined in `EnumConsumerGroupPurpose`:

| Purpose | Offset Policy | Pattern | Use Case |
|---------|---------------|---------|----------|
| `CONSUME` | `latest` | Continuous | Standard event processing |
| `INTROSPECTION` | `latest` | Targeted | Node discovery and health queries |
| `REPLAY` | `earliest` | Full topic | Reprocess historical data |
| `AUDIT` | `earliest` | Full topic | Compliance and audit logging |
| `BACKFILL` | `earliest` | Bounded | Populate derived state from history |

### 3. Typed Node Identity

Consumer group derivation uses `ModelNodeIdentity`, a frozen Pydantic model:

```python
from omnibase_infra.models import ModelNodeIdentity
from omnibase_infra.enums import EnumConsumerGroupPurpose
from omnibase_infra.utils import compute_consumer_group_id

identity = ModelNodeIdentity(
    env="dev",
    service="omniintelligence",
    node_name="claude_hook_event_effect",
    version="v1",
)

# Standard consumption
group_id = compute_consumer_group_id(identity)
# Result: "dev.omniintelligence.claude_hook_event_effect.consume.v1"

# Introspection
group_id = compute_consumer_group_id(identity, EnumConsumerGroupPurpose.INTROSPECTION)
# Result: "dev.omniintelligence.claude_hook_event_effect.introspection.v1"
```

### 4. Component Normalization

Each component is normalized to ensure Kafka compatibility:

1. **Lowercase conversion**: `DEV` becomes `dev`
2. **Invalid character replacement**: Spaces and special characters become underscores
3. **Separator collapse**: `foo..bar` becomes `foo.bar`
4. **Edge trimming**: Leading/trailing separators are removed

### 5. Length Constraint Handling

When the combined group ID exceeds 255 characters:

1. Generate 8-character SHA-256 hash suffix from original (pre-normalized) identity
2. Truncate the group ID prefix to `255 - 9` characters (reserving space for `_` + hash)
3. Append `_{hash_suffix}`

This ensures:
- Determinism: Same identity always produces same truncated ID
- Uniqueness: Hash suffix differentiates truncated IDs
- Kafka compliance: Result is always <= 255 characters

### 6. Event Bus Integration

The `subscribe()` method on event bus implementations accepts `ModelNodeIdentity` and `EnumConsumerGroupPurpose`:

```python
await event_bus.subscribe(
    topic="node.introspection.events",
    node_identity=identity,
    on_message=handler,
    purpose=EnumConsumerGroupPurpose.INTROSPECTION,
)
```

The event bus internally calls `compute_consumer_group_id()` to derive the group ID.

## Consequences

### Positive

- **Partition isolation**: Each node gets unique consumer groups, eliminating partition stealing
- **Deterministic assignment**: Same node identity always produces same group ID
- **Semantic clarity**: Group IDs encode environment, service, node, purpose, and version
- **Monitoring integration**: Hierarchical format enables Kafka tooling to filter by prefix (`dev.*`, `*.introspection.*`)
- **Offset policy alignment**: Purpose-based naming enables automatic offset reset configuration
- **Debugging support**: Group IDs in logs immediately identify the owning service and purpose

### Negative

- **Group ID verbosity**: Full format is longer than simple names like `"my-service"`
- **Truncation complexity**: Very long service/node names require hash-based truncation
- **Migration overhead**: Existing deployments must migrate to new group IDs (offset positions are not preserved)

### Neutral

- **Consumer group proliferation**: Each purpose creates a separate group, which is intentional for isolation
- **Kafka offset storage**: More consumer groups means more offset metadata stored in Kafka

## Runtime Naming Model (Current Constraint)

**INVARIANT**: In the current runtime model, `ModelRuntimeConfig.name` represents both `service_name` and `node_name` by design.

This means consumer group IDs have intentional redundancy:

```
local.my-service.my-service.introspection.v1
      ^^^^^^^^^^ ^^^^^^^^^^
      service    node_name (same value)
```

### Why This Is Acceptable

1. **Single-node deployments**: Current architecture has 1:1 service-to-node mapping
2. **Explicit redundancy**: Redundancy is honest and traceable (avoids inventing fake node names)
3. **Deterministic IDs**: Consumer group IDs remain deterministic and traceable
4. **No information loss**: When the split occurs, the format already has the slot for distinct values

### Trigger for Schema Split

Split `service_name` and `node_name` when:

- `ServiceKernel` supports registering multiple node contracts under one service runtime
- A single service process needs to host >1 ONEX node identity
- Multi-tenant node hosting becomes a requirement

### Migration Expectations

When the split occurs:

1. **Existing consumer groups will naturally diverge**: New IDs will have distinct service/node components
2. **Old group IDs orphaned**: Acceptable per no-backwards-compatibility policy (see CLAUDE.md)
3. **Offset positions reset**: Services will resume from configured offset policy (latest/earliest)
4. **No migration tooling required**: Clean break is preferred over compatibility shims

## Alternatives Considered

### 1. UUID-Based Consumer Group IDs

**Approach**: Generate random UUIDs for each consumer group.

```python
group_id = f"onex-{uuid.uuid4()}"
```

**Why rejected**:

1. **Non-deterministic**: Same service would get different group IDs on restart
2. **Partition rebalancing**: Every restart triggers full partition reassignment
3. **No semantic meaning**: UUIDs provide no context for debugging or monitoring
4. **Offset loss**: Offsets tied to old UUIDs are orphaned on restart

### 2. Simple Service Name Only

**Approach**: Use just the service name as the group ID.

```python
group_id = config.name  # "my-service"
```

**Why rejected**:

1. **Purpose collision**: Same service consuming for different purposes shares offsets
2. **Version collision**: Service upgrades compete with old versions for partitions
3. **Environment collision**: Dev and prod instances could share group IDs if misconfigured
4. **No node distinction**: Multi-node services cannot be differentiated

### 3. Topic-Prefixed Groups

**Approach**: Prefix group ID with the topic name.

```python
group_id = f"{topic}-{service_name}"  # "events-my-service"
```

**Why rejected**:

1. **Topic coupling**: Group ID changes if topic is renamed
2. **Multi-topic consumption**: Services consuming multiple topics get multiple group IDs per purpose
3. **Still lacks purpose/version**: Does not solve offset policy or version collision issues

### 4. Centralized Group Registry

**Approach**: Require services to register group IDs in a central registry (Consul/database).

**Why rejected**:

1. **Operational overhead**: Requires registry management and coordination
2. **Single point of failure**: Registry unavailability blocks service startup
3. **No clear benefit**: Derived naming achieves uniqueness without coordination
4. **Complexity**: Adds another moving part to the infrastructure

## Implementation Notes

### Key Files

- `src/omnibase_infra/utils/util_consumer_group.py`: Core derivation logic
- `src/omnibase_infra/enums/enum_consumer_group_purpose.py`: Purpose enumeration
- `src/omnibase_infra/models/model_node_identity.py`: Typed identity model
- `src/omnibase_infra/event_bus/event_bus_kafka.py`: Kafka integration
- `src/omnibase_infra/event_bus/event_bus_inmemory.py`: In-memory integration
- `tests/unit/utils/test_util_consumer_group.py`: Unit tests

### Error Handling

The `normalize_kafka_identifier()` function raises `ValueError` for:

- Empty input strings
- Input that normalizes to empty string (e.g., `"@#$%^"`)

All `ModelNodeIdentity` fields are validated as non-empty, non-whitespace strings.

### Monitoring Consumer Groups

Use Kafka tooling to monitor consumer groups by pattern:

```bash
# List all dev environment groups
kafka-consumer-groups.sh --list | grep '^dev\.'

# List all introspection consumers
kafka-consumer-groups.sh --list | grep '\.introspection\.'

# Describe specific group
kafka-consumer-groups.sh --describe --group dev.omniintelligence.claude_hook_event_effect.consume.v1
```

### Performance Characteristics

- **Normalization**: O(n) where n is input string length
- **Hash computation**: O(1) for SHA-256 (fixed input size after truncation)
- **Total derivation**: O(m) where m is sum of all component lengths

### Hash Computation Details

When group IDs exceed 255 characters, a hash suffix is computed from the original identity components. The hash input uses pipe (`|`) as a separator:

```
{env}|{service}|{node_name}|{purpose}|{version}
```

**Important**: Changing this separator would produce different hash suffixes, effectively creating new consumer groups and orphaning existing ones. This format is considered stable and should not be modified without a migration plan.

## References

- **EnumConsumerGroupPurpose**: Purpose classification enum
- **ModelNodeIdentity**: Typed node identity model
- **ADR-001**: Graceful Shutdown with Drain Period (related consumer lifecycle)
