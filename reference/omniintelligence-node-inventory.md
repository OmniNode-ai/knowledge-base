---
type: reference
status: current
date: "2026-08-25"
title: "OmniIntelligence Node Inventory"
topics:
  - omniintelligence
  - nodes
  - node-inventory
refs:
  - architecture/omniintelligence-four-node-architecture.md
---

# OmniIntelligence Node Inventory

**Source of truth:** `pyproject.toml [project.entry-points."onex.nodes"]`
**Owner:** omniintelligence
**Last verified:** 2026-08-25 — migrated from `omniintelligence` to the knowledge base; re-parsed `pyproject.toml [project.entry-points."onex.nodes"]` directly against the live source tree and confirmed 60 entries (24 compute / 31 effect / 2 reducer / 2 orchestrator + 1 audit), matching the source document unchanged.

This inventory is sourced directly from the `[project.entry-points."onex.nodes"]` section of `pyproject.toml`.

Total registered nodes: **60** (59 four-type + `node_audit`; the total counts every `onex.nodes` entry point, audit included)

---

## Compute Nodes (pure transforms, no I/O)

| Entry point | Module path | Purpose |
|-------------|-------------|---------|
| `node_agent_behavior_eval_compute` | `omniintelligence.nodes.node_agent_behavior_eval_compute` | Evaluate agent behavior against expected scenarios |
| `node_anti_gaming_guardrails_compute` | `omniintelligence.nodes.node_anti_gaming_guardrails_compute` | Detect and flag gaming or reward-hacking patterns |
| `node_ast_extraction_compute` | `omniintelligence.nodes.node_ast_extraction_compute` | Extract AST structures from source code |
| `node_behavior_scenario_generator_compute` | `omniintelligence.nodes.node_behavior_scenario_generator_compute` | Generate behavior evaluation scenarios |
| `node_chunk_classifier_compute` | `omniintelligence.nodes.node_chunk_classifier_compute` | Classify document or code chunks |
| `node_ci_error_classifier_compute` | `omniintelligence.nodes.node_ci_error_classifier_compute` | Classify CI failure error types |
| `node_ci_fingerprint_compute` | `omniintelligence.nodes.node_ci_fingerprint_compute` | Generate fingerprints for CI failure deduplication |
| `node_code_entity_bridge_compute` | `omniintelligence.nodes.node_code_entity_bridge_compute` | Bridge code entities across representation formats |
| `node_contract_eval_compute` | `omniintelligence.nodes.node_contract_eval_compute` | Evaluate ONEX contracts for compliance |
| `node_debug_retrieval_compute` | `omniintelligence.nodes.node_debug_retrieval_compute` | Retrieve debug context for error diagnosis |
| `node_doc_retrieval_compute` | `omniintelligence.nodes.node_doc_retrieval_compute` | Retrieve relevant documentation chunks |
| `node_document_parser_compute` | `omniintelligence.nodes.node_document_parser_compute` | Parse raw documents into structured form |
| `node_execution_trace_parser_compute` | `omniintelligence.nodes.node_execution_trace_parser_compute` | Parse session execution traces |
| `node_intent_classifier_compute` | `omniintelligence.nodes.node_intent_classifier_compute` | Classify user prompt intent |
| `node_intent_cost_forecast_compute` | `omniintelligence.nodes.node_intent_cost_forecast_compute` | Forecast token cost for intent execution |
| `node_intent_drift_detect_compute` | `omniintelligence.nodes.node_intent_drift_detect_compute` | Detect drift in intent classification over time |
| `node_memory_eval_compute` | `omniintelligence.nodes.node_memory_eval_compute` | Evaluate memory store quality and coverage |
| `node_pattern_extraction_compute` | `omniintelligence.nodes.node_pattern_extraction_compute` | Extract pattern candidates from code and traces |
| `node_pattern_learning_compute` | `omniintelligence.nodes.node_pattern_learning_compute` | ML pattern learning pipeline |
| `node_pattern_matching_compute` | `omniintelligence.nodes.node_pattern_matching_compute` | Match patterns against code or events |
| `node_plan_reviewer_multi_compute` | `omniintelligence.nodes.node_plan_reviewer_multi_compute` | Multi-model plan review (compute) |
| `node_scoring_reducer_compute` | `omniintelligence.nodes.node_scoring_reducer_compute` | Reduce multiple score signals into composite score |
| `node_semantic_analysis_compute` | `omniintelligence.nodes.node_semantic_analysis_compute` | Semantic code analysis |
| `node_success_criteria_matcher_compute` | `omniintelligence.nodes.node_success_criteria_matcher_compute` | Match patterns against success criteria |

---

## Effect Nodes (Kafka, PostgreSQL, external I/O)

| Entry point | Module path | Purpose |
|-------------|-------------|---------|
| `node_ci_failure_tracker_effect` | `omniintelligence.nodes.node_ci_failure_tracker_effect` | Record CI failure events to PostgreSQL |
| `node_claude_hook_event_effect` | `omniintelligence.nodes.node_claude_hook_event_effect` | Process Claude Code hook events from omniclaude |
| `node_code_crawler_effect` | `omniintelligence.nodes.node_code_crawler_effect` | Crawl source code repositories |
| `node_compliance_evaluate_effect` | `omniintelligence.nodes.node_compliance_evaluate_effect` | Evaluate and record compliance checks |
| `node_context_item_writer_effect` | `omniintelligence.nodes.node_context_item_writer_effect` | Write context items to storage |
| `node_crawl_scheduler_effect` | `omniintelligence.nodes.node_crawl_scheduler_effect` | Schedule and manage crawl jobs |
| `node_cursor_hook_event_effect` | `omniintelligence.nodes.node_cursor_hook_event_effect` | Process Cursor IDE hook events from omnicursor |
| `node_debug_fix_record_effect` | `omniintelligence.nodes.node_debug_fix_record_effect` | Record debug fix events |
| `node_dispatch_outcome_eval_effect` | `omniintelligence.nodes.node_dispatch_outcome_eval_effect` | Evaluate omniclaude dispatch worker outcomes |
| `node_doc_staleness_detector_effect` | `omniintelligence.nodes.node_doc_staleness_detector_effect` | Detect stale documents and emit staleness events |
| `node_document_fetch_effect` | `omniintelligence.nodes.node_document_fetch_effect` | Fetch documents from external sources |
| `node_embedding_generation_effect` | `omniintelligence.nodes.node_embedding_generation_effect` | Generate and store embeddings |
| `node_enforcement_feedback_effect` | `omniintelligence.nodes.node_enforcement_feedback_effect` | Record enforcement feedback events |
| `node_evidence_collection_effect` | `omniintelligence.nodes.node_evidence_collection_effect` | Collect and persist evidence artifacts |
| `node_git_repo_crawler_effect` | `omniintelligence.nodes.node_git_repo_crawler_effect` | Crawl git repositories for code analysis |
| `node_gmail_intent_evaluator_effect` | `omniintelligence.nodes.node_gmail_intent_evaluator_effect` | Evaluate email-based intent signals |
| `node_linear_crawler_effect` | `omniintelligence.nodes.node_linear_crawler_effect` | Crawl Linear tickets for context |
| `node_llm_routing_decision_effect` | `omniintelligence.nodes.node_llm_routing_decision_effect` | Record LLM routing decisions |
| `node_navigation_retriever_effect` | `omniintelligence.nodes.node_navigation_retriever_effect` | Retrieve navigation context |
| `node_pattern_compliance_effect` | `omniintelligence.nodes.node_pattern_compliance_effect` | Record pattern compliance events |
| `node_pattern_demotion_effect` | `omniintelligence.nodes.node_pattern_demotion_effect` | Demote patterns (validated to deprecated) |
| `node_pattern_feedback_effect` | `omniintelligence.nodes.node_pattern_feedback_effect` | Record session outcomes and rolling-window metrics |
| `node_pattern_learning_effect` | `omniintelligence.nodes.node_pattern_learning_effect` | Pattern extraction pipeline (contract-only, no node.py) |
| `node_pattern_lifecycle_effect` | `omniintelligence.nodes.node_pattern_lifecycle_effect` | Atomic pattern lifecycle transitions with audit trail |
| `node_pattern_projection_effect` | `omniintelligence.nodes.node_pattern_projection_effect` | Project pattern events to omnidash read-model |
| `node_pattern_promotion_effect` | `omniintelligence.nodes.node_pattern_promotion_effect` | Promote patterns (provisional to validated) |
| `node_pattern_storage_effect` | `omniintelligence.nodes.node_pattern_storage_effect` | Persist patterns to PostgreSQL |
| `node_protocol_handler_effect` | `omniintelligence.nodes.node_protocol_handler_effect` | Handle protocol-level events |
| `node_routing_feedback_effect` | `omniintelligence.nodes.node_routing_feedback_effect` | Process routing feedback events |
| `node_storage_router_effect` | `omniintelligence.nodes.node_storage_router_effect` | Route storage operations to correct backend |
| `node_watchdog_effect` | `omniintelligence.nodes.node_watchdog_effect` | Monitor and emit watchdog health events |

---

## Reducer Nodes (FSM state management)

| Entry point | Module path | Purpose |
|-------------|-------------|---------|
| `node_doc_promotion_reducer` | `omniintelligence.nodes.node_doc_promotion_reducer` | Document promotion FSM |
| `node_policy_state_reducer` | `omniintelligence.nodes.node_policy_state_reducer` | Policy enforcement state FSM |

---

## Orchestrator Nodes (workflow coordination)

| Entry point | Module path | Purpose |
|-------------|-------------|---------|
| `node_bloom_eval_orchestrator` | `omniintelligence.nodes.node_bloom_eval_orchestrator` | Bloom evaluation orchestration (contract `node_type: orchestrator`; `node.py` class is `NodeBloomEvalEffect`) |
| `node_pattern_assembler_orchestrator` | `omniintelligence.nodes.node_pattern_assembler_orchestrator` | Pattern assembly from execution traces |

---

## Audit Node

| Entry point | Module path | Purpose |
|-------------|-------------|---------|
| `node_audit` | `omniintelligence.nodes.audit` | AST purity and I/O violation audit enforcement |

---

## Notes

- `node_pattern_learning_effect` has no `node.py` — it is a contract-only node wired by the dispatch engine. See [ONEX Four-Node Architecture in OmniIntelligence](../architecture/omniintelligence-four-node-architecture.md#contract-only-nodes).
- Node types (Compute / Effect / Reducer / Orchestrator) are inferred from naming convention and base class. The `pyproject.toml` entry-points list does not encode type.
- For Kafka topics associated with each node, see [OmniIntelligence Event Surface](omniintelligence-event-surface.md).

## Unregistered Node Directories

The following node directories exist in `src/omniintelligence/nodes/` with full implementations (contract.yaml, handlers/, models/, node.py) but are **not registered** in `pyproject.toml [project.entry-points."onex.nodes"]`. They are in-progress or deferred work and not yet part of the active node registry:

| Directory | Notes |
|-----------|-------|
| `node_anti_gaming_alerter_effect` | Anti-gaming alerter effect (unregistered) |
| `node_intelligence_orchestrator` | Intelligence orchestrator (unregistered; distinct from `NodeIntelligenceOrchestrator` in orchestrator table) |
| `node_intelligence_reducer` | Intelligence reducer (unregistered; distinct from registered reducers) |
| `node_intent_graph_reducer` | Intent graph reducer (unregistered) |
| `node_objective_ab_framework_compute` | Objective A/B framework compute (unregistered) |
| `node_quality_scoring_compute` | Quality scoring compute (unregistered; distinct from `NodeQualityScoringCompute`) |
| `node_tcb_generation_compute` | TCB generation compute (unregistered) |

These directories should be registered in `pyproject.toml` or removed in a future cleanup PR.
