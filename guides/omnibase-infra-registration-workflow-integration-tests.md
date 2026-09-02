---
type: guide
status: current
date: "2026-09-02"
title: "Registration Workflow Integration Tests"
topics: [omnibase-infra, registration, workflow, integration]
refs: []
---

<!-- Migrated from omnibase_infra:tests/integration/registration/workflow/README.md on 2026-09-02. -->

# Registration Workflow Integration Tests

**Location**: `tests/integration/registration/workflow/`

This test suite provides comprehensive mocked end-to-end (E2E) tests for the ONEX node registration workflow. All tests run with ZERO real infrastructure, using test doubles for Consul, PostgreSQL, and Kafka.

## Purpose

The workflow tests validate the complete registration lifecycle from node introspection through backend registration, verifying:

- **Architecture separation**: Reducers perform pure computation, Effects handle I/O
- **Introspection protocol**: Nodes emit and respond to introspection events
- **Orchestration order**: Reducer always called before Effect
- **Idempotency**: Duplicate events produce consistent results
- **Determinism**: Same input produces same normalized output
- **Observability**: Proper logging with correlation tracking and secret sanitization

## Test Phases (A0-A6)

### Phase A0: Purity Gate
**File**: `test_workflow_a0_a2.py`

Verifies the fundamental architecture principle that reducers NEVER perform I/O.

| Test | Description |
|------|-------------|
| `test_a0_purity_gate_reducer_no_io` | Reducer emits intents but makes zero Consul/PostgreSQL calls |
| `test_a0_purity_gate_effect_performs_io` | Effect correctly performs I/O operations via mocked backends |
| `test_a0_purity_gate_complete_workflow_with_tracking` | Complete workflow with call order tracking |

### Phase A1: Introspection Publish
**File**: `test_workflow_a0_a2.py`

Validates that nodes correctly emit introspection events via `MixinNodeIntrospection`.

| Test | Description |
|------|-------------|
| `test_a1_introspection_event_structure` | Event contains required fields (node_id, node_type, correlation_id) |
| `test_a1_introspection_event_stable_node_id` | Same node emits consistent node_id across emissions |
| `test_a1_introspection_event_valid_node_types` | All ONEX node types (effect, compute, reducer, orchestrator) supported |
| `test_a1_introspection_event_endpoints_and_metadata` | Event includes endpoints and metadata dicts |

### Phase A2: Two-Way Introspection Loop
**File**: `test_workflow_a0_a2.py`

Verifies the bidirectional introspection protocol where registry requests introspection and nodes respond.

| Test | Description |
|------|-------------|
| `test_a2_registry_requests_introspection` | Registry can publish introspection request |
| `test_a2_node_responds_to_introspection_request` | Node responds with introspection event |
| `test_a2_correlation_id_preserved_in_loop` | Correlation ID preserved throughout request-response |
| `test_a2_multiple_nodes_respond_with_unique_correlation` | Multiple nodes respond independently |

### Phase A3: Orchestrated Dual Registration
**File**: `test_workflow_a3_a4.py`

Validates orchestrated workflow: Reducer computes intents, Effect executes them.

| Test | Description |
|------|-------------|
| `test_a3_orchestrated_dual_registration` | Complete orchestration with call order verification |
| `test_a3_reducer_produces_typed_intents` | Reducer produces properly typed intents for both backends |
| `test_a3_multiple_node_types` | Orchestration works for all ONEX node types |

### Phase A4: Idempotent Replay
**File**: `test_workflow_a3_a4.py`

Ensures replay of identical events produces consistent results with no duplicate registrations.

| Test | Description |
|------|-------------|
| `test_a4_idempotent_replay` | Re-emit identical event, state unchanged |
| `test_a4_reducer_idempotency_with_event_id` | Reducer uses event_id for idempotency detection |
| `test_a4_effect_idempotency_store_tracks_backends` | Effect tracks completed backends per correlation_id |
| `test_a4_different_correlation_ids_processed_independently` | Different correlation IDs processed independently |
| `test_a4_state_immutability_on_replay` | State is immutable and unchanged on replay |

### Phase A5: Normalized Determinism
**File**: `test_workflow_a5_a6.py`

Verifies that given deterministic input, the reducer produces identical normalized output across runs.

| Test | Description |
|------|-------------|
| `test_a5_normalized_determinism_same_input_same_output` | Same input produces same normalized output |
| `test_a5_normalized_determinism_state_transitions` | State transitions are deterministic |
| `test_a5_normalized_determinism_intents` | Intent generation is deterministic |
| `test_a5_normalized_determinism_snapshot_format` | Output has expected snapshot format |

### Phase A6: Observability
**File**: `test_workflow_a5_a6.py`

Validates logging, correlation tracking, and secret sanitization.

| Test | Description |
|------|-------------|
| `test_a6_observability_correlation_id_in_warning_logs` | Correlation ID in log records |
| `test_a6_observability_secrets_redacted` | No sensitive patterns in log messages |
| `test_a6_observability_secrets_not_in_intent_payloads` | Intent payloads are secret-free |
| `test_a6_observability_validation_errors_logged_safely` | Validation errors don't expose secrets |
| `test_a6_observability_structured_log_format` | Logs use structured extra data |
| `test_a6_observability_no_raw_exception_traces_in_logs` | Exception traces don't leak secrets |
| `test_a6_observability_explicit_secret_sanitization` | Explicit verification of secret sanitization |
| `test_a6_observability_error_messages_sanitized` | Error messages and result state are sanitized |
| `test_a6_observability_comprehensive_secret_pattern_coverage` | Pattern detection coverage validation |

## Running the Tests

### Run All Workflow Tests

```bash
# From repository root
pytest tests/integration/registration/workflow/ -v

# With integration marker
pytest tests/integration/registration/workflow/ -v -m integration
```

### Run Specific Phase

```bash
# Run A0-A2 tests (Purity, Introspection, Two-Way Loop)
pytest tests/integration/registration/workflow/test_workflow_a0_a2.py -v

# Run A3-A4 tests (Orchestration, Idempotency)
pytest tests/integration/registration/workflow/test_workflow_a3_a4.py -v

# Run A5-A6 tests (Determinism, Observability)
pytest tests/integration/registration/workflow/test_workflow_a5_a6.py -v
```

### Run Specific Test Class

```bash
# Run only purity gate tests
pytest tests/integration/registration/workflow/test_workflow_a0_a2.py::TestA0PurityGate -v

# Run only observability tests
pytest tests/integration/registration/workflow/test_workflow_a5_a6.py::TestA6Observability -v
```

## Test Dependencies and Fixtures

### Core Fixtures (from `conftest.py`)

| Fixture | Description |
|---------|-------------|
| `registration_reducer` | Fresh `RegistrationReducer` instance |
| `registry_effect` | `NodeRegistryEffect` with test double backends |
| `consul_client` | `StubConsulClient` test double |
| `postgres_adapter` | `StubPostgresAdapter` test double |
| `event_bus` | `InMemoryEventBus` for introspection events |
| `call_tracker` | `CallOrderTracker` for orchestration verification |

### Tracking Fixtures

| Fixture | Description |
|---------|-------------|
| `tracked_reducer` | Reducer wrapper that records calls |
| `tracked_effect` | Effect wrapper that records calls |
| `call_tracker` | Tracks call order (reducer vs effect) |

### Deterministic Fixtures

| Fixture | Description |
|---------|-------------|
| `deterministic_clock` | Controllable clock for reproducible timestamps |
| `uuid_generator` | Deterministic UUID generator for stable snapshots |
| `deterministic_introspection_event_factory` | Creates events with deterministic values |
| `registry_request_factory` | Creates registry requests with deterministic values |

### Log Capture

Tests use pytest's built-in `caplog` fixture (`pytest.LogCaptureFixture`) for log capture and assertion.

```python
def test_observability_logs(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.WARNING):
        # ... test code ...
    assert "correlation_id" in caplog.text
```

### Scenario Fixtures

| Fixture | Description |
|---------|-------------|
| `workflow_context` | Complete context with all components |
| `failure_injector` | Helper for injecting backend failures |

## Test Design Principles

1. **Zero Real Infrastructure**: All tests use test doubles (`StubConsulClient`, `StubPostgresAdapter`, `InMemoryEventBus`)

2. **Deterministic Inputs**: Fixed UUIDs, timestamps, and correlation IDs for reproducibility

3. **Call Count Tracking**: All mock backends track call counts for verification

4. **Correlation ID Tracing**: All tests verify correlation preservation

5. **Purity Verification**: Reducers are verified to have zero I/O calls

6. **Secret Sanitization**: Logs and outputs are checked for sensitive data patterns

## Sensitive Data Patterns

The test suite validates that none of these patterns appear in logs or outputs:

### Field Patterns (SENSITIVE_FIELD_PATTERNS)
- `password`, `passwd`, `pwd`
- `secret`, `api_key`, `apikey`, `api-key`
- `access_token`, `refresh_token`, `auth_token`
- `bearer`, `credential`
- `private_key`, `privatekey`, `encryption_key`, `master_key`
- `client_secret`, `session_token`
- `jwt`, `oauth_token`
- `ssh_key`, `ssl_cert`
- `conn_string`, `connection_string`

### Value Patterns (SENSITIVE_VALUE_PATTERNS)
- `password=`, `secret=`, `api_key=`
- `Bearer `, `Basic `
- `-----BEGIN`, `-----END` (PEM format)
- `AKIA` (AWS access key prefix)
- `sk_live_`, `sk_test_` (Stripe keys)
- `ghp_` (GitHub tokens)
- `xox` (Slack tokens)

### Safe Contexts (Not Flagged)
- `has_password: True` (boolean indicator)
- `password_present: True` (presence check)
- `api_key_length: 32` (length check)
- `secret: [redacted]` (redacted value)
- `password: ***` (masked value)

## Related Documentation

- **Architecture**: `docs/design/DESIGN_TWO_WAY_REGISTRATION_ARCHITECTURE.md`
- **Reducer**: `src/omnibase_infra/nodes/reducers/registration_reducer.py`
- **Effect**: `src/omnibase_infra/nodes/effects/node_registry_effect.py`
- **Test Doubles**: `tests/integration/registration/effect/test_doubles.py`

## Contributing

When adding new tests:

1. Follow the A0-A6 naming convention for consistency
2. Use deterministic fixtures for reproducibility
3. Verify both reducer purity and effect I/O behavior
4. Include correlation ID verification
5. Check for secret sanitization in any new log outputs
6. Update this README with new test descriptions
