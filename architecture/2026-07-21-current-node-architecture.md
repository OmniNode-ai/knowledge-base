---
type: architecture
status: accepted
date: "2026-07-21"
title: "ONEX Current Node Architecture"
topics: [omnibase-infra, current, node]
refs: []
---


# ONEX Current Node Architecture

This document describes the current ONEX node architecture. All nodes follow the declarative 4-node pattern: contract-driven, handler-based, container-injected. The runtime host (`RuntimeHostProcess`) loads and runs all nodes within a single process.

---

## Table of Contents

1. The Four Node Types
2. Standard Directory Structure
3. Node Inventory by Functional Group
   - Registration Family
   - Validation Pipeline
   - LLM Inference and Embeddings
   - Session Lifecycle
   - Checkpoint Pipeline
   - Event Ledger
   - Release Readiness Handshake (RRH)
   - Pattern Lifecycle
   - Auxiliary Effects
4. Complete Node Summary Table
5. Node Type Distribution

---

## 1. The Four Node Types

ONEX enforces a strict **4-node architecture** pattern:

| Node Type | Contract `node_type` | Purpose | Output Constraint |
|-----------|---------------------|---------|-------------------|
| **EFFECT** | `EFFECT_GENERIC` | External I/O (APIs, DB, filesystem, Kafka) | `events[]` |
| **COMPUTE** | `COMPUTE_GENERIC` | Pure deterministic transformations | `result` (required) |
| **REDUCER** | `REDUCER_GENERIC` | FSM state transitions; emits intents | `intents[]` |
| **ORCHESTRATOR** | `ORCHESTRATOR_GENERIC` | Workflow coordination; only type that publishes | `events[]`, `intents[]` |

**Communication Pattern**:

```text
EFFECT (I/O) → events → COMPUTE → REDUCER (FSM) → intents → ORCHESTRATOR
                                                                   │
                                                         handler_routing → EFFECT
```

**Key Invariants**:
- ORCHESTRATOR nodes **cannot** return `result`; they emit events or intents only
- COMPUTE nodes **must** return `result`; they have no side effects
- REDUCER nodes are pure: `delta(state, event) -> (new_state, intents[])`
- EFFECT nodes own all external I/O; handlers cannot publish events directly

---

## 2. Standard Directory Structure

```text
nodes/<node_name>/
├── __init__.py           # Public exports
├── contract.yaml         # ONEX contract (REQUIRED — source of truth)
├── node.py              # Declarative node class; no custom logic
├── models/              # Node-specific Pydantic models
│   ├── __init__.py
│   └── model_<name>.py
├── registry/            # Dependency injection registry
│   ├── __init__.py
│   └── registry_infra_<node_name>.py
├── handlers/            # Handler implementations (where logic lives)
│   ├── __init__.py
│   └── handler_<name>.py
└── dispatchers/         # Dispatcher adapters (optional)
    ├── __init__.py
    └── dispatcher_<name>.py
```

**There are no `v1_0_0/` subdirectories.** Versioning is done through `contract_version` fields in `contract.yaml`, not through directory nesting.

---

## 3. Node Inventory by Functional Group

### 3.1 Registration Family

The registration family handles the full lifecycle of ONEX node registration: from introspection through Consul and PostgreSQL backend persistence to state tracking.

**Data flow**:

```text
INTROSPECTION EVENT → NodeRegistrationOrchestrator
    → NodeRegistrationReducer (emits intents)
    → NodeRegistryEffect (dual-backend: Consul + PostgreSQL)
    → NodeRegistrationStorageEffect (storage queries)
    → NodeServiceDiscoveryEffect (service discovery backend)
```

| Node | Type | Description |
|------|------|-------------|
| `node_registration_orchestrator` | ORCHESTRATOR | Registration workflow orchestrator. Coordinates node lifecycle by calling the reducer for intents and the effect for execution. Handles the introspection → registration handshake including ACK flow. |
| `node_registration_reducer` | REDUCER | Pure reducer for the registration workflow. Processes introspection events and emits typed registration intents for Consul and PostgreSQL backends. FSM: `idle → pending → accepted → active`. |
| `node_registry_effect` | EFFECT | Dual-backend node registration. Executes registration against both Consul (service discovery) and PostgreSQL (record persistence) with partial failure support and circuit breaker protection. |
| `node_registration_storage_effect` | EFFECT | Capability-oriented storage for node registrations. Handles store, query, update, and delete operations with pluggable backend handlers (PostgreSQL). |
| `node_service_discovery_effect` | EFFECT | Service discovery operations. Provides capability-oriented service registration, deregistration, and discovery with pluggable backends (Consul, Kubernetes, Etcd). Named by capability, not technology. |

**Also in `nodes/effects/`** (standalone sub-package):

| Node | Type | Description |
|------|------|-------------|
| `effects/registry_effect` | EFFECT | Effect node for dual-backend node registration. Shares the `ModelRegistryRequest` / `ModelRegistryResponse` interface with `node_registry_effect`. (Legacy location; see `node_registry_effect` for the canonical version.) |

**Contract Registry** (tracks contract declarations from all nodes):

| Node | Type | Description |
|------|------|-------------|
| `contract_registry_reducer` | REDUCER | Reducer that consumes contract registration events from Kafka and materializes them to PostgreSQL for discovery and observability. Tracks contract registrations, heartbeats, deregistrations, and schema diffs. |
| `node_contract_persistence_effect` | EFFECT | Routes intents from `ContractRegistryReducer` to PostgreSQL handlers for contract and topic management. Supports upsert, update, deactivate, and cleanup operations. |

---

### 3.2 Validation Pipeline

The validation pipeline implements a multi-node pattern candidate validation workflow: plan → execute → adjudicate → publish verdicts → update pattern lifecycle.

**Data flow**:

```text
PATTERN CANDIDATE → NodeValidationOrchestrator
    → builds ModelValidationPlan
    → NodeValidationExecutor (runs checks: typecheck, lint, tests, risk, cost)
    → NodeValidationAdjudicator (REDUCER: aggregates results, produces PASS/FAIL/QUARANTINE)
    → NodePatternLifecycleEffect (applies verdict to tier state)
    → NodeValidationLedgerProjectionCompute (persists to validation ledger)
```

| Node | Type | Description |
|------|------|-------------|
| `node_validation_orchestrator` | ORCHESTRATOR | Orchestrator for the validation pipeline. Consumes pattern candidates, builds validation plans from the MVP check catalog, coordinates executor and adjudicator nodes, and publishes validation results. |
| `node_validation_executor` | EFFECT | Runs validation checks against a candidate. Receives a `ModelValidationPlan` and executes each planned check (typecheck, lint, unit tests, integration tests, risk assessment, cost metrics). Reports pass/fail/skip per check. |
| `node_validation_adjudicator` | REDUCER | Pure reducer for verdict production. Aggregates check results from the executor, applies scoring policy (required / recommended / informational severity), and produces a `PASS`, `FAIL`, or `QUARANTINE` verdict with score and rationale. |
| `node_validation_ledger_projection_compute` | COMPUTE | Subscribes to 3 cross-repo validation event topics and projects validation events into the `validation_event_ledger` for deterministic replay. Uses consistent Kafka position tracking for idempotency. |
| `node_pattern_lifecycle_effect` | EFFECT | Applies validation verdicts to pattern lifecycle state and computes tier transitions. Promotion tiers: `OBSERVED → SUGGESTED → VALIDATED → CANONICAL`. Demotion on `FAIL`; quarantine on repeated failures. |

**Architecture validation** (static analysis):

| Node | Type | Description |
|------|------|-------------|
| `architecture_validator` | COMPUTE | Analyzes Python source code and module structures to detect architecture violations. Validates three core rules: `ARCH-001` (no direct handler dispatch), `ARCH-002` (no circular imports), `ARCH-003` (no effect-to-reducer dependency). |

---

### 3.3 LLM Inference and Embeddings

The LLM family provides provider-agnostic inference and embedding generation with circuit breaker protection and multi-endpoint routing.

**Data flow**:

```text
INFERENCE REQUEST → NodeLlmInferenceEffect
    (routes to: OpenAI-compatible / Ollama handlers)
    → returns ModelLlmInferenceResponse (tokens, latency, trace)

EMBEDDING REQUEST → NodeLlmEmbeddingEffect
    (batch generation with retry)
    → returns ModelLlmEmbeddingResponse (vectors + dimension validation)

A/B COMPARISON → NodeBaselineComparisonCompute
    (paired baseline vs. candidate runs)
    → returns ModelAttributionRecord (cost/outcome deltas, ROI)
```

| Node | Type | Description |
|------|------|-------------|
| `node_llm_inference_effect` | EFFECT | Provider-agnostic LLM inference. Delegates to provider-specific handlers (OpenAI-compatible, Ollama) via declarative operation routing. Supports chat completions and raw completions with structured output extraction and tracing metadata. |
| `node_llm_embedding_effect` | EFFECT | Batch embedding generation via OpenAI-compatible and Ollama endpoints. Retry logic, circuit breaker protection, and dimension uniformity validation across batch outputs. |
| `node_baseline_comparison_compute` | COMPUTE | A/B baseline comparison. Takes paired baseline and candidate run results and computes cost deltas (token, time, retry savings), outcome deltas (quality improvement), and overall ROI score. Pure computation; no I/O. |

---

### 3.4 Session Lifecycle

The session lifecycle family manages pipeline run state using a filesystem-backed FSM. It tracks the complete run lifecycle from creation through completion.

**Data flow**:

```text
SESSION EVENT → NodeSessionLifecycleReducer
    (FSM: idle → run_created → run_active → run_ended)
    → emits intents → NodeSessionStateEffect
    (writes session.json and runs/{run_id}.json with atomic flock/fsync)
```

| Node | Type | Description |
|------|------|-------------|
| `node_session_lifecycle_reducer` | REDUCER | Pure reducer for session lifecycle management. Tracks the FSM `idle → run_created → run_active → run_ended` for each pipeline run. Emits intents for session index and run context writes. Supports concurrent runs. |
| `node_session_state_effect` | EFFECT | Filesystem I/O for session state. Owns all reads/writes to `~/.claude/state/` including `session.json` (with `flock`) and `runs/{run_id}.json`. Uses atomic write-tmp-fsync-rename pattern for crash safety. |

**Authorization gate** (used in session-level access control):

| Node | Type | Description |
|------|------|-------------|
| `node_auth_gate_compute` | COMPUTE | Pure compute node for work authorization decisions. Evaluates a 10-step cascade: whitelisted paths, emergency overrides, run_id validation, authorization scope checks (tools, paths, repos), and expiry. Returns `ModelAuthGateDecision` (ALLOW / DENY). |

**Intent storage** (graphs):

| Node | Type | Description |
|------|------|-------------|
| `node_intent_storage_effect` | EFFECT | Stores classified intents in Memgraph graph database. Supports querying intents by session and retrieving distribution statistics. |

---

### 3.5 Checkpoint Pipeline

The checkpoint pipeline provides pipeline state persistence across restarts, supporting resumable workflows.

**Data flow**:

```text
CHECKPOINT WRITE → NodeCheckpointValidateCompute (structural validation)
    → NodeCheckpointEffect (filesystem persistence: ~/.claude/checkpoints/{ticket_id}/{run_id}/)

CHECKPOINT READ → NodeCheckpointEffect (read operation)
    → NodeCheckpointValidateCompute (schema version, required fields, path normalization)
```

| Node | Type | Description |
|------|------|-------------|
| `node_checkpoint_effect` | EFFECT | Owns all filesystem I/O for pipeline checkpoint persistence. Supports write, read, and list operations on checkpoint YAML files stored under `~/.claude/checkpoints/{ticket_id}/{run_id}/`. |
| `node_checkpoint_validate_compute` | COMPUTE | Pure structural validation of checkpoint data. Verifies schema version, required fields, path normalization, phase-payload consistency, and commit SHA format. No filesystem access; receives pre-loaded data. |

---

### 3.6 Event Ledger

The event ledger provides an immutable audit trail for platform events, enabling complete traceability and deterministic replay.

**Data flow**:

```text
PLATFORM EVENTS (7 topics) → NodeLedgerProjectionCompute
    (projects events → ModelPayloadLedgerAppend intents)
    → NodeLedgerWriteEffect
    (idempotent PostgreSQL append via unique constraint on topic+partition+kafka_offset)
```

| Node | Type | Description |
|------|------|-------------|
| `node_ledger_projection_compute` | COMPUTE | Subscribes to 7 platform event topics. Projects events from the platform event bus into audit ledger append intents, enabling complete traceability and debugging support. |
| `node_ledger_write_effect` | EFFECT | Appends events to the PostgreSQL audit ledger with idempotent write support via unique constraint on `(topic, partition, kafka_offset)`. Duplicate events are silently skipped (returns `duplicate=True`). |

---

### 3.7 Release Readiness Handshake (RRH)

The RRH family validates that a repository meets release readiness criteria before a deployment proceeds. It gathers multi-dimensional environment data, evaluates 13 rules, and persists results as artifacts.

**Data flow**:

```text
RRH REQUEST → NodeRrhEmitEffect
    (3 independent handlers: git state, deployment targets, runtime health)
    → ModelRRHEnvironmentData
    → NodeRrhValidateCompute
    (evaluates RRH-1001 through RRH-1701 rules)
    → ModelRRHResult (PASS / FAIL / SKIP per rule)
    → NodeRrhStorageEffect
    (persists timestamped JSON artifact + symlinks: latest/{ticket}, latest/{repo})
```

| Node | Type | Description |
|------|------|-------------|
| `node_rrh_emit_effect` | EFFECT | Collects environment data for RRH validation. Three independent handlers gather: repository git state, deployment runtime targets, and runtime health metrics. |
| `node_rrh_validate_compute` | COMPUTE | Pure RRH validation. Evaluates 13 rules (`RRH-1001` through `RRH-1701`) against collected environment data using profile-driven severity and contract tightening. No I/O. |
| `node_rrh_storage_effect` | EFFECT | Persists RRH validation results as timestamped JSON artifacts and maintains convenience symlinks for quick lookup by ticket and repository. |

---

### 3.8 Pattern Lifecycle

Pattern lifecycle management is handled by `node_pattern_lifecycle_effect` (documented above in 3.2 Validation Pipeline). It applies verdicts to tier state and is invoked by the validation orchestrator.

---

### 3.9 Auxiliary Effects

| Node | Type | Description |
|------|------|-------------|
| `node_slack_alerter_effect` | EFFECT | Sends infrastructure alerts to Slack channels using either the Web API (`chat.postMessage` with threading) or incoming webhooks. Block Kit formatting, retry logic with exponential backoff, and rate limit handling. |

---

## 4. Complete Node Summary Table

| Node Directory | Node Type | Input Model | Output Model |
|----------------|-----------|-------------|--------------|
| `architecture_validator` | COMPUTE | `ModelArchitectureValidationRequest` | `ModelArchitectureValidationResult` |
| `contract_registry_reducer` | REDUCER | `ModelReducerInput` | `ModelReducerOutput` |
| `effects/registry_effect` | EFFECT | `ModelRegistryRequest` | `ModelRegistryResponse` |
| `node_auth_gate_compute` | COMPUTE | `ModelAuthGateRequest` | `ModelAuthGateDecision` |
| `node_baseline_comparison_compute` | COMPUTE | `ModelBaselineComparisonInput` | `ModelAttributionRecord` |
| `node_checkpoint_effect` | EFFECT | `ModelCheckpointEffectInput` | `ModelCheckpointEffectOutput` |
| `node_checkpoint_validate_compute` | COMPUTE | `ModelCheckpointValidateInput` | `ModelCheckpointValidateOutput` |
| `node_contract_persistence_effect` | EFFECT | `ModelIntent` | `ModelPersistenceResult` |
| `node_intent_storage_effect` | EFFECT | `ModelIntentStorageInput` | `ModelIntentStorageOutput` |
| `node_ledger_projection_compute` | COMPUTE | `ModelEventMessage` | `ModelIntent` |
| `node_ledger_write_effect` | EFFECT | `ModelPayloadLedgerAppend` | `ModelLedgerAppendResult` |
| `node_llm_embedding_effect` | EFFECT | `ModelLlmEmbeddingRequest` | `ModelLlmEmbeddingResponse` |
| `node_llm_inference_effect` | EFFECT | `ModelLlmInferenceRequest` | `ModelLlmInferenceResponse` |
| `node_pattern_lifecycle_effect` | EFFECT | `ModelLifecycleState` | `ModelLifecycleResult` |
| `node_registration_orchestrator` | ORCHESTRATOR | `ModelOrchestratorInput` | `ModelOrchestratorOutput` |
| `node_registration_reducer` | REDUCER | `ModelReducerInput` | `ModelReducerOutput` |
| `node_registration_storage_effect` | EFFECT | `ModelStorageQuery` | `ModelStorageResult` |
| `node_registry_effect` | EFFECT | `ModelRegistryRequest` | `ModelRegistryResponse` |
| `node_rrh_emit_effect` | EFFECT | `ModelRRHEmitRequest` | `ModelRRHEnvironmentData` |
| `node_rrh_storage_effect` | EFFECT | `ModelRRHStorageRequest` | `ModelRRHStorageResult` |
| `node_rrh_validate_compute` | COMPUTE | `ModelRRHValidateRequest` | `ModelRRHResult` |
| `node_service_discovery_effect` | EFFECT | `ModelServiceRegistration` | `ModelDiscoveryResult` |
| `node_session_lifecycle_reducer` | REDUCER | `ModelReducerInput` | `ModelReducerOutput` |
| `node_session_state_effect` | EFFECT | `ModelSessionIndex` | `ModelSessionStateResult` |
| `node_slack_alerter_effect` | EFFECT | `ModelSlackAlert` | `ModelSlackAlertResult` |
| `node_validation_adjudicator` | REDUCER | `ModelReducerInput` | `ModelReducerOutput` |
| `node_validation_executor` | EFFECT | `ModelValidationPlan` | `ModelExecutorResult` |
| `node_validation_ledger_projection_compute` | COMPUTE | `ModelEventMessage` | `ModelValidationLedgerEntry` |
| `node_validation_orchestrator` | ORCHESTRATOR | `ModelPatternCandidate` | `ModelValidationPlan` |

**Total: 29 documented nodes** across 4 archetypes (a curated subset). The live repository contains 123 `node_<name>/` directories under `src/omnibase_infra/nodes/` with 121 `contract.yaml` files; the additional nodes (delegation, merge-sweep, coding-agent, RSD, scope, GitHub/Gmail effects, etc.) are not enumerated in the inventory sections above. Section 3 covers the primary canonical nodes; the full census is maintained by `scripts/validate.py contracts`.

> _Verified against code on this refresh: `ls -d src/omnibase_infra/nodes/node_* | wc -l` → 123; `find src/omnibase_infra/nodes -name contract.yaml | wc -l` → 121._

---

## 5. Node Type Distribution

| Type | Count | Nodes |
|------|-------|-------|
| **EFFECT** | 16 | `effects/registry_effect`, `node_checkpoint_effect`, `node_contract_persistence_effect`, `node_intent_storage_effect`, `node_ledger_write_effect`, `node_llm_embedding_effect`, `node_llm_inference_effect`, `node_pattern_lifecycle_effect`, `node_registration_storage_effect`, `node_registry_effect`, `node_rrh_emit_effect`, `node_rrh_storage_effect`, `node_service_discovery_effect`, `node_session_state_effect`, `node_slack_alerter_effect`, `node_validation_executor` |
| **COMPUTE** | 8 | `architecture_validator`, `node_auth_gate_compute`, `node_baseline_comparison_compute`, `node_checkpoint_validate_compute`, `node_ledger_projection_compute`, `node_rrh_validate_compute`, `node_validation_ledger_projection_compute`, `node_validation_orchestrator`* |
| **REDUCER** | 4 | `contract_registry_reducer`, `node_registration_reducer`, `node_session_lifecycle_reducer`, `node_validation_adjudicator` |
| **ORCHESTRATOR** | 2 | `node_registration_orchestrator`, `node_validation_orchestrator` |

> *`node_validation_orchestrator` is classified `ORCHESTRATOR_GENERIC` in its contract; the COMPUTE count above corrects for that. The table in section 4 is authoritative.

**Corrected distribution (documented subset)**:

| Type | Count |
|------|-------|
| **EFFECT** | 16 |
| **COMPUTE** | 7 |
| **REDUCER** | 4 |
| **ORCHESTRATOR** | 2 |
| **Total** | 29 |

**Live whole-repo distribution** (all `contract.yaml` under `src/omnibase_infra/nodes/`, verified on this refresh via `find src/omnibase_infra/nodes -name contract.yaml -exec grep -h '^node_type:' {} \; | sort | uniq -c`):

| Type | Count |
|------|-------|
| **EFFECT** | 66 |
| **COMPUTE** | 29 |
| **REDUCER** | 13 |
| **ORCHESTRATOR** | 13 |
| **Total** | 121 |

> All 121 `contract.yaml` files declare a `node_type` field.

---

## Vendored Node Migration Pattern

Nodes that own projection tables ship their SQL migrations under:

```text
src/omnimarket/nodes/<node>/migrations/*.sql
```

These must be vendored into the infra repo at:

```text
docker/migrations/forward/nodes/<node>/
```

via `scripts/sync-node-migrations.sh`. The forward-migration runner discovers and applies vendored node migrations under namespaced IDs (`node:<node>:<file>`) so a clean redeploy re-creates all projection tables without manual intervention.

The `node-migration-sync` CI gate (`.github/workflows/node-migration-sync.yml`) enforces this on every PR: it re-runs the vendor `--check` against the current omnimarket `dev` tip. An un-vendored migration fails CI before merge.

See the vendored-node-migrations runbook for the full procedure.

---

## Related Documentation

| Topic | Document |
|-------|----------|
| Architecture overview and four-phase processing | [overview.md](2026-07-21-onex-runtime-overview.md) |
| Handler plugin system | ../patterns/handler_plugin_loader.md |
| Error handling patterns | ../patterns/error_handling_patterns.md |
| Circuit breaker implementation | ../patterns/circuit_breaker_implementation.md |
| Dispatcher resilience | ../patterns/dispatcher_resilience.md |
| Registration walkthrough | ../guides/registration-example.md |
| Message dispatch engine | [MESSAGE_DISPATCH_ENGINE.md](2026-07-21-message-dispatch-engine.md) |
| Vendored node migrations | ../runbooks/vendored-node-migrations.md |
| Coding standards (authoritative) | ../../CLAUDE.md |
