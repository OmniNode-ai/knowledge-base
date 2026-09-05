---
type: plan
status: active
date: "2026-07-05"
title: "Delegation to CI integration — design"
topics: [delegation, ci, gates, model-tiering]
---

# Delegation → CI-integration design (WS-D / D4)

**Author:** WS-D/D4 design lane (agent).
**Date:** 2026-07-05.
**Status:** DESIGN — this document is the spec; no code lands from this PR (docs-only).
**Driver:** the canonical rolling plan `ROLLING_SEVEN_DAY_PLAN.md` §2 WS-D/D4 (operator directive 2026-07-05) + §0 operating rules.
**Product framing:** "delegation and the self-extending agent ARE the product." D4 is the point where delegation stops being a demo and starts doing the platform's own daily CI work — under the same gates a human contributor is held to, with no privileged merge path.

---

## 0. Scope and non-goals

**In scope.** How `onex delegate` authors *real* daily CI artifacts — PR fixes, OCC receipts, node contracts+handlers, unit tests, dod_evidence — such that:

1. every artifact is gated by its **existing** validator (receipt gate, contract validators, pytest, dod_verify), never blind-applied;
2. there is **no self-merge** — the human/queue merge path is unchanged;
3. the whole thing is wired as a **real CI job + pre-commit hook**, not an opt-in script (§0 rule 5: *enforcement, not detection*);
4. adoption is **measured** via Skill Evidence Rows and only widens on an evidence ratchet (**≥70% ACCEPTED at ≥20 delegated artifacts** before a tier widens);
5. failure is **honest** — a provider-down / 429 / timeout surfaces a typed error and rolls back, never a silently fabricated artifact.

**Non-goals.**
- Not a new merge mechanism. Delegation produces a branch + PR like any contributor; GitHub's queue merges it.
- Not a new LLM-routing layer. Provider/tier selection stays inside `node_delegate_skill_orchestrator`; D4 consumes it.
- Not a replacement for the SEA graded benchmark (WS-P / D3). That proves *ladder quality*; D4 proves *artifacts survive the gates*. They compose (§9), they do not overlap.
- Not "let the model self-approve." Every gate is an existing, independently-owned validator. D4 adds no new authority; it removes the human keystrokes between a detected task and a gated PR.

---

## 1. What already exists (do not reinvent)

D4 is a generalization of a pattern that is **already landed and green**, not a greenfield build. Slice 0 shipped as **omnimarket#1612** (MERGED 2026-07-05). Naming the concrete surfaces so this design binds to real code:

| Surface | Location (module / node / repo) | Role |
|---|---|---|
| `onex delegate "<prompt>"` CLI | `omnibase_infra.cli.cli_delegate` | Single-command LLM invocation → typed `ModelSkillResult[ModelDelegateSkillResponse]`. Task-type classified (`test`/`document`/`research`/`code_generation`/`refactor`/`reasoning`/`review`); returns `status, response, model_name, provider, task_type, quality_gate_passed, metrics`. |
| `node_delegate_skill_orchestrator` | node in omnimarket | The delegation orchestrator the CLI dispatches. Owns provider-tier routing. Registered in the infra CLI `skill_mapping.yaml` as skill `delegate`. |
| `HandlerDelegatedFix` (node `node_pr_delegated_fix_effect`) | omnimarket | **Slice 0.** The proven end-to-end "delegation authors a CI artifact" pipeline (deterministic ruff fix). This is the scaffold D4 generalizes. |
| `is_delegation_eligible()` (module `delegation_eligibility`) | node `node_pr_lifecycle_fix_effect`, omnimarket | Pure, side-effect-free eligibility gate: blast-radius cap, path/keyword denylist, two-strike escalation. Reused verbatim by every artifact class. |
| `node_delegation_quality_gate_reducer` | node in omnimarket | Existing per-response quality gate (`quality_gate_passed`). |
| SEA graded ladder | `omnimarket.delegation.graded_ladder` | Ladder-quality separation evidence (D3 feed). |
| M5 Skill Evidence Rows | the `M5-capstone-dogfood` dogfood-evidence set (under the repo `docs` tree) | The durable measurement surface. Result classes: `skill-success \| skill-failed-manual-fallback \| skill-not-ready \| skill-blocked-by-runtime \| manual-exception-approved`. |

### 1.1 The Slice-0 pipeline, step by step (this is the template)

`HandlerDelegatedFix.handle()` already encodes the exact shape D4 needs. Every artifact class is a re-parameterization of these steps:

1. **Resolve a worktree** (`ProtocolWorktreeResolver`). If the resolved path's `.git` is a *directory* (canonical clone, not a worktree) → `REFUSED_NOT_A_WORKTREE`. Delegation never mutates a canonical clone (mirrors CLAUDE.md rule 9).
2. **Author** the change (`ProtocolRuffFixRunner` in Slice 0 — the *only* step that varies per class).
3. **No-op guard.** If authoring produced no diff → `NO_CHANGES`.
4. **Re-check blast radius against the ACTUAL diff** (not the caller-reported diff, which can be stale): `> MAX_DELEGATION_FILES (3)` or `> MAX_DELEGATION_LINES (60)` → `discard_changes()` + `REFUSED_SIZE_GATE`.
5. **Re-check eligibility/denylist against the ACTUAL diff** → `discard_changes()` + `REFUSED_DENYLIST`.
6. **Commit with a provenance trailer:** `delegated-by: <model> run: <run_id>`.
7. **Gate through the EXISTING flow.** Slice 0 re-enters `node_pr_polish` (gate → verify → push → CodeRabbit triage → auto-merge arm) via its CLI with `--skip-repair-dispatch` and **`--no-automerge` always set**. The pr_polish flow *never pushes on a precommit/gate failure* — so the "don't ship a broken artifact" property is satisfied *by construction of the existing gate*, not by anything the delegation handler asserts about itself.
8. **Map to a typed outcome.** `EnumDelegatedFixOutcome`: `ACCEPTED | NO_CHANGES | GATE_FAILED | REFUSED_SIZE_GATE | REFUSED_DENYLIST | REFUSED_NOT_A_WORKTREE | ERROR`. Every outcome is a durable `ModelDelegatedFixResult` receipt. Non-`ACCEPTED` is never silently swallowed.

Topics: `onex.cmd.omnimarket.pr-delegated-fix-start.v1` → `onex.evt.omnimarket.pr-delegated-fix-completed.v1`.

### 1.2 The safety bars, as already numbered in the code

These are not aspirations; they are enforced in `handler_delegated_fix.py` / `delegation_eligibility.py` today. D4 preserves every one and adds nothing that weakens them:

- **#1/#2 — never push on a gate failure.** Owned by the existing `node_pr_polish` flow, not by delegation.
- **#5 — `RECEIPT_FAILURE` is never delegation-eligible.** It stays on the agent path unconditionally.
- **#6 — a delegated artifact never self-arms auto-merge.** `--no-automerge` is hard-coded on the re-entry.
- **#7 — two-strike permanent escalation.** After 2 consecutive delegated failures on a task, it permanently routes to the agent path.
- **Denylist (hard refusal on any hit):** path substrings `onex_change_control`, `deploy-gate`, `no-raw-prod-bypass`, `prod_promotion_grants`, and the auth markers `auth_`, `_auth`, or an `auth` path segment; keywords `security, auth, crypto, injection, secret, password, credential, token`.

**Design principle:** D4's job is to add *artifact classes* and the *enforcement + ratchet wiring around them*. It must not add a new authoring step that bypasses steps 4–8. If a new class cannot express itself inside "author → re-check blast radius → re-check denylist → gate via an existing validator → typed outcome," that is a signal the class is not ready, not a signal to loosen the scaffold.

---

## 2. Artifact classes and per-class validator gates

Each class is defined by exactly three things: (a) the **authoring step** (task_type + how the LLM output becomes a diff), (b) the **class-specific validator** that gates *shape* (that the diff is actually a member of the class and nothing else), and (c) the **existing full gate** it re-enters. (a) varies; (b) is new-but-thin per class; (c) is always an already-owned validator.

| Class | Authoring (`onex delegate`) | Class-specific shape validator (new, thin) | Existing full gate (unchanged) | Increment |
|---|---|---|---|---|
| **PR fix (deterministic)** | ruff format + `ruff check --fix` (zero-LLM) | blast-radius + denylist re-check | `node_pr_polish` (pytest, mypy, pre-commit, receipt gate) | **Slice 0 — LANDED** |
| **Docstrings** | `--task-type document` → insert docstrings | `validator_docstring_only_diff` (AST: only docstring string-constants changed; no logic node delta) | `node_pr_polish` full suite | **Slice 1** |
| **OCC receipts** | `--task-type document`/templated → net-new receipt YAML | OCC preflight: net-new-file-only, `Evidence-Source`/`Evidence-Ticket` present, per-entry hash, append-only | Receipt-Gate (the `verify` workflow) + `occ-preflight` | Slice 2 |
| **Unit tests** | `--task-type test` → new `test_*` function(s) | test-only-diff (only test files touched; no product-source delta) + the new test must FAIL-then-PASS against a mutation (guard against vacuous asserts) | `node_pr_polish` full suite (`pytest -v`, no `-k`) | Slice 3 |
| **Node contracts + handlers** | `--task-type code_generation` → contract.yaml + handler | contract validators + `runtime_sweep` (handler wired, topics have producer+consumer) + metadata dependency check | full suite + `deploy-gate` | Slice 3 |
| **dod_evidence** | `--task-type document` → evidence block on a ticket contract | `dod_verify` DurableEvidenceGate (RECEIPT_TRACKED, CONTRACT_CITES_MERGE_COMMIT, CONTRACT_ON_OCC_MAIN) | `dod_verify` receipt | Slice 4 |
| **Logic-changing** | `--task-type code_generation`/`refactor` | *(no shape shortcut — full diff review)* | full suite + hostile_reviewer + human review | Slice 5 (gated on all prior tiers at ratchet) |

**Why a class-specific *shape* validator on top of the full gate.** The full suite (pytest/mypy) proves the change is *correct*; it does not prove the change is *what the class claims to be*. A "docstring" artifact that passes pytest could still have smuggled a one-line logic change. The shape validator closes that gap: it asserts the diff is a pure member of its class (only docstrings changed / only tests touched / only a net-new OCC file). Without it, "docstring tier" silently becomes "arbitrary code tier." The shape validator is the mechanism that makes the tiered ratchet meaningful — you cannot widen blast radius by mislabeling a class.

**Ordering rationale.** Classes are ordered by blast radius and by how mechanical their shape validator is. Docstrings first: pure-text, AST-verifiable as logic-free, lowest blast radius. OCC receipts next: net-new-file-only is trivially verifiable and the receipt gate is already strict. Tests: slightly higher risk (a vacuous test passes the suite), needing the mutation check. Contracts/handlers: real logic, but contract-validated and runtime-swept. Logic-changing last and hardest-gated.

---

## 3. The generalized authoring pipeline

Recommended structure: **keep one scaffold, make the authoring step pluggable.** The Slice-0 handler already injects every dependency as a Protocol (`ProtocolWorktreeResolver`, `ProtocolRuffFixRunner`, `ProtocolGitDiffAdapter`, `ProtocolPrPolishRunner`). Generalize by promoting the authoring step to a protocol and the gate re-entry to a protocol:

```
ProtocolArtifactAuthor.author(worktree, task) -> None        # writes the diff into the worktree
ProtocolClassShapeValidator.check(worktree, diff) -> Verdict # asserts the diff is a pure member of the class
ProtocolExistingGate.run(...) -> GateOutcome                 # re-enters the already-owned validator
```

- Slice 0 = `RuffAuthor` + `NullShapeValidator` (deterministic; blast-radius/denylist suffices) + `PrPolishGate`.
- Slice 1 = `DocstringDelegateAuthor` (calls `onex delegate --task-type document`) + `DocstringOnlyDiffValidator` + `PrPolishGate`.
- Later slices swap `ProtocolExistingGate` for `OccPreflightGate` / `DodVerifyGate` as appropriate.

The invariant sequence (worktree resolution → author → no-op guard → blast-radius re-check → denylist re-check → commit-with-trailer → existing gate → typed outcome) is written **once** and reused. A new class contributes an author + a shape validator; it cannot contribute a new way to skip the gate.

**Decision to record (not blocking this doc):** whether Slice 1+ extends `node_pr_delegated_fix_effect` in place (new authoring adapter, PR-agnostic entry) or lands a sibling `node_delegated_authoring_effect` that the PR-fix node becomes one caller of. Recommendation: **generalize in place first** (add the authoring protocol to the existing node, keep the ruff path as the default author), and only split to a sibling node if the PR-fix-specific `block_reason`/`pr_polish` coupling makes the shared node incoherent. Rationale: the safety scaffold is identical; a premature split duplicates it and invites drift (two places to weaken a bar).

---

## 4. Provenance and the enforcement surface (CI job + pre-commit hook)

This is the §0-rule-5 core: the gate that makes delegation-authored artifacts *unmergeable unless they passed their class validator* must be a **required status check + pre-commit hook**, not an opt-in convenience. Detection that isn't wired as a pre-merge gate gets ignored.

### 4.1 Provenance trailer (extend the Slice-0 trailer)

Slice 0 already writes `delegated-by: <model> run: <run_id>`. D4 extends it to carry the class and the shape-validator receipt so the gate can verify without re-deriving:

```
delegated-by: <model>
delegation-run: <run_id>
delegation-class: docstrings            # one of the class ids in §2
delegation-shape-receipt: sha256:<...>  # content-addressed shape-validator receipt
```

The receipt is a durable, content-addressed artifact (same `.onex_state` artifact store the Slice-0 receipts already write to), recording: class, worktree tree hash, shape-validator verdict, full-gate outcome, run_id, timestamp.

### 4.2 CI job — `delegation-provenance-gate` (required status check)

A new GitHub Actions workflow `delegation-provenance-gate.yml` (under `.github` `workflows`) running a checker (`check_delegated_artifact_provenance.py` or, preferably, a node `node_delegation_provenance_gate` so the logic is contract-owned, not a freestanding script). On every PR `[opened, edited, synchronize]`:

1. Enumerate commits in the PR range.
2. For each commit carrying a `delegated-by:` trailer:
   a. Parse `delegation-class` + `delegation-shape-receipt`.
   b. Resolve the referenced shape-validator receipt from the durable store; assert its tree hash == the commit's tree and its verdict == PASS. (Fail closed if the receipt is missing/forged/mismatched — a delegated commit with no passing receipt is rejected.)
   c. Assert the class's shape validator *actually is* the one named (guards a spoofed trailer claiming a lenient class).
3. **No-self-merge assertion:** verify the PR is not armed for auto-merge by the delegation identity, and the merger (once merged) is the human/queue path — never the delegation bot. (Reuses the fact that `--no-automerge` is hard-set upstream; this is the merge-side backstop.)
4. Fail the check if any delegated commit lacks a passing, tree-matched shape receipt, or if a delegated PR self-armed.

Wire it into `required_status_checks` on `dev` for the repos that accept delegated artifacts, in the **same PR that adds the workflow** (§0 rule 5 — a gate that isn't required is advisory).

### 4.3 Pre-commit hook — `reject-ungated-delegated-artifact`

Mirror of the CI job at commit time (same posture as the existing `reject-deploy-gate-skip-token.sh` and `no-raw-prod-bypass`): if the commit being created carries a `delegated-by:` trailer, the hook verifies a passing shape-validator receipt exists for the exact staged tree. No receipt → commit rejected locally. This closes the "push locally, fail remotely later" window — the delegated commit cannot even be created without its gate having run.

**No escape hatch by free-text.** As with the deploy-gate token, the only bypass is a real user-approval receipt id in a structured comment — never a self-written justification. A delegation bot cannot issue itself that receipt.

---

## 5. Ratchet mechanics

The ratchet governs **widening**: enabling a new class, or loosening a class's blast-radius/denylist caps. Widening is mechanically gated on recorded evidence; it is not an honor-system judgment call.

### 5.1 What "success" is measured on

Every delegated authoring attempt already emits a typed outcome receipt (§1.1 step 8) and a Skill Evidence Row (§6). **Success = outcome `ACCEPTED`** (authored + passed the full existing gate + landed via the normal merge path). Everything else — `REFUSED_*`, `GATE_FAILED`, `NO_CHANGES`, `ERROR` — is a non-success for ratchet purposes, but only `ACCEPTED` and `GATE_FAILED` count toward the *denominator* (a refusal or no-op is the safety bar working, not the model failing; counting refusals against the model would perversely discourage conservative denylists). Precise definition:

- **numerator** = count of `ACCEPTED` for the class.
- **denominator** = count of (`ACCEPTED` + `GATE_FAILED`) for the class — attempts where the model actually produced a diff that reached the gate.
- **success ratio** = numerator / denominator.

### 5.2 The threshold

A class tier may widen only when, for that class: **denominator ≥ 20 AND success ratio ≥ 0.70.** Below either bound the tier is frozen at its current caps. (These are the operator's numbers: ≥70% success at ≥20 delegated artifacts.)

### 5.3 Ratchet config as a checked-in, CI-verified file

The current tier state lives in a checked-in file (proposed: `ratchet.yaml` in `omnimarket.delegation`, co-located with `graded_ladder`, or in the onex_change_control repo if it should be OCC-governed). Per class it declares: `enabled: bool`, `max_files`, `max_lines`, and the `evidence_ref` (the aggregated evidence backing the current tier).

A widening is a PR that raises a cap, enables a class, or relaxes a denylist entry. A CI gate (`check_delegation_ratchet.py` / a `node_delegation_ratchet_gate`) verifies: for any diff to `ratchet.yaml` that *loosens* a tier, the PR must cite ≥20 recorded evidence rows for that class whose aggregate success ratio ≥ 0.70. The gate recomputes the ratio from the durable evidence rows (not from the PR's claim) and fails if the evidence does not back the widening. Tightening (lowering caps, adding denylist entries) is always allowed with no evidence bar — the ratchet only resists loosening.

This makes the ratchet the same *kind* of object as branch protection: state is in a file, mutation is gated by a required check, and the check reads ground truth rather than trusting the PR body.

### 5.4 Interaction with the two-strike bar

The ratchet (aggregate, per-class, governs widening) is orthogonal to the two-strike escalation (per-task, governs routing). Two-strike keeps a *specific pathological task* off the delegation path after 2 failures; the ratchet keeps a *whole class* frozen until it earns width. Both stay in force.

---

## 6. Measurement — Skill Evidence Rows

Every delegated authoring attempt appends one row to the M5 dogfood evidence surface (the `M5-capstone-dogfood` set), reusing the existing result-class taxonomy so D4 measurement is not a parallel system:

| Delegation outcome | M5 result class |
|---|---|
| `ACCEPTED` | `skill-success` |
| `GATE_FAILED` | `skill-failed-manual-fallback` (the artifact was authored but the gate rejected it; a human/agent takes over) |
| `REFUSED_*` | `skill-not-ready` (the safety bar refused — the class/task is out of scope, not a failure to record against the model) |
| `ERROR` (provider down / 429 / timeout) | `skill-blocked-by-runtime` |
| operator-forced delegation of a normally-refused task | `manual-exception-approved` |

Each row carries: class, task id, model/provider, outcome, files/lines changed, commit sha (if any), shape-receipt ref, and the durable `ModelDelegatedFixResult`/analog receipt ref. The ratchet computation in §5 reads these rows. Rows are the *only* input to widening decisions — no side-channel "it felt fine."

---

## 7. Honest-failure and fallback behavior

The operator hard-requirement: provider-down / 429 / timeout surfaces a typed error and never a fabricated artifact. This is already the Slice-0 behavior and D4 preserves it as an invariant:

- **Typed outcomes only.** Every failure path returns a typed outcome (`ERROR`, `GATE_FAILED`, `REFUSED_*`) with a populated `detail`/`error`. There is no code path that returns `ACCEPTED` without a committed sha that passed the existing gate.
- **Rollback on refusal.** Blast-radius/denylist refusal calls `discard_changes()` — the worktree is left clean; nothing half-authored is committed or pushed.
- **Provider failure = escalation, not fabrication.** A 429/timeout from the delegated model propagates through the tier ladder (a landed fix confirmed transport 429/timeout now *escalates* through tiers rather than terminating), and if the ladder exhausts, the attempt returns `ERROR` (M5 class `skill-blocked-by-runtime`) and the task falls back to the agent path. The pre-bump silent-termination behavior was install/publish drift, not a code regression — but the design bar is: **exhausted providers → typed ERROR → agent fallback, never an empty/hallucinated diff presented as done.**
- **No claim without evidence.** `GATE_FAILED` explicitly surfaces the underlying gate's error message rather than reporting success — matching the CLAUDE.md doctrine "agents lie about success; verify via the gate, not the self-report." The gate, not the delegation handler, is the source of truth for pass/fail.

---

## 8. Composition with the existing delegation stack

- **`node_delegate_skill_orchestrator`** is the invocation primitive. D4's authoring adapters call `onex delegate --task-type <t>` (or dispatch the node directly) and consume the typed `ModelDelegateSkillResponse`. Tier/provider selection and per-response `quality_gate_passed` stay inside the orchestrator; D4 does not re-implement routing.
- **`node_pr_delegated_fix_effect`** is Slice 0 and the scaffold. D4 generalizes its authoring step (§3), preserving its safety bars and typed outcomes.
- **`node_delegation_quality_gate_reducer`** gates the *response* (is the LLM output usable). The class shape validator gates the *diff* (is the change a pure member of its class). The existing full gate (pytest/mypy/receipt) gates *correctness*. Three distinct gates, composed in series — a delegated artifact must pass all three plus blast-radius/denylist.
- **SEA graded ladder / D3 beta-readiness gate.** D3 asks "is the ladder good enough to ship" (quality separation floor→ceiling). D4 asks "do delegated artifacts survive our gates in daily use." D4's adoption evidence (§6 rows, §5 ratchet) *is* the D3(3) "adoption evidence" input, and D4's honest-failure behavior *is* the D3(4) "honest failure/fallback" criterion. D4 is thus both a product surface and a feeder of the D3 gate — not a parallel track.
- **M5 dogfood rail.** D4 rows live in the same directory and taxonomy as the ops-skill dogfood rows, but measure the *product* (delegation authoring), distinct from ops-skill dogfooding (merge_sweep/dod_verify/etc.). Same measurement substrate, different subject.

---

## 9. Increment roadmap

| Slice | Class | Gate composition | Ratchet entry condition |
|---|---|---|---|
| **0 — LANDED** | Deterministic PR fix (ruff) | blast-radius + denylist + `node_pr_polish` | shipped (omnimarket#1612) |
| **1 — next (this design → impl)** | Docstrings | `DocstringOnlyDiffValidator` + `node_pr_polish` | enabled at conservative caps (≤3 files/≤60 lines); widen after ≥20/≥70% |
| 2 | OCC receipts | net-new-file + `occ-preflight` + receipt gate | gated on Slice 1 at ratchet |
| 3 | Unit tests; node contracts+handlers | test-only-diff + mutation check / contract validators + runtime_sweep | gated on Slice 2 at ratchet |
| 4 | dod_evidence | `dod_verify` DurableEvidenceGate | gated on Slice 3 at ratchet |
| 5 | Logic-changing | full suite + hostile_reviewer + human review | gated on all prior at ratchet; never un-gated |

Each slice is: add an authoring adapter + a class shape validator + register the class in `ratchet.yaml` (disabled or at conservative caps) + prove the provenance gate rejects an un-gated artifact of that class. No slice loosens the scaffold.

---

## 10. Slice 1 — concrete implementation plan (docstrings)

This is the buildable next step; it does not land in this docs PR.

### 10.1 Target and blast radius
- **Artifact:** missing docstrings on public modules/functions/classes that currently FAIL a docstring-presence check.
- **First target set:** a single low-risk, denylist-clean module directory (pick a pure-compute node package with no `auth`/`security`/`secret` in path), so the whole slice runs inside the existing ≤3-files/≤60-lines cap per attempt. One symbol set → one small PR per attempt.
- **Explicitly out:** any file matching the §1.2 denylist; anything in the onex_change_control repo, `deploy-gate`, or auth/security paths.

### 10.2 Authoring adapter — `DocstringDelegateAuthor`
- Detect missing-docstring targets via the presence check (§10.3).
- For each target, call `onex delegate "<prompt to write a docstring for <symbol> given its signature/body>" --task-type document` (the `document` task_type already routes correctly in `cli_delegate.py`'s classifier).
- Insert the returned docstring at the symbol via AST-anchored edit (position the string literal as the first statement of the module/function/class body). Do **not** free-text splice — anchor on the AST node to avoid corrupting adjacent code.

### 10.3 Class shape validator — `validator_docstring_only_diff`
- Parse the pre-change and post-change file with `ast` (and, to be robust to formatting, compare with a normalized/`ast.unparse` round-trip).
- **Assert:** the *only* delta between the two ASTs is the addition/replacement of docstring string-constants (the first-statement `Constant` of a module/`FunctionDef`/`AsyncFunctionDef`/`ClassDef` body). Any other node delta (a changed expression, a new import, a modified default) → `Verdict.FAIL` → the artifact is refused as "not a pure docstring change" (mislabeled class).
- This is the mechanism that keeps "docstring tier" from silently becoming "arbitrary code tier."

### 10.4 Existing gate re-entry (unchanged)
- Re-enter `node_pr_polish` exactly as Slice 0 does: `--skip-repair-dispatch --no-automerge`, full pytest/mypy/pre-commit/receipt gate. A docstring change to a `.py` file still runs the whole suite — a docstring that breaks a doctest or a `ruff` D-rule fails here, correctly.

### 10.5 CI-job stub (the enforcement surface)
- Add the `delegation-provenance-gate.yml` workflow (skeleton): trigger `pull_request: [opened, synchronize, reopened]`; single job running the provenance checker (§4.2) over the PR commit range; fail on any `delegated-by:` commit lacking a passing, tree-matched `delegation-shape-receipt`. Skeleton short-circuits (exit 0) on `merge_group` SHAs, matching the repo's deploy-gate convention so it does not wedge the queue.
- Add the pre-commit hook `reject-ungated-delegated-artifact` (§4.3) to `.pre-commit-config.yaml` in the same PR.
- Wire `delegation-provenance-gate` into `required_status_checks` on `dev` for the target repo in the **same PR** (§0 rule 5). Verify with `gh api repos/OmniNode-ai/<repo>/branches/dev/protection/required_status_checks --jq '.contexts'`.

### 10.6 Slice-1 acceptance
- One real docstring PR authored end-to-end by `onex delegate --task-type document`, gated by `validator_docstring_only_diff` + full `node_pr_polish`, landed via the **normal queue merge** (no self-merge), with a Skill Evidence Row recorded.
- Negative control: a planted artifact that smuggles a one-line logic change under a `delegation-class: docstrings` trailer is **rejected** by `validator_docstring_only_diff` and by the provenance gate — proving the shape validator and the CI enforcement actually bite (same negative-control discipline as the M5 aislop canary).
- Provenance gate proven **required**: a delegated commit with no passing shape receipt fails the PR check.

### 10.7 Slice-1 ticket + PR
- File the Slice-1 implementation ticket in the internal tracker (never an invented id), blocked-by this design.
- Implementation lands in **omnimarket** (node/handler/validator) with an **OCC companion** (heavy repo — `Evidence-Source: OCC#<n>`), plus the CI workflow + pre-commit hook + branch-protection wiring. Full local gates before push; PR title cites the Slice-1 ticket.

---

## 11. Open questions / risks (surface, do not paper over)

1. **Where does `ratchet.yaml` live** — omnimarket (co-located with the delegation code) or the onex_change_control repo (OCC-governed so widening rides the receipt gate)? Leaning OCC-governed, since widening delegation authority is exactly the kind of change that should carry a receipt. Operator/architecture call.
2. **In-place generalization vs sibling node** (§3) — recommend in-place first; revisit if PR-fix coupling forces a split.
3. **Shape-validator coverage per class is the whole ballgame.** A weak shape validator (e.g. a docstring check that misses an AST edit) collapses the tier guarantee. Every class's shape validator needs its own negative-control test proving it rejects a mislabeled diff, or the class does not ship.
4. **Provenance trailer forgery.** The gate re-derives/re-validates against the durable receipt store rather than trusting the trailer text; a forged `delegation-shape-receipt` that doesn't resolve to a tree-matched PASS receipt fails closed. This must be tested explicitly (forge a trailer → gate rejects).
5. **Publish-drift (recurring, D1 note).** Merged omnimarket fixes do not reach `onex delegate` until the wheel is re-co-installed into the omnibase_infra venv. D4 authoring reliability depends on the installed omnimarket being current; the ratchet's denominator will under-count if attempts run against a stale wheel. Track the durable co-install fix as a dependency of steady-state D4 adoption.
6. **Interaction with codex-nightly autonomous merges.** The no-self-merge bar must hold even under the shared codex identity; the merge-side backstop (§4.2 step 3) must treat a codex auto-merge of a `delegated-by:` PR the same as any other — the human/queue path, not the delegation bot arming its own merge.

---

## 12. Summary

D4 is not new machinery; it is the generalization of a landed, green pipeline (Slice 0 / omnimarket#1612) plus the enforcement and ratchet wiring that turns it into a governed daily-CI contributor. The three load-bearing additions over Slice 0 are: (1) a **class shape validator** per artifact class, so a tier means what it says; (2) a **required provenance gate + pre-commit hook**, so a delegated artifact is unmergeable unless it passed its class validator (enforcement, not detection); and (3) a **CI-verified ratchet file**, so a tier widens only on ≥20 attempts at ≥70% success read from durable evidence, not on a judgment call. Every existing safety bar is preserved; no new merge authority is created; failure stays typed and honest. Slice 1 (docstrings) is the concrete next build, specified in §10.
