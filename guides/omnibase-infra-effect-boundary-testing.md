---
type: guide
status: current
date: "2026-09-02"
title: "Effect Boundary Testing"
topics: [omnibase-infra, effect, boundary, testing]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/effect_boundary_testing.md on 2026-09-02. -->

# Effect Boundary Testing

## Overview

Effect nodes perform external I/O (database, HTTP, Kafka, etc.). Testing code that
depends on effect services requires mock or stub implementations that replace real
infrastructure. The `EffectMockRegistry` and its thread-local utilities
provide a lightweight pattern for managing these test doubles.

## EffectMockRegistry

A simple registry mapping protocol names to mock/stub instances. Use it when you need
to wire up multiple effect mocks for a test without full container setup.

```python
from omnibase_infra.testing import EffectMockRegistry

registry = EffectMockRegistry()
registry.register("ProtocolPostgresAdapter", StubPostgresAdapter())
registry.register("ProtocolConsulClient", StubConsulClient())

adapter = registry.resolve("ProtocolPostgresAdapter")
```

### Key Properties

| Property | Description |
|----------|-------------|
| **Not thread-safe** | Each instance is single-threaded by design |
| **Explicit opt-in** | Users must call `register()` for each mock |
| **Helpful errors** | `resolve()` lists registered protocols on miss |
| **Overwrite semantics** | Re-registering the same name replaces the previous mock |

## Thread-Local Usage (pytest-xdist)

When running tests in parallel with `pytest -n auto`, each worker runs in its own
thread. Use the thread-local utilities to get an isolated registry per thread:

```python
from omnibase_infra.testing import get_thread_local_registry

registry = get_thread_local_registry()
registry.register("ProtocolEventBus", mock_bus)
```

### Scoped Context Manager

For automatic cleanup, use `scoped_effect_mock_registry()`:

```python
from omnibase_infra.testing import scoped_effect_mock_registry

with scoped_effect_mock_registry() as registry:
    registry.register("ProtocolPostgresAdapter", StubPostgresAdapter())
    # ... test code ...
# All registrations are cleared on exit
```

### Recommended Fixture Pattern

```python
import pytest
from omnibase_infra.testing import scoped_effect_mock_registry

@pytest.fixture
def effect_registry():
    """Provide a clean effect mock registry for each test."""
    with scoped_effect_mock_registry() as registry:
        yield registry
    # Automatically cleaned up

def test_registration_handler(effect_registry):
    effect_registry.register("ProtocolPostgresAdapter", StubPostgresAdapter())
    # ... test code ...
```

### Cleanup

Always clean up thread-local state to prevent test pollution:

```python
from omnibase_infra.testing import clear_thread_local_registry

@pytest.fixture(autouse=True)
def clean_thread_local():
    clear_thread_local_registry()
    yield
    clear_thread_local_registry()
```

## When to Use What

| Scenario | Approach |
|----------|----------|
| Single test, few mocks | Direct `EffectMockRegistry()` instance |
| Parallel tests (pytest-xdist) | `get_thread_local_registry()` |
| Fixture with auto-cleanup | `scoped_effect_mock_registry()` context manager |
| Full container wiring | `ModelONEXContainer` with `RegistryInfra*` classes |

## API Reference

### `EffectMockRegistry`

| Method | Description |
|--------|-------------|
| `register(protocol_name, mock)` | Register a mock for a protocol name |
| `resolve(protocol_name)` | Resolve a registered mock (raises `KeyError` on miss) |
| `has(protocol_name)` | Check if a protocol is registered |
| `unregister(protocol_name)` | Remove a registration |
| `clear()` | Remove all registrations |
| `registered_protocols` | Sorted list of registered protocol names |

### Thread-Local Utilities

| Function | Description |
|----------|-------------|
| `get_thread_local_registry()` | Get/create per-thread registry instance |
| `clear_thread_local_registry()` | Clear and remove the thread-local registry |
| `scoped_effect_mock_registry()` | Context manager with auto-cleanup |

## Related

- Container Dependency Injection (`../architecture/omnibase-infra-container-dependency-injection.md`) - Full DI patterns
- Testing Patterns (`../guides/omnibase-infra-testing-patterns.md`) - General testing conventions
- Protocol Patterns (`../architecture/omnibase-infra-protocol-patterns.md`) - Protocol interface design
- : Add thread-local utility for EffectMockRegistry
- : Effect Classification System
