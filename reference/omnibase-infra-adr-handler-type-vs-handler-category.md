---
type: reference
status: current
date: "2026-09-02"
title: "ADR: EnumHandlerType vs EnumHandlerTypeCategory Distinction"
topics: [omnibase-infra, adr, handler, type]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-handler-type-vs-handler-category.md on 2026-09-02. -->

# ADR: EnumHandlerType vs EnumHandlerTypeCategory Distinction

**Status**: Accepted
**Date**: 2025-12-29

## Context

ONEX infrastructure handlers expose two distinct type properties that serve different purposes:

1. **handler_type** (via `EnumHandlerType`)
   - Values: `INFRA_HANDLER`, `DOMAIN_HANDLER`, `ORCHESTRATION_HANDLER`
   - Purpose: Architectural role classification

2. **handler_category** (via `EnumHandlerTypeCategory`)
   - Values: `EFFECT`, `COMPUTE`, `REDUCER`, `ORCHESTRATOR`
   - Purpose: Behavioral classification (node archetype alignment)

Previously, handlers returned transport-specific strings for `handler_type` (e.g., "consul", "database", "http", "vault"), which conflated architectural role with protocol identification.

## Decision

**Handlers use a three-dimensional type system:**

| Property | Enum | Example Value | Purpose |
|----------|------|---------------|---------|
| `handler_type` | `EnumHandlerType.INFRA_HANDLER` | `"infra_handler"` | Architectural role |
| `handler_category` | `EnumHandlerTypeCategory.EFFECT` | `"effect"` | Behavioral classification |
| `transport_type` | `EnumInfraTransportType.HTTP` | `"http"` | Protocol/transport identifier |

### Handler Type (Architectural Role)

`EnumHandlerType` classifies handlers by their architectural responsibility:

- **INFRA_HANDLER**: Protocol adapters (HTTP, Kafka, Consul, Vault, Database)
- **DOMAIN_HANDLER**: Business logic handlers
- **ORCHESTRATION_HANDLER**: Workflow coordination handlers

All infrastructure protocol handlers return `EnumHandlerType.INFRA_HANDLER`.

### Handler Category (Behavioral Classification)

`EnumHandlerTypeCategory` aligns handlers with node archetypes:

- **EFFECT**: Side-effecting I/O operations (database writes, HTTP calls, service discovery)
- **COMPUTE**: Pure transformations (message formatting, validation)
- **REDUCER**: State aggregation (event sourcing, FSM transitions)
- **ORCHESTRATOR**: Workflow coordination (saga orchestration, multi-step flows)

All infrastructure protocol handlers return `EnumHandlerTypeCategory.EFFECT` because they perform external I/O.

### Transport Type (Protocol Identifier)

`EnumInfraTransportType` identifies the specific protocol/transport:

- `HTTP`, `DATABASE`, `KAFKA`, `CONSUL`, `VAULT`, `VALKEY`, etc.

This replaces the old transport-specific `handler_type` strings.

## Rationale

### Why three dimensions

1. **Separation of concerns**: Architectural role, behavioral pattern, and protocol are orthogonal
2. **Query flexibility**: Filter handlers by any dimension (e.g., "all EFFECT handlers" or "all INFRA_HANDLERs")
3. **Node archetype alignment**: `handler_category` directly maps to ONEX node archetypes
4. **Registry compatibility**: `EnumHandlerType` is used for handler registration and lookup

### Why INFRA_HANDLER for all protocol handlers

1. **Consistent categorization**: All external service adapters share the same architectural role
2. **Registry grouping**: Infrastructure handlers are registered together
3. **Error handling**: Infrastructure errors use the same error hierarchy

### Why EFFECT for all protocol handlers

1. **Side-effect semantics**: All protocol handlers perform I/O operations
2. **Testing implications**: EFFECT handlers require mocking for unit tests
3. **Execution shape validation**: EFFECT handlers have specific input/output contracts

## Consequences

### Positive

- Clear semantic distinction between architectural role and behavioral classification
- Transport-specific identification via dedicated `transport_type` property
- Consistent with ONEX node archetype system
- Enables precise filtering and querying of handlers

### Negative

- Breaking change for tests expecting transport-specific `handler_type` values
- Requires updating `describe()` output to include all three dimensions
- Developers must understand the three-dimensional type system

## Implementation

### Handler properties

```python
class HttpRestHandler(BaseHandler):
    @property
    def handler_type(self) -> EnumHandlerType:
        """Return architectural role."""
        return EnumHandlerType.INFRA_HANDLER

    @property
    def handler_category(self) -> EnumHandlerTypeCategory:
        """Return behavioral classification."""
        return EnumHandlerTypeCategory.EFFECT

    @property
    def transport_type(self) -> EnumInfraTransportType:
        """Return protocol identifier."""
        return EnumInfraTransportType.HTTP
```

### describe() output

```python
def describe(self) -> dict[str, Any]:
    return {
        "handler_type": self.handler_type.value,        # "infra_handler"
        "handler_category": self.handler_category.value, # "effect"
        "transport_type": self.transport_type.value,     # "http"
        # ... other metadata
    }
```

### Test assertions

```python
# OLD (deprecated)
assert handler.handler_type == "http"  # ❌

# NEW
assert handler.handler_type == EnumHandlerType.INFRA_HANDLER  # ✅
assert handler.handler_category == EnumHandlerTypeCategory.EFFECT  # ✅
assert handler.transport_type == EnumInfraTransportType.HTTP  # ✅
```

## References

- `src/omnibase_infra/enums/enum_handler_type.py`
- `src/omnibase_infra/enums/enum_handler_type_category.py`
- `src/omnibase_infra/enums/enum_infra_transport_type.py`
- `src/omnibase_infra/handlers/handler_http.py`
- `src/omnibase_infra/handlers/handler_db.py`
- `src/omnibase_infra/handlers/handler_consul.py`
- `src/omnibase_infra/handlers/handler_vault.py`
- CLAUDE.md "Handler Architecture" section
