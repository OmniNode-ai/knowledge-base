---
type: plan
status: active
date: "2026-07-10"
title: "Merge-queue governor — conservative fail-closed action-mode (arm-gate)"
topics: [merge-queue, ci, governance, fail-closed]
---

# Conservative fail-closed action-mode for the merge-queue governor (corrected design)

**Invariant:** report-only is the DEFAULT and means ZERO mutation of the merge queue; enforce is opt-in + wave-gated (small N) + kill-switchable; a PR arms ONLY if it positively satisfies every ready-criterion; any None/unknown fails CLOSED.

## Recommended approach (survives the live code)

Build **Candidate-1's core architecture** — a single pure-COMPUTE fail-closed arm-gate node (`node_pr_arm_gate_compute`) as the sole ARM/WITHHOLD decider, feeding the ONE gated `pr_lifecycle` merge-effect arm path — with **five corrections** the adversarial verdict surfaced. **REJECT Candidate-2 (gate-at-the-adapter) entirely:** `GitHubMergeQueueAdapter` is provably NOT the choke point (exactly two callers, both already the dry_run-gated `pr_lifecycle` path), while three ungated surfaces fire arms via their own inline `urllib` `enablePullRequestAutoMerge`, their own `gh pr merge` subprocess, and an unconditional triage arm-emit — none touch the adapter; and the wave-cap is unenforceable across per-process adapter instances.

### The five corrections vs Candidate-1

1. **Fold `action_mode` + `kill_switch` INTO the gate's decision** so REPORT_ONLY/kill deterministically returns WITHHOLD (single choke point, not a separate orchestrator check the CI guard can't protect).
2. **Decouple the two distinct queue-mutation operations** instead of forcing both through the readiness gate. `_enable_auto_merge` genuinely has two callers — `merge_pr` (readiness-arm a not-yet-armed PR) and `remediate_queue_stall` (dequeue→arm→re-enqueue to re-mint a stalled merge-group SHA on an ALREADY-armed PR). Forcing remediation through the readiness gate breaks stall re-mint whenever the gate WITHHOLDs. Fix: gated arm-fresh is the sole readiness-arming path; stall-remediation is a SEPARATE operation behind the SAME `action_mode`/kill-switch envelope but its OWN opt-in flag `enable_stall_remediation` (default False), keeping its existing AWAITING_CHECKS/zero-merge_group precondition — NOT the readiness gate. Shipped conservative config then has literally one active arm path.
3. **DROP the anti-churn cooldown** from this slice. It has no data source — the normal arm path writes no ledger event and `EnumPrLedgerEventKind` has no `ARMED`/`ARM_ATTEMPTED` kind (only PR_INVENTORIED, WORKFLOW_RUN_OBSERVED, MERGE_GROUP_SHA_MINTED, RERUN_ATTEMPTED, FINAL_CONCLUSION). `wave_cap` already bounds per-pass blast radius; `enablePullRequestAutoMerge` is idempotent on an already-armed PR.
4. **Positively collect green-checks** via `statusCheckRollup == SUCCESS` rather than inferring from `mergeStateStatus`, so "green required checks" is a real positive fact, not always-None (else ENFORCE never arms anything).
5. **Neutralize the three ungated legacy surfaces:** hard-gate them fail-closed (default no-op) as the reliable primary move AND deregister entry_points in BOTH `pyproject.toml` AND each `metadata.yaml`. Full handler deletion/deregistration only after cluster-wide producer confirmation.

## Mechanism

`node_pr_arm_gate_compute` (pure NodeCompute: `contract.yaml` + single `handle()`) takes a `ModelArmCandidate` carrying genuine tri-state facts + a `ModelArmGatePolicy`, and returns `ModelArmGateDecision` (ARM | WITHHOLD + typed `withheld_reasons` + `priority_score`). ARM iff **all** positively true:

`action_mode == ENFORCE` AND `not kill_switch` AND `is_draft is False` AND `coderabbit_unresolved == 0` AND `merge_state_status == 'CLEAN'` AND `status_checks == 'SUCCESS'` AND `occ_companion_verified is True`.

ANY None/unknown/absent fact or policy → WITHHOLD. `occ_companion_verified` stays an EFFECT fact consumed by the gate (never re-derived in the pure compute).

**Fact provenance is mandatory** — without genuine facts the positive-only criteria are hollow (a draft or thread-blocked PR currently forges GREEN/approved):
- Inventory EFFECT (`node_pr_lifecycle_inventory_compute`): wire the already-fetched `isDraft` onto `ModelPrState.is_draft`; add `statusCheckRollup` to the `gh pr view` field set; fetch `reviewThreads` and compute `coderabbit_unresolved` (default MUST be None when unfetched, never 0).
- Thread all three + `merge_state_status` (as its own tri-state, stop collapsing into `approved`) through seam A (`PrRecord`, `_run_inventory` ~1921-1943) and seam B (`ModelPrInventoryItem`, `_call_triage` ~2038-2055); triage GREEN guard consults the genuine `is_draft`/`merge_state_status`.

## Files to touch

- `omnimarket/.../node_pr_arm_gate_compute/` (NEW: contract.yaml, metadata.yaml, handlers/handler_arm_gate.py, models/model_arm_gate_request.py, model_arm_gate_decision.py, model_arm_gate_policy.py) + register in `pyproject.toml`
- `omnimarket/pyproject.toml` (register gate node; DEREGISTER lines 189/296/297) + each legacy node's `metadata.yaml` (deregister the `entry_points: onex.nodes:` block)
- `omnimarket/.../node_pr_lifecycle_orchestrator/handlers/handler_pr_lifecycle_orchestrator.py` (seam A/B fact threading; add `action_mode`/`merge_queue_mutation_kill_switch`/`enable_stall_remediation` to `ModelPrLifecycleStartCommand`; build `ModelArmCandidate` per PR, call gate, wave-cap ENFORCE arming to small N priority-ordered through the single `HandlerPrLifecycleMerge.merge_pr` path; gate `_remediate_stalled_queue_prs` ~1958-2016 behind `action_mode==ENFORCE AND not kill_switch AND enable_stall_remediation`)
- `omnimarket/.../node_pr_lifecycle_orchestrator/protocols/protocol_sub_handlers.py` (add `is_draft` to `PrRecord`) + `.../contract.yaml`
- `omnimarket/.../node_pr_lifecycle_inventory_compute/handlers/handler_pr_lifecycle_inventory.py` + `.../models/model_pr_lifecycle_inventory.py` (add `coderabbit_unresolved`, `status_checks_state`)
- `omnimarket/.../node_pr_lifecycle_triage_compute/models/model_pr_inventory_item.py` + `.../handlers/handler_pr_lifecycle_triage.py` (add `is_draft` + `merge_state_status` tri-state)
- `omnimarket/.../node_merge_sweep_auto_merge_arm_effect/handlers/handler_auto_merge_arm.py`, `node_auto_merge_effect/handlers/handler_auto_merge_effect.py`, `node_merge_sweep_triage_orchestrator/handlers/handler_triage.py` (hard-gate fail-closed no-op by default)
- `omnimarket/src/omnimarket/config/env_flags.py` (NEW: canonical fail-closed `env_flag()` helper — malformed/unset → the SAFE value)
- `omnimarket/tests/test_single_arm_path_policy.py` (NEW: CI guard) + corresponding pre-commit hook (per Rule #5)
- **Deferred cross-repo:** omniclaude `merge_sweep` skill arg plumbing / omnibase_infra `cli_skill.py` to expose `action_mode`/`wave_cap`/`kill_switch` as opt-in enforce controls (ergonomics only; the safety core is omnimarket-only with safe defaults).

## Safety properties

- Fail-closed everywhere: unknown/None facts → WITHHOLD; malformed/unset env → REPORT_ONLY + kill-on; missing policy → no mutation.
- Report-only DEFAULT = zero mutation — `action_mode` gates BOTH arm dispatch AND `_remediate_stalled_queue_prs`; strictly more conservative than today's `dry_run`-defaults-to-mutate posture (both judges agree this holds and is the highest-value win).
- Single active arm path in the shipped config; a CI gate + pre-commit hook assert queue mutations are reachable only after `ArmGateDecision.ARM`.
- Genuine tri-state facts threaded end-to-end so a draft / thread-blocked / non-CLEAN PR can no longer forge GREEN.
- Wave-cap bounds per-pass blast radius to small N; priority orders the pass (CI-process fixes → OCC unblockers → runner/fleet fixes → docs/dependabot last).

## Risks

- Deregistering entry_points assumes NO cluster/out-of-repo producer to the three legacy subscribe topics (`merge-sweep-triage.v1`, `pr-auto-merge-arm.v1`, `auto-merge-requested.v1`); grep only proved no in-repo producer. If a producer may exist, ship hard-gate-only (gated no-op protects even a live publish), defer deregistration.
- Flipping remediation to zero-mutation-by-default means stalled queue PRs stay un-remediated unless a tick explicitly opts into ENFORCE + `enable_stall_remediation` — trades autonomy for report-only safety.
- Adding fields + a new node + rerouting dispatch breaks recorded golden-chain fixtures → must be re-recorded.

## Operator decisions remaining (the forks)

1. **Does queue-stall remediation count as an "arm path" for the "exactly one arm path" invariant?** Recommended interpretation: it is a distinct re-mint on an already-armed PR, under the same envelope but its own default-off opt-in, NOT routed through the readiness gate. If the operator insists on literally one `enablePullRequestAutoMerge` call site, remediation stays permanently disabled and stalled queues rely on manual/Codex remediation.
2. **Confirm no cluster/out-of-repo producer** to the three legacy topics before hard deregistration (else ship hard-gate-only).
3. **Whether the first ENFORCE wave arms-only or also enables stall remediation**, and the `wave_cap` value (small N).
4. **Accept reduced autonomy** for report-only safety, or wire an explicit enforce-remediation tick.
