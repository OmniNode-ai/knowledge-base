---
type: reference
status: current
date: "2026-09-02"
title: "ADR-004: Performance Baseline Thresholds for E2E Tests"
topics: [omnibase-infra, adr, performance, baseline]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-004-performance-baseline-thresholds.md on 2026-09-02. -->

# ADR-004: Performance Baseline Thresholds for E2E Tests

## Status

Accepted

## Date

2025-12-27

## Context

The ONEX 2-way registration pattern E2E tests require performance threshold assertions to ensure the registration flow meets latency requirements. These tests run against remote infrastructure at remote infrastructure server, which introduces network latency that differs significantly from local development environments.

**Problem Statement**: Without documented performance baselines:

1. **Flaky tests**: Thresholds chosen arbitrarily lead to intermittent failures
2. **False positives**: Tests pass locally but fail in CI due to network latency
3. **Unclear expectations**: Developers don't know if a threshold violation indicates a real problem
4. **Maintenance burden**: No guidance on when or how to recalibrate thresholds

The original  requirements assumed local infrastructure with minimal latency. When tests were implemented against production-like remote infrastructure, the thresholds needed recalibration.

## Decision

We established empirically-calibrated performance thresholds with documented rationale, stored in `tests/integration/registration/e2e/performance_utils.py`.

### 1. Target Infrastructure

All thresholds are calibrated for remote services at remote infrastructure server:
- **Redpanda (Kafka)**: Port 19092 (external) / 9092 (Docker internal)
- **PostgreSQL**: Port 5436
- **Consul**: Port 28500

### 2. Network Characteristics (Measured)

Baseline measurements taken December 2025:
- Network RTT to remote host: 10-25ms typical, 50ms worst-case
- Kafka produce acknowledgment: 15-40ms (includes replication)
- PostgreSQL query execution: 5-20ms (simple queries)
- Connection establishment overhead: 20-50ms (first connection)

### 3. Threshold Calculation Formula

```
threshold = (base_operation_time + network_overhead) * safety_margin
```

Where:
- `base_operation_time`: Measured P99 for the operation in isolation
- `network_overhead`: Measured RTT to remote infrastructure
- `safety_margin`: 2x multiplier for production variability (GC pauses, load spikes)

### 4. Chosen Thresholds

| Operation | Threshold | Breakdown |
|-----------|-----------|-----------|
| Introspection Broadcast | 200ms | (10ms serialize + 40ms Kafka + 25ms network) * 2 |
| Registry Processing | 300ms | (30ms consume + 50ms DB + 20ms logic + 25ms network) * 2 |
| Dual Registration | 1000ms | Full flow with aggressive target |
| Heartbeat Overhead | 150ms | (10ms serialize + 40ms Kafka + 25ms network) * 2 |
| Heartbeat Interval | 30s | Industry-standard balance of freshness vs overhead |
| Heartbeat Tolerance | 5s | ~16% of interval for scheduler jitter |

### 5. Environment Adjustment Guidelines

The thresholds are not one-size-fits-all. Documented adjustments:

**Local Development** (all services on localhost):
- 50ms, 100ms, 300ms, 50ms respectively
- No network RTT overhead

**CI/CD Pipeline** (GitHub Actions):
- Use default values (200ms, 300ms, 1000ms)
- Consider 1.5x multiplier for shared infrastructure contention

**Production Monitoring** (stricter SLAs):
- 100ms, 150ms, 500ms respectively
- Assumes dedicated infrastructure with predictable latency

### 6. Calibration Methodology

Documented process for establishing/recalibrating thresholds:

1. **Baseline measurement**: 100 iterations of each operation in isolation
2. **Load testing**: 10 concurrent operations to measure contention
3. **P99 extraction**: Use 99th percentile as base value
4. **Safety margin**: Apply 2x multiplier for production variability
5. **Rounding**: Round to nearest 50ms for cleaner thresholds

### 7. Recalibration Triggers

Documented conditions requiring recalibration:
- Infrastructure changes (new host, different network topology)
- Persistent test failures (>5% failure rate on threshold assertions)
- Performance improvements (after optimization work)
- Adding new operations to the registration flow

## Consequences

### Positive

- **Reduced flakiness**: Thresholds account for network variability, reducing false failures
- **Clear expectations**: Developers understand what each threshold means and why
- **Maintainability**: Documented recalibration process for future changes
- **Environment awareness**: Guidance for adjusting thresholds per environment
- **Traceability**: Linked to  and calibration date for context

### Negative

- **Documentation overhead**: Thresholds require documentation updates when recalibrated
- **Potentially loose thresholds**: 2x safety margin may mask some regressions
- **Remote infrastructure dependency**: Tests require access to remote infrastructure server

### Neutral

- **Not applicable to unit tests**: These thresholds are specifically for E2E integration tests
- **May need per-CI adjustment**: Different CI environments may have different latency characteristics

## Alternatives Considered

### 1. Fixed "Ideal" Thresholds (e.g., 50ms, 100ms)

**Why rejected**:
- Would require local infrastructure, defeating E2E test purpose
- Tests would fail consistently in production-like environments
- No documentation of why values differ from "ideal"

### 2. No Performance Assertions

**Why rejected**:
- Regressions would go undetected until production
- No way to validate SLA compliance during development
- Missing key observability for the registration flow

### 3. Dynamic Threshold Calibration

**Approach**: Run warmup iterations and set thresholds based on observed P99.

**Why rejected**:
- Masks real regressions (threshold adjusts to bad performance)
- Non-deterministic test behavior
- Harder to compare results across runs

### 4. Environment-Specific Threshold Files

**Approach**: Different threshold configurations per environment.

**Why deferred**:
- Current single-environment approach is sufficient for MVP
- Can be added later if multi-environment testing becomes a priority
- Documented adjustment guidelines provide interim solution

## Implementation Notes

### Key Files

- `tests/integration/registration/e2e/performance_utils.py`: Threshold definitions and utilities
- `tests/integration/registration/e2e/test_registration_flow_e2e.py`: E2E tests using thresholds

### Usage Example

```python
from performance_utils import PerformanceThresholds, timed_operation

async with timed_operation(
    "introspection_broadcast",
    threshold_ms=PerformanceThresholds.INTROSPECTION_BROADCAST_MS,
) as timing:
    await node.broadcast_introspection()
timing.assert_passed()
```

### Monitoring Test Performance

The `PerformanceCollector` class aggregates timing results for summary reporting:

```python
collector = PerformanceCollector()
async with collector.time("op1", threshold_ms=200):
    await do_op1()
collector.print_summary()
```

## References

- **PR #101**: Implementation pull request
- **CLAUDE.md (shared)**: Infrastructure topology and service endpoints
- `performance_utils.py`: Full threshold documentation and utilities
