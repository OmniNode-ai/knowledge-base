---
type: architecture
status: accepted
date: "2026-08-25"
title: "Delegation Dispatch Architecture"
topics:
  - omnimarket
  - delegation
  - llm-routing
refs:
  - architecture/delegation-routing-contract.md
---

# Delegation Dispatch Architecture

> **Last verified:** 2026-08-25, migrated from `omnimarket` to the knowledge base. The escalation tier ladder below was corrected during migration: the source document described a 3-tier ladder (`local` / `cheap_cloud` / `frontier_api`) ending in Claude Sonnet and Claude Haiku backends. Both Anthropic backends were removed from the live routing contract before this migration — the org holds no Anthropic API key (Claude Code access is OAuth-only), so `resolve_api_key('llm.anthropic.api_key')` returns `None` in every lane and the tier terminated `no_routable_backend_for_task` on every escalation. The live ladder is 4 tiers, confirmed against `src/omnimarket/configs/routing_tiers.yaml`.

OmniMarket's delegation path routes a caller's prompt to the cheapest capable
backend and escalates automatically when quality gates fail.

## Dispatch path

```
Caller (omniclaude skill / Codex adapter)
  │
  ▼
node_delegate_skill_orchestrator  (effect handler, contract.yaml)
  │  publishes: onex.cmd.omnimarket.delegate-skill.v1
  │
  ▼
node_delegation_orchestrator  (orchestrator, owned by omnimarket)
  │  route: onex.cmd.omnibase-infra.delegation-request.v1
  │
  ▼
node_llm_delegation_call_effect  (effect handler)
  │  dispatches via: DirectCurl posts endpoint_url VERBATIM
  │
  ▼
Backend (local vLLM/SGLang / cloud API)
  │
  ▼
node_delegation_quality_gate_reducer  (reducer, FSM transition)
  │  on pass: onex.evt.omnibase-infra.delegation-completed.v1
  │  on fail: triggers escalation emit
  │
  ▼
node_delegate_skill_orchestrator  collects terminal event and returns result
```

An earlier version of the dispatch path included bespoke port objects
(`source_tool: delegate-skill-runtime-port`) that owned HTTP client lifecycle
outside the canonical handler boundary. Those ports were removed; the
canonical effect handler now owns the full dispatch.

## endpoint_url verbatim rule

Every backend in `src/omnimarket/configs/bifrost_delegation.yaml` carries a
`endpoint_url` that is the **complete, final URL** including the full chat path
(e.g. `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`).
The call site posts this value verbatim — no in-code construction, append,
rstrip, or path-resolver exists. A bare base URL (no chat path) is a
misconfiguration and the resolver fails closed.

For site-local backends the `endpoint_url` is `null` in the repo default; the
`endpoint_url_env` key names the environment variable (or overlay file key)
that must hold the **complete** URL. The overlay file is typically
`~/.omninode/delegation/bifrost_overrides.yaml`.

## Escalation gate sequence

When a quality gate fails the orchestrator emits a
`onex.evt.omnimarket.delegation-escalation-requested.v1` event. The escalation
path tries tiers in the order defined by `routing_tiers.yaml`, cheapest first:

1. `local` tier — vLLM/SGLang models on the local inference server (`<onex-host>`), zero marginal API cost
2. `cheap_cloud` tier — metered hosted APIs (Gemini Flash/Pro via Google AI Studio and Vertex)
3. `cheap_frontier` tier — a free-tier frontier-quality model via OpenRouter (Qwen3-Coder-480B), when `OPENROUTER_API_KEY` is configured; sits between `cheap_cloud` and the ceiling to offer frontier-quality output at zero marginal cost
4. `claude` tier — the ceiling slot. Every task class's `escalation_policy.tier_order` and the handler's cost-tier map key on the literal tier name `claude`, but this is a stable slot identifier, not a provider claim — the org has no Anthropic key, so the ceiling backend is whichever HTTP frontier backend (Gemini, GLM, or an OpenRouter model) is currently proven reachable. `routing_tiers.yaml`'s own changelog comments record each repoint and why the prior backend was dropped; read that file for the current pin rather than treating any provider name here as fixed.

Each tier is attempted at most once. If all tiers are exhausted without a
passing quality gate the orchestrator emits
`onex.evt.omnimarket.delegate-skill-failed.v1`.

The escalation emit publisher is wired on the dispatch path so that
escalation events are visible to downstream projections
(`node_llm_delegation_projection`) even when the final attempt succeeds.

## per-backend max_tokens

Each backend entry in `bifrost_delegation.yaml` carries a `max_tokens` field
that caps the output-token budget for that backend. When the caller omits
`max_tokens` from the delegation request the orchestrator resolves the
effective value from the selected backend's ceiling. An explicit caller value
is capped at that ceiling. The contract-level `maximum: 200000` field is the
absolute schema bound; the per-backend ceiling is typically lower — for
example the local code backend and the Gemini ceiling backend are both
pinned to 65536, while the cheap_cloud Gemini Flash backend is capped at
8192 (the provider's real output limit for that model family).

See `bifrost_delegation.yaml` for current per-backend values.

## Related nodes

| Node | Archetype | Role |
| --- | --- | --- |
| `node_delegate_skill_orchestrator` | Orchestrator | Consumer-facing entry point |
| `node_delegation_orchestrator` | Orchestrator | Internal dispatch coordinator |
| `node_delegation_routing_reducer` | Reducer | Selects backend from routing tiers |
| `node_delegation_quality_gate_reducer` | Reducer | Evaluates result against criteria |
| `node_llm_delegation_call_effect` | Effect | Posts request to backend endpoint |
| `node_delegation_ab_runner` | Compute | A/B routing experiment runner |
| `node_llm_delegation_projection` | Projection | Materializes delegation event stream |

## Related configuration

- `src/omnimarket/configs/bifrost_delegation.yaml` — backend definitions, per-backend max_tokens
- `src/omnimarket/configs/routing_tiers.yaml` — tier escalation ladder
- `~/.omninode/delegation/bifrost_overrides.yaml` — local endpoint overlay (not committed)
