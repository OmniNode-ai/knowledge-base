---
type: reference
status: current
date: "2026-09-02"
title: "ADR-001: Graceful Shutdown with Drain Period"
topics: [omnibase-infra, adr, graceful, shutdown]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-001-graceful-shutdown-drain-period.md on 2026-09-02. -->

# ADR-001: Graceful Shutdown with Drain Period

## Status

Accepted

## Date

2025-12-17

## Context

The RuntimeHostProcess is the central coordinator for ONEX infrastructure runtime, managing event bus subscriptions and routing incoming envelopes to protocol handlers. When the process receives a shutdown signal, it must handle the transition from active message processing to a stopped state.

**Problem Statement**: Without graceful shutdown, stopping the runtime host could result in:

1. **In-flight message loss**: Messages currently being processed would be interrupted mid-execution
2. **Data integrity issues**: Partial database transactions or incomplete API calls
3. **Resource leaks**: Handlers not properly releasing connections, file handles, or external resources
4. **Inconsistent state**: Downstream systems receiving partial or corrupted responses

The system needed a mechanism to:
- Stop accepting new messages immediately upon shutdown signal
- Allow currently processing messages to complete
- Enforce a maximum wait time to prevent indefinite hangs
- Provide observability into the drain process

## Decision

We implemented a graceful shutdown mechanism with the following design:

### 1. Configurable Drain Timeout

- **Default**: 30 seconds
- **Valid range**: 1-300 seconds (values outside this range are clamped with a warning)
- **Configuration key**: `drain_timeout_seconds` in the config dict

The range was chosen to balance:
- Minimum of 1 second: Prevents effectively disabling the drain period
- Maximum of 300 seconds (5 minutes): Prevents indefinite hangs while allowing long-running operations to complete

### 2. Polling-Based Completion Detection

The implementation uses a polling approach with 100ms intervals to check if all in-flight messages have completed:

```python
while not await self.shutdown_ready():
    remaining = drain_deadline - loop.time()
    if remaining <= 0:
        # Timeout exceeded - force shutdown
        break
    await asyncio.sleep(min(0.1, remaining))
```

### 3. Lock-Protected Message Counter

A pending message counter tracks in-flight messages with lock protection:

```python
self._pending_message_count: int = 0
self._pending_lock: asyncio.Lock = asyncio.Lock()
```

- Counter is incremented when message processing begins
- Counter is decremented in a `finally` block to ensure decrement even on exceptions
- Lock ensures thread-safe access from concurrent message handlers

### 4. Shutdown Sequence

The stop() method follows this sequence:

1. **Unsubscribe from topics**: Stop receiving new messages immediately
2. **Drain period**: Wait for in-flight messages to complete (up to timeout)
3. **Handler shutdown**: Shutdown handlers by priority order
4. **Close event bus**: Release event bus resources

### 5. Forced Shutdown with Warning

If the drain timeout is exceeded, shutdown proceeds with a warning log that includes:
- Number of pending messages still in flight
- Configured drain timeout value

This ensures the system never hangs indefinitely while providing visibility into potentially lost messages.

## Consequences

### Positive

- **Clean shutdown**: Messages in flight are allowed to complete, preventing data loss
- **Message completion**: Handlers can finish database transactions, API calls, and other operations
- **Observability**: The `pending_message_count` property and `shutdown_ready()` method provide visibility into drain state
- **Configurable behavior**: Operators can tune the drain timeout based on their workload characteristics
- **Bounded wait time**: The timeout prevents indefinite hangs on stuck handlers
- **Structured logging**: Drain duration and final pending count are logged for operational insight

### Negative

- **Potential shutdown delay**: Shutdown may take up to `drain_timeout_seconds` to complete
- **Added complexity**: The pending message tracking adds state management overhead
- **Lock contention**: High-throughput scenarios may see minor contention on the pending lock
- **Potential message loss on timeout**: If drain timeout is exceeded, remaining messages are abandoned

## Alternatives Considered

### asyncio.Event-based Drain Signaling

**Approach**: Use `asyncio.Event` to signal when all messages have completed, allowing instant notification without polling.

```python
# Alternative approach (not chosen)
self._drain_complete = asyncio.Event()

async def _on_message(self, message):
    async with self._pending_lock:
        self._pending_message_count += 1
    try:
        await self._handle_envelope(envelope)
    finally:
        async with self._pending_lock:
            self._pending_message_count -= 1
            if self._pending_message_count == 0:
                self._drain_complete.set()

async def stop(self):
    # ...unsubscribe...
    await asyncio.wait_for(self._drain_complete.wait(), timeout=drain_timeout)
```

**Why polling was chosen instead**:

1. **Simpler state management**: Event-based requires careful handling of edge cases:
   - Event must be cleared when new messages arrive
   - Race condition if message arrives between check and wait
   - Additional state to manage (event object lifecycle)

2. **No practical performance difference**: With 100ms polling intervals and typical message processing times of 10-1000ms, the polling overhead is <1% of total drain time. For example, draining 10 messages taking 50ms each results in 500ms total processing time, where the 100ms polling adds at most 20% overhead in the worst case (single message scenario), but approaches 0% with multiple concurrent messages.

3. **Better timeout handling**: Polling naturally integrates with the timeout check in a single loop, making the code more readable and maintainable.

4. **Debugging clarity**: The polling approach makes it easier to add logging and understand the drain progress during debugging.

5. **Simpler correctness reasoning**: The polling approach has fewer edge cases and is easier to verify as correct.

**Future consideration**: If profiling shows the 100ms polling overhead is problematic in specific scenarios, event-based signaling could be revisited as an optimization.

### Immediate Shutdown (No Drain Period)

**Approach**: Stop immediately without waiting for in-flight messages.

**Why rejected**:

1. **Data loss risk**: Messages mid-processing would be interrupted, potentially causing:
   - Partial database writes
   - Incomplete API transactions
   - Lost acknowledgments to upstream systems

2. **Resource leaks**: Handlers might not release connections properly

3. **Inconsistent state**: Downstream systems could receive partial or corrupted data

4. **Poor operational experience**: No visibility into what was interrupted

### Infinite Drain (No Timeout)

**Approach**: Wait indefinitely for all messages to complete.

**Why rejected**:

1. **Hang risk**: A stuck handler or deadlock would prevent shutdown forever
2. **Poor operational experience**: Operators need predictable shutdown times
3. **Resource consumption**: System resources remain allocated during indefinite wait
4. **No recovery path**: Only option would be process kill, which defeats graceful shutdown

## Implementation Notes

### Key Files

- `src/omnibase_infra/runtime/runtime_host_process.py`: Main implementation

### Configuration

```python
process = RuntimeHostProcess(
    config={
        "drain_timeout_seconds": 60.0,  # Custom drain timeout
    }
)
```

### Monitoring the Drain Process

```python
# Check current in-flight message count (non-locking, for monitoring)
count = process.pending_message_count

# Check if ready for shutdown (locking, for accurate decisions)
ready = await process.shutdown_ready()
```

### Logging

The implementation logs:
- Drain period start (implicit in "Stopping RuntimeHostProcess")
- Drain timeout exceeded (WARNING level with pending count)
- Drain completion (INFO level with duration and final count)

### Health Check Integration

The `health_check()` method exposes drain state for load balancer integration:
- `is_draining`: Boolean indicating active drain period (True during graceful shutdown)
- `pending_message_count`: Number of in-flight messages being processed

Load balancers can use `is_draining=True` to remove the service from rotation
before the container becomes unhealthy, enabling smoother rolling deployments.

### Thread Safety

The `_pending_lock` is an `asyncio.Lock`, appropriate for the async context. The lock is acquired:
- When incrementing the counter (message processing start)
- When decrementing the counter (message processing end)
- When checking `shutdown_ready()` for accurate count

The `pending_message_count` property returns the value without locking for performance in monitoring scenarios where exact accuracy is not critical.

## Future Enhancements

### Prometheus Metrics Emission

The current implementation logs drain duration via structured logging, which can be scraped
by log aggregators. For environments with dedicated metrics infrastructure, consider adding
Prometheus metrics:

```python
# Potential future implementation
from prometheus_client import Histogram, Gauge

drain_duration_histogram = Histogram(
    "runtime_drain_duration_seconds",
    "Time spent draining pending messages during shutdown",
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

pending_message_gauge = Gauge(
    "runtime_pending_message_count",
    "Number of messages currently being processed"
)
```

This enhancement was deferred as the MVP focuses on core functionality, and structured
logging provides sufficient observability for initial deployments. Metrics integration
can be added when the broader metrics infrastructure is established.

## References

- **PR #48**: Implementation pull request
- **ModelLifecycleSubcontract**: Defines lifecycle patterns including shutdown behavior
