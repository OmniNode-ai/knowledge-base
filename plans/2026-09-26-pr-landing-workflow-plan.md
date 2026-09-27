---
type: plan
status: active
date: "2026-09-26"
title: "PR landing workflow: change-control companions and the mechanical landing rules as one ONEX workflow"
topics: [pr-lifecycle, change-control, merge, workflow, fsm, projection, determinism]
---

# PR landing workflow: change-control companions and the mechanical landing rules as one ONEX workflow

state_as_of: 2026-09-26T23:30:00Z

**Goal.** Every mechanical step between a product PR push and its merge runs as one event-driven, deterministic ONEX workflow in omnimarket: derive and create the change-control companion, stamp the product PR, arm the companion, regenerate it on conflict, re-run the product PR's change-control checks when the companion merges, update the branch when behind, re-run timed-out checks, and arm the product PR when green. No agent does mechanical landing work, and only real code failures reach an agent.

**Decision this plan follows (2026-09-26).** Change-control companion PRs are generated and carried to merge automatically end to end (create on push, stamp the product PR, regenerate on conflict, land when green, re-run the product PR's checks), with no hand work by agents. Hand-authored companions stop once this path lands.

**Status.** Plan only. No code, workflow or gate has changed. The internal tracker holds one epic and one ticket per task for waves 1 and 2. Waves 3 and 4 are ticketed when wave 2 exits, because the seam between waves is the next wave's first step and its shape depends on what wave 2 finds.

## 1. The canary it is modelled on

The delegation chain is the one ONEX workflow on this platform that already runs end to end under proof, so this workflow copies its shape rather than inventing one. Each row was read from the `dev` branch of the named repository on 2026-09-26.

| Delegation pattern | Where it lives | What this workflow reuses |
|--|--|--|
| Correlation-keyed orchestrator FSM with a `state_machine:` block in the contract | omnimarket `node_delegation_orchestrator/contract.yaml` (states RECEIVED to COMPLETED or FAILED) | the same block, keyed by `(repository, pr_number)` |
| Durable per-request FSM rows with optimistic concurrency and an in-row outbox (`state_io`) | the same contract; runtime wiring in omnibase_infra `runtime/auto_wiring/handler_wiring.py` | a `state_io` table `pr_landing_workflow_state` |
| Bounded non-terminal time with a restart policy (`completion_bound`) | the same contract | a bound per state; expiry hands the PR to an agent with reason `stalled` |
| Class-name to topic routing of typed terminals | the same contract, `published_events` | one terminal class per outcome |
| A pure routing reducer beside the orchestrator | `node_delegation_routing_reducer` | `node_pr_landing_reducer`, definition-B |
| A seam test over InMemoryTransport | omnibase_infra `tests/integration/runtime/test_s8_delegation_fsm_seam.py` and its CI gate | a landing seam test of the same shape |
| Chain tests from the contract walker | omnimarket `tests/chains/delegation/` and `tests/chains/chain_assert.py` | `tests/chains/pr_landing/` |
| A scheduled live chain canary with per-link verdicts | omnibase_infra `.github/workflows/chain-canary.yml` and `node_chain_canary_effect` | a landing chain canary (wave 3) |
| A projection pair: a pure fold plus a runner writer | for example omnimarket `node_projection_ci_attempt_outcome` with `omnimarket.projection.runner.BaseProjectionRunner` | `node_projection_pr_landing` |

## 2. Existing assets

Most of the mechanics already exist as separate nodes, workflows and scheduled jobs. The work is composing them under one FSM and removing the hand steps, not rebuilding them.

| Asset | Repo | State on 2026-09-26 | Reuse or replace |
|--|--|--|--|
| `call-occ-autobind.yml` publisher, fires on opened, synchronize, reopened and ready_for_review | the product repos | live; publishes `onex.cmd.omnimarket.occ-autobind.v1` to the dev-lane bus | reuse as ingress I1 (a PR was pushed) |
| `OccCompanionEmitter` in `node_pr_lifecycle_fix_effect`, with the pure rendering seam `occ_evidence_stamp.py` | omnimarket | the live producer; mints, stamps the product body in the same run, arms the companion | reuse behind the companion seam (T5); replaced by the compute path later (section 7) |
| `occ_autobind_outcome.py`: MINTED, DECLINED or ERROR as a head-bound check-run | omnimarket | live | reuse; the typed outcome also goes on the bus (T5) |
| `node_occ_companion_compute` (pure plan and attestation oracle), `node_occ_state_effect` (read), `node_occ_companion_effect` (write) | omnimarket | experimental, not the live producer | the derivation-in-a-compute-handler target; parity harness in T5 |
| Per-ticket batch companion behind `OMNI_OCC_COMPANION_BATCH_MODE` | omnimarket | merged, switch off | reuse; regenerate calls the batch rebuild when the switch is on |
| Conflict re-mint on synchronize | omnimarket | in review | the workflow issues an explicit `regenerate` command instead of waiting for a push |
| Scheduled companion-merge heal (re-runs failed preflights after the companion merges) | omniclaude `occ-companion-merge-heal.yml`; ports to omnimarket, omnibase_infra and one private infrastructure repo | live in omniclaude; ports open | kept as the fallback until wave 4, then retired |
| `occ-autobind-mint-verify.yml` (replays the publisher once when no stamp appears after 150 s) | omnimarket | live | retired at wave 4; the FSM verifies the stamp |
| Deterministic check classifier `merge_control/reason_code_classifier.py` (stale_context, github_api_outage, runner_infra, process_gate_refused, cancelled, product_failed) | omnimarket | live, used by the merge sweep | reuse; extended with change-control sub-reasons (T3) |
| `node_pr_lifecycle_triage_compute` (green, red, conflicted, occ_dependency, needs_review) | omnimarket | live | extended with a per-head operation (T3) |
| `node_pr_arm_gate_compute`: the fail-closed ARM or WITHHOLD decider with `action_mode` and a kill switch | omnimarket | active | every arm and enqueue intent passes through it; `action_mode` report_only is the shadow mode of wave 3 |
| `node_ci_rerun_effect` (rerun-failed-jobs), `node_merge_sweep_auto_merge_arm_effect` (GraphQL arm), `handler_auto_rebase` (update-branch) | omnimarket | live, contract-declared `GITHUB_TOKEN` | their REST and GraphQL calls move into one transport module the new effect uses (T9) |
| `node_pr_lifecycle_orchestrator` family (the batch merge sweep) | omnimarket | live as a sweep | left in place; it is not the per-PR workflow. Retiring its companion and arm legs is a wave 4 decision |
| `onex.evt.github.pr-merged.v1` Actions producers | omnimarket `pr-merged-publisher.yml`, omnibase_infra `pr-merged-event.yml` | live in two repos; none in onex_change_control | ingress I2; companion merges need I3 |
| Fetch-only git mirror effect `node_git_query_mirror_effect` | omnimarket | in progress | ingress I3: merge detection from git with no REST call |
| Event-driven PR state (a conditional reader, webhook ingress and a quota topic `onex.evt.github.api-quota.v1`) | a separate planned track | planned | ingress I4 when built; nothing here duplicates it |
| `omnimarket.occ_github_auth.resolve_occ_github_token` | omnimarket | live | the only credential for companion writes, unchanged |
| `merge_control/hold_marker.py` | omnimarket | live | the hold test the reducer applies before any arm |
| A launchd clone-sync tick on a developer workstation | a host script | runs every 180 s | not used: a host script, not a node on the lab runtime; I3 uses the mirror effect on the lab instead |

## 3. What it costs today (measured)

From a read-only measurement of GitHub on 2026-09-26 between 21:16Z and 23:00Z. Product-only percentiles were recomputed from the same list of the day's merges.

| Measure | Value |
|--|--|
| Merges on 2026-09-26 | 362: 141 change-control companion PRs in onex_change_control and 221 product PRs |
| Product push-to-merge, all 221 | **p50 0.63 h, p90 4.61 h** |
| Product PRs with a companion (140) against without (81) | mean 2.44 h (p50 0.95 h) against mean 0.92 h (p50 0.21 h); 212 extra PR-hours |
| Wait after the companion merged | p50 0.41 h, p90 2.72 h |
| Open PRs meant to merge that change control blocked | 34 of 79 (104 PR-hours) |
| Companion PRs in merge conflict | 11 of 13 conflicted PRs, median 6.5 h |
| Agent drain passes over the day | 585 passes, 3,549 agent-minutes, 60 distinct merges; about 59 agent-minutes per merge |
| Passes whose notes cite companion or stamp problems | **109** (keyword match) |

The same measurement ranked the companion chain first (about 316 PR-hours) and companion conflicts second (204 PR-hours). A third blocker that day, a broken shared hygiene workflow pin, is fixed separately and is out of scope here.

## 4. Success metric

These are targets, not estimates. They are measured over the first 24 hours after the fleet cutover (wave 4) and compared with section 3.

| Metric | Baseline 2026-09-26 | Target |
|--|--|--|
| Product push-to-merge p50 | 0.63 h | at most 0.30 h |
| Product push-to-merge p90 | 4.61 h | at most 1.50 h |
| p50 gap, with a companion against without | 0.74 h | at most 0.25 h |
| Companion merge to product re-run dispatched, p90 | 2.72 h (the wait after companion merge) | at most 2 minutes |
| Drain passes spent on companion work | 109 | **0** |
| Companions touched by hand | 16 over 2026-09-25 and 2026-09-26 | 0 |

Push-to-merge is computed per PR from its last push to its merge, over `gh search prs --merged` for the window, the same method as the baseline.

## 5. Architecture

Only CONTRACT, NODE and HANDLER. Every decision is a pure definition-B handler; every GitHub or bus side effect is an effect node; state is `state_io` for the orchestrator and a projection pair for readers. No language model is called anywhere in the workflow. The bus is the transport, and no node calls another over HTTP.

```
ingress (existing publishers first, the event-driven PR state track later)
  I1 onex.cmd.omnimarket.occ-autobind.v1         a PR was pushed or became ready
  I2 onex.evt.github.pr-merged.v1                the Actions producers, two repos
  I3 onex.evt.github.pr-merged.v1 source=mirror  node_git_query_mirror_effect on the runtime tick; companion and product merges, no REST
  I4 onex.evt.github.{pull-request,check-run,check-suite,workflow-run}.v1   when the webhook track lands
        |
node_pr_landing_orchestrator   (a state_io row per repository#pr, a completion_bound per state)
   calls node_pr_landing_reducer                        pure: state + observation -> next state + intents
   calls node_pr_lifecycle_triage_compute, op classify_head_checks   pure: check facts -> verdict
   calls node_pr_arm_gate_compute                       pure: ARM or WITHHOLD, before any arm or enqueue
        |  typed commands
        +--> companion leg: onex.cmd.omnimarket.occ-autobind.v1 with op derive | regenerate | verify
        |        the producer (OccCompanionEmitter today) -> onex.evt.omnimarket.pr-landing-companion-outcome.v1
        +--> node_pr_landing_github_effect: rerun named runs | update-branch | arm | enqueue | disarm | read head checks
        |        -> onex.evt.omnimarket.pr-landing-github-completed.v1 and -failed.v1, each with a header quota reading
        |
   emits onex.evt.omnimarket.pr-landing-transitioned.v1   every transition, with a per-key seq
   emits onex.evt.omnimarket.pr-landing-agent-needed.v1   real red, declined companion, stalled
   emits onex.evt.omnimarket.pr-landing-merged.v1 and pr-landing-closed.v1   terminals
        |
node_projection_pr_landing (fold + BaseProjectionRunner writer) -> pr_landing_state, pr_landing_transitions
   read by the drain (agent-needed), the dashboard, and the section 4 metric
```

### 5.1 The state machine (frozen for wave 1)

Key: `(repository, pr_number)`. The row carries `head_sha`, `base_ref`, `ticket_ids`, `draft`, `held`, `companion` (`occ_pr` and `status`: none, open, conflicting, merged, closed or declined), `stamp_present`, `merge_state`, `armed` (with method auto_merge or queue), budgets (derive 2, regenerate 3, one re-run per check per head, update-branch 2 per head), `seq` and `entered_state_at`.

| State | Meaning | Leaves on |
|--|--|--|
| OBSERVED | a new head or first sight; the reducer evaluates at once | evaluation |
| PARKED | draft, held (label or hold marker), no ticket token, or a base branch the workflow does not serve | ready_for_review, hold lifted, body edited, new head |
| COMPANION_PENDING | a derive or regenerate command is in flight | companion outcome |
| COMPANION_OPEN | companion open, stamp on the product body, companion armed | companion merged, conflicting, or closed unmerged |
| CHECKS_PENDING | companion merged or not required; change-control reds re-run; waiting for check results | head check verdict |
| READY | every required context green, not held, not draft | arm or enqueue confirmed |
| ARMED | auto-merge armed or enqueued | merged, disarmed, hold applied, new head |
| NEEDS_AGENT | real red, declined companion, budget spent or stalled; one agent-needed event per (head, reason) | new head, or hold lifted with a manual re-evaluation |
| MERGED | terminal | none |
| CLOSED | terminal | reopened, back to OBSERVED |

| From | Observation | To | Intents |
|--|--|--|--|
| any non-terminal | pushed (new head) | OBSERVED | none |
| OBSERVED | evaluation: draft, held or no ticket | PARKED | disarm if armed |
| OBSERVED | evaluation: companion required, none bound | COMPANION_PENDING | companion.derive |
| OBSERVED | evaluation: companion bound and open | COMPANION_OPEN | companion.verify (stamp and arm) |
| OBSERVED | evaluation: companion merged, or not required | CHECKS_PENDING | github.read_head_checks |
| COMPANION_PENDING | outcome MINTED (occ_pr, stamped, armed) | COMPANION_OPEN | github.arm(occ_pr) if not armed; companion.verify if not stamped |
| COMPANION_PENDING | outcome DECLINED (reason) | NEEDS_AGENT | agent_needed(companion_declined, reason) |
| COMPANION_PENDING | outcome ERROR, budget left | COMPANION_PENDING | companion.derive (retry) |
| COMPANION_PENDING | outcome ERROR, budget spent | NEEDS_AGENT | agent_needed(companion_error) |
| COMPANION_OPEN | companion conflicting, budget left | COMPANION_PENDING | companion.regenerate |
| COMPANION_OPEN | companion closed unmerged | COMPANION_PENDING | companion.derive |
| COMPANION_OPEN | companion merged | CHECKS_PENDING | github.rerun(the failed change-control runs on the head) |
| CHECKS_PENDING | verdict green | READY | arm gate, then github.arm or github.enqueue by the repo's live merge policy |
| CHECKS_PENDING | verdict change_control_stale, budget left | CHECKS_PENDING | github.rerun(named runs) |
| CHECKS_PENDING | verdict timed_out, runner_infra or cancelled, budget left | CHECKS_PENDING | github.rerun(named runs) |
| CHECKS_PENDING | verdict stale_caller_pin or behind_required | CHECKS_PENDING | github.update_branch |
| CHECKS_PENDING | verdict product_failed, or any budget spent | NEEDS_AGENT | agent_needed(real_red, checks) |
| CHECKS_PENDING | verdict pending | CHECKS_PENDING | github.read_head_checks after the state's poll interval |
| READY | armed confirmed | ARMED | none |
| ARMED | disarmed, or hold applied | PARKED or CHECKS_PENDING | disarm on hold |
| any non-terminal | merged | MERGED | terminal pr-landing-merged |
| any non-terminal | closed | CLOSED | terminal pr-landing-closed |
| any non-terminal | completion bound expired | NEEDS_AGENT | agent_needed(stalled, state) |

An observation for a head other than the row's `head_sha` is dropped, except merged and closed. `stale_caller_pin` is the class where a re-run replays the old reusable-workflow pin, so its remedy is update-branch and never re-run.

### 5.2 Safety properties (the model checks these; the reducer tests assert them)

- **P1** Never arm, enqueue or re-arm a PR that is draft or held at the observed head.
- **P2** Never re-run a check the classifier calls product_failed; at most one re-run per (head, check).
- **P3** At most one companion command in flight per product PR, and at most one open companion per ticket when the batch switch is on (the per-ticket lease).
- **P4** Exactly one terminal event per PR; at most one agent-needed event per (head, reason).
- **P5** The workflow never merges. GitHub merges an armed or enqueued PR when the required contexts pass. No gate, ruleset or required check changes.
- **P6** Liveness: a PR that is not held, not draft and has green required contexts reaches ARMED within one observation and one effect round trip.

### 5.3 Frozen names (the seam registry for wave 1)

| Name | Owner task |
|--|--|
| `node_pr_landing_orchestrator`, `node_pr_landing_reducer`, `ModelPrLandingState`, `ModelPrLandingObservation`, `ModelPrLandingIntent`, `EnumPrLandingState` | T2 |
| `onex.evt.omnimarket.pr-landing-transitioned.v1`, `-agent-needed.v1`, `-merged.v1`, `-closed.v1` | T2 |
| operation `classify_head_checks` on `node_pr_lifecycle_triage_compute`, `ModelHeadCheckFacts`, `ModelHeadCheckVerdict`, `EnumHeadCheckVerdict` | T3 |
| `node_pr_landing_github_effect`, `onex.cmd.omnimarket.pr-landing-github-requested.v1`, `onex.evt.omnimarket.pr-landing-github-completed.v1`, `-failed.v1`, `ModelGithubQuotaReading` | T4 |
| the `op` field on the existing autobind command (`derive`, `regenerate`, `verify`), `onex.evt.omnimarket.pr-landing-companion-outcome.v1`, `ModelPrLandingCompanionOutcome` | T5 |
| `node_projection_pr_landing`, tables `pr_landing_state` and `pr_landing_transitions` | T11 (wave 2) |

A wave 1 task changes a name it owns only by a contract version bump and a message to every other wave 1 task.

### 5.4 Identities and quota

- Companion writes keep the credential the live producer uses today, through `resolve_occ_github_token`. That App's installation bucket drained once, on 2026-09-21, so every effect call reports its rate-limit headers.
- Product-side calls (re-run, update-branch, arm, enqueue, disarm, check reads) use the contract-declared `GITHUB_TOKEN` the existing arm and re-run effects use. There is no new credential, no rotation, and never a ruleset bypass actor.
- Quota comes only from response headers, never from the `rate_limit` endpoint, which misreports the shared bucket. Each effect result carries a `ModelGithubQuotaReading`. A remaining count under the effect's declared floor makes the effect refuse with a typed reason rather than retry silently. Publishing to the shared `onex.evt.github.api-quota.v1` topic waits for the event-driven PR state track to freeze its model.
- Check reads: until the webhook families exist, the orchestrator reads a PR's head checks only while that PR is in CHECKS_PENDING, on its poll interval, with conditional requests (a 304 costs no quota). This replaces every drain lane's independent polling of the same PRs.

### 5.5 Where it runs

The lab runtime's dev lane, effects profile, beside the live autobind producer, lab first. The new contracts declare `runtime_lanes` scoped to the dev lane. Wave 3 runs in shadow mode (the arm gate in report_only and every effect in `dry_run`). Wave 4 enforces on omnimarket first, then across the repos.

## 6. Tasks

Sizes are lane-hours and are estimates. Each task is one PR, RED-first, with focused tests locally and wider runs pushed to CI or the lab. Build lanes hand each PR to the landing lane and never merge, arm, re-run or watch CI themselves.

### Wave 1: seams (contracts, fixtures, conformance tests). Five lanes in parallel.

**T1 (1.5 h) TLA+ model of the landing FSM.** The model lives in the building lane's scratch space until a shared formal-methods harness exists, with its TLC output attached to the task. It models section 5.1 with two concurrent ingress sources, duplicate and reordered delivery, `state_io` optimistic conflict with retry, the companion lease and the bound timer.
- AC1: TLC finds no violation of P1 to P5 over two PRs on one ticket with three observations each, with duplicates and reordering allowed -- falsifier: the attached TLC output reports a counterexample or fewer than five invariants checked
- AC2: removing the head-match drop rule produces a P1 counterexample -- falsifier: the mutated model's attached TLC output finds no violation
- AC3: a design-review verdict (PASS, or a list of changes to section 5.1) is recorded before T6 and T7 start -- falsifier: no verdict is recorded on the task

**T2 (3 h) Orchestrator and reducer contracts, models and the transition table.** omnimarket. Files: `src/omnimarket/nodes/node_pr_landing_orchestrator/{contract.yaml,metadata.yaml,models/}`, `src/omnimarket/nodes/node_pr_landing_reducer/{contract.yaml,metadata.yaml,models/}`, `src/omnimarket/events/topics.py`, `tests/fixtures/pr_landing/fsm_transitions.yaml`, `tests/fixtures/pr_landing/ingress/*.json`, `tests/unit/nodes/node_pr_landing_reducer/test_contract_conformance.py`.
- AC1: the transition table fixture holds every row of section 5.1, and a test fails when the contract's `state_machine` block and the fixture differ by any state or transition -- falsifier: uv run pytest on the conformance test after deleting one transition from the contract
- AC2: recorded payloads of the live autobind command and of `onex.evt.github.pr-merged.v1` parse into `ModelPrLandingObservation` with repository, PR number, head sha and kind, and an unknown kind is refused -- falsifier: uv run pytest over the ingress fixtures with one payload's kind altered
- AC3: runtime discovery over the omnimarket tree at this head wires no subscription for the two new nodes -- falsifier: a discovery test using omnibase_infra `runtime/auto_wiring/discovery.py` asserts zero routes for them
- AC4: every new topic is in `events/topics.py` and declared by exactly one publishing contract -- falsifier: the existing topic-registry and contract-topic tests, run with uv run pytest

**T3 (2.5 h) Per-check classification seam.** omnimarket. Adds operation `classify_head_checks` to `node_pr_lifecycle_triage_compute` (contract, `models/model_head_check_facts.py`, `models/model_head_check_verdict.py`), reusing `merge_control/reason_code_classifier.py` for per-check reason codes and adding the PR-level verdict: green, pending, change_control_open, change_control_stale, timed_out, runner_infra, cancelled, stale_caller_pin, behind_required, product_failed. Fixture corpus `tests/fixtures/pr_landing/checks/2026-09-26/*.json`: at least 40 real heads from the day, each with its check-runs, failed-step facts, companion state and a hand-assigned expected verdict.
- AC1: the corpus covers every verdict with at least three heads, and each fixture cites its repository, PR and head sha -- falsifier: uv run pytest on a corpus-coverage test
- AC2: the operation's contract and models validate every corpus input and expected output; the handler raises NotImplementedError until T8 -- falsifier: uv run pytest on the model round-trip test
- AC3: the verdict model refuses a product_failed verdict that also names a re-runnable check -- falsifier: uv run pytest on the model validator test

**T4 (3 h) GitHub landing effect seam.** omnimarket. Files: `src/omnimarket/nodes/node_pr_landing_github_effect/{contract.yaml,metadata.yaml,models/}`, `tests/fixtures/pr_landing/github/*.json`, `tests/unit/nodes/node_pr_landing_github_effect/fake_transport.py`. Operations: rerun_runs, update_branch, arm_auto_merge, enqueue, disarm and read_head_checks (conditional). Modes: dry_run (records the request and calls nothing) and enforce. Every result carries `ModelGithubQuotaReading` (limit, remaining, used, reset, resource, identity) parsed from response headers.
- AC1: the fake transport replays recorded responses for each operation, including a 304 on read_head_checks, a 403 secondary rate limit, a 422 update-branch conflict and an arm on a repo with auto-merge disabled -- falsifier: uv run pytest over the fake transport fixtures
- AC2: the quota model is built from headers only, and a test fails if any code path under the node reads the rate_limit endpoint -- falsifier: uv run pytest on a source-scan test for the rate_limit path
- AC3: the contract declares the existing `GITHUB_TOKEN` secret ref and no new credential -- falsifier: uv run pytest on a contract test comparing its secrets block with node_ci_rerun_effect's

**T5 (3 h) Companion seam.** omnimarket. Adds an `op` field (derive, regenerate, verify) to the live autobind command model; defines `ModelPrLandingCompanionOutcome` (MINTED, DECLINED or ERROR, with occ_pr, stamped, armed, conflicting and decline reason) and its outcome topic; and adds a parity harness. `tests/fixtures/pr_landing/companion_parity/` holds recorded inputs and the committed companion files of at least five companions merged on 2026-09-26, and a test renders each through `node_occ_companion_compute` and diffs the deterministic subset against the files the live emitter wrote.
- AC1: a command without `op` is read as derive, so the live publishers keep working unchanged -- falsifier: uv run pytest on the command model with a recorded publisher payload
- AC2: the outcome model maps every existing `occ_autobind_outcome` marker line to exactly one outcome -- falsifier: uv run pytest over recorded marker lines from 2026-09-26
- AC3: the parity test reports per companion either byte-equal or the list of differing files, and runs in CI as a non-required test -- falsifier: uv run pytest on the parity test with one fixture file altered

### Wave 2: builds against the frozen seams. Seven lanes in parallel once wave 1 merges.

- **T6 (3 h) Reducer handler.** `handle(ModelPrLandingReduceInput) -> ModelPrLandingReduceOutput`, pure, with no clock read (time comes from the observation). It passes the T2 transition table and property tests for P1 to P4 generated from the T1 model's invariants. Model citation: T1.
- **T7 (5 h) Orchestrator handler.** The delegation pattern: `state_io` table `pr_landing_workflow_state`, `completion_bound` per state, typed command dispatch, the transitioned and terminal events, and every arm or enqueue intent passed through `node_pr_arm_gate_compute` first. A seam test over InMemoryTransport in the shape of `test_s8_delegation_fsm_seam.py`, and a chain test in `tests/chains/pr_landing/`. Model citation: T1 (state_io optimistic conflict and the outbox).
- **T8 (2 h) Classifier handler.** Passes the T3 corpus exactly.
- **T9 (4 h) GitHub landing effect handlers.** Moves the REST and GraphQL calls out of `node_ci_rerun_effect`, `node_merge_sweep_auto_merge_arm_effect` and `handler_auto_rebase` into one transport module that both the old nodes and the new effect import. Reads the repo's live merge policy (auto-merge allowed, merge queue) before arm or enqueue.
- **T10 (3 h) The producer emits the typed companion outcome and honours regenerate.** In `node_pr_lifecycle_fix_effect`: publish `ModelPrLandingCompanionOutcome`; `op=regenerate` runs the conflict re-mint, or the batch rebuild when `OMNI_OCC_COMPANION_BATCH_MODE` is on, without needing a product push. Model citation: T1 (the per-ticket lease).
- **T11 (3 h) Projection pair.** `node_projection_pr_landing`: a pure fold and a `BaseProjectionRunner` writer with `onex_runtime_inprocess_dispatch = True`; tables `pr_landing_state` (key repository and pr_number; ordering authority the orchestrator's per-key `seq`; a stale write refused in the upsert WHERE) and `pr_landing_transitions` (append-only, key repository, pr_number and seq). Tests pin both known traps of the projection split.
- **T12 (2.5 h) Merge detection from the lab git mirror.** On the runtime tick, `node_git_query_mirror_effect` syncs onex_change_control and the product repos and publishes `onex.evt.github.pr-merged.v1` with `source=mirror` for each newly merged PR, deduplicated on (repository, pr_number) against the Actions producers. Depends on the mirror effect being on the lab.

### Wave 3: compose on the lab (ticketed at the wave 2 exit)

- **T13 (4 h) Deterministic replay of 2026-09-26.** Capture the day's real timelines (pushes, ready flips, companion opens, conflicts and merges, check-run completions) for the 221 product PRs and 141 companions into a scrubbed fixture. Publish them onto the dev-lane bus into the composed workflow with every effect in dry_run and the fake transport answering from the recording. Exit: two runs produce byte-identical transition logs; the decided actions and a simulated push-to-merge per PR; and every PR that drains touched for companion work shows the workflow's automatic action at the same point. A lab-pass receipt for the composed sha.
- **T14 (2 h) Shadow mode for 24 hours.** Live ingress, the arm gate in report_only and effects in dry_run on the dev lane. Compare each decided action with what the drain lanes did, and list every disagreement.
- **T15 (3 h) Landing chain canary.** `pr-landing-chain-canary.yml`, on a self-hosted runner that reaches the dev lane, in the shape of `chain-canary.yml`: a synthetic observation for a standing canary PR, a correlation-scoped readback of the transitioned event and the projection row, per-link verdicts, and the exit code as the verdict.
- **T16 (2 h) The landing skills consume the workflow.** The internal merge-drain, PR-landing and CI-watch skills read `pr-landing-agent-needed` and `pr_landing_state`, and drop their companion, stamp, re-run and arm steps for repos under enforce.

### Wave 4: cutover and measure (ticketed after wave 3)

- **T17** Enforce on omnimarket for 24 hours and measure section 4 for omnimarket alone. omnimarket is the batch-companion pilot repo and not the merge-queue trial repo (omnibase_infra), so the two results are not confounded.
- **T18** Enforce across the repos that carry the autobind publisher.
- **T19.1 to T19.4** Retire the scheduled companion-merge heal in each of the four repos that run it, and `occ-autobind-mint-verify.yml`; one PR per repo.
- **T20** Re-measure section 4 over 24 hours. Success is every target met.

Dependency order: T1 to T5 in parallel. T6 needs T1, T2 and T3. T7 needs T1, T2, T4 and T5. T8 needs T3. T9 needs T4. T10 needs T5. T11 needs T2. T12 needs the mirror effect. T13 needs T6 to T11. T14 and T15 need T13. T16 needs T14. T17 needs T14 to T16. Wave 1 is about 13 lane-hours, wave 2 about 22.5, and waves 3 and 4 about 18: about 54 in all.

## 7. Moving the derivation into a compute handler

The live companion is derived inside an effect: `OccCompanionEmitter` gathers PR and change-control facts with `gh` and `git` subprocesses and renders bytes through the pure seam `occ_evidence_stamp`. The compute node that already wraps that seam, `node_occ_companion_compute`, is not the live producer. This plan calls no script. It moves the derivation in two steps:

1. Wave 1 (T5) proves, per real companion from 2026-09-26, whether the compute node renders the same bytes the live emitter committed. The harness names every difference.
2. The switch from the emitter to the read, compute and write path (`node_occ_state_effect`, `node_occ_companion_compute`, `node_occ_companion_effect`) happens in one change that also stops the emitter's dispatch, so two producers never write one contract. It starts when the parity harness reports byte-equal on every fixture. The orchestrator does not change, because it talks to the companion seam, not to a producer.

## 8. Doctrine gates

| Gate | Met by |
|--|--|
| Rendered task content, no placeholders | every wave 1 task names files, tests and falsifiers; waves 3 and 4 are ticketed after the wave 2 exit |
| Replay determinism | T6 (a pure reducer with no clock); T13 (two replays byte-identical) |
| One ordering authority per projection | T11: the orchestrator's per-key `seq` |
| Deterministic keys plus UPSERT | T11 (repository, pr_number) and (repository, pr_number, seq); T12 dedupe on (repository, pr_number) |
| Measured against estimated cost | section 3 is measured; section 4 is targets; task sizes are estimates |
| One concept per topic | section 5: transitions, agent-needed, each terminal, the companion outcome and the GitHub effect results are separate topics |
| Pure envelopes | T2 and T5 typed models; no embedded-topic carrier |
| FAIL, not WARN | P1 to P5; a spent budget or a quota floor becomes agent-needed or a typed refusal, never a silent skip |
| Consumer health | T15 canary; T14 reads the consumer group Stable |
| Track isolation | `runtime_lanes` scoped to the dev lane (T2 AC3 and wave 3); shadow mode before enforce |
| Durable-queue contracts | T7 `state_io` in-row outbox |
| Column ownership for multi-path writes | T11: the writer is the only writer of both tables |
| Projection split (pure fold, runner writer) | T11 |
| Model before build | T1 before T6, T7 and T10 (a lease, several writers, a terminal) |
| No gate weakened | P5; no task edits a gate, ruleset or required check |

## 9. Adversarial pass

- **Counts.** Wave 1 has 5 tasks (T1 to T5), wave 2 has 7 (T6 to T12), wave 3 has 4 (T13 to T16) and wave 4 has 7 (T17, T18, T19.1 to T19.4, T20): 23 in all, 12 ticketed now.
- **Scope.** T16 is a skill change and does not enforce runtime behaviour; the canary (T15) and the replay (T13) are what prove the runtime.
- **Integration traps.** A new omnimarket contract is discovered by the runtime on the next deploy, so T2 AC3 proves the wave 1 contracts wire nothing. The live autobind command gains a field, so T5 AC1 keeps old payloads valid. onex_change_control has no merge publisher, so T12 covers companion merges without adding one.
- **Idempotency.** Transitions dedupe on (repository, pr_number, seq); companion commands keep the producer's open-or-sync idempotency; re-runs are keyed (head, check); agent-needed on (head, reason).
- **Proof strength.** Strong: the T1 model, the T13 byte-identical replay and the T15 canary exit code. Medium: the T14 shadow comparison against the drain lanes' recorded outcomes, which are claims rather than state. Weak, and never used alone: keyword counts of drain notes; T20 pairs them with `gh search prs --merged`.
- **Expansion.** The workflow arms product PRs, a step the landing lane does today; that is the first open decision below. The drain skills change in T16 and nowhere else.
- **Prerequisites.** T12 fails loudly if the mirror effect is not on the lab; T17 refuses to start without a reviewed T14 disagreement list; enforce refuses without the T15 canary green.

## 10. Risks

1. **The companion writer's App bucket.** Moving companion work from drains to the workflow adds no calls, but the calls come in tighter bursts. Every call reports headers, and the effect refuses under its floor.
2. **Two landers.** Until T16 lands, a drain lane and the workflow could both arm or re-run the same PR. Shadow mode (T14) and the skill change (T16) come before enforce.
3. **Declined companions.** The producer sometimes declines a diff it could prove. Those PRs become agent-needed with the decline reason, and the decline rate is a T14 output.
4. **Repos without a companion gate** can still merge a product PR before its companion. This plan does not change that.

## 11. Open decisions

1. Should the workflow arm (or enqueue) product PRs when green, taking that step from the landing lane? Recommended: yes. Auto-merge is already armed automatically for most product PRs on the dev-default repos, so this mostly covers the merge-queue repo, re-arms after a disarm, and repos without that automation.
2. When the producer declines to derive a companion (no provable red), should the PR go to an agent to fix the evidence, given that hand-authored companions stop once this path lands? Recommended: yes, as agent-needed with the decline reason, while the non-deterministic declines are fixed separately.
