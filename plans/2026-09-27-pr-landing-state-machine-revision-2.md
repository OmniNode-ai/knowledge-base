---
type: plan
status: active
date: "2026-09-27"
title: "PR landing workflow, revision 2: closed and reopened PRs, change_control_open, the completion bound and the arm across a push"
topics: [pr-lifecycle, change-control, merge, workflow, fsm, formal-methods, tla-plus, determinism]
refs:
  - plans/2026-09-26-pr-landing-workflow-plan.md
---

# PR landing workflow, revision 2: closed and reopened PRs, change_control_open, the completion bound and the arm across a push

state_as_of: 2026-09-27T06:00:00Z

**What this is.** A second revision of the state machine in [the PR landing workflow plan](2026-09-26-pr-landing-workflow-plan.md). Revision 1 (`plans/2026-09-27-pr-landing-state-machine-revision.md`, in review alongside this file) replaced sections 5.1 and 5.2 of that plan with ten model-derived changes, F1 to F10. It also listed four findings that the model had not checked. This revision checks those four and amends revision 1's tables where the model shows a change is needed. Where this file and revision 1 disagree, this file wins. Plans in this repository are frozen records, so both earlier files stay as written.

**Why.** Each of the four findings was a design question with no counterexample behind it. The TLA+ model of revision 1 was extended to cover each one, and TLC was run at the same bounds as before. Three findings need a change, and each change names the counterexample that requires it. The fourth needs no change to the state machine, only one sentence making explicit what revision 1 left implicit. The new no-stall property then found a fifth problem that revision 1 did not list: a reopened PR whose close and reopen arrive out of order can strand its row. Five small rules, four of them on CLOSED, fix it. The model, its configurations, every TLC output and a condensed trace of each counterexample are held in the internal tracker against the model task.

**Status.** Wave 1 task T2 owns the frozen transition table. It takes these rows together with revision 1's, under the same contract version bump. Nothing here changes a gate, a ruleset or a required check.

## 1. What the model checked

The model is revision 1's model with F1 to F10 applied, extended with switches that select, for each finding, the text as written or a proposed change. Every other part is unchanged: two ingress sources, delivery in any order with a budget of one duplicate, the `state_io` row under compare-and-set with an in-row outbox, the per-ticket companion lease, the completion-bound timer, and GitHub as the only actor that merges. The reducer is a pure function of (row, observation), with no clock and no language model.

It adds four properties.

- **P7, no silent stall.** A row in a state the workflow owns (COMPANION_PENDING, COMPANION_OPEN, CHECKS_PENDING or READY) always has something in flight that will move it: an outbox entry, an undelivered observation, a companion command, or an open companion that can still merge. If P7 fails, only the completion bound moves the row, and it moves it to an agent as `stalled` for a PR that has no fault.
- **TermKind.** A PR that GitHub merged never rests in CLOSED.
- **P1m.** GitHub merges only a head that the workflow armed. This is stronger than P1. It is checked to show what disarming on a push would and would not buy (section 2, G4).
- **CcOpenUnreached.** A `change_control_open` verdict for the row's head never reaches a row in CHECKS_PENDING. This is a reachability probe, not a requirement.

The completion bound is modelled two ways. For the safety runs it may expire at any time in the states it covers. For the liveness runs it expires only when the row has nothing in flight and GitHub has nothing left to do, which is a bound longer than any round trip.

| Run | Scope | Result | Distinct states |
|--|--|--|--|
| per PR, every feature, revision 2 | one PR, with another PR on the ticket able to mint or merge the companion; three ingress observations, duplicates on, the bound on | no violation of TypeOK, P1, P1arm, P2, P3, P4, P5, P7 and TermKind | 276,436,423 |
| per PR, revision 2, duplicates off | the same, with no duplicate delivery | no violation of the same nine | 32,274,005 |
| per PR, revision 2, bound off | the same, with duplicates and without the bound | no violation of the same nine | 20,544,166 |
| two PRs on one ticket, revision 2 | the companion slice, three ingress observations each, duplicates on, the bound off | no violation of the same nine | 56,257,011 |
| reopen, revision 2 | reopen allowed, P4 stated per episode | no violation, P7 included | 29,136,206 |
| liveness, revision 2 | P6 under weak fairness, the bound on, one and two ingress events | no violation | 218,217 and 2,377,490 |
| G1, no source for closed | the plan's ingress | **P7 violated**, a trace of 7 states | 43,591 at the stop |
| G1, closed always read as closed | closed ingress with no merged flag | **TermKind violated**, a trace of 11 states | 605,506 at the stop |
| G2, live companion fact | the classifier reads companion state from GitHub | CcOpenUnreached holds | 131,294,617 |
| G2, lagging companion fact | the classifier's companion fact may lag GitHub once | CcOpenUnreached violated (reachable), a trace of 7 states | 38,732 at the stop |
| G2, no row for the verdict | the verdict is dropped | **P7 violated**, a trace of 8 states | 136,389 at the stop |
| G2, verdict returns to COMPANION_OPEN | the row waits for the companion again | **P7 violated**, a trace of 8 states | 137,264 at the stop |
| G3, bound covers PARKED | revision 1's "any non-terminal" | **P6 violated**, a lasso of 13 states | 240,133 |
| G3, bound covers PARKED, safety | the nine invariants, duplicates off | no violation: covering PARKED breaks liveness, not safety | 33,966,233 |
| G3, expiry not tagged with its state | the bound without PARKED | no violation of P6 | 218,217 and 2,377,490 |
| G4, row forgets `armed` on a new head | no disarm, and the row clears the flag | **P1arm violated**, a trace of 10 states | 574,752 at the stop |
| G4, disarm on every new head | the nine invariants (duplicates off), and P6 | no violation | 34,150,127 and 243,489 |
| G4, P1m with and without the disarm | both variants | **P1m violated**, by the same trace of 12 states in both | 2,644,848 and 2,540,671 at the stop |
| G5 (a) off | a reopened snapshot re-evaluates only a CLOSED row | **P7 violated**, a trace of 10 states | 199,822 at the stop |
| G5 (b) off | CLOSED drops companion observations | **P7 violated**, a trace of 11 states | 361,043 at the stop |
| G5 (c) off | CLOSED reopens only on the snapshot marked reopened | **P7 violated**, a trace of 13 states | 828,667 at the stop |
| G5 (d) off | CLOSED drops a newer closed | **P7 violated**, a trace of 13 states | 856,644 at the stop |
| G5 (e) off | CLOSED drops merged | **P7 violated**, a trace of 19 states | 8,120,759 at the stop |

**Limits of the claim.**

- The two-PR run uses the companion slice, where check reads return nothing. G2 and the check-owned half of P7 rest on the per-PR run, where a second PR's effect on the shared companion is over-approximated, as in revision 1.
- The two-PR run with the bound on was not run to completion. The per-PR run has the bound on.
- The G3 safety run and the G4 disarm run are exhaustive with duplicates off. With duplicates and the bound on together, both were stopped past 230 million distinct states with no violation.
- The runs with reopen off were made before the reopen rules of G5 were added to the model. With reopen off, CLOSED is never left, so those rules change nothing any property reads. The duplicates-off and bound-off per-PR runs, the reopen run and every counterexample were made on the final model.
- One effect is in flight per PR. The duplicate budget, the bound budget and the lag budget are one each.
- The model has no clock. "The bound expired" is a nondeterministic event, and in the liveness runs it is limited to rows with nothing in flight.
- Not modelled, as in revision 1: update-branch, regenerate on a conflicting companion, ERROR retry, and the "companion not required" evaluation.

## 2. The findings

| # | Finding | Verdict | Counterexample without the change | Property broken |
|--|--|--|--|--|
| G1 | No ingress source publishes a closed, unmerged PR. I1 fires on opened, synchronize, ready_for_review, hold changes and reopened. I2 and I3 report merges only. | **Change.** I1 also fires on `closed` and carries GitHub's `merged` flag. A closed event with `merged` true is the merged observation, not a closed one. | The PR is closed on GitHub. The row reaches CHECKS_PENDING, and its check read finds the PR closed and returns nothing. Nothing else will ever arrive for the row. With the bound on, the closed PR goes to an agent as `stalled`, and no terminal is ever emitted. Separately, if every closed event is read as closed, a merged PR's closed event can arrive before I2 and I3. The row goes to CLOSED and emits pr-landing-closed, and both merged observations are then dropped as arriving after a terminal. | P7, and P4's "exactly one terminal". TermKind for the unflagged reading. |
| G2 | T3's verdict `change_control_open` has no row. | **Change.** In CHECKS_PENDING the verdict counts as pending: read the head checks again after the poll interval. | The verdict is reachable only when the classifier's companion fact lags GitHub. A row is in CHECKS_PENDING only after the companion merged, so a live read of the companion always says merged, and the verdict is `change_control_stale`. When the fact lags (for example, when it is read from the mirror) the verdict reaches a CHECKS_PENDING row. With no row, it is dropped, nothing is in flight, and the red change-control check is never re-run. Sending the row back to COMPANION_OPEN also fails: the "companion merged" observation has already been consumed, and the row waits for one that will never come. | P7 |
| G3 | Whether the completion bound covers PARKED. | **Change.** The bound covers every non-terminal state except PARKED. A draft or held PR waits on a person, and may do so indefinitely. | A draft PR parks. The bound expires in PARKED, and the row goes to NEEDS_AGENT as `stalled`. The PR is then marked ready and its checks go green. NEEDS_AGENT leaves only on a new head or a manual re-evaluation, so the PR is never armed. | P6 |
| G4 | Whether the workflow disarms on every new head, since GitHub auto-merge survives a push. | **No change to the transitions.** One clarification: the row keeps `armed` across a new head, exactly as GitHub does. | Disarming on every new head passes P1 to P7 but buys nothing measurable. The stronger property P1m ("GitHub merges only a head the workflow armed") fails with or without it, by the same trace. The workflow arms head 1. A push makes head 2, its checks go green, and GitHub merges head 2 before the push observation reaches the row. No workflow action can win that race. The clarification is needed because a row that clears `armed` on a new head, without disarming, breaks P1arm. The PR was armed at head 1, head 2 is a draft, and the row parks without a disarm because it no longer believes it is armed. GitHub stays armed on the draft. | P1arm, for a row that forgets `armed`. P1m is not a property the workflow can hold. |
| G5 | Found by P7, not listed in revision 1: a closed PR's row is stranded when the PR is reopened and the observations arrive out of order. | **Change.** Five rules, (a) to (e) in section 3. | Each rule has its own counterexample. (a) The reopened snapshot arrives before the closed, which is then dropped as older. The row is in CHECKS_PENDING, its check read ran while the PR was closed and returned nothing, and a same-head snapshot issues nothing. (b) A companion outcome arrives while the row is CLOSED and is dropped. After the reopen, evaluation finds the companion command still marked in flight (F4) and issues nothing, and the outcome never comes again. (c) The PR is reopened and pushed, and the push's snapshot reaches CLOSED before the reopened one and is dropped. The reopen then sends the row to read checks on the old head. (d) The PR is closed, reopened and closed again, and the second closed reaches CLOSED first and is dropped. The older reopened snapshot then reopens the row for a PR that is closed. Separately, (e) the PR is closed, reopened and merged, and the first closed arrives after the merge and before any merged observation. The merged observations are then dropped in CLOSED, and a late reopened snapshot sends the row to read checks for a merged PR. | P7 |

On G3, the finding also asked that an expiry name the state it was set for. The model does not need it. With the expiry untagged, P6 still holds at one and two ingress events. The head-match rule already drops an expiry from an older head, and the bounded runs found no case where an untagged expiry for a state the row had left changed an outcome. Tagging the expiry is harmless and may stay as an implementation choice. It is not model-derived.

## 3. Changes to revision 1's section 3

**Ingress.** I1, the occ-autobind command, also fires on `pull_request.closed`, carrying GitHub's `merged` flag (G1). `ModelPrLandingObservation` gains that flag for closed events. As a substitute, the mirror (I3) may report closed-unmerged PRs alongside merges. One of the two is required.

**Rows changed or added.** Rows not listed here stand as revision 1 wrote them.

| From | Observation | To | Intents | Change |
|--|--|--|--|--|
| any non-terminal | pushed: a head other than `head_sha`, newer by the ordering key | OBSERVED | none. `armed` carries over as it was, because GitHub keeps auto-merge across a push | F1, G4 |
| CHECKS_PENDING | verdict change_control_open | CHECKS_PENDING | github.read_head_checks after the state's poll interval | G2 |
| any non-terminal | merged (I2, I3, or an I1 closed event carrying `merged` true) | MERGED | terminal pr-landing-merged, keyed (PR, episode), carrying `seq` | F9, F10, G1 |
| any non-terminal | closed with `merged` false, newer by the ordering key | CLOSED | terminal pr-landing-closed, keyed (PR, episode), carrying `seq` | F2, F9, F10, G1 |
| any non-terminal except PARKED | completion bound expired | NEEDS_AGENT | agent_needed(stalled, state) | G3 |
| any non-terminal | reopened, newer by the ordering key (its closed arrived later, or not at all) | OBSERVED, evaluated at once; `episode` unchanged, because the row never applied the close | as evaluation | G5 (a) |
| CLOSED | a companion outcome or companion merged | CLOSED | none. The row records it in its companion fields, so a reopen evaluates the companion as it is | G5 (b) |
| CLOSED | any snapshot newer by the ordering key, reopened or not | OBSERVED, `episode` + 1 | as evaluation | F10, G5 (c) |
| CLOSED | closed, newer by the ordering key | CLOSED, with the newer key | none. The episode's terminal was already emitted | G5 (d) |
| CLOSED | merged | MERGED, `episode` + 1 | terminal pr-landing-merged, keyed (PR, new episode), carrying `seq` | F10, G5 (e) |

The PARKED state's row in the state table gains one clause: the completion bound does not apply there (G3). In the state table, CLOSED now leaves on any snapshot newer by the ordering key (a reopen, marked or not) and on merged, and it keeps applying the ordering key while it waits (G5). Rule (c) replaces revision 1's row "CLOSED, reopened, newer by the ordering key".

Rule (c) rests on one ingress fact: I1 publishes a snapshot only for an open PR, because GitHub sends no synchronize event for a closed one. A snapshot newer than the row's closed therefore proves a reopen happened, even if the reopened event itself is late or lost.

## 4. Changes to revision 1's section 4

Add one property:

- **P7** No silent stall. A row in COMPANION_PENDING, COMPANION_OPEN, CHECKS_PENDING or READY always has an effect, an observation or a companion command in flight that will move it, or, in COMPANION_OPEN, an open companion that can still merge. The completion bound is a backstop for a fault. It is never the transition by which a healthy PR leaves a state.

P1 to P6 stand as revision 1 wrote them. P1m, "GitHub merges only a head the workflow armed", is not adopted as a property. Section 2 shows the workflow cannot hold it: only GitHub-side configuration could.

## 5. What this changes downstream

- **T2** takes the rows in section 3 with revision 1's rows, adds the `merged` flag on closed observations, and states the bound's state set per state in the contract.
- **The ingress publisher for I1** subscribes to `pull_request.closed` (G1). If the mirror is used instead, it reports closed-unmerged PRs as well as merges.
- **T3** keeps `change_control_open`. Its fixtures should include a head where the companion merged but the classifier's companion fact still reads open, with expected verdict `change_control_open`, so the reducer's pending path is exercised (G2).
- **T6** asserts P7 and TermKind in the reducer tests, alongside P1 to P6.
- **T7** sets no completion bound in PARKED (G3), and carries `armed` across a new head (G4).
- **T2 and T6** take G5's CLOSED rules into the reducer and its tests. Each of (a) to (e) is a reducer test with the observations in the order the counterexample gives.
