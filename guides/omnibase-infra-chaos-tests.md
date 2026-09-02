---
type: guide
status: current
date: "2026-09-02"
title: "Chaos Tests"
topics: [omnibase-infra, chaos, tests]
refs: []
---

<!-- Migrated from omnibase_infra:tests/chaos/README.md on 2026-09-02. -->

# Chaos Tests

Chaos engineering tests for validating system resilience under failure conditions.

## Overview

This test suite validates ONEX infrastructure behavior under chaotic conditions including:

- **Handler Failures**: Random failures during handler processing
- **Timeout Scenarios**: Operations exceeding configured time limits
- **Network Partitions**: Simulated connectivity issues
- **Partial Failures**: Some effects succeed while others fail
- **Recovery Mechanisms**: Circuit breaker, DLQ, restart/resume

## Test Categories

| Category | Description | Marker |
|----------|-------------|--------|
| **Handler Failures** | Failures at pre/mid/post execution points | `chaos` |
| **Timeouts** | Timeout detection, handling, and cleanup | `chaos`, `slow` |
| **Network Partitions** | Connectivity issues and reconnection | `chaos` |
| **Partial Failures** | Rollback and compensation patterns | `chaos` |
| **Circuit Breaker** | Circuit breaker state transitions | `chaos` |
| **DLQ Recovery** | Dead letter queue processing | `chaos` |
| **Data Integrity** | At-least-once, deduplication, correlation | `chaos` |

## Running Tests

### Run All Chaos Tests

```bash
pytest tests/chaos/ -v
```

### Run by Marker

```bash
# All chaos tests
pytest -m chaos -v

# Exclude slow tests (faster CI runs)
pytest -m "chaos and not slow" -v

# Only slow tests
pytest -m "chaos and slow" -v
```

### Run Specific Test Files

```bash
# Handler failure tests
pytest tests/chaos/test_chaos_handler_failures.py -v

# Timeout tests (includes slow tests)
pytest tests/chaos/test_chaos_timeouts.py -v

# Network partition tests
pytest tests/chaos/test_chaos_network_partitions.py -v

# Partial failure tests
pytest tests/chaos/test_chaos_partial_failures.py -v

# Circuit breaker recovery
pytest tests/chaos/test_recovery_circuit_breaker.py -v

# DLQ recovery
pytest tests/chaos/test_recovery_dlq.py -v

# Restart/resume recovery
pytest tests/chaos/test_recovery_restart_resume.py -v

# Data integrity tests
pytest tests/chaos/test_data_integrity_at_least_once.py -v
pytest tests/chaos/test_data_integrity_deduplication.py -v
pytest tests/chaos/test_data_integrity_correlation.py -v
```

## Execution Time Estimates

| Test File | Approximate Time | Has Slow Tests |
|-----------|------------------|----------------|
| `test_chaos_handler_failures.py` | ~2s | No |
| `test_chaos_timeouts.py` | ~10s | Yes (0.5s delays) |
| `test_chaos_network_partitions.py` | ~3s | No |
| `test_chaos_partial_failures.py` | ~2s | No |
| `test_recovery_circuit_breaker.py` | ~3s | No (20ms delays) |
| `test_recovery_dlq.py` | ~2s | No |
| `test_recovery_restart_resume.py` | ~2s | No |
| `test_data_integrity_*.py` | ~3s each | No |

**Total Suite**: ~25-30 seconds (full), ~15-20 seconds (excluding slow)

## Slow Test Markers

Tests marked with `@pytest.mark.slow` have significant latency injection:

- `test_operation_exceeds_timeout` - 0.5s delay for timeout simulation
- `test_timeout_includes_operation_name` - 0.5s delay
- `test_timeout_includes_correlation_id` - 0.5s delay
- `test_timeout_does_not_prevent_retry` - 0.5s delay
- `test_concurrent_timeouts_are_independent` - Multiple 0.5s delays
- `test_backend_not_called_after_timeout` - 0.5s delay
- `test_executor_state_consistent_after_timeout` - 0.5s delay
- `test_timeout_after_idempotency_records_attempt` - 0.5s delay
- `test_timeout_counter_tracks_all_timeouts` - Multiple 0.5s delays

## Interpreting Failures

### Common Failure Patterns

**Timeout Test Failures**:
```
InfraTimeoutError: Operation 'xyz' exceeded timeout of 0.1s
```
- Expected behavior when testing timeout detection
- Verify error includes operation name and correlation_id
- Check that cleanup occurs properly after timeout

**Circuit Breaker Failures**:
```
InfraUnavailableError: Circuit breaker open - service temporarily unavailable
```
- Expected when failure threshold exceeded
- Verify circuit opens after configured failures
- Check that circuit transitions to half-open after reset timeout

**Network Partition Failures**:
```
InfraConnectionError: network partition active
```
- Expected during partition simulation
- Verify reconnection after partition heals
- Check buffered messages are delivered after reconnection

**DLQ Test Failures**:
```
DLQError: Message moved to DLQ after N retries
```
- Expected for permanently failing messages
- Verify DLQ entry contains original message and error context
- Check correlation_id is preserved in DLQ entry

### Debugging Tips

1. **Check fixture state**: Ensure chaos injector is configured as expected
2. **Verify mock behavior**: Check that AsyncMock is properly configured
3. **Review logs**: Look for correlation_id in error messages for tracing
4. **Check idempotency**: Ensure idempotency store is clean between tests

## Test Architecture

### Fixtures (conftest.py)

- `ChaosConfig`: Configuration for failure/timeout/latency injection
- `FailureInjector`: Utility for injecting failures into operations
- `NetworkPartitionSimulator`: Simulates network connectivity issues
- `ChaosEffectExecutor`: Effect executor with chaos injection capability
- `MockEventBusWithPartition`: Mock event bus with partition simulation

### Error Types Used

- `InfraConnectionError`: Network/connection failures
- `InfraTimeoutError`: Operation timeout
- `InfraUnavailableError`: Service unavailable (circuit breaker open)
- `ValueError`: Generic chaos injection failure

## Related Documentation

- Error Handling Patterns
- Error Recovery Patterns
- Circuit Breaker Implementation
- Retry Backoff Compensation Strategy

## CI Optimization

Run only fast tests (excludes slow markers):

```bash
pytest tests/chaos/ -m "not slow" -v
```

Run only chaos tests without slow tests:

```bash
pytest -m "chaos and not slow" -v
```

Run slow tests separately (useful for nightly builds):

```bash
pytest tests/chaos/ -m "slow" -v
```
