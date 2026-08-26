---
type: architecture
status: accepted
date: "2026-08-25"
title: "ONEX Four-Node Architecture in OmniMemory"
topics:
  - omnimemory
  - node-archetypes
  - architecture
refs:
  - guides/omnimemory-market-migration-boundary.md
  - reference/omnimemory-memory-data-ownership.md
---

# ONEX Four-Node Architecture in OmniMemory

> **Version**: 0.2.3
> **Last Updated**: 2026-08-25 — migrated from `omnimemory` to the knowledge base. During migration, the EFFECT node table and data-flow diagram below were corrected: they still listed `node_intent_event_consumer_effect`, which had already been removed from `omnimemory` (its consumer role was consolidated into `omnimarket` to eliminate a duplicate-consumer race on the same topic). Verified via `git ls-files src/omnimemory/nodes/` against the live `omnimemory` tree on 2026-08-25: 14 node directories, 13 with `contract.yaml` (`node_memory_consolidator_reducer` is a contract-less stub).
> **Status**: Active

## Overview

OmniMemory uses the ONEX 4-node architecture to organize all memory system
operations. Every piece of code in `src/omnimemory/nodes/` belongs to one of
four archetypes:

- **EFFECT** — touches the outside world (storage, event bus, APIs)
- **COMPUTE** — transforms data without side effects (analysis, similarity)
- **REDUCER** — aggregates and consolidates state (statistics, merging)
- **ORCHESTRATOR** — coordinates multi-step workflows (lifecycle, routing)

The pattern enforces unidirectional data flow and a clean separation between
I/O and logic. Handlers hold all business logic; nodes are thin wrappers that
wire container injection to the handler.

---

## Data Flow

```
  Kafka / External API
         |
         v
  +--------------+     +--------------+     +--------------+     +------------------+
  |    EFFECT    | --> |   COMPUTE    | --> |   REDUCER    | --> |  ORCHESTRATOR    |
  |              |     |              |     |              |     |                  |
  | intent_      |     | semantic_    |     | navigation_  |     | memory_lifecycle |
  | storage_     |     | analyzer     |     | history_     |     | _orchestrator    |
  | effect       |     | _compute     |     | reducer      |     |                  |
  |              |     |              |     |              |     |                  |
  | intent_query |     | similarity_  |     |              |     | agent_           |
  | _effect      |     | compute      |     |              |     | coordinator_     |
  |              |     |              |     |              |     | orchestrator     |
  |              |     |              |     |              |     |                  |
  | intent_query |     |              |     |              |     |                  |
  | _effect      |     |              |     |              |     |                  |
  |              |     |              |     |              |     |                  |
  | memory_      |     |              |     |              |     |                  |
  | retrieval_   |     |              |     |              |     |                  |
  | effect       |     |              |     |              |     |                  |
  |              |     |              |     |              |     |                  |
  | memory_      |     |              |     |              |     |                  |
  | storage_     |     |              |     |              |     |                  |
  | effect       |     |              |     |              |     |                  |
  +--------------+     +--------------+     +--------------+     +------------------+
         |                    |                    |                       |
         v                    v                    v                       v
    Memgraph /           Embedding /          Aggregated             Lifecycle
    PostgreSQL /         Similarity           Statistics             Commands
    Qdrant               Vectors
```

Data flows left to right. EFFECT nodes produce raw data from external sources;
COMPUTE nodes transform it into enriched representations; REDUCER nodes
consolidate results into aggregated state; ORCHESTRATOR nodes coordinate
workflows and lifecycle decisions.

---

## Node Types in OmniMemory

### EFFECT Nodes

EFFECT nodes own all external I/O: event bus subscription, database reads and
writes, API calls, and file system operations. They are the only nodes allowed
to produce side effects.

**Characteristics:**
- Subscribe to Kafka topics or query external APIs
- Write to Memgraph, PostgreSQL, Qdrant, or the filesystem
- Include circuit breakers, retry logic, and DLQ routing
- Emit observability events on success and failure
- Delegate business logic entirely to handlers

**OmniMemory EFFECT nodes:**

| Directory | Handler | Responsibility |
|-----------|---------|----------------|
| `nodes/node_intent_storage_effect/` | `HandlerIntentStorageAdapter` | Writes intent records to the graph store |
| `nodes/node_intent_query_effect/` | `HandlerIntentQuery` | Queries stored intents, returns results over the event bus |
| `nodes/node_memory_retrieval_effect/` | `HandlerMemoryRetrieval` | Retrieves memory records from Qdrant, PostgreSQL, and Memgraph |
| `nodes/node_memory_storage_effect/` | `AdapterFilesystem` | Persists memory payloads to the filesystem adapter |
| `nodes/node_kreuzberg_parse_effect/` | `HandlerKreuzbergParse` | Sends documents to the Kreuzberg parser service for text extraction |
| `nodes/node_agent_learning_retrieval_effect/` | *(none — see note)* | Contract + models + ranking helpers only; no handler class exists |
| `nodes/node_persona_storage_effect/` | `HandlerPersonaStorage` | Persists persona signals and profile updates |

> **`node_intent_event_consumer_effect` no longer exists in this repository.**
> Its Kafka-consumer role for `intent-classified.v1` was consolidated into
> `omnimarket` to eliminate a duplicate-consumer race on the same topic. Do
> not reintroduce it as a live entry in this table without first confirming
> against `src/omnimemory/nodes/` and the event-bus node-package list in the
> runtime plugin reference.

> **`node_agent_learning_retrieval_effect` is not implemented.** The table
> previously listed a `HandlerAgentLearningRetrieval` class; no such class has
> ever existed in `src/`. The package ships the contract, the request/response
> models, and four pure ranking/query-building helpers. A prior fix removed
> the contract's route to the phantom class; the node still declares a subscribe
> topic with nothing behind it, which is tracked separately.

### COMPUTE Nodes

COMPUTE nodes transform data. They have no persistent side effects — all
external calls (embedding APIs, LLM endpoints) are mediated through injected
provider protocols, keeping the node logic deterministic and testable.

**Characteristics:**
- Accept strongly-typed request models, return response models
- Delegate to providers via `ProtocolEmbeddingProvider` / `ProtocolLLMProvider`
- Lazy-initialize handlers on first `execute()` call
- Convert all exceptions to error response objects — never raise to callers
- No direct Kafka or database imports

**OmniMemory COMPUTE nodes:**

| Directory | Node Class | Responsibility |
|-----------|------------|----------------|
| `nodes/node_semantic_analyzer_compute/` | `NodeSemanticAnalyzerCompute` | Generates embeddings, extracts entities, runs full semantic analysis |
| `nodes/node_similarity_compute/` | `NodeSimilarityCompute` | Computes vector similarity between memory records |
| `nodes/node_persona_builder_compute/` | (handler-only; `contract.yaml` routes to `omnimemory.nodes.node_persona_builder_compute.handlers.handler_persona_classify`) | Classifies persona signals into an updated persona profile |

### REDUCER Nodes

REDUCER nodes aggregate state. They consume outputs from EFFECT and COMPUTE
nodes and produce consolidated views: statistics, merged records, rolled-up
counters.

**OmniMemory REDUCER nodes:**

| Directory | Responsibility | Status |
|-----------|----------------|--------|
| `nodes/node_navigation_history_reducer/` | Aggregates and persists agent navigation history | Runnable (has `contract.yaml`) |
| `nodes/node_memory_consolidator_reducer/` | Merges and deduplicates overlapping memory records | Stub — no `contract.yaml`; scaffolded skeleton only |

> `node_statistics_reducer` was decommissioned in an earlier cleanup pass and is no longer present in the repository.

### ORCHESTRATOR Nodes

ORCHESTRATOR nodes coordinate multi-step workflows. They issue commands to
other nodes, manage lifecycle transitions, and coordinate cross-agent activity.
They do not perform I/O directly — they delegate to EFFECT nodes.

**OmniMemory ORCHESTRATOR nodes:**

| Directory | Handler | Responsibility |
|-----------|---------|----------------|
| `nodes/node_memory_lifecycle_orchestrator/` | `HandlerMemoryTick`, `HandlerMemoryArchive`, `HandlerMemoryExpire` | Drives time-based lifecycle: ticking expiry counters, archiving old memories, expiring stale records |
| `nodes/node_agent_coordinator_orchestrator/` | (in progress) | Routes memory requests across agents, coordinates cross-service memory operations |

> `node_persona_lifecycle_orchestrator` was decommissioned in an earlier cleanup pass (never had a `contract.yaml`) and is no longer present in the repository.

---

## Lessons: Semantic Index and Multi-Store Query Latency

**Embed the semantic unit that captures a conclusion, not an activity.** When `node_semantic_analyzer_compute` generates embeddings for the semantic index, what gets embedded determines what similarity search returns. Embedding decisions — what was concluded — returns more actionable results for a "find similar prior work" query than embedding tasks — what was attempted. A task description and its outcome can diverge; the outcome is usually what a later search is actually looking for.

**Multi-store synthesis is latency-sensitive.** `node_memory_retrieval_effect` queries Qdrant, PostgreSQL, and Memgraph as three independent backends — each serves a distinct query pattern (semantic similarity, point/range lookup, graph traversal) that the others don't serve efficiently. Querying them sequentially sums their individual latencies; querying them in parallel with a timeout keeps end-to-end retrieval latency bounded by the slowest backend instead of the total, and prevents one slow backend from blocking a retrieval that needs a bounded response time.

---

## Naming Convention

All nodes follow the pattern `Node<Name><Type>` mapped to files named
`node_<name>_<type>.py`. Directories follow `node_<name>_<type>/`.

```
nodes/
  node_semantic_analyzer_compute/      # directory: node_<name>_<type>
    node_semantic_analyzer_compute.py  # file: node_<name>_<type>.py
    handlers/
      handler_semantic_compute.py
    models/
      model_semantic_analyzer_compute_request.py
      model_semantic_analyzer_compute_response.py
```

Handler class names follow `Handler<Name>` — they are not suffixed with the
node type because a handler may be shared across node types.

---

## Declaring an EFFECT Node

All ONEX nodes in omnimemory inherit from the base classes in
`omnimemory.nodes.base`, which provide container injection. The node itself
is a thin shell — all logic lives in the handler.

```python
# src/omnimemory/nodes/my_storage_effect/node_my_storage_effect.py

from omnimemory.nodes.base import BaseEffectNode, ContainerType
from .handlers import HandlerMyStorage
from .models import ModelMyStorageRequest, ModelMyStorageResponse


class NodeMyStorageEffect(BaseEffectNode):
    """EFFECT node for my-storage operations.

    Thin wrapper: all business logic lives in HandlerMyStorage.
    """

    def __init__(
        self,
        container: ContainerType,
        handler: HandlerMyStorage | None = None,
    ) -> None:
        super().__init__(container)
        self._handler = handler or HandlerMyStorage(container=container)

    async def execute(
        self,
        request: ModelMyStorageRequest,
    ) -> ModelMyStorageResponse:
        """Delegate to the handler. Convert exceptions to error responses."""
        try:
            return await self._handler.execute(request)
        except Exception as e:
            return ModelMyStorageResponse(
                status="error",
                error_message=f"{type(e).__name__}: {e}",
            )
```

The handler receives its dependencies via constructor injection:

```python
# src/omnimemory/nodes/my_storage_effect/handlers/handler_my_storage.py

from omnibase_core.container import ModelONEXContainer

from omnimemory.nodes.my_storage_effect.models import (
    ModelMyStorageRequest,
    ModelMyStorageResponse,
)


class HandlerMyStorage:
    def __init__(self, container: ModelONEXContainer) -> None:
        self._container = container
        self._initialized = False

    async def initialize(self, config: ModelMyStorageConfig) -> None:
        # set up DB connection, circuit breaker, etc.
        self._initialized = True

    async def execute(
        self,
        request: ModelMyStorageRequest,
    ) -> ModelMyStorageResponse:
        # Business logic here; no Kafka imports allowed (see ARCH-002)
        ...
```

---

## Runtime Wiring

The `MessageDispatchEngine` in `omnimemory.runtime.dispatch_handlers` wires
Kafka topics to the correct EFFECT node handlers at startup:

```python
from omnimemory.runtime.dispatch_handlers import create_memory_dispatch_engine

engine = create_memory_dispatch_engine(
    intent_consumer=intent_consumer_handler,
    intent_query_handler=intent_query_handler,
    publish_callback=event_bus.publish,
    publish_topics={"intent_query": "onex.evt.omnimemory.intent-query-response.v1"},  # Runtime env prefix (e.g., dev., prod.) is added by the topic builder
)
# engine is now frozen and ready for dispatch
```

The engine registers 4 handler slots covering 6 topic routes. EFFECT node
handlers receive deserialized `ModelEventEnvelope` objects; they never parse
raw Kafka bytes directly.

---

## Key Invariants

- **Handlers hold all logic.** Nodes are thin shells: `__init__` + `execute`.
- **No backwards data flow.** ORCHESTRATOR nodes do not call EFFECT nodes
  directly for reads — they issue commands that EFFECT nodes consume.
- **No direct transport imports in handlers.** See
  [ARCH-002 Kafka Abstraction](omnimemory-arch-002-kafka-abstraction.md).
- **All models are frozen Pydantic `BaseModel`.** No `Any` types.
- **Errors become response objects.** Nodes catch exceptions and return error
  response models; they do not propagate exceptions to callers.
