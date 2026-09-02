---
type: guide
status: current
date: "2026-09-01"
title: "omnibase_spi Quick Start"
topics:
  - omnibase_spi
  - getting-started
  - protocols
refs: []
---

<!-- Migrated from omnibase_spi:docs/QUICK-START.md on 2026-09-01 -->

# Quick Start Guide

## Overview

Get up and running with ONEX SPI protocols in minutes. This guide provides immediate hands-on experience with the core protocols.

## Installation

```bash
# Install the package (preferred)
uv add omnibase-spi

# Or with pip
pip install omnibase-spi
```

## Important: SPI vs Implementation

**`omnibase_spi` defines protocols (interfaces), not implementations.** The examples below demonstrate how to work with these protocol interfaces. Helper functions like `get_service_registry()`, `get_workflow_orchestrator()`, and `get_mcp_registry()` are **implementation-specific factories** provided by `omnibase_infra` or your own application code.

For concrete implementations, see:

- **`omnibase_infra` (in the omnibase_spi repository)** - Reference implementations
- **`omnibase_core` (in the omnibase_spi repository)** - Pydantic models and core types

## Basic Usage

### Service Registration and Resolution

```python
from omnibase_spi.protocols.container import ProtocolServiceRegistry
from omnibase_spi.protocols.core import ProtocolLogger

# Factory function - implementation provided by omnibase_infra
registry: ProtocolServiceRegistry = get_service_registry()
await registry.register_service(
    interface=ProtocolLogger,
    implementation=ConsoleLogger,  # Your concrete implementation
    lifecycle="singleton",
    scope="global"
)

# Resolve the service
logger = await registry.resolve_service(ProtocolLogger)
await logger.log("INFO", "Hello, ONEX SPI!")
```

### Workflow Orchestration

```python
from omnibase_spi.protocols.workflow_orchestration import ProtocolWorkflowOrchestrator

# Factory function - implementation provided by omnibase_infra
orchestrator: ProtocolWorkflowOrchestrator = get_workflow_orchestrator()
workflow = await orchestrator.start_workflow(
    workflow_type="order-processing",
    instance_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
    initial_data={"order_id": "ORD-12345"}
)

print(f"Workflow state: {workflow.current_state}")
```

### MCP Tool Execution

```python
from omnibase_spi.protocols.mcp import ProtocolMCPRegistry

# Factory function - implementation provided by omnibase_infra
mcp_registry: ProtocolMCPRegistry = get_mcp_registry()
result = await mcp_registry.execute_tool(
    tool_name="text_generation",
    parameters={"prompt": "Hello world"},
    correlation_id=UUID("req-abc123")
)

print(f"Tool result: {result}")
```

## Next Steps

1. **Explore the API Reference** - `Complete protocol documentation` (in the omnibase_spi repository)
2. **Container Protocols** - `Dependency injection patterns` (in the omnibase_spi repository)
3. **Workflow Orchestration** - `Event-driven FSM` (in the omnibase_spi repository)
4. **MCP Integration** - `Multi-subsystem coordination` (in the omnibase_spi repository)

## See Also

- **[Glossary](../reference/omnibase-spi-glossary.md)** - Definitions of SPI-specific terms (Protocol, Handler, Node, etc.)
- **[Developer Guide](omnibase-spi-developer-guide.md)** - Complete development workflow
- **[Architecture Overview](../architecture/omnibase-spi-overview.md)** - Design principles and patterns
- **`Contributing Guide` (in the omnibase_spi repository)** - How to contribute to the project
- **`Main README` (in the omnibase_spi repository)** - Repository overview

### Common Protocol References

- **`Node Protocols` (in the omnibase_spi repository)** - ONEX 4-node architecture (Compute, Effect, Reducer, Orchestrator)
- **`Handler Protocols` (in the omnibase_spi repository)** - I/O handler interfaces
- **`Contract Compilers` (in the omnibase_spi repository)** - Effect, Workflow, FSM compilers
- **`Registry Protocols` (in the omnibase_spi repository)** - Handler registry for DI
- **`Exception Hierarchy` (in the omnibase_spi repository)** - SPIError and subclasses

For term definitions, see the [Glossary](../reference/omnibase-spi-glossary.md).

---

*For comprehensive documentation, see the `API Reference` (in the omnibase_spi repository).*
