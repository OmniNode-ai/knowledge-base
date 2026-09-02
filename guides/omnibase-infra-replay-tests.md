---
type: guide
status: current
date: "2026-09-02"
title: "Replay Tests"
topics: [omnibase-infra, replay, tests]
refs: []
---

<!-- Migrated from omnibase_infra:tests/replay/README.md on 2026-09-02. -->

# Replay Tests

Event replay verification tests for validating reducer determinism, idempotency, and state reconstruction.

## Overview

This test suite validates ONEX reducer replay behavior:

- **Determinism**: Same inputs always produce same outputs
- **Idempotency**: Duplicate events don't cause duplicate side effects
- **State Reconstruction**: State can be rebuilt from event sequence
- **Out-of-Order Handling**: Events processed correctly regardless of order
- **Snapshot + Tail**: State recovery from snapshot plus tail events

## Test Categories

| Test File | Description | Marker |
|-----------|-------------|--------|
| `test_reducer_replay_determinism.py` | Pure function determinism | `unit` |
| `test_idempotent_replay.py` | Duplicate event handling | `unit` |
| `test_state_reconstruction.py` | State rebuild from events | `unit` |
| `test_out_of_order_events.py` | Out-of-order event handling | `unit` |
| `test_snapshot_plus_tail.py` | Snapshot recovery patterns | `unit` |
| `test_no_hidden_state.py` | Hidden state detection | `unit` |
| `test_event_sequence_capture.py` | Event sequence logging | `unit` |

## Running Tests

### Run All Replay Tests

```bash
pytest tests/replay/ -v
```

### Run by Marker

```bash
# All unit tests (replay tests use unit marker)
pytest -m unit tests/replay/ -v
```

### Run Specific Test Files

```bash
# Determinism tests
pytest tests/replay/test_reducer_replay_determinism.py -v

# Idempotency tests
pytest tests/replay/test_idempotent_replay.py -v

# State reconstruction tests
pytest tests/replay/test_state_reconstruction.py -v

# Out-of-order event tests
pytest tests/replay/test_out_of_order_events.py -v

# Snapshot + tail tests
pytest tests/replay/test_snapshot_plus_tail.py -v

# Hidden state detection tests
pytest tests/replay/test_no_hidden_state.py -v

# Event sequence capture tests
pytest tests/replay/test_event_sequence_capture.py -v
```

## Execution Time Estimates

| Test File | Approximate Time |
|-----------|------------------|
| `test_reducer_replay_determinism.py` | ~1s |
| `test_idempotent_replay.py` | ~1s |
| `test_state_reconstruction.py` | ~1s |
| `test_out_of_order_events.py` | ~1s |
| `test_snapshot_plus_tail.py` | ~1s |
| `test_no_hidden_state.py` | ~1s |
| `test_event_sequence_capture.py` | ~1s |

**Total Suite**: ~7-10 seconds

**Note**: Replay tests are fast by design as they test pure reducer logic without I/O.

## Key Concepts

### Reducer Purity

Reducers must be pure functions:
- `reduce(state, event) -> (new_state, intents)`
- No internal mutable state
- No I/O operations
- Deterministic: same inputs = same outputs

### Idempotency Pattern

Idempotency is achieved via `last_processed_event_id`:

1. Each event has a unique `correlation_id`
2. After processing, state tracks `last_processed_event_id`
3. On replay, `state.is_duplicate_event(event_id)` returns `True`
4. Duplicate events return current state unchanged with no intents

### State Reconstruction

State can be reconstructed by replaying all events:

```python
state = initial_state
for event in event_sequence:
    output = reducer.reduce(state, event)
    state = output.result
# state is now fully reconstructed
```

### Snapshot + Tail Pattern

For large event sequences:

1. Take periodic state snapshots
2. Store snapshot with last event position
3. On recovery: load snapshot + replay tail events
4. Reduces startup time vs. full replay

## Test Fixtures (conftest.py)

### Deterministic Generators

- `DeterministicIdGenerator`: Generates reproducible UUIDs
- `DeterministicClock`: Generates reproducible timestamps
- `EventFactory`: Creates deterministic introspection events

### Models

- `EventSequenceEntry`: Single entry in event sequence log
- `EventSequenceLog`: Log for capturing/replaying event sequences

### Fixed Values

- `fixed_node_id`: Fixed UUID for node identification
- `fixed_correlation_id`: Fixed UUID for correlation tracking
- `fixed_timestamp`: Fixed datetime for deterministic tests

## Interpreting Failures

### Determinism Failures

```
AssertionError: Status mismatch: registering != registered
```
- Indicates non-deterministic reducer behavior
- Check for hidden state or external dependencies
- Verify reducer is pure (no side effects)

### Idempotency Failures

```
AssertionError: Duplicate event produced N intents (expected 0)
```
- Indicates duplicate event not detected
- Check `is_duplicate_event()` implementation
- Verify `last_processed_event_id` is updated correctly

### State Reconstruction Failures

```
AssertionError: Reconstructed state differs from expected
```
- Check event ordering
- Verify all events in sequence
- Ensure reducer handles all event types

### Hidden State Failures

```
AssertionError: State contains hidden values not in events
```
- Indicates reducer uses external state
- Check for global variables or closures
- Remove dependencies on system state

## Debugging Tips

1. **Use deterministic generators**: Ensures reproducible test runs
2. **Compare serialized states**: Use `model_dump()` for detailed comparison
3. **Check event ordering**: Out-of-order may affect final state
4. **Verify event completeness**: All state values must derive from events

## Test Architecture

### Pure Reducer Testing Pattern

```python
def test_determinism(reducer, event_factory):
    # Create deterministic event
    event = event_factory.create_event()
    initial_state = ModelRegistrationState()

    # Run twice
    output1 = reducer.reduce(initial_state, event)
    output2 = reducer.reduce(initial_state, event)

    # Must be identical
    assert output1.result == output2.result
    assert output1.intents == output2.intents
```

### Cross-Instance Testing Pattern

```python
def test_cross_instance_determinism(event_factory):
    event = event_factory.create_event()
    initial_state = ModelRegistrationState()

    # Different reducer instances
    reducer1 = RegistrationReducer()
    reducer2 = RegistrationReducer()

    output1 = reducer1.reduce(initial_state, event)
    output2 = reducer2.reduce(initial_state, event)

    # Must produce identical results
    assert output1.result == output2.result
```

## Related Documentation

- ONEX Architecture (`../../docs/architecture/`)
- Reducer Pattern (`../../docs/patterns/`)
