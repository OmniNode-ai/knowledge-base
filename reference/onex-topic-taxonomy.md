---
type: reference
status: current
date: "2025-12-19"
title: "ONEX Kafka Topic Naming Standard"
topics: [onex, kafka, topic-naming, event-bus]
refs: []
---

# ONEX Kafka Topic Naming Standard

**Purpose**: Define the canonical Kafka topic naming convention for all ONEX domains
**Audience**: Developers, architects, infrastructure engineers
**Status**: Normative (ONEX v0.4.0+)
**Source**: omnibase_core `docs/standards/onex_topic_taxonomy.md`, migrated to the knowledge
base 2026-08-25. Verified live against omnibase_core@dev: `constants_topic_taxonomy.py`
exists with the exported constants this document names (e.g. `TOPIC_DISCOVERY_COMMANDS`,
`TOPIC_DISCOVERY_EVENTS`); no drift found.

---

## Overview

ONEX uses a structured Kafka topic naming convention to ensure consistency, discoverability,
and proper configuration across all domains.

### Design Principles

1. **Domain Isolation**: each domain has dedicated topics for separation of concerns
2. **Type Semantics**: topic types (`commands`, `events`, `intents`, `snapshots`) convey message semantics
3. **Consistent Configuration**: default retention and compaction policies per topic type
4. **Partition Alignment**: entity-based partitioning for ordering guarantees

### Topic Format

```text
onex.<domain>.<type>
```

| Component | Description | Example |
|-----------|-------------|---------|
| `onex.` | Required prefix (lowercase) | Always `onex.` |
| `<domain>` | Business/functional domain | `registration`, `discovery`, `runtime` |
| `<type>` | Topic type (semantics) | `commands`, `events`, `intents`, `snapshots` |

---

## Topic Structure

All ONEX Kafka topics **MUST** follow this three-part structure:

```python
TOPIC_PATTERN = r"^onex\.[a-z][a-z0-9-]*[a-z0-9]\.(commands|events|intents|snapshots)$|^onex\.[a-z]\.(commands|events|intents|snapshots)$"

# Valid
"onex.registration.commands"
"onex.registration.events"
"onex.discovery.intents"
"onex.runtime.snapshots"

# Invalid
"registration.events"           # Missing onex. prefix
"onex.registration"              # Missing type suffix
"onex.Registration.events"       # Uppercase not allowed
"onex.registration.logs"         # Invalid type
```

**Naming Rules**: prefix always `onex.` (lowercase); domain is lowercase alphanumeric with
optional hyphens (no underscores, cannot end with hyphen); type is one of `commands`,
`events`, `intents`, `snapshots`; single-dot separator; all lowercase.

---

## Topic Types

### commands

Write requests and command messages. Imperative ("RegisterNode", "ShutdownNode"); may be
rejected or fail; consumers process commands and emit events.

```yaml
cleanup.policy: delete
retention.ms: 604800000       # 7 days
retention.bytes: -1           # Unlimited
```

### events

Immutable event logs (domain events, facts). Past tense, immutable, append-only; the source
of truth for domain state; multiple consumers can replay independently.

```yaml
cleanup.policy: delete
retention.ms: 2592000000      # 30 days
retention.bytes: -1           # Unlimited
```

### intents

Coordination messages between nodes (side-effect declarations). Declare what should happen
(not imperative); emitted by REDUCER nodes to describe side effects without executing them;
consumed and executed by EFFECT nodes (the Pure FSM pattern).

```yaml
cleanup.policy: delete
retention.ms: 86400000        # 1 day (short-lived coordination)
retention.bytes: -1           # Unlimited
```

### snapshots

State snapshots for recovery and caching (optional per domain). Point-in-time state
captures; used for faster recovery (avoid full event replay); compacted by `entity_id`
(latest snapshot wins).

```yaml
cleanup.policy: compact,delete
retention.ms: 604800000       # 7 days
retention.bytes: -1           # Unlimited
min.compaction.lag.ms: 3600000  # 1 hour before compaction eligible
```

---

## Domain Registry

### Core Domains

| Domain | Purpose | Topics |
|--------|---------|--------|
| `registration` | Node registration and lifecycle | All 4 types |
| `discovery` | Node discovery protocol | `commands`, `events`, `intents` |
| `runtime` | Runtime orchestration | All 4 types |
| `metrics` | Metrics collection | `events`, `snapshots` |
| `audit` | Audit logging | `events` only |
| `health` | Health monitoring | `events`, `intents` |
| `workflow` | Workflow execution | All 4 types |

### Registering New Domains

New domains MUST be registered in the domain registry, use lowercase alphanumeric names
with optional hyphens, document which topic types are used, and follow the standard naming
pattern. Prefer singular nouns (`registration`, not `registrations`); prefer short,
descriptive names; avoid abbreviations unless widely understood (`dlq` is acceptable).

### Reserved Domains

| Domain | Purpose |
|--------|---------|
| `dlq` | Dead letter queues |
| `internal` | Internal system topics |
| `test` | Test/development topics |
| `debug` | Debug/diagnostic topics |

---

## Default Configurations

| Topic Type | cleanup.policy | retention.ms | Compaction | Use Case |
|------------|----------------|--------------|------------|----------|
| `commands` | `delete` | 7 days (604800000) | No | Write requests |
| `events` | `delete` | 30 days (2592000000) | No | Immutable logs |
| `intents` | `delete` | 1 day (86400000) | No | Coordination |
| `snapshots` | `compact,delete` | 7 days (604800000) | Yes | State recovery |

Retention/configuration can be overridden per environment (e.g. longer in production,
shorter in development).

---

## Partition Key Requirements

All messages **MUST** use `envelope.entity_id` as the partition key, for ordering
guarantees, consumer locality, and correct compaction of snapshots by entity.

```python
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

envelope = ModelEventEnvelope(
    event_type="NODE_REGISTERED",
    entity_id=node_id,  # This becomes the partition key
    payload={"node_type": "COMPUTE"},
    correlation_id=correlation_id,
)

producer.send(
    topic="onex.registration.events",
    key=str(envelope.entity_id).encode("utf-8"),
    value=envelope.model_dump_json().encode("utf-8"),
)
```

Key format: UUID as a lowercase, hyphenated string, UTF-8 encoded. Messages without an
`entity_id` (broadcast messages) use round-robin partitioning — acceptable only for
system-wide announcements, discovery broadcasts, and health-check pings.

---

## Examples

**Registration domain** — full topic set:

```text
onex.registration.commands   # Node registration commands
onex.registration.events     # Node lifecycle events
onex.registration.intents    # Side-effect coordination
onex.registration.snapshots  # Node state snapshots
```

Message flow: a client sends `REGISTER_NODE` on `onex.registration.commands` → the
Registration Reducer processes it and emits an intent on `onex.registration.intents` → the
Intent Executor publishes `NODE_REGISTERED` on `onex.registration.events` → a Snapshot Reducer
captures state on `onex.registration.snapshots`.

**Discovery**: `onex.discovery.{commands,events,intents}`.
**Runtime**: `onex.runtime.{commands,events,intents,snapshots}`.
**Metrics**: `onex.metrics.{events,snapshots}`.

---

## Validation Rules

```python
import re

VALID_TOPIC_PATTERN = re.compile(
    r"^onex\.[a-z][a-z0-9-]*[a-z0-9]\.(commands|events|intents|snapshots)$"
    r"|^onex\.[a-z]\.(commands|events|intents|snapshots)$"
)

def validate_topic_name(topic: str) -> bool:
    return bool(VALID_TOPIC_PATTERN.match(topic))

assert validate_topic_name("onex.registration.events")
assert not validate_topic_name("registration.events")       # Missing prefix
assert not validate_topic_name("onex.Registration.events")  # Uppercase
assert not validate_topic_name("onex.registration.logs")    # Invalid type
```

---

## Summary

| Aspect | Standard |
|--------|----------|
| **Format** | `onex.<domain>.<type>` |
| **Types** | `commands`, `events`, `intents`, `snapshots` |
| **Partition Key** | `envelope.entity_id` (UUID string) |
| **Events Retention** | 30 days (delete policy) |
| **Snapshots Policy** | compact,delete (7 days) |
| **Case** | All lowercase |

---

**Original Version**: 1.0.0, 2025-12-19, ONEX Architecture Team. Migrated to the knowledge
base 2026-08-25 with no content corrections — every referenced code path
(`constants_topic_taxonomy.py` and its exported constants) verified live.
