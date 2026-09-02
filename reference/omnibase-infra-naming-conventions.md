---
type: reference
status: current
date: "2026-09-02"
title: "Naming Conventions"
topics: [omnibase-infra, naming, conventions]
refs: []
---

<!-- Migrated from omnibase_infra:docs/conventions/NAMING_CONVENTIONS.md on 2026-09-02. -->

# Naming Conventions

> **Status**: Current | **Last Updated**: 2026-02-19

Naming conventions for all artifact types in `omnibase_infra`. The authoritative summary table lives in `CLAUDE.md` (Pydantic Model Standards section). This document expands on that table with rationale, examples verified against actual source, and coverage of node-specific artifacts not in the summary.

---

## Table of Contents

1. [File and Class Naming](#file-and-class-naming)
2. [Node Directory Naming](#node-directory-naming)
3. [Handler Naming](#handler-naming)
4. [Dispatcher Naming](#dispatcher-naming)
5. [Registry Naming](#registry-naming)
6. [Error File Naming](#error-file-naming)
7. [Enum Naming](#enum-naming)
8. [Protocol Naming](#protocol-naming)
9. [Store Naming](#store-naming)
10. [Util Naming](#util-naming)
11. [Common Mistakes](#common-mistakes)

---

## File and Class Naming

The table below is reproduced from `CLAUDE.md` for reference. The source of truth is `CLAUDE.md`; this document adds concrete examples from `src/omnibase_infra/`.

| Type | File Pattern | Class Pattern | Example File | Example Class |
|------|-------------|---------------|--------------|---------------|
| Model | `model_<name>.py` | `Model<Name>` | `model_infra_error_context.py` | `ModelInfraErrorContext` |
| Adapter | `adapter_<name>.py` | `Adapter<Name>` | `adapter_onex_tool_execution.py` | `AdapterOnexToolExecution` |
| Dispatcher | `dispatcher_<name>.py` | `Dispatcher<Name>` | `dispatcher_node_heartbeat.py` | `DispatcherNodeHeartbeat` |
| Enum | `enum_<name>.py` | `Enum<Name>` | `enum_circuit_state.py` | `EnumCircuitState` |
| Mixin | `mixin_<name>.py` | `Mixin<Name>` | `mixin_async_circuit_breaker.py` | `MixinAsyncCircuitBreaker` |
| Protocol | `protocol_<name>.py` | `Protocol<Name>` | `protocol_dispatch_engine.py` | `ProtocolDispatchEngine` |
| Service | `service_<name>.py` | `Service<Name>` | `service_health.py` | `ServiceHealth` |
| Store | `store_<name>.py` | `Store<Purpose><Backend>` | `store_effect_idempotency_inmemory.py` | `StoreEffectIdempotencyInmemory` |
| Validator | `validator_<name>.py` | `Validator<Name>` | `validator_contracts.py` | `ValidatorContracts` |
| Registry (node) | `registry_infra_<name>.py` | `RegistryInfra<Name>` | `registry_infra_node_registration_orchestrator.py` | `RegistryInfraNodeRegistrationOrchestrator` |
| Registry (standalone) | `registry_<purpose>.py` | `Registry<Purpose>` | `registry_effect.py` | `RegistryEffect` |
| Handler | `handler_<name>.py` | `Handler<Name>` | `handler_node_heartbeat.py` | `HandlerNodeHeartbeat` |
| Error | `error_<name>.py` | (class named after error) | `error_chain_propagation.py` | `ChainPropagationError` |

### Notes

- **Model** covers Pydantic data models (inputs, outputs, configs, payloads). All Pydantic classes must have the `Model` prefix.
- **Store** names encode both purpose and backend: `Store<What><Where>` (e.g., `StoreEffectIdempotencyInmemory`, `StoreEffectIdempotencyPostgres`).
- **Error files** use `error_<name>.py` but the *class* does not use a prefix; it uses the full descriptive error class name (e.g., `ChainPropagationError`, not `ErrorChainPropagation`).
- **Registry (node)** files always use `registry_infra_` prefix to signal they wire a specific node's DI container, distinct from standalone registries.

---

## Node Directory Naming

Node directories follow the pattern `node_<name>_<type>/`:

```text
nodes/
    node_registration_orchestrator/    # ORCHESTRATOR_GENERIC
    node_registration_reducer/         # REDUCER_GENERIC
    node_registration_storage_effect/  # EFFECT_GENERIC
    node_checkpoint_effect/            # EFFECT_GENERIC
    node_baseline_comparison_compute/  # COMPUTE_GENERIC
    node_ledger_projection_compute/    # COMPUTE_GENERIC
```

The type suffix (`_effect`, `_compute`, `_reducer`, `_orchestrator`) is **required** and must match the `node_type` declared in `contract.yaml`.

### Canonical Node Directory Structure

```text
nodes/<node_name>/
    __init__.py
    contract.yaml               # ONEX contract (REQUIRED)
    node.py                     # Declarative node class (REQUIRED)
    models/
        __init__.py
        model_<name>.py
    registry/
        __init__.py
        registry_infra_<node_name>.py
    handlers/                   # optional
        __init__.py
        handler_<name>.py
    dispatchers/                # optional
        __init__.py
        dispatcher_<name>.py
```

Every file inside a node directory follows the same global prefixing rules. For example, inside `handlers/`, files are named `handler_<name>.py` — not `handle_<name>.py` or `<name>_handler.py`.

---

## Handler Naming

Handlers implement `ProtocolHandler` (envelope-based) or `ProtocolMessageHandler` (category-based).

### File and Class

```
handler_<descriptive_name>.py
```

Class: `Handler<DescriptiveName>` in PascalCase.

### Examples from `src/`

| File | Class |
|------|-------|
| `handler_node_heartbeat.py` | `HandlerNodeHeartbeat` |
| `handler_node_introspected.py` | `HandlerNodeIntrospected` |
| `handler_node_registration_acked.py` | `HandlerNodeRegistrationAcked` |
| `handler_runtime_tick.py` | `HandlerRuntimeTick` |
| `handler_topic_catalog_query.py` | `HandlerTopicCatalogQuery` |

### Handler Classification Properties

Every handler must expose:

```python
@property
def handler_type(self) -> EnumHandlerType:
    """Architectural role: INFRA_HANDLER, NODE_HANDLER, PROJECTION_HANDLER."""
    return EnumHandlerType.INFRA_HANDLER

@property
def handler_category(self) -> EnumHandlerTypeCategory:
    """Behavioral classification: EFFECT, COMPUTE, NONDETERMINISTIC_COMPUTE."""
    return EnumHandlerTypeCategory.EFFECT
```

### Handler No-Publish Constraint

Handlers **must not** have direct event bus access. The constraint is verified by:
- Absence of `_bus`, `_event_bus`, or `_publisher` attributes
- No `publish()`, `emit()`, or `send_event()` methods

Only ORCHESTRATOR nodes publish events; they do so after receiving handler output.

---

## Dispatcher Naming

Dispatchers are adapter objects that route handler output to the event bus. They live alongside their corresponding handler in the `dispatchers/` subdirectory.

### File and Class

```
dispatcher_<descriptive_name>.py
```

Class: `Dispatcher<DescriptiveName>` — mirrors the handler name exactly.

### Examples from `src/`

| Handler File | Dispatcher File |
|-------------|----------------|
| `handler_node_heartbeat.py` | `dispatcher_node_heartbeat.py` |
| `handler_node_introspected.py` | `dispatcher_node_introspected.py` |
| `handler_node_registration_acked.py` | `dispatcher_node_registration_acked.py` |

### Dispatcher Resilience

Dispatchers own their own resilience. The `MessageDispatchEngine` does **not** wrap dispatchers with circuit breakers — each dispatcher implements `MixinAsyncCircuitBreaker` for external calls and raises `InfraUnavailableError` when the circuit opens.

---

## Registry Naming

Two variants exist depending on scope.

### Node Registry (wires a specific node)

```
registry/registry_infra_<node_name>.py
```

Class: `RegistryInfra<NodeName>`

Examples:
- `registry_infra_node_registration_orchestrator.py` → `RegistryInfraNodeRegistrationOrchestrator`
- `registry_infra_registration_storage.py` → `RegistryInfraRegistrationStorage`

### Standalone Registry

```
registry_<purpose>.py
```

Class: `Registry<Purpose>`

Example:
- `registry_effect.py` → `RegistryEffect`

---

## Error File Naming

Error files live in `src/omnibase_infra/errors/` and follow `error_<name>.py`. The class inside uses a full descriptive error name without an `Error` suffix in the filename base.

```text
errors/
    error_architecture_violation.py   → ArchitectureViolationError
    error_binding_resolution.py       → BindingResolutionError
    error_chain_propagation.py        → ChainPropagationError
    error_container_wiring.py         → ContainerWiringError
    error_consul.py                   → InfraConsulError
    error_db_ownership.py             → DbOwnershipMismatchError, DbOwnershipMissingError
    error_event_bus_registry.py       → EventBusRegistryError
```

Note: A single error file may contain multiple closely related error classes (e.g., `error_db_ownership.py` contains both `DbOwnershipMismatchError` and `DbOwnershipMissingError`).

---

## Enum Naming

All enum files are in `src/omnibase_infra/enums/` and follow `enum_<name>.py`.

The class uses `Enum<Name>` with PascalCase. Member values are `UPPER_SNAKE_CASE`.

```text
enum_circuit_state.py   → EnumCircuitState  (CLOSED, OPEN, HALF_OPEN)
enum_backend_type.py    → EnumBackendType
enum_auth_decision.py   → EnumAuthDecision
```

---

## Protocol Naming

Protocol files live in `src/omnibase_infra/protocols/` and follow `protocol_<name>.py`.

The class uses `Protocol<Name>`. Protocols define interfaces; they contain only method signatures with type annotations and docstrings — no implementation.

```text
protocol_dispatch_engine.py     → ProtocolDispatchEngine
protocol_event_bus_like.py      → ProtocolEventBusLike
protocol_idempotency_store.py   → ProtocolIdempotencyStore
protocol_ledger_sink.py         → ProtocolLedgerSink
```

When declaring a protocol-based service in DI, use the string name:

```python
bus = container.get_service("ProtocolEventBus")
```

---

## Store Naming

Stores combine purpose and backend in their name: `Store<What><Backend>`.

```text
store_effect_idempotency_inmemory.py   → StoreEffectIdempotencyInmemory
```

When a Postgres-backed variant exists, it would be:

```
store_effect_idempotency_postgres.py   → StoreEffectIdempotencyPostgres
```

This pattern makes the backend explicit and avoids ambiguity when multiple backends coexist.

---

## Util Naming

Utility modules live in `src/omnibase_infra/utils/` and follow `util_<name>.py`. Functions inside are named with verbs in `snake_case`.

Example:
```
utils/util_error_sanitization.py
```

Functions: `sanitize_error_message()`, `sanitize_secret_path()`

---

## Common Mistakes

| Wrong | Correct | Rule |
|-------|---------|------|
| `node_registration.py` (node dir missing type) | `node_registration_orchestrator/` | Node dirs include `_<type>` suffix |
| `ErrorChainPropagation` | `ChainPropagationError` | Error classes do not use `Error` prefix |
| `RegistryNodeRegistration` | `RegistryInfraNodeRegistrationOrchestrator` | Node registries use `RegistryInfra` prefix |
| `StoreIdempotency` | `StoreEffectIdempotencyInmemory` | Store names encode purpose AND backend |
| `handle_heartbeat.py` | `handler_node_heartbeat.py` | Handler files use full `handler_` prefix |
| `dispatch_heartbeat.py` | `dispatcher_node_heartbeat.py` | Dispatcher files use full `dispatcher_` prefix |

---

## Related Documentation

- `CLAUDE.md` — Authoritative naming table (Pydantic Model Standards section)
- `docs/conventions/PYDANTIC_BEST_PRACTICES.md` — Model ConfigDict and field patterns
- `docs/conventions/TERMINOLOGY_GUIDE.md` — Canonical term definitions
- `docs/patterns/handler_plugin_loader.md` — Handler contract declaration and namespace allowlisting
- `docs/patterns/container_dependency_injection.md` — DI container wiring patterns
