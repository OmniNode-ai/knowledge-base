---
type: architecture
status: accepted
date: "2026-09-01"
title: "OmniMarket Generation Pipeline Boundary"
topics:
  - omnimarket
  - generation
  - onex-runtime
refs: []
---

<!-- Migrated from omnimarket:docs/migrations/sea-generation-pipeline-routing.md on 2026-09-01 -->

# SEA Generation Pipeline Migration Boundary

The self-extending-agent (SEA) capability set included a bespoke imperative
node-generation loop. The generation engine and its two transport/runtime
wrappers had been split across three modules in the SEA repo:

- `pipeline/consumer.py` — the `GenerationConsumer` loop (LLM call, retry on
  validation failure, prior-success context lookup, cost calculation, emit).
- `pipeline_local/consumer_local.py` — a local-tier subclass (Track B): same
  loop bound to a local GPU endpoint with a distinct consumer group and a
  zero-marginal-cost basis.
- `pipeline/kafka_runner.py` — a cloud-tier daemon (Track A): a raw Kafka
  consumer/producer loop with SIGINT/SIGTERM handlers that drove the same engine.

That capability now has a permanent canonical home in OmniMarket's
`node_generation_consumer`. This document records the capability-to-canonical
boundary so the portable generation logic lives in one authoritative place and
transport/lifecycle is owned by the runtime, not by a hand-rolled daemon.

## Capability -> Canonical OmniMarket surface

| SEA capability | Canonical home |
| --- | --- |
| Main generation loop (LLM call + bounded retry on validation failure) | `node_generation_consumer` handler `HandlerGenerationConsumer.handle` — one async handler over the event envelope, dispatched by the runtime. The bounded retry loop runs over the contract-declared `max_attempts`. |
| Local tier (the former `consumer_local.py` subclass / Track B) | A routing intent, not a subclass: the local backend is the `local-coder` bifrost backend resolved from the routing-authority contract overlay. The local tier's zero-marginal cost basis comes from the canonical cost-pricing contract, not a hardcoded string. |
| Cloud tier (the former `kafka_runner.py` daemon / Track A) | The cloud backend (e.g. `cloud-gemini-flash`) is resolved from the same routing-authority overlay when the escalation ladder advances. Transport/lifecycle (consume, produce, offset commit, graceful shutdown) is owned by the node runtime; the node only declares its topics in `contract.yaml` and implements `handle`. There is no raw `KafkaConsumer`/`KafkaProducer` and no signal handler in the node. |
| Endpoint + api-key resolution | `resolve_generation_endpoint` resolves `endpoint_url + provider + served_model_id + api_key_ref` per-model from the bifrost delegation contract overlay keyed by the contract `endpoint_ref`. Endpoints are never read from an `LLM_*` environment variable; a shared bare env cannot serve multiple providers. Fail-closed on any missing field. |
| Per-run inference cost | `_calculate_cost` prices measured tokens through the canonical cost-pricing contract (`omnimarket/cost/cost_pricing.yaml`) for `(provider, served_model_id)` — no hardcoded source constant. |
| Usage-source provenance | `_aggregate_usage_source` returns MEASURED when any attempt carries provider-reported usage, otherwise ESTIMATED when any attempt is locally estimated, otherwise UNKNOWN; no silent ESTIMATED downgrade. |
| Lifecycle / topics | Subscribe + publish topics are declared in `node_generation_consumer/contract.yaml` (`event_bus.subscribe_topics` / `publish_topics`); the node owns no transport literals. |

## What Market owns

OmniMarket owns the canonical generation pipeline end to end through one node:

| Node | Role | Boundary |
| --- | --- | --- |
| `node_generation_consumer` | Orchestrator | Generates an ONEX node from a natural-language task, validates it (invoking the canonical validator platform — it does not own validation logic), retries on failure, and emits the benchmark, deploy, and registration events. Endpoint/model/tier resolution is delegated to the routing authority; the node records the authority's decision and never selects the next model itself. |

## Swappability and enforcement

Both tiers — local and cloud — resolve their provider, endpoint, model, and
api-key reference from the routing contract deep-merged with the user overlay. A
tier is swapped by editing the overlay (repoint a backend, override its
`endpoint_url` / `model_name` / `secret_ref`): no code change, no environment
variable, no CLI shell-out. Endpoints are never read from environment variables.

The structural parity between the canonical node and the prior SEA generation
loop is enforced by
`tests/unit/nodes/node_generation_consumer/test_sea_generation_routing_parity.py`.
The exhaustive per-tier endpoint-resolution proof (local vLLM and cloud Gemini
resolving to distinct URLs from the contract, fail-closed, no env-var endpoint)
lives in
`tests/unit/nodes/node_generation_consumer/test_endpoint_routing_authority.py`.

## Runtime-proven boundary

The canonical node is wired and reachable at runtime: its consumer group is in a
`Stable` state with a live member on the deployed lanes, has committed offsets
against `onex.cmd.omnimarket.node-generation-requested.v1`, and carries zero
consumer lag. The generation capability therefore has a proven canonical runtime
path, not merely a source-present node.

## Standalone SEA copies

The three SEA modules remain load-bearing within the SEA repo itself: the
in-process `GenerationConsumer` class still backs several SEA-internal surfaces
(the demo entrypoint, the model-comparison experiment runner, the agent demo and
tool surface, the delegation executor, and the eval runner) whose own
canonicalization is tracked by later phases of the migration. Deleting the SEA
copies standalone would break those still-imperative SEA surfaces and is
therefore deferred to the repo decommission phase, after every dependent SEA
surface has its own canonical home. The generation **capability** is routed and
proven canonically here; the SEA file removal is a repo-archival step, not a
parity step.
