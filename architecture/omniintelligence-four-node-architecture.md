---
type: architecture
status: accepted
date: "2026-08-25"
title: "ONEX Four-Node Architecture in OmniIntelligence"
topics:
  - omniintelligence
  - node-archetypes
  - architecture
refs:
  - reference/omniintelligence-node-inventory.md
  - reference/omniintelligence-event-surface.md
---

# ONEX Four-Node Architecture in OmniIntelligence

> **Scope**: OmniIntelligence-specific node inventory, data flow, and implementation patterns. For base class definitions, handler output constraints, and FSM/workflow contracts, see the platform's core ONEX Four-Node Architecture reference.
> **Last Updated**: 2026-08-25 — migrated from `omniintelligence` to the knowledge base. Node-type counts and dispatch handler/route counts were re-verified against the live source tree during migration (`pyproject.toml [project.entry-points."onex.nodes"]`: 60 entries, 24 compute / 31 effect / 2 reducer / 2 orchestrator + 1 audit) and matched the source document unchanged.

---

## Four Node Types

| Type | Base Class | Allowed Handler Outputs | Count | Example Node |
|------|-----------|------------------------|-------|--------------|
| **Compute** | `NodeCompute` | `result` only | 24 | `NodeQualityScoringCompute` |
| **Effect** | `NodeEffect` | `events[]` only | 31 | `NodeClaudeHookEventEffect` |
| **Reducer** | `NodeReducer` | `projections[]` only | 2 | `NodeDocPromotionReducer` |
| **Orchestrator** | `NodeOrchestrator` | `events[]`, `intents[]` | 2 | `NodePatternAssemblerOrchestrator` |

> Counts reflect `[project.entry-points."onex.nodes"]` in `pyproject.toml` (60 total registered: 59 four-type + 1 Audit node). For the full inventory see [OmniIntelligence Node Inventory](../reference/omniintelligence-node-inventory.md).

---

## Node Topology

### Claude Code Hook Pipeline

```
Claude Code Extension
    |
    v  (omniclaude publishes)
{env}.onex.cmd.omniintelligence.claude-hook-event.v1
    |
    v
NodeClaudeHookEventEffect
    |
    +-- UserPromptSubmit --> NodeIntentClassifierCompute (pure compute, no I/O)
    |                             |
    |                             v
    |                    {env}.onex.evt.omniintelligence.intent-classified.v1
    |                             |
    |                             v
    |                        omnimemory (graph storage, separate service)
    |
    +-- Stop event -----> {env}.onex.cmd.omniintelligence.pattern-learning.v1
    |
    +-- all others -----> handle_no_op() (success, no output)
```

### Pattern Learning Pipeline

```
{env}.onex.cmd.omniintelligence.pattern-learning.v1
    |
    v
NodePatternLearningEffect (contract-only, wired via dispatch engine)
    |  dispatch_handler_pattern_learning.py
    |
    +-- NodePatternExtractionCompute (extract candidates from trace)
    +-- NodePatternLearningCompute (ML learning pipeline)
    |
    v
{env}.onex.evt.omniintelligence.pattern-learned.v1
    |
    v
NodePatternStorageEffect
    |
    v
PostgreSQL (via AdapterPatternStore / PostgresRepositoryRuntime)
```

### Pattern Lifecycle Pipeline

```
NodePatternPromotionEffect --publishes--> {env}.onex.cmd.omniintelligence.pattern-lifecycle-transition.v1
NodePatternDemotionEffect  --publishes-->                       |
                                                                |
                                                                v
                                                NodePatternLifecycleEffect
                                                (subscribes; applies all transitions atomically)
                                                    |
                                                    +-- CANDIDATE -> PROVISIONAL
                                                    +-- PROVISIONAL -> VALIDATED
                                                    +-- VALIDATED -> DEPRECATED
                                                    |
                                                    v
                                                PostgreSQL (atomic transition with audit trail)
                                                Kafka (emits: pattern-lifecycle-transitioned.v1)
```

### Intelligence Orchestration Pipeline

> **Registration note**: `node_intelligence_orchestrator` and `node_intelligence_reducer` are
> **not** registered in `pyproject.toml [project.entry-points."onex.nodes"]` (see
> [Node Inventory — Unregistered Node Directories](../reference/omniintelligence-node-inventory.md#unregistered-node-directories)). The
> orchestrator's `handler_receive_intent` is nonetheless wired into the live dispatch engine
> (`runtime/dispatch_handlers.py`), so this pipeline runs via dispatch rather than via a
> registered standalone node entry-point.

```
Kafka (code-analysis / document-ingestion / pattern-learning / quality-assessment commands)
    |
    v
NodeIntelligenceOrchestrator
    |
    v
NodeIntelligenceReducer (FSM: INGESTION | PATTERN_LEARNING | QUALITY_ASSESSMENT)
    |
    +-- QUALITY_ASSESSMENT --> NodeQualityScoringCompute
    |                          NodeSemanticAnalysisCompute
    |
    +-- PATTERN_LEARNING   --> NodePatternMatchingCompute
    |                          NodePatternExtractionCompute
    |
    +-- INGESTION          --> NodeExecutionTraceParserCompute
                               NodeSuccessCriteriaMatcherCompute
```

---

## Contract-Only Nodes

Three node directories have no `node.py` and are driven entirely by `contract.yaml` plus
handler modules wired through the dispatch engine:

| Directory | Registered in `pyproject.toml`? |
|-----------|----------------------------------|
| `node_pattern_learning_effect` | Yes |
| `node_intent_graph_reducer` | No (unregistered — see [Node Inventory — Unregistered Node Directories](../reference/omniintelligence-node-inventory.md#unregistered-node-directories)) |
| `node_tcb_generation_compute` | No (unregistered) |

The registered example is `NodePatternLearningEffect`.

**Why**: The pattern learning handler coordinates multiple compute nodes (extraction, learning),
reads from PostgreSQL, and publishes to Kafka. The handler logic is complex enough that wrapping
it in a thin-shell `node.py` adds no value — the handler function IS the implementation.

**How it works**: `PluginIntelligence.wire_dispatchers()` calls
`create_intelligence_dispatch_engine()` in `runtime/dispatch_handlers.py`, which reads publish
topics from the node's `contract.yaml` and wires `dispatch_handler_pattern_learning.py` as the
route handler. The `MessageDispatchEngine` routes incoming Kafka messages to the correct handler
without needing a node class as intermediary.

**When to use contract-only**:
- Handler coordinates multiple compute nodes in a non-trivial pipeline
- Handler has real dependencies (repository, Kafka producer) that need explicit wiring
- A node.py shell would be a thin pass-through with no additional structure

**When to use a node.py thin shell**:
- The delegation boundary provides meaningful structure (e.g., injecting a handler class)
- The node participates in protocol-based testing (`isinstance` checks)
- The node type needs to be discoverable for introspection/registration purposes

---

## PluginIntelligence: Node Discovery and Wiring

`PluginIntelligence` (in `runtime/plugin.py`) is the entry point for the ONEX kernel. It
implements `ProtocolDomainPlugin` and runs five sequential bootstrap phases:

```
1. should_activate()   — activation gate; returns True if OMNIINTELLIGENCE_DB_URL is set
2. initialize()        — creates PostgreSQL pool + RegistryMessageType
2.5 validate_handshake() — B1: verifies DB ownership; B2: verifies schema fingerprint
3. wire_handlers()     — registers handlers with the container
4. wire_dispatchers()  — builds MessageDispatchEngine (30 register_handler / 39 register_route calls in runtime/dispatch_handlers.py; 1 handler + 3 routes register conditionally inside an `if _projection_store is not None:` block — the pattern-projection handler)
5. start_consumers()   — subscribes to all intelligence Kafka topics
```

**Topic Discovery (contract-driven)**:

`collect_subscribe_topics_from_contracts()` in `runtime/contract_topics.py` scans all effect
node `contract.yaml` files at import time and collects `event_bus.subscribe_topics`. This list
drives Kafka subscriptions — there are no hardcoded topic lists in `plugin.py`.

Source contracts scanned:
- `node_claude_hook_event_effect/contract.yaml`
- `node_pattern_feedback_effect/contract.yaml`
- `node_pattern_learning_effect/contract.yaml`
- `node_pattern_lifecycle_effect/contract.yaml`
- `node_pattern_storage_effect/contract.yaml`

**Dispatch engine routes**:

`create_intelligence_dispatch_engine()` in `runtime/dispatch_handlers.py` issues 30
`engine.register_handler(...)` and 39 `engine.register_route(...)` calls (1 handler and 3 routes
are inside the `if _projection_store is not None:` block that wires the pattern-projection handler;
`_projection_store` is resolved from `pattern_query_store`/`pattern_upsert_store`), drawing
on the 14 `runtime/dispatch_handler_*.py` modules. The table below shows the original core routes;
for the full event surface see [OmniIntelligence Event Surface](../reference/omniintelligence-event-surface.md).

| Route | Handler | Source Topic |
|-------|---------|--------------|
| `intelligence-claude-hook-route` | `route_hook_event()` | `claude-hook-event.v1` |
| `intelligence-tool-content-route` | `route_hook_event()` | `tool-content.v1` |
| `intelligence-session-outcome-route` | `record_session_outcome()` | `session-outcome.v1` |
| `intelligence-pattern-lifecycle-route` | `apply_transition()` | `pattern-lifecycle-transition.v1` |
| `intelligence-pattern-learned-route` | pattern storage handler | `pattern-learned.v1` |
| `intelligence-pattern-discovered-route` | pattern storage handler | `evt.pattern.discovered.v1` |
| `intelligence-pattern-learning-route` | `create_pattern_learning_dispatch_handler()` | `pattern-learning.v1` |
| … (24 additional routes) | code analysis, compliance, crawl scheduling, routing feedback, and more | see `runtime/dispatch_handlers.py` |

**Activation gate**: `PluginIntelligence.should_activate()` returns `True` only if
`OMNIINTELLIGENCE_DB_URL` is set. Without a database URL, no consumers start and all
handlers remain unwired.

---

## Node Implementation Decision Tree

```
Is the operation pure computation with no external I/O?
    YES --> Compute node
        Examples: QualityScoring, SemanticAnalysis, IntentClassifier

Does the node manage FSM state transitions?
    YES --> Reducer node
        Example: IntelligenceReducer (INGESTION / PATTERN_LEARNING / QUALITY_ASSESSMENT FSMs)

Does the node coordinate other nodes without doing I/O itself?
    YES --> Orchestrator node
        Registered examples: PatternAssemblerOrchestrator, BloomEvalOrchestrator
        (note: node_bloom_eval_orchestrator declares node_type: orchestrator but its
         node.py class is NodeBloomEvalEffect)

Does the node read/write external systems (Kafka, PostgreSQL)?
    YES --> Effect node
        Simple delegation? --> node.py thin shell (most effect nodes)
        Complex multi-node pipeline? --> Contract-only effect (NodePatternLearningEffect)
```

**Handler location rule**: All business logic — error handling, retry, logging, validation —
belongs in handler functions or classes under `handlers/`. The `node.py` file contains only
type declarations and a single delegation call.

---

## Kafka Topic Naming

All intelligence topics follow: `{env}.onex.{kind}.omniintelligence.{event-name}.v{n}`

- `kind=cmd` for commands / inputs
- `kind=evt` for events / outputs

| Topic | Direction | Produced By | Consumed By |
|-------|-----------|-------------|-------------|
| `{env}.onex.cmd.omniintelligence.claude-hook-event.v1` | In | omniclaude | `NodeClaudeHookEventEffect` |
| `{env}.onex.cmd.omniintelligence.tool-content.v1` | In | omniclaude | `NodeClaudeHookEventEffect` |
| `{env}.onex.evt.omniintelligence.intent-classified.v1` | Out | `NodeClaudeHookEventEffect` | omnimemory |
| `{env}.onex.cmd.omniintelligence.pattern-learning.v1` | In/Out | `NodeClaudeHookEventEffect` (Stop) | `NodePatternLearningEffect`, `NodeIntelligenceOrchestrator` |
| `{env}.onex.evt.omniintelligence.pattern-learned.v1` | Out | `NodePatternLearningEffect` | `NodePatternStorageEffect` |
| `{env}.onex.evt.omniintelligence.pattern-stored.v1` | Out | `NodePatternStorageEffect` | downstream |
| `{env}.onex.evt.omniintelligence.pattern-promoted.v1` | Out | `NodePatternStorageEffect`, `NodePatternPromotionEffect` | downstream |
| `{env}.onex.evt.omniintelligence.pattern-deprecated.v1` | Out | `NodePatternDemotionEffect` | downstream |

---

**See Also**: the platform's core ONEX Four-Node Architecture reference — base class definitions, handler output constraints, and FSM/workflow subcontract reference.
