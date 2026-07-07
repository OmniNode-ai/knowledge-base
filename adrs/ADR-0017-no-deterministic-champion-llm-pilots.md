---
type: adr
status: proposed
date: "2026-07-06"
title: "ADR-0017: No Deterministic Champion in Live Play; Learning Loop Repointed at LLM Pilots"
adr_id: ADR-0017
topics: [steel-onslaught, learning-loop, llm-pilots, non-determinism, evolutionary-search]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0017: No Deterministic Champion in Live Play; Learning Loop Repointed at LLM Pilots

## Context

Steel Onslaught's in-game learning loop worked and was live-verified
(select_champion / field_champion / auto-field trigger). But the loop tuned only
**HEURISTIC archetype pilots** — deterministic decision trees with numeric thresholds —
never LLM personas. So the fielded champion was inherently deterministic, colliding with
the invariant that live play runs on live local LLMs (ADR-0015). This was rolling-plan
open decision §3.23 (and STEEL_DESIGN open-call #3): does a deterministic heuristic
champion belong in the live LLM game?

## Decision

**No deterministic champion in live Steel Onslaught play, ever.** LLMs drive BOTH pilots
in all live modes; deterministic policies are CI-fixture-only. The existing
evolutionary-search machinery (`learning/{loop,promotion,lineage_store,fielding}.py`) is
**repointed at LLM pilots, not rebuilt**: the genome becomes what the LLM consumes
(doctrine/prompt-strategy variants, loadout/personality priors, decoding temperature, and
draft-policy priors). Evaluation keeps the seed-battery + paired-comparison +
disjoint-holdout gate, but live-play promotion runs on the **live qwen35 path** via a new
non-deterministic `LiveMatchEvaluator` (variance handled with more samples per scenario,
never fake seeds); the deterministic `DuelEvaluator` stays **CI-fixture-only**; the trigger
moves in-game to an **after-match auto-learn hook** that fields the promoted genome as the
served pilot.

## Alternatives Considered

1. Accept a deterministic heuristic champion as a sparring/opponent seat vs a live-LLM pilot. Rejected by the operator — "that is fucking boring"; a live opponent seat does not make the champion non-deterministic, and the game must showcase live-LLM play on both seats.
2. Keep the offline learning loop test-only and never field it into live play. Rejected: the operator requirement is a learning loop *built into the game* (after-match, not offline `so learn`) that measurably improves the LLM pilots.
3. Rebuild a new learning substrate from scratch. Rejected: the existing evolutionary-search machinery is reused (repointed), preserving the seed-battery/paired-comparison/holdout gate.

## Consequences

Positive: the fielded champion is itself an LLM configuration (non-deterministic),
consistent with ADR-0015; the loop improves the actual product surface (LLM pilots) rather
than a deterministic side-policy; `draft_policy_priors` becomes a first-class genome
dimension so the loop can tune what a persona values in the loadout draft. Negative: a live
non-deterministic evaluator needs more samples per scenario to control variance (higher
evaluation cost); the loop must never use fake seeds to fake determinism; scope grows
(mode-toggle UI, after-match auto-learn hook, LLM-pilot genome
definition; the in-game learning loop rescoped). Full design lives in
`docs/plans/2026-07-06-steel-llm-pilot-learning-rescope.md`.

## Derived From

`docs/plans/2026-07-06-steel-onslaught-redesign-plan.md` §8 Decisions log, "§3.23
(learning substrate) — RESOLVED 2026-07-06" (operator quote + the repoint design), which
resolves rolling-plan §3.23 and STEEL_DESIGN open-call #3.

## Evidence

Hand-driven ADR canary batch (2026-07-06). Source records a direct
operator decision (verbatim quote) plus the concrete rescope (LiveMatchEvaluator,
DuelEvaluator CI-only, after-match hook) and the filed follow-up tickets.

## Related Pivots

- Steel = model-vs-model by design (project memory `project_steel_model_vs_model_by_design.md`) — qwen35-both-sides was only a 4090-outage fallback; different LLMs pilot the two seats.
