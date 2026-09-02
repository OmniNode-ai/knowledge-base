---
type: architecture
status: accepted
date: "2026-09-02"
title: "Container-Based Dependency Injection"
topics: [omnibase-infra, container, dependency, injection]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/container_dependency_injection.md on 2026-09-02. -->

# Container-Based Dependency Injection

## Overview

ONEX infrastructure uses container-based dependency injection through `ModelONEXContainer` for type-safe service resolution. This pattern eliminates global singletons and enables testability.

## Core Concepts

### Service Container

The service container manages service lifecycles and resolves dependencies:

```python
from omnibase_core.container import ModelONEXContainer

# Container holds all registered services
container = ModelONEXContainer()
```

### Service Registry

Services are registered and resolved by type interface:

```python
from omnibase_infra.runtime.policy_registry import PolicyRegistry

# Register service
container.service_registry.register_service(
    interface=PolicyRegistry,
    implementation=PolicyRegistry(),
    scope="global",
)

# Resolve service
policy_registry = container.service_registry.resolve_service(PolicyRegistry)
```

## Bootstrap Pattern

### Infrastructure Services Wiring

All infrastructure services use a centralized wiring function:

```python
from omnibase_core.container import ModelONEXContainer
from omnibase_infra.runtime.container_wiring import wire_infrastructure_services
from omnibase_infra.runtime.policy_registry import PolicyRegistry

# Bootstrap container with all infrastructure services
container = ModelONEXContainer()
wire_infrastructure_services(container)

# Services are now available for resolution
policy_registry = container.service_registry.resolve_service(PolicyRegistry)
```

### Wiring Implementation

```python
# omnibase_infra/runtime/container_wiring.py
from omnibase_core.container import ModelONEXContainer
from omnibase_infra.runtime.policy_registry import PolicyRegistry

def wire_infrastructure_services(container: ModelONEXContainer) -> None:
    """Wire all infrastructure services into container.

    Args:
        container: ONEX service container
    """
    # Register PolicyRegistry as global singleton
    policy_registry = PolicyRegistry()
    container.service_registry.register_service(
        interface=PolicyRegistry,
        implementation=policy_registry,
        scope="global",
    )

    # Future services registered here
    # container.service_registry.register_service(...)
```

## Service Registration

### Registration Scopes

| Scope | Lifecycle | Use Cases |
|-------|-----------|-----------|
| `global` | Singleton, shared across application | Registries, configuration, connection pools |
| `request` | New instance per request | Request handlers, transient operations |
| `thread` | Thread-local instance | Thread-specific resources |

### Service Registration Keys

| Service | Interface Type | Scope | Purpose |
|---------|---------------|-------|---------|
| PolicyRegistry | `PolicyRegistry` | global | Policy class resolution |

## Constructor Injection Pattern

### Node Class Pattern

All ONEX nodes and services receive container via constructor:

```python
from omnibase_core.container import ModelONEXContainer
from omnibase_infra.runtime.policy_registry import PolicyRegistry

class NodePostgresAdapterEffect:
    """PostgreSQL adapter node with dependency injection."""

    def __init__(self, container: ModelONEXContainer):
        """Initialize node with container.

        Args:
            container: ONEX service container
        """
        self.container = container

        # Resolve dependencies on-demand
        self.policy_registry = container.service_registry.resolve_service(
            PolicyRegistry
        )

    async def execute_effect(self, request: ModelPostgresQueryRequest) -> ModelPostgresQueryResponse:
        """Execute database query using resolved services."""
        # Use injected policy registry
        policy_class = self.policy_registry.get_policy(
            transport=EnumInfraTransportType.DATABASE,
            operation="query",
        )
        # ... implementation
```

### Service Class Pattern

```python
from omnibase_core.container import ModelONEXContainer
from omnibase_infra.runtime.policy_registry import PolicyRegistry

class KafkaPublisherService:
    """Kafka publishing service with dependency injection."""

    def __init__(self, container: ModelONEXContainer):
        self.container = container
        self.policy_registry = container.service_registry.resolve_service(
            PolicyRegistry
        )

    async def publish(self, topic: str, message: bytes) -> None:
        """Publish message to Kafka topic."""
        policy_class = self.policy_registry.get_policy(
            transport=EnumInfraTransportType.KAFKA,
            operation="publish",
        )
        # Use policy for validation/transformation
        await self._do_publish(topic, message)
```

## Helper Functions

### Type-Safe Resolution Helpers

```python
from omnibase_core.container import ModelONEXContainer
from omnibase_infra.runtime.policy_registry import PolicyRegistry

def get_policy_registry_from_container(
    container: ModelONEXContainer
) -> PolicyRegistry:
    """Get PolicyRegistry from container.

    Args:
        container: ONEX service container

    Returns:
        Resolved PolicyRegistry instance
    """
    return container.service_registry.resolve_service(PolicyRegistry)
```

## Migration from Singletons

### Deprecated Patterns

**OLD** (singleton-based):
```python
# ❌ Module-level singleton - avoid
_policy_registry: PolicyRegistry | None = None

def get_policy_registry() -> PolicyRegistry:
    """Get global policy registry singleton."""
    global _policy_registry
    if _policy_registry is None:
        _policy_registry = PolicyRegistry()
    return _policy_registry

# ❌ Convenience function - avoid
def get_policy_class(
    transport: EnumInfraTransportType,
    operation: str,
) -> type[ModelBasePolicy]:
    """Get policy class from global registry."""
    return get_policy_registry().get_policy(transport, operation)
```

### Preferred Patterns

**NEW** (container-based):
```python
# ✅ Container-based resolution
from omnibase_core.container import ModelONEXContainer
from omnibase_infra.runtime.policy_registry import PolicyRegistry

def get_policy_class(
    container: ModelONEXContainer,
    transport: EnumInfraTransportType,
    operation: str,
) -> type[ModelBasePolicy]:
    """Get policy class from container.

    Args:
        container: ONEX service container
        transport: Transport type
        operation: Operation name

    Returns:
        Policy class for transport/operation
    """
    policy_registry = container.service_registry.resolve_service(PolicyRegistry)
    return policy_registry.get_policy(transport, operation)

# ✅ Class-based injection
class MyService:
    def __init__(self, container: ModelONEXContainer):
        self.policy_registry = container.service_registry.resolve_service(
            PolicyRegistry
        )
```

## Testing with Containers

### Test Container Setup

```python
import pytest
from omnibase_core.container import ModelONEXContainer
from omnibase_infra.runtime.container_wiring import wire_infrastructure_services

@pytest.fixture
def container() -> ModelONEXContainer:
    """Create test container with infrastructure services."""
    container = ModelONEXContainer()
    wire_infrastructure_services(container)
    return container

def test_node_with_container(container: ModelONEXContainer):
    """Test node using container."""
    node = NodePostgresAdapterEffect(container=container)
    # Test node behavior
    assert node.policy_registry is not None
```

### Mock Service Registration

```python
from unittest.mock import Mock
from omnibase_infra.runtime.policy_registry import PolicyRegistry

@pytest.fixture
def container_with_mock_registry() -> ModelONEXContainer:
    """Create container with mock PolicyRegistry."""
    container = ModelONEXContainer()

    # Register mock instead of real service
    mock_registry = Mock(spec=PolicyRegistry)
    container.service_registry.register_service(
        interface=PolicyRegistry,
        implementation=mock_registry,
        scope="global",
    )

    return container

def test_with_mock_registry(container_with_mock_registry: ModelONEXContainer):
    """Test using mock registry."""
    registry = container_with_mock_registry.service_registry.resolve_service(
        PolicyRegistry
    )

    # Configure mock behavior
    registry.get_policy.return_value = MockPolicyClass

    # Test code that uses registry
    node = NodePostgresAdapterEffect(container=container_with_mock_registry)
    # Assertions...
```

## Advanced Patterns

### Lazy Resolution

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omnibase_infra.runtime.policy_registry import PolicyRegistry

class NodeWithLazyResolution:
    """Node that resolves dependencies lazily."""

    def __init__(self, container: ModelONEXContainer):
        self.container = container
        self._policy_registry: PolicyRegistry | None = None

    @property
    def policy_registry(self) -> PolicyRegistry:
        """Lazy-load policy registry on first access."""
        if self._policy_registry is None:
            self._policy_registry = self.container.service_registry.resolve_service(
                PolicyRegistry
            )
        return self._policy_registry
```

### Factory Pattern

```python
from typing import Protocol

class ServiceFactory(Protocol):
    """Factory for creating service instances."""

    def create(self, container: ModelONEXContainer) -> object:
        """Create service instance."""
        ...

def register_factory(
    container: ModelONEXContainer,
    interface: type,
    factory: ServiceFactory,
) -> None:
    """Register service factory in container.

    Args:
        container: Service container
        interface: Service interface type
        factory: Factory for creating instances
    """
    container.service_registry.register_service(
        interface=interface,
        implementation=factory.create(container),
        scope="request",  # New instance per request
    )
```

## Best Practices

### DO

✅ **Pass container to constructors**: `def __init__(self, container: ModelONEXContainer)`
✅ **Resolve services lazily**: Defer resolution until needed
✅ **Use type interfaces**: Resolve by interface type, not concrete class
✅ **Wire at startup**: Call `wire_infrastructure_services()` once at bootstrap
✅ **Test with containers**: Create test containers in fixtures
✅ **Document dependencies**: Clearly specify required services

### DON'T

❌ **Use global singletons**: Replace with container resolution
❌ **Resolve in module scope**: Only resolve inside functions/methods
❌ **Hardcode dependencies**: Always inject through container
❌ **Create containers everywhere**: One container per application
❌ **Skip wiring**: Always wire services before use
❌ **Mix patterns**: Choose container-based OR singleton, not both

## Migration Checklist

When migrating from singletons to container-based injection:

- [ ] Replace `get_policy_registry()` with `container.service_registry.resolve_service(PolicyRegistry)`
- [ ] Add `container: ModelONEXContainer` parameter to constructors
- [ ] Remove global/module-level service instances
- [ ] Update tests to use container fixtures
- [ ] Call `wire_infrastructure_services(container)` at startup
- [ ] Remove `get_policy_class()` convenience function
- [ ] Update all service instantiation to use container

## Related Patterns

- Error Handling Patterns (internal knowledge base) - Using services in error handling
- Error Recovery Patterns (internal knowledge base) - Service-based retry logic
- Correlation ID Tracking (`../architecture/omnibase-infra-correlation-id-tracking.md`) - Passing context through services
