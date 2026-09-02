---
type: architecture
status: accepted
date: "2026-09-02"
title: "Async Thread Safety Pattern"
topics: [omnibase-infra, async, thread, safety]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/async_thread_safety_pattern.md on 2026-09-02. -->

# Async Thread Safety Pattern

## Overview

This document describes thread safety patterns for asyncio-based concurrency in ONEX infrastructure components. These patterns apply when multiple coroutines may access shared state within a single event loop.

**Key Distinction**: asyncio uses cooperative concurrency (single-threaded with coroutines), not multi-threading. The patterns here protect against race conditions during `await` points, not CPU-level parallelism.

### When to Use

- Components with mutable shared state accessed by multiple coroutines
- Counter updates that must be atomic
- State transitions that must be consistent
- Operations with pre-check/execute/post-update patterns

### When NOT Needed

- Pure functions with no shared state
- Read-only operations on immutable data
- Single-coroutine-at-a-time usage (caller serializes)
- Dataclasses used as value objects (create new instances instead of mutating)

## Lock Scope Patterns

The critical insight is to **minimize lock scope** - only protect the specific state mutations, not entire operations.

### Pattern: Counter-Only Locking

```python
import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

# Type alias for async backend operations that return bool
BackendOperation = Callable[[], Awaitable[bool]]


class OperationTracker:
    """Tracks operations with atomic counter updates.

    Thread Safety:
        Designed for single asyncio event loop usage. The asyncio.Lock
        protects counter updates ONLY, not the entire operation.

    Lock Scope:
        - PROTECTED: Counter increments (execution_count, failed_count)
        - NOT PROTECTED: Pre-checks, operation execution, callbacks
    """

    def __init__(self) -> None:
        self.execution_count = 0
        self.failed_count = 0
        self._lock = asyncio.Lock()

    async def execute_tracked_operation(
        self,
        operation_id: UUID,
        backend_operation: BackendOperation,
    ) -> bool:
        """Execute operation with atomic counter tracking.

        Multiple concurrent calls are supported. Counters are eventually
        accurate after all operations complete.
        """
        # --- PHASE 1: Pre-execution (NO LOCK HELD) ---
        # Pre-checks run concurrently, no lock needed
        await self._validate_preconditions(operation_id)

        # --- PHASE 2: Execution (NO LOCK HELD) ---
        # Main operation runs without lock to allow concurrency
        try:
            result = await backend_operation()

            # --- COUNTER UPDATE: Lock acquired briefly ---
            async with self._lock:
                self.execution_count += 1
            # --- Lock released immediately ---

            return result

        except Exception:
            # --- FAILURE COUNTER: Lock acquired briefly ---
            async with self._lock:
                self.failed_count += 1
            # --- Lock released ---
            raise
```

### Pattern: State Transition Locking

```python
import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

# Type alias for async callbacks with no parameters
# Callbacks that perform I/O or state transitions typically have this signature
AsyncCallback = Callable[[], Awaitable[None]]


@dataclass
class StateManager:
    """Manages state with atomic transitions.

    Thread Safety:
        Lock protects state mutations only. Callbacks execute outside
        lock to avoid deadlocks from callback-initiated lock acquisition.

    Lock Scope:
        - PROTECTED: is_active, state_data modifications
        - NOT PROTECTED: Transition callbacks (may perform I/O)

    Callback Type:
        transition_callbacks expects functions with signature:
            async def callback() -> None

        Callbacks are awaited sequentially after state transition completes.
    """

    is_active: bool = False
    state_data: dict[str, object] = field(default_factory=dict)
    transition_callbacks: list[AsyncCallback] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def register_transition_callback(self, callback: AsyncCallback) -> None:
        """Register a callback to be invoked after state transitions.

        Args:
            callback: Async function with signature `async def fn() -> None`.
                      Will be awaited after transition completes.
        """
        self.transition_callbacks.append(callback)

    async def transition_to_active(self) -> None:
        """Transition to active state.

        Acquires lock for state modification, releases before callbacks.
        """
        # Acquire lock for atomic state transition
        async with self._lock:
            if self.is_active:
                return  # Already active, early exit
            self.is_active = True
            self.state_data["activated_at"] = time.time()

        # Callbacks execute OUTSIDE lock (may perform I/O, acquire other locks)
        for callback in self.transition_callbacks:
            await callback()


# Example callback implementations
async def log_activation() -> None:
    """Example callback - logs activation event."""
    print("State activated")


async def notify_subscribers() -> None:
    """Example callback - notifies external subscribers."""
    await asyncio.sleep(0.01)  # Simulate I/O


# Usage (run in async context)
async def example_state_transition() -> None:
    """Example usage of StateManager with callbacks."""
    manager = StateManager()
    manager.register_transition_callback(log_activation)
    manager.register_transition_callback(notify_subscribers)
    await manager.transition_to_active()
```

## Counter Accuracy Pattern

Counters are **eventually accurate** - they correctly reflect totals after all concurrent operations complete, but may show intermediate values during active execution.

### The Problem

```python
# INCORRECT: Asserting during active execution
async def incorrect_pattern(executor: EffectExecutor) -> None:
    """Demonstrates race condition when asserting during execution."""
    task = asyncio.create_task(executor.execute(...))
    assert executor.execution_count == 0  # Race condition! May be 0 or 1
    await task
```

### The Solution

```python
# CORRECT: Wait for all operations before asserting
async def correct_pattern(executor: EffectExecutor) -> None:
    """Demonstrates proper counter verification after gather."""
    results = await asyncio.gather(
        executor.execute(uuid4(), "op1"),
        executor.execute(uuid4(), "op2"),
        executor.execute(uuid4(), "op3"),
        return_exceptions=True,
    )
    # Now counters are stable and accurate
    assert executor.execution_count + executor.failed_count == 3
```

### Test Utility

```python
import asyncio
from collections.abc import Coroutine
from typing import TypeVar

# TypeVar for generic result type
T = TypeVar("T")


async def gather_with_error_collection(
    coroutines: list[Coroutine[None, None, T]],
    *,
    return_exceptions: bool = True,
) -> tuple[list[T], list[Exception]]:
    """Execute coroutines concurrently and separate successes from failures.

    Simplifies the common pattern of running multiple async operations
    and classifying their outcomes.

    Type Parameters:
        T: The return type of the coroutines. All coroutines should return
           the same type for type-safe result handling.

    Args:
        coroutines: List of coroutines to execute concurrently.
                    Each coroutine should have signature:
                    `async def fn(...) -> T`
        return_exceptions: If True, exceptions are captured instead of raised.

    Returns:
        Tuple of (successful_results, exceptions).
        - successful_results: List of T values from successful operations
        - exceptions: List of Exception instances from failed operations

    Example:
        >>> # Type-safe usage with bool-returning operations
        >>> async def operation(i: int) -> bool:
        ...     return i % 2 == 0
        ...
        >>> successes, failures = await gather_with_error_collection(
        ...     [operation(i) for i in range(10)]
        ... )
        >>> # successes is list[bool], failures is list[Exception]
        >>> assert len(successes) + len(failures) == 10
    """
    results = await asyncio.gather(*coroutines, return_exceptions=return_exceptions)

    successes: list[T] = [r for r in results if not isinstance(r, Exception)]
    failures: list[Exception] = [r for r in results if isinstance(r, Exception)]

    return successes, failures
```

## Callback Execution Outside Locks

**Critical Rule**: Callbacks that may perform I/O or acquire locks MUST execute outside the lock that triggers them.

### Why?

1. **Deadlock Prevention**: If callback acquires the same lock, deadlock occurs
2. **I/O Blocking**: Holding lock during I/O blocks all waiters unnecessarily
3. **Cascading Delays**: Long callbacks delay unrelated state updates

### Pattern: Capture-Then-Execute

```python
import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

# Type aliases for callback signatures
# Use descriptive names to clarify the callback's purpose

# Simple async callback with no parameters
AsyncCallback = Callable[[], Awaitable[None]]

# Callback that receives recovery context (e.g., recovery duration, timestamp)
RecoveryCallback = Callable[[float], Awaitable[None]]


@dataclass
class RecoveryManager:
    """Manages recovery with typed callbacks.

    Callback Types:
        recovery_callbacks: list[AsyncCallback]
            Simple callbacks invoked after recovery completes.
            Signature: async def callback() -> None

        recovery_with_context_callbacks: list[RecoveryCallback]
            Callbacks that receive the recovery timestamp.
            Signature: async def callback(recovered_at: float) -> None
    """

    is_recovering: bool = False
    recovered_at: float = 0.0
    recovery_callbacks: list[AsyncCallback] = field(default_factory=list)
    recovery_with_context_callbacks: list[RecoveryCallback] = field(
        default_factory=list
    )
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def register_recovery_callback(self, callback: AsyncCallback) -> None:
        """Register a simple recovery callback.

        Args:
            callback: Async function with signature `async def fn() -> None`.
        """
        self.recovery_callbacks.append(callback)

    def register_recovery_with_context(self, callback: RecoveryCallback) -> None:
        """Register a callback that receives recovery context.

        Args:
            callback: Async function with signature
                      `async def fn(recovered_at: float) -> None`.
        """
        self.recovery_with_context_callbacks.append(callback)

    async def simulate_recovery_with_callbacks(
        self,
        duration_ms: int = 100,
    ) -> None:
        """Recover from failure state with callbacks.

        Thread Safety:
            Acquires lock for state transition only. Callbacks execute
            outside lock to allow concurrent I/O operations.
        """
        await asyncio.sleep(duration_ms / 1000.0)

        # Step 1: Acquire lock and update state atomically
        async with self._lock:
            self.is_recovering = False
            self.recovered_at = time.time()
            # Capture callbacks to execute (could also copy list if mutable)
            simple_callbacks = self.recovery_callbacks
            context_callbacks = self.recovery_with_context_callbacks
            recovery_time = self.recovered_at

        # Step 2: Execute callbacks OUTSIDE lock
        for callback in simple_callbacks:
            await callback()  # May perform I/O, acquire other locks safely

        for callback in context_callbacks:
            await callback(recovery_time)  # Pass recovery context


# Example callback implementations
async def log_recovery() -> None:
    """Simple callback - logs recovery completion."""
    print("System recovered")


async def update_metrics(recovered_at: float) -> None:
    """Context callback - updates metrics with recovery timestamp."""
    print(f"Recovery completed at {recovered_at}")


# Usage (run in async context)
async def example_recovery() -> None:
    """Example usage of RecoveryManager with callbacks."""
    manager = RecoveryManager()
    manager.register_recovery_callback(log_recovery)
    manager.register_recovery_with_context(update_metrics)
    await manager.simulate_recovery_with_callbacks(duration_ms=50)
```

### Anti-Pattern: Lock Held During Callbacks

```python
# WRONG - Holds lock during potentially slow callbacks
async def wrong_callback_execution(self) -> None:
    """Anti-pattern: holding lock during callback execution."""
    async with self._lock:
        self.is_recovering = False
        for callback in self.recovery_callbacks:
            await callback()  # If this acquires _lock -> DEADLOCK
                              # If this is slow -> all waiters blocked
```

## Callback Type Patterns Reference

This section provides a comprehensive reference for callback type hints used throughout ONEX infrastructure.

### Common Callback Type Aliases

```python
from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

# ============================================================
# SIMPLE CALLBACKS (no parameters)
# ============================================================

# Async callback with no parameters, no return value
# Use for: notifications, cleanup, logging
AsyncCallback = Callable[[], Awaitable[None]]

# Sync callback with no parameters, no return value
# Use for: synchronous cleanup, simple state updates
SyncCallback = Callable[[], None]


# ============================================================
# CALLBACKS WITH CONTEXT (single parameter)
# ============================================================

# Callback that receives a timestamp (float)
# Use for: metrics, timing, recovery tracking
TimestampCallback = Callable[[float], Awaitable[None]]

# Callback that receives a correlation ID
# Use for: distributed tracing, request tracking
CorrelationCallback = Callable[[UUID], Awaitable[None]]

# Callback that receives an error
# Use for: error handlers, failure notifications
ErrorCallback = Callable[[Exception], Awaitable[None]]

# Callback that receives a generic message/payload
MessageCallback = Callable[[str], Awaitable[None]]


# ============================================================
# CALLBACKS WITH MULTIPLE PARAMETERS
# ============================================================

# Callback for operation completion (operation_id, success, duration)
OperationCompleteCallback = Callable[[UUID, bool, float], Awaitable[None]]

# Callback for state transitions (old_state, new_state)
StateTransitionCallback = Callable[[str, str], Awaitable[None]]


# ============================================================
# CALLBACKS THAT RETURN VALUES
# ============================================================

# Validator callback - returns True if valid
ValidatorCallback = Callable[[], Awaitable[bool]]

# Transform callback - receives input, returns transformed output
T = TypeVar("T")
U = TypeVar("U")
TransformCallback = Callable[[T], Awaitable[U]]

# Decision callback - returns action to take
DecisionCallback = Callable[[], Awaitable[str]]
```

### Callback Registration Pattern

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from uuid import UUID

# Define descriptive type aliases for your domain
OnConnectCallback = Callable[[], Awaitable[None]]
OnDisconnectCallback = Callable[[str], Awaitable[None]]  # receives reason
OnErrorCallback = Callable[[Exception, UUID], Awaitable[None]]  # error + correlation


@dataclass
class ConnectionManager:
    """Connection manager with typed callback registration.

    Callback Types:
        on_connect: Called when connection established.
            Signature: async def callback() -> None

        on_disconnect: Called when connection lost.
            Signature: async def callback(reason: str) -> None

        on_error: Called when connection error occurs.
            Signature: async def callback(error: Exception, correlation_id: UUID) -> None
    """

    on_connect_callbacks: list[OnConnectCallback] = field(default_factory=list)
    on_disconnect_callbacks: list[OnDisconnectCallback] = field(default_factory=list)
    on_error_callbacks: list[OnErrorCallback] = field(default_factory=list)

    def on_connect(self, callback: OnConnectCallback) -> OnConnectCallback:
        """Register a connection callback. Can be used as decorator.

        Example:
            @manager.on_connect
            async def handle_connect() -> None:
                print("Connected!")
        """
        self.on_connect_callbacks.append(callback)
        return callback  # Return for decorator pattern

    def on_disconnect(self, callback: OnDisconnectCallback) -> OnDisconnectCallback:
        """Register a disconnection callback. Can be used as decorator.

        Example:
            @manager.on_disconnect
            async def handle_disconnect(reason: str) -> None:
                print(f"Disconnected: {reason}")
        """
        self.on_disconnect_callbacks.append(callback)
        return callback

    def on_error(self, callback: OnErrorCallback) -> OnErrorCallback:
        """Register an error callback. Can be used as decorator.

        Example:
            @manager.on_error
            async def handle_error(error: Exception, correlation_id: UUID) -> None:
                logger.error(f"Error {correlation_id}: {error}")
        """
        self.on_error_callbacks.append(callback)
        return callback

    async def _notify_connect(self) -> None:
        """Notify all connect callbacks (called outside lock)."""
        for callback in self.on_connect_callbacks:
            await callback()

    async def _notify_disconnect(self, reason: str) -> None:
        """Notify all disconnect callbacks (called outside lock)."""
        for callback in self.on_disconnect_callbacks:
            await callback(reason)

    async def _notify_error(self, error: Exception, correlation_id: UUID) -> None:
        """Notify all error callbacks (called outside lock)."""
        for callback in self.on_error_callbacks:
            await callback(error, correlation_id)
```

### Event-Based Callback Pattern

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Event types for callback dispatch."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    MESSAGE_RECEIVED = "message_received"
    ERROR = "error"


# Event payload model for type-safe event data
class EventPayload(BaseModel):
    """Base event payload."""
    event_type: EventType
    timestamp: float
    data: dict[str, object] = Field(default_factory=dict)


# Callback that receives typed event payload
EventCallback = Callable[[EventPayload], Awaitable[None]]


@dataclass
class EventEmitter:
    """Event emitter with typed callbacks per event type.

    Supports registering multiple callbacks per event type.
    All callbacks receive a typed EventPayload.
    """

    _callbacks: dict[EventType, list[EventCallback]] = field(
        default_factory=lambda: {et: [] for et in EventType}
    )

    def on(self, event_type: EventType, callback: EventCallback) -> EventCallback:
        """Register callback for event type.

        Args:
            event_type: The event type to listen for.
            callback: Async function with signature:
                      `async def fn(payload: EventPayload) -> None`

        Returns:
            The callback (for decorator pattern).

        Example:
            @emitter.on(EventType.CONNECTED)
            async def handle_connected(payload: EventPayload) -> None:
                print(f"Connected at {payload.timestamp}")
        """
        self._callbacks[event_type].append(callback)
        return callback

    async def emit(self, payload: EventPayload) -> None:
        """Emit event to all registered callbacks.

        Args:
            payload: The event payload to dispatch.
        """
        for callback in self._callbacks[payload.event_type]:
            await callback(payload)
```

### Callable Protocol Pattern

For more complex callback requirements, use `Protocol` instead of `Callable`:

```python
import asyncio
from typing import Protocol
from uuid import UUID


class ReconnectionHandler(Protocol):
    """Protocol for reconnection handling callbacks.

    Implementations must be async and accept reconnection context.
    Using Protocol allows for more complex signatures and documentation.
    """

    async def __call__(
        self,
        attempt: int,
        max_attempts: int,
        last_error: Exception | None,
        correlation_id: UUID,
    ) -> bool:
        """Handle reconnection attempt.

        Args:
            attempt: Current attempt number (1-indexed).
            max_attempts: Maximum attempts configured.
            last_error: The error from previous attempt, or None for first.
            correlation_id: Request correlation ID.

        Returns:
            True to continue reconnection, False to abort.
        """
        ...


class BackoffCalculator(Protocol):
    """Protocol for backoff delay calculation."""

    def __call__(self, attempt: int, base_delay: float) -> float:
        """Calculate delay for attempt.

        Args:
            attempt: Current attempt number.
            base_delay: Base delay in seconds.

        Returns:
            Delay in seconds before next attempt.
        """
        ...


# Usage with Protocol
async def reconnect_with_handler(
    handler: ReconnectionHandler,
    backoff: BackoffCalculator,
    correlation_id: UUID,
) -> bool:
    """Reconnect using typed handlers.

    Args:
        handler: Reconnection decision handler.
        backoff: Backoff calculation function.
        correlation_id: Request correlation ID.
    """
    for attempt in range(1, 6):
        should_continue = await handler(
            attempt=attempt,
            max_attempts=5,
            last_error=None,
            correlation_id=correlation_id,
        )
        if not should_continue:
            return False

        delay = backoff(attempt, 1.0)
        await asyncio.sleep(delay)

    return True
```

## Test Isolation Recommendations

### Fresh Instances Per Test

Use pytest fixtures that provide fresh instances:

```python
@pytest.fixture
def effect_executor(
    idempotency_store: InMemoryIdempotencyStore,
    failure_injector: FailureInjector,
    backend_client: MagicMock,
) -> EffectExecutor:
    """Create fresh executor per test.

    Returns:
        EffectExecutor with zero counters and clean state.
    """
    return EffectExecutor(
        idempotency_store=idempotency_store,
        failure_injector=failure_injector,
        backend_client=backend_client,
    )
```

### Reset Methods for Shared State

When fresh instances are expensive, provide reset methods:

```python
def reset_counts(self) -> None:
    """Reset execution counters.

    Warning:
        NOT thread-safe. Only call when no concurrent operations
        are in progress. Typically called at test setup/teardown.
    """
    # No lock - caller ensures no concurrent operations
    self.execution_count = 0
    self.failed_count = 0
```

### Gather-Then-Assert Pattern

For concurrent test scenarios:

```python
async def test_concurrent_operations(effect_executor):
    """Test concurrent execution with proper counter verification."""
    # Launch multiple concurrent operations
    results = await asyncio.gather(
        effect_executor.execute(uuid4(), "op1"),
        effect_executor.execute(uuid4(), "op2"),
        effect_executor.execute(uuid4(), "op3"),
        effect_executor.execute(uuid4(), "op4"),
        effect_executor.execute(uuid4(), "op5"),
        return_exceptions=True,
    )

    # NOW counters are stable - safe to assert
    total = effect_executor.execution_count + effect_executor.failed_count
    assert total == 5, f"Expected 5 operations tracked, got {total}"

    # Classify results
    successes = [r for r in results if r is True]
    failures = [r for r in results if isinstance(r, Exception)]

    # Counters should match result classification
    assert effect_executor.execution_count == len(successes)
    assert effect_executor.failed_count == len(failures)
```

## Complete Example: ChaosEffectExecutor

This example from the chaos testing infrastructure demonstrates all patterns:

```python
class ChaosEffectExecutor:
    """Effect executor with chaos injection capability.

    Thread Safety:
        Designed for single asyncio event loop usage. NOT thread-safe
        for multi-threaded access.

        The asyncio.Lock provides atomicity for counter updates ONLY.
        Lock is NOT held during the entire execute operation.

    Lock Scope:
        - PROTECTED: execution_count and failed_count increments
        - NOT PROTECTED: Idempotency checks, chaos injection, backend execution

    Concurrency Considerations:
        Multiple concurrent calls to execute_with_chaos are supported.
        Each call will:
        1. Independently check idempotency (no lock held)
        2. Execute backend operations concurrently (no lock held)
        3. Atomically update counters (lock acquired/released per update)

    Counter Accuracy:
        Counters are eventually accurate - they reflect total successes
        and failures, but assertions during active execution may observe
        intermediate states.

    Test Isolation:
        For deterministic testing:
        1. Sequential execution: Await each operation individually
        2. Gather then assert: Use asyncio.gather() then check counters
        3. Fresh executor per test: Use fixture for clean state
    """

    def __init__(
        self,
        idempotency_store: InMemoryIdempotencyStore,
        failure_injector: FailureInjector,
        backend_client: MagicMock,
    ) -> None:
        self.idempotency_store = idempotency_store
        self.failure_injector = failure_injector
        self.backend_client = backend_client
        self.execution_count = 0
        self.failed_count = 0
        # Lock for atomic counter updates only
        self._lock = asyncio.Lock()

    async def execute_with_chaos(
        self,
        intent_id: UUID,
        operation: str,
        domain: str = "chaos",
        correlation_id: UUID | None = None,
        fail_point: str | None = None,
    ) -> bool:
        """Execute operation with chaos injection.

        Args:
            intent_id: Unique identifier for this intent.
            operation: Name of the operation.
            domain: Idempotency domain.
            correlation_id: Optional correlation ID.
            fail_point: Specific point to inject failure.

        Returns:
            True if operation succeeded.
        """
        # --- PHASE 1: Pre-execution chaos (NO LOCK) ---
        if fail_point == "pre":
            await self.failure_injector.maybe_inject_failure(
                f"{operation}:pre", correlation_id
            )

        # --- PHASE 2: Idempotency check (NO LOCK) ---
        # Store has its own synchronization
        is_new = await self.idempotency_store.check_and_record(
            message_id=intent_id,
            domain=domain,
            correlation_id=correlation_id,
        )

        if not is_new:
            return True  # Duplicate - skip execution

        # --- PHASE 3: Execution (NO LOCK) ---
        try:
            if fail_point == "mid":
                await self.failure_injector.maybe_inject_failure(
                    f"{operation}:mid", correlation_id
                )

            await self.failure_injector.maybe_inject_latency()
            await self.backend_client.execute(operation, intent_id)

            # --- Counter update: Lock briefly ---
            async with self._lock:
                self.execution_count += 1

            if fail_point == "post":
                await self.failure_injector.maybe_inject_failure(
                    f"{operation}:post", correlation_id
                )

            return True

        except Exception:
            # --- Failure counter: Lock briefly ---
            async with self._lock:
                self.failed_count += 1
            raise
```

## Best Practices Summary

### DO

- Minimize lock scope to specific state mutations
- Execute callbacks outside locks
- Use `asyncio.gather()` before asserting on counters
- Provide fresh fixtures per test
- Document thread safety in class docstrings
- Clearly specify what is protected vs not protected
- Use typed callback aliases (e.g., `AsyncCallback = Callable[[], Awaitable[None]]`)
- Document callback signatures in class docstrings
- Use `Protocol` for complex callback signatures with documentation

### DON'T

- Hold locks during I/O operations
- Assert on counters during active concurrent execution
- Share mutable instances across tests without reset
- Use same lock for unrelated state (creates contention)
- Call lock-acquiring methods from within callbacks
- Use untyped `list` for callback collections (always use `list[CallbackType]`)
- Use `Any` in callback type hints (use `object` or specific types)

## Multi-Threading Warning

These patterns are for **asyncio cooperative concurrency only**. If your code uses `concurrent.futures.ThreadPoolExecutor` or multiple threads:

1. Use `threading.Lock` instead of `asyncio.Lock`
2. Consider `threading.RLock` if callbacks may re-enter
3. Use `asyncio.run_coroutine_threadsafe()` for cross-thread async calls
4. See `docs/architecture/CIRCUIT_BREAKER_THREAD_SAFETY.md` for multi-threaded patterns

## Related Patterns

- Circuit Breaker Implementation (`../guides/omnibase-infra-circuit-breaker-implementation.md`) - Circuit breaker with lock patterns
- Error Recovery Patterns (internal knowledge base) - Retry and backoff strategies
- Correlation ID Tracking (`../architecture/omnibase-infra-correlation-id-tracking.md`) - Request tracing across async operations
