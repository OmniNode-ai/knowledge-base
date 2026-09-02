---
type: guide
status: current
date: "2026-09-01"
title: "omnibase_spi Integration Testing"
topics:
  - omnibase_spi
  - testing
  - integration
refs: []
---

<!-- Migrated from omnibase_spi:tests/integration/README.md on 2026-09-01 -->

# Integration Tests

This directory contains integration tests for `omnibase_spi` protocols. Unlike unit tests
that verify protocol compliance in isolation, integration tests verify that protocols work
correctly with real (or realistic mock) implementations in end-to-end scenarios.

## Purpose

Integration tests in the SPI layer serve to:

1. **Verify Protocol Contracts**: Ensure that protocol definitions are implementable and
   that implementations work correctly together.

2. **Test Provider Patterns**: Validate factory patterns, lifecycle management, and
   provider configurations work as expected.

3. **Cross-Protocol Validation**: Test that multiple protocols can work together in
   realistic scenarios.

4. **Implementation Examples**: Serve as working examples of how to implement and use
   the protocols defined in `omnibase_spi`.

## Directory Structure

```
tests/integration/
├── __init__.py                    # Package marker
├── conftest.py                    # Integration fixtures and markers
├── README.md                      # This file
└── test_protocol_integration.py   # Sample integration tests
```

## Running Integration Tests

### Run All Integration Tests

```bash
uv run pytest tests/integration/ -v
```

### Run Integration Tests by Marker

```bash
# Run only integration tests
uv run pytest -m "integration" -v

# Run integration tests excluding slow tests
uv run pytest -m "integration and not slow" -v

# Skip integration tests (run only unit tests)
uv run pytest -m "not integration"
```

### Run Specific Integration Test File

```bash
uv run pytest tests/integration/test_protocol_integration.py -v
```

### Run with Coverage

```bash
uv run pytest tests/integration/ --cov=src/omnibase_spi --cov-report=term-missing
```

## Writing Integration Tests

### Test Markers

All integration tests should be marked with `@pytest.mark.integration`:

```python
import pytest

@pytest.mark.integration
class TestEventBusProviderIntegration:
    """Integration tests for event bus provider."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, mock_event_bus_provider):
        # Test implementation
        pass
```

For slow tests, add the `slow` marker:

```python
@pytest.mark.integration
@pytest.mark.slow
async def test_large_message_throughput():
    # Test that takes a long time
    pass
```

### Available Fixtures

The `conftest.py` provides several fixtures for integration testing:

| Fixture | Type | Description |
|---------|------|-------------|
| `mock_event_bus_provider` | `MockEventBusProvider` | A functional mock implementation of `ProtocolEventBusProvider` |
| `connected_event_bus` | `MockEventBus` | A pre-connected event bus instance |
| `mock_compute_node` | `MockComputeNode` | A functional mock implementation of `ProtocolComputeNode` |
| `mock_handler` | `MagicMock` | A generic mock for handler/callback testing |

### Mock Implementations

The fixtures provide mock implementations that:

1. **Are Functional**: They actually work, not just pass `isinstance` checks
2. **Track State**: They maintain state for verification (e.g., published messages)
3. **Support Testing**: They provide helper methods for test assertions

Example usage:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_and_verify(connected_event_bus):
    # Publish a message
    await connected_event_bus.publish("test-topic", {"key": "value"})

    # Verify using the mock's helper method
    messages = connected_event_bus.get_published_messages()
    assert len(messages) == 1
    assert messages[0]["topic"] == "test-topic"
```

### Best Practices

1. **Mark All Tests**: Always use `@pytest.mark.integration` for discoverability

2. **Test Real Scenarios**: Focus on realistic usage patterns, not edge cases (those
   belong in unit tests)

3. **Use Provided Fixtures**: Leverage the mock implementations in `conftest.py`
   rather than creating ad-hoc mocks

4. **Clean Up Resources**: Use `async with` or ensure cleanup in `finally` blocks

5. **Document Intent**: Each test should have a clear docstring explaining what
   end-to-end behavior is being verified

## Integration vs Unit Tests

| Aspect | Unit Tests | Integration Tests |
|--------|------------|-------------------|
| Location | `tests/protocols/` | `tests/integration/` |
| Focus | Protocol compliance | End-to-end behavior |
| Mocks | Minimal implementations | Functional implementations |
| Speed | Fast | May be slower |
| Marker | None (default) | `@pytest.mark.integration` |

## CI/CD Configuration

In CI pipelines, you may want to run unit and integration tests separately:

```yaml
# Run unit tests first (faster)
- name: Unit Tests
  run: uv run pytest -m "not integration" --cov

# Run integration tests
- name: Integration Tests
  run: uv run pytest -m "integration" -v
```

## Adding New Integration Tests

When adding new protocols to `omnibase_spi`, consider adding:

1. **Mock Implementation**: Add a functional mock to `conftest.py`
2. **Fixture**: Create a pytest fixture for the mock
3. **Integration Tests**: Add tests verifying the protocol works in realistic scenarios

See `test_protocol_integration.py` for examples of the expected test patterns.
