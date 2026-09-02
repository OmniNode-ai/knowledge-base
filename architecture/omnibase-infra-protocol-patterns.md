---
type: architecture
status: accepted
date: "2026-09-02"
title: "Protocol Patterns"
topics: [omnibase-infra, protocol, patterns]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/protocol_patterns.md on 2026-09-02. -->

# Protocol Patterns

## Overview

Protocols in this codebase use `typing.Protocol` (PEP 544) to enable structural typing with full type checker support. Unlike abstract base classes (ABCs) that require explicit inheritance, protocols use structural subtyping - any class with matching method signatures automatically satisfies the protocol.

This approach enables three primary use cases in ONEX infrastructure:

1. **Mixin Composition** - Type-safe cross-mixin method access without inheritance conflicts (e.g., `ProtocolCircuitBreakerAware`)
2. **Plugin Systems** - Behavioral contracts for deterministic compute operations (e.g., `ProtocolPluginCompute`)
3. **Validation Frameworks** - Self-describing plugin interfaces for extensible validators (e.g., `ProtocolArchitectureRule`)

Protocols are the preferred abstraction boundary for interfaces where the consumer does not need to modify or extend behavior - only call it. When implementation sharing or runtime guarantees are required, use ABCs or concrete base classes instead.

## Protocol vs ABC vs Concrete Base

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

- **Structural typing needed** - Consumer should work with any class having matching signatures
- **Cross-mixin method access** - Type-safe access to methods from cooperating mixins
- **Adapter/DI boundaries** - Loose coupling between components
- **Optional capabilities with guard flags** - Check capability before use (e.g., `_circuit_breaker_initialized`)

### When to Use ABC

- **Shared behavior/implementation needed** - Common logic that subclasses inherit
- **Invariants must be enforced** - Constructor validation, state initialization
- **Protected helper methods required** - Internal API for subclass use
- **Runtime inheritance checks needed** - Reliable `isinstance()` checks

### When to Use Concrete Base

- **Default implementation with override points** - Sensible defaults, optional customization
- **Template method pattern** - Algorithm skeleton with customizable steps
- **Common initialization logic** - Constructor patterns shared by all subclasses

### When NOT to Use Protocol

- **You need state** - Protocols cannot enforce instance attributes at runtime
- **Runtime guarantees required** - `isinstance()` only checks method names, not signatures
- **Private hooks needed** - Protocols cannot define protected/private API contracts

## Exemplar: ProtocolCircuitBreakerAware

**Location**: `src/omnibase_infra/mixins/protocol_circuit_breaker_aware.py`

### Purpose

Enables type-safe access to circuit breaker methods across mixin boundaries without inheritance. When `MixinRetryExecution` needs to interact with `MixinAsyncCircuitBreaker` methods, the protocol provides the contract without requiring a common base class.

### Interface

```python
from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class ProtocolCircuitBreakerAware(Protocol):
    """Protocol for components with circuit breaker capability.

    Concurrency Safety:
        All circuit breaker methods MUST be called while holding
        ``_circuit_breaker_lock``. This is documented in each method's
        docstring using: "REQUIRES: self._circuit_breaker_lock must be
        held by caller."
    """

    _circuit_breaker_lock: asyncio.Lock

    async def _check_circuit_breaker(
        self, operation: str, correlation_id: UUID | None = None
    ) -> None:
        """Check if circuit breaker allows operation.

        REQUIRES: self._circuit_breaker_lock must be held by caller.

        Raises:
            InfraUnavailableError: If circuit breaker is open.
        """
        ...

    async def _record_circuit_failure(
        self, operation: str, correlation_id: UUID | None = None
    ) -> None:
        """Record a failure and potentially open the circuit.

        REQUIRES: self._circuit_breaker_lock must be held by caller.
        """
        ...

    async def _reset_circuit_breaker(self) -> None:
        """Reset circuit breaker to closed state.

        REQUIRES: self._circuit_breaker_lock must be held by caller.
        """
        ...
```

### Why Protocol Over ABC

1. **Multiple mixins compose without inheritance conflicts** - A handler can inherit from both `MixinAsyncCircuitBreaker` and `MixinRetryExecution` without MRO issues
2. **`MixinAsyncCircuitBreaker` satisfies protocol through structural typing** - No explicit inheritance declaration needed
3. **`MixinRetryExecution` consumes via `cast()` pattern** - Type-safe access without runtime overhead
4. **No runtime overhead, full type safety** - Type checker validates at compile time

### Consumer Pattern

The `MixinRetryExecution` class demonstrates the canonical pattern for consuming a protocol from a cooperating mixin:

```python
from typing import cast
from omnibase_infra.mixins.protocol_circuit_breaker_aware import (
    ProtocolCircuitBreakerAware,
)


class MixinRetryExecution:
    """Mixin providing retry logic with optional circuit breaker integration."""

    # Guard flag - set by MixinAsyncCircuitBreaker when initialized
    _circuit_breaker_initialized: bool = False

    def _as_circuit_breaker(self) -> ProtocolCircuitBreakerAware:
        """Cast self to ProtocolCircuitBreakerAware for type-safe access.

        Returns:
            Self cast as ProtocolCircuitBreakerAware for type checker.

        Note:
            Only call when _circuit_breaker_initialized is True.
        """
        return cast(ProtocolCircuitBreakerAware, self)

    async def _record_circuit_failure_if_enabled(
        self, operation: str, correlation_id: UUID
    ) -> None:
        """Record circuit breaker failure if enabled."""
        if self._circuit_breaker_initialized:
            cb = self._as_circuit_breaker()
            async with cb._circuit_breaker_lock:
                await cb._record_circuit_failure(operation, correlation_id)

    async def _check_circuit_if_enabled(
        self, operation: str, correlation_id: UUID
    ) -> None:
        """Check circuit breaker state if enabled."""
        if self._circuit_breaker_initialized:
            cb = self._as_circuit_breaker()
            async with cb._circuit_breaker_lock:
                await cb._check_circuit_breaker(operation, correlation_id)
```

### Best Practices from This Exemplar

- **Document concurrency requirements** - Each method specifies lock requirements
- **Use `...` (Ellipsis) for method bodies** - Per PEP 544 convention, not `pass` or `raise NotImplementedError`
- **Include version annotations** - `.. versionadded:: 0.4.1` for API stability tracking
- **Private prefix (`_`) for internal interfaces** - Signals this is not public API
- **Guard flag pattern** - Check `_circuit_breaker_initialized` before accessing protocol methods

## Mini-Exemplars

### ProtocolPluginCompute

**Location**: `src/omnibase_infra/protocols/protocol_plugin_compute.py`

**Purpose**: Behavioral contract for deterministic compute operations. Plugins implementing this protocol perform pure data transformations without side effects.

**Surface**: 1 method (`execute`)

```python
from typing import Protocol, runtime_checkable
from omnibase_infra.plugins.models import (
    ModelPluginInputData,
    ModelPluginOutputData,
    ModelPluginContext,
)


@runtime_checkable
class ProtocolPluginCompute(Protocol):
    """Protocol for deterministic compute plugins.

    Implementations must guarantee deterministic behavior where the
    same inputs always produce the same outputs.
    """

    def execute(
        self,
        input_data: ModelPluginInputData,
        context: ModelPluginContext,
    ) -> ModelPluginOutputData:
        """Execute deterministic computation on input data.

        Must not perform I/O operations or access external state.
        """
        ...
```

**Key Lesson**: Protocols enforce behavioral guarantees through documentation - the contract specifies what implementations **CAN'T** do (I/O, external state, randomness) as much as what they must provide. This documentation-as-contract approach works because violations manifest as test failures or runtime errors, not type errors.

### ProtocolArchitectureRule

**Location**: `src/omnibase_infra/nodes/architecture_validator/protocols/protocol_architecture_rule.py`

**Purpose**: Self-describing plugin interface for validation rules. Each rule provides metadata (ID, name, severity) alongside its validation logic.

**Surface**: 4 properties + 1 method

```python
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from omnibase_infra.enums import EnumValidationSeverity
    from omnibase_infra.nodes.architecture_validator.models import (
        ModelRuleCheckResult,
    )


@runtime_checkable
class ProtocolArchitectureRule(Protocol):
    """Contract for architecture validation rules."""

    @property
    def rule_id(self) -> str:
        """Unique identifier (e.g., 'NO_HANDLER_PUBLISHING')."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name (e.g., 'No Handler Publishing')."""
        ...

    @property
    def description(self) -> str:
        """Detailed description of what this rule checks."""
        ...

    @property
    def severity(self) -> EnumValidationSeverity:
        """Severity level for violations (ERROR, WARNING, INFO)."""
        ...

    def check(self, target: object) -> ModelRuleCheckResult:
        """Check the target against this rule."""
        ...
```

**Key Lesson**: Properties in protocols enable metadata-driven systems. The validator can introspect rules to build reports, filter by severity, or display human-readable names - all without coupling to specific rule implementations.

### ProtocolIdempotencyStore

**Location**: `src/omnibase_infra/idempotency/protocol_idempotency_store.py`

**Purpose**: Contract for message deduplication stores that track processed messages and prevent duplicate processing in distributed systems. Multiple implementations (in-memory for testing, PostgreSQL for production) satisfy the same interface.

**Surface**: 4 methods

```python
from typing import Protocol, runtime_checkable
from datetime import datetime
from uuid import UUID


@runtime_checkable
class ProtocolIdempotencyStore(Protocol):
    """Protocol for idempotency store implementations.

    Key Properties:
        - Coroutine-safe: All operations must be safe for concurrent async access
        - Atomic: check_and_record must provide atomic check-and-set semantics
        - Domain-isolated: Messages can be namespaced by domain
    """

    async def check_and_record(
        self,
        message_id: UUID,
        domain: str | None = None,
        correlation_id: UUID | None = None,
    ) -> bool:
        """Atomically check if message was processed and record if not.

        Returns True if message is new (should be processed).
        Returns False if message is duplicate (should be skipped).
        """
        ...

    async def is_processed(
        self, message_id: UUID, domain: str | None = None
    ) -> bool:
        """Check if a message was already processed (read-only)."""
        ...

    async def mark_processed(
        self,
        message_id: UUID,
        domain: str | None = None,
        correlation_id: UUID | None = None,
        processed_at: datetime | None = None,
    ) -> None:
        """Mark a message as processed (upsert)."""
        ...

    async def cleanup_expired(self, ttl_seconds: int) -> int:
        """Remove entries older than TTL. Returns count removed."""
        ...
```

**Key Lesson**: Protocols can specify concurrency and atomicity guarantees through documentation. The `check_and_record` method documents that exactly ONE caller must receive `True` when multiple coroutines race - InMemoryIdempotencyStore uses `asyncio.Lock`, PostgresIdempotencyStore uses database transactions. Same interface, different implementation strategies.

### ProtocolDomainPlugin

**Location**: `src/omnibase_infra/runtime/protocol_domain_plugin.py`

**Purpose**: Enables domain-specific initialization (Registration, Intelligence, etc.) to hook into the kernel bootstrap sequence without modifying kernel code. Follows dependency inversion - the kernel depends on the abstract protocol, not concrete implementations.

**Surface**: 2 properties + 6 methods (lifecycle hooks)

```python
from typing import Protocol, runtime_checkable
from omnibase_infra.runtime.models import (
    ModelDomainPluginConfig,
    ModelDomainPluginResult,
)


@runtime_checkable
class ProtocolDomainPlugin(Protocol):
    """Protocol for domain-specific initialization plugins.

    Lifecycle Order:
        1. should_activate() - Check environment/config
        2. initialize() - Create pools, connections
        3. wire_handlers() - Register handlers in container
        4. wire_dispatchers() - Register with dispatch engine
        5. start_consumers() - Start event consumers
        6. shutdown() - Clean up during kernel shutdown
    """

    @property
    def plugin_id(self) -> str:
        """Unique identifier (e.g., 'registration', 'intelligence')."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable name for logs and output."""
        ...

    def should_activate(self, config: ModelDomainPluginConfig) -> bool:
        """Check if plugin should activate based on environment."""
        ...

    async def initialize(
        self, config: ModelDomainPluginConfig
    ) -> ModelDomainPluginResult:
        """Create domain-specific resources (pools, connections)."""
        ...

    async def wire_handlers(
        self, config: ModelDomainPluginConfig
    ) -> ModelDomainPluginResult:
        """Register handlers with the container."""
        ...

    async def wire_dispatchers(
        self, config: ModelDomainPluginConfig
    ) -> ModelDomainPluginResult:
        """Register dispatchers with MessageDispatchEngine."""
        ...

    async def start_consumers(
        self, config: ModelDomainPluginConfig
    ) -> ModelDomainPluginResult:
        """Start event consumers."""
        ...

    async def shutdown(
        self, config: ModelDomainPluginConfig
    ) -> ModelDomainPluginResult:
        """Clean up resources during kernel shutdown."""
        ...
```

**Key Lesson**: Protocols define extension points for runtime systems. By defining lifecycle hooks (initialize, wire_handlers, shutdown), the kernel can orchestrate arbitrary domains without knowing their implementation details. New domains like "Intelligence" or "Audit" can be added by implementing this protocol - no kernel code changes required.

## Common Mistakes

### Using `isinstance()` for Signature Checking

`isinstance()` with `@runtime_checkable` protocols only verifies method **names** exist, not signatures:

```python
# WRONG - This passes even if signatures don't match!
class BadImplementation:
    def execute(self) -> None:  # Missing required parameters
        pass

# isinstance check passes (method name exists)
assert isinstance(BadImplementation(), ProtocolPluginCompute)  # True!

# But actual call fails
plugin.execute(input_data, context)  # TypeError at runtime
```

**Fix**: Use duck typing verification for critical interfaces:

```python
# Verify method exists and is callable
if hasattr(obj, "execute") and callable(obj.execute):
    # Type checker handles signature validation
    result = obj.execute(input_data, context)
```

### Forgetting `@runtime_checkable`

Without `@runtime_checkable`, `isinstance()` raises `TypeError`:

```python
# WRONG - Missing decorator
class MyProtocol(Protocol):
    def method(self) -> None: ...

isinstance(obj, MyProtocol)  # TypeError: Protocols without @runtime_checkable cannot be used with isinstance()
```

**Fix**: Add `@runtime_checkable` if you need runtime type checks.

### Putting Implementation in Protocol

Protocols define interfaces, not behavior:

```python
# WRONG - Protocol with implementation
class BadProtocol(Protocol):
    def process(self, data: str) -> str:
        return data.upper()  # Implementation in protocol!
```

**Fix**: Use ABC if you need shared implementation:

```python
from abc import ABC, abstractmethod

class ProcessorBase(ABC):
    @abstractmethod
    def process(self, data: str) -> str:
        """Subclasses must implement."""
        ...

    def preprocess(self, data: str) -> str:
        """Shared preprocessing logic."""
        return data.strip()
```

### Over-Engineering with Protocols

Not every interface needs a protocol:

```python
# WRONG - Protocol for simple direct dependency
class ProtocolLogger(Protocol):
    def log(self, message: str) -> None: ...

# When there's only one implementation and no testing benefit
class MyService:
    def __init__(self, logger: ProtocolLogger): ...
```

**Fix**: Use protocols when you need structural typing or multiple implementations. For simple DI, direct class references often suffice.

### Missing TYPE_CHECKING Imports

Protocol imports in consumer modules can cause circular imports at runtime:

```python
# WRONG - Direct import causes circular dependency
from omnibase_infra.protocols import ProtocolCircuitBreakerAware

class MyMixin:
    def get_breaker(self) -> ProtocolCircuitBreakerAware:
        return cast(ProtocolCircuitBreakerAware, self)
```

**Fix**: Use `TYPE_CHECKING` block to defer protocol imports to type-checking time only:

```python
from __future__ import annotations
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from omnibase_infra.protocols import ProtocolCircuitBreakerAware

class MyMixin:
    def get_breaker(self) -> ProtocolCircuitBreakerAware:
        return cast(ProtocolCircuitBreakerAware, self)
```

Note: `from __future__ import annotations` enables PEP 563 deferred annotation evaluation, allowing forward references without string quotes.

### Confusing Protocol Attributes with Instance Attributes

Protocol attributes define interface shape, not storage. Protocols cannot enforce that implementations actually store these attributes:

```python
# WRONG - Expecting protocol to enforce state
@runtime_checkable
class ProtocolStateful(Protocol):
    count: int  # This is a type hint, not storage!

class BadImpl:
    @property
    def count(self) -> int:
        return 42  # Property, not attribute - still satisfies protocol!

obj = BadImpl()
obj.count = 10  # AttributeError: can't set attribute
```

**Fix**: If you need guaranteed state storage, use ABC with explicit attribute initialization:

```python
from abc import ABC

class StatefulBase(ABC):
    def __init__(self) -> None:
        self.count: int = 0  # Guaranteed instance attribute

class GoodImpl(StatefulBase):
    def increment(self) -> None:
        self.count += 1  # Works as expected
```

For protocols, document that attributes may be properties and design consumers accordingly.

### Using `pass` Instead of `...` for Method Bodies

PEP 544 convention uses `...` (Ellipsis) for protocol method bodies, not `pass`:

```python
# WRONG - Using pass
class BadProtocol(Protocol):
    def method(self) -> None:
        pass

# WRONG - Using NotImplementedError
class AlsoBadProtocol(Protocol):
    def method(self) -> None:
        raise NotImplementedError
```

**Fix**: Use `...` (Ellipsis) for all protocol method bodies:

```python
class GoodProtocol(Protocol):
    def method(self) -> None:
        ...

    @property
    def value(self) -> int:
        ...
```

The `...` is semantically correct because protocol methods have no implementation - they define shape only. Using `pass` or `raise NotImplementedError` suggests there should be executable code, which is misleading.

## Review Checklist

Use this checklist when reviewing PRs that add or modify protocols:

```markdown
### Protocol Review Checklist
- [ ] Protocol uses `typing.Protocol` base
- [ ] `@runtime_checkable` added if `isinstance()` checks needed
- [ ] Method bodies use `...` (Ellipsis), not `pass` or `raise NotImplementedError`
- [ ] All method signatures have complete type hints
- [ ] Docstrings document behavioral contracts and concurrency requirements
- [ ] Protocol lives in appropriate location (`protocols/` or with coupled implementation)
- [ ] At least one implementation exists and satisfies the protocol
- [ ] No implementation code in protocol (use ABC if shared behavior needed)
- [ ] Version annotation included (`.. versionadded::`)
```

## Related Patterns

- **Circuit Breaker Implementation (`../guides/omnibase-infra-circuit-breaker-implementation.md`)** - Uses `ProtocolCircuitBreakerAware` for mixin composition
- **Error Handling Patterns (internal knowledge base)** - Error types raised by protocol implementations
- **Container Dependency Injection (`../architecture/omnibase-infra-container-dependency-injection.md`)** - Protocols as DI boundaries for loose coupling

## See Also

### Source Files

- `src/omnibase_infra/mixins/protocol_circuit_breaker_aware.py` - Cross-mixin protocol exemplar
- `src/omnibase_infra/protocols/protocol_plugin_compute.py` - Behavioral contract exemplar
- `src/omnibase_infra/nodes/architecture_validator/protocols/protocol_architecture_rule.py` - Metadata-driven protocol exemplar
- `src/omnibase_infra/mixins/mixin_retry_execution.py` - Protocol consumer pattern (`_as_circuit_breaker`)
- `src/omnibase_infra/idempotency/protocol_idempotency_store.py` - Adapter pattern with atomicity guarantees
- `src/omnibase_infra/runtime/protocol_domain_plugin.py` - Runtime extensibility with lifecycle hooks

### CLAUDE.md Sections

- **File & Class Naming** - `protocol_<name>.py` naming convention
- **Protocol File Naming** - Single protocol vs domain-grouped `protocols.py`
- **Strong Typing & Models** - No `Any` types in protocol signatures

### External References

- [PEP 544 - Protocols: Structural subtyping](https://peps.python.org/pep-0544/)
- [typing.Protocol documentation](https://docs.python.org/3/library/typing.html#typing.Protocol)
