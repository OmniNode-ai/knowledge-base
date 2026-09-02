---
type: reference
status: current
date: "2026-09-01"
title: "omnibase_spi Glossary"
topics:
  - omnibase_spi
  - glossary
  - terminology
refs: []
---

<!-- Migrated from omnibase_spi:docs/GLOSSARY.md on 2026-09-01 -->

# ONEX SPI Glossary

This glossary provides definitions for key terms used throughout the ONEX Service Provider Interface (SPI) documentation. Terms are organized by category for easier navigation.

---

## Table of Contents

- [Architecture Terms](#architecture-terms)
- [Protocol Terms](#protocol-terms)
- [SPI-Specific Terms](#spi-specific-terms)
- [Integration Terms](#integration-terms)
- [Node Terms](#node-terms)
- [Handler Terms](#handler-terms)
- [Container Terms](#container-terms)
- [Event Bus Terms](#event-bus-terms)

---

## Architecture Terms

### ONEX (OmniNode eXecution)

The distributed orchestration platform that provides event-driven workflow execution, protocol-first design, and enterprise-grade service coordination. ONEX follows a layered architecture with clear separation between contracts (SPI), models (Core), and implementations (Infra).

See: [Architecture Overview](../architecture/omnibase-spi-overview.md)

### SPI (Service Provider Interface)

The Service Provider Interface package (`omnibase_spi`) that defines protocol-based contracts for the ONEX platform. SPI contains only Python `Protocol` definitions and exceptions with zero implementation dependencies. Implementations live in `omnibase_infra`.

See: `README.md` (in the omnibase_spi repository)

### 4-Node Architecture

The fundamental ONEX pattern where all processing is categorized into four distinct node types: **Compute**, **Effect**, **Reducer**, and **Orchestrator**. Each node type has specific responsibilities and constraints regarding side effects and determinism.

| Node Type | Purpose | Side Effects | Deterministic |
|-----------|---------|--------------|---------------|
| Compute | Pure transformations | No | Yes |
| Effect | I/O operations | Yes | No |
| Reducer | State aggregation | Controlled | Varies |
| Orchestrator | Workflow coordination | Delegates | N/A |

See: `NODES.md - Architecture` (in the omnibase_spi repository)

### Protocol-First Design

The design philosophy where all services are defined through Python `Protocol` interfaces before any implementation is created. This ensures loose coupling, testability, and clear contract boundaries.

See: [Architecture Overview](../architecture/omnibase-spi-overview.md)

---

## Protocol Terms

### Protocol (Python typing.Protocol)

A Python `typing.Protocol` that defines structural subtyping (duck typing with type safety). Protocols specify method signatures and properties that implementations must provide without requiring explicit inheritance.

```python
from typing import Protocol

class ProtocolExample(Protocol):
    def method(self) -> str:
        ...  # Ellipsis indicates abstract method
```

See: `Python typing.Protocol documentation` (in the omnibase_spi repository)

### @runtime_checkable

A decorator from `typing` that enables `isinstance()` checks against a Protocol at runtime. All SPI protocols must be decorated with `@runtime_checkable` to support runtime type validation.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ProtocolHandler(Protocol):
    @property
    def handler_type(self) -> str: ...
```

See: `HANDLERS.md - Protocol Definition` (in the omnibase_spi repository)

### Duck Typing

A programming concept where an object's suitability is determined by the presence of methods and properties rather than its explicit type. Python's Protocol system provides type-safe duck typing through structural subtyping.

### Structural Typing

A type system where type compatibility is determined by the structure (methods and properties) of types rather than explicit declarations or inheritance. Python Protocols implement structural typing.

### Protocol Compliance

The state where an implementation correctly satisfies all requirements of a Protocol including method signatures, property types, return types, and semantic contracts. Use `isinstance()` with `@runtime_checkable` protocols to verify compliance at runtime.

```python
# Verify an object implements ProtocolHandler
if isinstance(handler, ProtocolHandler):
    result = await handler.execute(request, config)
```

---

## SPI-Specific Terms

### Namespace Isolation

The architectural rule that SPI must never import from `omnibase_infra` (implementation package). SPI may import from `omnibase_core` for type definitions. This ensures clean dependency boundaries.

```text
Allowed:     SPI → Core
Forbidden:   SPI → Infra
Forbidden:   Core → SPI
```

See: `CLAUDE.md - Architecture` (in the omnibase_spi repository)

### Contract

A declarative specification (typically YAML) that defines behaviors, state machines, or workflows. Contracts are compiled at build-time by Contract Compilers into runtime models that nodes use for execution.

**Contract Types**:
- **Effect Contract**: Defines side-effecting operations (API calls, DB queries)
- **Workflow Contract**: Defines multi-step orchestration flows
- **FSM Contract**: Defines finite state machine configurations

See: `CONTRACTS.md` (in the omnibase_spi repository)

### Contract Compiler

A build-time tool that compiles YAML contract files into runtime contract models. Compilers validate contract structure and semantic correctness before generating optimized runtime representations.

See: `CONTRACTS.md - Architecture` (in the omnibase_spi repository)

### Handler Lifecycle

The state progression of a handler from creation through operation to cleanup: **Created** → **Initialized** → **Closed**. Handlers must be initialized before execution and properly shut down to release resources.

```python
handler = HttpRestHandler()
await handler.initialize(config)  # Created → Initialized
try:
    await handler.execute(request, config)  # Operations
finally:
    await handler.shutdown()  # Initialized → Closed
```

See: `HANDLERS.md - Lifecycle Diagram` (in the omnibase_spi repository)

### Handler Registry

A service locator pattern (`ProtocolHandlerRegistry`) that manages the mapping between protocol type identifiers (e.g., `"http"`, `"kafka"`) and their handler implementations. Enables dependency injection of handlers into effect nodes.

See: `REGISTRY.md` (in the omnibase_spi repository)

---

## Integration Terms

### omnibase_core

The core models package that contains Pydantic models, enums, and runtime type definitions shared across ONEX packages. SPI protocols reference Core models for type hints.

**Contains**: `ModelComputeInput`, `ModelEffectOutput`, `ModelConnectionConfig`, etc.

See: `CLAUDE.md - Architecture` (in the omnibase_spi repository)

### omnibase_infra

The infrastructure package that contains concrete implementations of SPI protocols. Infra depends on both SPI (contracts) and Core (models).

**Contains**: `HttpRestHandler`, `KafkaHandler`, `PostgresHandler`, etc.

### MCP (Model Context Protocol)

The Model Context Protocol integration for multi-subsystem tool coordination. MCP protocols provide tool registry, load balancing, health monitoring, and execution tracking across distributed systems.

See: `MCP.md` (in the omnibase_spi repository)

### FSM (Finite State Machine)

A computational model used for workflow state management in ONEX. FSM contracts define states, transitions, guards, and actions for managing lifecycle workflows (e.g., order processing, document approval).

**FSM States Example**: `pending` → `running` → `completed`

See: `CONTRACTS.md - ProtocolFSMContractCompiler` (in the omnibase_spi repository)

### Event Bus

The distributed messaging infrastructure that provides publish/subscribe patterns, event serialization, and dead letter queue handling. Supports multiple backend adapters including Kafka, Redpanda, and in-memory implementations.

See: `EVENT-BUS.md` (in the omnibase_spi repository)

### Event Sourcing

An architectural pattern where state changes are stored as a sequence of events with sequence numbers and causation tracking. ONEX workflows use event sourcing for audit trails, replay capabilities, and real-time projections.

See: `WORKFLOW-ORCHESTRATION.md` (in the omnibase_spi repository)

---

## Node Terms

### Compute Node

A node type (`ProtocolComputeNode`) that performs pure, deterministic transformations with no side effects. The same input always produces the same output. Suitable for data transformation, validation, and algorithm execution.

**Key Properties**:
- No I/O operations
- Deterministic output
- Safe to retry without side effects
- Uses `ModelComputeInput` / `ModelComputeOutput`

See: `NODES.md - ProtocolComputeNode` (in the omnibase_spi repository)

### Effect Node

A node type (`ProtocolEffectNode`) that performs side-effecting I/O operations such as API calls, database queries, and file operations. Effect nodes have lifecycle management (initialize/shutdown) and may be non-deterministic.

**Key Properties**:
- Has side effects (I/O)
- Requires lifecycle management
- May not be deterministic
- Often delegates to `ProtocolHandler`
- Uses `ModelEffectInput` / `ModelEffectOutput`

See: `NODES.md - ProtocolEffectNode` (in the omnibase_spi repository)

### Reducer Node

A node type (`ProtocolReducerNode`) that aggregates state from a stream of inputs. Reducers maintain accumulated state across invocations and produce aggregated outputs. Used for metrics collection, event aggregation, and state accumulation.

**Key Properties**:
- Maintains accumulated state
- Processes streams of inputs
- Produces reduced/aggregated outputs
- Uses `ModelReductionInput` / `ModelReductionOutput`

See: `NODES.md - ProtocolReducerNode` (in the omnibase_spi repository)

### Orchestrator Node

A node type (`ProtocolOrchestratorNode`) that coordinates the execution of other nodes or workflows. Orchestrators manage complex multi-step processes, handle error recovery, and implement compensation logic.

**Key Properties**:
- Coordinates multiple nodes
- Manages workflow state
- Handles partial failures
- May implement saga patterns
- Uses `ModelOrchestrationInput` / `ModelOrchestrationOutput`

See: `NODES.md - ProtocolOrchestratorNode` (in the omnibase_spi repository)

---

## Handler Terms

### Handler

A protocol-specific I/O adapter (`ProtocolHandler`) that encapsulates communication with external systems. Handlers provide a consistent interface for effect nodes to perform operations like HTTP requests, database queries, or message publishing.

**Handler Types**: `http`, `kafka`, `postgresql`, `neo4j`, `redis`, `grpc`, `websocket`, `file`, `memory`

See: `HANDLERS.md` (in the omnibase_spi repository)

### Effect (Side Effect)

Any operation that interacts with the external world or modifies state outside the current function scope. Examples include file I/O, network requests, database operations, and logging. In ONEX, side effects are isolated to Effect Nodes and Handlers.

### Handler Type

A string identifier that categorizes a handler's protocol (e.g., `"http"`, `"kafka"`, `"postgresql"`). Handler types are used for registry lookups, metrics collection, and routing.

---

## Container Terms

### Dependency Injection

A design pattern where components receive their dependencies from an external source rather than creating them internally. ONEX uses `ProtocolServiceRegistry` for enterprise-grade dependency injection with lifecycle management.

See: `CONTAINER.md` (in the omnibase_spi repository)

### Service Lifecycle

The lifetime pattern for service instances managed by the container. ONEX supports multiple lifecycle patterns:

| Lifecycle | Description |
|-----------|-------------|
| `singleton` | Single instance shared across all requests |
| `transient` | New instance created for each resolution |
| `scoped` | Instance per scope (request, session, thread) |
| `pooled` | Fixed pool of instances for performance |
| `lazy` | Created on first use |
| `eager` | Created at startup |

See: `CONTAINER.md - Lifecycle Management` (in the omnibase_spi repository)

### Injection Scope

The boundary within which scoped instances are shared. ONEX supports: `request`, `session`, `thread`, `process`, `global`, and `custom` scopes.

### Circular Dependency

A situation where two or more services depend on each other, creating a cycle that prevents resolution. ONEX's `ProtocolServiceRegistry` automatically detects and prevents circular dependencies.

See: `CONTAINER.md - Circular Dependency Detection` (in the omnibase_spi repository)

---

## Event Bus Terms

### Dead Letter Queue (DLQ)

A holding queue for messages that cannot be successfully processed after exhausting retry attempts. The `ProtocolDLQHandler` provides monitoring, metrics, and reprocessing capabilities for DLQ messages.

See: `EVENT-BUS.md - Dead Letter Queue Handler` (in the omnibase_spi repository)

### Event Envelope

A generic wrapper (`ProtocolEventEnvelope`) for event payloads that provides metadata and breaks circular dependencies in event processing systems.

See: `EVENT-BUS.md - Event Envelope Protocol` (in the omnibase_spi repository)

### Correlation ID

A unique identifier (UUID) that tracks a request or workflow across multiple services and events. Used for distributed tracing and debugging.

### Causation ID

A unique identifier that links an event to the event that caused it. Combined with correlation IDs, enables full event causation tracking and replay.

### Schema Registry

A service (`ProtocolSchemaRegistry`) that manages schema versions for event validation. Supports JSON Schema, Avro, and Protobuf formats with compatibility checking.

See: `EVENT-BUS.md - Schema Registry Protocol` (in the omnibase_spi repository)

---

## Quick Reference

| Term | Package | Purpose |
|------|---------|---------|
| SPI | `omnibase_spi` | Protocol contracts |
| Core | `omnibase_core` | Pydantic models |
| Infra | `omnibase_infra` | Implementations |
| Protocol | `typing.Protocol` | Interface definition |
| Handler | SPI protocols | I/O adapters |
| Node | SPI protocols | Execution units |
| Contract | YAML files | Declarative specs |
| Registry | SPI protocols | Service location |
| Event Bus | SPI protocols | Async messaging |

---

## See Also

- **`Main README` (in the omnibase_spi repository)** - Repository overview and quick start
- **`Documentation Hub` (in the omnibase_spi repository)** - Complete documentation overview
- **[Architecture Overview](../architecture/omnibase-spi-overview.md)** - Design principles and patterns
- **`API Reference` (in the omnibase_spi repository)** - Complete protocol documentation
- **[Quick Start Guide](../guides/omnibase-spi-quick-start.md)** - Get up and running quickly
- **[Developer Guide](../guides/omnibase-spi-developer-guide.md)** - Complete development workflow
- **`Contributing Guide` (in the omnibase_spi repository)** - How to contribute to the project
- **[Dependency Direction](../architecture/omnibase-spi-dependency-direction.md)** - Import graph and boundary rules

### Common Protocol References

- **`Node Protocols` (in the omnibase_spi repository)** - ProtocolNode, ProtocolComputeNode, etc.
- **`Handler Protocols` (in the omnibase_spi repository)** - ProtocolHandler interface
- **`Contract Compilers` (in the omnibase_spi repository)** - Effect, Workflow, FSM compilers
- **`Registry Protocols` (in the omnibase_spi repository)** - ProtocolHandlerRegistry
- **`Exception Hierarchy` (in the omnibase_spi repository)** - SPIError and subclasses

---

This glossary is maintained as part of the omnibase_spi documentation. Last updated: 2025-12-07.
