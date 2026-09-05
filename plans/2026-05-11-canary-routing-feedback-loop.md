---
type: plan
status: active
date: "2026-05-11"
title: "Canary-to-routing feedback loop"
topics: [routing, canary, model-scoring, reducers]
---

# Canary-to-Routing Feedback Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan phase-by-phase.

**Goal:** Close the feedback loop between canary grading results and routing policy decisions so that model scores from canary runs automatically update the routing engine's model rankings.

**Architecture:** The canary orchestrator already publishes `adr-canary-completed` events containing `ModelCanaryReport` with per-model scores. The `routing_outcomes` and `capability_scores` tables already exist (migrations 060, 066). The gap is a reducer that subscribes to canary-completed events and materializes scores into these tables, plus wiring the routing policy engine to read from `capability_scores` instead of requiring static scores as input.

**Tech Stack:** Python 3.12+, Pydantic, Kafka (Redpanda), PostgreSQL, omnimarket node patterns

---

## Known Types Inventory

> Types discovered in the repository that are relevant to this plan.
> Any new type introduced by a task below MUST reference this inventory
> and state why an existing type does not suffice.

- `ModelModelScore` — `omnimarket/src/omnimarket/nodes/node_adr_canary_orchestrator/models/model_canary_report.py:14` — per-model grading aggregates (avg_recall, avg_precision, avg_fidelity, avg_format_compliance, estimated_cost_usd, total_latency_ms)
- `ModelCanaryReport` — `omnimarket/src/omnimarket/nodes/node_adr_canary_orchestrator/models/model_canary_report.py:34` — full canary run output including `model_scores: list[ModelModelScore]`
- `ModelRoutingPolicyRequest` — `omnimarket/src/omnimarket/nodes/node_routing_policy_engine/models/model_routing_policy_request.py:47` — routing input with `available_models: tuple[ModelAvailableModel, ...]` where each model has a static `score` field
- `ModelAvailableModel` — `omnimarket/src/omnimarket/nodes/node_routing_policy_engine/models/model_routing_policy_request.py:29` — model candidate with `score: float` (0.0-1.0), `cost_per_token: float`, `capabilities: frozenset`
- `ModelRoutingPolicyResult` — `omnimarket/src/omnimarket/nodes/node_routing_policy_engine/models/model_routing_policy_result.py:34` — routing output with selected model + alternatives
- `ModelComparisonRow` — `omnimarket/src/omnimarket/nodes/node_ab_compare_reducer/models/model_comparison_row.py:11` — AB compare output with `quality: str` field (default `""`, never populated from grading)
- `ModelEvidenceRecord` — `omnimarket/src/omnimarket/nodes/node_adr_canary_orchestrator/handlers/handler_canary_orchestrator.py:113` — per-model, per-document grading evidence
- `ModelGradingResult` — `omnimarket/src/omnimarket/nodes/node_adr_extraction_grader_llm_effect/models/model_grading_result.py:45` — single grading output (recall, precision, fidelity, format_compliance)
- `ModelRoutingRule` — `omnibase_core/src/omnibase_core/models/delegation/model_routing_rule.py:14` — static delegation routing rule (capability → target_ref)
- `EnumTaskType` — `omnimarket/src/omnimarket/nodes/node_routing_policy_engine/models/model_routing_policy_request.py:13` — CODE, REASONING, EMBEDDING, SUMMARIZATION, GENERAL

## Runtime State Inventory

> Actual runtime state queried from source artifacts.

### capability_scores Table Schema

**Source:** `omnibase_infra/docker/migrations/forward/060_create_routing_outcomes.sql`

| Column | Type | Source Migration |
|--------|------|-----------------|
| `id` | BIGSERIAL PK | 060 |
| `model_key` | TEXT NOT NULL | 060 |
| `task_type` | TEXT NOT NULL | 060 |
| `success_count` | BIGINT DEFAULT 0 | 060 |
| `failure_count` | BIGINT DEFAULT 0 | 060 |
| `total_count` | BIGINT DEFAULT 0 | 060 |
| `success_rate` | DOUBLE PRECISION | 060 |
| `avg_latency_ms` | DOUBLE PRECISION | 060 |
| `avg_tokens_per_sec` | DOUBLE PRECISION | 060 |
| `total_cost` | DOUBLE PRECISION DEFAULT 0 | 060 |
| `graduated` | BOOLEAN DEFAULT FALSE | 060 |
| `last_updated` | TIMESTAMPTZ DEFAULT NOW() | 060 |

Unique constraint: `(model_key, task_type)`

### routing_outcomes Table Schema

**Source:** `omnibase_infra/docker/migrations/forward/060_create_routing_outcomes.sql` + `066_add_quality_score_to_routing_outcomes.sql`

| Column | Type | Source Migration |
|--------|------|-----------------|
| `id` | BIGSERIAL PK | 060 |
| `correlation_id` | UUID NOT NULL | 060 |
| `model_key` | TEXT NOT NULL | 060 |
| `task_type` | TEXT NOT NULL | 060 |
| `task_subtype` | TEXT | 060 |
| `selected` | BOOLEAN NOT NULL | 060 |
| `success` | BOOLEAN | 060 |
| `actual_latency_ms` | DOUBLE PRECISION | 060 |
| `actual_cost` | DOUBLE PRECISION | 060 |
| `input_tokens` | BIGINT | 060 |
| `output_tokens` | BIGINT | 060 |
| `composite_score` | DOUBLE PRECISION | 060 |
| `quality_score` | DOUBLE PRECISION | 066 |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | 060 |
| `completed_at` | TIMESTAMPTZ | 060 |

### Kafka Topics

**Source:** contract.yaml files in each node directory

| Topic | Publisher | Consumer |
|-------|-----------|----------|
| `onex.evt.omnimarket.adr-canary-completed.v1` | node_adr_canary_orchestrator | **NONE** (the gap) |
| `onex.cmd.omnimarket.routing-policy-requested.v1` | callers | node_routing_policy_engine |
| `onex.evt.omnimarket.routing-policy-completed.v1` | node_routing_policy_engine | callers |

---

## Dependencies

This plan depends on the following in-flight canary tickets completing first:

| Title | Status | Dependency |
|-------|--------|------------|
| Build canary orchestrator (bus-triggered) | Pending | Must be done — orchestrator must publish canary-completed events to the bus |
| Proof of Life — single ADR end-to-end | Pending | Must be done — proves the canary pipeline works before wiring feedback |
| Full canary — 31 ADRs x 19 models | Pending | Should be done — produces the grading data that feeds the reducer |
| Human review gate for proposed ADRs | Pending | Independent — can proceed in parallel |

---

## Task 1: Build node_canary_score_reducer — contract and models

**Why:** No node currently consumes `adr-canary-completed` events. This reducer materializes canary grading scores into the existing `capability_scores` table, closing the feedback loop.

**Not reusing `node_ab_compare_reducer` because:** AB compare reducer consumes `ab-inference-completed` events (different schema — `ModelInferenceResultEntry` vs `ModelCanaryReport`), tracks cost metrics only (`quality="skipped"`), and materializes to `llm_call_metrics` table. The canary reducer consumes canary-completed events with 4-dimension grading scores and materializes to `capability_scores`. Different input, different output, different table.

**Files:**
- Create: `omnimarket/src/omnimarket/nodes/node_canary_score_reducer/__init__.py`
- Create: `omnimarket/src/omnimarket/nodes/node_canary_score_reducer/contract.yaml`
- Create: `omnimarket/src/omnimarket/nodes/node_canary_score_reducer/metadata.yaml`
- Create: `omnimarket/src/omnimarket/nodes/node_canary_score_reducer/models/__init__.py`
- Create: `omnimarket/src/omnimarket/nodes/node_canary_score_reducer/models/model_score_reducer_state.py`
- Create: `omnimarket/src/omnimarket/nodes/node_canary_score_reducer/handlers/__init__.py`
- Test: `omnimarket/src/omnimarket/nodes/node_canary_score_reducer/tests/__init__.py`

**Step 1: Write contract.yaml**

Define the node contract:
- Subscribe: `onex.evt.omnimarket.adr-canary-completed.v1`
- Publish: `onex.evt.omnimarket.capability-scores-updated.v1`
- Projection: table `capability_scores`, snapshot topic `onex.snapshot.projection.capability-scores.v1`
- Type: REDUCER
- Handler module: `omnimarket.nodes.node_canary_score_reducer.handlers.handler_canary_score_reducer`

**Step 2: Write model_score_reducer_state.py**

Reducer state model tracks the latest scores per model_key + task_type:

```python
from pydantic import BaseModel, Field


class ModelCapabilityScoreRow(BaseModel, frozen=True):
    model_key: str
    task_type: str
    avg_recall: float | None = Field(None, ge=0.0, le=1.0)
    avg_precision: float | None = Field(None, ge=0.0, le=1.0)
    avg_fidelity: float | None = Field(None, ge=0.0, le=1.0)
    avg_format_compliance: float | None = Field(None, ge=0.0, le=1.0)
    composite_score: float | None = Field(None, ge=0.0, le=1.0)
    entries_evaluated: int = Field(0, ge=0)
    estimated_cost_usd: float | None = Field(None, ge=0.0)
    total_latency_ms: int = Field(0, ge=0)
    canary_run_id: str = ""


class ModelScoreReducerState(BaseModel):
    scores: dict[str, ModelCapabilityScoreRow] = Field(
        default_factory=dict,
        description="Keyed by '{model_key}::{task_type}'",
    )
```

**Step 3: Write metadata.yaml**

Standard omnimarket node metadata with tags: `["reducer", "canary", "routing", "feedback"]`.

**Step 4: Commit**

```bash
git add omnimarket/src/omnimarket/nodes/node_canary_score_reducer/
git commit -m "feat(OMN-XXXX): scaffold node_canary_score_reducer contract and models"
```

**Acceptance:**
- contract.yaml parses without error
- Subscribe topic matches `onex.evt.omnimarket.adr-canary-completed.v1` exactly
- Projection table is `capability_scores`
- `ModelCapabilityScoreRow` contains all 4 grading dimensions plus composite_score
- `ModelScoreReducerState` uses `{model_key}::{task_type}` composite key

**Verification grade:** medium (contract parses, model instantiates)

---

## Task 2: Implement canary score reducer handler

**Why:** The handler is the core logic: consume a `ModelCanaryReport`, extract `model_scores`, compute composite scores, and upsert into `capability_scores` table.

**Files:**
- Create: `omnimarket/src/omnimarket/nodes/node_canary_score_reducer/handlers/handler_canary_score_reducer.py`
- Test: `omnimarket/src/omnimarket/nodes/node_canary_score_reducer/tests/test_handler_canary_score_reducer.py`

**Step 1: Write the failing test**

```python
import pytest
from omnimarket.nodes.node_adr_canary_orchestrator.models.model_canary_report import (
    ModelCanaryReport,
    ModelModelScore,
)
from omnimarket.nodes.node_canary_score_reducer.handlers.handler_canary_score_reducer import (
    HandlerCanaryScoreReducer,
)
from omnimarket.nodes.node_canary_score_reducer.models.model_score_reducer_state import (
    ModelScoreReducerState,
)


@pytest.mark.unit
def test_accumulate_updates_state_from_canary_report() -> None:
    handler = HandlerCanaryScoreReducer()
    state = ModelScoreReducerState()

    report = ModelCanaryReport(
        run_id="canary-001",
        manifest_path="/tmp/manifest.yaml",
        entries_total=10,
        entries_completed=10,
        entries_failed=0,
        model_scores=[
            ModelModelScore(
                model_key="qwen3-coder-30b",
                entries_evaluated=10,
                entries_failed=0,
                avg_recall=0.94,
                avg_precision=0.91,
                avg_fidelity=0.88,
                avg_format_compliance=0.95,
                total_latency_ms=45000,
                estimated_cost_usd=0.12,
            ),
            ModelModelScore(
                model_key="deepseek-r1-14b",
                entries_evaluated=10,
                entries_failed=0,
                avg_recall=0.87,
                avg_precision=0.83,
                avg_fidelity=0.80,
                avg_format_compliance=0.90,
                total_latency_ms=32000,
                estimated_cost_usd=0.08,
            ),
        ],
        evidence_dir="/tmp/evidence",
        scorecard_path="/tmp/scorecard.md",
        dry_run=False,
        success=True,
    )

    new_state = handler.accumulate(state, report)

    assert len(new_state.scores) == 2
    qwen_score = new_state.scores["qwen3-coder-30b::adr_extraction"]
    assert qwen_score.avg_recall == 0.94
    assert qwen_score.composite_score is not None
    assert qwen_score.composite_score > 0.0
    assert qwen_score.canary_run_id == "canary-001"

    ds_score = new_state.scores["deepseek-r1-14b::adr_extraction"]
    assert ds_score.avg_recall == 0.87
    assert qwen_score.composite_score > ds_score.composite_score


@pytest.mark.unit
def test_composite_score_weights_recall_and_precision_highest() -> None:
    handler = HandlerCanaryScoreReducer()

    score = handler._compute_composite(
        recall=1.0, precision=1.0, fidelity=0.0, format_compliance=0.0,
    )
    score_low_recall = handler._compute_composite(
        recall=0.0, precision=1.0, fidelity=1.0, format_compliance=1.0,
    )
    assert score > score_low_recall


@pytest.mark.unit
def test_materialize_produces_upsert_rows() -> None:
    handler = HandlerCanaryScoreReducer()
    state = ModelScoreReducerState(
        scores={
            "qwen3-coder-30b::adr_extraction": ModelCapabilityScoreRow(
                model_key="qwen3-coder-30b",
                task_type="adr_extraction",
                avg_recall=0.94,
                avg_precision=0.91,
                avg_fidelity=0.88,
                avg_format_compliance=0.95,
                composite_score=0.92,
                entries_evaluated=10,
                estimated_cost_usd=0.12,
                total_latency_ms=45000,
                canary_run_id="canary-001",
            ),
        },
    )

    rows = handler.materialize(state)
    assert len(rows) == 1
    assert rows[0]["model_key"] == "qwen3-coder-30b"
    assert rows[0]["task_type"] == "adr_extraction"
    assert rows[0]["success_rate"] == pytest.approx(0.92, abs=0.01)
```

**Step 2: Run test to verify it fails**

Run: `cd omnimarket && uv run pytest src/omnimarket/nodes/node_canary_score_reducer/tests/test_handler_canary_score_reducer.py -v`
Expected: FAIL — handler not implemented

**Step 3: Implement handler**

```python
from __future__ import annotations

from omnimarket.nodes.node_adr_canary_orchestrator.models.model_canary_report import (
    ModelCanaryReport,
    ModelModelScore,
)
from omnimarket.nodes.node_canary_score_reducer.models.model_score_reducer_state import (
    ModelCapabilityScoreRow,
    ModelScoreReducerState,
)

TASK_TYPE = "adr_extraction"

WEIGHT_RECALL = 0.35
WEIGHT_PRECISION = 0.35
WEIGHT_FIDELITY = 0.20
WEIGHT_FORMAT = 0.10


class HandlerCanaryScoreReducer:

    def accumulate(
        self,
        state: ModelScoreReducerState,
        report: ModelCanaryReport,
    ) -> ModelScoreReducerState:
        if not report.success:
            return state

        new_scores = dict(state.scores)
        for ms in report.model_scores:
            key = f"{ms.model_key}::{TASK_TYPE}"
            composite = self._compute_composite(
                recall=ms.avg_recall,
                precision=ms.avg_precision,
                fidelity=ms.avg_fidelity,
                format_compliance=ms.avg_format_compliance,
            )
            new_scores[key] = ModelCapabilityScoreRow(
                model_key=ms.model_key,
                task_type=TASK_TYPE,
                avg_recall=ms.avg_recall,
                avg_precision=ms.avg_precision,
                avg_fidelity=ms.avg_fidelity,
                avg_format_compliance=ms.avg_format_compliance,
                composite_score=composite,
                entries_evaluated=ms.entries_evaluated,
                estimated_cost_usd=ms.estimated_cost_usd,
                total_latency_ms=ms.total_latency_ms,
                canary_run_id=report.run_id,
            )
        return ModelScoreReducerState(scores=new_scores)

    def materialize(self, state: ModelScoreReducerState) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for row in state.scores.values():
            rows.append({
                "model_key": row.model_key,
                "task_type": row.task_type,
                "success_rate": row.composite_score,
                "avg_latency_ms": float(row.total_latency_ms) / max(row.entries_evaluated, 1),
                "total_cost": row.estimated_cost_usd,
                "total_count": row.entries_evaluated,
                "success_count": row.entries_evaluated,
                "failure_count": 0,
            })
        return rows

    def _compute_composite(
        self,
        recall: float | None,
        precision: float | None,
        fidelity: float | None,
        format_compliance: float | None,
    ) -> float | None:
        components = [
            (recall, WEIGHT_RECALL),
            (precision, WEIGHT_PRECISION),
            (fidelity, WEIGHT_FIDELITY),
            (format_compliance, WEIGHT_FORMAT),
        ]
        scored = [(v, w) for v, w in components if v is not None]
        if not scored:
            return None
        total_weight = sum(w for _, w in scored)
        return sum(v * w for v, w in scored) / total_weight
```

**Step 4: Run tests**

Run: `cd omnimarket && uv run pytest src/omnimarket/nodes/node_canary_score_reducer/tests/test_handler_canary_score_reducer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add omnimarket/src/omnimarket/nodes/node_canary_score_reducer/
git commit -m "feat(OMN-XXXX): implement canary score reducer handler with composite scoring"
```

**Acceptance:**
- `accumulate()` consumes a `ModelCanaryReport` and produces updated `ModelScoreReducerState`
- Composite score weights recall (0.35) and precision (0.35) highest, fidelity (0.20), format (0.10)
- `materialize()` produces rows matching `capability_scores` table schema exactly (model_key, task_type, success_rate, avg_latency_ms, total_cost, total_count, success_count, failure_count)
- All 3 test cases pass
- No new models introduced — reuses `ModelModelScore` and `ModelCanaryReport` from canary orchestrator

**Verification grade:** medium (unit tests assert specific field values and ranking)

---

## Task 3: Wire routing policy engine to read from capability_scores

**Why:** `HandlerRoutingPolicy` currently requires callers to pass model scores as static input. After this task, callers can look up scores from the `capability_scores` table instead of hardcoding them.

**Files:**
- Create: `omnimarket/src/omnimarket/nodes/node_routing_policy_engine/handlers/handler_score_lookup.py`
- Modify: `omnimarket/src/omnimarket/nodes/node_routing_policy_engine/models/model_routing_policy_request.py`
- Test: `omnimarket/src/omnimarket/nodes/node_routing_policy_engine/tests/test_handler_score_lookup.py`

**Step 1: Write the failing test**

```python
import pytest
from omnimarket.nodes.node_routing_policy_engine.handlers.handler_score_lookup import (
    build_available_models_from_scores,
)
from omnimarket.nodes.node_routing_policy_engine.models.model_routing_policy_request import (
    ModelAvailableModel,
)


@pytest.mark.unit
def test_build_available_models_from_capability_scores() -> None:
    capability_rows = [
        {
            "model_key": "qwen3-coder-30b",
            "task_type": "adr_extraction",
            "success_rate": 0.92,
            "avg_latency_ms": 4500.0,
            "total_cost": 0.12,
            "total_count": 10,
        },
        {
            "model_key": "deepseek-r1-14b",
            "task_type": "adr_extraction",
            "success_rate": 0.85,
            "avg_latency_ms": 3200.0,
            "total_cost": 0.08,
            "total_count": 10,
        },
    ]
    cost_map = {
        "qwen3-coder-30b": 0.0001,
        "deepseek-r1-14b": 0.00005,
    }

    models = build_available_models_from_scores(capability_rows, cost_map)

    assert len(models) == 2
    assert models[0].key == "qwen3-coder-30b"
    assert models[0].score == pytest.approx(0.92, abs=0.01)
    assert models[1].key == "deepseek-r1-14b"
    assert models[1].score == pytest.approx(0.85, abs=0.01)


@pytest.mark.unit
def test_build_available_models_empty_scores_returns_empty() -> None:
    models = build_available_models_from_scores([], {})
    assert models == []
```

**Step 2: Run test to verify it fails**

Run: `cd omnimarket && uv run pytest src/omnimarket/nodes/node_routing_policy_engine/tests/test_handler_score_lookup.py -v`
Expected: FAIL — module not found

**Step 3: Implement score lookup**

```python
from __future__ import annotations

from omnimarket.nodes.node_routing_policy_engine.models.model_routing_policy_request import (
    ModelAvailableModel,
)


def build_available_models_from_scores(
    capability_rows: list[dict[str, object]],
    cost_map: dict[str, float],
) -> list[ModelAvailableModel]:
    models: list[ModelAvailableModel] = []
    for row in capability_rows:
        model_key = str(row["model_key"])
        score = float(row.get("success_rate", 0.0) or 0.0)
        cost = cost_map.get(model_key, 0.0)
        models.append(
            ModelAvailableModel(
                key=model_key,
                score=score,
                cost_per_token=cost,
                capabilities=frozenset(),
            ),
        )
    return models
```

**Step 4: Run tests**

Run: `cd omnimarket && uv run pytest src/omnimarket/nodes/node_routing_policy_engine/tests/test_handler_score_lookup.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add omnimarket/src/omnimarket/nodes/node_routing_policy_engine/
git commit -m "feat(OMN-XXXX): add score lookup to bridge capability_scores → routing policy"
```

**Acceptance:**
- `build_available_models_from_scores()` converts `capability_scores` rows into `ModelAvailableModel` instances
- Score values map to `ModelAvailableModel.score` field (0.0-1.0)
- Empty input returns empty list (no crash)
- Existing `HandlerRoutingPolicy` is NOT modified — this is a caller-side bridge, not a handler change
- No new models introduced — reuses `ModelAvailableModel`

**Verification grade:** medium (unit tests assert specific field mapping)

---

## Task 4: Populate routing_outcomes.quality_score from canary grading

**Why:** The `routing_outcomes` table has a `quality_score` column (migration 066) that is never written. `node_platform_readiness` already queries it (`SELECT COUNT(*) FROM routing_outcomes WHERE quality_score IS NOT NULL`). Populating it from canary scores makes platform readiness checks pass with real data.

**Files:**
- Modify: `omnimarket/src/omnimarket/nodes/node_canary_score_reducer/handlers/handler_canary_score_reducer.py`
- Test: `omnimarket/src/omnimarket/nodes/node_canary_score_reducer/tests/test_handler_canary_score_reducer.py`

**Step 1: Write the failing test**

```python
@pytest.mark.unit
def test_materialize_produces_routing_outcome_rows() -> None:
    handler = HandlerCanaryScoreReducer()
    state = ModelScoreReducerState(
        scores={
            "qwen3-coder-30b::adr_extraction": ModelCapabilityScoreRow(
                model_key="qwen3-coder-30b",
                task_type="adr_extraction",
                avg_recall=0.94,
                avg_precision=0.91,
                avg_fidelity=0.88,
                avg_format_compliance=0.95,
                composite_score=0.92,
                entries_evaluated=10,
                estimated_cost_usd=0.12,
                total_latency_ms=45000,
                canary_run_id="canary-001",
            ),
        },
    )

    result = handler.materialize(state)
    assert result.routing_outcome_rows is not None
    assert len(result.routing_outcome_rows) == 1
    row = result.routing_outcome_rows[0]
    assert row["quality_score"] == pytest.approx(0.92, abs=0.01)
    assert row["model_key"] == "qwen3-coder-30b"
    assert row["task_type"] == "adr_extraction"
```

**Step 2: Run test to verify it fails**

Expected: FAIL — `materialize()` returns a list, not an object with `routing_outcome_rows`

**Step 3: Update materialize to produce both table outputs**

Create a `ModelMaterializeResult` to hold both `capability_score_rows` and `routing_outcome_rows`. Update `materialize()` to return both. Each `routing_outcome_row` includes `quality_score` set to the composite score.

**Step 4: Run tests**

Run: `cd omnimarket && uv run pytest src/omnimarket/nodes/node_canary_score_reducer/tests/ -v`
Expected: PASS (all tests including Task 2 tests updated for new return type)

**Step 5: Commit**

```bash
git add omnimarket/src/omnimarket/nodes/node_canary_score_reducer/
git commit -m "feat(OMN-XXXX): materialize quality_score into routing_outcomes from canary grading"
```

**Acceptance:**
- `materialize()` returns rows for BOTH `capability_scores` and `routing_outcomes` tables
- `routing_outcomes.quality_score` is set to the composite score from the canary grading
- `routing_outcomes.model_key` and `task_type` match the canary result
- Platform readiness query `SELECT COUNT(*) FROM routing_outcomes WHERE quality_score IS NOT NULL` returns > 0 after a canary run

**Verification grade:** medium (unit tests assert specific field values)

---

## Task 5: Proof of Life — End-to-End Canary → Scores → Routing

**Why:** Proves the full chain works: canary run produces grades, reducer materializes scores, routing policy reads from scores.

**Files:**
- Create: `omnimarket/src/omnimarket/nodes/node_canary_score_reducer/tests/test_integration_feedback_loop.py`

**Step 1: Write the integration test**

```python
import pytest
from omnimarket.nodes.node_adr_canary_orchestrator.models.model_canary_report import (
    ModelCanaryReport,
    ModelModelScore,
)
from omnimarket.nodes.node_canary_score_reducer.handlers.handler_canary_score_reducer import (
    HandlerCanaryScoreReducer,
)
from omnimarket.nodes.node_canary_score_reducer.models.model_score_reducer_state import (
    ModelScoreReducerState,
)
from omnimarket.nodes.node_routing_policy_engine.handlers.handler_routing_policy import (
    HandlerRoutingPolicy,
)
from omnimarket.nodes.node_routing_policy_engine.handlers.handler_score_lookup import (
    build_available_models_from_scores,
)
from omnimarket.nodes.node_routing_policy_engine.models.model_routing_policy_request import (
    ModelRoutingPolicyRequest,
)


@pytest.mark.integration
def test_canary_scores_feed_routing_decisions() -> None:
    # 1. Simulate canary report
    report = ModelCanaryReport(
        run_id="canary-integration-001",
        manifest_path="/tmp/manifest.yaml",
        entries_total=10,
        entries_completed=10,
        entries_failed=0,
        model_scores=[
            ModelModelScore(
                model_key="qwen3-coder-30b",
                entries_evaluated=10,
                entries_failed=0,
                avg_recall=0.94,
                avg_precision=0.91,
                avg_fidelity=0.88,
                avg_format_compliance=0.95,
                total_latency_ms=45000,
                estimated_cost_usd=0.12,
            ),
            ModelModelScore(
                model_key="deepseek-r1-14b",
                entries_evaluated=10,
                entries_failed=0,
                avg_recall=0.70,
                avg_precision=0.65,
                avg_fidelity=0.60,
                avg_format_compliance=0.80,
                total_latency_ms=32000,
                estimated_cost_usd=0.08,
            ),
        ],
        evidence_dir="/tmp/evidence",
        scorecard_path="/tmp/scorecard.md",
        dry_run=False,
        success=True,
    )

    # 2. Reducer accumulates and materializes
    reducer = HandlerCanaryScoreReducer()
    state = reducer.accumulate(ModelScoreReducerState(), report)
    result = reducer.materialize(state)

    # 3. Score lookup bridges to routing
    cost_map = {"qwen3-coder-30b": 0.0001, "deepseek-r1-14b": 0.00005}
    available = build_available_models_from_scores(
        result.capability_score_rows, cost_map,
    )

    # 4. Routing selects the champion
    router = HandlerRoutingPolicy()
    routing_result = router.handle(
        ModelRoutingPolicyRequest(
            task_type="GENERAL",
            available_models=tuple(available),
        ),
    )

    # 5. Verify: Qwen3-Coder wins (highest composite score)
    assert routing_result.selected_model_key == "qwen3-coder-30b"
    assert routing_result.selection_mode.value == "EXPLOIT"

    # 6. Verify: quality_score is populated for routing_outcomes
    assert len(result.routing_outcome_rows) == 2
    qwen_outcome = next(
        r for r in result.routing_outcome_rows
        if r["model_key"] == "qwen3-coder-30b"
    )
    assert qwen_outcome["quality_score"] > 0.0
```

**Step 2: Run the test**

Run: `cd omnimarket && uv run pytest src/omnimarket/nodes/node_canary_score_reducer/tests/test_integration_feedback_loop.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add omnimarket/src/omnimarket/nodes/node_canary_score_reducer/tests/
git commit -m "test(OMN-XXXX): proof of life — canary → reducer → routing feedback loop"
```

**Acceptance:**
- Canary report with 2 models → reducer produces scores → score lookup bridges to routing → routing selects the higher-scoring model
- The chain works without any database — pure in-memory from event to routing decision
- `routing_outcomes` rows include `quality_score` > 0.0
- Qwen3-Coder (0.94 recall) is selected over DeepSeek-R1 (0.70 recall)

**Verification grade:** strong (end-to-end chain assertion with specific model selection + quality score verification)

---

## Task 6: Product packaging integration — investor demo surface

**Why:** Delegation + canary + feedback loop + champion tracking exist as infrastructure. This task packages them into an investor-demonstrable product surface: "run a canary sweep across N models, see which one wins, see the routing update automatically."

**Files:**
- Create: `docs/plans/2026-05-XX-product-packaging-vertical-templates.md` (design doc for vertical templates)
- Modify: `docs/research/2026-05-11-anthropic-feature-deep-dive.md` (update status)

**Step 1: Write the product packaging design doc**

Document the 3-5 vertical templates with their delegation contracts:
1. **Model Migration Validator** — canary sweep + grading + routing update
2. **Compliance Evidence Generator** — receipt-backed audit trail
3. **Prompt Regression Guard** — replay + semantic diff
4. **Cost Optimization Auditor** — grid search + champion tracking

Each template maps to: trigger → canary/replay → grade → feedback → evidence report.

**Step 2: Define the investor demo script**

The demo is the Proof of Life from Task 5, run live:
1. "Here are 31 architectural decision records."
2. "We run them through 19 models." (canary orchestrator)
3. "We grade every extraction on 4 dimensions." (grading node)
4. "The system identifies which model wins." (reducer + champion)
5. "Routing automatically updates." (score lookup → policy engine)
6. "Here's the audit trail." (event bus + receipts)

**Step 3: Create Linear ticket for the full packaging sprint**

This task is a planning/scoping task. The actual packaging work (landing page, demo polish, template contracts) gets its own tickets created from the design doc.

**Step 4: Commit**

```bash
git add docs/plans/
git commit -m "docs(OMN-XXXX): product packaging design for vertical templates and investor demo"
```

**Acceptance:**
- Design doc defines exactly 3-5 named templates with contract schemas
- Investor demo script maps to existing infrastructure (no new engineering required)
- Each template references the specific nodes and topics it chains together
- Linear ticket created for the packaging sprint

**Verification grade:** weak (document review — no runtime assertion, but this is a planning task)

---

## Routing

```yaml
routing:
  strategy: ticket-pipeline
  repo: omnimarket
  dependencies:
    - canary orchestrator (bus-triggered)
    - proof of life (single ADR)
  epic: "Canary-to-Routing Feedback Loop"
  notes: >
    Tasks 1-5 are engineering in omnimarket.
    Task 6 is product/planning in omni_home.
    Tasks 1-4 are sequential. Task 5 depends on 1-4.
    Task 6 can start after Task 5 passes.
```
