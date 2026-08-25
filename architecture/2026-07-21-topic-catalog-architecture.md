---
type: architecture
status: accepted
date: "2026-07-21"
title: "Topic Catalog Architecture"
topics: [omnibase-infra, topic, catalog]
refs: []
---

# Topic Catalog Architecture

> **Status**: Current | **Last Updated**: 2026-02-19

The topic catalog provides runtime discovery of all Kafka topics known to the ONEX platform. Any node or service can query the catalog to find out which topics exist, who publishes to them, who subscribes, and what their metadata looks like. This is central to dashboard observability, dynamic routing, and contract validation.

Introduced across  (models),  (ServiceTopicCatalog),  (warnings channel),  (query handler + dispatcher).

---

## Table of Contents

1. Purpose
2. Component Inventory
3. Data Flow
4. Consul KV Structure
5. ServiceTopicCatalog — Design Details
6. KV Precedence Rules
7. In-Process Cache
8. Timeout Budget and Partial Results
9. Catalog Versioning and CAS
10. Query Handler and Dispatcher
11. Warnings Channel
12. Data Models
13. Usage Pattern
14. See Also

---

## Purpose

Each ONEX node declares in Consul KV which topics it publishes to and subscribes from. The topic catalog aggregates all of those declarations across all registered nodes into a single queryable snapshot. The snapshot is:

- **Version-stamped**: consumers know when the catalog has changed
- **Partial-success**: a Consul outage or timeout returns whatever data was available plus warnings, rather than failing the whole query
- **Cached**: repeated queries at the same version hit the in-process cache, not Consul

---

## Component Inventory

| Component | Location | Role |
|-----------|----------|------|
| `ServiceTopicCatalog` | `services/service_topic_catalog.py` | Core service: reads Consul KV, builds catalog, manages cache |
| `HandlerTopicCatalogQuery` | `nodes/node_registration_orchestrator/handlers/handler_topic_catalog_query.py` | ONEX handler: validates query, delegates to service, always responds |
| `DispatcherTopicCatalogQuery` | `nodes/node_registration_orchestrator/dispatchers/dispatcher_topic_catalog_query.py` | Dispatch adapter: circuit breaker + deserialization |
| `ModelTopicCatalogEntry` | `models/catalog/model_topic_catalog_entry.py` | Single topic entry with computed `is_active` |
| `ModelTopicCatalogQuery` | `models/catalog/model_topic_catalog_query.py` | Client request: filters, pattern, correlation ID |
| `ModelTopicCatalogResponse` | `models/catalog/model_topic_catalog_response.py` | Catalog snapshot: topics, version, node count, warnings |
| `ModelTopicCatalogChanged` | `models/catalog/model_topic_catalog_changed.py` | Model for catalog version change notifications; exists but is not currently emitted by the registration path |
| `catalog_warning_codes.py` | `models/catalog/catalog_warning_codes.py` | Stable string constants for all warning tokens |
| `TopicResolver` | `topics/topic_resolver.py` | Maps topic suffixes to fully-qualified Kafka topic names |

---

## Data Flow

```text
Client (dashboard, node, or service)
        |
        | publish ModelTopicCatalogQuery to "platform.topic-catalog-query" topic
        v
+-------------------------------+
| DispatcherTopicCatalogQuery   |  -- circuit breaker; deserializes payload
+-------------------------------+
        |
        v
+-----------------------------+
| HandlerTopicCatalogQuery    |  -- validates payload; never raises to caller
+-----------------------------+
        |
        v
+------------------------+
| ServiceTopicCatalog    |
|  .build_catalog()      |
+------------------------+
        |
        +-- Check cache (version-keyed)
        |     hit -> re-apply caller filters -> return immediately
        |
        +-- Miss: recursive KV get "onex/nodes/" from Consul
        |     (max 5s, partial on timeout)
        |
        +-- _process_raw_kv_items()
        |     parse JSON arrays per node
        |     cross-reference topics -> publisher/subscriber sets
        |     apply enrichment (description, partitions, tags)
        |
        +-- TopicResolver.resolve() per topic suffix
        |
        +-- Build ModelTopicCatalogResponse
        |
        +-- Store in _cache[catalog_version]
        |
        v
ModelTopicCatalogResponse (topics, version, node_count, warnings)
        |
        v
HandlerTopicCatalogQuery wraps in ModelHandlerOutput.events
        |
        v
DispatcherTopicCatalogQuery returns ModelDispatchResult
        |
        v
Client receives ModelTopicCatalogResponse on "platform.topic-catalog-response" topic
```

---

## Consul KV Structure

All catalog data lives under the `onex/` namespace:

```text
onex/catalog/version                                  -- monotonic integer
onex/nodes/{node_id}/event_bus/subscribe_topics       -- JSON array of topic suffixes (AUTHORITATIVE)
onex/nodes/{node_id}/event_bus/publish_topics         -- JSON array of topic suffixes (AUTHORITATIVE)
onex/nodes/{node_id}/event_bus/subscribe_entries      -- JSON array of enrichment dicts (optional)
onex/nodes/{node_id}/event_bus/publish_entries        -- JSON array of enrichment dicts (optional)
onex/topics/{topic}/subscribers                       -- JSON array of node_ids (derived cache only)
```

The `onex/nodes/{node_id}/` structure means each node owns a namespace under its ID. The recursive KV get on `onex/nodes/` fetches everything for all nodes in one call.

### Enrichment dict structure

Each entry in `subscribe_entries` / `publish_entries` is an object with optional enrichment fields:

```json
{
  "topic_suffix": "onex.evt.platform.node-registration.v1",
  "description": "Emitted when a node completes registration",
  "partitions": 6,
  "tags": ["platform", "lifecycle"]
}
```

---

## ServiceTopicCatalog — Design Details

### Constructor

```python
service = ServiceTopicCatalog(
    container=container,
    consul_handler=handler,    # HandlerConsul instance; None disables catalog
    topic_resolver=resolver,   # optional; defaults to pass-through TopicResolver
)
```

When `consul_handler` is `None`, every `build_catalog()` call returns an empty response with `CONSUL_UNAVAILABLE` in warnings. This is the correct behavior for environments without Consul (e.g., unit tests).

### `build_catalog(correlation_id, include_inactive, topic_pattern)`

The main entry point. Steps:

1. Read `onex/catalog/version` from Consul
2. Return cached response immediately if version matches (and re-apply caller's filters)
3. Recursive KV fetch of `onex/nodes/` with a 5-second timeout budget
4. `_process_raw_kv_items()` — pure CPU work, always completes even if network timed out
5. `TopicResolver.resolve()` for each topic suffix
6. Build `ModelTopicCatalogEntry` per topic, sorted by `topic_suffix`
7. Build `ModelTopicCatalogResponse` with warnings
8. Store in `_cache[version]`; evict older versions
9. Re-apply caller filters (`include_inactive`, `topic_pattern`) and return

### `_process_raw_kv_items()`

This method is intentionally synchronous (no I/O). It takes the raw list of Consul KV items already fetched and does all the cross-referencing in memory. It runs to completion even when the network fetch timed out, so partial results are always returned rather than abandoned.

Processing order:
1. Build per-node dict: `{node_id: {sub_key: [parsed values]}}`
2. Identify nodes with malformed KV entries (appends `PARTIAL_NODE_DATA` warning)
3. Cross-reference: for each node's `publish_topics` and `subscribe_topics`, accumulate publisher/subscriber sets per topic suffix
4. Apply enrichment data (description, partitions, tags) — first-write-wins per field

---

## KV Precedence Rules

This is the most non-obvious design decision and critical to understand:

**The `subscribe_topics` and `publish_topics` arrays are the single source of truth for which topics a node uses.** They are authoritative.

**The `subscribe_entries` and `publish_entries` arrays are enrichment only.** They add human-readable metadata (description, partitions, tags) but cannot change which topics a node is associated with. If entries exist for a topic that isn't in the topic arrays, those entries are ignored.

**Enrichment conflict resolution**: when both `subscribe_entries` and `publish_entries` contain data for the same topic suffix, `publish_entries` wins (last-write-wins within the enrichment merge). This is intentional — a publisher typically has more authoritative knowledge about a topic's characteristics than a subscriber.

**The `onex/topics/{topic}/subscribers` path is a derived cache.** It is never read by `ServiceTopicCatalog`. It exists only for external tools that need to reverse-lookup by topic name.

---

## In-Process Cache

The cache is a plain `dict[int, ModelTopicCatalogResponse]` keyed by `catalog_version`. Python's GIL provides sufficient protection for asyncio single-threaded event loop access.

Cache behavior:
- **Hit**: when version is stable and already cached, response is returned instantly with no Consul I/O
- **Miss**: full rebuild from Consul, then stored
- **Eviction**: when a newer version is cached, all older versions are evicted to bound memory
- **Version -1 (unknown)**: caching is disabled; every call performs a full rebuild

```text
version read from Consul -> 42
cache contains key 42    -> return _cache[42], re-apply filters

version read from Consul -> 43 (new)
cache miss               -> full rebuild
store _cache[43]
evict _cache[42]         -> memory stays bounded
```

---

## Timeout Budget and Partial Results

A 5-second timeout applies to the Consul KV recursive scan. If the scan exceeds the budget:

1. `asyncio.wait_for` raises `TimeoutError`
2. `raw_kv_items` is left as an empty list
3. `CONSUL_SCAN_TIMEOUT` is added to warnings
4. `_process_raw_kv_items([])` runs (returns empty topic map)
5. An empty response with the warning is returned — not an exception

This means the catalog always responds, even when Consul is slow. The caller checks `response.warnings` to detect degraded results.

Similarly, a 10,000-key cap (`_MAX_KV_KEYS`) prevents runaway scans. When the cap is hit, `CONSUL_KV_MAX_KEYS_REACHED` is added to warnings.

---

## Catalog Versioning and CAS

`ServiceTopicCatalog.increment_version()` atomically increments the version key using Consul's Check-and-Set (CAS):

```text
1. Read current value + ModifyIndex via kv_get_with_modify_index()
2. Compute new_version = current + 1 (or 1 if key absent/corrupt)
3. Write new_version with cas=ModifyIndex via kv_put_raw_with_cas()
   -> Success: returns new_version
   -> Failure (concurrent write): returns -1
4. Retry up to 3 times with exponential backoff: 100ms, 200ms, 400ms
5. If all retries exhausted: return -1 (caller detects and handles)
```

Catalog version increment during node registration is **not currently implemented**. `IntentEffectConsulRegister` does not call `increment_version()`, and no other caller in the registration path does either. `increment_version()` exists as a public API for future use (e.g., an explicit topology-change handler). All catalog readers detect a new version and invalidate their caches on the next `build_catalog()` call.

---

## Query Handler and Dispatcher

### `HandlerTopicCatalogQuery`

An INFRA_HANDLER/EFFECT handler that implements the "always respond" contract:

- **Valid query**: delegates to `ServiceTopicCatalog.build_catalog()`, returns full response
- **Invalid payload type**: returns empty response with `INVALID_QUERY_PAYLOAD` warning
- **Unexpected exception from service**: returns empty response with `INTERNAL_ERROR` warning
- **Consul unavailable** (already handled by service): response contains `CONSUL_UNAVAILABLE` warning

The handler never raises to its caller. Every code path ends with a `ModelHandlerOutput` containing one `ModelTopicCatalogResponse` event.

Response time tracking: `processing_time_ms` is set in `ModelHandlerOutput` using `time.perf_counter()`.

### `DispatcherTopicCatalogQuery`

Implements `ProtocolMessageDispatcher` for integration with `MessageDispatchEngine`:

- **Deserialization**: accepts `ModelTopicCatalogQuery` directly, or `dict` (validated via `model_validate`)
- **Circuit breaker**: configured for KAFKA transport (`threshold=3`, `reset_timeout=20.0s`)
- **Success**: records circuit breaker reset
- **Failure**: records circuit breaker failure, returns `HANDLER_ERROR` dispatch result
- **Circuit open**: `InfraUnavailableError` propagates (for DLQ handling by engine)
- **Validation failure**: returns `INVALID_MESSAGE` dispatch result

---

## Warnings Channel

`ModelTopicCatalogResponse.warnings` is a `tuple[str, ...]` of stable string tokens. These tokens are constants defined in `catalog_warning_codes.py` — never free-form messages.

| Token constant | Value | Emitted by | Meaning |
|----------------|-------|------------|---------|
| `CONSUL_UNAVAILABLE` | `"consul_unavailable"` | Service | Consul unreachable or no handler configured |
| `CONSUL_SCAN_TIMEOUT` | `"consul_scan_timeout"` | Service | 5s budget exceeded; partial results |
| `CONSUL_KV_MAX_KEYS_REACHED` | `"consul_kv_max_keys_reached"` | Service | Result set capped at 10,000 keys |
| `VERSION_UNKNOWN` | `"version_unknown"` | Service | Version key absent or corrupt; caching disabled |
| `PARTIAL_NODE_DATA` | `"partial_node_data"` | Service | One or more nodes had malformed KV entries |
| `INTERNAL_ERROR` | `"internal_error"` | Handler | Unexpected exception; empty response returned |
| `INVALID_QUERY_PAYLOAD` | `"invalid_query_payload"` | Handler | Malformed query; empty response returned |
| `f"unresolvable_topic:{suffix}"` | Dynamic | Service | Topic suffix could not be resolved via TopicResolver |
| `f"invalid_json_at:{key}"` | Dynamic | Service | A specific Consul KV value was not valid JSON |

**Consumer guidance**: match against constant values (or the `UNRESOLVABLE_TOPIC_PREFIX` prefix), not substring patterns. Multiple warnings can coexist in one response — for example, `VERSION_UNKNOWN` and `CONSUL_SCAN_TIMEOUT` both appear when the version key is absent and the subsequent scan times out.

A response with `warnings=()` means Consul was fully reachable, all data was parseable, and the version is known.

---

## Data Models

### `ModelTopicCatalogEntry`

A single topic in the catalog. The `is_active` field is always computed from publisher/subscriber counts — it cannot be set externally.

```python
entry = ModelTopicCatalogEntry(
    topic_suffix="onex.evt.platform.node-registration.v1",   # canonical identity
    topic_name="onex.evt.platform.node-registration.v1",     # resolved Kafka name
    description="Node registration events",
    partitions=6,
    publisher_count=2,
    subscriber_count=3,
    # is_active computed as True (publisher_count > 0 or subscriber_count > 0)
    tags=("lifecycle", "platform"),
)
assert entry.is_active is True
```

### `ModelTopicCatalogQuery`

```python
query = ModelTopicCatalogQuery(
    correlation_id=uuid4(),
    client_id="omnidash-ui",
    include_inactive=False,       # exclude topics with zero pub/sub
    topic_pattern="onex.evt.*",   # fnmatch glob; only [a-zA-Z0-9.*?_-] allowed
    schema_version=1,
)
```

### `ModelTopicCatalogResponse`

```python
response = ModelTopicCatalogResponse(
    correlation_id=query.correlation_id,   # matches query for pairing
    topics=(entry1, entry2, ...),          # sorted by topic_suffix
    catalog_version=42,                    # monotonic; 0 means error condition
    node_count=15,                         # total nodes seen during scan
    generated_at=datetime.now(UTC),
    warnings=("consul_scan_timeout",),     # empty tuple = fully healthy
    schema_version=1,
)
```

**`catalog_version=0` is a sentinel for error-condition responses** (e.g., when the handler returns an empty response due to `INTERNAL_ERROR`). A real catalog always has version >= 1.

---

## Usage Pattern

```python
# Service setup (done once during node initialization)
service = ServiceTopicCatalog(
    container=container,
    consul_handler=container.get_service("HandlerConsul"),
)

# Query (called per-request)
response = await service.build_catalog(
    correlation_id=uuid4(),
    include_inactive=False,
    topic_pattern="onex.evt.platform.*",
)

if response.warnings:
    logger.warning("Catalog built with warnings: %s", response.warnings)

for entry in response.topics:
    print(f"{entry.topic_suffix}: {entry.publisher_count} publishers, "
          f"{entry.subscriber_count} subscribers, active={entry.is_active}")

# Increment version after a topology change
new_version = await service.increment_version(correlation_id=uuid4())
if new_version == -1:
    logger.warning("CAS increment failed after 3 retries")
```

---

## See Also

- `src/omnibase_infra/services/service_topic_catalog.py` — ServiceTopicCatalog implementation
- `src/omnibase_infra/models/catalog/` — all catalog data models
- `src/omnibase_infra/nodes/node_registration_orchestrator/handlers/handler_topic_catalog_query.py` — query handler
- `src/omnibase_infra/nodes/node_registration_orchestrator/dispatchers/dispatcher_topic_catalog_query.py` — dispatcher
- `docs/architecture/REGISTRATION_ORCHESTRATOR_ARCHITECTURE.md` — how this handler fits into the orchestrator
- `docs/patterns/circuit_breaker_implementation.md` — circuit breaker mechanics used by the dispatcher
- `docs/patterns/dispatcher_resilience.md` — dispatcher pattern reference
