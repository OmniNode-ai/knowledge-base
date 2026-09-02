---
type: guide
status: current
date: "2026-09-02"
title: "PluginCompute Unit Tests"
topics: [omnibase-infra, plugin, compute, unit]
refs: []
---

<!-- Migrated from omnibase_infra:tests/unit/plugins/README.md on 2026-09-02. -->

# PluginCompute Unit Tests

Unit tests for the `PluginComputeBase` abstract base class.

## Current Status

**PluginJsonNormalizer removed** (the tracking ticket): The example `PluginComputeBase` subclass
was migration debt per the canonical architecture (CLAUDE.md, the tracking ticket). It has been
deleted. Canonical compute logic belongs in `NodeCompute` archetypes (contract.yaml +
handler) in omnimarket.

## Test Coverage

### Protocol Conformance (1 test)
- `test_protocol_conformance_with_base_class` — Verify base class conforms to protocol

### Abstract Base Class Behavior (3 tests)
- `test_base_class_is_abstract` — Cannot instantiate base class directly
- `test_execute_method_is_abstract` — Must override execute() method
- `test_validation_hooks_are_optional` — Can use base class without validation hooks

### Validation Hook Execution (3 tests)
- `test_validate_input_called_before_execute` — Hook execution order
- `test_validate_output_called_after_execute` — Hook execution order
- `test_validation_errors_propagate` — Validation exceptions bubble up

### Context Propagation (2 tests)
- `test_context_available_in_execute` — Context parameter in execute()
- `test_context_available_in_validation_hooks` — Context in validation hooks

### ONEX Architecture Compliance (13+ tests)
- See `test_onex_architecture_compliance.py`

## Running Tests

```bash
uv run pytest tests/unit/plugins/ -v
```

## Dependencies

Tests require:
- `pytest` framework
- `omnibase_infra.plugins.plugin_compute_base` (exists — legacy base class, not for new work)
