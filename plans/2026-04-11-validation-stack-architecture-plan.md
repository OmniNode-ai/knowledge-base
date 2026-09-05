---
type: plan
status: active
date: "2026-04-11"
title: "Validation stack architecture — implementation plan"
topics: [validation, ci, architecture, gates]
---

# Validation Stack Architecture — Implementation Plan

**Design doc:** `docs/design/validation-stack-architecture.md`
**Extends:** `docs/plans/2026-04-11-vacuous-green-prevention-gate-plan.md` (vggp plan, 16 tasks — do NOT re-implement those tasks here)
**Status:** Ready for ticketization

---

## Scope

This plan covers the validation stack components NOT already in the vggp plan:
- §2: Golden chain coverage linter + exemption mechanism
- §3: Projection table policy + `projection.yaml` convention + migration runner
- §8: Vacuous-green pattern detector (static CI script)
- §7: DoD enforcement meta-validation
- §9: Alerting runbook
- §10: Retroactive remediation priority filter + wave ordering

The vggp plan's 16 tasks (Layers 1–3, dogfood, retroactive audit) are the implementation plan for §4, §5, §6, §10 (base). This plan adds the remaining layers.

---

## Wave Ordering

| Wave | Tasks | Prerequisite |
|------|-------|-------------|
| Wave 0 | Fix confirmed FAIL: _dispatch_ci_watch | None (blocking) |
| Wave 1 | vggp plan Waves 1–2 (hostile_reviewer + pre-commit hook wiring) | Wave 0 |
| Wave 2 | Golden chain coverage linter (§2) | vggp Wave 1 |
| Wave 3 | Projection table policy + projection.yaml convention (§3) | Wave 2 |
| Wave 4 | Vacuous-green static detector in CI (§8) | vggp Wave 2 (CI templates exist) |
| Wave 5 | DoD meta-validation (§7 extension) | already merged |
| Wave 6 | Alerting runbook (§9) | Wave 1 (alert mechanism exists via slack_gate) |
| Wave 7 | Retroactive remediation epic + sub-tickets (§10 priority filter) | vggp Tasks 11–12 |
| Wave 8 | Cross-domain integration sweep (Level 4, weekly schedule) | Wave 3 |

---

## Task: Fix _dispatch_ci_watch (Wave 0, blocking)

**File:** `omnimarket/src/omnimarket/nodes/node_overnight/handlers/handler_overnight.py`

**Current state:**
```python
def _dispatch_ci_watch(command, contract):
    if not command.dry_run:
        logger.warning("[OVERNIGHT] ci_watch dispatched without PR context — skipping")
    return True, None  # Always reports success regardless of mode
```

**Required fix (two options — team-lead decides):**

Option A: Implement real CI watch dispatch (publish to Kafka, poll for result)
Option B: Mark as explicit SKIP with recorded reason

Option B template:
```python
def _dispatch_ci_watch(command, contract):
    # Explicit skip: ci_watch requires a PR context that is not available
    # in standalone overnight sessions. This phase is intentionally skipped
    # when no PR context is provided. This is NOT a success — it is a skip.
    if not contract.get("pr_number"):
        logger.info("[OVERNIGHT] ci_watch: no PR context — phase SKIPPED (not SUCCESS)")
        return False, "SKIPPED: no PR context"
    # ... real implementation if PR context available
```

**Acceptance criteria:**
- `_dispatch_ci_watch` no longer returns `(True, None)` unconditionally
- The phase outcome is either a real CI result or an explicit SKIP with a non-empty reason
- A `@pytest.mark.integration` test calls `dispatch_phases=True` and asserts the phase outcome is not `(True, None)` when no PR context is provided

---

## Task: Add overnight_sessions projection table (Wave 0, blocking)

**Required for:** Golden chain coverage linter to have a chain to validate for overnight topics.

**Projection schema:**

```yaml
# omnimarket/src/omnimarket/nodes/node_overnight/projection.yaml
table: overnight_sessions
idempotency_key: correlation_id
schema_fields:
  - name: session_id
    type: TEXT NOT NULL
  - name: phase
    type: TEXT NOT NULL
  - name: outcome
    type: TEXT  # NULL if phase not yet complete
  - name: phase_dispatcher
    type: TEXT NOT NULL
  - name: dry_run
    type: BOOLEAN NOT NULL DEFAULT false
```

**Migration:** Generate via `generate_projection_migration.py` (new script — see Wave 3).

**Golden chain entry:** Add `overnight` chain to `chain_registry.py`:
```python
ModelChainDefinition(
    name="overnight",
    head_topic="onex.evt.omnimarket.overnight.phase-complete.v1",
    tail_table="overnight_sessions",
    lookup_column="correlation_id",
    lookup_fixture_key="correlation_id",
    fixture_template={
        "session_id": "golden-chain-test-overnight-session",
        "phase": "ci_watch",
        "outcome": "skipped",
        "phase_dispatcher": "_dispatch_ci_watch",
    },
    assertions=(
        ModelChainAssertion(field="session_id", op="eq", expected="golden-chain-test-overnight-session"),
        ModelChainAssertion(field="phase_dispatcher", op="eq", expected="_dispatch_ci_watch"),
    ),
)
```

---

## Task: Golden chain coverage linter (Wave 2)

**File to create:** `omnimarket/scripts/validate_golden_chain_coverage.py`

**Logic:**
1. Walk all repos under the workspace root for `contract.yaml` files
2. For each `event_bus.publish_topics` entry:
   - Check if the topic exists in `chain_registry.py` chains
   - If yes: PASS
   - If no AND the contract has `golden_chain_exempt: true` for that topic: PASS (log exempt reason)
   - If no AND no exemption: check `suspect_topics.yaml` for the topic
   - If in `suspect_topics.yaml`: WARNING (not fail)
   - If neither chain nor exemption nor suspect_topics: FAIL

**New files:**
- `omnimarket/scripts/validate_golden_chain_coverage.py`
- `omnimarket/config/suspect_topics.yaml` (initial: populate with all current un-chained topics)

**CI wiring:** Add to omnimarket CI quality gate as a new step:
```yaml
- name: Validate golden chain coverage
  run: uv run python scripts/validate_golden_chain_coverage.py --root "$WORKSPACE_ROOT"
```

**Acceptance criteria:**
- All 5 existing chains pass
- overnight topic fails until the overnight chain is added (or suspect_topics.yaml populated)
- Script exits 0 on PASS, exits 1 on FAIL
- Script exits 0 on WARNING (warnings are surfaced but do not block)

---

## Task: Projection table policy infrastructure (Wave 3)

**New files:**
- `omnimarket/scripts/generate_projection_migration.py` — reads `projection.yaml`, generates Alembic migration
- `omnimarket/config/projection_registry.yaml` — master list of all projection tables (for sweep assertion)

**`projection_registry.yaml` format:**
```yaml
projections:
  - table: agent_routing_decisions
    topic: onex.evt.omniclaude.routing-decision.v1
    chain: registration
    node: node_golden_chain_payload_compute
  - table: overnight_sessions
    topic: onex.evt.omnimarket.overnight.phase-complete.v1
    chain: overnight
    node: node_overnight
  # ... one entry per projection table
```

**Migration runner:** `generate_projection_migration.py --node node_overnight --projection-yaml src/omnimarket/nodes/node_overnight/projection.yaml`

Output: `alembic/versions/{timestamp}_add_{table}_projection.py`

**Acceptance criteria:**
- Script reads `projection.yaml` and generates valid Alembic migration
- Generated migration includes the schema fields declared in `projection.yaml`
- `projection_registry.yaml` is the authoritative list read by the Level 5 standing sweep

---

## Task: Vacuous-green static detector in CI (Wave 4)

**File to create:** `omnimarket/scripts/detect_vacuous_green.py`

**Logic:**
- Accept a list of changed Python files (from `git diff --name-only`)
- For each file matching `Handler*.py`, parse all `handle*` method bodies using `ast`
- For each method body, check for call sites from the side-effect set (see §8)
- If no side-effect calls found AND no `# vacuous-green-ok:` comment: emit WARNING annotation
- Exit 0 (warnings do not block)

**AST-based detection (more robust than regex):**
```python
import ast

SIDE_EFFECT_CALLS = {
    "publish",           # event_bus.publish
    "execute",           # asyncpg cursor.execute
    "post",              # httpx / aiohttp post
    "run",               # subprocess.run
    "create_subprocess_exec",
}
```

**CI step:**
```yaml
- name: Vacuous-green detector (warning only)
  run: |
    CHANGED=$(git diff --name-only ${{ github.event.pull_request.base.sha }} ${{ github.event.pull_request.head.sha }} | grep 'Handler.*\.py$' || true)
    if [[ -n "$CHANGED" ]]; then
      uv run python scripts/detect_vacuous_green.py --files "$CHANGED"
    fi
```

**Acceptance criteria:**
- Detects `_dispatch_ci_watch` pattern (returns without side-effect calls)
- Does NOT detect `_handle_dict` shim (delegates to `_handle_typed` — helper delegation)
- Exits 0 for handlers with `# vacuous-green-ok:` comment with non-empty reason
- Exits 0 always (warnings only)

---

## Task: DoD meta-validation extension (Wave 5)

**File to modify:** The Done-state hook (locate in omniclaude hooks).

**Extension:** Add meta-validation check:

```python
def check_dod_meta_validation(state: ModelDodVerifyState, contract: ModelTicketContract) -> None:
    """Alert if dod_verify returned SKIPPED but contract has evidence fields."""
    if state.status != EnumDodVerifyStatus.SKIPPED:
        return
    if state.total_checks > 0:
        return  # Checks were provided, SKIPPED is valid (all skipped)
    # SKIPPED with 0 checks — check if contract has evidence
    has_evidence_fields = bool(
        contract.dod_evidence or contract.rendered_output
    )
    if has_evidence_fields:
        # Meta-validation failure: evidence exists but dod_verify ran 0 checks
        alert_slack(
            channel="#onex-alerts",
            message=f"[ONEX] dod_verify meta-validation failure for {contract.ticket_id}: "
                    f"contract has evidence fields but dod_verify ran 0 checks. "
                    f"Evidence collection step may be broken.",
            level="error",
        )
        log_meta_failure(contract.ticket_id, state)
```

**Acceptance criteria:**
- Hook detects SKIPPED + 0 checks + contract-has-evidence and alerts
- Hook does NOT alert when SKIPPED is legitimate (contract has no evidence fields)
- Meta-failure logged to `.onex_state/dod_meta_failures/{ticket_id}.json`

---

## Task: Alerting runbook (Wave 6)

**File to create:** `docs/runbooks/validation-sweep-failure.md`

**Content (template):**

```markdown
# Validation Sweep Failure Runbook

## Level 3: Golden chain sweep failure
1. Check sweep artifact: `onex_change_control/drift/integration/{date}-{sha}.yaml`
2. Identify failed chain(s)
3. Check DB projection table for recent rows: `SELECT * FROM {table} ORDER BY created_at DESC LIMIT 5;`
4. If no rows: Kafka consumer may be down — check `docker logs omninode-runtime`
5. If rows exist but sweep missed them: correlation_id mismatch — check sweep fixture template
6. File ticket if not self-resolving within 30 minutes

## dod_verify meta-validation failure
1. Check `.onex_state/dod_meta_failures/{ticket_id}.json`
2. Verify the evidence collection step in the Done-state hook is running
3. Check that `ModelTicketContract` is populated correctly for the ticket
4. Re-run dod_verify manually: `/onex:dod_verify --ticket {ticket_id}`
```

---

## Task: Retroactive remediation epic (Wave 7)

**Execute after vggp Tasks 11–12 (audit doc + initial tickets exist).**

**Priority filter (from §10):**

1. **Immediate (handled in Wave 0):** `_dispatch_ci_watch` — already in this plan.
2. **High-priority sub-tickets (create first batch of 10):** Handlers with DB write side effects:
   - `node_retention_cleanup/handler_retention_cleanup.py`
   - `node_baselines_batch_compute/handler_baselines_batch_compute.py`
   - `node_pattern_storage_effect/handler_promote_pattern.py`
   - `node_pattern_demotion_effect/handler_demotion.py`
   - `node_pattern_promotion_effect/handler_auto_promote.py`
   - `node_pattern_lifecycle_effect/handler_transition.py`
   - `node_claude_hook_event_effect/handler_claude_event.py`
   - `node_code_entity_bridge_compute/handler_bridge.py`
   - `node_delegation_orchestrator/handler_delegation_workflow.py` (omnibase_infra)
   - `node_registry_api_effect/handler_registry_api_get_health.py`
3. **Medium-priority (next batch):** Handlers with external API side effects (GitHub, Slack, Linear).
4. **Acknowledged-no-action (register in suspect_topics.yaml):** Channel adapters (Telegram, SMS, Discord, Email) — no test double exists.

---

## Open Questions (require human decision)

1. **Auto-merge template sweep promotion:** Should the auto-merge template sweep be promoted to Wave 0 so the hostile_reviewer gate ships to all repos simultaneously? Or proceed with per-repo manual wiring (vggp plan Wave 5)? Currently deferred in vggp plan.

2. **Slack `#onex-alerts` channel:** Does this channel exist? Does the Slack bot token have `chat:write` permission for it? Requires human setup if not.

3. **Linear Done-state automation config:** The Done-state hook must be wired in Linear workspace automation. This is a Linear platform configuration requiring human action. Is it currently wired?

4. **Rollback authority:** If the hostile_reviewer gate blocks a PR that should merge (gate false positive), who has authority to bypass? Current proposal: team-lead can merge with `--no-verify` override and must file a bypass ticket with reason. Requires human decision.

5. **Migration freeze:** `omnibase_compat` and affected repos have `.migration_freeze` active. The `overnight_sessions` projection table requires a migration. Does the freeze apply to projection tables or only to core schema migrations? Requires human decision before Wave 0 migration task.

---

## Relationship to Parallel Architecture Domains

**architect-executor:** Owns projection table emission. Must provide `projection.yaml` for new projections. Must add new topics to `chain_registry.py` or `suspect_topics.yaml`. Interface: see §3 and §2.

**plugin-arch-designer:** Owns CI plugin install step. Must ensure `claude --skip-permissions` works in CI for hostile_reviewer invocation. Must ensure pre-commit hook Python is compatible with all repos. Interface: see §4 and §5.
