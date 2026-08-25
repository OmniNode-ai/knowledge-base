---
type: reference
status: current
date: "2026-08-25"
title: "OmniIntelligence Event Surface"
topics:
  - omniintelligence
  - kafka
  - event-surface
refs: []
---

# OmniIntelligence Event Surface

**Owner:** omniintelligence
**Last verified:** 2026-08-25 — migrated from `omniintelligence` to the knowledge base. During migration, one row was corrected and one produced topic was added: the Consumed Topics table listed `onex.cmd.omniintelligence.quality-assessment.v1` as consumed "(planned — Gap 4 in wiring-gaps plan)"; live source (`node_pattern_feedback_effect`'s `contract.yaml` and its `handler_session_outcome.py`) shows this command is actively published, so the "planned" language was removed and the corresponding Produced Topics row was added. Two downstream sections (Projected/Read-Model Events, Dashboard-Visible Events) describe an omnidash-side consumer file that could not be located in the current omnidash tree — see the flag on those sections below.
**Verification source:** contract YAML files under `src/omniintelligence/nodes/*/contract.yaml` — this page is generated from those files, not hand-maintained.

This page lists all Kafka topics produced, consumed, or otherwise associated with omniintelligence.

**Topic naming convention:** `onex.{kind}.{producer-service}.{event-name}.v{N}`

The companion doc for which of these topics reach omnidash (`DASH_INTEGRATION_TRUTH_BOUNDARY.md`) was quarantined during this migration rather than published — its omnidash-side wiring claims could not be re-verified against the current omnidash tree (same finding as the flag below) and it remains in the `omniintelligence` repo pending a dedicated cross-repo pass.

---

## Produced Topics

Topics published by omniintelligence nodes.

| Topic | Publisher node | Purpose | Consumer(s) |
|-------|---------------|---------|-------------|
| `onex.evt.omniintelligence.intent-classified.v1` | `NodeClaudeHookEventEffect` | Classified user intent from hook events | omnimemory (graph storage) |
| `onex.evt.omniintelligence.pattern-learned.v1` | `NodePatternLearningEffect` | Pattern extracted and learned from trace | `NodePatternStorageEffect` |
| `onex.evt.omniintelligence.pattern-stored.v1` | `NodePatternStorageEffect` | Pattern persisted to PostgreSQL | downstream subscribers |
| `onex.evt.omniintelligence.pattern-promoted.v1` | `NodePatternStorageEffect`, `NodePatternPromotionEffect` | Pattern promoted (provisional to validated) | downstream subscribers |
| `onex.evt.omniintelligence.pattern-deprecated.v1` | `NodePatternDemotionEffect` | Pattern demoted (validated to deprecated) | downstream subscribers |
| `onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1` | `NodePatternLifecycleEffect` | Atomic lifecycle transition applied with audit trail | downstream subscribers |
| `onex.evt.omniintelligence.code-analysis-completed.v1` | `NodeIntelligenceOrchestrator` | Code analysis workflow completed | downstream subscribers |
| `onex.evt.omniintelligence.code-analysis-failed.v1` | `NodeIntelligenceOrchestrator` | Code analysis workflow failed | downstream subscribers |
| `onex.evt.omniintelligence.document-ingestion-completed.v1` | `NodeIntelligenceOrchestrator` | Document ingestion completed | downstream subscribers |
| `onex.evt.omniintelligence.document-ingestion-failed.v1` | `NodeIntelligenceOrchestrator` | Document ingestion failed | downstream subscribers |
| `onex.evt.omniintelligence.pattern-learning-completed.v1` | `NodeIntelligenceOrchestrator` | Pattern learning workflow completed | downstream subscribers |
| `onex.evt.omniintelligence.pattern-learning-failed.v1` | `NodeIntelligenceOrchestrator` | Pattern learning workflow failed | downstream subscribers |
| `onex.evt.omniintelligence.quality-assessment-completed.v1` | `NodeIntelligenceOrchestrator` | Quality assessment scoring completed | omnidash (flagged — see Dashboard-Visible Events below) |
| `onex.evt.omniintelligence.quality-assessment-failed.v1` | `NodeIntelligenceOrchestrator` | Quality assessment scoring failed | downstream subscribers |
| `onex.cmd.omniintelligence.quality-assessment.v1` | `NodePatternFeedbackEffect` | Quality-assessment command emitted per updated pattern after effectiveness scoring | `NodeIntelligenceOrchestrator` |
| `onex.evt.omniintelligence.bloom-eval-completed.v1` | `NodeBloomEvalOrchestrator` | Bloom evaluation suite completed | omnidash (flagged — see Dashboard-Visible Events below) |
| `onex.evt.omniintelligence.routing-feedback-processed.v1` | `NodeRoutingFeedbackEffect` | Routing feedback event processed | omnidash (flagged — see Dashboard-Visible Events below) |
| `onex.cmd.omniintelligence.pattern-lifecycle-transition.v1` | `NodePatternPromotionEffect`, `NodePatternDemotionEffect` | Command forwarded to trigger `NodePatternLifecycleEffect` | `NodePatternLifecycleEffect` |
| `onex.evt.omniintelligence.pattern-scored.v1` | `NodePatternFeedbackEffect` | Per-pattern scored events emitted after effectiveness scores are recomputed from rolling metrics | downstream subscribers |
| `onex.evt.omniintelligence.dispatch-outcome-evaluated.v1` | `NodeDispatchOutcomeEvalEffect` | Normalized dispatch outcome evaluation event for downstream intelligence consumers | downstream subscribers |

---

## Consumed Topics

Topics subscribed to by omniintelligence nodes. Collected by `collect_subscribe_topics_from_contracts()` from contract YAML files — no hardcoded lists in Python.

| Topic | Subscriber node | Source producer | Purpose |
|-------|----------------|-----------------|---------|
| `onex.cmd.omniintelligence.claude-hook-event.v1` | `NodeClaudeHookEventEffect` | omniclaude | Claude Code hook events (UserPromptSubmit, Stop, etc.) |
| `onex.cmd.omniintelligence.tool-content.v1` | `NodeClaudeHookEventEffect` | omniclaude | Tool content events from Claude Code |
| `onex.cmd.omniintelligence.pattern-lifecycle-transition.v1` | `NodePatternLifecycleEffect` | `NodePatternPromotionEffect`, `NodePatternDemotionEffect` | Apply pattern lifecycle transitions atomically |
| `onex.cmd.omniintelligence.pattern-learning.v1` | `NodePatternLearningEffect`, `NodeIntelligenceOrchestrator` | `NodeClaudeHookEventEffect` (Stop) | Trigger pattern learning pipeline |
| `onex.evt.omniintelligence.pattern-learned.v1` | `NodePatternStorageEffect` | `NodePatternLearningEffect` | Persist learned patterns to PostgreSQL |
| `onex.evt.pattern.discovered.v1` | `NodePatternStorageEffect` | External systems (omniclaude, multi-producer domain event) | Pattern discovered externally; producer segment intentionally omitted |
| `onex.cmd.omniintelligence.session-outcome.v1` | `NodePatternFeedbackEffect` | External (session lifecycle triggers) | Record session outcome and update rolling-window metrics |
| `onex.cmd.omniintelligence.code-analysis.v1` | `NodeIntelligenceOrchestrator` | External callers | Trigger code analysis workflow |
| `onex.cmd.omniintelligence.document-ingestion.v1` | `NodeIntelligenceOrchestrator` | External callers | Trigger document ingestion workflow |
| `onex.cmd.omniintelligence.quality-assessment.v1` | `NodeIntelligenceOrchestrator` | `NodePatternFeedbackEffect` | Trigger quality scoring pass |
| `onex.evt.omniclaude.dispatch_worker-completed.v1` | `NodeDispatchOutcomeEvalEffect` | omniclaude dispatch worker | Dispatch worker completion events consumed for outcome evaluation |

---

## Projected / Read-Model Events

> **Flagged during 2026-08-25 migration:** the source document named an omnidash consumer file (`omniintelligence-projections.ts`) and a `READ_MODEL_TOPICS` registry as the verification points for this table. Neither was found in the current omnidash tree: there is no file by that name under `omnidash/server/`, no `SUFFIX_INTELLIGENCE_*` constant anywhere in the omnidash source, and no reference to `pattern_learning_artifacts`, `routing_feedback_events`, or `bloom_eval_results` in omnidash's code or migrations. omnidash's current server layer instead exposes a generic `GET /projection/:topic` endpoint over `onex.snapshot.projection.*` topics (`server/routes.ts`, `server/*-projection-reader.ts`), which is a different consumption model than the one this table describes. Whether/how the events below reach that generic layer was not re-verified in this migration — this is an omnidash-side question, out of scope for an omniintelligence-only migration. Treat the table below as historical intent, not verified live wiring, until an omnidash-side check confirms it.

Events consumed by omnidash read-model projections, as described by the source document at time of migration.

| Topic | Dash projection handler (as documented; unverified — see flag above) | Target table | Status |
|-------|------------------------|--------------|--------|
| `onex.evt.omniintelligence.quality-assessment-completed.v1` | `omniintelligence-projections.ts` (not found in current omnidash tree) | `pattern_learning_artifacts.quality_score` | Unverified |
| `onex.evt.omniintelligence.routing-feedback-processed.v1` | `omniintelligence-projections.ts` (not found in current omnidash tree) | `routing_feedback_events` | Unverified |
| `onex.evt.omniintelligence.bloom-eval-completed.v1` | None currently | `bloom_eval_results` (planned) | GAP — no consumer or table exists yet |

---

## Dashboard-Visible Events

> Same flag as above — the omnidash surfaces below were not re-verified against the current omnidash tree during this migration.

Events documented as appearing in omnidash dashboard surfaces (after projection), as described by the source document at time of migration.

| Topic | Dashboard surface | Status |
|-------|-------------------|--------|
| `onex.evt.omniintelligence.quality-assessment-completed.v1` | `/patterns` quality score column | Unverified |
| `onex.evt.omniintelligence.routing-feedback-processed.v1` | `routing_feedback_events` read-model | Unverified |

---

## Internal-Only Events

Events produced or consumed within this repo's pipeline that are not intended for external consumers.

| Topic | Notes |
|-------|-------|
| `onex.cmd.omniintelligence.pattern-lifecycle-transition.v1` | Produced by promotion/demotion nodes, consumed by lifecycle node — internal pipeline command |

---

## Deprecated or Drained Events

Events that had constants defined in omnidash but have no live producer in this repo, as of the last omnidash-side audit reflected in the source document. Not re-verified against the current omnidash tree during this migration (see the flag above).

| Topic | Status | Notes |
|-------|--------|-------|
| `onex.evt.omniintelligence.pattern-discovered.v1` | Dead — no producer (as last audited) | No omniintelligence node publishes this topic. |
| `onex.evt.omniintelligence.session-outcome.v1` | Dead — no producer (as last audited) | No producer exists here. |
| `onex.evt.omniintelligence.eval-completed.v1` | Misnamed — actual topic is `bloom-eval-completed.v1` (as last audited) | Naming reconciliation pending, per source document. |
| `routing.feedback` (bare legacy topic) | Drain pending (as last audited) | Legacy bare topic without `onex.*` prefix. `NodeRoutingFeedbackEffect` was updated to subscribe to `onex.evt.omniclaude.routing-feedback.v1`. |

---

## DLQ Pattern

All effect nodes route failed messages to `{topic}.dlq` with:

- Original envelope preserved
- Error message and timestamp
- Retry count and service metadata
- Secret sanitization via `LogSanitizer`

---

## Correlation ID Tracing

All operations thread `correlation_id: UUID` through:

1. Input model
2. Handler logging (`extra={"correlation_id": ...}`)
3. Kafka payloads (`"correlation_id": str(correlation_id)`)
4. Output models (preserved for downstream)
