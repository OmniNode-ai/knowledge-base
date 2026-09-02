---
type: architecture
status: accepted
date: "2026-09-02"
title: "Compute Plugin Determinism"
topics: [omnibase-infra, compute, plugin, determinism]
refs: []
---

<!-- Migrated from omnibase_infra:docs/plugins/PLUGIN_DETERMINISM.md on 2026-09-02. -->

# Compute Plugin Determinism

> **Status**: Current | **Last Updated**: 2026-04-24

## Overview

All compute plugins implementing `ProtocolPluginCompute` MUST guarantee deterministic behavior. This document defines the specific requirements, testing procedures, and verification criteria for ensuring determinism in compute plugins.

## Core Principle

**Determinism Requirement**: Given the same `input_data` and `context`, a compute plugin MUST always produce the exact same output, regardless of:
- Number of executions
- Object instance identity
- Process boundaries
- Platform or Python implementation
- Concurrent execution
- Call order

## Five Verification Requirements

### 1. Repeatability (100+ Iterations)

**Requirement**: Same input → Same output across 100+ iterations

**What This Means**:
- Plugin must produce bit-for-bit identical outputs for identical inputs
- Test across multiple executions in the same process
- Verify with simple inputs, nested structures, and large datasets
- Edge cases (empty inputs, unicode) must also be repeatable

**Test Pattern**:
```python
def test_repeatability_100_iterations():
    plugin = MyComputePlugin()
    input_data = {"test": "data"}
    context = {"correlation_id": "test-123"}

    # Execute 100 times
    results = [plugin.execute(input_data, context) for _ in range(100)]

    # All results must be identical
    assert all(result == results[0] for result in results)
```

**Common Violations**:
- ❌ Using `random.random()` without explicit seed
- ❌ Accessing `datetime.now()` or `time.time()`
- ❌ Iterating over unsorted sets or dictionaries
- ❌ Using `uuid.uuid4()` for non-deterministic UUIDs
- ❌ Hash randomization without explicit seeds

### 2. Object Identity Independence

**Requirement**: Different instances → Same result

**What This Means**:
- Plugin behavior must not depend on object identity or memory addresses
- Fresh plugin instances must produce identical outputs to reused instances
- Object IDs (`id(obj)`) must not affect results
- Instance variables should be immutable configuration only

**Test Pattern**:
```python
def test_object_identity_independence():
    input_data = {"test": "data"}
    context = {"correlation_id": "test-123"}

    # Create different instances
    plugin1 = MyComputePlugin()
    plugin2 = MyComputePlugin()
    plugin3 = MyComputePlugin()

    result1 = plugin1.execute(input_data, context)
    result2 = plugin2.execute(input_data, context)
    result3 = plugin3.execute(input_data, context)

    # All instances produce identical results
    assert result1 == result2 == result3
```

**Common Violations**:
- ❌ Using `id(self)` in computation logic
- ❌ Mutable instance variables modified during `execute()`
- ❌ Singleton patterns with mutable shared state
- ❌ Class-level mutable default arguments

### 3. Process Boundary Determinism

**Requirement**: Cross-process consistency

**What This Means**:
- Results must be identical across process boundaries
- Fork/spawn/multiprocessing must yield same outputs
- Inter-process communication must preserve determinism
- Serialization/deserialization must not affect results

**Test Pattern**:
```python
import multiprocessing

def test_process_boundary_determinism():
    input_data = {"test": "data"}
    context = {"correlation_id": "test-123"}

    def worker(input_data, context, result_queue):
        plugin = MyComputePlugin()
        result = plugin.execute(input_data, context)
        result_queue.put(result)

    # Execute in multiple processes
    processes = []
    result_queue = multiprocessing.Queue()

    for _ in range(5):
        p = multiprocessing.Process(target=worker, args=(input_data, context, result_queue))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    # Collect results from all processes
    results = [result_queue.get() for _ in range(5)]

    # All process results must be identical
    assert all(result == results[0] for result in results)
```

**Common Violations**:
- ❌ Process ID (`os.getpid()`) affecting computation
- ❌ Global state shared across processes
- ❌ Environment variables influencing results
- ❌ File descriptor or socket operations

### 4. Platform Independence

**Requirement**: Cross-platform consistency

**What This Means**:
- Results must be identical across Python implementations (CPython, PyPy)
- Platform-specific behaviors must be isolated and documented
- Floating-point operations must use consistent precision
- Path separators and locale settings must not affect results

**Test Pattern**:
```python
def test_platform_independence():
    # Use platform-neutral operations
    from decimal import Decimal
    from pathlib import Path

    plugin = MyComputePlugin()
    input_data = {
        "value": "123.456",  # Use string for exact decimal representation
        "path": "data/file.txt",  # Use forward slashes or pathlib
    }
    context = {"correlation_id": "test-platform"}

    result = plugin.execute(input_data, context)

    # Result should be platform-independent
    # (Manual verification across platforms recommended)
```

**Common Violations**:
- ❌ Using `float` for exact decimal math (use `decimal.Decimal`)
- ❌ OS-specific path separators (use `pathlib`)
- ❌ Locale-dependent string sorting
- ❌ Platform-specific hash functions

### 5. Concurrent Execution Safety

**Requirement**: Parallel determinism

**What This Means**:
- Concurrent executions with same input must yield same results
- Thread-safe operation without locks affecting determinism
- Race conditions must not influence outputs
- No shared mutable state between concurrent executions

**Test Pattern**:
```python
import concurrent.futures

def test_concurrent_execution_safety():
    plugin = MyComputePlugin()
    input_data = {"test": "data"}
    context = {"correlation_id": "test-concurrent"}

    # Execute concurrently with 4 threads, 20 total executions
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(plugin.execute, input_data, context)
            for _ in range(20)
        ]
        concurrent_results = [future.result() for future in futures]

    # All concurrent results must be identical
    assert all(result == concurrent_results[0] for result in concurrent_results)
```

**Common Violations**:
- ❌ Shared mutable state modified during execution
- ❌ Non-atomic operations on shared data
- ❌ Thread-local storage affecting results
- ❌ Lock acquisition order affecting computation

## Additional Verification Requirements

### Input Immutability

**Requirement**: MUST NOT modify `input_data` or `context`

**Test Pattern**:
```python
import copy

def test_input_immutability():
    plugin = MyComputePlugin()
    input_data = {"test": "data"}
    context = {"correlation_id": "test-immutable"}

    input_data_original = copy.deepcopy(input_data)
    context_original = copy.deepcopy(context)

    plugin.execute(input_data, context)

    # Inputs must remain unchanged
    assert input_data == input_data_original
    assert context == context_original
```

### State Independence

**Requirement**: MUST NOT maintain mutable state between calls

**Test Pattern**:
```python
def test_state_independence():
    plugin = MyComputePlugin()
    input_data = {"test": "data"}
    context = {"correlation_id": "test-state"}

    # Execute multiple times
    result1 = plugin.execute(input_data, context)
    result2 = plugin.execute(input_data, context)
    result3 = plugin.execute(input_data, context)

    # All results must be identical (no state accumulation)
    assert result1 == result2 == result3
```

### Call Order Independence

**Requirement**: Results must be independent of execution order

**Test Pattern**:
```python
def test_call_order_independence():
    plugin = MyComputePlugin()
    input1 = {"test": "data1"}
    input2 = {"test": "data2"}
    input3 = {"test": "data3"}
    context = {"correlation_id": "test-order"}

    # Execute in different orders
    # Order 1: 1 -> 2 -> 3
    result1_order1 = plugin.execute(input1, context)
    result2_order1 = plugin.execute(input2, context)
    result3_order1 = plugin.execute(input3, context)

    # Order 2: 3 -> 1 -> 2
    result3_order2 = plugin.execute(input3, context)
    result1_order2 = plugin.execute(input1, context)
    result2_order2 = plugin.execute(input2, context)

    # Results must be identical regardless of order
    assert result1_order1 == result1_order2
    assert result2_order1 == result2_order2
    assert result3_order1 == result3_order2
```

## Non-Deterministic Operations to Avoid

### ⚠️ Absolutely Forbidden

| Operation | Why Forbidden | Deterministic Alternative |
|-----------|---------------|---------------------------|
| `random.random()` | Non-deterministic random number generation | Use `random.Random(seed)` with seed from `context` |
| `datetime.now()` | Current time changes | Pass timestamp as input parameter |
| `time.time()` | Current time changes | Pass timestamp as input parameter |
| `uuid.uuid4()` | Random UUID generation | Use deterministic UUID generation or pass UUID as input |
| `os.getpid()` | Process ID varies | Pass process ID as input if needed |
| `id(obj)` | Memory address varies | Use object content, not identity |
| `set` iteration | Unordered, non-deterministic | Convert to sorted list before iteration |
| `hash(obj)` | Hash randomization in Python 3.3+ | Use `hashlib` with explicit algorithm |

### ⚠️ Use With Caution

| Operation | Caution Reason | How to Use Safely |
|-----------|----------------|-------------------|
| `dict` iteration | Ordered in Python 3.7+ but not guaranteed | Explicitly sort keys: `sorted(dict.keys())` |
| `float` arithmetic | Floating-point precision issues | Use `decimal.Decimal` for exact math |
| `json.dumps()` | Key order not guaranteed in all versions | Use `sort_keys=True` parameter |
| `pathlib` operations | Platform-specific separators | Use `as_posix()` for cross-platform paths |
| `str.lower()` / `str.upper()` | Locale-dependent in some cases | Use `str.casefold()` for locale-independent comparison |

## Comprehensive Test Suite

All compute plugins MUST pass the comprehensive determinism test suite:

```python
# tests/unit/plugins/test_plugin_compute_determinism.py

class TestRepeatabilityRequirement:
    """Test Requirement 1: Same input → Same output (100+ iterations)."""

    def test_repeatability_100_iterations_simple_input(self) -> None:
        """Test with simple input."""
        ...

    def test_repeatability_100_iterations_nested_input(self) -> None:
        """Test with nested structures."""
        ...

    def test_repeatability_100_iterations_large_input(self) -> None:
        """Test with large datasets."""
        ...

class TestObjectIdentityIndependence:
    """Test Requirement 2: Different instances → Same result."""

    def test_different_instances_same_result(self) -> None:
        """Test multiple plugin instances."""
        ...

    def test_instance_reuse_vs_fresh_instances(self) -> None:
        """Test reused vs fresh instances."""
        ...

class TestConcurrentExecutionSafety:
    """Test Requirement 5: Parallel determinism."""

    def test_concurrent_execution_4_threads_20_calls(self) -> None:
        """Test basic concurrency."""
        ...

    def test_concurrent_execution_10_threads_50_calls(self) -> None:
        """Test high concurrency."""
        ...

class TestCallOrderIndependence:
    """Test call order independence."""

    def test_determinism_across_different_call_orders(self) -> None:
        """Test different execution orders."""
        ...

class TestInputImmutability:
    """Test input immutability."""

    def test_input_data_not_modified(self) -> None:
        """Test input_data immutability."""
        ...

    def test_context_not_modified(self) -> None:
        """Test context immutability."""
        ...

class TestStateIndependence:
    """Test state independence."""

    def test_no_state_mutation_between_calls(self) -> None:
        """Test no state accumulation."""
        ...
```

## Verification Checklist

Before deploying a compute plugin, verify:

- [ ] Passes all repeatability tests (100+ iterations)
- [ ] Passes object identity independence tests
- [ ] Passes concurrent execution safety tests (20+ parallel calls)
- [ ] Passes call order independence tests
- [ ] Passes input immutability tests
- [ ] Passes state independence tests
- [ ] No usage of forbidden non-deterministic operations
- [ ] Cautious operations use deterministic patterns
- [ ] Edge cases (empty input, unicode, large datasets) are deterministic
- [ ] Documentation clearly states determinism boundaries
- [ ] Code review confirms no side effects or I/O operations

## Example: Deterministic Plugin Implementation

```python
from typing import Any
from omnibase_infra.plugins.plugin_compute_base import PluginComputeBase

class MyDeterministicPlugin(PluginComputeBase):
    """Example deterministic compute plugin.

    This plugin demonstrates proper determinism practices:
    - No I/O operations
    - No external state dependencies
    - Explicit input validation
    - Immutable configuration only
    - Deterministic algorithms
    """

    def __init__(self, max_depth: int = 10):
        """Initialize with immutable configuration.

        Args:
            max_depth: Maximum nesting depth (immutable configuration)
        """
        self.max_depth = max_depth  # Immutable configuration - set once

    def execute(
        self, input_data: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute deterministic computation.

        Args:
            input_data: Input data to process
            context: Execution context

        Returns:
            Computation result with deterministic output
        """
        # Extract values (no modification of input_data)
        values = input_data.get("values", [])

        # Deterministic computation (sorted to ensure order)
        sorted_values = sorted(values)
        sum_values = sum(sorted_values)

        # Return deterministic output
        return {
            "sorted_values": sorted_values,
            "sum": sum_values,
            "count": len(sorted_values),
            "correlation_id": context.get("correlation_id"),
        }

    def validate_input(self, input_data: dict[str, Any]) -> None:
        """Validate input data.

        Args:
            input_data: Input to validate

        Raises:
            ValueError: If validation fails
        """
        if "values" not in input_data:
            raise ValueError("Missing required field: values")

        if not isinstance(input_data["values"], list):
            raise ValueError("Field 'values' must be a list")
```

## Conclusion

Determinism is a **non-negotiable requirement** for all compute plugins. By following these verification requirements and testing patterns, you ensure that your plugins are:

1. **Reliable**: Same inputs always produce same outputs
2. **Testable**: Pure functions are trivially testable
3. **Scalable**: Stateless computation enables horizontal scaling
4. **Maintainable**: No hidden state or side effects
5. **Composable**: Plugins combine without coordination complexity

All compute plugins MUST pass the comprehensive determinism test suite before deployment.
