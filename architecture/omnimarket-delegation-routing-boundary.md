---
type: architecture
status: accepted
date: "2026-09-01"
title: "OmniMarket Delegation Routing Boundary"
topics:
  - omnimarket
  - delegation
  - llm-routing
refs: []
---

<!-- Migrated from omnimarket:docs/migrations/sea-delegation-routing.md on 2026-09-01 -->

# SEA Delegation Routing Migration Boundary

The self-extending-agent (SEA) capability set included a research-harness
escalation ladder for model delegation. That capability has a permanent canonical
home in OmniMarket's delegation node surface. This document records the
capability-to-canonical-surface boundary so the portable workflow logic lives in
one authoritative place.

## Capability -> Canonical OmniMarket surface

| Capability | Canonical home |
| --- | --- |
| Tier ladder, per-tier budgets | `configs/routing_tiers.yaml` + the task-class overlay `configs/task_class_contracts.v1.yaml` + the bifrost endpoint overlay. Parsed by `node_delegation_routing_reducer.models.model_delegation_config.parse_delegation_config_yaml`. Tiers, retry budgets, providers, endpoints, models, and api-key references are declared in the contract overlay, not built imperatively. |
| Escalate / terminate verdict + next-tier resolution | `node_delegation_escalation_decision_compute` (`HandlerEscalationDecision`) for the deterministic verdict, plus `node_delegation_routing_reducer` (`next_eligible_tier` / `tier_max_retries` / `describe_no_higher_tier_available`) for next-tier and per-tier-budget resolution. Tier execution runs through the canonical HTTP inference effect `node_llm_delegation_call_effect`, not a shelled CLI. |
| Delegation lifecycle events | Delegation topics declared in `node_delegation_orchestrator/contract.yaml`; escalation events emitted by `handler_delegation_workflow`. Topics are contract-sourced. |
| Generation + readiness validation | The canonical generation validator invoked by `node_generation_consumer` (`semantic_validation.py`). Validation logic lives in the validator platform; the generation consumer invokes it. |

## What Market owns

OmniMarket owns the canonical delegation escalation ladder end to end:

| Node | Role | Boundary |
| --- | --- | --- |
| `node_delegation_routing_reducer` | Reducer | Pure routing: maps a request to a tier/model/endpoint/key resolved from the contract overlay. Owns `next_eligible_tier`, `tier_max_retries`, and the ladder-exhaustion reason. |
| `node_delegation_escalation_decision_compute` | Compute | Pure deterministic escalate-or-terminate verdict (budget, retryability, ladder exhaustion). Zero I/O. |
| `node_delegation_orchestrator` | Orchestrator | Drives the correlation-keyed delegation FSM, resolves config-dependent inputs from the routing reducer, and delegates the verdict to the escalation compute. |
| `node_llm_delegation_call_effect` | Effect | HTTP inference side-effect boundary. The only out-of-process call; no shelled CLI. |

## Swappability and enforcement

Every tier — including the ceiling — resolves its provider, endpoint, model, and
api-key reference from the routing contract deep-merged with the user overlay. A
tier is swapped by editing the overlay (repoint a backend, override its
`endpoint_url` / `model_name` / `secret_ref`): no code change, no environment
variable, no CLI shell-out. Endpoints are never read from environment variables.
The escalation-ladder parity between the canonical nodes above and the prior
research-harness behavior is proven by the delegation parity integration test
under `tests/integration/golden_chain/`.
