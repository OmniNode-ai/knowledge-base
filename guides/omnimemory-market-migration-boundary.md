---
type: guide
status: current
date: "2026-08-25"
title: "OmniMemory → OmniMarket Node Migration Boundary"
topics:
  - omnimemory
  - omnimarket
  - migration
  - nodes
refs:
  - architecture/omnimemory-four-node-architecture.md
  - reference/omnimemory-memory-data-ownership.md
---

# Market Migration Boundary

**Owner:** `omnimemory`
**Last verified:** 2026-08-25 — migrated from `omnimemory` to the knowledge base. This document previously framed the migration entirely as a future plan ("Migration Goal: Migrate all 15 runnable ONEX nodes..."). That framing is now stale: verified directly against both repositories' source trees, `omnimarket` already carries a directory counterpart for every one of the 15 originally-targeted nodes and depends on the omnimemory package (`omninode-memory==0.17.1` in `omnimarket`'s `pyproject.toml` at verification time). Two of the 15 have already been fully removed from `omnimemory` as dead duplicates once their `omnimarket` copies became canonical (see "Already Resolved" below); the remaining 13 are still present in `omnimemory`'s own tree, not yet cleaned up. This document is rewritten below to describe that as an **in-progress migration**, not a not-yet-started one — see the caveat at the end of "Already Resolved" for what was not independently re-verified.
**Verification:** `git ls-files src/omnimemory/nodes/` (omnimemory) and a directory-name match against `src/omnimarket/nodes/` (omnimarket), both run 2026-08-25.

---

## Migration Goal

Migrate all 15 originally-targeted runnable ONEX nodes from `omnimemory` into `omnimarket`, leaving `omnimemory` as a **pure primitives package**: models, protocols, and storage adapters. This is partially complete — see "Current State" below.

Once complete, nodes auto-wire via the ONEX runtime's `importlib.metadata` discovery using the `onex.nodes` entry point — exactly like every other omnimarket node. `omnimemory` retains the `onex.domain_plugins` entry point (`PluginMemory`) for runtime plugin lifecycle management.

---

## Current State (verified 2026-08-25)

| Node | Status |
|------|--------|
| `node_filesystem_crawler_effect` | **Resolved.** Copied into `omnimarket` (live there under a different handler/topic naming), then the `omnimemory` original was deleted as an unwired dead duplicate. |
| `node_intent_event_consumer_effect` | **Resolved.** Its consumer role on the `intent-classified` topic was consolidated into `omnimarket` to remove a duplicate-consumer race; the `omnimemory` original is gone from that repository's git history. |
| All 13 other nodes in the table below | `omnimarket` already has a directory counterpart for each (verified by name match). Whether each `omnimarket` copy is the live/wired one, a duplicate awaiting `omnimemory`-side cleanup like the two rows above, or independently diverged was **not verified per-node** this pass — that requires checking each node's wiring/dispatch registration in both repositories individually, which is beyond what this migration pass verified. Treat "present in omnimarket" as confirmed; treat "which side is canonical" as unconfirmed for these 13. |

This reframes the migration from "not started" to "further along than this document previously stated, with an unresolved cleanup question for 13 of the 15 nodes."

---

## What Stays in omnimemory

These components are the permanent core of omnimemory. They do not move to omnimarket.

### Protocols

All protocol interfaces remain in `src/omnimemory/protocols/`:

- `ProtocolEmbedding`, `ProtocolEmbeddingProvider`
- `ProtocolHandlerIntent`
- `ProtocolIntentGraphAdapter`
- `ProtocolSecretsProvider`
- `base_protocols.py`, `data_models.py`, `error_models.py`

**Why:** Handlers in omnimarket depend on these protocols for dependency injection. Moving protocols to omnimarket would create a circular import (`omnimarket` depends on `omnimemory` protocols — if protocols moved to omnimarket, `omnimemory` adapters would need to import from omnimarket, reversing the dependency direction).

### Models

All domain models remain in `src/omnimemory/models/`:

- Crawl models (`ModelCrawlTickCommand`, `ModelDocumentDiscoveredEvent`, etc.)
- Memory models (`ModelMemoryItem`, `ModelMemoryQuery`, `ModelSimilarityResult`, etc.)
- Persona models (`ModelPersonaSignal`, `ModelUserPersonaV1`, etc.)
- Foundation, intelligence, scoring, subscription, events, service, config models

**Why:** Models are the shared language between omnimarket handlers and omnibase_infra adapters. Keeping them in omnimemory means both parties can depend on `omninode-memory` without circularity.

### Adapters

All concrete protocol implementations remain in omnimemory (per-node `adapters/` subdirectories):

- Qdrant adapter (`handlers/adapters/`)
- Filesystem adapter (`handlers/adapters/`, `nodes/node_memory_storage_effect/adapters/`)
- Memgraph adapter (`nodes/node_intent_storage_effect/adapters/`)
- Archive adapters (`nodes/node_memory_lifecycle_orchestrator/adapters/`)
- Persona storage adapters (`nodes/node_persona_storage_effect/adapters/`)

**Why:** Adapters are concrete infrastructure implementations. They belong with the domain package that owns the storage contract, not in omnimarket's portable workflow layer.

### Runtime Infrastructure

- `bootstrap.py`, `settings.py`, `secrets.py`
- `runtime/` — plugin entry point, DI container wiring (`PluginMemory`)
- `audit/` — I/O audit tooling
- `enums/`, `errors/`, `tools/`, `utils/`

### Storage Services

Qdrant, Memgraph, Valkey, and Kreuzberg remain omnimemory-owned. See [Memory Data Ownership](../reference/omnimemory-memory-data-ownership.md).

---

## What Moves to omnimarket

All 15 originally-targeted nodes (those with a `contract.yaml` when this boundary was drafted) move to `omnimarket/src/omnimarket/nodes/`. As of 2026-08-25, `omnimarket` already has a directory present for every row below; the "In omnimemory" column reflects whether the `omnimemory` original is still there too (see "Current State" above for what that does and does not confirm):

| Node | Type | Domain | In omnimarket | In omnimemory |
|------|------|--------|----------------|----------------|
| `node_filesystem_crawler_effect` | EFFECT | Crawl | Yes | No — removed |
| `node_kreuzberg_parse_effect` | EFFECT | Crawl | Yes | Yes |
| `node_memory_storage_effect` | EFFECT | Memory | Yes | Yes |
| `node_memory_retrieval_effect` | EFFECT | Memory | Yes | Yes |
| `node_memory_lifecycle_orchestrator` | ORCHESTRATOR | Memory | Yes | Yes |
| `node_semantic_analyzer_compute` | COMPUTE | Intelligence | Yes | Yes |
| `node_similarity_compute` | COMPUTE | Intelligence | Yes | Yes |
| `node_agent_coordinator_orchestrator` | ORCHESTRATOR | Coordination | Yes | Yes |
| `node_agent_learning_retrieval_effect` | EFFECT | Learning | Yes | Yes |
| `node_intent_event_consumer_effect` | EFFECT | Intent | Yes | No — removed |
| `node_intent_query_effect` | EFFECT | Intent | Yes | Yes |
| `node_intent_storage_effect` | EFFECT | Intent | Yes | Yes |
| `node_navigation_history_reducer` | REDUCER | Navigation | Yes | Yes |
| `node_persona_builder_compute` | COMPUTE | Persona | Yes | Yes |
| `node_persona_storage_effect` | EFFECT | Persona | Yes | Yes |

**What moves with each node:** handler implementations, node-local models, `contract.yaml`, clients, registry, utils, validators.

**What stays in omnimemory:** each node's `adapters/` subdirectory (concrete protocol implementations injected at runtime via DI).

**Stub node (no contract.yaml) — not migrated:**
- `node_memory_consolidator_reducer` — skeleton only; no `contract.yaml`

**Decommissioned nodes — not migrated, not present:**
- `node_persona_lifecycle_orchestrator` — removed; never had a `contract.yaml`
- `node_persona_retrieval_effect` — removed; never had a `contract.yaml`

---

## Migration Waves

| Wave | Nodes | Status (2026-08-25) |
|------|-------|----------------------|
| 1 | `node_similarity_compute`, `node_persona_builder_compute`, `node_semantic_analyzer_compute` | Present in omnimarket; `omnimemory` cleanup unconfirmed per-node |
| 2 | `node_memory_storage_effect`, `node_memory_retrieval_effect`, `node_persona_storage_effect`, `node_persona_retrieval_effect`, `node_agent_learning_retrieval_effect` | Present in omnimarket; `node_persona_retrieval_effect` was separately decommissioned from `omnimemory` (never had a `contract.yaml` there) |
| 3 | `node_filesystem_crawler_effect`, `node_kreuzberg_parse_effect` | `node_filesystem_crawler_effect` resolved (see "Current State"); `node_kreuzberg_parse_effect` present in omnimarket, `omnimemory` cleanup unconfirmed |
| 4 | `node_intent_storage_effect`, `node_intent_query_effect`, `node_intent_event_consumer_effect` | `node_intent_event_consumer_effect` resolved (see "Current State"); the other two present in omnimarket, `omnimemory` cleanup unconfirmed |
| 5 | `node_memory_lifecycle_orchestrator`, `node_navigation_history_reducer`, `node_agent_coordinator_orchestrator` | Present in omnimarket; `omnimemory` cleanup unconfirmed per-node |

Pre-work: add `omninode-memory` dependency to omnimarket (blocked Wave 1) — **done**. `omnimarket`'s `pyproject.toml` pins `omninode-memory==0.17.1` as of 2026-08-25.

---

## Import Path Changes After Migration

| Before migration | After migration |
|-----------------|----------------|
| `omnimemory.nodes.<node>.*` | `omnimarket.nodes.<node>.*` |
| `omnimemory.protocols.*` | `omnimemory.protocols.*` (unchanged) |
| `omnimemory.models.*` | `omnimemory.models.*` (unchanged) |

`contract.yaml` schema refs must update:
- `omnimemory.nodes.<node>.models.*` → `omnimarket.nodes.<node>.models.*`
- `omnimemory.nodes.<node>.handlers.*` → `omnimarket.nodes.<node>.handlers.*`

---

## Circular Dependency Guard

| Rule | Rationale |
|------|-----------|
| `omnimarket` MAY import `omnimemory` (for protocols, models, adapters) | Correct direction: market node handlers depend on domain primitives |
| `omnimemory` MUST NOT import `omnimarket` | Would create circular dependency |
| Adapters stay in omnimemory and are injected at runtime via DI | Preserves the protocol-adapter-handler separation |

---

## Post-Migration omnimemory State

After all 15 nodes move:

- `nodes/` retains only adapter subdirectories and stub nodes
- The `onex.node_package` entry point (if present) is removed from `pyproject.toml`
- The `onex.domain_plugins` entry point (`PluginMemory`) remains
- Package description: "OmniNode memory primitives — models, protocols, and storage adapters for Qdrant, Memgraph, and PostgreSQL backends."

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| Runtime consumers pick up stale entry points from old omnimemory | After migration, remove `onex.node_package` from omnimemory and re-deploy via Kafka rebuild command |
| Schema refs in `contract.yaml` not updated | Update all `schema_ref: omnimemory.nodes.*` to `omnimarket.nodes.*` per node |
| Adapter injection breaks post-migration | Verify via golden chain tests per node; DI container (omnimemory bootstrap) must inject adapters into omnimarket handler constructors |
| `omnimarket/pyproject.toml` does not yet depend on omnimemory | Add `omninode-memory` to omnimarket dependencies before Wave 1 |
