---
type: reference
status: current
date: "2026-09-02"
title: "ONEX Infrastructure Topic Taxonomy"
topics: [omnibase-infra, topic, taxonomy]
refs: []
---

<!-- Migrated from omnibase_infra:docs/standards/TOPIC_TAXONOMY.md on 2026-09-02. -->

# ONEX Infrastructure Topic Taxonomy

> **Status**: Current | **Last Updated**: 2026-02-19

Kafka topic naming convention for `omnibase_infra`. Covers the realm-agnostic suffix format introduced in , the topic name construction pattern, and all defined topic suffix constants.

---

## Table of Contents

1. [Overview](#overview)
2. [Topic Suffix Format](#topic-suffix-format)
3. [Kind Reference](#kind-reference)
4. [Topic Name Construction](#topic-name-construction)
5. [Platform Topic Suffixes](#platform-topic-suffixes)
6. [Intelligence Domain Topic Suffixes](#intelligence-domain-topic-suffixes)
7. [Topic Spec Registry](#topic-spec-registry)
8. [Validation](#validation)
9. [See Also](#see-also)

---

## Overview

All Kafka topics in `omnibase_infra` are defined as **realm-agnostic suffixes** in `src/omnibase_infra/topics/platform_topic_suffixes.py`. The full topic name is composed at runtime by prepending a tenant or namespace prefix.

 changed the topic format from an environment-prefixed scheme (e.g., `dev.archon-intelligence.intelligence.code-analysis-requested.v1`) to the current realm-agnostic scheme (`onex.<kind>.<producer>.<event-name>.v<version>`). The new format does not encode environment or deployment context in the suffix itself — that is the caller's responsibility.

---

## Topic Suffix Format

```text
onex.<kind>.<producer>.<event-name>.v<version>
```

**Components**:

| Component | Description | Rules |
|-----------|-------------|-------|
| `onex` | Required prefix | Always lowercase, always first |
| `<kind>` | Message category | One of: `evt`, `cmd`, `intent`, `snapshot`, `dlq` |
| `<producer>` | Routing domain | `platform` for infrastructure; domain name for plugins (e.g., `omniintelligence`) |
| `<event-name>` | Descriptive name | Lowercase kebab-case |
| `v<version>` | Semantic version | `v1`, `v2`, etc. (no dot-notation) |

**Examples**:

```text
onex.evt.platform.node-registration.v1
onex.cmd.platform.request-introspection.v1
onex.intent.platform.runtime-tick.v1
onex.snapshot.platform.registration-snapshots.v1
onex.cmd.omniintelligence.claude-hook-event.v1
onex.evt.omniintelligence.intent-classified.v1
```

---

## Kind Reference

| Kind | Full Word | Retention Default | Cleanup Policy | Purpose |
|------|-----------|-------------------|----------------|---------|
| `evt` | event | 30 days | delete | State changes, notifications, domain facts |
| `cmd` | command | 7 days | delete | Requests for action (may be rejected or fail) |
| `intent` | intent | 1 day | delete | Internal workflow coordination (side-effect declarations) |
| `snapshot` | snapshot | 7 days | compact,delete | Periodic state captures for recovery |
| `dlq` | dead-letter queue | 7 days | delete | Failed message routing |

---

## Topic Name Construction

Topic suffixes are **not full topic names**. At runtime, a tenant or namespace prefix is prepended. The construction utility is in `omnibase_core.validation`:

```python
from omnibase_core.validation import compose_full_topic

# Suffix only (stored in platform_topic_suffixes.py)
suffix = "onex.evt.platform.node-registration.v1"

# Full topic (prepend tenant/namespace at call site)
full_topic = compose_full_topic(tenant="dev", namespace="myservice", suffix=suffix)
# -> "dev.myservice.onex.evt.platform.node-registration.v1"
```

**E2E tests use suffixes directly** (no prefix) when interacting with the local Docker infrastructure. The topic `onex.evt.platform.node-introspection.v1` is used as-is. Note that as of  the runtime kernel no longer reads `ONEX_INPUT_TOPIC` / `ONEX_OUTPUT_TOPIC` — topics are derived from each node's `contract.yaml` `event_bus` declaration and setting those env vars raises `ProtocolConfigurationError` at bootstrap.

**`TopicProvisioner`** at runtime startup creates topics from `ALL_PROVISIONED_TOPIC_SPECS`, using the suffix as the full Kafka topic name (no additional prefix in the current deployment model).

---

## Platform Topic Suffixes

All constants defined in `src/omnibase_infra/topics/platform_topic_suffixes.py`. Producer: `platform`.

### Node Lifecycle Events (`evt`)

| Constant | Suffix | Partitions | Description |
|----------|--------|------------|-------------|
| `SUFFIX_NODE_REGISTRATION` | `onex.evt.platform.node-registration.v1` | 6 | Node registered with runtime |
| `SUFFIX_NODE_INTROSPECTION` | `onex.evt.platform.node-introspection.v1` | 6 | Node responded to introspection request |
| `SUFFIX_REGISTRY_REQUEST_INTROSPECTION` | `onex.evt.platform.registry-request-introspection.v1` | 6 | Registry-initiated introspection request |
| `SUFFIX_NODE_HEARTBEAT` | `onex.evt.platform.node-heartbeat.v1` | 6 | Node liveness heartbeat |
| `SUFFIX_FSM_STATE_TRANSITIONS` | `onex.evt.platform.fsm-state-transitions.v1` | 6 | FSM state machine transition |
| `SUFFIX_CONTRACT_REGISTERED` | `onex.evt.platform.contract-registered.v1` | 6 | Node contract registered with runtime |
| `SUFFIX_CONTRACT_DEREGISTERED` | `onex.evt.platform.contract-deregistered.v1` | 6 | Node contract deregistered |

### Command Topics (`cmd`)

| Constant | Suffix | Partitions | Description |
|----------|--------|------------|-------------|
| `SUFFIX_REQUEST_INTROSPECTION` | `onex.cmd.platform.request-introspection.v1` | 6 | Request introspection from a node |
| `SUFFIX_NODE_REGISTRATION_ACKED` | `onex.cmd.platform.node-registration-acked.v1` | 6 | Node acknowledges successful registration |

### Intent Topics (`intent`)

| Constant | Suffix | Partitions | Description |
|----------|--------|------------|-------------|
| `SUFFIX_RUNTIME_TICK` | `onex.intent.platform.runtime-tick.v1` | 1 | Runtime orchestration tick (triggers periodic tasks) |

### Snapshot Topics (`snapshot`)

| Constant | Suffix | Partitions | Description |
|----------|--------|------------|-------------|
| `SUFFIX_REGISTRATION_SNAPSHOTS` | `onex.snapshot.platform.registration-snapshots.v1` | 1 | Aggregated registration state snapshots |

### Topic Catalog Topics

| Constant | Suffix | Partitions | Retention | Description |
|----------|--------|------------|-----------|-------------|
| `SUFFIX_TOPIC_CATALOG_QUERY` | `onex.cmd.platform.topic-catalog-query.v1` | 1 | 1 hour | Client requests topic catalog |
| `SUFFIX_TOPIC_CATALOG_RESPONSE` | `onex.evt.platform.topic-catalog-response.v1` | 1 | 1 hour | Catalog query response |
| `SUFFIX_TOPIC_CATALOG_CHANGED` | `onex.evt.platform.topic-catalog-changed.v1` | 1 | 7 days | Topic catalog delta notification |

---

## Intelligence Domain Topic Suffixes

All constants defined in `src/omnibase_infra/topics/platform_topic_suffixes.py`. Producer: `omniintelligence`. Partitions: 3 each.

### Command Topics (`cmd`)

| Constant | Suffix | Description |
|----------|--------|-------------|
| `SUFFIX_INTELLIGENCE_CLAUDE_HOOK_EVENT` | `onex.cmd.omniintelligence.claude-hook-event.v1` | Claude hook events dispatched to intelligence pipeline |
| `SUFFIX_INTELLIGENCE_SESSION_OUTCOME` | `onex.cmd.omniintelligence.session-outcome.v1` | Session outcome commands (success/failure attribution) |
| `SUFFIX_INTELLIGENCE_PATTERN_LIFECYCLE_TRANSITION` | `onex.cmd.omniintelligence.pattern-lifecycle-transition.v1` | Pattern lifecycle transition commands |

### Event Topics (`evt`)

| Constant | Suffix | Description |
|----------|--------|-------------|
| `SUFFIX_INTELLIGENCE_INTENT_CLASSIFIED` | `onex.evt.omniintelligence.intent-classified.v1` | Intent classification events |
| `SUFFIX_INTELLIGENCE_PATTERN_LEARNED` | `onex.evt.omniintelligence.pattern-learned.v1` | New pattern discovered |
| `SUFFIX_INTELLIGENCE_PATTERN_STORED` | `onex.evt.omniintelligence.pattern-stored.v1` | Pattern persisted to database |
| `SUFFIX_INTELLIGENCE_PATTERN_PROMOTED` | `onex.evt.omniintelligence.pattern-promoted.v1` | Pattern promoted from candidate to validated |
| `SUFFIX_INTELLIGENCE_PATTERN_LIFECYCLE_TRANSITIONED` | `onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1` | Pattern lifecycle transition completed |
| `SUFFIX_INTELLIGENCE_LLM_CALL_COMPLETED` | `onex.evt.omniintelligence.llm-call-completed.v1` | LLM call metrics (token counts, cost, latency) |
| `SUFFIX_INTELLIGENCE_PATTERN_DISCOVERED` | `onex.evt.pattern.discovered.v1` | Generic pattern discovery events |

---

## Topic Spec Registry

`platform_topic_suffixes.py` exports three combined registries used by `TopicProvisioner`:

| Registry Constant | Contents |
|-------------------|----------|
| `ALL_PLATFORM_TOPIC_SPECS` | All platform-reserved `ModelTopicSpec` objects |
| `ALL_INTELLIGENCE_TOPIC_SPECS` | All intelligence domain `ModelTopicSpec` objects |
| `ALL_PROVISIONED_TOPIC_SPECS` | `ALL_PLATFORM_TOPIC_SPECS + ALL_INTELLIGENCE_TOPIC_SPECS` — single source of truth for startup topic creation |

Two derived string tuples for validation code:

| Constant | Contents |
|----------|----------|
| `ALL_PLATFORM_SUFFIXES` | Tuple of platform suffix strings (derived from `ALL_PLATFORM_TOPIC_SPECS`) |
| `ALL_PROVISIONED_SUFFIXES` | Tuple of all provisioned suffix strings (platform + domain) |

All suffixes are validated at import time via `validate_topic_suffix()`. An invalid suffix raises `OnexError` immediately at module load, preventing misconfigured deployments from starting.

---

## Validation

Suffix validation runs at import time and enforces:

```python
from omnibase_core.validation import validate_topic_suffix

result = validate_topic_suffix("onex.evt.platform.node-registration.v1")
assert result.is_valid  # True

result = validate_topic_suffix("dev.bad-format")
assert not result.is_valid  # True — missing onex prefix and kind
```

**Valid suffix pattern**:
```text
^onex\.(evt|cmd|intent|snapshot|dlq)\.[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*\.v[0-9]+$
```

---

## See Also

| Topic | Document |
|-------|----------|
| Terminology (topic suffix vs. full topic) | ONEX_TERMINOLOGY.md (internal knowledge base) |
| E2E infrastructure (topic provisioning in tests) | ../testing/INTEGRATION_TESTING.md |
| Topic source file | `src/omnibase_infra/topics/platform_topic_suffixes.py` |
| Topic spec model | `src/omnibase_infra/topics/model_topic_spec.py` |
| Topic resolver | `src/omnibase_infra/topics/topic_resolver.py` |
| omnibase_core topic taxonomy (domain format) | `docs/standards/onex_topic_taxonomy.md` in omnibase_core |
