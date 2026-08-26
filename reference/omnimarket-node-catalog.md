---
type: reference
status: current
date: "2026-08-26"
title: "OmniMarket Node Catalog"
topics:
  - omnimarket
  - nodes
  - onex-runtime
refs: []
---

# OmniMarket Node Catalog

> **Last verified:** 2026-08-26. Corrected against `omnimarket@dev` (`pyproject.toml` at version `0.4.11`): 384 registered `onex.nodes` entry points, statically counted from this package's own `[project.entry-points."onex.nodes"]` table (not the runtime `importlib.metadata.entry_points()` call, which over-counts in a dev venv because it also picks up entries registered by `omnibase_core`/`omnibase_infra` installed as dependencies in the same environment), and 387 `node_*` package directories under `src/omnimarket/nodes/`, all 387 carrying a `metadata.yaml`. This corrects the 2026-08-25 migration snapshot below, which claimed 390 directories with 3 missing `metadata.yaml` (`node_multi_agent_orchestrator`, `node_dispatch_request_handler`, `node_doc_freshness_sweep`) — that claim did not hold even on the day it was written: all three directories had already been deleted, in commits dated 2026-06-28, 2026-08-13, and 2026-08-20, all before the migration. These are counts, not a generator — see the inspection commands below to re-derive them at any point in time rather than trusting this snapshot as it ages further.

The canonical entry-point list is
`[project.entry-points."onex.nodes"]` in `pyproject.toml`.

As of this correction the repository contains 387 node package directories
under `src/omnimarket/nodes/` and registers 384 `onex.nodes` entry points
(some directories are deliberately deregistered — handler source retained,
`contract.yaml` marked `lifecycle: deprecated`, superseded by a newer node —
rather than deleted). All 387 directories have a `metadata.yaml`.

## Inspect The Catalog

List registered entry points:

```bash
uv run python - <<'PY'
from importlib.metadata import entry_points

for entry_point in sorted(entry_points(group="onex.nodes"), key=lambda item: item.name):
    print(f"{entry_point.name} = {entry_point.value}")
PY
```

List node package directories:

```bash
find src/omnimarket/nodes -mindepth 1 -maxdepth 1 -type d -name 'node_*' | sort
```

Verify every registered entry point has the expected package shape:

```bash
uv run python -m omnimarket.nodes.node_runtime_sweep --import-check
```

## Node Families

| Family | Representative nodes |
| --- | --- |
| Build and pipeline | `node_build_loop_orchestrator`, `node_build_dispatch_effect`, `node_loop_state_reducer`, `node_ticket_pipeline`, `node_pipeline_fill`, `node_session_orchestrator` |
| PR and review lifecycle | `node_pr_lifecycle_orchestrator`, `node_pr_lifecycle_triage_compute`, `node_pr_lifecycle_merge_effect`, `node_pr_polish`, `node_pr_review_orchestrator`, `node_pr_review_fsm_reducer`, `node_github_review_effect`, `node_judge_verdict_parse_compute`, `node_rebase_effect`, `node_ci_fix_effect` |
| Validation and diagnostics | `node_platform_readiness`, `node_runtime_sweep`, `node_golden_chain_sweep`, `node_data_flow_sweep`, `node_quality_scoring_compute`, `node_environment_health_scanner`, `node_version_skew_detector`, `node_volume_config_drift_sweep` |
| Planning and tickets | `node_design_to_plan`, `node_plan_to_tickets`, `node_create_ticket`, `node_ticket_query`, `node_ticket_work`, `node_rsd_fill_compute` |
| Memory and intelligence | `node_memory_lifecycle_orchestrator`, `node_memory_storage_effect`, `node_intelligence_orchestrator`, `node_intelligence_reducer`, `node_semantic_analyzer_compute`, `node_persona_lifecycle_orchestrator` |
| Projection and data | `node_projection_baselines`, `node_projection_registration`, `node_projection_session_outcome`, `node_log_projection`, `node_projection_routing_decision`, `node_projection_pattern_learning` |
| Operations and integration | `node_emit_daemon`, `node_authorize`, `node_release`, `node_redeploy`, `node_model_router`, `node_onboarding`, `node_monitor_alert_responder`, `node_delegate_skill_orchestrator`, `node_integration_sweep_orchestrator` |

## Current Canary Nodes

Use these as reference implementations:

- `node_platform_readiness` for pure compute and readiness results.
- `node_aislop_sweep` for repository-analysis behavior.
- `node_loop_state_reducer` for pure reducer/FSM behavior.
- `node_build_loop_orchestrator` for workflow coordination.
- `node_emit_daemon` for service-node lifecycle.
- `node_projection_*` packages for projection patterns.

## Adding A Catalog Entry

1. Add the node package under `src/omnimarket/nodes/node_<name>/`.
2. Add `contract.yaml` and `metadata.yaml`.
3. Add the entry point to `pyproject.toml`.
4. Add or update a golden-chain test.
5. Run:

```bash
uv run python -m omnimarket.nodes.node_runtime_sweep --import-check
uv run python scripts/ci/check_node_metadata_dependencies.py
```
