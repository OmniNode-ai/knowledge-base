---
type: guide
status: current
date: "2026-09-01"
title: "OmniMarket Node Testing"
topics:
  - omnimarket
  - testing
  - onex-runtime
refs: []
---

<!-- Migrated from omnimarket:docs/node-testing.md on 2026-09-01 -->

# Node Testing Pattern

Testing harness for skill-to-node dispatch parity validation.

## Overview

Every ported node must satisfy three properties:

1. **Standalone execution**: `python -m omnimarket.nodes.<node_name> --dry-run` exits 0 or 1 and writes valid JSON to stdout.
2. **Schema parity**: the JSON output is parseable as the node's result model (e.g. `CoverageSweepResult`).
3. **Handler parity**: direct `handler.handle(request)` and subprocess invocation produce structurally equivalent output.

## Test file

`tests/test_skill_dispatch.py` is parametrized over the initial ported nodes:

- `node_coverage_sweep`
- `node_runtime_sweep`
- `node_aislop_sweep`

All tests are marked `@pytest.mark.unit` and run without network or database access.

## Running

```bash
uv run pytest tests/test_skill_dispatch.py -v -m unit
```

## Adding a new node

When porting a new skill to a node, add it to the parameterized list in `test_node_dry_run_exits_and_writes_json` and add a dedicated parity test following the pattern of `test_coverage_sweep_parity`.

Requirements for a node to be harness-compatible:

1. Has a `__main__.py` with a `--dry-run` flag that exits 0 when there are no findings, 1 when findings exist.
2. Writes `result.model_dump_json(indent=2)` to stdout.
3. The result model has a `status` or `findings` field (or both).

## CI gate

The harness runs as part of the standard `pytest -m unit` suite in CI. No separate configuration required.

## Dispatcher route-coverage gate

Every node that subscribes to a command topic must declare a dispatcher route.
A node that subscribes without a dispatcher route silently delivers messages to
the dead-letter queue. This has caused two production incidents (June 9 DLQ
regression; DEL-01 June 12 live finding).

The gate is implemented in `tests/ci/test_dispatcher_route_coverage_fixtures.py`
and runs as part of the `pytest -m unit` suite. It scans every `contract.yaml`
in the omnimarket contract tree and asserts that for every subscribed command
topic (`onex.cmd.*`) the contract declares either `handler_routing` or
`runtime_dispatch`.

### What counts as a dispatcher route

- `handler_routing` block with at least one `handlers` entry, OR
- `runtime_dispatch` block with a `command_topic` field.

`compatibility_publish_topics` are sender-side declarations and are never a
gap; they do not satisfy the gate.

### When adding a node that subscribes to a command topic

1. Add `handler_routing` (preferred) or `runtime_dispatch` to your
   `contract.yaml`.
2. Run the coverage gate locally:

   ```bash
   uv run pytest tests/ci/test_dispatcher_route_coverage_fixtures.py -v -m unit
   ```

3. Do not add an allowlist entry to bypass the gate — fix the contract.

### Real-dispatch-path tests

Handler-isolation tests can pass while the live dispatch path fails. A
real-dispatch-path test registers the handler through the real dispatcher,
emits the command event, and asserts the terminal event is produced.

For delegation nodes, see
`tests/unit/delegation/test_delegation_wiring.py` for the dispatch wiring
pattern. For general nodes, the golden-chain test in `tests/test_golden_chain_*.py`
satisfies this requirement when it uses `EventBusInmemory` with real handler
registration (not a mock).
