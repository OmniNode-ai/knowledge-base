---
type: plan
status: active
date: "2026-09-27"
title: "PR landing workflow, revision 1: the state machine and safety properties after model checking"
topics: [pr-lifecycle, change-control, merge, workflow, fsm, formal-methods, tla-plus, determinism]
refs:
  - plans/2026-09-26-pr-landing-workflow-plan.md
---

# PR landing workflow, revision 1: the state machine and safety properties after model checking

state_as_of: 2026-09-27T03:30:00Z

**What this is.** A revision of sections 5.1 and 5.2 of [the PR landing workflow plan](2026-09-26-pr-landing-workflow-plan.md). Plans in this repository are frozen records, so that plan stays as written. This file replaces its section 5.1 (the state machine) and its section 5.2 (the safety properties). Every other section of that plan still holds. Where the two disagree on the state machine or the properties, this revision wins.

**Why.** Wave 1 task T1 of that plan built a TLA+ model of section 5.1 and checked it with TLC. Its design-review verdict was **changes required**. Section 5.1 as written breaks P1, P3 and P4, and the liveness property P6. After the ten changes below, TLC finds no violation. Every change here comes from the model, and each one names the property its counterexample breaks. Nothing else is changed. The model, its configurations, every TLC output and a condensed trace for each counterexample are held in the internal tracker against task T1.

**Status.** The wave 2 builds (T6 onward) start only after this revision has been reviewed. Wave 1 task T2 owns the frozen transition table, so it takes these changes by a contract version bump, following the rule in section 5.3 of the plan.

## 1. What the model checked

The model is keyed by PR, with two PRs on one ticket and batch companion mode on. It covers:

- two ingress sources: I1 snapshots (open, push, ready or draft, hold, reopen), and I2 plus I3 merged, so every merge arrives twice;
- delivery in any order, plus a budget of duplicate deliveries;
- the `state_io` row, written under compare-and-set with retry, holding an in-row outbox that a dispatcher drains one effect at a time;
- the per-ticket companion lease, held by the producer from its read to its write;
- the completion-bound timer, the arm gate, and a re-run budget of one per (head, check);
- GitHub, which merges only an armed, green PR. The workflow has no merge action.

The reducer in the model is a pure function of (row, observation), with no clock and no language model.

| Run | Scope | Result | Distinct states |
|--|--|--|--|
| per PR, every feature | one PR; another PR on the ticket may mint or merge the companion at any time | no violation of the seven invariants | 60,350,755 |
| two PRs, duplicates on | the companion slice, timer off | no violation | 56,257,011 |
| two PRs, duplicates off | the companion slice, timer off | no violation | 7,852,404 |
| two workers | real concurrent workers under compare-and-set instead of atomic delivery | no violation | 66,959,760 |
| at-least-once outbox | the outbox may re-send after a crash, effects deduplicate | no violation | 46,767,663 |
| reopen | reopen allowed, P4 stated per episode | no violation | 9,553,884 |
| liveness | P6 under weak fairness, timer off | no violation | 73,228 and 819,481 |
| head-match drop rule removed | the mutant the plan asked for (T1 AC2) | **P1 violated** at depth 11 | 217,199 |

The seven invariants are TypeOK, P1, P1arm (P1 read at a settled row, section 3), P2, P3, P4 and P5.

**Limits of the claim.**

- The two-PR run with every feature on (duplicates and the timer together) was stopped at 62.9 million distinct states with no violation. It is not exhaustive.
- The two-PR runs use the companion slice, which is exact for P3. P1, P2 and P4 are per-PR properties. They rest on the per-PR run, where a second PR's effect on the shared companion is over-approximated.
- One effect is in flight per PR. The duplicate budget and the timer budget are one each.
- P6 was checked as eventual, at one and two ingress events. The bounded form in section 4 ("within one observation and one effect round trip") was not checked.

The head-match drop rule is load-bearing. Without it, a green verdict read for the old head arrives after a push, moves the row to READY and arms the new head, whose checks were never read.

## 2. The ten changes

| # | Change to section 5.1 | Counterexample without it | Property broken |
|--|--|--|--|
| F1 | "pushed (new head)" means **newer** by a per-PR ordering key, not just a different `head_sha`. `ModelPrLandingObservation` carries that key. The key is the source sequence, or, where a source has none, the orchestrator re-reads the PR when a head arrives out of order. | A reordered old push takes the row back to the old head. A later stale snapshot then overwrites the draft flag, and a draft head is armed. | P1 |
| F2 | A same-head snapshot (draft, ready, hold) applies only when it is newer by that key. The head-match rule does not order two snapshots of the same head. | An older ready snapshot of the same head, delivered after a newer draft snapshot, takes the row out of PARKED, and the draft head is armed. | P1 |
| F3 | A draft or hold at the row's head moves COMPANION_PENDING, COMPANION_OPEN, CHECKS_PENDING and READY to PARKED, disarming if armed. In NEEDS_AGENT it disarms and the row stays put. A green verdict on a draft or held row goes to PARKED, not to a READY whose arm is withheld. | The row is armed at READY, the PR is converted to draft, and the arm stays on GitHub. Separately, a READY row with a withheld arm never leaves READY after the hold lifts. | P1 (settled form) and P6 |
| F4 | The row records the companion command in flight: `companion.status` gains `pending`, plus a `command_id`. An evaluation made while a command is in flight issues nothing. | A push during COMPANION_PENDING issues a second derive. This is the plan as written. | P3 |
| F5 | Companion outcomes correlate by `command_id`, not by `head_sha`. An outcome for any other command is dropped. "Companion merged" is also a transition from COMPANION_PENDING to CHECKS_PENDING. | The companion merges through the other PR on the ticket while this PR's derive is in flight, and the row stays in COMPANION_PENDING forever. Exempting outcomes from the head rule without correlating them also fails: a stale DECLINED clears the in-flight marker and a second derive goes out. | P6 and P3 |
| F6 | A disarm added to the outbox removes an unsent arm, and an arm removes an unsent disarm. Or, instead, the outbox is FIFO per row. | The disarm is dispatched before the arm it should have cancelled, and the draft PR ends armed. | P1 (settled form) |
| F7 | Head-check verdicts carry each check's run attempt. A re-run records the attempt it started. A result older than that attempt counts as pending (read again), not as a second failure. When the companion merges, the workflow reads the head checks first, then re-runs only what the verdict names red. | The re-read beats the re-run, sees the old `timed_out` result, spends the budget, and sends a PR that goes green to NEEDS_AGENT. | P6 |
| F8 | The dispatcher removes an outbox entry through the same `state_io` compare-and-set the reducer uses. | Without compare-and-set, a stale reducer write brings back a derive that was already dispatched. | P3 |
| F9 | The outbox is at-least-once, so effects and consumers deduplicate: a re-run on (head, check, attempt), agent-needed on (head, reason), and a terminal on (PR, episode). | The dispatcher crashes after emitting a terminal and before removing it, and the re-send emits a second terminal. With deduplication the same run passes. | P4 |
| F10 | "Exactly one terminal per PR" is false once a CLOSED PR can be reopened. P4 is restated per (PR, open episode), and merged is final. The row carries an `episode` counter that reopen increments. Terminal events carry the row `seq`, because the outbox can emit an older episode's closed after a newer merged. | Closed, reopened, closed: two terminals for one PR. | P4 |

The per-ticket companion lease that P3 already names is required. Without it, two PRs on one ticket each create a companion (P3). That is a confirmation of the plan, not a change to it.

## 3. Revised section 5.1: the state machine (frozen for wave 1)

Key: `(repository, pr_number)`. The row carries:

- `head_sha`, `base_ref`, `ticket_ids`, `draft`, `held`;
- `source_seq`: the ordering key of the newest snapshot the row applied (F1, F2);
- `companion`: `occ_pr`, `status` (none, **pending**, open, conflicting, merged, closed or declined) and the `command_id` of the command in flight (F4, F5);
- `stamp_present`, `merge_state`, `armed` (with method auto_merge or queue);
- `expected_attempt` per check: the run attempt the last re-run started (F7);
- `episode`: the open-episode counter, incremented on reopen (F10);
- budgets: derive 2, regenerate 3, one re-run per check per head, update-branch 2 per head;
- the in-row outbox (F6, F8, F9), `seq` and `entered_state_at`.

| State | Meaning | Leaves on |
|--|--|--|
| OBSERVED | a new head or first sight; the reducer evaluates at once | evaluation |
| PARKED | draft, held (label or hold marker), no ticket token, or a base branch the workflow does not serve | ready_for_review, hold lifted, body edited, new head (each newer by the ordering key) |
| COMPANION_PENDING | a derive or regenerate command is in flight, recorded by `command_id` | the outcome of that command, companion merged (F5), draft or hold (F3) |
| COMPANION_OPEN | companion open, stamp on the product body, companion armed | companion merged, conflicting, or closed unmerged; draft or hold (F3) |
| CHECKS_PENDING | companion merged or not required; waiting for check results | head check verdict; draft or hold (F3) |
| READY | every required context green, not held, not draft | arm or enqueue confirmed; draft or hold (F3) |
| ARMED | auto-merge armed or enqueued | merged, disarmed, hold applied, new head |
| NEEDS_AGENT | real red, declined companion, budget spent or stalled; one agent-needed event per (head, reason) | new head, or hold lifted with a manual re-evaluation. A draft or hold here disarms without leaving (F3) |
| MERGED | terminal, final | none |
| CLOSED | terminal for this episode | reopened, back to OBSERVED in a new episode (F10) |

Rows marked in the last column are new or changed by this revision.

| From | Observation | To | Intents | Change |
|--|--|--|--|--|
| any non-terminal | pushed: a head other than `head_sha`, newer by the ordering key | OBSERVED | none | F1 |
| any non-terminal | a snapshot at the row's head that is not newer by the ordering key | unchanged | none (dropped) | F2 |
| OBSERVED | evaluation: draft, held or no ticket | PARKED | disarm if armed | |
| OBSERVED | evaluation: companion required, none bound, none in flight | COMPANION_PENDING | companion.derive; the row records status pending and the `command_id` | F4 |
| OBSERVED | evaluation: a companion command is in flight | COMPANION_PENDING | none | F4 |
| OBSERVED | evaluation: companion bound and open | COMPANION_OPEN | companion.verify (stamp and arm) | |
| OBSERVED | evaluation: companion merged, or not required | CHECKS_PENDING | github.read_head_checks | |
| COMPANION_PENDING | outcome MINTED (occ_pr, stamped, armed) for the command in flight | COMPANION_OPEN | github.arm(occ_pr) if not armed; companion.verify if not stamped | F5 |
| COMPANION_PENDING | outcome DECLINED (reason) for the command in flight | NEEDS_AGENT | agent_needed(companion_declined, reason) | F5 |
| COMPANION_PENDING | outcome ERROR for the command in flight, budget left | COMPANION_PENDING | companion.derive (retry), recorded under a new `command_id` | F4, F5 |
| COMPANION_PENDING | outcome ERROR for the command in flight, budget spent | NEEDS_AGENT | agent_needed(companion_error) | F5 |
| COMPANION_PENDING | an outcome for any other `command_id` | unchanged | none (dropped) | F5 |
| COMPANION_PENDING | companion merged | CHECKS_PENDING | github.read_head_checks | F5, F7 |
| COMPANION_OPEN | companion conflicting, budget left | COMPANION_PENDING | companion.regenerate, recorded by `command_id` | F4 |
| COMPANION_OPEN | companion closed unmerged | COMPANION_PENDING | companion.derive, recorded by `command_id` | F4 |
| COMPANION_OPEN | companion merged | CHECKS_PENDING | github.read_head_checks; a re-run follows only for what that verdict names red | F7 |
| COMPANION_PENDING, COMPANION_OPEN, CHECKS_PENDING, READY | draft or hold at the row's head, newer by the ordering key | PARKED | disarm if armed | F3 |
| NEEDS_AGENT | draft or hold at the row's head, newer by the ordering key | NEEDS_AGENT | disarm if armed | F3 |
| CHECKS_PENDING | a verdict naming a check result older than that check's `expected_attempt` | CHECKS_PENDING | github.read_head_checks | F7 |
| CHECKS_PENDING | verdict green; not draft, not held | READY | arm gate, then github.arm or github.enqueue by the repo's live merge policy | |
| CHECKS_PENDING | verdict green; draft or held | PARKED | none | F3 |
| CHECKS_PENDING | verdict change_control_stale, budget left | CHECKS_PENDING | github.rerun(named runs); the row records each run's `expected_attempt` | F7 |
| CHECKS_PENDING | verdict timed_out, runner_infra or cancelled, budget left | CHECKS_PENDING | github.rerun(named runs); the row records each run's `expected_attempt` | F7 |
| CHECKS_PENDING | verdict stale_caller_pin or behind_required | CHECKS_PENDING | github.update_branch | |
| CHECKS_PENDING | verdict product_failed, or any budget spent | NEEDS_AGENT | agent_needed(real_red, checks) | |
| CHECKS_PENDING | verdict pending | CHECKS_PENDING | github.read_head_checks after the state's poll interval | |
| READY | armed confirmed | ARMED | none | |
| ARMED | disarmed, or hold applied | PARKED or CHECKS_PENDING | disarm on hold | |
| any non-terminal | merged | MERGED | terminal pr-landing-merged, keyed (PR, episode), carrying `seq` | F9, F10 |
| any non-terminal | closed, newer by the ordering key | CLOSED | terminal pr-landing-closed, keyed (PR, episode), carrying `seq` | F2, F9, F10 |
| CLOSED | reopened, newer by the ordering key | OBSERVED, `episode` + 1 | none | F10 |
| any non-terminal | completion bound expired | NEEDS_AGENT | agent_needed(stalled, state) | |

**The head-match drop rule.** An observation for a head other than the row's `head_sha` is dropped. The exceptions are merged and closed, a companion outcome (correlated by `command_id`, F5) and companion merged (a ticket fact with no head). A push is not an exception: it is the "pushed" row, and it applies only when newer by the ordering key (F1).

**The outbox.** Intents go to the in-row outbox in the same compare-and-set that writes the row. A disarm removes an unsent arm, and an arm removes an unsent disarm, unless the outbox is FIFO per row (F6). The dispatcher removes an entry through the same compare-and-set (F8). Delivery is at-least-once, so every effect and every consumer deduplicates on the keys in F9.

`stale_caller_pin` is the class where a re-run replays the old reusable-workflow pin, so its remedy is update-branch and never re-run.

## 4. Revised section 5.2: safety properties (the model checks these; the reducer tests assert them)

- **P1** Never arm, enqueue or re-arm a PR that is draft or held at the observed head. The model checks P1 in two forms: at the step that issues an arm, and at a settled row, where GitHub must not be left armed on a head the orchestrator knows to be draft or held (P1arm). The counterexamples to F3 and F6 break the settled form.
- **P2** Never re-run a check the classifier calls product_failed; at most one re-run per (head, check).
- **P3** At most one companion command in flight per product PR, and at most one open companion per ticket when the batch switch is on (the per-ticket lease).
- **P4** Exactly one terminal event per (PR, open episode), and none after merged; at most one agent-needed event per (head, reason). (Changed by F10. A reopened PR starts a new episode, so a PR that is closed, reopened and merged emits two terminals, one per episode.)
- **P5** The workflow never merges. GitHub merges an armed or enqueued PR when the required contexts pass. No gate, ruleset or required check changes.
- **P6** Liveness: a PR that is not held, not draft and has green required contexts reaches ARMED within one observation and one effect round trip. (The model checked the eventual form only.)

## 5. What this changes downstream

- **T2** bumps the contract version of its frozen transition table and the `state_machine` block to these rows, and adds the ordering key to `ModelPrLandingObservation` (F1, F2), `command_id` and the pending status to the companion fields (F4, F5), the episode counter (F10), and the run attempt to the verdict the reducer reads (F7).
- **T3**'s verdict carries each check's run attempt (F7).
- **T6** asserts P4 per episode.
- **T7** implements the outbox rules (F6, F8, F9) and the consumer deduplication keys.
- **T10**'s outcome event carries the `command_id` of the command it answers (F5).
