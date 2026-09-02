---
type: reference
status: current
date: "2026-09-02"
title: "ADR-003: Remove Health Check Methods from Handlers"
topics: [omnibase-infra, adr, remove, handler]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-003-remove-handler-health-checks.md on 2026-09-02. -->

# ADR-003: Remove Health Check Methods from Handlers

## Status

Accepted

## Date

2025-12-26

## Context

The handler implementations (HandlerVault, HandlerConsul, HandlerDb, HttpRestHandler) each contained `health_check()` methods that returned information about their connection state and readiness. A code review (PR #91) identified inconsistency in the return types across handlers:

- HandlerVault: `dict[str, JsonValue]`
- HandlerConsul: `dict[str, JsonValue]`
- HandlerDb: `ModelDbHealthResponse` (typed Pydantic model)
- HttpRestHandler: `dict[str, JsonValue]`

The initial ticket proposed standardizing these return types. However, architectural analysis revealed a more fundamental question: **Why do handlers need health check methods at all?**

### Event-Based Architecture Context

ONEX uses an event-based architecture where:

1. **Handlers consume events from Kafka**, not HTTP requests from load balancers
2. **Kafka handles consumer coordination** through consumer groups and partition rebalancing
3. **Failures are handled by the event system** through retry queues and Dead Letter Queues (DLQ)

This differs fundamentally from HTTP-based microservices where health checks serve critical functions:

| Concern | HTTP Service | Event-Based Handler |
|---------|--------------|---------------------|
| Traffic routing | Load balancer uses `/health` to route requests | Kafka partitions route events automatically |
| Failure handling | Remove unhealthy instance from rotation | Event goes to retry queue, reprocessed when dependency recovers |
| Scaling | Health checks inform autoscaler | Consumer lag metrics inform autoscaler |
| Dependency availability | Health check fails → stop routing | Dependency fails → event goes to DLQ → retry when available |

## Decision

**Remove health check methods from all handlers** rather than standardize them.

### What Was Removed

| Handler | Methods Removed | Models Removed | Operations Removed |
|---------|-----------------|----------------|-------------------|
| HandlerVault | `health_check()`, `_health_check_operation()` | `ModelVaultHealthCheckPayload` | `vault.health_check` |
| HandlerConsul | `health_check()`, `_health_check_operation()` | `ModelConsulHealthCheckPayload` | `consul.health_check` |
| HandlerDb | `health_check()` | `ModelDbHealthResponse` | N/A |
| HttpRestHandler | `health_check()` | `ModelHttpHealthCheckPayload` | N/A |

### What Was Preserved

- **`describe()` methods**: Retained for capability introspection (what operations a handler supports)
- **`health_check_interval_seconds`** in Consul config: This is for Consul's own service health checks on registered services, not the handler's health check operation
- **Circuit breaker state**: Still tracked internally, exposed via metrics (not health endpoints)

## Consequences

### Positive

1. **Simpler handler interface**: `initialize()`, `execute()`, `shutdown()` - that's it
2. **Aligned with event architecture**: No HTTP-style patterns in event-based components
3. **Reduced code**: ~1,500 lines removed across handlers, models, and tests
4. **Clearer observability model**: Health → metrics, not endpoints
5. **No standardization debt**: No need to maintain consistent health check contracts

### Negative

1. **Debugging changes**: Developers must use metrics/logs instead of calling `handler.health_check()`
2. **Migration for existing consumers**: Any code calling handler health checks must be updated

### Neutral

1. **Kubernetes liveness probes**: These check if the process is alive, not handler health. A simple "return 200" endpoint at the runtime level is sufficient.
2. **Readiness probes**: For event-based systems, "ready" means "consuming from Kafka", which is already observable through consumer group status.

## Alternatives Considered

### 1. Standardize Health Check Return Types

**Approach**: Create a common `ModelHandlerHealthResponse` that all handlers return.

**Why rejected**:
- Each handler has different health semantics (Vault has token TTL, Consul has leader status, DB has pool size)
- A common model would have many optional fields or be overly generic
- Doesn't address the fundamental question of why handlers need health checks

### 2. Add Health Check Protocol

**Approach**: Define `ProtocolHealthCheckable` in `omnibase_spi` that handlers implement.

**Why rejected**:
- Still doesn't answer "who calls this and why?"
- In event-based systems, the runtime aggregates component health, not individual handlers
- Adds protocol complexity without clear consumer

### 3. Keep Health Checks for Debugging

**Approach**: Retain health checks but don't standardize them; treat as internal debugging tools.

**Why rejected**:
- Inconsistent API remains a maintenance burden
- Debugging is better served by structured logging and metrics
- `describe()` method already provides capability introspection

## Observability Model

With health checks removed, observability comes from:

| What to Observe | Mechanism | Tool |
|-----------------|-----------|------|
| Handler processing events | Consumer lag | Kafka metrics |
| Handler failures | DLQ depth | Kafka metrics |
| Circuit breaker state | Prometheus gauge | Metrics endpoint |
| Connection pool status | Prometheus gauge | Metrics endpoint |
| Handler lifecycle | Structured logs | Log aggregator |

## Implementation Notes

### Key Files Changed

- `src/omnibase_infra/handlers/handler_*.py`: Removed health_check methods
- `src/omnibase_infra/handlers/models/*/model_*_health_check_payload.py`: Deleted
- `src/omnibase_infra/handlers/models/*/enum_*_operation_type.py`: Removed HEALTH_CHECK values
- `tests/unit/handlers/test_handler_*.py`: Removed health check tests
- `tests/integration/handlers/test_*_handler_integration.py`: Removed health check tests

### Migration Path

If existing code calls `handler.health_check()`:

1. **For debugging**: Use logging or attach a debugger
2. **For monitoring**: Expose metrics via Prometheus client
3. **For capability introspection**: Use `handler.describe()`

## References

- **PR #99**: Implementation pull request
- **PR #91**: Code review that identified the inconsistency
