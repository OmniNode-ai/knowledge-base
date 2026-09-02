---
type: guide
status: current
date: "2026-09-01"
title: "omnibase_spi Protocol Selection Guide"
topics:
  - omnibase_spi
  - protocols
  - design-patterns
refs: []
---

<!-- Migrated from omnibase_spi:docs/patterns/PROTOCOL-SELECTION-GUIDE.md on 2026-09-01 -->

# Protocol Selection Guide

## Decision Framework

A comprehensive guide for choosing the right protocols for your use case.

> Rewritten against the live package — every protocol name below
> imports at the domain shown; the previous revision named several protocols
> that do not exist anywhere in `omnibase_spi` (`ProtocolErrorHandler` is
> real, but `ProtocolMemoryBase`, `ProtocolMemoryOperations`,
> `ProtocolMemorySecurity`, `ProtocolAgentManager`, `ProtocolKafkaClient`,
> `ProtocolValidation`, `ProtocolInputValidationTool`, and
> `ProtocolPrecommitChecker` were fabricated).

## Core System Protocols

### When to Use Core Protocols

**Use Core Protocols when you need:**
- System-level observability and monitoring
- Error handling and recovery
- Performance metrics and monitoring
- Service discovery and registration

**Key Protocols** (`omnibase_spi.protocols.core`):
- `ProtocolLogger` - Structured logging across services
- `ProtocolHealthMonitor` - Health monitoring and status tracking
- `ProtocolErrorHandler` - Centralized error handling
- `ProtocolPerformanceMetricsCollector` - Performance metrics collection (returns
  `ProtocolPerformanceMetrics`, which is a `types`-domain data protocol, not `core`)

## Container Management Protocols

### When to Use Container Protocols

**Use Container Protocols when you need:**
- Dependency injection and service lifecycle management
- Circular dependency detection
- Service health monitoring
- Factory patterns and injection contexts

**Key Protocols** (`omnibase_spi.protocols.container`):
- `ProtocolServiceRegistry` - Service registration and resolution
- `ProtocolServiceFactory` - Service instance creation
- `ProtocolDependencyGraph` - Dependency analysis
- `ProtocolInjectionContext` - Injection context management

## Workflow Orchestration Protocols

### When to Use Workflow Protocols

**Use Workflow Protocols when you need:**
- Event-driven workflow orchestration
- Event sourcing with sequence numbers
- Workflow state management and projections
- Distributed task scheduling

**Key Protocols** (`omnibase_spi.protocols.workflow_orchestration`):
- `ProtocolWorkflowOrchestrator` - Workflow lifecycle management
- `ProtocolWorkflowEventBus` - Event-driven coordination
- `ProtocolEventStore` / `ProtocolSnapshotStore` - Event-sourced persistence
  (there is no single `ProtocolWorkflowPersistence` — see
  `WORKFLOW-ORCHESTRATION.md` (in the omnibase_spi repository))
- `ProtocolWorkQueue` - Task scheduling

## MCP Integration Protocols

### When to Use MCP Protocols

**Use MCP Protocols when you need:**
- Multi-subsystem tool coordination
- Dynamic tool discovery and routing
- Load balancing across implementations
- Tool execution tracking and monitoring

**Key Protocols** (`omnibase_spi.protocols.mcp`):
- `ProtocolMCPRegistry` - Tool registration and discovery
- `ProtocolMCPToolProxy` - Tool execution coordination
- `ProtocolMCPMonitor` - Health monitoring
- `ProtocolMCPSubsystemClient` - Subsystem communication

## Event Bus Protocols

### When to Use Event Bus Protocols

**Use Event Bus Protocols when you need:**
- Distributed messaging infrastructure
- Event publishing and subscription
- Message serialization and routing
- Dead letter queue handling

**Key Protocols** (`omnibase_spi.protocols.event_bus`):
- `ProtocolEventBusProvider` - Event bus instance creation and lifecycle
  (there is no bare `ProtocolEventBus` in this package — see
  `EVENT-BUS.md` (in the omnibase_spi repository))
- `ProtocolKafkaAdapter` - Kafka integration
- `ProtocolEventPublisher` - Event publishing
- `ProtocolDLQHandler` - Dead letter queue handling

## Memory Management Protocols

### When to Use Memory Protocols

**Use Memory Protocols when you need:**
- Key-value storage operations
- Agent coordination and management
- Memory security, PII detection, and encryption
- Streaming and cursor-paginated content

**Key Protocols** (`omnibase_spi.protocols.memory`):
- `ProtocolKeyValueStore` - Base key-value storage shape (there is no
  `ProtocolMemoryBase`)
- `ProtocolMemoryCache` - Caching with TTL, invalidation, and warming
- `ProtocolMemorySecurityNode` - PII detection, access control, encryption
- `ProtocolAgentCoordinator` - Agent registration and coordination (there is
  no `ProtocolAgentManager` or `ProtocolAgentPool`)

See the [Memory Protocols Guide](omnibase-spi-memory-protocols-guide.md) for
worked examples of all four.

## Networking Protocols

### When to Use Networking Protocols

**Use Networking Protocols when you need:**
- HTTP client operations, including streaming and OAuth2/JWT
- Circuit breaker patterns
- Communication bridges between protocols

**Key Protocols** (`omnibase_spi.protocols.networking`):
- `ProtocolHttpClient` - HTTP operations
- `ProtocolHttpExtendedClient` - Streaming, WebSocket, and advanced auth
- `ProtocolCircuitBreaker` - Circuit breaker patterns
- `ProtocolCommunicationBridge` - Protocol bridging

> Kafka is **not** in this domain — there is no `ProtocolKafkaClient`.
> Kafka/event-streaming protocols (`ProtocolKafkaAdapter`,
> `ProtocolRedpandaAdapter`, `ProtocolSchemaRegistry`) live in
> `omnibase_spi.protocols.event_bus`.

## File Handling Protocols

### When to Use File Handling Protocols

**Use File Handling Protocols when you need:**
- File reading and writing operations
- File type detection and processing
- Directory traversal and discovery
- File I/O optimization

**Key Protocols** (`omnibase_spi.protocols.file_handling`):
- `ProtocolFileReader` - File reading operations
- `ProtocolFileWriter` - File writing operations
- `ProtocolFileTypeHandlerRegistry` - Type detection and handler dispatch
- `ProtocolDirectoryTraverser` - Directory traversal

## Validation Protocols

### When to Use Validation Protocols

**Use Validation Protocols when you need:**
- Generic protocol-conformance checking
- ONEX naming/architecture compliance checking
- Code quality and complexity assessment
- Import/dependency validation

**Key Protocols** (`omnibase_spi.protocols.validation`, unless noted):
- `ProtocolValidator` - Generic "does X implement protocol Y" check (there
  is no `ProtocolValidation`)
- `ProtocolComplianceValidator` - ONEX naming and architecture compliance
- `ProtocolImportValidator` - Import/dependency validation
- `ProtocolQualityValidator` - Code quality and complexity assessment
- `ProtocolInputValidator` (in `omnibase_spi.protocols.schema`, not
  `validation`) - Input sanitization and injection-pattern checking

> There is no `ProtocolInputValidationTool` or `ProtocolPrecommitChecker`
> anywhere in the package — see
> `VALIDATION.md` (in the omnibase_spi repository) for the full, real
> validation surface.

## Selection Decision Tree

### 1. What is your primary use case?

**System Operations** → Core Protocols
**Service Management** → Container Protocols
**Workflow Processing** → Workflow Orchestration Protocols
**Tool Coordination** → MCP Integration Protocols
**Event Processing** → Event Bus Protocols
**Data Storage** → Memory Management Protocols
**Communication** → Networking Protocols
**File Operations** → File Handling Protocols
**Data Validation** → Validation Protocols

### 2. Do you need multiple capabilities?

**Yes** → Use Protocol Composition Patterns
**No** → Use individual protocols

### 3. What is your performance requirement?

**High Performance** → Use async protocols with optimization
**Standard Performance** → Use standard protocol implementations
**Development/Testing** → Use in-memory or lightweight protocols

### 4. What is your deployment environment?

**Distributed** → Use protocols with clustering support
**Single Node** → Use protocols with local optimization
**Cloud** → Use protocols with cloud integration

## Best Practices

### Protocol Selection

1. **Start Simple** - Begin with core protocols and add complexity as needed
2. **Compose Gradually** - Build complex behaviors from simpler protocols
3. **Consider Performance** - Choose protocols that match your performance requirements
4. **Plan for Scale** - Select protocols that can scale with your needs

### Integration Patterns

1. **Dependency Injection** - Use container protocols for service management
2. **Event-Driven** - Use event bus protocols for loose coupling
3. **Health Monitoring** - Include health monitoring in all critical services
4. **Error Handling** - Implement comprehensive error handling

## API Reference

- **`Core Protocols` (in the omnibase_spi repository)** - System fundamentals
- **`Container Protocols` (in the omnibase_spi repository)** - Dependency injection
- **`Workflow Orchestration` (in the omnibase_spi repository)** - Event-driven FSM
- **`MCP Integration` (in the omnibase_spi repository)** - Multi-subsystem coordination
- **`Event Bus` (in the omnibase_spi repository)** - Distributed messaging
- **`Memory Management` (in the omnibase_spi repository)** - Memory operations
- **`Networking` (in the omnibase_spi repository)** - Communication protocols
- **`File Handling` (in the omnibase_spi repository)** - File operations
- **`Validation` (in the omnibase_spi repository)** - Input validation

---

*For detailed protocol documentation, see the `API Reference` (in the omnibase_spi repository).*
