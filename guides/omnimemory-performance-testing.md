---
type: guide
status: current
date: "2026-08-26"
title: "OmniMemory Performance Testing"
topics:
  - omnimemory
  - performance
  - benchmarks
  - testing
refs:
  - guides/omnimemory-pii-handling.md
  - reference/omnimemory-handler-reuse-matrix.md
---

> **Last verified:** 2026-08-26 — migrated from the `omnimemory` repository. Triage verdict `CORRECT_THEN_MIGRATE`. Structure verified against live source: every test class named below (`TestSLAVerification`, `TestVectorSearchPerformance`, `TestPIIDetectionOverhead`, `TestStorageEfficiency`, `TestPIIDetectorPerformance`, `TestModelSerializationPerformance`, `TestConcurrencyPerformance`, `TestStressPerformance`, `TestBenchmarkSummary`, `TestEndToEndPerformance`) exists verbatim in `tests/test_performance.py`, and `benchmark` and `slow` are both declared pytest markers.
>
> **Corrections applied on migration:** every command was written as `poetry run pytest ...`. The project is built and dependency-managed with uv and hatchling — there is no `poetry.lock` and no Poetry usage anywhere in CI — so all sixteen invocations are now `uv run pytest ...`. The CI example likewise installed Poetry pinned "to match `POETRY_VERSION` in `.github/workflows/test.yml`"; no such workflow file exists and no workflow references Poetry, so the example now uses `astral-sh/setup-uv` and `uv sync --locked`, matching what the repository's real CI does.

# Performance Testing Guide

This document describes how to run and interpret performance benchmarks for OmniMemory.

## Table of Contents

- [SLA Targets](#sla-targets)
- [Running Benchmarks](#running-benchmarks)
- [Test Categories](#test-categories)
- [Interpreting Results](#interpreting-results)
- [Baseline Numbers](#baseline-numbers)
- [Troubleshooting](#troubleshooting)

## SLA Targets

OmniMemory has the following documented performance targets:

| Metric | Target | Test Class |
|--------|--------|------------|
| Memory Operations | <100ms (P95) | `TestSLAVerification` |
| Throughput | 1M+ ops/hour | `TestSLAVerification` |
| Vector Search | <50ms | `TestVectorSearchPerformance` |
| Bulk Operations | >10K records/sec | `TestSLAVerification` |
| PII Detection Overhead | <10ms | `TestPIIDetectionOverhead` |
| Storage Efficiency | <10MB per 100K records | `TestStorageEfficiency` |

## Running Benchmarks

### Quick Performance Check

Run the quick SLA validation (recommended for CI/CD):

```bash
# Quick check of all SLA targets
uv run pytest tests/test_performance.py::TestBenchmarkSummary -v -s

# Run all benchmark tests (excluding slow tests)
uv run pytest tests/test_performance.py -m "benchmark and not slow" -v -s
```

### Full Benchmark Suite

Run the complete benchmark suite including slow tests:

```bash
# Full suite with timing output
uv run pytest tests/test_performance.py -v -s

# Include slow tests (stress tests and extended benchmarks)
uv run pytest tests/test_performance.py -v -s -m "benchmark"

# Only slow tests
uv run pytest tests/test_performance.py -v -s -m "slow"
```

### Specific Test Categories

```bash
# PII detection performance only
uv run pytest tests/test_performance.py::TestPIIDetectorPerformance -v -s
uv run pytest tests/test_performance.py::TestPIIDetectionOverhead -v -s

# Model serialization performance
uv run pytest tests/test_performance.py::TestModelSerializationPerformance -v -s

# Concurrency performance
uv run pytest tests/test_performance.py::TestConcurrencyPerformance -v -s

# SLA verification tests
uv run pytest tests/test_performance.py::TestSLAVerification -v -s

# Vector search simulation
uv run pytest tests/test_performance.py::TestVectorSearchPerformance -v -s

# Storage efficiency
uv run pytest tests/test_performance.py::TestStorageEfficiency -v -s

# End-to-end workflow tests
uv run pytest tests/test_performance.py::TestEndToEndPerformance -v -s
```

### Running with Coverage

```bash
# Run benchmarks with coverage (note: coverage may slightly affect timing)
uv run pytest tests/test_performance.py -v -s --cov=src/omnimemory --cov-report=term-missing
```

## Test Categories

### 1. PII Detection Performance (`TestPIIDetectorPerformance`, `TestPIIDetectionOverhead`)

Tests PII detection speed and overhead:

- **50KB text scan**: Must complete in <100ms
- **Clean text scan**: Must complete in <50ms (no PII to process)
- **Throughput**: At least 10 scans/second for 10KB documents
- **Overhead**: PII detection must add <10ms to operations
- **P95 Response**: <10ms for typical 5KB content

### 2. Model Serialization (`TestModelSerializationPerformance`)

Tests Pydantic model serialization/deserialization:

- **Serialization**: <1ms per item
- **Deserialization**: <1ms per item
- **JSON roundtrip**: <2ms per item
- **Batch throughput**: >10K items/second

### 3. Concurrency Performance (`TestConcurrencyPerformance`)

Tests async concurrency primitives:

- **FairSemaphore acquisition**: <1ms overhead per cycle
- **PriorityLock acquisition**: <2ms overhead per cycle
- **Concurrent throughput**: >500 ops/second under contention
- **Statistics overhead**: <1ms for stats retrieval

### 4. SLA Verification (`TestSLAVerification`)

Validates documented SLA targets:

- **P95 Memory Operations**: <100ms
- **Hourly Throughput**: >1M operations (extrapolated from sample)
- **Bulk Operations**: >10K records/second at various batch sizes

### 5. Storage Efficiency (`TestStorageEfficiency`)

Tests memory footprint and storage overhead:

- **100K records footprint**: <10MB serialized
- **Content overhead**: <3x JSON formatting overhead

### 6. Vector Search Simulation (`TestVectorSearchPerformance`)

Simulates vector database operations:

- **Cosine similarity computation**: <50ms for 1000 vectors
- **Vector preprocessing**: <50ms per 100 vectors
- **Dimensions tested**: 384, 768, 1536 (common embedding sizes)

### 7. End-to-End Workflows (`TestEndToEndPerformance`)

Tests complete memory operation workflows:

- **Full workflow P95**: <100ms (create + PII scan + serialize + deserialize)
- **Concurrent workflows**: <150ms P95 under load

### 8. Stress Tests (`TestStressPerformance`)

Edge case and boundary condition tests:

- **Max text length PII scan**: <200ms for 50KB
- **Large batch operations**: >10K items/second for 10K items

## Interpreting Results

### Understanding Percentile Metrics

The tests use percentile metrics to measure consistent performance:

- **P50 (median)**: 50% of requests complete faster than this
- **P90**: 90% of requests complete faster than this
- **P95**: 95% of requests complete faster than this (our primary SLA metric)
- **P99**: 99% of requests complete faster than this

### Sample Output

```
Memory Operations SLA Report:
  P50: 1.23ms
  P90: 2.15ms
  P95: 2.87ms (target: <100ms) PASS
  P99: 4.12ms
  Mean: 1.45ms
```

### SLA Summary Report

The quick check test produces a summary like:

```
============================================================
SLA TARGETS QUICK CHECK SUMMARY
============================================================
  Memory ops <100ms: 1.23ms [PASS]
  PII detection <10ms: 0.89ms [PASS]
  Bulk ops >10K/sec: 45123/sec [PASS]
  Serialization <1ms: 0.0234ms [PASS]
============================================================
Overall: ALL PASSED
============================================================
```

### What to Look For

1. **All SLA targets should PASS** - any FAIL indicates a regression
2. **P95 values should have headroom** - if P95 is 90ms for a 100ms target, there's little margin
3. **Throughput numbers should be stable** - significant variance may indicate system issues
4. **Mean vs P95 gap** - large gaps indicate outliers that should be investigated

## Baseline Numbers

These are typical baseline performance numbers on reference hardware:

### Reference System
- CPU: Modern multi-core processor (2020+)
- Memory: 16GB+ RAM
- Storage: SSD
- Python: 3.12+
- No significant background load

### Typical Results

| Metric | Typical Value | Target | Variance |
|--------|--------------|--------|----------|
| Memory ops P95 | 2-5ms | <100ms | +/- 50% |
| PII detection (5KB) | 0.5-2ms | <10ms | +/- 30% |
| Serialization | 0.01-0.05ms | <1ms | +/- 50% |
| Bulk ops/sec | 30K-60K | >10K | +/- 40% |
| Vector similarity (768d, 1000 vectors) | 10-30ms | <50ms | +/- 30% |

### Acceptable Variance

- **Normal variance**: +/- 30% from baseline is acceptable
- **Environment variance**: CI/CD may show +50% compared to local development
- **Load impact**: Running under system load may show +100% or more

## Troubleshooting

### Tests Failing or Running Slow

1. **Check system load**: Close other applications, check for background processes
2. **Run warmup first**: Some tests include warmup iterations, but cold caches can affect first runs
3. **Check available memory**: Memory pressure can cause significant slowdowns
4. **Verify Python version**: the project requires Python 3.12+

### Inconsistent Results

1. **Run multiple times**: Take the median of 3+ runs
2. **Check for thermal throttling**: Long-running tests may trigger CPU throttling
3. **Disable power saving**: Ensure CPU is running at full speed
4. **Use `time.perf_counter()`**: All tests use high-resolution timers

### Common Issues

**Issue**: PII detection tests fail on clean text
```
Solution: Clean text should scan faster. Check if regex patterns have regressions.
```

**Issue**: Bulk operations below 10K/sec
```
Solution: Check for memory pressure. Large batch tests allocate significant memory.
```

**Issue**: Concurrent tests timeout
```
Solution: Check async event loop configuration. Ensure pytest-asyncio is configured correctly.
```

**Issue**: Vector search simulation slow
```
Solution: These tests use pure Python math. Consider numpy for production vector operations.
```

## CI/CD Integration

### Recommended CI Configuration

```yaml
# GitHub Actions example
performance-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.12'
    - name: Install uv
      uses: astral-sh/setup-uv@v7
    - name: Install dependencies
      run: uv sync --locked --group dev
    - name: Run performance benchmarks
      run: |
        uv run pytest tests/test_performance.py::TestBenchmarkSummary -v -s
        uv run pytest tests/test_performance.py -m "benchmark and not slow" -v -s
```

### Exit Codes

- `0`: All tests passed, SLA targets met
- `1`: One or more tests failed, investigate immediately
- `2`: Test collection error, check test configuration

## Contributing

When adding new features to OmniMemory:

1. **Add corresponding benchmarks** in `tests/test_performance.py`
2. **Document SLA targets** for any new operations
3. **Run full benchmark suite** before submitting PR
4. **Include baseline numbers** in PR description

### Adding New Benchmarks

```python
@pytest.mark.benchmark
def test_new_feature_performance(self) -> None:
    """
    Benchmark: Description of what's being tested.

    Target: <Xms for Y operation
    """
    measurements: List[float] = []

    for _ in range(100):  # Sufficient iterations for statistical significance
        start = time.perf_counter()
        # ... operation under test ...
        elapsed_ms = (time.perf_counter() - start) * 1000
        measurements.append(elapsed_ms)

    calc = PercentileCalculator(measurements)

    assert calc.p95 < TARGET_MS, (
        f"Feature P95={calc.p95:.2f}ms exceeds {TARGET_MS}ms target"
    )
```

---

For questions or issues with performance testing, open an issue on the `omnimemory` repository.
