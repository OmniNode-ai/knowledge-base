---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Protocol Design Guidelines"
topics: [omnibase-infra, adr, protocol, design]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-protocol-design-guidelines.md on 2026-09-02. -->

# ADR: Protocol Design Guidelines

**Status**: Accepted
**Date**: 2026-01-17

## Context

The ONEX infrastructure codebase uses multiple abstraction mechanisms for defining interfaces:

1. **`typing.Protocol`** (PEP 544) - Structural typing with duck typing support
2. **Abstract Base Classes (ABCs)** - Nominal typing with shared implementation
3. **Concrete Base Classes** - Default implementations with override points

Without clear guidance, developers inconsistently choose between these abstractions, leading to:

- Protocols with implementation code (violating their purpose)
- ABCs used where structural typing would reduce coupling
- Concrete bases used where ABCs would enforce required overrides
- Over-engineered protocols for simple direct dependencies

This ADR establishes a decision framework for selecting the appropriate abstraction.

## Decision

Use the following decision matrix to select the appropriate interface abstraction:

### Decision Matrix

| Criterion | Protocol | ABC | Concrete Base |
|-----------|----------|-----|---------------|
| Structural typing (duck typing) | Yes | No | No |
| Shared implementation | No | Yes | Yes |
| Multiple inheritance friendly | Yes | Careful | No |
| Runtime `isinstance()` reliable | Method names only | Yes | Yes |
| Template method pattern | No | Yes | Yes |
| Protected helpers (`_method`) | No | Yes | Yes |
| State management | No | Yes | Yes |

### When to Use Protocol

Use `typing.Protocol` when:

- **Structural typing needed** - Consumer should work with any class having matching signatures
- **Cross-mixin method access** - Type-safe access to methods from cooperating mixins
- **Adapter/DI boundaries** - Loose coupling between components
- **Optional capabilities with guard flags** - Check capability before use (e.g., `_circuit_breaker_initialized`)

**Example**: `ProtocolCircuitBreakerAware` enables `MixinRetryExecution` to access circuit breaker methods from `MixinAsyncCircuitBreaker` without inheritance.

### When to Use ABC

Use `abc.ABC` with `@abstractmethod` when:

- **Shared behavior/implementation needed** - Common logic that subclasses inherit
- **Invariants must be enforced** - Constructor validation, state initialization
- **Protected helper methods required** - Internal API for subclass use
- **Runtime inheritance checks needed** - Reliable `isinstance()` checks

**Example**: Node base classes (`NodeEffect`, `NodeCompute`, `NodeReducer`, `NodeOrchestrator`) from `omnibase_core` use ABCs because they provide shared initialization and require subclass implementation.

### When to Use Concrete Base

Use a concrete base class when:

- **Default implementation with override points** - Sensible defaults, optional customization
- **Template method pattern** - Algorithm skeleton with customizable steps
- **Common initialization logic** - Constructor patterns shared by all subclasses

**Example**: Handler base classes that provide default error handling with optional override points.

### When NOT to Use Protocol

Avoid protocols when:

- **You need state** - Protocols cannot enforce instance attributes at runtime
- **Runtime guarantees required** - `isinstance()` only checks method names, not signatures
- **Private hooks needed** - Protocols cannot define protected/private API contracts

## Implementation Guidelines

### Protocol Conventions

```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class ProtocolExample(Protocol):
    """Protocol for example capability.

    Note:
        Add @runtime_checkable only if isinstance() checks are needed.
    """

    def method(self, param: str) -> bool:
        """Method description.

        REQUIRES: Document any preconditions (e.g., locks held).
        """
        ...  # Use Ellipsis, not pass or raise NotImplementedError
```

### Consumer Pattern for Cross-Mixin Protocols

When consuming a protocol from a cooperating mixin:

```python
from typing import cast


class MixinConsumer:
    """Mixin consuming a protocol from cooperating mixin."""

    # Guard flag - set by cooperating mixin when initialized
    _capability_initialized: bool = False

    def _as_capability(self) -> ProtocolCapability:
        """Cast self to protocol for type-safe access."""
        return cast(ProtocolCapability, self)

    def _use_capability_if_enabled(self) -> None:
        """Use capability only if initialized."""
        if self._capability_initialized:
            cap = self._as_capability()
            cap.some_method()
```

### ABC Pattern

```python
from abc import ABC, abstractmethod


class ServiceBase(ABC):
    """Abstract base for services with shared initialization."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._validate_config()

    @abstractmethod
    def execute(self) -> Result:
        """Subclasses must implement."""
        ...

    def _validate_config(self) -> None:
        """Shared validation logic."""
        if not self._config.is_valid:
            raise ConfigurationError("Invalid config")
```

## Consequences

### Positive

- **Clear decision framework** - Developers can quickly determine the appropriate abstraction
- **Reduced coupling** - Protocols enable structural typing at DI boundaries
- **Type safety** - All approaches provide full type checker support
- **Mixin composition** - Protocols solve the diamond inheritance problem for cooperating mixins
- **Consistent patterns** - Codebase uses each abstraction for its intended purpose

### Negative

- **Learning curve** - Developers must understand when to use each abstraction
- **Protocol limitations** - Cannot enforce state or provide implementation
- **Runtime checks limited** - `isinstance()` with protocols only checks method names, not signatures

### Trade-offs

| Abstraction | Flexibility | Safety | Complexity |
|-------------|-------------|--------|------------|
| Protocol | High | Compile-time | Low |
| ABC | Medium | Runtime + Compile | Medium |
| Concrete Base | Low | Runtime | Low |

## Common Mistakes to Avoid

### 1. Using `isinstance()` for Signature Checking

`isinstance()` with `@runtime_checkable` protocols only verifies method **names** exist, not signatures:

```python
# WRONG - This passes even if signatures don't match!
class BadImplementation:
    def execute(self) -> None:  # Missing required parameters
        pass

assert isinstance(BadImplementation(), ProtocolPluginCompute)  # True!
```

### 2. Putting Implementation in Protocol

Protocols define interfaces, not behavior:

```python
# WRONG - Protocol with implementation
class BadProtocol(Protocol):
    def process(self, data: str) -> str:
        return data.upper()  # Implementation in protocol!
```

### 3. Over-Engineering with Protocols

Not every interface needs a protocol:

```python
# WRONG - Protocol for simple direct dependency with one implementation
class ProtocolLogger(Protocol):
    def log(self, message: str) -> None: ...
```

Use protocols when you need structural typing or multiple implementations.

## Review Checklist

Use this checklist when reviewing PRs that add or modify protocols:

- [ ] Protocol uses `typing.Protocol` base
- [ ] `@runtime_checkable` added if `isinstance()` checks needed
- [ ] Method bodies use `...` (Ellipsis), not `pass` or `raise NotImplementedError`
- [ ] All method signatures have complete type hints
- [ ] Docstrings document behavioral contracts and concurrency requirements
- [ ] Protocol lives in appropriate location (`protocols/` or with coupled implementation)
- [ ] At least one implementation exists and satisfies the protocol
- [ ] No implementation code in protocol (use ABC if shared behavior needed)

## Related Documentation

- **Protocol Patterns** - Detailed implementation patterns and exemplars
- **Circuit Breaker Implementation** - Uses `ProtocolCircuitBreakerAware` for mixin composition
- **Container Dependency Injection** - Protocols as DI boundaries

## References

- [PEP 544 - Protocols: Structural subtyping](https://peps.python.org/pep-0544/)
- [typing.Protocol documentation](https://docs.python.org/3/library/typing.html#typing.Protocol)
- CLAUDE.md "File & Class Naming" section - `protocol_<name>.py` naming convention
