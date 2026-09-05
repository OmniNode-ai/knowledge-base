---
type: plan
status: active
date: "2026-07-02"
title: "Escalation proof corpus — specification"
topics: [delegation, model-tiering, evaluation, escalation]
---

# Escalation Proof Corpus — Spec (Option A)

- **Goal:** produce the live three-way discriminator: one `code_generation` delegation terminating with `escalation_count >= 1` AND a non-local cloud `model_name` AND `quality_gate_passed = true`. The static passability guard exists (`test_code_generation_escalation_passability.py`); the missing artifact is the runtime proof row.
- **Why a corpus:** the reproven blocker is not a defect — on every prompt tested so far (including a deliberately hard thread-safe TTL LRU cache task) the local tier honestly clears the 0.85 bar, so escalation never fires (see the second reprove record). Proof requires tasks where a lower tier FAILS HONESTLY and the ceiling passes.
- **Preconditions:** the local-path escalation loop + judge-combine change and the honest `passes_existing_tests` change merged to dev. The local bus-less run is deploy-free (in-process from a dev checkout); the bus-path run additionally needs the stability re-pin.

## Binding guardrails (from the Track 2 adjudication — violating any of these invalidates the proof)

No lowering the 0.85 bar; no weakening `final_artifact_only` or the refusal/empty floor; no tier_order edits; cheapest-first initial tier preserved; every attempt records real metered cost. The corpus makes the PROMPTS harder — never the gate softer.

## Corpus design (10 tasks, 3 bands)

- **Band C — controls (3 tasks):** tasks the local tier is expected to pass (single-function, clear spec, e.g. the existing TTL LRU cache task). Purpose: prove the gate is not simply harder-everywhere; if controls start failing, the run is invalid (gate drift, not tier separation).
- **Band H — discriminators (5 tasks):** tasks selected for capability separation between local and the GLM-5.2 ceiling, NOT for trickiness: many simultaneous hard constraints (e.g. implement a bounded-concurrency scheduler with cancellation + deadline + fairness invariants, all asserted), cross-file coherence (edit 3 interacting modules keeping an invariant), spec-adherence under long constraint lists (10+ MUST clauses each mechanically checkable), and subtle-concurrency correctness with a deterministic stress test as `acceptance_command`. Expected: local honest-FAIL, ceiling PASS.
- **Band X — calibration (2 tasks):** hard enough that even the ceiling may fail. Purpose: upper calibration so a 100% Band-H ceiling pass rate is interpretable.

**Anti-overfit rule:** tasks must not target one model's idiosyncratic weaknesses (tiers are overlay-swappable; the corpus must survive a model swap). Difficulty must come from objective task structure, verified by `acceptance_command` where feasible (once the honest-evaluation change lands, an evaluated command is honest; absent command → the check reports SKIPPED, never passed).

**Failure honesty check:** for every Band-H local FAIL, the evidence must show WHICH deterministic check or judge criterion failed — a FAIL caused by `final_artifact_only` formatting rather than capability is a corpus defect (rewrite the task's output-format instruction, don't count it).

## Run protocol

1. **Local path (deploy-free, first):** dev checkout post-merge; run each task via the bus-less CLI; record per-attempt tier, model, gate score, deterministic-check outcomes, judge score/verdict, escalation events, metered cost. Success = ≥1 Band-H task satisfying the three-way discriminator.
2. **Bus path (after stability re-pin):** replay the passing Band-H tasks through the bus orchestrator on the stability lane; the discriminator must hold in the projection row (readback from the projection, not the runner's claim — verifier ≠ runner).
3. **Evidence:** the escalation-proof evidence folder — per-task attempt table + the raw terminal rows; the discriminator DoD cites it.

## Deliverables

1. `omnimarket/tests/fixtures/escalation_corpus/` — 10 task YAMLs (prompt, task_type, acceptance_command where feasible, band, expected-separation rationale).
2. A runner script (or extension of the existing reprove procedure in `docs/evidence/2026-06-25-plan-drive/redeploy-reprove/`) executing the protocol and emitting the attempt table.
3. The evidence doc + the closure comments on the two tracker items.

Also fold in the single refusal reprove (refusal prompt → `quality_gate_passed=false` row) — same session, one extra task in the run matrix; its DoD has been unmet since that change merged.
