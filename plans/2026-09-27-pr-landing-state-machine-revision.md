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

state_as_of: 2026-09-27T06:10:00Z

**What this is.** A revision of sections 5.1 and 5.2 of [the PR landing workflow plan](2026-09-26-pr-landing-workflow-plan.md). Plans in this repository are frozen records, so that plan stays as written. This file replaces its section 5.1 (the state machine) and its section 5.2 (the safety properties), and it names the producer of every input the state machine reads (section 6). Every other section of that plan still holds. Where the two disagree on the state machine, the properties or the ingress, this revision wins.

**Why.** Wave 1 task T1 of that plan built a TLA+ model of section 5.1 and checked it with TLC. Its design-review verdict was **changes required**. Section 5.1 as written breaks P1, P3 and P4, and the liveness property P6. After the ten changes F1 to F10 (section 2), TLC found no violation. A design review of that first version of this revision then found four more cases the model had not checked: a companion outcome that arrives while the row is parked, a completion bound that escalates intentionally parked PRs, a classifier verdict with no transition, and model inputs with no named producer. It also asked that disarming on a new head cover an already armed PR, an unsent arm and an arm already in flight. The model was extended for each case, and the changes R1 to R4 (section 2a) and the reopen rules G5 came out of that extension. Every change here comes from the model, and each one names the property its counterexample breaks. The model, its configurations, every TLC output and a condensed trace for each counterexample are held in the internal tracker against task T1.

**Status.** The wave 2 builds (T6 onward) start only after this revision has been reviewed. Wave 1 task T2 owns the frozen transition table, so it takes these changes by a contract version bump, following the rule in section 5.3 of the plan.

## 1. What the model checked

The model is keyed by PR, with two PRs on one ticket and batch companion mode on. It covers:

- the inputs the reducer reads: snapshots of the PR (head, draft, hold, open or closed), merged, companion outcomes, companion merged, head-check verdicts, the arm confirmation and the completion-bound expiry. Section 6 names the producer of each one in the deployed system, or the read that stands in for it;
- delivery in any order, plus a budget of duplicate deliveries;
- the `state_io` row, written under compare-and-set with retry, holding an in-row outbox that a dispatcher drains one effect at a time;
- an arm request in flight between the dispatcher's send and GitHub's answer, and GitHub's check of the arm's expected head at the moment it answers;
- the per-ticket companion lease, held by the producer from its read to its write;
- the completion-bound timer, the arm gate, and a re-run budget of one per (head, check);
- GitHub, which merges only an armed, green PR, and keeps an arm across a push. The workflow has no merge action.

The reducer in the model is a pure function of (row, observation), with no clock and no language model.

Runs of the first version of this revision (changes F1 to F10):

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

Runs of this revision (F1 to F10, R1 to R4 and G5), at the same bounds as the per-PR run above: one PR, a foreign PR on the same ticket, two ingress events, heads up to 2, one duplicate delivery and one bound expiry:

| Run | Scope | Result | Distinct states |
|--|--|--|--|
| per PR, every feature | the per-PR run above, plus an arm in flight, the one-in-flight rule and a bound per state entry | no violation of the twelve invariants | 314,956,682 (depth 43) |
| reopen | reopen allowed, three ingress events, no duplicates, timer off, P4 per episode | no violation of the eleven invariants that apply | 32,521,954 (depth 45) |
| liveness | P6 under weak fairness, with a bound that expires only on a real stall | no violation | 417,135 at one ingress event, 4,457,448 at two |
| liveness, PARKED under the bound | R2c alone, R2a removed | no violation | 457,092 |

The seven invariants are TypeOK, P1, P1arm (P1 read at a settled row, section 4), P2, P3, P4 and P5. This revision adds P7 (no silent stall), TermKind (a merged PR never rests in CLOSED), CompTracked (R1), TimerFresh (R2) and P1new (R4), defined in section 4.

**Every new rule was mutation-tested.** Each run below removes one rule from the fixed model, or restores the text of the first version of this revision, and TLC must find a counterexample:

| Rule removed, or first-version text restored | Result | Counterexample |
|--|--|--|
| R1: an outcome is accepted only in COMPANION_PENDING | **CompTracked violated**; P7 violated in a separate run | 8 states: derive, draft, MINTED while PARKED is dropped, the row keeps a completed command in flight. The P7 run (10 states) goes on to ready_for_review and a COMPANION_PENDING row with nothing in flight |
| R2b: the expiry is matched on the state name only | **TimerFresh violated** | 8 states: bound set in COMPANION_PENDING, draft, ready, the old expiry escalates the new entry |
| R2a and R2c together: PARKED under the bound, no recovery | **P6 violated** | 13 states: a parked draft stalls to NEEDS_AGENT, turns ready and green, and is never armed |
| R2a alone, or R2c alone | no violation | each one on its own closes the P6 path above; both are kept |
| R3: no row for change_control_open (dropped) | **P7 violated** | 8 states |
| R3: the row goes back to COMPANION_OPEN | **P7 violated** | 8 states: it waits for a companion merged it already consumed |
| R3 reachability: the verdict reaches a CHECKS_PENDING row | reached (the witness) | 7 states, through the classifier's lagging companion fact. Without that lag the extension found it unreachable in 131,294,617 states |
| R4: the plan as written, the arm is kept on a new head | **P1new violated** | 11 states |
| R4: the armed flag is cleared without a disarm | **P1new violated** | 11 states |
| R4: no one-in-flight rule | **P1arm violated** | 13 states: an arm in flight lands after the disarm a draft issued |
| R4: no outbox rule (F6) | **P1arm violated** | 13 states |
| R4: neither the outbox rule nor the expected head | **P1new violated** | 14 states: an unsent arm for the old head goes out after the disarm |
| R4: no new-head rule out of CLOSED (reopen configuration) | **P1new violated** | 14 states: a stale closed, a reopen and a push leave the old arm on the new head |
| R4: the expected head alone | no violation found; stopped at 109,136,436 distinct states | not shown load-bearing while the outbox rule and the one-in-flight rule hold. Kept as defence in depth, because GitHub checks it at the moment it answers |
| G5: each of the five reopen rules, one at a time (extension runs) | **P7 violated** in all five | 10 to 19 states |

**Limits of the claim.**

- The two-PR run with every feature on (duplicates and the timer together) was stopped at 62.9 million distinct states with no violation. It is not exhaustive. The runs of this revision are per PR, with a foreign PR on the ticket.
- The two-PR runs use the companion slice, which is exact for P3. P1, P2 and P4 are per-PR properties. They rest on the per-PR run, where a second PR's effect on the shared companion is over-approximated.
- One effect is in flight per PR, and that is now a requirement (R4), not only a bound of the model. The duplicate budget and the timer budget are one each.
- P6 was checked as eventual, at one and two ingress events. The bounded form in section 4 ("within one observation and one effect round trip") was not checked.
- The model's reducer sees snapshots. Section 6 is what makes those snapshots exist in deployment. A property in section 4 holds in deployment only once the producer section 6 names for each input it relies on is running.
- The model does not contain the ERROR companion outcome, the regenerate command, or a row that reaches CHECKS_PENDING with no companion required. The rows for them below follow the modelled rows but are not checked.
- The design review read the documents and the reported proof limits. It did not re-run TLC.

The head-match drop rule is load-bearing. Without it, a green verdict read for the old head arrives after a push, moves the row to READY and arms the new head, whose checks were never read.

## 2. The ten changes

| # | Change to section 5.1 | Counterexample without it | Property broken |
|--|--|--|--|
| F1 | "pushed (new head)" means **newer** by a per-PR ordering key, not just a different `head_sha`. `ModelPrLandingObservation` carries that key. Section 6 defines the key: the orchestrator's own read sequence for the PR. | A reordered old push takes the row back to the old head. A later stale snapshot then overwrites the draft flag, and a draft head is armed. | P1 |
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

## 2a. Changes from the design review

| # | Change to section 5.1 | Counterexample without it | Property broken |
|--|--|--|--|
| R1 | A companion outcome for the command in flight is **recorded in every non-terminal state** (and in CLOSED): it sets `companion.status` and clears `command_id` whatever the control state. Only COMPANION_PENDING also changes state on it. A held or draft row stays PARKED, and when it leaves PARKED the evaluation reads the recorded status. | Derive starts, a hold is applied (PARKED), MINTED arrives while parked and is dropped, the hold lifts. The row still shows a command in flight that has already completed, re-enters COMPANION_PENDING, issues nothing, and waits forever. | CompTracked, and P7 |
| R2a | The completion bound covers OBSERVED, COMPANION_PENDING, COMPANION_OPEN, CHECKS_PENDING, READY, ARMED and NEEDS_AGENT. It **does not cover PARKED**: a draft, a hold, no ticket token or an unserved base branch is an intentional wait, not a stall. | An ordinary draft is parked, its bound expires, the row goes to NEEDS_AGENT, and the ready_for_review that follows has no transition out. The PR goes green and is never armed. | P6 |
| R2b | Every bound is **bound to the state entry it was set for**. The row carries `state_entry_generation`, incremented whenever the state, the head or the episode changes. The bound's expiry carries (`episode`, `state_entry_generation`) and is dropped unless both equal the row's current values. Matching on the state name alone is not enough. | A bound is set in COMPANION_PENDING. The PR is converted to draft (PARKED) and back to ready, and the row re-enters COMPANION_PENDING at the same head. The old expiry arrives, matches the state name, and sends the new entry to NEEDS_AGENT before its own bound. | TimerFresh |
| R2c | In NEEDS_AGENT, a ready_for_review or a hold lifted (a snapshot at the row's head, newer by the ordering key, that clears a draft or hold the row had recorded) **re-evaluates** the row. Agent-needed stays deduplicated per (head, reason), so a re-evaluation that finds the same fault emits nothing new. | With PARKED under the bound (the first version of this revision), the stalled draft of R2a stays in NEEDS_AGENT after ready_for_review. R2a alone removes that path; R2c keeps NEEDS_AGENT recoverable when an agent parks a PR and then releases it. | P6 |
| R3 | CHECKS_PENDING has a row for the verdict **change_control_open**. The row's companion fact wins over the classifier's: the companion leg recorded companion merged, so a red change-control check reported as open means the classifier's companion fact (read from the mirror) lags. The row stays in CHECKS_PENDING and reads the head checks again after the poll interval. That next verdict resumes progress: change_control_stale (re-run the named runs, F7) or green (arm). If the row's companion status is not merged, the row returns to OBSERVED and the evaluation reconciles the companion: it waits on an open companion, or derives one within the derive budget. | With no row, the verdict is dropped and nothing is left in flight: the PR waits until its bound. With a row that goes back to COMPANION_OPEN, the row waits for a companion merged that was already consumed. | P7 |
| R4 | A pushed new head **disarms if armed**, where armed means an arm queued in the outbox, sent and not yet answered, or confirmed. Three rules together cover the three cases. An arm already confirmed on GitHub: the disarm intent. An arm unsent in the outbox: the disarm removes it (F6). An arm in flight: the dispatcher sends no second effect for a PR while one is in flight, so the disarm goes out after GitHub has answered the arm, and the arm carries the expected head, so GitHub refuses it once the head has moved. The row's `armed` flag is set when the arm intent is written, not when it is confirmed. The rule also applies when a newer snapshot with a new head takes a CLOSED row back to OBSERVED: the reopen run found a closed that was reordered before a reopen and a push, and the row left CLOSED on the new head with the old arm still on GitHub. | The plan as written keeps GitHub's arm on the new head, whose checks the arm gate never judged. Clearing the row's armed flag without a disarm does the same. Without the one-in-flight rule, an arm in flight lands after the disarm that a draft or hold issued, and the draft head ends armed. Without both the outbox rule and the expected head, an unsent arm for the old head goes out after the disarm. Without the rule out of CLOSED, a stale closed followed by a reopen and a push leaves the old arm on the new head. | P1new, and P1arm |

**The residual window of R4.** GitHub keeps an arm across a push by anyone with write access. Between the push and the moment the disarm is sent, GitHub can merge the new head if its required checks pass before the orchestrator has observed the push. The model shows this: with R4 in place, a merge-step form of P1new is still violated by a 12-state trace in which GitHub merges the new head before the row has seen the push. The window cannot be closed without a required check that the workflow owns, and P5 rules that out. Inside the window the merge still needs every required check green on the new head, and a draft cannot merge. P1new is therefore stated for a settled row: once the row has applied the new head and nothing it queued or sent is outstanding.

**The reopen rules (G5).** The same extension checked reopen with the ordering key, and five rules are needed so that a reopened PR neither stalls nor emits a second terminal in one episode. A reopened snapshot newer by the key re-evaluates the row from any non-terminal state, because its closed may have been reordered after it and dropped. A CLOSED row still records companion outcomes and companion merged, staying CLOSED, so a reopen evaluates the companion as it is. In CLOSED, any snapshot newer than the row reopens it, because the reader only sees an open PR as open. In CLOSED, a newer closed advances the ordering key and emits no second terminal. In CLOSED, merged (possible only after a reopen) moves the row to MERGED in a new episode with its own terminal. Removing any one of the five produces a P7 counterexample (a stall) in the reopen configuration.

## 3. Revised section 5.1: the state machine (frozen for wave 1)

Key: `(repository, pr_number)`. The row carries:

- `head_sha`, `base_ref`, `ticket_ids`, `draft`, `held`;
- `source_seq`: the ordering key of the newest snapshot the row applied (F1, F2), the orchestrator's read sequence for the PR (section 6);
- `companion`: `occ_pr`, `status` (none, **pending**, open, conflicting, merged, closed or declined) and the `command_id` of the command in flight (F4, F5). The status is written by companion outcomes in every non-terminal state (R1);
- `stamp_present`, `merge_state`, `armed` (with method auto_merge or queue; set when the arm intent is written, R4);
- `expected_attempt` per check: the run attempt the last re-run started (F7);
- `episode`: the open-episode counter, incremented on reopen (F10);
- `state_entry_generation`: incremented whenever the state, `head_sha` or `episode` changes (R2b);
- budgets: derive 2, regenerate 3, one re-run per check per head, update-branch 2 per head;
- the in-row outbox (F6, F8, F9), `seq` and `entered_state_at`.

| State | Meaning | Leaves on |
|--|--|--|
| OBSERVED | a new head or first sight; the reducer evaluates at once | evaluation |
| PARKED | draft, held (label or hold marker), no ticket token, or a base branch the workflow does not serve. No completion bound (R2a) | ready_for_review, hold lifted, title edited, new head (each newer by the ordering key) |
| COMPANION_PENDING | a derive or regenerate command is in flight, recorded by `command_id` | the outcome of that command, companion merged (F5), draft or hold (F3) |
| COMPANION_OPEN | companion open, stamp on the product body, companion armed | companion merged, conflicting, or closed unmerged; draft or hold (F3) |
| CHECKS_PENDING | companion merged or not required; waiting for check results | head check verdict; draft or hold (F3) |
| READY | every required context green, not held, not draft | arm or enqueue confirmed; draft or hold (F3) |
| ARMED | auto-merge armed or enqueued | merged, disarmed, hold applied, new head |
| NEEDS_AGENT | real red, declined companion, budget spent or stalled; one agent-needed event per (head, reason) | new head; ready_for_review or hold lifted re-evaluates (R2c). A draft or hold here disarms without leaving (F3) |
| MERGED | terminal, final | none |
| CLOSED | terminal for this episode | reopened or any newer snapshot, back to OBSERVED in a new episode (F10, G5) |

Rows marked in the last column are new or changed by this revision.

| From | Observation | To | Intents | Change |
|--|--|--|--|--|
| any non-terminal | pushed: a head other than `head_sha`, newer by the ordering key | OBSERVED | disarm if armed (an unsent arm is removed, an arm in flight is answered first) | F1, R4 |
| any non-terminal | a snapshot at the row's head that is not newer by the ordering key | unchanged | none (dropped) | F2 |
| any non-terminal | reopened, at the row's head and newer by the ordering key | OBSERVED | none (re-evaluate) | G5 |
| OBSERVED | evaluation: draft, held or no ticket | PARKED | disarm if armed | |
| OBSERVED | evaluation: companion required, status none or declined, none in flight | COMPANION_PENDING | companion.derive; the row records status pending and the `command_id` | F4 |
| OBSERVED | evaluation: a companion command is in flight (status pending) | COMPANION_PENDING | none | F4 |
| OBSERVED | evaluation: companion bound and open | COMPANION_OPEN | companion.verify (stamp and arm) | |
| OBSERVED | evaluation: companion merged, or not required | CHECKS_PENDING | github.read_head_checks | |
| COMPANION_PENDING | outcome MINTED (occ_pr, stamped, armed) for the command in flight | COMPANION_OPEN | github.arm(occ_pr) if not armed; companion.verify if not stamped | F5 |
| COMPANION_PENDING | outcome DECLINED (reason) for the command in flight | NEEDS_AGENT | agent_needed(companion_declined, reason) | F5 |
| COMPANION_PENDING | outcome ERROR for the command in flight, budget left | COMPANION_PENDING | companion.derive (retry), recorded under a new `command_id` | F4, F5 |
| COMPANION_PENDING | outcome ERROR for the command in flight, budget spent | NEEDS_AGENT | agent_needed(companion_error) | F5 |
| PARKED, COMPANION_OPEN, CHECKS_PENDING, READY, ARMED, NEEDS_AGENT, CLOSED | outcome for the command in flight | unchanged | none; the row records the outcome in `companion` (MINTED: open; DECLINED: declined; ERROR: none) and clears `command_id` | R1 |
| any non-terminal, CLOSED | an outcome for any other `command_id` | unchanged | none (dropped) | F5 |
| COMPANION_PENDING | companion merged | CHECKS_PENDING | github.read_head_checks | F5, F7 |
| PARKED, CHECKS_PENDING, READY, ARMED, NEEDS_AGENT, CLOSED | companion merged | unchanged | none; the row records companion status merged | R1, G5 |
| COMPANION_OPEN | companion conflicting, budget left | COMPANION_PENDING | companion.regenerate, recorded by `command_id` | F4 |
| COMPANION_OPEN | companion closed unmerged | COMPANION_PENDING | companion.derive, recorded by `command_id` | F4 |
| COMPANION_OPEN | companion merged | CHECKS_PENDING | github.read_head_checks; a re-run follows only for what that verdict names red | F7 |
| COMPANION_PENDING, COMPANION_OPEN, CHECKS_PENDING, READY | draft or hold at the row's head, newer by the ordering key | PARKED | disarm if armed | F3 |
| PARKED | ready_for_review, hold lifted or title edited, at the row's head and newer by the ordering key, leaving it neither draft nor held | OBSERVED | none (re-evaluate; the evaluation reads the recorded companion status) | R1 |
| NEEDS_AGENT | draft or hold at the row's head, newer by the ordering key | NEEDS_AGENT | disarm if armed | F3 |
| NEEDS_AGENT | ready_for_review or hold lifted at the row's head, newer by the ordering key, clearing a recorded draft or hold | OBSERVED | none (re-evaluate) | R2c |
| CHECKS_PENDING | a verdict naming a check result older than that check's `expected_attempt` | CHECKS_PENDING | github.read_head_checks | F7 |
| CHECKS_PENDING | verdict green; not draft, not held | READY | arm gate, then github.arm or github.enqueue by the repo's live merge policy, carrying the expected head; the row sets `armed` | R4 |
| CHECKS_PENDING | verdict green; draft or held | PARKED | none | F3 |
| CHECKS_PENDING | verdict change_control_open; companion status merged | CHECKS_PENDING | github.read_head_checks after the state's poll interval | R3 |
| CHECKS_PENDING | verdict change_control_open; companion status not merged | OBSERVED | none (re-evaluate: wait on the open companion, or derive) | R3 |
| CHECKS_PENDING | verdict change_control_stale, budget left | CHECKS_PENDING | github.rerun(named runs); the row records each run's `expected_attempt` | F7 |
| CHECKS_PENDING | verdict timed_out, runner_infra or cancelled, budget left | CHECKS_PENDING | github.rerun(named runs); the row records each run's `expected_attempt` | F7 |
| CHECKS_PENDING | verdict stale_caller_pin or behind_required | CHECKS_PENDING | github.update_branch | |
| CHECKS_PENDING | verdict product_failed, or any budget spent | NEEDS_AGENT | agent_needed(real_red, checks) | |
| CHECKS_PENDING | verdict pending | CHECKS_PENDING | github.read_head_checks after the state's poll interval | |
| READY | armed confirmed | ARMED | none | |
| ARMED | disarmed, or hold applied | PARKED or CHECKS_PENDING | disarm on hold | |
| any non-terminal | merged | MERGED | terminal pr-landing-merged, keyed (PR, episode), carrying `seq` | F9, F10 |
| any non-terminal | closed, newer by the ordering key | CLOSED | terminal pr-landing-closed, keyed (PR, episode), carrying `seq` | F2, F9, F10 |
| CLOSED | reopened, or any snapshot newer by the ordering key | OBSERVED, `episode` + 1 | disarm if armed when the snapshot's head differs from `head_sha` (the new-head rule, R4) | F10, G5, R4 |
| CLOSED | closed, newer by the ordering key | CLOSED | none; the row advances `source_seq` | G5 |
| CLOSED | merged | MERGED, `episode` + 1 | terminal pr-landing-merged for the new episode | G5 |
| OBSERVED, COMPANION_PENDING, COMPANION_OPEN, CHECKS_PENDING, READY, ARMED, NEEDS_AGENT | completion bound expired, carrying the (`episode`, `state_entry_generation`) it was set for, both equal to the row's | NEEDS_AGENT | agent_needed(stalled, state) | R2a, R2b |
| any | completion bound expired for another episode or state entry, or in PARKED | unchanged | none (dropped) | R2a, R2b |

**The head-match drop rule.** An observation for a head other than the row's `head_sha` is dropped. The exceptions are merged and closed, a companion outcome (correlated by `command_id`, F5), companion merged (a ticket fact with no head) and the completion bound (correlated by episode and state entry, R2b). A push is not an exception: it is the "pushed" row, and it applies only when newer by the ordering key (F1).

**The outbox.** Intents go to the in-row outbox in the same compare-and-set that writes the row. A disarm removes an unsent arm, and an arm removes an unsent disarm, unless the outbox is FIFO per row (F6). The dispatcher removes an entry through the same compare-and-set (F8). The dispatcher sends no effect for a PR while another effect for that PR is in flight, and an arm carries the head it was judged for (R4). Delivery is at-least-once, so every effect and every consumer deduplicates on the keys in F9.

`stale_caller_pin` is the class where a re-run replays the old reusable-workflow pin, so its remedy is update-branch and never re-run.

## 4. Revised section 5.2: safety properties (the model checks these; the reducer tests assert them)

- **P1** Never arm, enqueue or re-arm a PR that is draft or held at the observed head. The model checks P1 in two forms: at the step that issues an arm, and at a settled row, where GitHub must not be left armed on a head the orchestrator knows to be draft or held (P1arm). A row is settled when its outbox is empty and no effect for it is in flight. The counterexamples to F3, F6 and the one-in-flight rule of R4 break the settled form.
- **P1new** (R4) Once the row has applied the PR's current head and nothing it queued or sent is outstanding for it (no unsent disarm, no arm in flight), GitHub is armed on that head only if the workflow armed that head or has an arm for it queued. The window before that point is described under R4.
- **P2** Never re-run a check the classifier calls product_failed; at most one re-run per (head, check).
- **P3** At most one companion command in flight per product PR, and at most one open companion per ticket when the batch switch is on (the per-ticket lease).
- **CompTracked** (R1) A row whose companion status is pending always has that command in flight: queued in the outbox, at the producer, or with its outcome undelivered. A completed command never stays pending.
- **P4** Exactly one terminal event per (PR, open episode), and none after merged; at most one agent-needed event per (head, reason). (Changed by F10. A reopened PR starts a new episode, so a PR that is closed, reopened and merged emits two terminals, one per episode.)
- **P5** The workflow never merges. GitHub merges an armed or enqueued PR when the required contexts pass. No gate, ruleset or required check changes.
- **P6** Liveness: a PR that is not held, not draft and has green required contexts reaches ARMED within one observation and one effect round trip. (The model checked the eventual form only.)
- **P7** No silent stall: a row in COMPANION_PENDING, COMPANION_OPEN, CHECKS_PENDING or READY always has something in flight that will move it (an outbox entry, an undelivered observation, a producer command, an arm in flight, or an open companion that can merge).
- **TermKind** A PR that GitHub merged never rests in CLOSED.
- **TimerFresh** (R2b) A completion-bound expiry is applied only to the state entry, and the episode, it was set for.

## 5. What this changes downstream

- **T2** bumps the contract version of its frozen transition table and the `state_machine` block to these rows, and adds the ordering key to `ModelPrLandingObservation` (F1, F2), `command_id` and the pending status to the companion fields (F4, F5), the episode counter (F10), `state_entry_generation` on the row and (`episode`, `state_entry_generation`) on the bound's expiry (R2b), and the run attempt to the verdict the reducer reads (F7). Its fixtures add a case for each counterexample in sections 2 and 2a.
- **T3**'s verdict carries each check's run attempt (F7), and its corpus keeps change_control_open (R3).
- **T4** adds the operation `read_pr_state`, a conditional read of head, draft, title, labels, state, merged and auto-merge state (section 6), and its arm and enqueue operations take the expected head (R4).
- **T6** asserts P4 per episode, and CompTracked, TimerFresh and P7 as reducer properties.
- **T7** implements the outbox rules (F6, F8, F9), one effect in flight per PR (R4), the completion bound per state entry (R2a, R2b), the reconciliation read of section 6, and the consumer deduplication keys.
- **T10**'s outcome event carries the `command_id` of the command it answers (F5).
- **T12** is the producer of companion merged, and of merged for every repository without an Actions producer (section 6).

## 6. Where each input comes from

The model assumes that each input reaches the reducer. This section names, for each one, what produces it in the code as it is today, what stands in until the planned producer exists, and which properties depend on it. Read against the code on 2026-09-27.

**The autobind command is a prompt, not a snapshot.** The ingress I1 publisher (`call-occ-autobind.yml`, calling `scripts/publish_occ_autobind_command.py`) sends `repo`, `pr_number`, `ticket_id`, `correlation_id`, `requested_at` and the batch flag. It carries no head sha (its docstring says the adapter re-resolves the head from GitHub), no draft or hold flag, no event action and no sequence. So the snapshots the model reads cannot come from I1 itself. The orchestrator produces them: on every I1 command, and on a reconciliation tick for every non-terminal row, it issues `github.read_pr_state` (a conditional request, so an unchanged PR costs no quota) and turns the answer into the snapshot observation. Reads for one PR are serialized by the one-in-flight rule (R4), so the orchestrator's read sequence for the PR is monotonic, and that sequence is the ordering key of F1 and F2. A read coalesces every change since the previous read. For the safety properties that is one of the behaviours the model already has (the intermediate snapshots are dropped as older by the key). For P6 it is enough that a read eventually follows the last change, which the tick guarantees.

| Input the model reads | Producer today | Stand-in until the producer exists | Properties that rely on it |
|--|--|--|--|
| opened | I1, `pull_request` `opened`, in the nine product repositories that carry `call-occ-autobind.yml` | none needed | P6 (the PR reaches the workflow at all) |
| pushed (new head) | I1, `synchronize` | none needed; `read_pr_state` supplies the head and the ordering key | F1, P1, P1new, R4 |
| reopened | I1, `reopened` | none needed | P4 per episode, G5 |
| ready_for_review | I1, `ready_for_review` | none needed | P6, R2c |
| converted to draft | **none**: `converted_to_draft` is not in I1's trigger types | the reconciliation read; I4 when the webhook track lands | P1arm and F3 (disarm on draft), P1new |
| hold applied or lifted (a hold token in the title or a label, `merge_control/hold_marker.py`) | **none**: `labeled`, `unlabeled` and `edited` are not in I1's trigger types | the reconciliation read; I4 | P1arm and F3 (disarm on hold); P6 for a lifted hold (the row otherwise stays PARKED) |
| closed unmerged | I1 `closed`, only in omnimarket and only while the repository variable `OMNI_OCC_COMPANION_BATCH_MODE` is `ticket`; none elsewhere | the reconciliation read (state closed, merged false); I4 | P4 (the closed terminal), P7; without it the row waits for its bound and pages an agent for a closed PR |
| merged | I2, `pr-merged-publisher.yml` in omnimarket and `pr-merged-event.yml` in omnibase_infra, on `closed` with merged true; none in the other product repositories | the reconciliation read (merged true); I3 from T12 | P4 (the merged terminal), TermKind |
| companion merged (a ticket fact) | **none**: onex_change_control has no merged publisher, and the mirror effect `node_git_query_mirror_effect` answers queries but publishes no merge events yet | T12 (I3 from the mirror); until then `companion.verify` on the reconciliation tick of COMPANION_OPEN rows reads the companion's state | P6 and P7 for every PR that needs a companion; F5 |
| companion outcome (MINTED, DECLINED, ERROR, with `command_id`) | the producer writes the outcome as a head-bound check-run marker (`occ_autobind_outcome.py`); the typed bus outcome is T10 | none: the typed outcome with `command_id` is required before wave 3 | P3, CompTracked, R1, P6 |
| head-check verdict with run attempts | the orchestrator's own `github.read_head_checks` (T4, T9) classified by T3 and T8 | none needed | P2, F7, R3 |
| arm confirmed | the answer to the orchestrator's own `github.arm` (T9) | none needed | P6 |
| completion-bound expiry | the orchestrator's `completion_bound` (T7), tagged with the state entry | none needed | R2a, R2b |

**What holds in deployment, and when.**

- With I1 as it is, `read_pr_state` on each I1 command, and no reconciliation tick: the PR enters the workflow and follows its pushes, ready flips and reopens. Converting to draft, applying or lifting a hold, and closing without merging are not observed. P1 at the arm step still holds if the arm effect reads draft and hold in the same call as the arm and refuses on either, which T9 should do regardless. P1arm, F3's disarm on draft or hold, a lifted hold, and the closed terminal do not hold. The safety properties in section 4 must not be claimed for those events on this footing.
- With the reconciliation tick added (every non-terminal row, PARKED included, on its state's poll interval): every input in the table is observed within one poll interval, and the section 4 properties hold with that latency. Disarm on draft or hold (P1arm) happens within one poll interval of the change, and the arm-time read covers the arm step inside that interval.
- With I4 (the webhook track), the tick becomes a backstop rather than the only producer for draft, hold and closed. Adding `converted_to_draft`, `labeled`, `unlabeled`, `edited` and `closed` to I1's trigger types in the product repositories is the smaller alternative, with the same effect as I4 for these events. Either is a change to the ingress, recorded here rather than made here.
- Merged and companion merged: until T12 runs on the lab, merged comes from I2 in two repositories and from the reconciliation read everywhere else, and companion merged comes only from `companion.verify` on the tick. The scheduled companion-merge heal stays as the fallback until wave 4, as the plan already says.
