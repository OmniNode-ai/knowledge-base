---
type: plan
status: completed
date: "2026-05-02"
title: "Fix onex run-node to publish to contract-declared topics"
topics: [cli, contracts, topics, runtime]
---

## Problem Statement

`onex run-node <node_id> --input '{...}'` publishes commands to a hardcoded generic
topic `onex.cmd.platform.run-node.v1` and polls `onex.evt.platform.run-node-response.v1`.
Zero nodes subscribe to these topics. Every message goes to silence; every invocation
times out after 30 seconds.

Meanwhile, every omnimarket/omnibase_core node declares its own command topic in
`contract.yaml` under `event_bus.subscribe_topics` (e.g.
`onex.cmd.omnimarket.duplication-sweep-start.v1`). The runtime auto-wiring
(`omnibase_infra handler_wiring.py`) subscribes handlers to those declared topics.
The runtime is already listening — `run-node` is publishing to the wrong address.

**Fix:** Make `onex run-node` resolve the target node's contract, publish to its
declared command topic, and poll its `terminal_event` topic for the correlated
response. Fail fast if the contract or topics cannot be resolved — do not silently
publish to dead generic topics.

---

## Known Types Inventory

| Type / Function | Location | Purpose |
|---|---|---|
| `_resolve_packaged_contract(node_name)` | `cli_node.py:29` | Resolves node name → `contract.yaml` Path via `onex.nodes` entry points. Raises `click.ClickException`. |
| `_entry_point_module(value)` | `cli_node.py:81` | Extracts importable module path from entry-point value string. |
| `load_dispatch_bus_route(contract_path)` | `dispatch_bus_client.py:84` | Loads contract → `ModelDispatchBusRoute(command_topic, terminal_topic)`. Uses `publish_topics[0]` for command, `terminal_event` for terminal. |
| `_resolve_command_topic(raw)` | `dispatch_bus_client.py:48` | Extracts `publish_topics[0]` or `event_bus.publish_topics[0]` from raw contract dict. |
| `_resolve_terminal_topic(raw)` | `dispatch_bus_client.py:69` | Extracts `terminal_event` (string or dict with `.topic`). |
| `ModelDispatchBusRoute` | `model_dispatch_bus_route.py` | Frozen Pydantic model: `contract_path`, `command_topic`, `terminal_topic`. |
| `TOPIC_CLI_RUN_NODE_CMD` | `constants_event_types.py:63` | Hardcoded `"onex.cmd.platform.run-node.v1"` — the dead topic. |
| `TOPIC_CLI_RUN_NODE_RESPONSE` | `constants_event_types.py:64` | Hardcoded `"onex.evt.platform.run-node-response.v1"` — the dead topic. |
| `discover_external_nodes()` | `discovery_external_nodes.py:28` | Full entry-point scan → `dict[str, DiscoveredNode]`. Heavier than needed here. |
| `load_and_validate_yaml_model()` | `util_safe_yaml_loader.py` | Safe YAML load into `ModelGenericYaml`. |
| `ModelGenericYaml` | `model_generic_yaml.py` | Catch-all Pydantic model for arbitrary YAML. |
| `publish_and_poll()` | `cli_run_node.py:37` | Current function: produces to hardcoded CMD topic, consumes from hardcoded RESPONSE topic, matches by correlation_id. |

---

## Runtime State Inventory

| Topic | Producer | Consumer | Status |
|---|---|---|---|
| `onex.cmd.platform.run-node.v1` | `cli_run_node.py` | **Nothing** | Dead — zero subscribers |
| `onex.evt.platform.run-node-response.v1` | **Nothing** | `cli_run_node.py` | Dead — zero publishers |
| `onex.cmd.omnimarket.<node>-start.v1` | (should be CLI) | Runtime auto-wiring | Live — handlers listening |
| `onex.evt.omnimarket.<node>-completed.v1` | Node handlers | (should be CLI) | Live — handlers publishing |

---

## Task 1: Extract shared contract-to-topics resolver

**Files:**
- NEW: `src/omnibase_core/cli/cli_resolve_contract_topics.py`
- Read-only: `src/omnibase_core/cli/cli_node.py` (reference pattern)
- Read-only: `src/omnibase_core/dispatch/dispatch_bus_client.py` (reference pattern)

**Steps:**

1. Create `cli_resolve_contract_topics.py` with two functions:
   - `resolve_node_contract(node_id: str) -> Path`: Adapts `_resolve_packaged_contract`
     logic from `cli_node.py` but raises `ModelOnexError` instead of `click.ClickException`
     so it is reusable outside click commands. Resolves `node_id` via
     `importlib.metadata.entry_points(group="onex.nodes")` → entry point module →
     `importlib.util.find_spec` → `contract.yaml` path.
   - `resolve_contract_topics(contract_path: Path) -> tuple[str, str]`: Loads the
     contract YAML via `load_and_validate_yaml_model`. Command topic resolution priority:
     (a) explicit `event_bus.command_topic` if present, (b) `subscribe_topics[0]` as
     documented compatibility fallback with stderr warning if multiple subscribe topics
     exist. Terminal topic: `terminal_event` (string or dict with `.topic`). Returns
     `(command_topic, terminal_topic)`. Raises `ModelOnexError` with clear messages
     naming the contract path and missing field on any resolution failure.

2. The command topic resolution differs from `dispatch_bus_client._resolve_command_topic`:
   that function reads `publish_topics` (what the node publishes TO), but `run-node` needs
   `subscribe_topics` (what the node listens ON) because the CLI is the sender, not the
   receiver. New function reads `subscribe_topics[0]`.

3. The terminal topic resolution reuses the same logic as
   `dispatch_bus_client._resolve_terminal_topic`: reads `terminal_event` as string or
   `terminal_event.topic` as dict.

**Acceptance criteria:**
- `resolve_node_contract("node_duplication_sweep")` returns a valid Path ending in
  `contract.yaml` (requires omnimarket installed).
- `resolve_contract_topics(path)` for the duplication_sweep contract returns
  `("onex.cmd.omnimarket.duplication-sweep-start.v1", "onex.evt.omnimarket.duplication-sweep-completed.v1")`.
- Unknown `node_id` raises `ModelOnexError` with a message listing known nodes.
- Missing `subscribe_topics` raises `ModelOnexError` (not silent fallback).
- Missing `terminal_event` raises `ModelOnexError`.

**Verification grade:** Unit test only (no Kafka, no runtime needed).

---

## Task 2: Rewire `publish_and_poll` to accept dynamic topics

**Files:**
- Modify: `src/omnibase_core/cli/cli_run_node.py`

**Steps:**

1. Change `publish_and_poll` signature to accept `command_topic: str` and
   `response_topic: str` instead of using the hardcoded constants. Remove the import
   of `TOPIC_CLI_RUN_NODE_CMD` and `TOPIC_CLI_RUN_NODE_RESPONSE`.

2. Replace `TOPIC_CLI_RUN_NODE_CMD` on line 108 with the `command_topic` parameter.

3. Replace `TOPIC_CLI_RUN_NODE_RESPONSE` on line 96 with the `response_topic` parameter.

4. Update the `run_node` click command to:
   a. Attempt contract resolution: call `resolve_node_contract(node_id)` then
      `resolve_contract_topics(contract_path)`.
   b. If resolution succeeds, use the resolved topics.
   c. If resolution fails (unknown node, missing contract, missing topics), **exit
      non-zero** with a clear error naming the node_id, contract path (if found), and
      missing field. Do NOT fall back to the dead generic topics by default.
   d. Add `--legacy-generic-topics` flag: when explicitly passed, fall back to the
      generic topics with a stderr warning. This is the only path to the old behavior.
   e. Pass the resolved topics into `publish_and_poll`.

5. Add `--verbose` flag to `run_node` command that prints before publishing:
   `node_id`, `contract_path`, `command_topic`, `terminal_topic`, `fallback_used=false/true`.

**Acceptance criteria:**
- `publish_and_poll` no longer imports or references `TOPIC_CLI_RUN_NODE_CMD` /
  `TOPIC_CLI_RUN_NODE_RESPONSE` directly.
- When a node with contract topics is invoked, the producer publishes to the
  contract-resolved command topic and the consumer polls `terminal_event`.
- When contract resolution fails, the CLI **exits non-zero** with a clear error
  (not silent fallback). The error message names the contract path and missing field.
- `--legacy-generic-topics` is the only path to the old dead topics.
- Existing correlation_id matching logic is unchanged.
- The command envelope must match what the runtime auto-wiring deserializes. Add a
  unit test comparing the emitted envelope shape against `ModelDispatchBusCommand`
  (or whatever the runtime handler expects). If the shapes diverge, fix the envelope
  in this task — do not defer.

**Verification grade:** Unit test with mocked Kafka (same pattern as existing
`test_cli_run_node.py`).

---

## Task 3: Update tests for contract-resolved topic routing

**Files:**
- Modify: `tests/unit/cli/test_cli_run_node.py`
- NEW: `tests/unit/cli/test_cli_resolve_contract_topics.py`

**Steps:**

1. **New file `test_cli_resolve_contract_topics.py`:**
   - Test `resolve_node_contract` with a synthetic entry point (mock
     `importlib.metadata.entry_points` to return a fake node pointing at a temp
     directory with a `contract.yaml`).
   - Test `resolve_node_contract` with unknown node_id → `ModelOnexError`.
   - Test `resolve_contract_topics` with a valid contract dict containing
     `event_bus.subscribe_topics` and `terminal_event` → returns correct tuple.
   - Test `resolve_contract_topics` with missing `subscribe_topics` → `ModelOnexError`.
   - Test `resolve_contract_topics` with missing `terminal_event` → `ModelOnexError`.
   - Test `resolve_contract_topics` with `terminal_event` as dict `{topic: "..."}` →
     correct extraction.

2. **Update `test_cli_run_node.py`:**
   - Update `TestPublishAndPoll` tests to pass explicit `command_topic` and
     `response_topic` parameters.
   - Add a test verifying the click command resolves contract topics when available
     (mock the resolver to return specific topics, assert `producer.produce` is called
     with the contract topic, not the generic one).
   - Add a test verifying the fallback path: mock the resolver to raise
     `ModelOnexError`, assert `producer.produce` is called with the generic
     `TOPIC_CLI_RUN_NODE_CMD`.

**Acceptance criteria:**
- All existing tests pass with updated signatures.
- New tests cover: happy path resolution, unknown node, missing topics, fallback.
- `pytest tests/unit/cli/test_cli_run_node.py tests/unit/cli/test_cli_resolve_contract_topics.py -v`
  passes clean.

**Verification grade:** Unit test.

---

## Task 4: Mark generic run-node topics as dead, gate behind --legacy flag

**Files:**
- Modify: `src/omnibase_core/constants/constants_event_types.py`

**Steps:**

1. Add dead-code comments to `TOPIC_CLI_RUN_NODE_CMD` and
   `TOPIC_CLI_RUN_NODE_RESPONSE` constants:
   ```python
   # DEAD: Generic run-node topics. Zero subscribers, zero publishers.
   # Only reachable via --legacy-generic-topics CLI flag. Remove when flag is removed.
   ```

2. Constants remain importable but are only used in the `--legacy-generic-topics`
   code path (Task 2 step 4d). Default CLI path never touches them.

**Acceptance criteria:**
- Default `onex run-node` never imports or uses these constants.
- Only `--legacy-generic-topics` code path references them.
- The deprecation marker cites the real tracker id, not a placeholder.

**Verification grade:** Grep confirmation — `grep TOPIC_CLI_RUN_NODE` shows references
only in the legacy flag handler and the constants file itself.

---

## Task 5: Contract Resolution Proof

**Files:**
- NEW: `tests/integration/cli/test_cli_run_node_contract_resolution.py`

**Steps:**

1. Write an integration test (marker: `@pytest.mark.integration`) that:
   a. Requires `omnimarket` to be installed (skip with message
      `"omnimarket entry point node_duplication_sweep not installed"` if not).
   b. Calls `resolve_node_contract("node_duplication_sweep")`.
   c. Calls `resolve_contract_topics` on the resolved path.
   d. Asserts command topic is `"onex.cmd.omnimarket.duplication-sweep-start.v1"`.
   e. Asserts terminal topic is `"onex.evt.omnimarket.duplication-sweep-completed.v1"`.
   f. Records provenance: `node_id`, `contract_path`, `sha256(contract_file)`,
      `resolved_command_topic`, `resolved_terminal_topic`.
   g. Calls the resolver a second time on the same contract and asserts identical
      output (determinism proof — given pinned contract, resolution is identical).

2. This test proves the full resolution chain: `node_id` → entry point → module →
   `contract.yaml` → YAML parse → topic extraction. It does NOT prove end-to-end
   command→handler→response correlation (that requires Kafka + runtime).

3. Does NOT require Kafka or a running runtime — only that `omnimarket` is pip-installed
   so the entry point is discoverable.

**Acceptance criteria:**
- Test passes when omnimarket is installed.
- Test skips cleanly with named reason when omnimarket is not installed.
- Resolved topics match the actual values in `node_duplication_sweep/contract.yaml`.
- Repeated resolution returns identical topics (determinism).
- Provenance is recorded in test output (contract path + sha256).

**Verification grade:** Integration test (real entry points, real contract file, no
mocks). This is a **contract resolution proof**, not an end-to-end run-node proof.
The correlation_id propagation through runtime terminal events is a separate
verification that requires Kafka + runtime and is tracked as a follow-up.

---

## Task 6: Envelope Compatibility Proof

**Files:**
- NEW: `tests/unit/cli/test_cli_run_node_envelope.py`

**Steps:**

1. Read the envelope shape that `publish_and_poll` serializes (the dict passed to
   `producer.produce`).

2. Read the envelope shape that the runtime auto-wiring deserializes when a message
   arrives on a node's subscribe topic. Check `handler_wiring.py` dispatch callback
   and the handler's expected input model.

3. Write a unit test that constructs the CLI's outbound envelope for a synthetic
   node_id + payload and validates it against the runtime's expected input schema
   (either `ModelDispatchBusCommand` or whatever the wiring callback deserializes).

4. If the shapes diverge, fix the CLI envelope in this task to match what the
   runtime expects.

**Acceptance criteria:**
- Unit test asserts the CLI-produced envelope can be deserialized by the runtime's
  dispatch callback without error.
- If divergence is found, the fix is in this PR (not deferred).

**Verification grade:** Unit test (medium — asserts schema compatibility, no live Kafka).

---

## Adversarial Review (R1–R10)

### R1: Execution correctness
The plan modifies only the CLI client path. The runtime auto-wiring is untouched.
The CLI publishes to the topic the runtime is already listening on — no new wiring
needed on the server side. The correlation_id mechanism is preserved unchanged.

### R2: Replay determinism
State reduction replay is not applicable (CLI tool, not a reducer). However, topic
resolution must be deterministic for a pinned installed package set and contract file.
Given the same `node_id` and contract snapshot, resolver output must be identical.
Task 5 step 1g proves this with a repeated-resolution assertion.

### R3: Ordering guarantees
Single command → single response. No ordering concerns. The consumer uses
`auto.offset.reset=latest` and a unique group_id per invocation, same as today.

### R4: Idempotency
Not changed. Each `run-node` invocation creates a fresh correlation_id (UUID4).
Re-running produces a new command with a new correlation_id.

### R5: Measured vs. estimated
Task 5 is a measured proof: real entry points, real contract file, real YAML parse.
Tasks 1-3 use unit tests with mocks, which is appropriate for the code paths being
tested (Kafka producer/consumer are always mocked in unit tests).

### R6: Topic reconciliation
This is the entire point. Before: CLI → dead generic topic. After: CLI → node's
declared `subscribe_topics[0]`. The fallback path preserves the generic topic for
nodes that lack contract topics (none currently, but backward-compatible).

### R7: Envelope purity
The command envelope format is unchanged: `{correlation_id, node_id, payload, timestamp}`.
The only change is which Kafka topic it is published to. The handler on the receiving
end already expects this envelope format (or can adapt — the `correlation_id` is the
only field the polling consumer cares about matching).

**Risk:** Some handlers may expect a different envelope format (e.g. `ModelDispatchBusCommand`
wrapping). The current CLI sends a plain JSON dict; if the target handler deserializes via
`ModelDispatchBusCommand.model_validate_json`, the shape must match. Task 6 (Envelope
Compatibility Proof) addresses this: it asserts the CLI envelope can be deserialized by
the runtime dispatch callback and fixes any divergence in this PR.

### R8: Proof of Life degradation
Task 5 explicitly tests the full resolution chain against a real installed node.
The integration test fails if entry points, contract files, or topic declarations
change — it acts as a regression guard.

### R9: Consumer health
The CLI consumer uses a unique ephemeral consumer group per invocation
(`onex-run-node-{correlation_id}`). This is unchanged. No consumer group management
concerns.

### R10: Track isolation
All changes are in `omnibase_core` CLI layer only. No changes to `omnimarket`,
`omnibase_infra`, or any runtime/handler code. The runtime does not know or care
that the CLI changed its publish target — it just receives messages on the topic it
already subscribes to.

### Additional adversarial notes

**What if `subscribe_topics` has multiple entries?** Some nodes list multiple subscribe
topics (e.g. `node_pr_review_bot` has both a `-start` and a `-verify-push` topic).
The plan uses `subscribe_topics[0]` which is the command/start topic by convention.
This is correct for the CLI dispatch use case — the first topic is always the
"start this node" command topic. If a node has a non-standard layout, the fallback
to generic topics catches it.

**What about the response path?** The plan polls `terminal_event` for the response.
The terminal event is published by the runtime-synthesized terminal event mechanism
(documented in `CLAUDE.md`). The runtime publishes to the contract's
`terminal_event` topic after handler completion. The CLI consumer subscribes to that
topic and matches by `correlation_id`. The `correlation_id` propagation from command
envelope → handler → terminal event is handled by the runtime — if the runtime
currently propagates it, this works; if not, the CLI will timeout (same as today,
but now for a real reason rather than a dead topic). This is the most likely follow-up
issue if proof-of-life testing reveals timeouts despite correct topic routing.

**What if omnimarket is not installed?** The fallback to generic topics activates.
The CLI emits a stderr warning and publishes to the old dead topics. Behavior is
identical to today — no regression.
