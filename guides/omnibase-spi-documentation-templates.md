---
type: guide
status: current
date: "2026-09-01"
title: "omnibase_spi Documentation Templates"
topics:
  - omnibase_spi
  - documentation
  - templates
refs: []
---

<!-- Migrated from omnibase_spi:docs/templates/README.md on 2026-09-01 -->

# Documentation Templates

## Overview

Templates and examples for creating comprehensive protocol documentation.

## Protocol Documentation Template

### Basic Protocol Template

```markdown
# ProtocolName

## Overview

Brief description of the protocol's purpose and primary use cases.

## Protocol Definition

```python
@runtime_checkable
class ProtocolName(Protocol):
    """
    Brief description of the protocol's purpose.

    Detailed description covering:
    - Primary use cases and scenarios
    - Key features and capabilities
    - Integration patterns and usage
    - Implementation requirements
    """

    async def method_name(
        self,
        param: str,
        optional_param: Optional[int] = None
    ) -> str:
        """
        Method description with clear purpose.

        Args:
            param: Description of required parameter
            optional_param: Description of optional parameter

        Returns:
            Description of return value

        Raises:
            ValueError: When parameter validation fails
        """
        ...
```

## Usage Examples

### Basic Usage

```python
# Initialize protocol
protocol: ProtocolName = get_protocol_implementation()

# Use protocol
result = await protocol.method_name("example", optional_param=42)
print(f"Result: {result}")
```

### Advanced Usage

```python
# Advanced usage example
# ... more complex example ...
```

## Integration Patterns

### With Other Protocols

```python
# Integration example
# ... integration example ...
```

## Best Practices

1. **Usage Guidelines**
   - Best practice 1
   - Best practice 2
   - Best practice 3

2. **Performance Considerations**
   - Performance tip 1
   - Performance tip 2

3. **Error Handling**
   - Error handling tip 1
   - Error handling tip 2

## API Reference

- **`Core Protocols` (in the omnibase_spi repository)** - System fundamentals
- **`Container Protocols` (in the omnibase_spi repository)** - Dependency injection

---

*For detailed protocol documentation, see the `API Reference` (in the omnibase_spi repository).*
```

## Service Integration Template

### Service Integration Template

```markdown
# ServiceName Integration

## Overview

Integration guide for ServiceName with ONEX SPI protocols.

## Prerequisites

- Prerequisite 1
- Prerequisite 2
- Prerequisite 3

## Basic Integration

### Service Registration

```python
from omnibase_spi.protocols.container import ProtocolServiceRegistry

# Initialize service registry
registry: ProtocolServiceRegistry = get_service_registry()

# Register service
await registry.register_service(
    interface=ProtocolServiceName,
    implementation=ServiceNameImplementation,
    lifecycle="singleton",
    scope="global"
)
```

### Service Usage

```python
# Resolve and use service
service = await registry.resolve_service(ProtocolServiceName)
result = await service.perform_operation(data)
```

## Advanced Integration

### Configuration

```python
# Advanced configuration example
# ... configuration example ...
```

### Error Handling

```python
# Error handling example
# ... error handling example ...
```

## Best Practices

1. **Integration Guidelines**
   - Guideline 1
   - Guideline 2

2. **Performance Optimization**
   - Optimization tip 1
   - Optimization tip 2

## API Reference

- **`Core Protocols` (in the omnibase_spi repository)** - System fundamentals
- **`Container Protocols` (in the omnibase_spi repository)** - Dependency injection

---

*For detailed protocol documentation, see the `API Reference` (in the omnibase_spi repository).*
```

## Workflow Template

### Workflow Documentation Template

```markdown
# WorkflowName Workflow

## Overview

Description of the workflow and its purpose.

## Workflow Definition

### States

- **State 1**: Description of state 1
- **State 2**: Description of state 2
- **State 3**: Description of state 3

### Transitions

- **State 1 → State 2**: Trigger and conditions
- **State 2 → State 3**: Trigger and conditions
- **State 3 → State 1**: Trigger and conditions

## Implementation

### Workflow Orchestrator

```python
from omnibase_spi.protocols.workflow_orchestration import ProtocolWorkflowOrchestrator

# Initialize orchestrator
orchestrator: ProtocolWorkflowOrchestrator = get_workflow_orchestrator()

# Start workflow
workflow = await orchestrator.start_workflow(
    workflow_type="workflow-name",
    instance_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
    initial_data={"key": "value"}
)
```

### Event Handling

```python
# Event handling example
# ... event handling example ...
```

## Usage Examples

### Basic Workflow

```python
# Basic workflow example
# ... basic example ...
```

### Advanced Workflow

```python
# Advanced workflow example
# ... advanced example ...
```

## Best Practices

1. **Workflow Design**
   - Design principle 1
   - Design principle 2

2. **Event Handling**
   - Event handling tip 1
   - Event handling tip 2

## API Reference

- **`Workflow Orchestration` (in the omnibase_spi repository)** - Workflow orchestration protocols
- **`Event Bus` (in the omnibase_spi repository)** - Event bus protocols

---

*For detailed protocol documentation, see the `API Reference` (in the omnibase_spi repository).*
```

## Best Practices

### Documentation Standards

1. **Structure**
   - Use clear, descriptive headings
   - Include comprehensive examples
   - Provide integration patterns

2. **Content**
   - Write clear, concise descriptions
   - Include practical examples
   - Document best practices

3. **Formatting**
   - Use consistent formatting
   - Include code examples
   - Provide cross-references

### Template Usage

1. **Protocol Documentation**
   - Use protocol template for protocol documentation
   - Include comprehensive examples
   - Document integration patterns

2. **Service Integration**
   - Use service integration template for service guides
   - Include configuration examples
   - Document error handling

3. **Workflow Documentation**
   - Use workflow template for workflow guides
   - Include state diagrams
   - Document event handling

## API Reference

- **`Core Protocols` (in the omnibase_spi repository)** - System fundamentals
- **`Container Protocols` (in the omnibase_spi repository)** - Dependency injection
- **`Workflow Orchestration` (in the omnibase_spi repository)** - Event-driven FSM
- **`MCP Integration` (in the omnibase_spi repository)** - Multi-subsystem coordination

---

*For detailed protocol documentation, see the `API Reference` (in the omnibase_spi repository).*
