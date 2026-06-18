---
type: adr
status: proposed
date: "2026-06-18"
title: "ADR-0009: Complexity-Aware Delegation Routing"
adr_id: ADR-0009
topics: [delegation, routing, complexity, learned-routing, per-model-baselines, shadow-mode]
refs:
  - doctrine/deterministic-under-replay.md
  - doctrine/truth-must-be-proven.md
  - doctrine/evidence-is-first-class-output.md
supersedes: []
superseded_by: []
---

# ADR-0009: Complexity-Aware Delegation Routing

(Per-Model Baselines + Async Replay Learner)

## Context

OmniNode's delegation layer routes each unit of work down a tier ladder, trying
the cheapest capable backend first and escalating only when a tier's output fails
the task-class contract DoD gate. The mechanism is canonical and bus-native. The
live node graph (every node below confirmed present under
`omnimarket/src/omnimarket/nodes/`, 2026-06-18):

```
delegation command (bus)
  → node_llm_delegation_routing_compute        (pure COMPUTE: select target model)
  → node_llm_delegation_call_effect            (EFFECT: resolve backend, POST /v1/chat/completions, emit ONE terminal)
terminal events (omnimarket namespace):
  onex.evt.omnimarket.delegation-call-completed.v1       (success)
  onex.evt.omnimarket.delegation-escalation-triggered.v1 (gate fail → climb)
  onex.evt.omnimarket.delegation-all-tiers-failed.v1     (exhausted)
  → node_delegation_routing_feedback_reducer   (REDUCER: terminal events → per-(model_id, task_type) counters)
       emits onex.evt.omnimarket.routing-feedback-updated.v1
```

A separate **config-side** path exists: `node_delegation_routing_reducer`
consumes `routing_tiers.yaml` + `task_class_contracts.v1.yaml` and is where the
per-class `escalation_policy.tier_order` is enforced. Whether the compute router
and the routing reducer are both live on the same dispatch path, or are two
parallel routing implementations, is **not verified** (see §Flagged).

**The current strategy is cheapest-first-escalate, and that is the
*zero-information* strategy.** It is correct *only because the router has no
per-task difficulty signal*. With no signal, starting at the cheapest tier and
climbing is the right default (see the asymmetry below). But it pays a
**wasted-cheap-attempt tax** on hard tasks: a task that needs `cheap_frontier`
still runs `local` first, fails the gate, and climbs — burning a local attempt
(and the escalation round-trip) every time.

The goal of this ADR is to route to the **right starting tier** using a
complexity signal, cutting that tax, **without risking output quality**.

### Current state, stated precisely (verified live, 2026-06-18)

These are real seams, not aspirational. The design extends them.

- **There is NO complexity-based starting-tier selection today.** Starting tier
  is determined by `task_policy.preferred_models` *declaration order* (or an
  explicit `required_tier` override on the request). `node_llm_delegation_routing_compute`'s
  algorithm is: if `request.required_tier` is set, filter `model_profiles` to
  that tier and take the first non-degraded / non-unhealthy / context-fitting
  model (fails hard if none — no cross-tier fallback); else iterate
  `task_policy.preferred_models` in declaration order skipping degraded /
  context-too-small / unhealthy models; else `task_policy.fallback`.
- **A token estimate already exists but is used only for context-fit skipping,
  NOT for tier selection.** `_estimate_tokens(prompt) = max(1, len(prompt) // 4)`
  (`_CHARS_PER_TOKEN = 4`) at
  `node_llm_delegation_routing_compute/handlers/handler_delegation_routing.py:49-50`.
  Its only consumer skips a candidate model when
  `estimated_tokens > int(profile.max_context * 0.8)` (`_CONTEXT_SAFETY_MARGIN`,
  `:144`). It is **not** compared across tiers, **not** used to choose a starting
  tier, and **never persisted onto any event**. (`routing_tiers.yaml` separately
  carries a per-model `fast_path_threshold_tokens`, but that is config consumed by
  the routing *reducer*, not by this compute handler.)
- **Per-CLASS complexity routing already exists in config — enforced by the
  routing reducer, not the compute router.** `task_class_contracts.v1.yaml` gives
  each task_class an `escalation_policy.tier_order` that demonstrably varies by
  class (e.g. `code_generation: cheap_cloud → local → claude`;
  `complex_reasoning: local → claude`; `documentation/reasoning/planning/review/
  summarization: local → cheap_cloud → …`; `escalation: claude` only). What does
  **not** exist is *per-task* (within a class) complexity routing, or any
  *learned* signal behind the hand-authored `tier_order`s.
- **`node_delegation_ab_runner` is a baseline-vs-delegated A/B COMPARISON harness,
  NOT an event-replay learner.** `HandlerDelegationAbRunner.handle()` is
  **synchronous**; it runs the same `task_payload` through baseline (frontier, no
  gate) then delegated (cheaper/local, with quality gate) via live httpx
  OpenAI-compatible calls, then returns `ModelABComparisonResult.compute()`
  (token_savings, cost_savings_usd, latency_delta_ms, winner). Caveats observed in
  source: cost is **estimated from hardcoded module constants** (a Gemini-1.5-Flash
  approximation), **not** the pricing manifest; `_evaluate_quality` is a `>20`-char
  length heuristic, not a real evaluator; the `escalated` flag is
  **hardcoded `False`** (`handlers/handler_delegation_ab_runner.py:94`) and never
  set true — no actual escalation-to-frontier is wired despite the docstring. It
  does not read or replay terminal events; no learner/train/backfill code exists.
- **`node_delegation_routing_feedback_reducer` already consumes the three terminal
  events** (`delegation-call-completed.v1`, `delegation-escalation-triggered.v1`,
  `delegation-all-tiers-failed.v1`, per `contract.yaml:47-49`) and accumulates
  per-`(model_id, task_type)` counters (total/success/failure/escalation counts +
  incremental `avg_latency_ms` + derived `success_rate`/`escalation_rate`),
  materializing a `ModelRoutingFeedback` projection and emitting
  `routing-feedback-updated.v1`. **CRITICAL:** although the contract comment says
  downstream routing reducers *can* use this projection to skip poor-success
  models, `node_llm_delegation_routing_compute` does **NOT** read
  `ModelRoutingFeedback` today — its inputs are only `degradation_state` and
  `health_state`. **The feedback loop is materialized but NOT wired back into the
  compute router.** (A reducer-hardening ticket made it no-op on empty/
  unidentifiable payloads instead of crashing.)
- **`shadow_mode` is BUILT but DISABLED.** It lives in
  `bifrost_delegation.yaml:400-405` (NOT in `routing_tiers.yaml`):
  `enabled: false`, `policy_version: "unknown"`, `log_sample_rate: 1.0`,
  `comparison_logging_enabled: true`, `max_shadow_latency_ms: 5.0`. Per the
  shadow-mode ticket comment, shadow decisions are emitted as comparison events
  only and **never** affect live routing; disabled by default to prevent accidental
  learned-policy activation. This design activates and extends it rather than
  building a new evaluator.

### The terminal-event payload today (what is, and is not, a training label)

The completed terminal event is `ModelLlmDelegationCompletedEvent`
(`delegation-call-completed.v1`) — **not** the in-process
`ModelLlmDelegationCallResult`. It carries (verified field list):
`task_type`, `selected_model`, `model_id`, `model_tier`, `provider`,
`endpoint_ref` (an env-var *name*, not a raw URL), `tokens_in`, `tokens_out`,
`latency_ms`, `actual_cost_usd`, `opus_equivalent_cost_usd`, `savings_usd`,
`usage_source`, `cost_basis`, pricing/policy/registry hashes, `success`,
`quality_score` (`float|None`), `escalated_to`, `escalation_reason`,
`prompt_hash`, `output_hash`, `correlation_id`/`causation_id`/`request_id`,
`created_at`.

**Fields the training set will need that are MISSING from the terminal event
today** (verified absent):

- No **complexity / difficulty / prompt-size-bucket / estimated-token** label.
  `_estimate_tokens` is computed in-memory in the compute router and never
  emitted.
- No **starting-tier** label distinct from the *winning* tier (`model_tier` is the
  tier that won; the tier we *started* at is not recorded).
- No **per-request attempt/escalation count** on the completed event.
  `attempt_number` exists only on `delegation-escalation-triggered.v1`;
  `escalation_count` is a **derived** counter computed inside the feedback
  reducer's projection, not a field on any terminal event.
- No **quality_gate_passed** boolean on the terminal event — it exists only on the
  in-process `ModelLlmDelegationCallResult`, not on
  `ModelLlmDelegationCompletedEvent`.
- No `task_class` field — the dimension present is `task_type` (a free string).
- No `backend_id` on the event — `backend_id` lives only in
  `routing_tiers.yaml`/bifrost config; the event carries `provider` +
  `endpoint_ref` instead.
- No `ns_in`/`ns_out`, `n_score`, `n_gate_passed`, `task_class`, bare `tier`, or
  `n_attempts` fields — these names do not exist; the real fields are as listed
  above.

Phase 0 scopes the payload-enrichment work to *exactly these missing labels.*

### The asymmetry that governs the whole design

The starting-tier choice is **not symmetric** in cost:

- **Start too LOW** → you pay *one extra cheap attempt* (plus an escalation
  round-trip). Escalation backstops you: the task still completes at the right
  tier, one rung later. Bounded, cheap, self-correcting.
- **Start too HIGH** → you burn the **ceiling** (the most expensive tier, which is
  `budgeted` per the typed cost model in ADR-0008) on a task a cheap tier would
  have passed. That spend is **unrecoverable** and is exactly the spend the
  savings story exists to avoid. It destroys savings.

This asymmetry is the load-bearing fact. It dictates a **bias-low** policy: only
move a task *up* from cheapest-first when we *confidently* know it is hard;
otherwise leave it at cheapest-first. We must **never** predict an exact tier for
every task — that maximizes the expensive failure mode.

---

## Decision

### D1 — Per-MODEL capability baseline, NOT per-tenant

The complexity→tier policy decomposes into two independent factors:

1. **A per-MODEL capability profile** — "model M handles complexity band ≤ C at
   quality Q for task_class T" — expressed as a *success-rate per complexity band
   per task_class*. This is a property of the model **weights**, so it is
   **shareable and shippable across tenants**. It is the natural promotion of
   `routing_tiers.yaml`'s `use_for` from a *categorical list* to a *learned
   complexity-band-with-confidence per (model, task_class)*.
2. **The tenant's tier ladder** — which models, in what order — already in
   `routing_tiers.yaml` ⊕ store.

**Selection = compose the ladder × the profiles.** This kills cold-start: a new
tenant running the same model build inherits the **global** profile on day one;
any per-tenant drift is a **thin delta** layered on top, not a from-scratch
learning problem.

**KEY — the profile key is the SERVED model identity, not the friendly name.**
Effective capability depends on quantization, context window, sampling, and
throughput, so the key is `(model-version, quant, serving-profile)`. **Proof from
live config:** `Qwen3.6-35B-A3B` appears twice in `routing_tiers.yaml` — once as a
local-coder profile with `max_context_tokens: 65536` and once as a
heavy-reasoning profile with `max_context_tokens: 8192`. Same weights, two
different served capabilities. A friendly-name key would collapse these and
mis-route; the served-identity key keeps them distinct. (The exact line anchors
from prior reads were `:38`/`:58`; the dual-identity fact is verified, the precise
line numbers are FLAGGED below.)

### D2 — Inline path: cheap heuristic + confidence-gated floor-lowering

In `node_llm_delegation_routing_compute`, add a **near-free heuristic complexity
score** (token count / diff size / file count, building on the existing
`_estimate_tokens`) plus a **confidence flag**, and a **contract-declared
`complexity → starting_tier` policy** (declared in `task_class_contracts` /
`routing_tiers`, never source constants).

Governed by the asymmetry, the policy is **bias-low**:

- Only **bump** a task above cheapest-first when it is **confidently** known hard.
- Everything else **stays cheapest-first**.
- **Do not predict an exact tier for every task** — predicting a floor we are
  confident about is safe; predicting a ceiling is not.

The estimator must be the cheapest thing that works: heuristic first; a small
local model only if data later justifies it; and it is **hard-bounded on latency**
— the router must never cost more than it saves.

### D3 — Async free-local replay learner (the signal the inline path cannot get)

Inline, you **stop at the first passing tier**, so you only ever learn the
*ceiling-of-need* — you **never** learn whether a *cheaper* tier would *also* have
passed. That counterfactual is exactly the signal the bias-low policy needs to
safely lower floors.

An **async node** subscribes to `onex.evt.omnimarket.delegation-call-completed.v1`,
and **off the critical path** re-runs the served task on the **cheaper** tiers
through the **same** `node_llm_delegation_call_effect` and the **same**
deterministic `node_delegation_quality_gate_reducer`, then emits **comparison
events** that feed the per-model baseline (D1). This generates the "the floor
could've been lower" counterfactual, which (per the asymmetry) is the **safe**
direction to move.

**Economics:** the cheaper tiers are `free_local` (the zero-cost local tier —
`cost_per_1k_tokens: 0.0` in `routing_tiers.yaml`; typed as `free_local` once the
typed cost model in ADR-0008 lands), so replay costs only **idle compute**.
Schedule it **idle-priority / off-peak and BOUNDED**, so it never steals latency
from the live path.

This is the dormant `shadow_mode` + `node_delegation_ab_runner` +
`node_delegation_routing_feedback_reducer` machinery **extended with a
replay-from-events dimension** (the ab_runner today is a synchronous comparison
harness, not a replay learner — see Context). It is bus-native — subscribe to
terminal events, emit comparison events — **no new transport, no new HTTP route.**

### D4 — Probabilistic PRIOR, DETERMINISTIC output (doctrine-critical)

The per-model profile is a **success-RATE distribution** used **only as a prior to
choose the starting tier**. Whatever a tier actually produces still passes the
**deterministic** `task_class_contracts` DoD gate
(`node_delegation_quality_gate_reducer`) before acceptance.

- The probability lives **entirely** in "which tier to try first."
- It lives **NEVER** in what is shipped.
- The async learner adjusts **only the prior**; it never alters a served result.

This keeps the system inside the
[OmniNode deterministic-truth doctrine](../doctrine/deterministic-under-replay.md):
a probabilistic prior that picks a *starting tier* is a routing heuristic, not a
truth claim, because the deterministic gate still adjudicates every output.

### D5 — Convergence with node generation

The same replay lane **surfaces node-generation candidates**. A recurring task
pattern that **consistently needs `cheap_cloud`+** is simultaneously:

1. a **routing-baseline fact** (this pattern's floor is `cheap_cloud`), and
2. a **"make this a deterministic node" signal** — a recurring pattern that always
   costs an LLM call is a candidate to compile into a deterministic node via the
   live `node_generation_consumer`
   (`omnimarket/src/omnimarket/nodes/node_generation_consumer`).

**One event-sourced consumer feeds both savings levers** (route-cheaper and
make-deterministic). No second pipeline.

---

## Phasing (data-availability driven)

The phasing is dictated by **what data exists**, not by a date.

### Phase 0 (now) — bootstrap the training set

Cheapest-first stays untouched. The **only** add is enriching the terminal-event
payload with the **routing-feature labels that are missing today** (see Context →
"missing labels"): starting-tier, complexity/prompt-size bucket + estimated
tokens, per-request attempt/escalation count, `task_class`, and
quality-gate-passed — so the event stream *is* a usable training set. Phase 0 is
**not wasted** — it is the bootstrap that **GENERATES** the data every later phase
trains on.

### Phase 1 — inline informed starting tier

Inline heuristic estimator + per-model baseline **schema** + **shipped default
baselines** + contract-declared `complexity → starting_tier` policy.
Confidence-gated, **bias-low**; escalation still backstops every wrong-low guess.

### Phase 2 — async learner + shadow-validated activation

Async free-local replay learner (D3); baseline updates flow via
`node_delegation_routing_feedback_reducer`; **the feedback projection is wired
back into the compute router for the first time** (it is materialized-but-unwired
today); the learned policy is validated in `shadow_mode` (comparison-only, **never
affects live**) before activation.

---

## Canonical + evidence guardrails (binding on every workstream)

1. The complexity→tier policy and per-model baselines are **CONTRACT-DECLARED** and
   resolved through the routing contract (extending `routing_tiers.yaml` /
   `task_class_contracts.v1.yaml`), **never** env vars or source constants.
2. The estimator is the **cheapest possible** (heuristic first; small local model
   only if data justifies) and **hard-bounded on latency** — the router must never
   cost more than it saves.
3. **Learned routing only goes live through shadow validation.** Never flip it on
   against live without comparison proof.
4. **All learning is bus-native:** subscribe to terminal events, emit comparison
   events; **no new HTTP routes, no new transport.**
5. **The deterministic output gate is preserved end to end (D4).** The prior
   chooses where to start; the gate decides what ships.
6. **Evidence discipline (every ticket):** a code PR alone is **not** sufficient.
   Each work item carries durable evidence per the OCC/Receipt-gate recipe — a
   per-ticket DoD contract capturing the DoD, an Evidence-Source OCC SHA, and a
   paired OCC receipt PR — plus concrete probe/test evidence (named test, live
   probe, or comparison-event readback).

---

## Alternatives Considered

- **Predict an exact starting tier for every task.** Rejected: violates the
  asymmetry — guessing a ceiling that is too high burns unrecoverable spend.
  Bias-low + escalation-backstop is strictly safer.
- **Learn the floor inline (no async lane).** Rejected: structurally impossible —
  the inline path stops at the first passing tier and never observes whether a
  cheaper tier would have passed. Only an off-path replay can generate the
  counterfactual.
- **Per-tenant learned profiles from scratch.** Rejected: cold-start per tenant.
  The capability is a property of the weights (D1), so a global per-model baseline
  shared across tenants with a thin per-tenant delta is correct and
  cold-start-free.
- **A probabilistic / sampled OUTPUT.** Rejected: violates the deterministic-truth
  doctrine. The probability is confined to tier *selection*; the deterministic DoD
  gate adjudicates every shipped output (D4).
- **A new evaluator service / HTTP eval route.** Rejected: the `shadow_mode` +
  `node_delegation_ab_runner` + feedback-reducer machinery already exists and is
  bus-native; activate and extend it.

---

## Consequences

**Positive**
- Cuts the wasted-cheap-attempt tax on confidently-hard tasks while the bias-low
  policy + escalation backstop keep the failure mode bounded and cheap.
- Per-model baselines (D1) ship with the model build → new tenants get an informed
  router on day one (no cold start).
- The async learner generates the counterfactual signal (D3) the inline path
  structurally cannot, and reuses the dormant shadow/A-B harness instead of
  building new infra.
- One event-sourced lane feeds both *route-cheaper* and *make-deterministic-node*
  savings levers (D5).
- Stays inside the deterministic-truth doctrine: the probability is confined to
  tier selection; the output gate is unchanged (D4).

**Negative / cost**
- Terminal-event payload schema change (Phase 0) → producers + projection must
  carry the new labels.
- New per-model baseline schema keyed on served identity, plus shipped default
  baselines to maintain per model build.
- Phase 2 must **wire the feedback projection back into the compute router** — a
  seam that does not exist today (the router reads only `degradation_state` /
  `health_state`).
- The async replay learner is new compute (bounded, idle-priority, free_local) — it
  must be scheduled so it provably never steals live latency.
- `node_delegation_ab_runner` must be reworked from a synchronous comparison
  harness into (or alongside) an event-replay learner, and its hardcoded cost
  constants / `>20`-char quality heuristic / hardcoded `escalated=False` replaced
  with the pricing manifest, the real deterministic gate, and real escalation.

**Neutral**
- The node graph and bus topology are otherwise unchanged; this is a
  routing-policy + learning-lane change, not a transport change. The inline path in
  Phase 0 is behaviorally identical to today (cheapest-first) — only the event
  payload grows.

---

## Overturned prior conclusions (this session)

State these explicitly so they are not re-introduced:

1. **"The subscription ceiling is ≈ $0 marginal."** Overturned. The ceiling tier is
   `budgeted` with a real overage cost (the typed cost model in ADR-0008). The
   asymmetry's "start-too-high burns unrecoverable ceiling spend" reasoning depends
   on this correction — a $0 ceiling would void the whole bias-low rationale.
2. **"Complexity-based routing is greenfield."** Overturned. *Partial seams already
   exist:* a token estimate (`_estimate_tokens`, used only for context-fit
   skipping), and **per-CLASS** complexity routing via
   `task_class_contracts.v1.yaml`'s `escalation_policy.tier_order` (enforced by the
   routing reducer). What is missing is *per-task* complexity-keyed starting-tier
   selection and any *learned* signal — this ADR adds those, it does not invent
   complexity routing from zero.
3. **"`node_delegation_ab_runner` is already a replay learner."** Overturned. It is
   a **synchronous baseline-vs-delegated comparison harness** with estimated
   (hardcoded-constant) cost, a `>20`-char length quality heuristic, and a
   hardcoded `escalated=False` (no real escalation). It does not read or replay
   terminal events and contains no learner/train/backfill code. D3 *extends* it
   into a replay learner; it is not one today.
4. **"The routing feedback loop already informs routing."** Overturned. The
   feedback reducer *materializes* `ModelRoutingFeedback` from terminal
   events, but `node_llm_delegation_routing_compute` does **not** consume it (reads
   only `degradation_state` / `health_state`). The loop is built but **not wired
   back** into the compute router; Phase 2 wires it.

---

## Flagged — unverified, resolve before building

1. **Terminal-event namespace discrepancy (HIGH).** This ADR's verification read
   omnimarket source and found the omnimarket-namespace terminal
   `onex.evt.omnimarket.delegation-call-completed.v1` (consumed by the feedback
   reducer). But the 2026-06-17 live runtime probe (the runtime delegation/SEA
   state report in the omni_home repo) watched — and got terminal records on —
   `onex.evt.omnibase-infra.delegation-completed.v1`, a **different** namespace.
   Either both exist (an omnibase_infra runtime-side delegation event *and* the
   omnimarket node-side event) or one is stale. The async learner (D3) and the
   feedback reducer subscribe to specific topics, so the **canonical terminal the
   learner consumes must be pinned before Phase 2.** Resolve by listing live topics
   on the runtime host and identifying the producer of each. (Note: the session's
   config-authority ADR/plan/handoff docs cite the `omnibase-infra` name from the
   live probe; this ADR cites the `omnimarket` name from code — the discrepancy is
   real and unreconciled, not a typo in either.)
2. **Compute-router vs routing-reducer (MEDIUM).** Whether
   `node_llm_delegation_routing_compute` and `node_delegation_routing_reducer` are
   both on the same live dispatch path, or are two parallel routing
   implementations, is unverified. D2 / Phase 2 must target whichever is the live
   decision point — and may have to reconcile the two first.
3. **D1 line anchors (LOW).** The `Qwen3.6-35B-A3B` dual-served-identity fact is
   verified; the exact `routing_tiers.yaml` line numbers (~`:38`/`:58`) are from an
   earlier read and are approximate.

---

## Related Pivots

- The "subscription ceiling has ≈ $0 marginal cost" assumption was overturned this
  session; without that correction the entire bias-low rationale collapses.
- "Complexity-based routing is greenfield" was overturned: partial per-class seams
  already exist and this ADR extends rather than invents them.

## Related Doctrine

- `doctrine/deterministic-under-replay.md` — the probabilistic prior chooses only
  the starting tier; every shipped output still passes the deterministic DoD gate,
  keeping replay determinism intact.
- `doctrine/truth-must-be-proven.md` — learned routing only goes live through
  shadow validation with comparison proof; never flipped on against live without it.
- `doctrine/evidence-is-first-class-output.md` — Phase 0 enriches the
  terminal-event payload so the event stream *is* a usable, durable training set.

## Derived From

This ADR is anchored against live source and composes with the config-authority +
budget-aware-cost work in **ADR-0008** (session work items tracked in the OmniNode
private Linear, cited in the accompanying PR). That work makes the cost model
honest and the config multi-tenant; **this** work makes the *starting-tier choice*
informed. They compose; they do not overlap.

It also builds on several internal work items (cited in the accompanying PR):

- the delegation savings projection epic,
- the typed tier-cost-model work (supplies the `free_local`/`metered`/`budgeted`
  cost numbers this design's asymmetry reasoning depends on),
- the shadow-mode work for delegation A/B testing (Done),
- the routing-feedback-loop work (Done),
- the URLs/config-from-contracts epic,
- the routing-authority enforcement work,
- the feedback-reducer hardening ticket.

## Evidence

Verified 2026-06-18 against live source in the `omnimarket` repo:

- `omnimarket/.../node_llm_delegation_routing_compute/handlers/handler_delegation_routing.py:43,46,49-50,102,144` — `_CONTEXT_SAFETY_MARGIN = 0.8`, `_CHARS_PER_TOKEN = 4`, `_estimate_tokens`, context-fit-only use of the estimate. Home of the inline estimator (D2).
- `omnimarket/.../node_delegation_ab_runner/handlers/handler_delegation_ab_runner.py:94` — `escalated = False` hardcode; synchronous comparison harness (overturned #3).
- `omnimarket/.../node_delegation_routing_feedback_reducer/contract.yaml:47-51` — subscribes the three terminal events, emits `routing-feedback-updated.v1`. The materialized-but-unwired feedback projection (overturned #4).
- `omnimarket/src/omnimarket/configs/bifrost_delegation.yaml:400-405` — `shadow_mode` block: `enabled: false`, `comparison_logging_enabled: true`, `max_shadow_latency_ms: 5.0` (the dormant harness; D3, Phase 2).
- `omnimarket/src/omnimarket/configs/routing_tiers.yaml` — tier ladder, per-tier `cost_per_1k_tokens` (local `0.0`, cheap_cloud `0.002`, cheap_frontier `0.0`, claude `0.015`), per-model `id`/`backend_id`/`use_for`/`max_context_tokens`/`fast_path_threshold_tokens`; `Qwen3.6-35B-A3B` dual served identity (D1 proof — line anchors FLAGGED).
- `omnimarket/src/omnimarket/configs/task_class_contracts.v1.yaml` — per-task_class `escalation_policy.tier_order` (per-class complexity routing already exists; overturned #2).
- `omnimarket/.../node_llm_delegation_call_effect/` — egress effect; emits exactly one terminal per dispatch (replay reuses this, D3).
- `omnimarket/.../node_delegation_quality_gate_reducer/` — deterministic DoD gate (preserved, D4).
- `omnimarket/.../node_generation_consumer/` — node-generation lane (D5 convergence target).
- Terminal events (omnimarket namespace, verified via node topic strings 2026-06-18): `onex.evt.omnimarket.delegation-call-completed.v1`, `onex.evt.omnimarket.delegation-escalation-triggered.v1`, `onex.evt.omnimarket.delegation-all-tiers-failed.v1`.

## Supersedes

None. This ADR is adjacent to but distinct from **ADR-0008** (config-authority +
budget-aware cost); they compose without overlap.

## Superseded By

None.
