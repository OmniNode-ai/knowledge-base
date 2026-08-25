---
type: adr
status: accepted
date: "2025-10-30"
title: "ADR-0030: Protocol-Based Dependency Injection Architecture"
adr_id: ADR-0030
topics: [omnibase_core, dependency-injection, protocols, service-registry, architecture]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0030: Protocol-Based Dependency Injection Architecture

**Status**: Implemented
**Date**: 2025-10-30
**Updated**: 2025-12-18
**Deciders**: ONEX Framework Team
**Source**: omnibase_core `docs/decisions/ADR-001-protocol-based-di-architecture.md`

> **Note (v0.3.6+)**: This decision was written when `omnibase_core` depended on `omnibase_spi`
> for protocol definitions. As of v0.3.6, the dependency was inverted — SPI now depends
> on Core. Protocol definitions are Core-native in `omnibase_core.protocols`.
> References to `omnibase_spi` protocols should be understood as referring to the current
> `omnibase_core.protocols` module.

---

## Context

The omnibase_core framework requires a robust dependency injection (DI) system that supports:

1. **Protocol-driven interfaces** (Core-native protocols in `omnibase_core.protocols`)
2. **Type-safe service resolution**
3. **Multiple service lifecycles** (singleton, transient, scoped)
4. **Observable service management** (health monitoring, performance tracking)
5. **Pydantic validation** for all configurations and contracts

### The "Registry" Terminology Problem

The term "registry" appears in three distinct architectural contexts within omnibase_core, leading to confusion:

1. **ServiceRegistry** — Dependency injection container (compile-time resolution)
2. **Business Registries** — CLI/event discovery systems (contract-time discovery)
3. **MixinServiceRegistry** — Runtime tool discovery (event-time discovery)

This decision clarifies these distinctions and establishes the protocol-based DI pattern as the canonical approach.

---

## Decision

We adopt **Protocol-Based Dependency Injection** via `ServiceRegistry` as the exclusive DI mechanism for omnibase_core.

### Core Principles

1. **Protocol Interfaces Only**: All services resolved by protocol interface, never by concrete class
2. **Pydantic Validation**: All configuration/registration models are Pydantic BaseModel subclasses
3. **Type-Safe Resolution**: Generic type parameters ensure compile-time type safety
4. **Observable Lifecycle**: All registrations tracked with health monitoring and performance metrics
5. **Clear Separation**: Business domain registries serve distinct purposes from DI container

---

## Architectural Components

### 1. ServiceRegistry (DI Container)

**Purpose**: Protocol-based dependency injection and service lifecycle management

**Key Classes**:
- `ServiceRegistry` — Main DI container (implements `ProtocolServiceRegistry`)
- `ModelServiceRegistryConfig` — Configuration (Pydantic BaseModel)
- `ModelServiceRegistryStatus` — Health/status reporting (Pydantic BaseModel)
- `ModelServiceRegistration` — Service registration metadata (Pydantic BaseModel)

**Usage Pattern**:
```python
# Initialize registry
config = create_default_registry_config()
registry = ServiceRegistry(config)

# Register service by protocol interface
await registry.register_instance(
    interface=ProtocolLoggerLike,
    instance=logger_instance,
    scope="global"
)

# Resolve service by protocol
logger = await registry.resolve_service(ProtocolLoggerLike)
```

**Files** (2026-08-25 migration note: renamed since this decision was written —
`container/service_registry.py` is now `container/container_service_registry.py`):
- `src/omnibase_core/container/container_service_registry.py`
- `src/omnibase_core/models/container/model_registry_config.py`
- `src/omnibase_core/models/container/model_registry_status.py`

### 2. Business Domain Registries (Separate Concern)

**Purpose**: Dynamic discovery of CLI actions, events, and commands from node contracts

These are **NOT dependency injection registries** — they serve business logic purposes:

#### ModelActionRegistry
- **Purpose**: Discover CLI actions from node contracts
- **Pattern**: Loads `contract.yaml` → validates with `ModelGenericYaml` (Pydantic) → registers `ModelCliAction`
- **Usage**: CLI command routing and action discovery

#### ModelEventTypeRegistry
- **Purpose**: Discover event types from node contracts
- **Pattern**: Loads `contract.yaml` → validates with `ModelGenericYaml` (Pydantic) → registers `ModelEventType`
- **Usage**: Event type validation and namespace management

#### ModelCliCommandRegistry
- **Purpose**: CLI command routing and discovery
- **Pattern**: IS a Pydantic BaseModel, stores `ModelCliCommandDefinition` instances
- **Usage**: CLI command parsing and execution routing

**Key Distinction**: These registries discover **business logic** (actions, events) from contracts, not **service dependencies**.

**Files**:
- `src/omnibase_core/models/core/model_action_registry.py`
- `src/omnibase_core/models/core/model_event_type_registry.py`
- `src/omnibase_core/models/core/model_cli_command_registry.py`

### 3. MixinServiceRegistry (Runtime Discovery)

**Purpose**: Event-driven tool discovery and lifecycle management

**Pattern**:
- Subscribes to event bus (`core.node.start`, `core.node.stop`)
- Maintains live catalog of available tools
- Tracks service health via `MixinServiceRegistryEntry` (Pydantic)

**Key Distinction**: This handles **runtime discovery** of tools that come online/offline dynamically, not compile-time dependency resolution.

**Files** (2026-08-25 migration note: `model_service_registry_entry.py` now lives
under `models/mixins/`, not `mixins/`):
- `src/omnibase_core/mixins/mixin_service_registry.py`
- `src/omnibase_core/models/mixins/model_service_registry_entry.py`

---

## Resolution Flow

### Dependency Injection (ServiceRegistry)

```text
User Code
    │
    ▼
container.get_service(ProtocolLoggerLike)
    │
    ▼
ServiceRegistry.resolve_service(ProtocolLoggerLike)
    │
    ├─→ Check interface_map for ProtocolLoggerLike
    │
    ├─→ Get registration metadata (Pydantic validated)
    │
    ├─→ Resolve by lifecycle (singleton/transient)
    │
    └─→ Return typed instance: logger (type: ProtocolLoggerLike)
```

### Business Registry (Action Discovery)

```text
Node Contract (contract.yaml)
    │
    ▼
load_and_validate_yaml_model(file, ModelGenericYaml)  # Pydantic validation
    │
    ▼
Extract CLI interface section
    │
    ▼
ModelCliAction.from_contract_action(...)  # Pydantic model
    │
    ▼
ModelActionRegistry.register_action(action)
    │
    └─→ Stored in _actions dict for CLI routing
```

### Runtime Discovery (MixinServiceRegistry)

```text
Tool Node Starts
    │
    ▼
Event: core.node.start published to event bus
    │
    ▼
MixinServiceRegistry._handle_node_start(event)
    │
    ▼
Create MixinServiceRegistryEntry (Pydantic)
    │
    ▼
Store in self.service_registry[tool_id]
    │
    └─→ Tool available in live catalog
```

---

## Consequences

### Positive

- **Type Safety**: Generic type parameters ensure compile-time correctness
- **Testability**: Easy to mock protocol interfaces in tests
- **Observability**: Built-in health monitoring and performance tracking
- **Flexibility**: Multiple lifecycles (singleton, transient, scoped)
- **Validation**: Pydantic ensures configuration correctness
- **Consistency**: Single pattern for all dependency management
- **Future-Proof**: Protocol-based design supports Core protocol evolution

### Neutral

- **Learning Curve**: Developers must understand protocol vs concrete class distinction
- **Terminology**: "Registry" used in three contexts requires clear documentation

### Negative

- **Performance Overhead**: Protocol resolution adds ~1-2ms per resolution (acceptable for non-hot-path)
- **Fallback Complexity**: Dual resolution strategy (legacy fallback) adds maintenance burden

---

## Alternatives Considered

### Alternative 1: Concrete Class DI

Register/resolve by concrete class rather than protocol. **Rejected**: tight coupling to
implementation, hard to mock in tests, violates Dependency Inversion.

### Alternative 2: String-Based Resolution

Register/resolve by string name. **Rejected**: no type safety (`Any` return), typos cause
runtime errors, no IDE autocomplete, difficult to refactor.

### Alternative 3: Decorator-Based DI

`@injectable(ProtocolLoggerLike)` class decorators. **Rejected**: requires complex decorator
machinery, hard to debug when injection fails, adds "magic" behavior.

---

## References

### Related Documentation

- [ONEX Four-Node Architecture](https://github.com/OmniNode-ai/knowledge-base) (omnibase_core `docs/architecture/ONEX_FOUR_NODE_ARCHITECTURE.md`)
- Protocol Architecture, Dependency Injection docs (omnibase_core `docs/architecture/`)

### Code References

- `src/omnibase_core/container/container_service_registry.py` — ServiceRegistry implementation
- `src/omnibase_core/models/container/model_onex_container.py` — ModelONEXContainer implementation
- `omnibase_core.protocols.ProtocolServiceRegistry`, `LiteralServiceLifecycle`, `LiteralInjectionScope`

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.2 | 2026-08-25 | Migrated to knowledge base; corrected two renamed file paths (`container_service_registry.py`, `models/mixins/model_service_registry_entry.py`) verified against omnibase_core@dev |
| 1.1 | 2025-12-18 | Updated for v0.3.6 dependency inversion — protocols now Core-native |
| 1.0 | 2025-10-30 | Initial decision following comprehensive registry audit |
