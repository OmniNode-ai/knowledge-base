---
type: architecture
status: accepted
date: "2026-09-02"
title: "Environment-Aware Topic Naming Pattern"
topics: [omnibase-infra, environment, aware, topic]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/ENVIRONMENT_TOPICS.md on 2026-09-02. -->

# Environment-Aware Topic Naming Pattern

## Overview

ONEX supports two topic naming conventions. The canonical format is **ONEX Kafka**
(`onex.<domain>.<type>`), which is used for all core platform event bus traffic.
The **Environment-Aware** format (`<env>.<domain>.<category>.<version>`) is an
alternate convention that embeds deployment environment and API version directly
into the topic name.

This document specifies the Environment-Aware format — its structure, supported
environments, routing behavior, and operational best practices.

**Related documentation**:
- ONEX Topic Taxonomy: `docs/architecture/TOPIC_TAXONOMY.md`
- Message category routing: `omnibase_infra.enums.EnumMessageCategory`
- Topic standard detection: `omnibase_infra.enums.EnumTopicStandard`
- Topic parser: `omnibase_infra.models.dispatch.ModelTopicParser`

---

## Format Specification

```
<env>.<domain>.<category>.<version>
```

| Segment | Type | Allowed Values | Example |
|---------|------|----------------|---------|
| `env` | string | `dev`, `staging`, `prod`, `test`, `local` | `prod` |
| `domain` | string | Lowercase alphanumeric with hyphens; must start with letter | `order-fulfillment` |
| `category` | string | `events`, `commands`, `intents` | `events` |
| `version` | string | `v` followed by one or more digits | `v2` |

All segments are case-insensitive at parse time but are normalised to lowercase
in `ModelParsedTopic`.

### Valid Examples

```
dev.user.events.v1
staging.order.commands.v1
prod.order-fulfillment.events.v2
test.inventory.intents.v1
local.auth.commands.v1
```

### Invalid Examples

```
production.user.events.v1    # "production" is not a recognised env
dev.user.snapshots.v1        # "snapshots" is not a supported category for env-aware
dev.user.events              # Missing version segment
dev.user.events.1            # Version must start with "v"
dev..events.v1               # Empty domain
```

---

## Supported Environments

| Value | Meaning | Typical Use |
|-------|---------|-------------|
| `dev` | Development | Local developer machines, feature branches |
| `staging` | Pre-production staging | Integration tests, QA, acceptance testing |
| `prod` | Production | Live traffic; apply strict access controls |
| `test` | Automated test runs | CI pipelines, isolated test suites |
| `local` | Local Docker / single-node | `docker-compose` local dev stacks |

### Environment Isolation

Each environment prefix creates a **logical namespace** on the same Kafka cluster.
Topics with different environment prefixes are completely independent:

```
dev.order.events.v1     # Development events
prod.order.events.v1    # Production events — separate partition, separate consumers
```

Consumer groups are scoped per topic and do not span environments. Never subscribe
a production consumer to a `dev.*` or `test.*` topic, and vice versa.

---

## Routing Behaviour

The `ModelTopicParser` detects the format automatically and populates
`ModelParsedTopic` with the extracted components:

```python
from omnibase_infra.models.dispatch import ModelTopicParser

parser = ModelTopicParser()
result = parser.parse("prod.order.events.v2")

assert result.standard.value == "environment_aware"
assert result.environment == "prod"
assert result.domain == "order"
assert result.category.value == "event"    # EnumMessageCategory.EVENT
assert result.version == "v2"
assert result.is_valid is True
assert result.is_routable() is True
```

The `MessageDispatchEngine` routes messages using `result.category` —
the same routing key as for ONEX Kafka topics. This means dispatchers
registered for `EnumMessageCategory.EVENT` receive events from both
`onex.registration.events` and `prod.order.events.v2` without any
additional configuration.

### Category Mapping

| Topic category segment | `EnumMessageCategory` value |
|------------------------|-----------------------------|
| `events` | `EVENT` |
| `commands` | `COMMAND` |
| `intents` | `INTENT` |

Note: `snapshots` is **not** supported in the Environment-Aware format.
Snapshot topics must use the ONEX Kafka format (`onex.<domain>.snapshots`).

---

## API Versioning with the Version Segment

The version suffix enables **multiple concurrent API versions** on the same topic
namespace without conflict:

```
prod.order.events.v1   # Legacy consumers still subscribed
prod.order.events.v2   # New event schema; new consumers subscribe here
```

**Version lifecycle**:
1. Introduce `v2` topic alongside `v1`; producers write to both during migration
2. Migrate consumers to `v2`
3. Once all consumers are on `v2`, stop producing to `v1`
4. After retention period, the `v1` topic can be deleted

Never reuse a version number for an incompatible schema change — increment the
version instead.

---

## When to Use Environment-Aware vs ONEX Kafka

| Scenario | Recommended Format |
|----------|--------------------|
| Core ONEX platform events (registration, discovery, intent routing) | `onex.<domain>.<type>` |
| Multi-environment deployment with topic isolation per environment | `<env>.<domain>.<category>.<version>` |
| Versioned external-facing event schemas | `<env>.<domain>.<category>.<version>` |
| Internal infrastructure events (scheduler, health checks) | `onex.<domain>.<type>` |
| Consumer applications bridging external systems | `<env>.<domain>.<category>.<version>` |

The ONEX Kafka format is preferred for all first-party ONEX platform traffic.
Use the Environment-Aware format when the deployment environment and/or API
version must be expressed in the topic name itself — typically for external
integrations or when operating shared clusters across environments.

---

## Cross-Environment Messaging Considerations

Cross-environment message delivery (e.g., staging producing to a prod topic) is
an architecture violation. To prevent accidental cross-environment delivery:

1. **Topic ACLs**: Configure Redpanda/Kafka ACLs so that each environment's
   service accounts can only produce to topics prefixed with their own environment.

2. **Runtime assertion**: Before publishing, assert that the topic's environment
   matches the `ONEX_ENVIRONMENT` variable (or equivalent config key):

   ```python
   from omnibase_infra.models.dispatch import ModelTopicParser

   parser = ModelTopicParser()
   parsed = parser.parse(target_topic)

   if parsed.environment and parsed.environment != runtime_env:
       raise ValueError(
           f"Cross-environment publish blocked: "
           f"runtime={runtime_env!r}, topic_env={parsed.environment!r}"
       )
   ```

3. **Consumer group naming**: Include the environment in the consumer group name
   (e.g., `prod-order-service-v2`) to make cross-environment accidents visible
   in monitoring.

---

## Detection and Validation

Use `ModelTopicParser` to check topic format before publishing or subscribing:

```python
from omnibase_infra.models.dispatch import ModelTopicParser
from omnibase_infra.enums import EnumTopicStandard

parser = ModelTopicParser()

topic = "dev.inventory.commands.v1"

if parser.is_environment_aware_format(topic):
    result = parser.parse(topic)
    # result.environment, .domain, .category, .version are populated
elif parser.is_onex_kafka_format(topic):
    result = parser.parse(topic)
    # result.domain, .category, .topic_type are populated; env/version are None
else:
    result = parser.parse(topic)
    # result.standard == EnumTopicStandard.UNKNOWN
    # result.is_valid may still be True if category was inferred
```

For strict validation (reject UNKNOWN topics):

```python
result = parser.parse(topic)
if result.standard == EnumTopicStandard.UNKNOWN:
    raise ValueError(f"Unrecognised topic format: {topic!r}")
```

---

## `ModelParsedTopic` Fields for Environment-Aware Topics

| Field | Type | Populated? | Description |
|-------|------|------------|-------------|
| `raw_topic` | `str` | Always | Original topic string |
| `standard` | `EnumTopicStandard` | Always | `ENVIRONMENT_AWARE` |
| `domain` | `str \| None` | Yes | Domain segment (e.g., `order`) |
| `category` | `EnumMessageCategory \| None` | Yes | Routing category |
| `topic_type` | `EnumTopicType \| None` | No | Always `None` for env-aware topics |
| `environment` | `str \| None` | Yes | Normalised environment (e.g., `prod`) |
| `version` | `str \| None` | Yes | Version string (e.g., `v2`) |
| `is_valid` | `bool` | Always | `True` when parse succeeded |
| `validation_error` | `str \| None` | On failure | Describes parse failure |

---

## Best Practices

1. **Prefer ONEX Kafka format for internal platform traffic.** The env-aware format
   adds complexity; only adopt it when environment isolation or versioning in the
   topic name is a hard requirement.

2. **Standardise on a single environment identifier.** Drive the `env` prefix from
   a single config source (e.g., `ONEX_ENVIRONMENT` env var) so that all services
   in a deployment use the same value.

3. **Validate topics at startup.** Parse and validate all topic strings at service
   initialisation to catch misconfiguration before any messages are produced.

4. **Increment versions for breaking changes only.** Adding optional fields to an
   event schema is backward-compatible and does not require a new version.

5. **Never mix environment-aware and ONEX Kafka topics in the same dispatcher
   registration.** A dispatcher registered for `EnumMessageCategory.EVENT` will
   receive events from both formats; ensure handler logic is schema-agnostic or
   explicitly checks `ModelParsedTopic.standard`.

6. **Document retained versions in your service's CLAUDE.md.** If you maintain
   both `v1` and `v2` topics, note the migration timeline and which consumers
   are on each version.
