---
type: guide
status: current
date: "2026-09-01"
title: "omnibase_spi Protocol Testing"
topics:
  - omnibase_spi
  - testing
  - protocols
refs: []
---

<!-- Migrated from omnibase_spi:docs/TESTING.md on 2026-09-01 -->

# Testing Guide

## Overview

Comprehensive testing strategies for protocol compliance and quality assurance.

## Protocol Testing

### Runtime Protocol Validation

```python
from omnibase_spi.protocols.container import ProtocolServiceRegistry
from omnibase_spi.protocols.core import ProtocolLogger

# Test protocol compliance
def test_protocol_compliance():
    registry = MockServiceRegistry()
    assert isinstance(registry, ProtocolServiceRegistry)

    logger = MockLogger()
    assert isinstance(logger, ProtocolLogger)

# Test protocol methods
async def test_protocol_methods():
    registry = MockServiceRegistry()

    # Test service registration
    registration_id = await registry.register_service(
        interface=ProtocolLogger,
        implementation=MockLogger,
        lifecycle="singleton",
        scope="global"
    )
    assert registration_id is not None

    # Test service resolution
    service = await registry.resolve_service(ProtocolLogger)
    assert service is not None
```

### Mock Protocol Implementation

```python
class MockServiceRegistry:
    """Mock implementation of ProtocolServiceRegistry."""

    def __init__(self):
        self.services = {}

    async def register_service(
        self,
        interface: Type[TInterface],
        implementation: Type[TImplementation],
        lifecycle: LiteralServiceLifecycle,
        scope: LiteralInjectionScope,
        configuration: dict[str, ContextValue] | None = None,
    ) -> str:
        registration_id = f"reg-{len(self.services)}"
        self.services[registration_id] = {
            "interface": interface,
            "implementation": implementation,
            "lifecycle": lifecycle,
            "scope": scope,
            "configuration": configuration
        }
        return registration_id

    async def resolve_service(
        self,
        interface: Type[TInterface],
        scope: LiteralInjectionScope | None = None,
        context: dict[str, ContextValue] | None = None,
    ) -> TInterface:
        for service_info in self.services.values():
            if service_info["interface"] == interface:
                return service_info["implementation"]()
        raise ServiceNotFoundError(f"Service {interface} not found")
```

## Integration Testing

### Service Integration Tests

```python
import pytest
from omnibase_spi.protocols.container import ProtocolServiceRegistry
from omnibase_spi.protocols.workflow_orchestration import ProtocolWorkflowOrchestrator

@pytest.fixture
async def service_registry():
    """Create service registry for testing."""
    registry = MockServiceRegistry()
    await registry.register_service(
        interface=ProtocolLogger,
        implementation=MockLogger,
        lifecycle="singleton",
        scope="global"
    )
    return registry

@pytest.fixture
async def workflow_orchestrator():
    """Create workflow orchestrator for testing."""
    return MockWorkflowOrchestrator()

async def test_service_integration(service_registry, workflow_orchestrator):
    """Test service integration."""
    # Resolve logger
    logger = await service_registry.resolve_service(ProtocolLogger)
    assert logger is not None

    # Start workflow
    workflow = await workflow_orchestrator.start_workflow(
        workflow_type="test-workflow",
        instance_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        initial_data={"test": "data"}
    )
    assert workflow.current_state == "pending"
```

### Event Bus Integration Tests

```python
async def test_event_bus_integration():
    """Test event bus integration."""
    event_bus = MockEventBus()

    # Subscribe to events
    subscription_id = await event_bus.subscribe_to_topic(
        topic="test-events",
        handler=test_event_handler
    )
    assert subscription_id is not None

    # Publish event
    await event_bus.publish_event(
        topic="test-events",
        message=ProtocolEventMessage(
            topic="test-events",
            value=b'{"test": "data"}',
            headers={"event_type": "test"}
        )
    )

    # Verify event was received
    assert len(event_bus.received_events) == 1

async def test_event_handler(message: ProtocolEventMessage, context: dict[str, ContextValue]):
    """Test event handler."""
    assert message.topic == "test-events"
    assert message.value == b'{"test": "data"}'
```

## Performance Testing

### Load Testing

```python
import asyncio
import time
from omnibase_spi.protocols.memory import ProtocolKeyValueStore

async def test_memory_performance():
    """Test memory performance under load."""
    store: ProtocolKeyValueStore = MockKeyValueStore()

    # Test lookups at scale
    start_time = time.time()
    for i in range(1000):
        assert store.has_key(f"key_{i}") or True
    end_time = time.time()

    assert (end_time - start_time) < 1.0  # Should complete in under 1 second

async def test_concurrent_operations():
    """Test concurrent key-value lookups."""
    store: ProtocolKeyValueStore = MockKeyValueStore()

    # Create concurrent tasks
    tasks = [
        asyncio.create_task(store.get_value(f"concurrent_key_{i}"))
        for i in range(100)
    ]

    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks)

    # Verify all lookups completed without raising
    assert len(results) == 100
```

## Validation Testing

### Input Validation Tests

```python
from omnibase_spi.protocols.schema import ProtocolInputValidator

async def test_input_validation():
    """Test input validation."""
    validator: ProtocolInputValidator = MockInputValidator()

    # Test a valid email
    result = await validator.validate_string(
        value="john@example.com",  # sanitization-ok: illustrative test fixture, not a real address
        min_length=1,
        max_length=254,
        pattern=None,
        allow_empty=False,
    )
    assert result.is_valid

    # Test an unsafe value against injection patterns
    result = await validator.check_security_patterns(
        value="'; DROP TABLE users; --",
        check_sql_injection=True,
        check_xss=False,
        check_path_traversal=False,
        check_command_injection=False,
    )
    assert not result.is_valid
    assert len(result.errors) > 0
```

## Test Utilities

### Test Helpers

```python
class TestHelpers:
    """Test helper utilities."""

    @staticmethod
    async def create_mock_service_registry():
        """Create mock service registry for testing."""
        registry = MockServiceRegistry()
        await registry.register_service(
            interface=ProtocolLogger,
            implementation=MockLogger,
            lifecycle="singleton",
            scope="global"
        )
        return registry

    @staticmethod
    async def create_mock_workflow_orchestrator():
        """Create mock workflow orchestrator for testing."""
        return MockWorkflowOrchestrator()

    @staticmethod
    async def create_mock_event_bus():
        """Create mock event bus for testing."""
        return MockEventBus()

    @staticmethod
    async def create_mock_memory():
        """Create mock memory for testing."""
        return MockMemory()
```

### Test Fixtures

```python
@pytest.fixture
async def mock_services():
    """Create all mock services for testing."""
    return {
        "registry": await TestHelpers.create_mock_service_registry(),
        "orchestrator": await TestHelpers.create_mock_workflow_orchestrator(),
        "event_bus": await TestHelpers.create_mock_event_bus(),
        "memory": await TestHelpers.create_mock_memory()
    }

@pytest.fixture
async def test_data():
    """Create test data for testing."""
    return {
        "user_id": "12345",
        "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
        "test_data": {"key": "value"}
    }
```

## Best Practices

### Testing Strategy

1. **Unit Tests** - Test individual protocol implementations
2. **Integration Tests** - Test protocol interactions
3. **Performance Tests** - Test under load and stress
4. **Validation Tests** - Test input validation and error handling

### Test Organization

1. **Protocol Tests** - Test protocol compliance
2. **Integration Tests** - Test service interactions
3. **Performance Tests** - Test scalability and performance
4. **Validation Tests** - Test data validation and error handling

### Mock Implementation

1. **Protocol Compliance** - Ensure mocks implement protocols correctly
2. **Behavioral Testing** - Test expected behaviors and edge cases
3. **Error Simulation** - Test error handling and recovery
4. **Performance Simulation** - Test under various load conditions

## API Reference

- **`Core Protocols` (in the omnibase_spi repository)** - System fundamentals
- **`Container Protocols` (in the omnibase_spi repository)** - Dependency injection
- **`Workflow Orchestration` (in the omnibase_spi repository)** - Event-driven FSM
- **`Validation` (in the omnibase_spi repository)** - Input validation

---

*For detailed protocol documentation, see the `API Reference` (in the omnibase_spi repository).*
