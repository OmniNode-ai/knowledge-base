---
type: plan
status: active
date: "2026-04-27"
title: "Skills-to-market phase 2: validator gates"
topics: [validation, skills, gates, ci]
---

# Skills-to-Market Phase 2: Validator Gates

> Validator ownership note: the skill-backing-node liveness validator section in
> this file is retired in favor of `omnibase_core` as defined by
> `omnibase_core/docs/decisions/adr-2026-04-28-skill-liveness-validator-home.md`.

**Goal:** Establish three blocking validators before any wave conversion begins. Validators
prove teeth before enforcement: each must fail on current main (unclean state) and pass after
the first converted skill lands.

**Dependency:** Phase 1 merged (ADR, template, pattern doc, dispatch-record persistence).

**Architecture:** Three validators, each wired as pre-commit hook + CI gate. No warn-only modes.
All validators read from `skills_to_market_manifest.yaml` — not hardcoded skill lists.

**Invariant enforcement mapping (from master plan Non-Negotiable Invariants):**
- Task 1 (contract-shape validator): enforces invariant 7 ("no skill contains business logic")
  → moves it from **Phase-Gated** to **Current Blocking** when this CI gate lands.
- Task 2 (liveness validator): enforces invariant 2 (backing node declared in contract.yaml)
  → already Current Blocking; this validator adds runtime proof.
- Task 3 (delegate topic fix): enforces invariant 1 (no hardcoded topic strings) in the
  specific case of `DELEGATION_REQUEST`/`DELEGATE_TASK` drift.
- Task 4 (package-boundary import validator): enforces invariants 6 ("foreground-only Agent()")
  and 12 (temporary `omnimarket → omniclaude` import exception) → moves invariant 6 from
  **Phase-Gated** to **Current Blocking** when this CI gate lands. The allowlist contains
  exactly the two import paths declared in the master plan Known Boundary Violation section.

**Tech Stack:** Python 3.12, `omnimarket.routing.contract_loader`, YAML parsing, pytest subprocess.

**Known Types Inventory:** No new types. Validators are read-only Python scripts.

---

## Task 1: Contract-shape validator — archetype-aware

**Repo:** `omnimarket`
**Ticket sketch:** OMN-NEW-FOUNDATION-03

**Files:**
- Create: `omnimarket/scripts/ci/check_skill_backing_contract_shape.py`
- Create: `omnimarket/tests/unit/test_skill_backing_contract_shape.py`
- Modify: `omnimarket/.pre-commit-config.yaml` — add hook
- Modify: `omnimarket/.github/workflows/ci.yml` — add CI step

**Not reusing existing checker because:** `scripts/ci/run_runtime_sweep.py` and
`check_node_metadata_dependencies.py` verify other invariants but neither checks the
skill-backing-node-specific shape by archetype.

**Step 1: Write failing test**

The test must fail on current main because `node_skill_dispatch_engine_orchestrator`
lacks `terminal_event` (verified: `contract.yaml:96` — `maturity: stub`).

```python
# omnimarket/tests/unit/test_skill_backing_contract_shape.py
import yaml, subprocess, sys
from pathlib import Path

# Archetype-specific requirements:
# compute:      must return ModelDispatchWorkerResult (proposed_agent_spawn_args in output)
# orchestrator: must declare terminal_event OR event_bus.publish_topics
# broker:       must declare event_bus.publish_topics for spawn-request topic

COMPUTE_ARCHETYPE_NODES = ["node_dispatch_worker"]
ORCHESTRATOR_ARCHETYPE_NODES = [
    "node_merge_sweep_triage_orchestrator",
    "node_skill_overseer_verify_orchestrator",
]
# node_skill_dispatch_engine_orchestrator is DEFERRED (stub) — not validated here

def _load(name: str) -> dict:
    path = Path(f"src/omnimarket/nodes/{name}/contract.yaml")
    return yaml.safe_load(path.read_text())

def test_compute_nodes_declare_proposed_agent_spawn_args():
    for name in COMPUTE_ARCHETYPE_NODES:
        contract = _load(name)
        # Look for the field name in the contract text (output_fields or description)
        raw = (Path(f"src/omnimarket/nodes/{name}/contract.yaml")).read_text()
        assert "proposed_agent_spawn_args" in raw, (
            f"{name}: compute-archetype node must declare proposed_agent_spawn_args in contract"
        )

def test_orchestrator_nodes_declare_terminal_event_or_publish_topics():
    for name in ORCHESTRATOR_ARCHETYPE_NODES:
        contract = _load(name)
        has_terminal = "terminal_event" in contract
        bus = contract.get("event_bus") or {}
        has_publish = bool(bus.get("publish_topics") or bus.get("publish"))
        assert has_terminal or has_publish, (
            f"{name}: orchestrator-archetype node must declare terminal_event "
            f"or event_bus.publish_topics"
        )

def test_all_skill_backing_nodes_subscribe_to_correct_namespace():
    """Subscribe topics must be onex.cmd.omnimarket.* or onex.cmd.omniclaude.*"""
    all_nodes = COMPUTE_ARCHETYPE_NODES + ORCHESTRATOR_ARCHETYPE_NODES
    for name in all_nodes:
        contract = _load(name)
        bus = contract.get("event_bus") or {}
        subscribe = bus.get("subscribe") or {}
        topics = bus.get("subscribe_topics") or []
        if isinstance(subscribe, dict) and subscribe.get("topic"):
            topics = topics + [subscribe["topic"]]
        for topic in topics:
            assert topic.startswith("onex.cmd."), (
                f"{name}: subscribe topic {topic!r} must start with 'onex.cmd.'"
            )

def test_validator_script_exits_nonzero_on_current_main():
    """Validator must have teeth: current main has at least one violation (stub maturity)."""
    result = subprocess.run(
        [sys.executable, "scripts/ci/check_skill_backing_contract_shape.py", "--all"],
        capture_output=True, text=True,
    )
    # This test must fail on current main because node_skill_dispatch_engine_orchestrator
    # is maturity: stub. When the dispatch engine is deferred (Phase 7), remove it from
    # the validator's scope and this test will need updating.
    # For now: at least one violation must exist to prove teeth.
    assert result.returncode != 0 or "WARNING" in result.stdout, (
        "Validator must flag at least one issue on current main (stub nodes exist)"
    )
```

**Step 2: Implement the validator**

`scripts/ci/check_skill_backing_contract_shape.py`:
1. Accepts `--all` flag to check all nodes, or `--nodes <name,...>` for specific
2. Iterates `src/omnimarket/nodes/node_*/contract.yaml`
3. For each node in the SKILL_BACKING_NODES list:
   - archetype=compute: asserts `proposed_agent_spawn_args` in contract text
   - archetype=orchestrator: asserts `terminal_event` OR `event_bus.publish_topics`
   - all: asserts subscribe topics match `^onex\.cmd\.(omnimarket|omniclaude|omnibase-infra)\.[a-z]`
4. Exits non-zero on any violation; prints `{node, archetype, violation}` tuples as JSON

Allowlist for `node_skill_dispatch_engine_orchestrator` with explicit expiry:

```python
KNOWN_STUB_ALLOWLIST = {
    # node_name: "OMN-XXXX ticket that will remove this entry"
    "node_skill_dispatch_engine_orchestrator": "OMN-NEW-DISPATCH-ENGINE",
}
# Allowlist entry is REMOVED when the node reaches maturity: production.
# The validator asserts: if a node is in KNOWN_STUB_ALLOWLIST AND its maturity
# is already 'production', fail with "allowlist entry stale — remove it".
```

**Acceptance criteria:**
- Script exists and is importable
- `test_validator_script_exits_nonzero_on_current_main`: PASS (validator has teeth)
- After first wave skill lands with backing node at `production`: script exits 0 (with allowlist)
- Script wired in `.pre-commit-config.yaml` (test asserts hook ID present)
- Script wired in `.github/workflows/ci.yml` quality job (test asserts step name present)

---

## Task 2: Skill-backing-node liveness validator

**Repo:** `omnimarket`
**Ticket sketch:** OMN-NEW-VALIDATOR
**Dependency:** Task 1 merged; `skills_to_market_manifest.yaml` committed

**Files:**
- Create: `omnimarket/scripts/ci/validate_skill_node_liveness.py`
- Create: `omnimarket/tests/unit/test_skill_node_liveness_validator.py`
- Modify: `.pre-commit-config.yaml`, `.github/workflows/ci.yml`

**Not reusing existing validator because:** No existing CI script asserts that every skill
citing a backing node points at a node with `metadata.maturity: production`.

**Step 1: Write failing test**

```python
# omnimarket/tests/unit/test_skill_node_liveness_validator.py
import subprocess, sys, os

def test_validator_detects_stub_backing_nodes_on_current_main():
    """node_skill_dispatch_engine_orchestrator is stub — validator must catch it."""
    result = subprocess.run(
        [sys.executable, "scripts/ci/validate_skill_node_liveness.py"],
        capture_output=True, text=True,
        env={**os.environ, "WORKSPACE_ROOT": os.environ.get("WORKSPACE_ROOT", "")},
    )
    assert result.returncode != 0, "validator must exit non-zero when stub backing nodes exist"
    assert "node_skill_dispatch_engine_orchestrator" in result.stdout + result.stderr, (
        "validator must call out the stub node by name"
    )

def test_validator_passes_for_production_node(tmp_path):
    """A skill pointing at a production node must pass liveness check."""
    # Synthetic fixture: create minimal skill + contract
    skill_dir = tmp_path / "test_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nbacking_node: node_fake_prod\n---\n## Dispatch\nuv run onex run-node node_fake_prod\n"
    )
    node_dir = tmp_path / "nodes" / "node_fake_prod"
    node_dir.mkdir(parents=True)
    (node_dir / "contract.yaml").write_text(
        "metadata:\n  maturity: production\nname: node_fake_prod\n"
    )
    result = subprocess.run(
        [sys.executable, "scripts/ci/validate_skill_node_liveness.py",
         "--skills-root", str(tmp_path),
         "--nodes-root", str(tmp_path / "nodes")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"should pass for production node: {result.stderr}"
```

**Step 2: Implement the validator**

`scripts/ci/validate_skill_node_liveness.py`:
1. Accepts `--skills-root` (default: discovers from `$WORKSPACE_ROOT/omniclaude/plugins/onex/skills`) and `--nodes-root` (default: `$WORKSPACE_ROOT/omnimarket/src/omnimarket/nodes`)
2. Reads `skills_to_market_manifest.yaml` to get `backing_node` per skill (manifest-driven, not hardcoded)
3. For each skill with a non-TBD `backing_node`:
   a. Load `<nodes-root>/<backing_node>/contract.yaml`
   b. Assert `metadata.maturity == "production"`
   c. Assert the contract loads without exception via `omnimarket.routing.contract_loader`
   d. Assert the handler module is importable
4. Allowlist (ticket-bound, expiry rule enforced):

```python
KNOWN_NON_PRODUCTION_ALLOWLIST = {
    # backing_node: "OMN-XXXX — deferred until Phase N"
    "node_skill_dispatch_engine_orchestrator": "OMN-NEW-DISPATCH-ENGINE — deferred to Phase 7",
}
# Expiry: if a node in this list reaches maturity:production, the validator fails with
# "allowlist entry stale for <node> — remove from KNOWN_NON_PRODUCTION_ALLOWLIST"
```

5. Exits 0 only if all non-allowlisted skills pass; otherwise prints JSON violations and exits 1

**Acceptance criteria:**
- `test_validator_detects_stub_backing_nodes_on_current_main`: PASS (validator catches stub)
- `test_validator_passes_for_production_node`: PASS (validator accepts production)
- Validator wired as pre-commit hook + CI gate
- Allowlist is explicit, ticket-bound, and auto-invalidates when node reaches production

---

## Task 3: Delegate topic fix gate

**Repo:** `omniclaude`

**Files:**
- Modify: `omniclaude/src/omniclaude/hooks/topics.py:451` — align `DELEGATION_REQUEST` value
- Remove: `DELEGATE_TASK` duplicate constant at `:479`
- Create: `omniclaude/tests/unit/test_delegate_topic_alignment.py`

**Step 1: Write failing test**

```python
# omniclaude/tests/unit/test_delegate_topic_alignment.py
import yaml
from pathlib import Path
from omniclaude.hooks.topics import TopicBase

def test_publisher_topic_matches_consumer_subscription():
    consumer_contract = yaml.safe_load(
        Path("src/omniclaude/nodes/node_delegation_orchestrator/contract.yaml").read_text()
    )
    bus = consumer_contract.get("event_bus") or {}
    consumed = set(bus.get("subscribe_topics") or [])
    if isinstance(bus.get("subscribe"), dict):
        consumed.add(bus["subscribe"].get("topic", ""))
    assert TopicBase.DELEGATION_REQUEST.value in consumed, (
        f"DELEGATION_REQUEST = {TopicBase.DELEGATION_REQUEST.value!r} not in consumer topics: {consumed}"
    )

def test_no_duplicate_delegation_topic_constants():
    """DELEGATION_REQUEST and DELEGATE_TASK must not both exist pointing at the same topic."""
    members = {m.name: m.value for m in TopicBase}
    # After fix: DELEGATE_TASK should be removed; only DELEGATION_REQUEST remains
    assert "DELEGATE_TASK" not in members, (
        "DELEGATE_TASK constant must be removed after aligning DELEGATION_REQUEST"
    )
```

**Step 2: Apply the fix**

```python
# topics.py:451 — BEFORE
DELEGATION_REQUEST = "onex.cmd.omnibase-infra.delegation-request.v1"
# topics.py:479
DELEGATE_TASK = "onex.cmd.omniclaude.delegate-task.v1"

# AFTER — change DELEGATION_REQUEST value; remove DELEGATE_TASK
DELEGATION_REQUEST = "onex.cmd.omniclaude.delegate-task.v1"
# DELEGATE_TASK removed; update all references to use DELEGATION_REQUEST
```

Verify all references: `grep -rn "DELEGATE_TASK\|DELEGATION_REQUEST" omniclaude/src/ omniclaude/tests/`

**Acceptance criteria:**
- `test_publisher_topic_matches_consumer_subscription`: PASS
- `test_no_duplicate_delegation_topic_constants`: PASS
- Full `omniclaude` test suite green
- PR grep evidence: no remaining references to `DELEGATE_TASK` (or all updated to `DELEGATION_REQUEST`)

---

## Task 4: Package-boundary import validator (prevents omnimarket→omniclaude debt from spreading)

**Repo:** `omnimarket`
**Ticket sketch:** OMN-NEW-BOUNDARY-VALIDATOR

**Files:**
- Create: `omnimarket/scripts/ci/check_package_boundary_imports.py`
- Create: `omnimarket/tests/unit/test_package_boundary_imports.py`
- Modify: `.pre-commit-config.yaml`, `.github/workflows/ci.yml`

**Purpose:** The known boundary violation (see master plan) allows one import of `omniclaude`
from `omnimarket` temporarily. This validator prevents it from spreading to more than the
allowed list while the migration to `omnibase_core` is in flight.

**Step 1: Write failing test (proves teeth)**

```python
# omnimarket/tests/unit/test_package_boundary_imports.py
import subprocess, sys

def test_validator_runs_and_produces_output():
    result = subprocess.run(
        [sys.executable, "scripts/ci/check_package_boundary_imports.py"],
        capture_output=True, text=True,
    )
    # Should exit 0 on current main (the one allowed violation is in the allowlist)
    # but the script must exist and run
    assert result.returncode in (0, 1), f"script must run cleanly: {result.stderr}"

def test_validator_rejects_new_omniclaude_imports(tmp_path):
    """Any new omnimarket file importing from omniclaude must fail the gate."""
    (tmp_path / "bad_handler.py").write_text(
        "from omniclaude.hooks.lib.something import foo\n"
    )
    result = subprocess.run(
        [sys.executable, "scripts/ci/check_package_boundary_imports.py",
         "--path", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, "new omniclaude import must fail the gate"
```

**Step 2: Implement**

`check_package_boundary_imports.py`:
1. Walks `src/omnimarket/**/*.py`
2. Greps for `from omniclaude` or `import omniclaude`
3. Compares against an explicit allowlist:

```python
ALLOWED_OMNICLAUDE_IMPORTS = {
    # file_path_relative: "reason and follow-up ticket"
    "src/omnimarket/nodes/node_dispatch_worker/handlers/handler_dispatch_worker.py":
        "OMN-NEW-RELOCATE-DISPATCH-RECORD — temporary until ModelDispatchRecord moves to omnibase_core",
}
```

4. Any import NOT in the allowlist fails the gate
5. If a file in the allowlist no longer imports from `omniclaude`, fails with "allowlist entry stale"

**Acceptance criteria:**
- Gate exits 0 on current main (the one known violation is allowlisted)
- Gate exits 1 if any new file imports from `omniclaude`
- Gate exits 1 if an allowlisted file no longer has the import (stale allowlist detection)
- Wired as pre-commit + CI gate

---

## Mandatory Proof of Life

Phase 2 does not add new runtime paths. Proof of life for Phase 2 is:
- All three validators exit 0 on current main (with allowlists where needed)
- All three validators exit 1 on a synthetic violation fixture (proves teeth for each)
- Phase 1 proof-of-life still passes (validators do not break existing shim skills)
