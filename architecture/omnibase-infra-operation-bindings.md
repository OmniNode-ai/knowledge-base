---
type: architecture
status: accepted
date: "2026-09-02"
title: "Operation Bindings: Declarative Handler Parameter Resolution"
topics: [omnibase-infra, operation, bindings]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/operation_bindings.md on 2026-09-02. -->

# Operation Bindings: Declarative Handler Parameter Resolution



## Overview

Operation bindings provide a declarative way to map event envelope fields, payload data, and runtime context into handler parameters. Instead of writing imperative code to extract fields from envelopes, handlers declare their parameter bindings in `contract.yaml` and the dispatch engine resolves them automatically.

This document covers:

- The `additional_context_paths` contract and dispatch engine obligations
- Observability and metrics for binding resolution
- Error behavior and error codes
- Best practices for context path naming and multi-tenant patterns

**Related**:  (parent feature),  (observability)

---

## Expression Syntax

Binding expressions follow the format `${source.path.to.field}` where:

- **source** is one of: `payload`, `envelope`, `context`
- **path** is a dot-separated sequence of field names (no array indexing)

```yaml
operation_bindings:
  version: { major: 1, minor: 0, patch: 0 }
  global_bindings:
    - parameter_name: "correlation_id"
      expression: "${envelope.correlation_id}"
  bindings:
    "db.query":
      - parameter_name: "sql"
        expression: "${payload.sql}"
      - parameter_name: "timestamp"
        expression: "${context.now_iso}"
        required: false
```

### Sources

| Source | Description | Access Pattern |
|--------|-------------|---------------|
| `payload` | Event payload data | `envelope.payload.<field>` |
| `envelope` | Event envelope metadata | `envelope.<field>` (e.g., `correlation_id`, `trace_id`) |
| `context` | Runtime dispatch context | Injected by dispatch engine (see below) |

### Guardrails

| Guardrail | Default | Configurable Range | Error Code |
|-----------|---------|-------------------|------------|
| Max expression length | 256 chars | 32 - 1024 | `BINDING_LOADER_013` |
| Max path depth | 20 segments | 3 - 50 | `BINDING_LOADER_012` |
| No array indexing | Always enforced | N/A | `BINDING_LOADER_010` |
| Valid sources only | Always enforced | N/A | `BINDING_LOADER_011` |
| Context path allowlist | Always enforced | Extensible via `additional_context_paths` | `BINDING_LOADER_016` |

---

## The `additional_context_paths` Contract

### Overview

The base context paths provided by the dispatch engine are:

| Path | Type | Description |
|------|------|-------------|
| `now_iso` | `str` | Current timestamp in ISO 8601 format |
| `dispatcher_id` | `str` | Unique identifier of the dispatcher instance |
| `correlation_id` | `UUID` | Request correlation ID for distributed tracing |

When a handler needs additional context values (e.g., tenant ID, request ID), it declares them via `additional_context_paths` in the contract:

```yaml
operation_bindings:
  additional_context_paths:
    - "tenant_id"
    - "request_id"
  bindings:
    "db.query":
      - parameter_name: "tenant"
        expression: "${context.tenant_id}"
        required: true
```

### Dispatch Engine Obligation

**This is a contractual obligation.** When a handler declares `additional_context_paths`, the dispatch engine is **obligated** to provide these values in the context dict passed to binding resolution.

The dispatch engine fulfills this contract by populating the context before resolution:

```python
# In MessageDispatchEngine._dispatch_to_entry()
dispatch_context: dict[str, object] = {
    "now_iso": datetime.now(UTC).isoformat(),
    "dispatcher_id": entry.dispatcher_id,
    "correlation_id": correlation_id,
    # Additional context paths must be populated here
    # by the dispatch engine or upstream middleware
}
```

### Error Behavior When Context Is Missing

If a declared `additional_context_path` is not provided in the dispatch context:

1. **Warning is logged** with the missing path names, dispatcher ID, and correlation ID
2. **Binding resolution continues** -- the expression resolves to `None`
3. **If the binding is `required: true`** -- a `BindingResolutionError` is raised with diagnostic context
4. **If the binding is `required: false` with a default** -- the default value is used

```python
# Missing required context path -> BindingResolutionError
BindingResolutionError(
    "Required binding 'tenant' resolved to None",
    operation_name="db.query",
    parameter_name="tenant",
    expression="${context.tenant_id}",
    correlation_id=correlation_id,
)
```

### Context Path Naming Rules

Context path names must follow this pattern: `^[a-z][a-z0-9_]*$`

| Constraint | Example Valid | Example Invalid |
|-----------|-------------|----------------|
| Start with lowercase letter | `tenant_id` | `TenantId`, `123abc` |
| Only lowercase, numbers, underscores | `user_session_v2` | `user-session`, `user.session` |
| No dots (reserved for path traversal) | `tenant_id` | `tenant.id` |
| No duplicates with base paths | `request_id` | `now_iso` (already a base path) |

**Error code**: `BINDING_LOADER_022` (INVALID_CONTEXT_PATH_NAME)

---

## Multi-Tenant Context Patterns

### Pattern 1: Tenant Isolation via Context Binding

```yaml
operation_bindings:
  additional_context_paths:
    - "tenant_id"
    - "tenant_region"
  bindings:
    "db.query":
      - parameter_name: "tenant"
        expression: "${context.tenant_id}"
        required: true
      - parameter_name: "region"
        expression: "${context.tenant_region}"
        required: false
        default: "us-east-1"
```

The dispatch engine populates tenant context from the incoming request:

```python
dispatch_context["tenant_id"] = extract_tenant_from_request(envelope)
dispatch_context["tenant_region"] = lookup_tenant_region(tenant_id)
```

### Pattern 2: Request Tracing via Context

```yaml
operation_bindings:
  additional_context_paths:
    - "request_id"
    - "trace_parent"
  global_bindings:
    - parameter_name: "request_id"
      expression: "${context.request_id}"
      required: false
    - parameter_name: "trace_parent"
      expression: "${context.trace_parent}"
      required: false
```

### Pattern 3: Feature Flags via Context

```yaml
operation_bindings:
  additional_context_paths:
    - "feature_flags"
  bindings:
    "process.order":
      - parameter_name: "flags"
        expression: "${context.feature_flags}"
        required: false
        default: {}
```

---

## Resolution Order

Binding resolution follows a deterministic order:

1. **Global bindings** are applied first (shared across all operations)
2. **Operation-specific bindings** override globals for the same parameter name
3. **Required bindings** are validated -- `None` values trigger fail-fast error
4. **Optional bindings** use defaults when resolved value is `None`

```yaml
operation_bindings:
  global_bindings:
    - parameter_name: "source"
      expression: "${envelope.trace_id}"  # Applied first
  bindings:
    "db.query":
      - parameter_name: "source"
        expression: "${payload.data}"      # Overrides global
```

---

## Observability and Metrics

### Binding Resolution Metrics

The `OperationBindingResolver` emits metrics for every resolution attempt, accessible via the `metrics` property:

```python
resolver = OperationBindingResolver()

# ... resolve bindings ...

m = resolver.metrics
print(f"Total resolutions: {m.total_resolutions}")
print(f"Success rate: {m.success_rate:.1%}")
print(f"Avg latency: {m.avg_latency_ms:.2f}ms")
print(f"Bindings resolved: {m.bindings_resolved_count}")
```

### Available Metrics

| Metric | Type | Description | Prometheus Name |
|--------|------|-------------|----------------|
| `total_resolutions` | Counter | Total resolution attempts | `onex_binding_resolutions_total` |
| `successful_resolutions` | Counter | Successful resolutions | `onex_binding_resolutions_total{status="success"}` |
| `failed_resolutions` | Counter | Failed resolutions | `onex_binding_resolutions_total{status="error"}` |
| `bindings_resolved_count` | Counter | Individual bindings resolved | `onex_bindings_resolved_total` |
| `latency_histogram` | Histogram | Resolution duration distribution | `onex_binding_resolution_duration_ms` |
| `error_counts_by_code` | Counter (labeled) | Failures by error code | `onex_binding_resolution_errors_total{code="..."}` |
| `per_operation_resolutions` | Counter (labeled) | Resolutions by operation | `onex_binding_resolutions_total{operation="..."}` |
| `per_operation_errors` | Counter (labeled) | Errors by operation | `onex_binding_resolution_errors_total{operation="..."}` |
| `missing_context_path_warnings` | Counter | Missing context path warnings | `onex_binding_context_path_warnings_total` |

### Latency Histogram Buckets

Binding resolution is typically sub-millisecond. The histogram uses fine-grained buckets:

```
0.1ms, 0.5ms, 1ms, 2.5ms, 5ms, 10ms, 25ms, 50ms, 100ms, >100ms
```

### Exporting Metrics

The metrics model provides a `to_dict()` method for JSON-compatible export:

```python
import json

metrics_snapshot = resolver.metrics.to_dict()
json.dumps(metrics_snapshot)  # Prometheus pushgateway, StatsD, logging, etc.
```

For periodic export with counter reset:

```python
# Export and reset
snapshot = resolver.metrics
resolver.reset_metrics()
export_to_prometheus(snapshot.to_dict())
```

### Debug Logging

Binding resolution emits structured debug logs on every resolution:

```
DEBUG binding_resolver: Binding resolution succeeded for operation 'db.query' (0.23ms, 3 bindings resolved)
DEBUG binding_resolver: Binding resolution failed for operation 'db.query' (0.15ms, 1 bindings resolved before failure)
```

Enable with `logging.getLogger("omnibase_infra.runtime.binding_resolver").setLevel(logging.DEBUG)`.

---

## Error Codes Reference

### Expression Validation Errors (010-019)

| Code | Name | Description |
|------|------|-------------|
| `BINDING_LOADER_010` | `EXPRESSION_MALFORMED` | Invalid syntax or array access attempted |
| `BINDING_LOADER_011` | `INVALID_SOURCE` | Source is not `payload`, `envelope`, or `context` |
| `BINDING_LOADER_012` | `PATH_TOO_DEEP` | Path exceeds max segments |
| `BINDING_LOADER_013` | `EXPRESSION_TOO_LONG` | Expression exceeds max length |
| `BINDING_LOADER_014` | `EMPTY_PATH_SEGMENT` | Path contains empty segment (e.g., `${payload..field}`) |
| `BINDING_LOADER_016` | `INVALID_CONTEXT_PATH` | Context path not in allowlist |

### Binding Validation Errors (020-029)

| Code | Name | Description |
|------|------|-------------|
| `BINDING_LOADER_020` | `UNKNOWN_OPERATION` | Operation name not in `io_operations` list |
| `BINDING_LOADER_021` | `DUPLICATE_PARAMETER` | Duplicate parameter name within scope |
| `BINDING_LOADER_022` | `INVALID_CONTEXT_PATH_NAME` | Invalid context path name format |

### File/Contract Errors (030-039)

| Code | Name | Description |
|------|------|-------------|
| `BINDING_LOADER_030` | `CONTRACT_NOT_FOUND` | Contract file does not exist |
| `BINDING_LOADER_031` | `YAML_PARSE_ERROR` | Invalid YAML syntax |

### Security Errors (050-059)

| Code | Name | Description |
|------|------|-------------|
| `BINDING_LOADER_050` | `FILE_SIZE_EXCEEDED` | Contract file exceeds 10MB limit |

---

## Per-Contract Guardrail Overrides

Guardrails can be customized per contract:

```yaml
operation_bindings:
  version: { major: 1, minor: 0, patch: 0 }
  max_expression_length: 512   # Override default 256
  max_path_segments: 30        # Override default 20
  max_json_recursion_depth: 50 # Override default 100
```

| Parameter | Default | Min | Max | Purpose |
|-----------|---------|-----|-----|---------|
| `max_expression_length` | 256 | 32 | 1024 | Expression length limit |
| `max_path_segments` | 20 | 3 | 50 | Path depth limit |
| `max_json_recursion_depth` | 100 | 10 | 1000 | JSON validation depth |

---

## Best Practices

### DO

- Declare all required context paths in `additional_context_paths`
- Use descriptive, lowercase_snake_case names for context paths
- Provide defaults for optional bindings that may not always be available
- Monitor `missing_context_path_warnings` metric for contract violations
- Use global bindings for parameters shared across all operations

### DO NOT

- Rely on undeclared context paths -- always declare in `additional_context_paths`
- Use dots in context path names (reserved for path traversal)
- Duplicate base context path names (`now_iso`, `dispatcher_id`, `correlation_id`)
- Use array indexing in expressions (`${payload.items[0]}` is not supported)
- Exceed guardrail limits without explicit contract override

---

## See Also

- **Error Handling Patterns (internal knowledge base)** -- Error context and `BindingResolutionError`
- **Correlation ID Tracking (`../architecture/omnibase-infra-correlation-id-tracking.md`)** -- Request tracing with `correlation_id`
- **Operation Routing (`../architecture/omnibase-infra-operation-routing.md`)** -- Contract-driven operation dispatch
- **Dispatcher Resilience (internal knowledge base)** -- Dispatcher-owned resilience patterns
