---
type: adr
status: proposed
date: "2026-06-18"
title: "ADR-0008: Delegation Config Authority and Budget-Aware Tier Cost"
adr_id: ADR-0008
topics: [delegation, routing, config-authority, secrets, multi-tenant, cost-model, bifrost]
refs:
  - doctrine/truth-must-be-proven.md
  - doctrine/fail-fast-and-loud.md
  - doctrine/authoritative-projections-own-truth.md
supersedes: []
superseded_by: []
---

# ADR-0008: Delegation Config Authority and Budget-Aware Tier Cost

## Context

OmniNode's delegation layer routes each unit of work down a tier ladder
(`local → cheap_cloud → cheap_frontier → claude`), trying the cheapest capable
backend first and escalating only when a tier's output fails the task-class
contract. The mechanism is canonical and bus-native:

```
delegation command (bus)
  → node_delegation_orchestrator
  → node_llm_delegation_routing_compute        (classify task_class)
  → node_delegation_routing_reducer            (load routing_tiers.yaml ladder)
  → node_llm_delegation_call_effect            (resolve backend, httpx POST)   ← "Bifrost" lives here
  → node_delegation_quality_gate_reducer       (task_class_contracts.v1.yaml: accept | escalate)
  → node_delegation_routing_feedback_reducer   (outcome → routing feedback)
  → node_projection_delegation                 (materialize terminal events → dashboard read surface)
terminal events:
  onex.evt.omnibase-infra.delegation-completed.v1 / delegation-failed.v1
  onex.evt.omnimarket.delegation-escalation-triggered.v1
```

**"Bifrost" is not a proxy.** In this codebase it is the routing-authority +
egress-resolution layer: the `bifrost_delegation.yaml` contract, its loader
(`config_loader_bifrost_delegation.py`), and the resolver
(`delegation_backend_resolution.py`). Backends carry **direct provider URLs**
(`api.anthropic.com`, `openrouter.ai`, `generativelanguage.googleapis.com`,
`api.z.ai`), and `node_llm_delegation_call_effect` →
`handler_inference_intent.py` POSTs straight to the resolved complete URL via
`httpx`. There is no gateway hop.

Two product requirements forced this ADR:

1. **OmniNode is a product others deploy, not just our own runtime.** The
   delegation config must be provider-agnostic and multi-tenant. Each tenant
   chooses their own providers, keys, models, and frontier ceiling.
2. **The cost/savings story must be honest per tenant.** A subscription ceiling
   (e.g. Claude Code) is **not** free at the margin — escalation consumes a
   finite usage budget, and overloading it costs real money (overage / plan
   upgrade / throttling). A flat `$0.015/1k` constant cannot model that, and it
   cannot model that one tenant meters their ceiling while another subscribes.

### What the committed contract carries today (verified 2026-06-18)

- Ceiling tier `claude` → backend `cloud-sonnet` =
  `https://api.anthropic.com/v1/chat/completions`, `secret_ref:
  llm.anthropic.api_key`, `api_key_env: ANTHROPIC_API_KEY`
  (`bifrost_delegation.yaml:94-115`, `routing_tiers.yaml:159-176`). This is the
  committed **repo default**, set by the ticket that removed the shelled
  `cli-claude` backend. It **directly contradicts** the platform policy
  "ANTHROPIC_API_KEY is never required; OAuth only."
- `cloud-vertex-gemini` and AI-Studio `cloud-gemini-flash` are both
  committed. Vertex is a legitimate *product* option, but its presence as a live
  default is a site-specific choice, not a universal default.
- Site-specific endpoint values resolve from a **local file overlay**
  (`~/.omninode/delegation/bifrost_overrides.yaml`), not from the store
  (`delegation_backend_resolution.py:32-33`).
- Secret **values** resolve through `ProtocolSecretStore`, but the
  resolver **defaults to an env-backed store** (`AdapterEnvSecretStore`); it only
  resolves from the secrets-manager-backed store when one is injected at deploy
  (`secret_store_resolver.py:6-20, 42-113`).
- Cost is computed in the projection as `cost_n_usd` from a versioned **pricing
  manifest** — flat per-token, no budget/subscription concept
  (`handler_projection_delegation.py`).

---

## Decision

### D1 — The committed contract is a capability skeleton; per-deployment values live in the store

`bifrost_delegation.yaml`, `routing_tiers.yaml`, and `task_class_contracts.v1.yaml`
that ship in git declare **structure only**: backend ids, capabilities, tiers,
escalation order, task-class DoD, and **logical `secret_ref` / endpoint-ref
names**. They MUST NOT carry any deployment-specific reality — no enabled-provider
selection, no API keys, no tenant model choices, no tenant cost/budget figures.

Universal public-cloud URL **defaults** may remain in the committed contract
(they are not secret), but they are defaults, overridable per tenant, never the
tenant's effective truth.

### D2 — Resolution authority is the secrets-manager-backed store, not env vars or a committed/hand-edited overlay

Every per-deployment value — complete endpoint URLs, API keys, enabled providers,
model selection, and the tier cost model — resolves from the configured store at
the effect boundary, per tenant/lane. The local-file overlay pattern
(`bifrost_overrides.yaml`) is transitional and is replaced by a store-backed
overlay. The env-backed `ProtocolSecretStore` default and the `api_key_env`
migration field are retired once the secrets-manager-backed store is the deployed
default.

The existing fail-closed discipline is preserved: a resolved endpoint must be the
**complete** URL (incl. `/v1/chat/completions`); a bare base fails closed.
Store entries therefore hold complete URLs, never bases.

### D3 — Tier cost is **typed**, not a flat per-token constant

`routing_tiers.yaml` gains a per-tier **cost type**, replacing the bare
`cost_per_1k_tokens`:

| Cost type | Meaning | Marginal cost model |
|-----------|---------|---------------------|
| `free_local` | self-hosted inference (local vLLM) | ≈ 0 marginal (compute already owned) |
| `metered` | pay-per-token cloud API | `rate_usd_per_1k × tokens` |
| `budgeted` | flat-fee subscription with a finite usage budget (e.g. Claude Code) | within budget: consumes headroom (tracked); at/over budget: `overage_rate_usd_per_1k × tokens`. Implied amortized rate = `plan_fee ÷ budget_tokens`. |

The cost-type, rate, budget cap, and overage rate are **per-tenant values from
the store** (D2), not committed constants.

### D4 — The frontier ceiling is a per-tenant config choice, resolved like every other tier

The frontier ceiling is a per-tenant **config** choice, resolved through the
**same contract-driven inference path as every other tier**: provider, endpoint,
auth, and model all come from the routing contract ⊕ store. There is no open
design question here. For **our** deployment the ceiling is **Claude Code**, typed
`budgeted` (D3). Claude runs on whatever the system is configured to use, exactly
like any other tier — the provider/auth mechanism is deployment configuration, not
an architectural decision to litigate.

The hardcoded Anthropic-API-key HTTP backend as the **committed ceiling
default** is the **defect to remove** — not an architecture to debate. The
committed default MUST NOT bind `ANTHROPIC_API_KEY` (or any tenant-specific
provider/auth) as the ceiling; the ceiling backend resolves per tenant from
config like every other tier, and fails closed when unconfigured.

### D5 — Savings are priced at the tenant's real ceiling economics

The savings number the dashboard reports is:

```
savings = Σ over delegated calls [ (ceiling-tier cost for those tokens) − (winning-tier cost) ]
```

where ceiling-tier cost uses the tenant's typed cost model (D3). For a `budgeted`
ceiling, the dashboard additionally surfaces **budget consumption and headroom**
as first-class signals — "X% of the Claude Code budget used this period;
delegation preserved Y% of it" — because for a subscription that is the signal
that predicts real incremental spend, not a per-call dollar figure.

---

## Alternatives Considered

- **Keep the flat `cost_per_1k_tokens` and treat the subscription ceiling as $0.**
  Rejected: dishonest — a subscription has a finite budget; overload costs money.
- **Delete Vertex / non-default providers from the contract.** Rejected (this was
  an earlier, us-centric conclusion now overturned): the product must support all
  providers; only the tenant-specific *binding* leaves git, not the capability.
- **Keep ANTHROPIC_API_KEY as the committed ceiling default.** Rejected: violates
  the OAuth-only platform policy and bakes our metered-API choice into every
  tenant's default.

---

## Consequences

**Positive**
- Product-ready: a tenant configures providers/keys/models/budget in their store;
  nothing tenant-specific is in git.
- Honest savings: cost reflects the tenant's actual ceiling economics, including
  subscription budget pressure.
- Resolves the standing ANTHROPIC_API_KEY-vs-OAuth contradiction in the committed
  default.

**Negative / cost**
- `routing_tiers.yaml` schema change (typed cost) → migration + the projection
  pricing-manifest must learn cost types.
- The committed `ANTHROPIC_API_KEY` ceiling default must be removed; the ceiling
  is then resolved per-tenant from config like every other tier.
- Budget tracking requires a per-tenant budget-state surface the projection can
  read.

**Neutral**
- The node graph and bus topology are unchanged; this is a config-authority and
  cost-model change, not a transport change.

---

## Overturned prior conclusions (this session)

Recorded explicitly per ground-truth discipline:

1. ~~"Bifrost is one HTTP proxy fronting all providers."~~ → It is a
   config/resolution layer; the effect POSTs directly to provider URLs.
2. ~~"Vertex / Anthropic-API in config are live-volume drift to delete."~~ → They
   are in the **committed** contract; Vertex is a product capability to **keep**.
   Only the site-specific binding leaves the committed default.
3. ~~"A Claude Code subscription ceiling has ≈ 0 marginal cost."~~ → It is
   `budgeted`: finite budget, real overage cost.
4. ~~"The quality gate that fails short-but-correct answers is an open bug."~~ →
   **Fixed 2026-06-18** (`semantic_adequacy` replaced the
   `min_length_chars_*` floors). Remaining work is redeploy/verify, not a contract
   change.
5. ~~"The dashboard savings surface needs to be built; the 404 means no read
   surface."~~ → The savings projection + `/api/delegation/savings` API are
   **already declared** (`node_projection_delegation/api_contract.yaml`) and
   partially ticketed (the delegation savings projection epic). The 404 is
   non-materialization on those lanes, not absence of design. The real gap is the
   budget-aware cost model + a redeploy.

---

## Related Pivots

- The "subscription ceiling has ≈ $0 marginal cost" assumption was overturned
  this session; the corrected `budgeted` cost type (D3) is the load-bearing
  insight that makes the savings story honest.

## Related Doctrine

- `doctrine/truth-must-be-proven.md` — savings figures must reflect the tenant's
  real ceiling economics, not a convenient flat constant.
- `doctrine/authoritative-projections-own-truth.md` — cost and savings are
  materialized in the delegation projection from terminal events, not computed
  ad hoc at the read surface.
- `doctrine/fail-fast-and-loud.md` — a resolved endpoint that is a bare base
  (missing `/v1/chat/completions`) fails closed rather than silently appending.

## Derived From

This ADR is anchored by, and supersedes the committed defaults of, several
internal work items (tracked in the OmniNode private Linear, cited in the
accompanying PR):

- the URLs/config-from-contracts epic (config-authority),
- the `ProtocolSecretStore` work (secret values resolve from the store at the
  effect boundary),
- the routing-authority enforcement work,
- the delegation savings projection epic,
- the pricing-manifest work (flat per-token cost today),
- the routing-authority ticket that introduced the HTTP Anthropic-API ceiling
  default this ADR removes,
- the Vertex-Gemini backend addition,
- the `semantic_adequacy` quality-gate fix.

The references it verified against live source are listed under **Evidence**.

## Evidence

Verified 2026-06-18 against live source in the `omnimarket` repo:

- `omnimarket/src/omnimarket/configs/bifrost_delegation.yaml:30-281`
- `omnimarket/src/omnimarket/configs/routing_tiers.yaml:34-176`
- `omnimarket/src/omnimarket/configs/task_class_contracts.v1.yaml:35-303` (the `semantic_adequacy` change at `:85-90, 114-119, 255-260`)
- `omnimarket/src/omnimarket/routing/delegation_backend_resolution.py:32-33, 82-211`
- `omnimarket/src/omnimarket/inference/secret_store_resolver.py:6-20, 42-113`
- `omnimarket/src/omnimarket/nodes/node_llm_delegation_call_effect/handlers/handler_inference_intent.py:31, 38, 121-122`
- `omnimarket/src/omnimarket/nodes/node_projection_delegation/api_contract.yaml:1-40`
- `omnimarket/src/omnimarket/nodes/node_projection_delegation/handlers/handler_projection_delegation.py` (`cost_n_usd`, pricing manifest)
- Runtime state: the 2026-06-17 runtime delegation/SEA state report in the omni_home repo (`docs/research/2026-06-17-runtime-delegation-sea-state-report.md`), flagged there for re-verification.

## Supersedes

This ADR does not supersede a prior ADR. It supersedes two *committed contract
defaults*: the HTTP Anthropic-API ceiling default and the flat
`cost_per_1k_tokens` model in `routing_tiers.yaml`.

## Superseded By

None.
