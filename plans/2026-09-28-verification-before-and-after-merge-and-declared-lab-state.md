---
type: plan
status: active
date: "2026-09-28"
title: "Verification before and after merge, and declared lab state, as ONEX nodes, events and projections"
topics: [ci, merge-queue, verification, projection, reconcile, drift, broker-acl, determinism]
---

# Verification before and after merge, and declared lab state, as ONEX nodes, events and projections

state_as_of: 2026-09-28T14:48:00Z

**Goal.** A pull request from any author merges only after every milestone board check that can run
without lab hardware has passed on its merge-group commit, and every check that needs lab hardware has
passed on its head through a receipt. A red `dev` head is detected, traced to the merge that caused it,
and reverted by nodes whose state is a projection. Every piece of lab state that a runtime needs (broker
grants, host settings, lane services, deployed bundles) is declared in a typed document, applied at
bring-up by a reconcile node, and compared with the live state by a drift projection that fails loudly.

**Decisions this plan follows (operator, 2026-09-28, paraphrased).**

1. Every milestone board check that can run before merge runs on the merge-group commit and gates it as a
   required check, for every PR author and for everything, not only the current milestone. A post-merge
   `dev` head watcher traces a red to its merge and opens a revert. All lab state is declared in code and
   applied at bring-up. A check that cannot decide fails closed.
2. The design is expressed only in ONEX primitives (contracts, nodes, handlers with typed models, bus
   events, projections, and the dashboard rendering projections), and the operator sees the plan before
   any of it is built.

**Status.** Plan only. No code, workflow, ruleset or lab host was changed to write it. The build lanes
that had started on the first decision were stopped by the second. Tasks are ticketed in the internal
tracker only after the operator reviews this plan. Host-specific inventory, the lab's own overlay values
and the ticket mapping are kept in an internal companion document, because this repository is public.

---

## 1. What went wrong on 2026-09-28, and why nothing caught it

| # | Regression | Class | Why CI and the merge queue missed it (observed) |
| - | - | - | - |
| a | omnibase_infra#4227 made the gateway forwarder subscribe to one more inbound topic. On the lab broker, which enforces per-topic grants, the principal had no grant for it. `cloud_transport.start()` raised a topic-authorization error with no guard and the process exited, then restarted in a loop. Fix: omnibase_infra#4254, open. | behaviour under an enforcing broker | The unit test swaps in a fake transport. CI test shards exclude the `kafka` marker. Every CI broker is either plaintext with no auth, or SASL with its one user made a superuser (`tests/integration/customer_path/redpanda_sasl_harness.py:613`), so topic grants are never checked. No job starts the forwarder. The board check that did catch it is scheduled four times a day and caught it about two hours after the break. |
| b | omnibase_infra#4111 changed a routing table that three tests under `tests/ci/` assert on. `dev` went red on six cases. Fix: omnibase_infra#4255, open. | merge outside the queue | PR CI ran smart selection, which maps that config file to no tests, so the three tests never ran. **The merge queue did catch it**: the full suite failed on the merge group six times, and the queue removed the PR six times. A landing lane then merged it with a direct REST merge call, outside the queue. `dev` push CI diffs only `HEAD~1` and is smart-selected, so it passed. Every later merge group then failed on the same six cases. |
| b' | The same bypass happened again at 14:27Z: omnibase_infra#4197 was removed from the queue for failed checks and then merged by a direct REST call. | merge outside the queue | The landing brief of the drain says "merges by REST squash on the exact head" in its general rules and "enqueue, never a REST merge" in its omnibase_infra rule. Lanes followed the general rule. GitHub accepted the REST merge on a branch whose ruleset requires the queue. |
| c | The lab delegation client was refused by the lab broker. The grants it depends on exist only in broker state, typed by hand, and a rebuild of the broker volume loses them all. | undeclared state | Nothing declares broker grants for lab principals, and nothing compares live grants with a declaration. |
| d | Two lab lanes were down after a reboot because a bundle prune had deleted deployed bundle directories that their containers still mounted. Fix: omnibase_infra#4252, open. | undeclared state, unchecked invariant | The prune reads only its own lane's registry and never checks live mounts. |
| e | The lab alarm read the lab-pass receipt as INDETERMINATE for ten hours and raised nothing. Fix: omnibase_infra#4247, open. | undecidable fails open | An undecidable verdict was treated as "no news". |

The pattern: (a) and (c) are the same missing fact (which grants a principal needs is known from
contracts, but never derived or applied), (b) is a landing path that can leave the queue, and (d) and
(e) are state and verdicts that nobody declares or bounds.

## 2. Existing assets

Read from the `dev` branch of each named repository on 2026-09-28 between 14:30Z and 14:48Z, unless
another source is given.

| Asset | Repo | State | Reuse or replace |
| - | - | - | - |
| Merge queue on omnibase_infra `dev` (ALLGREEN, squash, up to 5 entries built); the `merge_group` event forces the full suite (`scripts/ci/detect_test_paths.py:673`) | omnibase_infra | live | **reuse**: the merge-group commit is where the new required checks run |
| `CI Summary`, the single required context: a no-`needs`, default-deny, fail-closed poller over every job of the run; the only non-gating jobs are the `SOFT_ALLOWLIST` in `scripts/ci/ci_summary_gate.py:424` | omnibase_infra | live | **reuse**: a new job in `ci.yml` that is not soft-allowlisted gates the merge with no branch-protection write |
| `FULL_SUITE_BRANCHES = {"main"}` (`detect_test_paths.py:287`); push CI computes changes from `HEAD~1` (`ci.yml`, detect-changes job) | omnibase_infra | live | **extend**: a `dev` push whose commit was not validated by the queue gets the full suite (task S2) |
| `node_pr_landing_github_effect`: the landing workflow's single GitHub effect. Its verbs are rerun, update branch, arm, enqueue, disarm and reads. It has no direct-merge verb. | omnimarket | live | **reuse as the only merge path**; it gains one verb, open-revert (task B5, a labelled expansion) |
| The drain's landing brief, a temporary process skill in the private process-skill repository | private | live; carries the REST-merge instruction behind (b) and (b') | **fix now** (task S1); its node replacement is `node_pr_landing_github_effect` |
| `node_github_webhook_ingress_effect`, `webhook_fold.py`: folds `pull_request`, `pull_request_review` and `check_run` deliveries into `pr_state` and `pr-merged` events. A `check_run` with no pull requests (a push to `dev`) is dropped (`webhook_fold.py:248-251`). | omnibase_infra | landed 2026-09-28 (the change behind regression a) | **extend**: base-branch check runs become branch-head observations (task B1) |
| `node_focused_test_run_effect` (one pytest node id at one commit in a throwaway container on a lab host, returns a receipt), `node_pytest_failure_digest_compute` | omnimarket | live | **reuse** as the bisect probe (task B4) |
| Lab proof for every PR: proof-profile registry, `pr-head` lab receipt with an offline verifier (omnibase_infra#4133 and #4161 merged), receipt event and projection, `lab-proof` required context that works on `merge_group` | omnibase_infra, omnimarket | registry and receipt subject merged; event, projection, check run, scheduler and gate not built | **reuse as workstream A's lab half**; this plan adds board checks to the profiles' mandatory checks and changes nothing in that design |
| `node_chain_canary_effect` (the chain canary, per-link verdicts from broker readback) | omnibase_infra | live, scheduled | **reuse**; its verdict joins the probe-result event (task A3) |
| Board-check probe scripts `scripts/ci/c11_negative_paths_probe.py`, `c12_provider_catalogue_probe.py`, `c16_receipt_identity_probe.py`, `c28_consumer_flow_probe.py`, and their scheduled workflows | omnibase_infra | live, schedule or dispatch only; none runs on `pull_request` or `merge_group` | **replace**: each becomes a handler of one probe effect node; the workflows become thin shims (task A2) |
| The milestone board publisher and its criteria and probe table | private deployment repository | live, hourly | **reuse**; it reads the probe-result projection instead of workflow runs (task A3) |
| `node_setup_local_provision_effect` (compose up, down and status from a `ModelDeploymentTopology`), `node_setup_validate_effect` | omnibase_infra | live | **reuse** to bring up the CI ephemeral stack (task A4) |
| The config-overlay spine: `EnumConfigOverlayKey`, `ModelConfigOverlayDocument`, store path `onex/config/<environment>/<lane>/<key>`, JSON Schema export, a validated seed path; first keys `runtime.lane` and `runtime.bus_lane` | omnibase_core, omnibase_infra | live | **reuse**: each declared-state class is one more overlay key (task C1) |
| The lab's overlay documents and their CI validation | private deployment repository | live for `runtime.lane` | **reuse** as the home of the lab's declared state (task C6) |
| `node_projection_lab_lane_health` (one row per lab lane from census, census drift, lab-pass receipts and runtime health), exposed through the generic projection route | omnimarket | live | **extend**: it folds the drift count (task C5) |
| `node_environment_health_scanner`, `node_env_parity_collect_effect`, `node_volume_config_drift_sweep` | omnimarket | live | **reuse as prior art**; each observes one kind of live state against contracts, and the observe handlers follow their shape |
| `TopicProvisioner`, `ModelTopicSpec`, `compute_consumer_group_id` | omnibase_infra | live | **reuse**: the grant derivation reads the same topic and group identities (task C2) |
| A tenant ACL manager that writes broker ACLs through the Redpanda admin API | private deployment repository (an API service) | live for tenant ACLs | **prior art only**: the lab's grants are not tenant grants, and an API service is not a node |
| Cloud broker grants: a topic list, an IAM policy and a parity gate | private deployment repository | live | **left as is**: the cloud broker uses IAM, not broker ACLs; the parity gate is the cloud counterpart of task C5 |
| `node_slack_alerter_effect` | omnibase_infra | live | **reuse** for loud failure (tasks B6, C5) |
| The lab alarm (a scheduled script) | omnibase_infra `scripts/lab_alarm.py` | live; failed open for ten hours (e) | **replace** by the branch-head health projection plus the alerter (task B7) |
| TLA+ harness | none | the formal-verification plan proposes one; not built | models live in the building lane's scratch space until it lands |

## 3. Design

### 3.1 The primitives, in one table

Every new capability below is a contract, a node of one of the four archetypes, handlers with typed
models, bus events and projections. Nothing new is a daemon, a script, a scheduled job or a `Plugin*`
class. A CI step or a skill that only invokes a node (`onex run-node <node>`) is a thin shim, and each
temporary process skill named here says which node replaces it.

| Kind | Name | Repo | Purpose |
| - | - | - | - |
| event | `onex.evt.github.branch-head-status.v1` | omnibase_infra | one base-branch check-run verdict: repo, branch, sha, check name, verdict, trigger (`push` or `merge_group`), run id, `as_of`, delivery id |
| event | `onex.evt.omnibase-infra.merge-provenance-evaluated.v1` | omnibase_infra | whether a `dev` commit was validated by a successful merge group: `VALIDATED`, `UNVALIDATED` or `UNDECIDABLE`, with the run ids read |
| event | `onex.evt.omnibase-infra.board-probe-result.v1` | omnibase_infra | one board check's outcome on one subject: check id, subject (repo, sha, kind `merge_group`, `pr_head`, `branch_head` or `scheduled`), surface (`ci_ephemeral`, `lab`, `cloud`), `PASS`, `FAIL` or `INDETERMINATE`, reasons |
| event | `onex.evt.omnimarket.devhead-red-detected.v1`, `...devhead-culprit-identified.v1`, `...devhead-revert-opened.v1` | omnimarket | the guard's three terminals, keyed by repo, branch and first red sha |
| event | `onex.evt.omnibase-infra.declared-state-observed.v1`, `...declared-state-applied.v1` | omnibase_infra | one declared item's desired and observed digests and status (`IN_SYNC`, `DRIFTED`, `MISSING`, `UNOBSERVABLE`); one apply result |
| command | `onex.cmd.omnibase-infra.board-probe-run.v1`, `onex.cmd.omnimarket.devhead-bisect.v1`, `onex.cmd.omnibase-infra.declared-state-reconcile.v1` | as above | durable command topics that start each node; the reconcile command carries scope, mode (`observe` or `apply`) and trigger (`bring_up`, `schedule`, `boot`, `manual`) |
| compute | `node_merge_provenance_compute` | omnibase_infra | pure: a commit and the merge-group runs read for it, to a provenance verdict |
| compute | `node_board_check_plan_compute` | omnibase_infra | pure: the probe contract's declared checks and a subject, to the checks that must pass on that subject and on which surface |
| compute | `node_board_check_verdict_compute` | omnibase_infra | pure: the plan and the probe results, to one verdict; a missing or `INDETERMINATE` result is a failure |
| effect | `node_board_probe_effect` | omnibase_infra | one handler per board check; the target is an injected adapter bound per surface (the CI ephemeral stack, or a lab lane through its overlay) |
| reducer | `node_devhead_guard_reducer` | omnimarket | pure FSM per (repo, branch): `GREEN` to `RED_DETECTED` to `BISECTING` to `CULPRIT_CONFIRMED` to `REVERT_OPEN` to `GREEN`, with `ESCALATED` on an ambiguous or unreproduced bisect or an expired bound |
| orchestrator | `node_devhead_guard_orchestrator` | omnimarket | consumes branch-head, provenance, probe and lab-pass events; issues focused test runs for the bisect and the revert through the GitHub effect |
| compute | `node_broker_grant_derive_compute` | omnibase_infra | pure: the contracts a principal runs, to the exact topic and group grants it needs |
| effect | `node_declared_state_observe_effect` | omnibase_infra | one handler per surface kind, reading live state through injected adapters: broker ACLs, compose services, host settings, deployed bundles |
| compute | `node_declared_state_diff_compute` | omnibase_infra | pure: desired against observed, to drift items and an idempotent apply plan |
| effect | `node_declared_state_apply_effect` | omnibase_infra | applies plan items for the surface kinds its overlay policy allows, refuses the rest by name |
| orchestrator | `node_declared_state_reconcile_orchestrator` | omnibase_infra | observe, diff, apply when in `apply` mode, observe again, publish |
| projection | `node_projection_branch_head_health` | omnimarket | one row per (repo, branch) and a history row per (repo, branch, sha): head sha, verdict, provenance, lab-pass state, open red, culprit, revert PR |
| projection | `node_projection_board_probe_results` | omnimarket | one row per (check id, subject kind, repo, sha, surface) |
| projection | `node_projection_declared_state_drift` | omnimarket | one row per (surface kind, surface id, item key), latest status and since when |
| core types | overlay keys `broker.principal_grants`, `host.settings`, `lane.services` and their typed documents; protocols for the four observe adapters | omnibase_core, omnibase_spi | the declaration a deployment supplies; shipped code names no lane, host or principal |

Each projection is two classes (a pure fold and an effect-class writer on the projection runner base),
declares `projection_api.expose`, and is read by the dashboard through the generic projection route. The
queue-status skill and the drain read the same route; neither reads GitHub for these facts.

### 3.2 Workstream A: pre-merge verification for every PR author

1. **Where checks run.** Each board check handler in `node_board_probe_effect` declares, in the node's
   contract, a stable check id named for what it checks (`consumer_flow`, `negative_paths`,
   `provider_catalogue`, `receipt_identity`, `forwarder_refused_topic`, `declared_state`) and a surface
   class: `ci_ephemeral` (runs against a stack CI can start), `lab_hardware` (needs a local model server
   or other lab hardware), `cloud`, or `post_release` (tests published packages). The milestone mapping
   (which check proves which board criterion) stays in the private board.
2. **The CI half.** On `pull_request` and on `merge_group`, one job in the repository's `ci.yml` brings
   up an ephemeral stack with `node_setup_local_provision_effect` (broker with per-topic authorization on
   and a non-superuser runtime principal, Postgres, the runtime, the gateway forwarder), runs the declared
   state reconcile in `apply` mode so the stack gets exactly the derived grants, asks
   `node_board_check_plan_compute` for the `ci_ephemeral` checks, runs them through
   `node_board_probe_effect`, and grades with `node_board_check_verdict_compute`. Every result is
   published as a probe-result event. The job is not soft-allowlisted, so `CI Summary`, the required
   context, fails when it fails. Checks that grade a model's answer run with a stub responder in CI and
   grade only routing and terminal shape; the real-model leg is a `lab_hardware` check.
3. **The lab half.** `lab_hardware` checks join the `mandatory_checks` of the lab proof profiles of the
   repositories they cover. Nothing else changes: the prover runs the profile on the PR head, the
   verifier mints the `pr-head` receipt, the receipt projection feeds the `lab-proof` required context,
   and that context already reads the queue ref on `merge_group`.
4. **Undecidable fails closed.** A check that is planned and has no result, or has `INDETERMINATE`, is a
   failure in the verdict compute and in the `lab-proof` verifier. There is no neutral or skipped
   conclusion for a planned check.
5. **`cloud` and `post_release` checks** stay scheduled after merge. Their results feed the branch-head
   guard (3.3), so a red one is traced and reverted like a red test.

### 3.3 Workstream B: the `dev` head guard

1. **The queue cannot be left.** The only merge verb in the landing path is enqueue
   (`node_pr_landing_github_effect`); the temporary brief is fixed to match (S1); and the operator
   decides whether GitHub itself refuses a merge outside the queue (decision D1).
2. **Provenance.** On every `dev` push, CI asks `node_merge_provenance_compute` whether this exact commit
   is a merge-group commit with a successful `CI Summary`. A queue landing makes the merge-group commit
   the new `dev` head, so the answer is a lookup, not an inference. `UNVALIDATED` or `UNDECIDABLE` forces
   the full suite on that push. That alone would have turned `dev` red within one push run after (b).
3. **Detection.** The webhook ingress folds base-branch check runs (push and merge group) into
   branch-head observations. The branch-head health projection folds those, the provenance events,
   post-merge probe results and lab-pass receipts. A lab-pass or probe verdict that stays `INDETERMINATE`
   past its declared bound is folded as red, which closes (e).
4. **Bisect.** The guard orchestrator takes the failing test ids from the red run, and for each merge
   between the last green and the first red head, in order, runs them with `node_focused_test_run_effect`
   at the merge and at its parent. A culprit is confirmed only when the failing ids fail at the merge and
   pass at its parent. For a failing board check it replays the probe on the same surface at both
   commits. Anything else is `ESCALATED` with the evidence, never guessed.
5. **Revert.** For a confirmed culprit the orchestrator opens a revert PR through the GitHub effect
   (idempotency key: repo, culprit sha), labelled and linked to the red, and it enters the queue like any
   PR. If a fix PR naming the same failing ids is already in the queue, the revert waits for one queue
   cycle, then proceeds. Whether a revert lands without a human is decision D2.
6. **Visible.** The dashboard shows the branch-head health rows; the queue-status skill and the drain map
   read the same projection, so a red `dev` is the first line of every queue report.

### 3.4 Workstream C: declared lab state

1. **Declaration.** Three overlay keys, each a typed document in core with a JSON Schema export, supplied
   by whoever runs the deployment:
   - `broker.principal_grants`: a principal, the contract set (or client profile) it runs, and any
     explicit extra grants with a reason. The grants themselves are **derived**, not listed:
     `node_broker_grant_derive_compute` reads the contracts' subscribe and publish topics and the group
     ids `compute_consumer_group_id` produces. A contract that adds a topic therefore adds its grant on
     the next reconcile, which is what (a) and (c) lacked.
   - `host.settings`: kernel parameters, systemd units and drop-ins by content digest, network-interface
     and power settings, per host.
   - `lane.services`: per lane, the services and their restart policies, and the one-shot jobs that must
     have completed since the service they prepare was last recreated.
   Deployed bundles need no declaration: each lane's registry already says what it deploys, and the
   invariant (a mounted bundle directory exists and is not empty) is checked by the observe handler.
2. **Where our values live.** Our lab's documents live in the private deployment repository beside its
   `runtime.lane` documents, validated there against the core schemas, and reach the runtimes only
   through the config store's seed path. No public repository holds any of them.
3. **Reconcile.** `node_declared_state_reconcile_orchestrator` runs at bring-up (every deploy path emits
   the reconcile command after a lane starts), at boot, and on a contract-declared schedule. In `apply`
   mode it changes only the surface kinds its overlay policy allows (decision D3) and applies each plan
   item idempotently, keyed by (surface kind, surface id, item key, desired digest).
4. **Loud failure.** Every observed item is an event; the drift projection keeps the latest per item. A
   `DRIFTED`, `MISSING` or `UNOBSERVABLE` item older than one reconcile interval fails the `declared_state`
   board check, fails a new `declared_state_in_sync` mandatory check on the post-merge lab-pass receipt
   (so staging delivery stops), and alerts through the alerter.
5. **Reboot drill (proposed, not run).** An operator reboots one lab host. The boot trigger runs the
   reconcile; the drill passes when, within a declared bound, every drift row for that host is `IN_SYNC`
   and every lane on it has a PASS lab-pass receipt. The grading is a check id (`reboot_recovery`) in the
   probe effect, computed from the two projections. Running it is decision D5.

### 3.5 What stays outside the primitives, and why

- CI workflow steps and the queue-status and drain skills are shims that call nodes or read projections.
  The drain's landing brief is a temporary process skill; its replacement is the landing workflow of the
  PR landing plan, whose GitHub effect is `node_pr_landing_github_effect`.
- The gateway forwarder's process entrypoint (`src/omnibase_infra/runtime/gateway_forwarder.py`) is
  existing non-canonical debt. Its refused-topic fix (omnibase_infra#4254) lands as is; the CI test in
  S3 pins the behaviour at the deployed entrypoint, so the test survives when the forwarder becomes the
  handler of `node_bus_forwarder_effect`.
- The lab alarm is retired, not rebuilt (B7).

## 4. The first slice: what would have caught (a) and (b) this week

Four tasks, smallest first. S1, S2 and S4 need nothing else from this plan; S3 needs omnibase_infra#4254
merged, because the test it adds is red on today's `dev`.

- **S1** stops the landing brief from telling lanes to merge outside the queue. Prevents (b) and (b').
- **S2** gives every `dev` push that did not come through the queue the full suite. Detects (b) on the
  first push after it.
- **S3** runs the forwarder against a broker that enforces grants, with one topic it may not read. Fails
  on the (a) merge, passes on the fix.
- **S4** is the operator's ruleset change (D1) and the audit that keeps it.

Every other task follows in section 6 order.

## 5. Tasks

Each task is one lane, one PR, one ticket. Each writes the failing test first, runs only focused tests
locally, and runs anything broad on a lab host or in CI. Each PR body cites its lab readback. Sizes are
lane-hours and are estimates unless marked measured.

### Slice

**S1. The drain's landing brief never merges outside a queue** (private process-skill repository: the
drain workflow's rules block and the land skill's merge step). Test first: for a repository whose base
branch carries a merge-queue rule, the rendered rules contain no REST merge call and name the enqueue
verb; for a repository without one, the squash merge on the exact head stays. Minimal change: one rule
text, chosen by the live queue read the drain already makes. Lab step: one drain refresh in dry-run
against the live queue read. Size 1.
- The rendered rules for omnibase_infra contain `--match-head-commit` and no `pulls/<n>/merge` --
  falsifier: render the rules block for omnibase_infra and grep for `pulls/` and `merge_method`.
- The skill's frontmatter names `node_pr_landing_github_effect` as its replacement -- falsifier: grep the
  frontmatter's `replaces_when` for the node name.

**S2. `node_merge_provenance_compute`, and the full suite for an unvalidated `dev` push** (omnibase_infra:
`src/omnibase_infra/nodes/node_merge_provenance_compute/{contract.yaml,node.py,handlers/handler_merge_provenance.py,models/model_merge_provenance_request.py,models/model_merge_provenance_result.py}`;
the detect-changes job in `.github/workflows/ci.yml`; `scripts/ci/detect_test_paths.py` accepts a
forced-full input with its own reason `UNVALIDATED_PUSH`, passed only for an `UNVALIDATED` or
`UNDECIDABLE` verdict). The handler is definition-B and pure: its
request carries the pushed sha and the merge-group check runs a shim step read for it. Test first: the
real pair from 2026-09-28, `dev` commit e263eee (no merge-group run, the queue's commit was bbc24237)
returns `UNVALIDATED`; a queue-landed commit returns `VALIDATED`; a request whose read failed returns
`UNDECIDABLE`. Focused test: `uv run pytest tests/unit/nodes/node_merge_provenance_compute -q`. Lab step:
the shim step run against the live `dev` head from a lab runner, output recorded. Size 5.
- The three verdicts above for the three inputs -- falsifier: the unit test table with those three rows.
- A `dev` push run whose provenance is `UNVALIDATED` or `UNDECIDABLE` selects the full 15-split suite with
  reason `UNVALIDATED_PUSH` -- falsifier: `selection.json` of the push run shows `split_count` 15 and that
  reason.
- A `VALIDATED` push keeps smart selection -- falsifier: `selection.json` of the next queue-landed push
  shows the reason is not `UNVALIDATED_PUSH`.
- The workflow step contains no provenance logic, only the node invocation -- falsifier: the step's `run:`
  is one `onex run-node node_merge_provenance_compute` call plus its output write.

**S3. The forwarder survives a refused topic, on a broker that enforces grants** (omnibase_infra:
`tests/integration/bus_acl_boundary/test_forwarder_refused_topic.py`; a non-superuser principal option
in `tests/integration/customer_path/redpanda_sasl_harness.py`; a `bus-acl-boundary` job in
`.github/workflows/ci.yml` on `pull_request` and `merge_group`, unconditional, not path-scoped). The
harness keeps one superuser for bootstrap only and creates a runtime principal with grants for every
topic the forwarder subscribes to except one canary inbound topic. The test starts the forwarder through
its deployed entrypoint and asserts: the process is alive after 30 s; the refused topic is reported by
name; one event produced on a granted inbound topic arrives on its outbound topic. Negative control: the
same test against the forwarder at c6c1c47c8 (the #4227 merge) fails. Depends on omnibase_infra#4254.
Lab step: the job's test run on a lab runner against the fix's head, and the negative control at
c6c1c47c8. Size 6.
- Passes at the #4254 head and fails at c6c1c47c8 -- falsifier: both runs' junit results, cited in the PR.
- The job name is absent from `SOFT_ALLOWLIST` and the job runs on `merge_group` -- falsifier: a unit test
  in `tests/ci/test_ci_summary_gate.py` asserting absence, and the job's check run present on the next
  merge-group commit.
- The runtime principal is not a superuser -- falsifier: the harness's `rpk acl user list` and superuser
  config read inside the test, asserted.

**S4. No merge leaves the queue** (operator: decision D1, a ruleset change on the queue-controlled
branches; then onex_change_control `scripts/audit_branch_protection.sh`). Test first: the audit fails on a
queue ruleset that lists any bypass actor. Lab step: the audit run against live settings after the
change. Size 1, plus the operator's change.
- A REST merge of a queue-controlled PR is refused -- falsifier: the next direct merge attempt by a
  landing identity returns the refusal (read from the drain's own STATUS, never provoked on purpose).
- The audit fails on a queue ruleset with a bypass actor -- falsifier: its test fixture with one.

### Workstream A

**A1. The probe effect's contract and its first handler, `consumer_flow`** (omnibase_infra:
`src/omnibase_infra/nodes/node_board_probe_effect/`, the handler body migrated from
`scripts/ci/c28_consumer_flow_probe.py`; the target adapter protocol in omnibase_spi, its I/O models in
omnibase_core). The contract declares each check handler with `check_id` and `surface_class`. The
scheduled workflow becomes a shim, and its leftover push trigger on a feature branch is removed. Test
first: the handler against a recorded flow returns `PASS`, against a stalled consumer group returns
`FAIL`, against an unreachable target returns `INDETERMINATE`. Lab step: the node run against the lab dev
lane through its overlay, the result compared with the script's on the same minute. Size 6.
- The three outcomes for the three recordings -- falsifier: the unit test table.
- Node and script agree on the lab dev lane -- falsifier: both outputs in the PR body, same verdict.
- The workflow's `run:` is only a node invocation -- falsifier: read the workflow file.

**A2. The remaining CI-class handlers: `negative_paths`, `provider_catalogue`, `receipt_identity`**
(same node; handler bodies from the matching scripts; `receipt_identity` against a stub responder). Test
first per handler as in A1. Lab step as in A1. Size 8.
- Each handler returns all three outcomes on its recordings -- falsifier: the unit test tables.

**A3. The probe-result event and projection** (omnibase_infra publishes; omnimarket
`src/omnimarket/nodes/node_projection_board_probe_results/` fold and writer, migration, `projection_api`
exposed; the chain canary's verdict published in the same shape). Ordering authority: the result's
`finished_at`, then the event offset. Key (check id, subject kind, repo, sha, surface), UPSERT on key.
Test first: two results for one key in either order fold to the later `finished_at`; a replay of the
topic reproduces the table byte for byte. Lab step: one probe run on the lab dev lane, the row read back
through the projection route, and the consumer group read. Size 5.
- Replay reproduces the table -- falsifier: the replay test compares row digests.
- Rows readable at `/projection/board_probe_results` -- falsifier: the route's response in the PR body.

**A4. The merge-group board-check job in omnibase_infra** (`.github/workflows/ci.yml` job
`board-checks-ephemeral`; a CI deployment topology document for `node_setup_local_provision_effect`;
`node_board_check_plan_compute` and `node_board_check_verdict_compute` under
`src/omnibase_infra/nodes/`). The stack's broker grants come from a fixture document until C4 lands, then
from the reconcile node. Test first: the verdict compute returns FAIL for a plan with one missing result
and for one `INDETERMINATE` result. Lab step: the job's steps run on a lab runner against the merge-group
commit of a real queued PR. Depends on A1, A2, A3, S3. Size 10.
- A planned check with no result fails the job -- falsifier: the verdict unit test, and one deliberate
  red run on a draft PR with a handler disabled.
- The job runs on every merge-group entry and is not soft-allowlisted -- falsifier: its check run on the
  next three merge-group commits, and the allowlist test.
- Wall time on the merge group is recorded -- falsifier: the job's duration on three runs, in the PR body
  (measured, not estimated).

**A5. The same job in every repository that has a merge group** (a reusable workflow in omnimarket, the
home for reusable gates; one caller per repository). omnimarket's merge-queue ruleset is disabled today,
so without decision D6 its job runs on `pull_request` only. Size 4 per repository.
- The caller exists and gates in each repository with a merge queue -- falsifier: the check run on a
  merge-group commit per repository.

**A6. Lab-hardware checks become mandatory checks of the lab proof profiles** (omnibase_infra
`config/lab_proof_profiles.yaml` rows for omnimarket and omnibase_infra; the checks
`customer_local_delegation` and `customer_local_routing`). Depends on the lab-proof plan's receipt event,
projection and check-run slices. Test first: the registry validator refuses a profile that lists a check
id the probe effect does not declare. Lab step: one prover run whose receipt carries both checks. Size 3.
- A receipt missing one of the two is refused -- falsifier: the verifier's test with that receipt.

**A7. `INDETERMINATE` fails closed in every verdict path** (the verdict compute and the `pr-head`
verifier). Test first: `INDETERMINATE` in either path yields a failure token, never a pass or a neutral.
Size 3.
- Both paths refuse `INDETERMINATE` -- falsifier: one unit test per path.

### Workstream B

**B1. Base-branch check runs become branch-head observations** (omnibase_infra
`nodes/node_github_webhook_ingress_effect/webhook_fold.py`, a new model
`models/model_github_branch_head_observation.py`, the contract's `published_events`). A `check_run` whose
name is a summary check and whose branch is a watched base, or a merge-group ref, is folded instead of
dropped. Test first: a recorded push-triggered `CI Summary` delivery with an empty pull-request list
yields one observation with the sha and verdict; a merge-group delivery yields one with trigger
`merge_group`. Lab step: a real delivery on the lab dev lane, the event read back from the broker. Size 4.
- The two recorded deliveries fold as stated -- falsifier: the fold unit test.
- A delivery for an unwatched branch still folds to nothing -- falsifier: same test, third row.

**B2. The branch-head health projection** (omnimarket
`src/omnimarket/nodes/node_projection_branch_head_health/`, fold and writer, migration, exposed). One
writer; columns owned by source: verdict and sha from branch-head events, provenance from provenance
events, lab-pass state from receipts, probe state from probe results, guard state from guard events. An
`INDETERMINATE` lab-pass or probe older than its declared bound folds as red. Test first: the (e) case, a
receipt INDETERMINATE for longer than the bound, reads red; replay reproduces the table. Lab step: the
projection on the lab dev lane after one `dev` push, read through the route, consumer group read. Size 6.
- The (e) replay folds red -- falsifier: the fold test with the recorded sequence.
- Each column is written by exactly one event type -- falsifier: a test that folds each event type alone
  and asserts which columns changed.

**B3. A TLA+ model of the guard** (in the building lane's scratch space until the harness lands; cited by
path in B4 and B5). Properties: at most one revert PR per culprit; a revert is never opened for a merge
that did not fail at itself and pass at its parent; a fix PR and a revert for the same red never both
land without a check in between; a bisect run's runner slot is always released; every red reaches
`GREEN` or `ESCALATED` within the bound. Design-review verdict recorded in the ticket. Blocks B4 and B5.
Size 5.

**B4. The guard reducer and orchestrator, detection and bisect** (omnimarket
`src/omnimarket/nodes/node_devhead_guard_reducer/`, `node_devhead_guard_orchestrator/`; reuses
`node_focused_test_run_effect` and `node_pytest_failure_digest_compute`). Test first: replayed events of
2026-09-28 (#4111's merge, then red push runs) drive the reducer to `CULPRIT_CONFIRMED` for #4111's
merge; a flaky failure that passes at the merge goes to `ESCALATED`. Lab step: one bisect on the lab over
two real commits, with the focused-run receipts cited. Size 12.
- The recorded day confirms #4111 as the culprit -- falsifier: the replay test's terminal event.
- An unreproduced failure never confirms -- falsifier: the flaky-row replay.
- Every bisect run's container is torn down -- falsifier: the focused-run receipts' teardown flags.

**B5. The revert verb and the revert step** (omnimarket: `node_pr_landing_github_effect` gains
`open_revert_pr`, a labelled expansion; its callers are unchanged because the verb is new; the
orchestrator issues it). Idempotency key (repo, culprit sha): a second request returns the existing PR.
Test first: two requests for one culprit open one PR. Lab step: a revert opened for a synthetic culprit
on a scratch branch of a test repository, never on a real base. Size 6.
- Two requests yield one PR -- falsifier: the effect's test against a recorded GitHub adapter.
- The revert PR enters the queue through enqueue, never a direct merge -- falsifier: the adapter's call
  log in the test has no merge call.

**B6. The dashboard widget and the queue report** (omnidash: a widget over
`/projection/branch_head_health`; the queue-status skill reads the same route; the alerter fires on a
row turning red). Test first: the widget renders a red row with its culprit and revert link from a
recorded response. Lab step: the widget against the lab projection route. Size 5.
- A red `dev` is the first line of queue-status -- falsifier: the skill run against a recorded red row.

**B7. The lab alarm's receipt grading moves to the projection** (omnibase_infra `scripts/lab_alarm.py`
stops grading lab-pass receipts; B2 and the alerter carry it). Size 3.
- The alarm script no longer reads receipts -- falsifier: grep the script for the receipt reader.

### Workstream C

**C1. The declarations** (omnibase_core: `EnumConfigOverlayKey` gains `BROKER_PRINCIPAL_GRANTS`,
`HOST_SETTINGS`, `LANE_SERVICES`; models under `src/omnibase_core/models/config_overlay/`; JSON Schema
exports; omnibase_spi: the four observe-adapter protocols). Frozen, `extra="forbid"`, no defaults, no lane
or host names. Test first: a document naming an unknown field or an empty principal is refused; the
schema export round-trips. Size 5.
- The core source names no lab principal, host or lane -- falsifier: `git grep -n -E 'compose-dev|stability-test|judge|prepr-'` over exactly the files the PR adds returns no hit, with the same grep over `constants_runtime_lanes.py` as the positive control.

**C2. `node_broker_grant_derive_compute`** (omnibase_infra). Pure: the contracts in a principal's
declared set to topic READ, WRITE and DESCRIBE grants and group grants, with group ids from
`compute_consumer_group_id`. Test first: the forwarder's contract set yields a grant for every topic its
contract subscribes to, including the topic #4227 added. Size 6.
- Grants cover every subscribed and published topic of the set -- falsifier: a test that walks the
  contracts independently and diffs.
- Adding a topic to a contract adds exactly its grant -- falsifier: a two-version fixture.

**C3. The observe effect** (omnibase_infra `node_declared_state_observe_effect`: handlers for broker ACLs
through the broker admin API, compose services, host settings, deployed bundles; adapters bound per
lane by overlay). Test first: each handler returns `IN_SYNC`, `DRIFTED`, `MISSING` and `UNOBSERVABLE` on
recordings; the bundle handler reports an empty mounted directory as `MISSING`. Lab step: observe mode on
the lab dev lane, every item's status in the PR body. Size 10.

**C0. A TLA+ model of reconcile** (the building lane's scratch space until the harness lands; cited by
path in C4). Properties: apply and a concurrent hand edit converge; two reconciles on one surface never
interleave applies; an apply never removes a grant a declared principal needs; an `UNOBSERVABLE` surface
is never applied to. Design-review verdict recorded in the ticket. Blocks C4. Size 5.

**C4. Diff, apply and the reconcile orchestrator** (omnibase_infra `node_declared_state_diff_compute`,
`node_declared_state_apply_effect`, `node_declared_state_reconcile_orchestrator`). Depends on C0, C2, C3.
Test first: a second apply of the same plan changes nothing; a surface kind not allowed by policy is
refused by name. Lab step: apply mode on the lab dev lane's broker grants, then observe shows no drift.
Size 12.
- Apply is idempotent -- falsifier: apply twice, the second apply event lists zero operations.
- A disallowed kind is refused by name -- falsifier: the policy test.

**C5. The drift projection and loud failure** (omnimarket `node_projection_declared_state_drift`, fold
and writer, exposed; `node_projection_lab_lane_health` folds the drift count, a labelled expansion; the
`declared_state` handler in the probe effect; a `declared_state_in_sync` mandatory check on the post-merge
lab-pass receipt). Test first: a drifted item older than one interval makes the check `FAIL`; an
`UNOBSERVABLE` item does the same. Lab step: one deliberate drift on the lab dev lane's scratch principal,
the red read back through the route, then reconcile clears it. Size 6.

**C6. Our lab's declarations** (private deployment repository, beside the `runtime.lane` documents; its
CI validates them against the C1 schemas; seeded through the store). Details in the internal companion.
Size 6.

**C7. The bring-up and boot triggers** (every deploy path emits the reconcile command after a lane
starts; the runtime declares the schedule and the boot trigger in the orchestrator's contract; the A4
job's stack bring-up switches from its fixture grants to the reconcile node). Depends on A4 and C4. Size 4.
- A lane start emits exactly one reconcile command -- falsifier: the broker readback after a lane start.
- The A4 job holds no fixture grant document any more -- falsifier: grep the job and its topology
  document for the fixture's file name.

**C8. Bundles that are mounted are never pruned** (omnibase_infra#4252 adopted; the bundle observe
handler from C3 is its standing check). Size 3.

**C9. The reboot drill** (the `reboot_recovery` handler in the probe effect over the two projections; a
runbook kept with the lab's own documents). Running it is decision D5. Size 4.

## 6. Order of work and size

Dependency order, no dates. Parallel within a line.

1. S1, S2, S4. Then S3 once omnibase_infra#4254 is merged.
2. A1, B1, C1, B3, C0.
3. A2, A3, B2, C2, C3, A7.
4. A4, B4, C4, A6.
5. B5, B6, C5, C6, C7, C8.
6. A5 per repository, B7, C9.

Tasks: 4 in the slice, 7 in workstream A, 7 in workstream B, 10 in workstream C (C0 to C9), 28 in all.
Sizes, all estimates: slice 13, A 39 (A5 counted once), B 41, C 61. Total 154 lane-hours, plus 4 per
additional repository for A5.

## 7. Doctrine gates

| Gate | Where it is met |
| - | - |
| rendered task content, no placeholders | every task names its files and its falsifiers; A4 and A7 fail a plan with a missing result |
| replay determinism | A3, B2, C5 replay tests; B4 replays the recorded day |
| ordering authority per projection | A3 `finished_at` then offset; B2 per column source `as_of` then offset; C5 observation time then offset |
| deterministic keys plus UPSERT | A3, B2, C5 keys above; B5 revert key; C4 apply key |
| measured versus estimated cost | every size is an estimate; A4 records measured wall time |
| one concept per topic | section 3.1: one topic per fact; no topic shared with the post-merge lab-pass lanes |
| pure envelopes | every compute handler is definition-B (`handle(request) -> result`) with no envelope |
| FAIL-not-WARN | A4, A7, B2, C5: missing or undecidable is a failure |
| consumer health | the lab step of A3, B2 and C5 reads the projection's consumer group |
| track isolation | S3 and A4 run on ephemeral stacks; B4 runs in throwaway containers; B5's lab step never touches a real base; C4's lab step uses a scratch principal |
| durable-queue contracts | the three commands are durable topics declared in their contracts |
| column ownership for multi-path writes | B2's per-source column test |
| projection two-class split | A3, B2, C5 |
| model before build | B3 blocks B4 and B5; C0 blocks C4 |

## 8. Adversarial pass (applied before review)

- **R1 count.** Section 6 recounted from section 5: 28 tasks, the sizes summed per workstream.
- **R2 criteria.** No criterion says "tests pass" alone; each names a table, a run or a read.
- **R3 scope.** S1 is a text change in a temporary skill and cannot enforce anything at GitHub; S4 is the
  enforcement, and S2 the detection behind it. The CI job cannot prove lab-only checks; A6 routes those
  to the lab receipt.
- **R4 integration.** File paths, the harness line, the allowlist location, the selection function and
  the webhook fold's drop point are cited at `dev` as read on 2026-09-28. Topic names follow the existing
  producer segments (`github`, `omnibase-infra`, `omnimarket`).
- **R5 idempotency.** Keys: provenance by sha; probe results by (check, subject, surface); branch-head
  rows by (repo, branch) and (repo, branch, sha); revert by (repo, culprit sha); apply by (surface kind,
  surface id, item key, desired digest). A rerun replaces or no-ops.
- **R6 verification.** Strong: S3's negative control at the #4227 merge; B4's replay of the recorded day;
  C4's double apply. Medium: A1's node-versus-script comparison. Weak and never alone: any lab readback
  without a negative control.
- **R7 expansion.** B5 adds a verb to `node_pr_landing_github_effect`; C5 adds a column to lab lane
  health. Both are additive; no caller changes behaviour.
- **R8 prerequisites.** S3 needs #4254; A6 needs the lab-proof receipt slices; A5 in omnimarket needs D6
  for `merge_group`; C6 needs C1 released and pinned; B4 and B5 need B3's verdict; C4 needs C0's. Each
  unmet one leaves its task blocked, never partly shipped.

## 9. Risks

- **Runner time.** A4 adds a stack bring-up to every merge-group entry. A4 measures it before A5 copies
  it; if it exceeds the queue's check timeout, the fix is a smaller stack, not a path filter.
- **Revert churn.** A wrong culprit reverts good work. B4 confirms only on fail-at-merge and
  pass-at-parent; everything else escalates.
- **Apply on hosts.** Host-level apply needs privileged adapters on lab hosts. Decision D3 keeps it
  observe-only until the drill passes once.
- **Derived grants are wider than hand grants** where a principal runs contracts it never exercises. The
  derivation is by declared contract set, so narrowing is a declaration edit.

## 10. Out of scope

Production and the public cluster. Cloud broker grants (IAM, already declared). The lab delegation
probe's refused-group tolerance (being fixed separately). Moving the forwarder into its node. The
proof-profile scheduler of the lab-proof plan.

## 11. Decisions for the operator

- **D1.** Should GitHub refuse any merge outside the queue on queue-controlled branches, by removing
  every bypass from those rulesets? Recommended: yes. The landing path never needs one.
- **D2.** When the guard confirms a culprit, should its revert PR land through the queue without a human?
  Options: (a) land when green; (b) wait one queue cycle for a fix PR naming the same failing tests, then
  land; (c) open only. Recommended: (b).
- **D3.** May the reconcile node apply host-level settings (kernel, systemd, network, power) on lab
  hosts, or only observe them and fail loudly? Recommended: apply broker grants, lane services and
  bundles; observe host settings until the reboot drill passes once, then decide again.
- **D4.** Should the board-check job run on every merge-group entry, at an extra bring-up per entry?
  Recommended: yes; the alternative, one run per batch, cannot attribute a red to an entry.
- **D5.** May one lab host be rebooted for the drill once C5 to C7 have landed? Recommended: yes, the
  least-loaded host first.
- **D6.** Should omnimarket's merge queue be turned on, so its board checks run on the merge-group commit
  as in omnibase_infra? Recommended: yes, after A4 has run green for a week of merges in omnibase_infra.
