---
type: plan
status: active
date: "2026-09-28"
title: "Verification before and after merge, and declared lab state, as ONEX nodes, events and projections"
topics: [ci, merge-queue, verification, projection, reconcile, drift, broker-acl, determinism]
---

# Verification before and after merge, and declared lab state, as ONEX nodes, events and projections

state_as_of: 2026-09-28T15:14:00Z

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
| a | omnibase_infra#4227 added a tenant-prefixed command topic to the gateway forwarder's **cloud inbound** set (`node_bus_forwarder_effect/contract.yaml`, `mirror_topics.inbound`). The topic does not exist on the dev cloud broker until the cloud side provisions it, so the lab dev lane's forwarder got a topic-authorization error from the **cloud** broker in `cloud_transport.start()` (`gateway_forwarder.py:1073`), with no guard, and the process exited and restarted in a loop. Fix: omnibase_infra#4254, open. | behaviour under an enforcing broker; cross-repo provisioning order | The unit test swaps in a fake transport. CI test shards exclude the `kafka` marker. Every CI broker is either plaintext with no auth, or SASL with its one user made a superuser (`tests/integration/customer_path/redpanda_sasl_harness.py:613`), so topic grants are never checked. No job starts the forwarder. The two-sided provisioning pin (`tests/unit/nodes/node_bus_forwarder_effect/test_provisioning_sync_omn17201.py`) passed because #4227 added the topic to the pin's own literal list in the same PR: a pin its own PR can edit proves nothing about the other side. The board check that did catch it is scheduled four times a day and caught it about two hours after the break. |
| b | omnibase_infra#4111 changed a routing table that three tests under `tests/ci/` assert on. `dev` went red on six cases. Fix: omnibase_infra#4255, open. | merge outside the queue | PR CI ran smart selection, which maps that config file to no tests, so the three tests never ran. **The merge queue did catch it**: the full suite failed on the merge group six times, and the queue removed the PR six times. A landing lane then merged it with a direct REST merge call, outside the queue. `dev` push CI diffs only `HEAD~1` and is smart-selected, so it passed. Every later merge group then failed on the same six cases. |
| b' | The same bypass happened again at 14:27Z: omnibase_infra#4197 was removed from the queue for failed checks and then merged by a direct REST call. | merge outside the queue | The landing brief of the drain says "merges by REST squash on the exact head" in its general rules and "enqueue, never a REST merge" in its omnibase_infra rule. Lanes followed the general rule. GitHub accepted the REST merge on a branch whose ruleset requires the queue. |
| c | The lab delegation client was refused by the lab broker. The grants it depends on exist only in broker state, typed by hand, and a rebuild of the broker volume loses them all. | undeclared state | Nothing declares broker grants for lab principals, and nothing compares live grants with a declaration. |
| d | Two lab lanes were down after a reboot because a bundle prune had deleted deployed bundle directories that their containers still mounted. Fix: omnibase_infra#4252, open. | undeclared state, unchecked invariant | The prune reads only its own lane's registry and never checks live mounts. |
| e | The lab alarm read the lab-pass receipt as INDETERMINATE for ten hours and raised nothing. Fix: omnibase_infra#4247, open. | undecidable fails open | An undecidable verdict was treated as "no news". |

The pattern: (a) and (c) are the same class, not the same fact. In both, what a principal needs on a
broker is known from contracts but never derived and checked against what the broker admits. They differ
in the broker, the owner and the operation: (a) is a missing topic on the cloud broker, provisioned by
the cloud side; (c) is a missing group DESCRIBE grant on a lab broker, applied by hand. The plan treats
them separately (3.4). (b) is a landing path that can leave the queue, and (d) and (e) are state and
verdicts that nobody declares or bounds.

## 2. Existing assets

Read from the `dev` branch of each named repository on 2026-09-28 between 14:30Z and 14:48Z, unless
another source is given.

| Asset | Repo | State | Reuse or replace |
| - | - | - | - |
| Merge queue on omnibase_infra `dev` (ALLGREEN, squash, up to 5 entries built); the `merge_group` event forces the full suite (`scripts/ci/detect_test_paths.py:673`) | omnibase_infra | live | **reuse**: the merge-group commit is where the new required checks run |
| `CI Summary`, the single required context: a no-`needs`, default-deny, fail-closed poller over every job of the run; the only non-gating jobs are the `SOFT_ALLOWLIST` in `scripts/ci/ci_summary_gate.py:424` | omnibase_infra | live | **reuse**: a new job in `ci.yml` that is not soft-allowlisted gates the merge with no branch-protection write |
| `FULL_SUITE_BRANCHES = {"main"}` (`detect_test_paths.py:287`); push CI computes changes from `HEAD~1` (`ci.yml`, detect-changes job) | omnibase_infra | live | **extend**: a `dev` push whose commit was not validated by the queue gets the full suite (task S2) |
| `node_pr_landing_github_effect`: the landing workflow's GitHub effect. Its verbs are rerun, update branch, arm, enqueue, disarm and reads. It has no direct-merge verb. `node_pr_landing_orchestrator` and `node_projection_pr_landing` already carry the landing transitions and merged events. | omnimarket | live | **reuse as the landing path**; it gains one verb, open-revert (task B5, a labelled expansion); the guard reads landing state from `node_projection_pr_landing`, not from GitHub |
| Other code that can merge a PR: `node_pr_lifecycle_merge_effect` (arms `--auto` on queue repositories, squash-merges elsewhere, through `adapter_github_merge_queue.py`), `HandlerAdminMerge` in `node_pr_lifecycle_fix_effect` (an opt-in admin merge of stuck queue PRs, behind the arm-gate choke point), `node_auto_merge_effect` (`gh pr merge`, hard-gated off) | omnimarket | live code; gated | **inventory and pin** (task S4): on a queue-controlled branch each either enqueues or refuses, proven by a test per path; `HandlerAdminMerge` is removed, because an admin merge of a PR the queue refused is exactly (b) |
| `node_lab_proof_plan_compute` (handlers `lab_proof.plan` and `lab_proof.verdict`: mandatory checks graded from a run's observations, with a base-control result) and `node_lab_proof_run_effect` | omnibase_infra | live | **reuse as the one grader**: the CI half adds a `ci_ephemeral` surface to the same plan and verdict handlers instead of two new compute nodes (A4) |
| `node_projection_ci_attempt_outcome` (one row per repository, PR, head, check and run attempt, with a cause code) | omnimarket | live | **reuse** for PR-scoped attempts; branch-head rows (B2) carry what it has no key for: a base-branch sha with no PR |
| `CI Summary` counts `skipped` as passed for jobs outside its registered gates (`GOOD_CONCLUSIONS`, `scripts/ci/ci_summary_gate.py:913`); only registered gates must be present and completed (`:2717`) | omnibase_infra | live | **extend**: every new job is a registered strict gate, so absent, skipped, neutral or cancelled fails (S3, A4) |
| The SASL harness adopts a declared broker when one is configured and resolves the Docker-host address on self-hosted runners (`redpanda_sasl_harness.py:28-56`); the local provisioner polls `localhost` (`handler_local_provision.py:243`) | omnibase_infra | live | **extend**: S3 and A4 refuse broker adoption and use the harness's address resolution, so they run the same on hosted and fleet runners and never touch a lab broker |
| The two-sided forwarder provisioning pin (`test_provisioning_sync_omn17201.py` here, the provisioner's union constant in the private deployment repository) | omnibase_infra, private | live; passed on #4227 because that PR edited both the contract and the pin | **replace** its literal list with the C2 derivation, and add the lab-half `forwarder_refused_topic` check (S5), which reads what the cloud broker actually admits |
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
| event | `onex.evt.github.branch-ref-advanced.v1` | omnibase_infra | one base-branch ref move from a `push` delivery: repo, branch, before sha, after sha, pusher, `as_of`, delivery id. Only this event moves a branch head |
| event | `onex.evt.github.branch-head-status.v1` | omnibase_infra | one check-run verdict on a base-branch commit: repo, branch, sha, check name, verdict, run id, run attempt, `as_of`, delivery id. It attaches to its exact sha and never moves the head |
| event | `onex.evt.github.merge-group-status.v1` | omnibase_infra | one check-run verdict on a merge-group candidate: repo, base branch, candidate sha, the PRs in the group, verdict, run id. A candidate is not the branch; a red candidate never turns `dev` red |
| event | `onex.evt.omnibase-infra.merge-provenance-evaluated.v1` | omnibase_infra | whether a `dev` commit was validated by a successful merge group: `VALIDATED`, `UNVALIDATED` or `UNDECIDABLE`, with the run ids read |
| event | `onex.evt.omnibase-infra.board-probe-result.v1` | omnibase_infra | one board check's outcome in one execution: check id, subject (repo, sha, kind `merge_group`, `pr_head`, `branch_head` or `scheduled`), surface class and surface instance, execution id, plan digest, target digest (the image or bundle the probe ran against), `started_at`, `finished_at`, `PASS`, `FAIL` or `INDETERMINATE`, reasons. Partition key: the subject |
| event | `onex.evt.omnimarket.verdict-deadline-elapsed.v1` | omnimarket | a declared bound expired for one open episode (an `INDETERMINATE` or missing verdict, a bisect, a revert): subject, episode id, bound, deadline. Emitted by the guard orchestrator from a timer declared in its contract and re-armed from the projection on restart, so silence still produces an event |
| event | `onex.evt.omnimarket.devhead-red-detected.v1`, `...devhead-culprit-identified.v1`, `...devhead-revert-opened.v1` | omnimarket | the guard's three terminals, keyed by repo, branch and first red sha |
| event | `onex.evt.omnibase-infra.declared-state-observed.v1`, `...declared-state-applied.v1` | omnibase_infra | one declared item's desired and observed digests and status (`IN_SYNC`, `DRIFTED`, `MISSING`, `UNOBSERVABLE`); one apply result |
| command | `onex.cmd.omnibase-infra.board-probe-run.v1`, `onex.cmd.omnimarket.devhead-bisect.v1`, `onex.cmd.omnibase-infra.declared-state-reconcile.v1` | as above | durable command topics that start each node; the reconcile command carries scope, mode (`observe` or `apply`) and trigger (`bring_up`, `schedule`, `boot`, `manual`) |
| effect | `node_merge_provenance_observe_effect` | omnibase_infra | reads, through an injected GitHub adapter, the merge-group runs and `CI Summary` conclusions recorded for one sha, and publishes them as a typed observation; a failed read is an observation with `read_ok=false`, never an empty list |
| compute | `node_merge_provenance_compute` | omnibase_infra | pure: a commit and the merge-group observation for it, to a provenance verdict |
| compute | `node_lab_proof_plan_compute` (existing), new handlers `board_check.plan` and a `ci_ephemeral` surface on `lab_proof.verdict` | omnibase_infra | pure: the coverage contract and a subject, to the checks that must pass on that subject and on which surface; then the plan and the results of **that execution**, to one verdict. A missing, `INDETERMINATE`, stale (another execution id or target digest) or empty result set is a failure, and so is an empty plan |
| contract | `board_check_coverage.yaml` (in `node_board_probe_effect`) | omnibase_infra | every board criterion a check covers, by stable check id, with its surface class; a check classed `cloud` or `post_release` carries the reason it cannot run before merge. The private board maps its criteria onto these ids and its CI fails on a criterion no check id covers |
| orchestrator | `node_board_check_orchestrator` | omnibase_infra | owns the pre-merge run: provision the ephemeral stack, reconcile its grants, plan, probe, grade, tear down, publish. A CI job is one `onex run-node` call to it plus the upload of its result |
| effect | `node_board_probe_effect` | omnibase_infra | one handler per board check; the target is an injected adapter bound per surface (the CI ephemeral stack, or a lab lane through its overlay) |
| reducer | `node_devhead_guard_reducer` | omnimarket | pure FSM per (repo, branch): `GREEN` to `RED_DETECTED` to `BISECTING` to `CULPRIT_CONFIRMED` to `REVERT_OPEN` to `GREEN`, with `ESCALATED` on an ambiguous or unreproduced bisect or an expired bound |
| orchestrator | `node_devhead_guard_orchestrator` | omnimarket | consumes branch-head, provenance, probe and lab-pass events; issues focused test runs for the bisect and the revert through the GitHub effect |
| compute | `node_broker_grant_derive_compute` | omnibase_infra | pure: a principal's **resolved bus bindings** (the typed model the runtime itself builds: broker identity, physical topic after tenant prefixing, direction, the actual consumer group id, and the operations the client performs such as group DESCRIBE) to the exact grants it needs on each broker. It reads the same model the runtime uses, so a binding the runtime adds is a grant the derivation adds |
| effect | `node_declared_state_observe_effect` | omnibase_infra | one handler per surface kind, reading live state through injected adapters: broker ACLs, compose services, host settings, deployed bundles |
| compute | `node_declared_state_diff_compute` | omnibase_infra | pure: desired against observed, to drift items and an idempotent apply plan |
| effect | `node_declared_state_apply_effect` | omnibase_infra | applies plan items for the surface kinds its overlay policy allows, refuses the rest by name |
| orchestrator | `node_declared_state_reconcile_orchestrator` | omnibase_infra | observe, diff, apply when in `apply` mode, observe again, publish |
| projection | `node_projection_branch_head_health` | omnimarket | one row per (repo, branch) and a history row per (repo, branch, sha): head sha (moved only by `branch-ref-advanced`), verdict per check at that exact sha, provenance, lab-pass state, open red, open deadlines, culprit, revert PR |
| projection | `node_projection_board_probe_results` | omnimarket | one row per (check id, subject kind, repo, sha, surface) |
| projection | `node_projection_declared_state_drift` | omnimarket | one row per (surface kind, surface id, item key), latest status and since when |
| core types | overlay keys `broker.principal_grants`, `host.settings`, `lane.services` and their typed documents; the resolved bus-binding model; protocols for the four observe adapters | omnibase_core, omnibase_spi | the declaration a deployment supplies, which is also the **expected inventory**: every declared item, lane and host must be observed in each round; shipped code names no lane, host or principal |

Each projection is two classes (a pure fold and an effect-class writer on the projection runner base),
declares `projection_api.expose`, and is read by the dashboard through the generic projection route. The
queue-status skill and the drain read the same route; neither reads GitHub for these facts.

### 3.2 Workstream A: pre-merge verification for every PR author

1. **Where checks run.** Each board check handler in `node_board_probe_effect` declares, in the node's
   contract, a stable check id named for what it checks (`consumer_flow`, `negative_paths`,
   `provider_catalogue`, `receipt_identity`, `forwarder_refused_topic`, `declared_state`) and a surface
   class: `ci_ephemeral` (runs against a stack CI can start), `lab_hardware` (needs a local model server
   or other lab hardware), `cloud`, or `post_release` (tests published packages). The coverage contract
   (3.1) lists every check id; the private board maps its criteria onto those ids, and a criterion with
   no check id, or a check classed `cloud` or `post_release` without a stated reason, fails the board's
   own CI. A plan that comes out empty for a subject that has declared checks is a failure, never a pass.
2. **The CI half.** On `pull_request` and on `merge_group`, one job in the repository's `ci.yml` makes
   one call, `onex run-node node_board_check_orchestrator`. The orchestrator brings up an ephemeral stack
   it owns exclusively with `node_setup_local_provision_effect` (broker with per-topic authorization on
   and a non-superuser runtime principal, Postgres, the runtime, the gateway forwarder), runs the declared
   state reconcile in `apply` mode so the stack gets exactly the derived grants, asks
   `node_lab_proof_plan_compute` for the `ci_ephemeral` checks, runs them through
   `node_board_probe_effect`, grades that execution with the same verdict handler the lab half uses,
   tears the stack down and publishes every result as a probe-result event. The stack never adopts an
   existing broker, and endpoints are resolved the way the SASL harness resolves them, so the job runs the
   same on hosted and on fleet runners and needs no lab host, credential or service. The job is a
   **registered strict gate** of `CI Summary`: absent, skipped, neutral, cancelled or timed out fails the
   required context. Checks that grade a model's answer run with a stub responder in CI and grade only
   routing and terminal shape; the real-model leg is a `lab_hardware` check.
3. **The lab half.** `lab_hardware` checks join the `mandatory_checks` of the lab proof profiles of the
   repositories they cover. Nothing else changes: the prover runs the profile on the PR head, the
   verifier mints the `pr-head` receipt, the receipt projection feeds the `lab-proof` required context,
   and that context already reads the queue ref on `merge_group`.
4. **Undecidable fails closed.** A check that is planned and has no result from this execution, or has
   `INDETERMINATE`, or has a result bound to another execution id or target digest, is a failure in the
   verdict handler and in the `lab-proof` verifier. There is no neutral or skipped conclusion for a planned
   check.
5. **`cloud` and `post_release` checks** stay scheduled after merge. Their results feed the branch-head
   guard (3.3), so a red one is traced and reverted like a red test.

### 3.3 Workstream B: the `dev` head guard

1. **The queue cannot be left.** The only merge verb in the landing path is enqueue
   (`node_pr_landing_github_effect`); every other code path that can merge is inventoried and either
   enqueues or refuses on a queue-controlled branch (S4); the temporary brief is fixed to match (S1,
   which removes one known instruction and prevents nothing by itself); and the operator decides whether
   GitHub itself refuses a merge outside the queue (decision D1). Prevention is claimed only when the
   effective ruleset, including its bypass list, is readable and shows no bypass; an unreadable policy
   counts as not enforced.
2. **Provenance.** On every `dev` push, CI calls `node_merge_provenance_observe_effect` and then
   `node_merge_provenance_compute` for this exact commit: was it a merge-group commit with a successful
   `CI Summary`? A queue landing makes the merge-group commit the new `dev` head, so the answer is a
   lookup, not an inference. `UNVALIDATED` or `UNDECIDABLE` forces the full suite on that push. That alone
   would have turned `dev` red within one push run after (b); S2 proves it by replaying that push.
3. **Detection.** The webhook ingress folds `push` deliveries on a watched base branch into
   `branch-ref-advanced`, base-branch check runs into `branch-head-status` attached to their exact sha,
   and merge-group check runs into `merge-group-status`, which describes a candidate and never the branch.
   The branch-head health projection moves a head only on `branch-ref-advanced`; a late result for an
   older sha updates that sha's history row and never the head's verdict. It also folds provenance,
   post-merge probe results and lab-pass receipts. A fold only changes on an input, so a bound is enforced
   by an event: the guard orchestrator arms a deadline for every open `INDETERMINATE` or missing verdict
   from its contract-declared timer, re-arms open deadlines from the projection on restart, and emits
   `verdict-deadline-elapsed` when one expires; the projection folds that as red and the alerter fires.
   That closes (e) even when the producer goes silent.
4. **Bisect.** The guard orchestrator takes the failing test ids from the red run, and for each merge
   between the last green and the first red head, in order, runs them with `node_focused_test_run_effect`
   at the merge and at its parent, each in a fresh container with the dependency lock of that commit. A
   culprit is confirmed only when the failing ids fail at the merge and pass at its parent under the same
   runner image and lock digests. A failing board check is bisected only when its surface class is
   `ci_ephemeral`, by starting a fresh ephemeral stack at each commit; a `lab_hardware`, `cloud` or
   `post_release` red, whose surface cannot be held constant across two commits, goes to `ESCALATED` with
   the evidence. Anything else is `ESCALATED` too, never guessed.
5. **Revert.** For a confirmed culprit the orchestrator opens a revert PR through the GitHub effect
   (idempotency key: repo, culprit sha), labelled and linked to the red, and it enters the queue like any
   PR. If a fix PR naming the same failing ids is already in the queue, the revert waits for one queue
   cycle, then proceeds. Whether a revert lands without a human is decision D2.
6. **Visible.** The dashboard shows the branch-head health rows; the queue-status skill and the drain map
   read the same projection, so a red `dev` is the first line of every queue report.

### 3.4 Workstream C: declared lab state

1. **Declaration.** Three overlay keys, each a typed document in core with a JSON Schema export, supplied
   by whoever runs the deployment:
   - `broker.principal_grants`: a principal, the broker it is declared for, the contract set (or client
     profile) it runs, and any explicit extra grants with a reason. The grants themselves are
     **derived**, not listed: `node_broker_grant_derive_compute` reads the principal's resolved bus
     bindings, the same typed model the runtime builds, so tenant prefixing, the forwarder's own group
     names and the operations a client performs (a group DESCRIBE, as in (c)) are all covered. A binding
     the runtime adds is therefore a grant the derivation adds on the next reconcile. This closes (c) on
     lab brokers, which the reconcile node may write.
   - The cloud broker is not written by this plan (section 10). For (a) the plan closes the outage and
     the silence, not the provisioning: the forwarder survives a refused topic (S3), a refused topic is a
     `FAIL` of the `forwarder_refused_topic` check on the lab half before merge and on the lab-pass receipt
     after it (S5), and the forwarder's provisioning pin reads the C2 derivation instead of a literal list
     its own PR can edit (C2). The cloud side's parity check can consume the same derivation.
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
   mode it changes only the surface kinds its overlay policy allows (decision D3). Command deduplication
   and repair are different things: a reconcile command is deduplicated by (surface id, trigger, round
   id), but every round observes first and plans from what it observed, so a hand edit made after a
   successful apply is repaired by the next round. Each apply item carries the observed generation it was
   planned from as a precondition and is refused if the surface moved since; one reconcile holds a
   per-surface lease, so two rounds never interleave applies on one surface.
4. **Loud failure.** Every observed item is an event; the drift projection keeps the latest per item and
   compares each round with the declaration, which is the expected inventory. A declared item, lane or
   host with no observation in a round is `MISSING`; a round that did not complete is `UNOBSERVABLE` for
   every item it did not reach; zero observations for a surface that declares items is a failure, never a
   clean result. A `DRIFTED`, `MISSING` or `UNOBSERVABLE` item older than one reconcile interval fails
   the `declared_state` board check, fails a new `declared_state_in_sync` mandatory check on the
   post-merge lab-pass receipt (so staging delivery stops), and alerts through the alerter.
5. **Reboot drill (proposed, not run).** An operator reboots one lab host. The boot trigger runs the
   reconcile; the drill passes when, within a declared bound, the host reports a new boot id, a complete
   observation round after that boot shows every declared item for that host `IN_SYNC`, and every lane
   declared on that host has a PASS lab-pass receipt produced after the new boot. A receipt from before
   the boot, or a lane with no receipt, fails. The grading is a check id (`reboot_recovery`) in the probe
   effect, computed from the two projections. Running it is decision D5.

### 3.5 What stays outside the primitives, and why

- CI workflow steps and the queue-status and drain skills are shims that call nodes or read projections;
  each CI step is one `onex run-node` call plus writing its output, and holds no selection, grading or
  GitHub logic. The drain's landing brief is a temporary process skill; its replacement is the landing
  workflow of the PR landing plan, whose GitHub effect is `node_pr_landing_github_effect`.
- The branch-protection audit in the change-control repository (S4) stays a script for now: that repository
  audits settings of every repository and is not a runtime. Its new rule is a pure function with a table
  test, so it can move into a compute node there without being rewritten.
- The ruleset change itself (D1) is a GitHub setting, not a primitive. It is the enforcement GitHub offers;
  the plan's own mechanism is the S4 inventory and the provenance check (S2), which work without it.
- The gateway forwarder's process entrypoint (`src/omnibase_infra/runtime/gateway_forwarder.py`) is
  existing non-canonical debt. Its refused-topic fix (omnibase_infra#4254) lands as is; the CI test in
  S3 pins the behaviour at the deployed entrypoint, so the test survives when the forwarder becomes the
  handler of `node_bus_forwarder_effect`.
- The lab alarm is retired, not rebuilt (B7).

## 4. The first slice: what would have caught (a) and (b) this week

Five tasks, smallest first. S1, S2 and S4 need nothing else from this plan; S3 and S5 need
omnibase_infra#4254 merged, because the behaviour they pin is that fix.

- **S1** removes the instruction that sent lanes outside the queue. It prevents nothing by itself; it
  stops the landing brief from being the cause.
- **S2** gives every `dev` push that did not come through the queue the full suite. Detects (b) on the
  first push after it, proven by replaying that push.
- **S3** runs the forwarder against a broker that enforces grants, with one topic it may not read. Pins
  the crash half of (a): a refused topic can no longer take the forwarder down.
- **S4** inventories every code path that can merge and pins each to enqueue-or-refuse on a
  queue-controlled branch, plus the operator's ruleset change (D1) and the audit that keeps it. Prevents
  (b) and (b') from code; D1 prevents them from a person or a token.
- **S5** makes a refused topic a failure on the lab half before merge. Catches the provisioning half of
  (a): #4227's head would have failed the check on the lab lane whose cloud leg refused the topic.

Every other task follows in section 6 order.

## 5. Tasks

Each task is one lane and one ticket, with one PR per repository it touches. Each writes the failing test
first, runs only focused tests locally, and runs anything broad on a lab host or in CI. Each PR body cites
its lab readback. Sizes are lane-hours and are estimates unless marked measured.

### Slice

**S1. The drain's landing brief never merges outside a queue** (private process-skill repository: the
drain workflow's rules block and the land skill's merge step). Test first: for a repository whose base
branch carries a merge-queue rule, the rendered rules contain no REST merge call and name the enqueue
verb; for a repository without one, the squash merge on the exact head stays. Minimal change: one rule
text, chosen by the live queue read the drain already makes; an unreadable queue read renders the enqueue
rule, never the REST one. Lab step: one drain refresh in dry-run against the live queue read. Size 1.
- The rendered rules for omnibase_infra contain `--match-head-commit` and no `pulls/<n>/merge` --
  falsifier: render the rules block for omnibase_infra and grep for `pulls/` and `merge_method`.
- A failed queue read renders the enqueue rule -- falsifier: the render test with the read stubbed to fail.
- The skill's frontmatter names `node_pr_landing_github_effect` as its replacement -- falsifier: grep the
  frontmatter's `replaces_when` for the node name.

**S2. Merge provenance, and the full suite for an unvalidated `dev` push** (omnibase_infra:
`src/omnibase_infra/nodes/node_merge_provenance_observe_effect/` and
`src/omnibase_infra/nodes/node_merge_provenance_compute/{contract.yaml,node.py,handlers/handler_merge_provenance.py,models/model_merge_provenance_request.py,models/model_merge_provenance_result.py}`;
the detect-changes job in `.github/workflows/ci.yml`; `scripts/ci/detect_test_paths.py` accepts a
forced-full input with its own reason `UNVALIDATED_PUSH`, passed only for an `UNVALIDATED` or
`UNDECIDABLE` verdict). The observe effect reads the merge-group runs for the pushed sha through an
injected GitHub adapter; the compute handler is definition-B and pure. Test first: the real pair from
2026-09-28, `dev` commit e263eee (no merge-group run, the queue's commit was bbc24237) returns
`UNVALIDATED`; a queue-landed commit returns `VALIDATED`; an observation with `read_ok=false` returns
`UNDECIDABLE`. Focused test: `uv run pytest tests/unit/nodes/node_merge_provenance_compute -q`. Lab
step: replay the push path at e263eee on a lab runner (a dispatch of the same workflow's push job graph
against that sha), then at the fix for (b). Size 6.
- The three verdicts above for the three inputs -- falsifier: the unit test table with those three rows.
- The push-path replay at e263eee selects the full suite with reason `UNVALIDATED_PUSH`, **executes all
  six failing cases** named in the internal companion, and turns `CI Summary` red; the same replay at the
  fix passes -- falsifier: the junit files of both replays list the six node ids with outcome `failed`
  and `passed` respectively, and the two `CI Summary` conclusions.
- A `VALIDATED` push keeps smart selection -- falsifier: `selection.json` of the next queue-landed push
  shows the reason is not `UNVALIDATED_PUSH`.
- The workflow steps contain no provenance logic -- falsifier: each step's `run:` is one `onex run-node`
  call plus its output write.

**S3. The forwarder survives a refused topic, on a broker that enforces grants** (omnibase_infra:
`tests/integration/bus_acl_boundary/test_forwarder_refused_topic.py`; a non-superuser principal option
in `tests/integration/customer_path/redpanda_sasl_harness.py`; a `bus-acl-boundary` job in
`.github/workflows/ci.yml` on `pull_request` and `merge_group`, unconditional, not path-scoped, and
registered as a strict gate of `CI Summary`). The harness starts its own broker for this test and refuses
to adopt a declared one, keeps one superuser for bootstrap only, and creates a runtime principal with
grants for every topic the forwarder subscribes to except one canary inbound topic. The test starts the
forwarder through its deployed entrypoint and asserts: the process is alive after 30 s; the refused topic
is reported by name in `refused_topics`; one event produced on a granted inbound topic arrives on its
outbound topic. Negative control: the identical test file, transplanted onto c6c1c47c8 (the #4227 merge)
with no other change, collects, runs, and fails on the forwarder exiting with a topic-authorization
error. Depends on omnibase_infra#4254. Lab step: the job's test run on a lab runner against the fix's
head, and the transplanted negative control. Size 7.
- Passes at the #4254 head; at c6c1c47c8 the same test fails with a topic-authorization exit, not a
  collection or setup error -- falsifier: both runs' junit results, the failure message cited in the PR.
- The job is a strict gate: absent, skipped, cancelled and timed-out each fail `CI Summary` -- falsifier:
  four rows in `tests/ci/test_ci_summary_gate.py` fed through the real evaluator, plus the job's check
  run on the next merge-group commit.
- The runtime principal is not a superuser and the broker is the test's own -- falsifier: the harness's
  `rpk acl user list`, superuser config and container id read inside the test, asserted.
- The same job passes on a hosted runner and on a fleet runner -- falsifier: one run of each, cited.

**S4. No code path, and no person, merges outside the queue** (omnimarket: remove `HandlerAdminMerge`
from `node_pr_lifecycle_fix_effect`; a test per remaining merge-capable path (`node_pr_landing_github_effect`,
`node_pr_lifecycle_merge_effect`, `node_auto_merge_effect`) that on a queue-controlled branch it enqueues
or refuses; operator: decision D1, a ruleset change on the queue-controlled branches; change-control
repository: `scripts/audit_branch_protection.sh` gains a rule that fails on a queue ruleset with any
bypass actor, and on a ruleset whose bypass list it cannot read). Test first: the audit fails on a
fixture with one bypass actor and on one with an unreadable bypass list. Lab step: the audit run against
live settings after the change with a token that can read bypass lists. Size 3, plus the operator's
change.
- Every merge-capable path enqueues or refuses on a queue branch -- falsifier: the per-path tests against
  a recorded GitHub adapter, whose call logs contain no merge call for a queue branch.
- `HandlerAdminMerge` is gone -- falsifier: a repository-wide search for the class name in omnimarket
  returns nothing.
- A direct merge of a queue-controlled PR is refused by GitHub -- falsifier: on a test repository with the
  same ruleset shape and a landing identity of the same kind, a REST merge returns the refusal; the
  result is cited, never provoked on a real repository.
- The audit fails on a bypass actor and on an unreadable list -- falsifier: its two fixtures.

**S5. A refused topic fails the lab half before merge** (omnibase_infra: a `forwarder_refused_topic`
check in `node_board_probe_effect`, class `lab_hardware`, and its row in the omnibase_infra lab proof
profile's mandatory checks). The check reads, on the lane under proof, the forwarder's process state and
its `refused_topics` after one retry interval: `PASS` when the process is up and nothing is refused,
`FAIL` when a topic is refused or the process is down, `INDETERMINATE` (so `FAIL`) when the lane's cloud
leg is not the broker the lane's overlay declares. Until A6's `lab-proof` required context exists, this
runs in the lab-pool proof the landing lanes already require before enqueue. Depends on
omnibase_infra#4254. Test first: the handler on recordings of the three states. Lab step: one prover run
at the #4254 head on the lab dev lane, where the webhook topic is still refused, reading `FAIL`. Size 3.
- The three states grade as stated -- falsifier: the handler's unit test table.
- The check fails on today's lab with the webhook topic refused -- falsifier: the prover run's receipt.

### Workstream A

**A1. The probe effect's contract and its first handler, `consumer_flow`** (omnibase_infra:
`src/omnibase_infra/nodes/node_board_probe_effect/`, the handler body migrated from
`scripts/ci/c28_consumer_flow_probe.py`; the target adapter protocol in omnibase_spi, its I/O models in
omnibase_core). The contract declares each check handler with `check_id` and `surface_class`, and the
node carries `board_check_coverage.yaml` (3.1). The scheduled workflow becomes a shim, and its leftover
push trigger on a feature branch is removed. Test first: the handler against a recorded flow returns
`PASS`, against a stalled consumer group returns `FAIL`, against an unreachable target returns
`INDETERMINATE`; the coverage validator refuses a check id with no handler, a handler with no coverage row,
and a `cloud` or `post_release` row with no reason. Lab step: the node run against the lab dev lane
through its overlay, the result compared with the script's on the same minute. Size 7.
- The three outcomes for the three recordings -- falsifier: the unit test table.
- Coverage is complete both ways -- falsifier: the validator's three refusal fixtures.
- Node and script agree on the lab dev lane -- falsifier: both outputs in the PR body, same verdict.
- The workflow's `run:` is only a node invocation -- falsifier: read the workflow file.

**A2. The remaining CI-class handlers: `negative_paths`, `provider_catalogue`, `receipt_identity`**
(same node; handler bodies from the matching scripts; `receipt_identity` against a stub responder). Test
first per handler as in A1. Lab step as in A1. Size 8.
- Each handler returns all three outcomes on its recordings -- falsifier: the unit test tables.

**A3. The probe-result event and projection** (omnibase_infra publishes; omnimarket
`src/omnimarket/nodes/node_projection_board_probe_results/` fold and writer, migration, `projection_api`
exposed; the chain canary's verdict published in the same shape). Ordering authority: the result's
`finished_at` within one partition (partition key: the subject), then the offset. Key (check id, subject
kind, repo, sha, surface instance, execution id), UPSERT on key, so a rerun is a new row and an old
execution never answers for a new one; a latest-per-subject view picks by `finished_at`. Test first: two
results for one key in either order fold to the later `finished_at`; a result from another execution id
does not satisfy a verdict request; a replay of the topic reproduces the table byte for byte. Lab step:
one probe run on the lab dev lane, the row read back through the projection route, and the consumer
group read. Size 6.
- A result from another execution never satisfies a request -- falsifier: the verdict test with a PASS
  whose execution id differs.
- Replay reproduces the table -- falsifier: the replay test compares row digests.
- Rows readable at `/projection/board_probe_results` -- falsifier: the route's response in the PR body.

**A4. The merge-group board-check job in omnibase_infra** (`.github/workflows/ci.yml` job
`board-checks-ephemeral`, one `onex run-node node_board_check_orchestrator` call, registered as a strict
gate of `CI Summary`; `src/omnibase_infra/nodes/node_board_check_orchestrator/`; a CI deployment topology
document for `node_setup_local_provision_effect` that resolves client endpoints the way the SASL harness
does; the `board_check.plan` handler and the `ci_ephemeral` surface of `lab_proof.verdict` in
`node_lab_proof_plan_compute`). The stack's broker grants come from a fixture document until C4 lands,
then from the reconcile node. Test first: the verdict returns FAIL for a plan with one missing result, for
one `INDETERMINATE` result, for a result from another execution, and for an empty plan on a subject with
declared checks. Lab step: the job's steps run on a lab runner against the merge-group commit of a real
queued PR. Depends on A1, A2, A3, S3. Size 12.
- A planned check with no result fails the job -- falsifier: the verdict unit test, and one deliberate
  red run on a draft PR with a handler disabled.
- An empty plan fails -- falsifier: the verdict test with the coverage contract emptied.
- The job runs on every merge-group entry and is a strict gate -- falsifier: its check run on the next
  three merge-group commits, and the absent, skipped, cancelled and timed-out rows of the gate test.
- The same job passes on a hosted runner and on a fleet runner, and never adopts a lab broker --
  falsifier: one run of each, with the broker container id started by the run.
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
`models/model_github_branch_head_observation.py`, the contract's `published_events`). A `push`
delivery on a watched base branch folds to `branch-ref-advanced`; a summary `check_run` on a watched base
branch folds to `branch-head-status` for its exact sha; a summary `check_run` on a merge-group ref folds
to `merge-group-status`, never to a branch-head event. Test first: a recorded push delivery yields one
ref-advance with before and after sha; a recorded push-triggered `CI Summary` delivery with an empty
pull-request list yields one branch-head status; a failed merge-group delivery yields one merge-group
status and no branch-head event. Lab step: a real delivery on the lab dev lane, the event read back from
the broker. Size 5.
- The three recorded deliveries fold as stated -- falsifier: the fold unit test.
- A red merge-group candidate never produces a branch-head event -- falsifier: same test, the failed
  candidate row.
- A delivery for an unwatched branch still folds to nothing -- falsifier: same test, fourth row.

**B2. The branch-head health projection** (omnimarket
`src/omnimarket/nodes/node_projection_branch_head_health/`, fold and writer, migration, exposed). One
writer; columns owned by source: verdict and sha from branch-head events, provenance from provenance
events, lab-pass state from receipts, probe state from probe results, guard state from guard events. The
head moves only on `branch-ref-advanced`; a status for an older sha updates that sha's history row only.
A `verdict-deadline-elapsed` event folds the open episode as red. The deadline itself is armed by the
guard orchestrator (B4) from its contract-declared timer and re-armed from this projection's open
episodes on restart. Test first: the (e) case, one `INDETERMINATE` receipt followed by **no further
input** until the bound, reads red once the deadline event arrives; a late green for an older sha after a
red head leaves the head red; replay reproduces the table. Lab step: the projection on the lab dev lane
after one `dev` push, read through the route, consumer group read. Size 7.
- The (e) sequence folds red with no second receipt -- falsifier: the fold test with the recorded
  sequence plus the deadline event, and the orchestrator test that a restart re-arms the open deadline.
- A late result for an older sha never changes the head's verdict -- falsifier: the out-of-order fold
  test.
- Each column is written by exactly one event type -- falsifier: a test that folds each event type alone
  and asserts which columns changed.

**B3. A TLA+ model of the guard** (committed in omnimarket beside the reducer, `formal/devhead_guard/`,
with its checker configuration; cited by path in B4 and B5). Properties: at most one revert PR per culprit; a revert is never opened for a merge
that did not fail at itself and pass at its parent; a fix PR and a revert for the same red never both
land without a check in between; a bisect run's runner slot is always released; every red reaches
`GREEN` or `ESCALATED` within the bound. The checker's result is recorded with the model's content
digest, and for each safety property one mutated model that violates it is shown to fail. Blocks B4 and
B5. Size 6.
- Each property holds on the model and fails on its mutation -- falsifier: the checker output for the
  model and for each mutation, committed with the digests.

**B4. The guard reducer and orchestrator, detection and bisect** (omnimarket
`src/omnimarket/nodes/node_devhead_guard_reducer/`, `node_devhead_guard_orchestrator/`; reuses
`node_focused_test_run_effect` and `node_pytest_failure_digest_compute`). The orchestrator also owns the
deadlines of B2. Test first: replayed events of 2026-09-28 (#4111's merge, then red push runs) drive the
reducer to `CULPRIT_CONFIRMED` for #4111's merge; a flaky failure that passes at the merge goes to
`ESCALATED`; a red `lab_hardware` board check goes to `ESCALATED` without a bisect; two runs of one
commit under different runner image or lock digests never confirm. Lab step: one bisect on the lab over
two real commits, with the focused-run receipts cited. Size 13.
- A red whose surface cannot be held constant is escalated, not bisected -- falsifier: the replay row
  with a `lab_hardware` red.
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
stops grading lab-pass receipts; B2 and the alerter carry it). Blocked until the replacement is shown to
work. Size 4.
- The replacement alerts on its own -- falsifier: on the lab dev lane, an injected `INDETERMINATE`
  receipt with no follow-up turns the branch-head row red and posts one alert within the bound, both read
  back, before the script change merges.
- The alarm script no longer reads receipts -- falsifier: grep the script for the receipt reader.

### Workstream C

**C1. The declarations** (omnibase_core: `EnumConfigOverlayKey` gains `BROKER_PRINCIPAL_GRANTS`,
`HOST_SETTINGS`, `LANE_SERVICES`; models under `src/omnibase_core/models/config_overlay/`; JSON Schema
exports; omnibase_spi: the four observe-adapter protocols). Frozen, `extra="forbid"`, no defaults, no lane
or host names. Test first: a document naming an unknown field or an empty principal is refused; the
schema export round-trips. Size 5.
- The core source names no lab principal, host or lane -- falsifier: `git grep -n -E 'compose-dev|stability-test|judge|prepr-'` over exactly the files the PR adds returns no hit, with the same grep over `constants_runtime_lanes.py` as the positive control.

**C2. `node_broker_grant_derive_compute` and the resolved bus-binding model** (omnibase_core: the
binding model; omnibase_infra: the runtime and the gateway forwarder build their transports from it, and
the derive compute reads it). Pure: a principal's resolved bindings, per broker, to topic READ, WRITE and
DESCRIBE grants and group grants, with the physical topic after tenant prefixing and the group id the
runtime actually uses. The forwarder's provisioning pin
(`tests/unit/nodes/node_bus_forwarder_effect/test_provisioning_sync_omn17201.py`) asserts against this
derivation instead of its own literal list. Test first: the real forwarder configuration yields, for the
cloud broker, the tenant-prefixed topic #4227 added and the `tenant-<slug>-gateway-forwarder-inbound`
group; a client that lists and describes groups gets DESCRIBE on exactly the groups it describes (the (c)
case). Size 8.
- Grants cover every binding the runtime builds -- falsifier: a test that starts the transports' config
  builder, collects the bindings it produced, and diffs them with the derivation.
- Adding a topic to a contract adds exactly its grant -- falsifier: a two-version fixture.
- The pin can no longer pass on a one-sided edit -- falsifier: the pin test file contains no topic
  literal.

**C3. The observe effect** (omnibase_infra `node_declared_state_observe_effect`: handlers for broker ACLs
through the broker admin API, compose services, host settings, deployed bundles; adapters bound per
lane by overlay). Each round
carries a round id and compares with the declaration as the expected inventory. Test first: each handler
returns `IN_SYNC`, `DRIFTED`, `MISSING` and `UNOBSERVABLE` on recordings; the bundle handler reports an
empty mounted directory as `MISSING`; a declared item the round never reached is `MISSING`, and an adapter
that returns zero rows for a surface with declared items is `UNOBSERVABLE`, never clean. Lab step: observe
mode on the lab dev lane, every item's status in the PR body. Size 11.
- Zero observations is never clean -- falsifier: the round test with an adapter stubbed to return
  nothing.

**C0. A TLA+ model of reconcile** (committed in omnibase_infra beside the orchestrator,
`formal/declared_state_reconcile/`, with its checker configuration; cited by path in C4). Properties:
apply and a concurrent hand edit converge; two reconciles on one surface never interleave applies; an
apply planned from a stale observation is refused; an apply never removes a grant a declared principal
needs; an `UNOBSERVABLE` surface is never applied to. The checker's result is recorded with the model's
content digest, and for each safety property one mutated model that violates it is shown to fail. Blocks
C4. Size 6.

**C4. Diff, apply and the reconcile orchestrator** (omnibase_infra `node_declared_state_diff_compute`,
`node_declared_state_apply_effect`, `node_declared_state_reconcile_orchestrator`). Depends on C0, C2, C3.
Test first: a first apply of a wrong state changes it; a second round lists zero operations; a hand
edit after that is repaired by the next round; an item whose surface moved since it was observed is
refused; two concurrent rounds on one surface serialize on the lease; a surface kind not allowed by policy
is refused by name. Lab step: apply mode on the lab dev lane's scratch principal, then observe shows no
drift, then one hand edit, then the next round repairs it. Size 13.
- Apply converges and keeps converging -- falsifier: the four-round test (wrong, fixed, hand-edited,
  fixed again), each round's operation count asserted, and the same four rounds on the lab.
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
runbook kept with the lab's own documents). Running it is decision D5. Test first: a PASS receipt from
before the boot, a lane with no receipt, and a round that started before the boot each fail. Size 5.
- Only post-boot evidence counts -- falsifier: the handler's table with those three rows.

## 6. Order of work and size

Dependency order, no dates. Parallel within a line.

1. S1, S2, S4. Then S3 and S5 once omnibase_infra#4254 is merged.
2. A1, B1, C1, B3, C0.
3. A2, A3, B2, C2, C3, A7.
4. A4, B4, C4, A6.
5. B5, B6, C5, C6, C7, C8.
6. A5 per repository, B7, C9.

Tasks: 5 in the slice, 7 in workstream A, 7 in workstream B, 10 in workstream C (C0 to C9), 29 in all.
Sizes, all estimates: slice 20, A 43 (A5 counted once), B 46, C 67. Total 176 lane-hours, plus 4 per
additional repository for A5.

## 7. Doctrine gates

| Gate | Where it is met |
| - | - |
| rendered task content, no placeholders | every task names its files and its falsifiers; A4 and A7 fail a plan with a missing result |
| replay determinism | A3, B2, C5 replay tests; B4 replays the recorded day |
| ordering authority per projection | A3 `finished_at` within the subject's partition, then offset, keyed by execution id; B2 head moved only by ref-advance events, per-sha columns by source `as_of` then offset; C5 round id, then observation time, then offset |
| deterministic keys plus UPSERT | A3, B2, C5 keys above; B5 revert key; C4 apply key |
| measured versus estimated cost | every size is an estimate; A4 records measured wall time |
| one concept per topic | section 3.1: one topic per fact; no topic shared with the post-merge lab-pass lanes |
| pure envelopes | every compute handler is definition-B (`handle(request) -> result`) with no envelope |
| FAIL-not-WARN | S3, S5, A4, A7, B2, C3, C5: missing, skipped, empty, stale or undecidable is a failure; B2 enforces bounds with a deadline event, so silence fails too |
| consumer health | the lab step of A3, B2 and C5 reads the projection's consumer group |
| track isolation | S3 and A4 run on ephemeral stacks they start and own, never an adopted broker; B4 runs in throwaway containers; B5's lab step never touches a real base; C4's lab step uses a scratch principal; S4's refusal test runs on a test repository |
| durable-queue contracts | the three commands are durable topics declared in their contracts |
| column ownership for multi-path writes | B2's per-source column test |
| projection two-class split | A3, B2, C5 |
| model before build | B3 blocks B4 and B5; C0 blocks C4 |

## 8. Adversarial pass (applied before review)

- **R1 count.** Section 6 recounted from section 5: 29 tasks, the sizes summed per workstream.
- **R2 criteria.** No criterion says "tests pass" alone; each names a table, a run or a read.
- **R3 scope.** S1 is a text change in a temporary skill and prevents nothing; S4 is the enforcement in
  code, D1 at GitHub, and S2 the detection behind both. S3 pins the crash half of (a) and S5 its
  provisioning half; no task writes the cloud broker. The CI job cannot prove lab-only checks; S5 and A6
  route those to the lab receipt.
- **R4 integration.** File paths, the harness line, the allowlist location, the selection function and
  the webhook fold's drop point are cited at `dev` as read on 2026-09-28. Topic names follow the existing
  producer segments (`github`, `omnibase-infra`, `omnimarket`).
- **R5 idempotency.** Keys: provenance by sha; probe results by (check, subject, surface); branch-head
  rows by (repo, branch) and (repo, branch, sha); revert by (repo, culprit sha); apply by (surface kind,
  surface id, item key, desired digest). A rerun replaces or no-ops.
- **R6 verification.** Strong: S2's push-path replay executing the six failing cases; S3's transplanted
  negative control at the #4227 merge; S5's prover run on today's refused topic; B4's replay of the
  recorded day; C4's four-round convergence. Medium: A1's node-versus-script comparison. Weak and never alone: any lab readback
  without a negative control.
- **R7 expansion.** B5 adds a verb to `node_pr_landing_github_effect`; C5 adds a column to lab lane
  health. Both are additive; no caller changes behaviour.
- **R8 prerequisites.** S3 and S5 need #4254; A6 needs the lab-proof receipt slices; A5 in omnimarket needs D6
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
- **S5 reads the lab lane's real cloud leg.** If the lane under proof has no cloud leg, or a different
  one, the check is `INDETERMINATE` and fails, which blocks every omnibase_infra landing until the lane is
  fixed. That is intended: an unproven boundary is not a pass.
- **The strict-gate change is wider than two jobs.** Registering S3 and A4 as strict gates is scoped to
  those jobs; `skipped` stays accepted for other unregistered jobs, and widening that is its own change.

## 10. Out of scope

Production and the public cluster. Writing cloud broker topics or grants (IAM, owned by the cloud side);
the checks that read what the cloud broker admits (S5) are in scope. The lab delegation
probe's refused-group tolerance (being fixed separately). Moving the forwarder into its node. The
proof-profile scheduler of the lab-proof plan.

## 11. Decisions for the operator

- **D1.** Should GitHub refuse any merge outside the queue on queue-controlled branches, by removing
  every bypass from those rulesets? Recommended: yes. The landing path never needs one. Whether any bypass
  exists today is not known: the token used for this plan could not read the bypass list.
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

## 12. Hostile review record (2026-09-28)

An external reviewer model read this plan and its evidence at high effort, asked for anything outside the
primitives, unfalsifiable criteria, missed reuse, a slice that would not catch (a) or (b), hidden machine
dependence and gates that pass while doing nothing. Seventeen findings; each was checked against the
source before it was taken.

Taken, and where: design outside the primitives (A4's orchestration moved into
`node_board_check_orchestrator`, S2's GitHub read into an observe effect, 3.5 lists what is left and
why); missed reuse and competing merge writers (section 2 rows, S4); `CI Summary` accepting `skipped`
(strict gates in S3 and A4); empty coverage passing (the coverage contract, A1 and A4); S1 overstated as
prevention (section 4, 3.3); S2 proving selection instead of execution (the push-path replay); runner and
broker adoption (S3, A4); grant derivation missing the forwarder's real topic and group (C2, the resolved
binding model); (a) and (c) treated as one fact (section 1, 3.4, S5); merge-group candidates moving the
branch head (B1, B2); timeouts that cannot fire under silence (the deadline event, B2, B4, B7); results
not bound to an execution (A3, A4); zero-row and stale drift and drill results (C3, C9, 3.4); idempotency
that suppresses repair (C4, 3.4); bisecting on a surface that cannot be held constant (B4, 3.3); a
negative control that could pass on a collection error (S3) and an alarm retired before its replacement
worked (B7); formal models kept outside the repository (B3, C0).

Added by this review beyond the reviewer's list: the two-sided provisioning pin passed on #4227 because
the same PR edited it (section 1, C2); the forwarder now survives a refused topic silently, so a refused
topic had to become a failure (S5); an admin-merge handler for stuck queue PRs exists and is removed (S4).

Not taken: making the change-control audit a node now (that repository audits settings and is not a
runtime; its new rule is written as a pure function so it can move later); treating the ruleset change as
a design primitive (it is a GitHub setting, kept as decision D1 with the code-side inventory as the
mechanism).
