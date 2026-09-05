---
type: plan
status: active
date: "2026-09-05"
title: "Pre-push impacted migration watchdog and owned-process cleanup"
topics:
  - test-infrastructure
  - process-lifecycle
  - migration-validation
refs: []
---

# Pre-push impacted migration watchdog and owned-process cleanup

## Status and decision boundary

This plan is amended after the independently reviewed two-strike diagnosis. The frozen watchdog
prototype is diagnostic evidence only and is not commit-ready. The Phase 0 environment-validator
publication is held behind this issue; its reviewed branch was not published. No third timing or
cleanup implementation attempt is authorized until the discriminator traces below amend the
diagnosis and an independent review records PASS for this amended plan.

The plan does not diagnose a migration correctness failure. It addresses a liveness and test
process-ownership failure in the governed local pre-push path. It prohibits bypassing the gate,
loosening the selected scope, adding a retry loop, or skipping a migration test.

## Observed evidence

On the reviewed Phase 0 candidate, the normal pre-push hook selected this local impacted-test
command:

```text
uv run pytest scripts/tests/ tests/ci/ tests/scripts/ tests/unit/scripts/ --ignore=tests/integration --tb=short
```

The selected invocation remained non-terminal for more than 32 minutes. The verified owned
process chain was Git push, pre-commit, the smart-test hook, `uv`, pytest, the
forward-migrations shell runner, and a local SQL-client child. The smart-test hook invokes
pytest directly for this path; the pytest configuration provides no end-to-end timeout.

The migration runner has bounded readiness and advisory-lock substeps. Those bounds do not
bound the whole pytest invocation, so they cannot provide a complete liveness guarantee.

A separately parented disposable local PostgreSQL service was still live after recovery. It was
not a descendant of the push tree and was deliberately not signalled. This is evidence requiring
an ownership audit, not proof that the service was created by this exact run or that it leaked
because of the timeout.

## Safe recovery record

Immediately before intervention, each target was rechecked as a descendant of the owned push.
Only the owned child tree received TERM, from leaves toward its parent. The root push exited
within one second; no KILL was necessary. The candidate worktree remained clean at its reviewed
head, and the corresponding remote branch and pull request were absent after recovery.

The recovery deliberately did not signal the independently parented database process, use a
global process matcher, rerun the push, or bypass hooks. This establishes the containment rule
for a future watchdog: a timeout handler may only act on a process it started and can still prove
it owns.

## Two-strike diagnosis protocol

This is a two-strike-style investigation rather than permission for speculative patches.

1. **Evidence point one — absent outer bound.** The selected local pytest path has no
   process-wide deadline. Reproduce it under an isolated, externally bounded harness while
   collecting a sanitized phase/parent-chain receipt.
2. **Evidence point two — incomplete ownership observation.** A non-descendant disposable
   database service survived the owned-tree recovery. Determine, using fixture-local ownership
   records and isolated test resources, whether normal, setup-failure, timeout, and signal paths
   each reap all children the fixture starts.

If two independent implementation attempts fail either the bounded-exit or owned-child-cleanup
invariant, stop implementation and amend this diagnosis with the failed traces. Before a third
attempt, run the bounded discriminator-trace procedure in this plan and obtain an independent
PASS on its amended requirements. Do not add a third speculative attempt, quarantine the test, or
change the selected test set to hide the failure.

### Two-strike hold and discriminator traces

The reviewed prototype exhausted the two-strike allowance because a synthetic short-policy
deadline sometimes reached the graceful `wrapper_deadline_terminated`/124 path and sometimes
reached fail-closed `cleanup_uncertain`/125. That variance is not evidence that the production
2700-second policy is wrong and must not be addressed by expanding, restarting, or overriding any
production deadline. The prototype remains frozen and uncommitted until this plan's proof gates
are met.

Before any third implementation change, collect bounded, event-driven discriminator traces for
both a successful graceful-TERM case and the failing/uncertain case under the same external
watchdog. The trace must let review distinguish: insufficient synthetic scheduling room, serial
control waiting, an incorrectly placed launch instant, and a real terminal-correlation/direct-reap
defect. It records only the following sanitized fields: a test-run correlation token; actor (`P`,
`G`, or `S`); monotonic offset from the run origin; named phase/event and barrier state; message
and terminal-message correlation tokens; normalized result; and logical ownership/reap state
(`P_OWNS_G`, `G_OWNS_S`, `S_OWNS_PAYLOAD`, `REAP_CONFIRMED`, or `UNVERIFIED`). It contains no
secret, command, environment, endpoint, filesystem path, raw PID, raw PGID, raw wait status, or
process-tree dump. The trace is bounded in record count and byte size, and review receives the
sanitized failed/successful pair plus the residual-process assertion, not a timing-only claim.

The independent reviewer must classify the pair before another fix: (a) a barrier-sensitive
synthetic-fixture variance authorizes replacement of the timing assertion with the equivalent
barrier proof; (b) serial multiplexing or correlation/reap evidence authorizes one narrowly
reviewed protocol fix; or (c) missing/inconclusive proof keeps the prototype frozen. An amended
plan independent PASS is a precondition of option (a) or (b), not a post-hoc review step.

## Required target design

### Policy authority and one common deadline

No existing hook overlay currently supplies this deadline. The remediation must introduce the
committed, typed contract overlay
`config/overlays/prepush-execution-deadline.v1.yaml`, parsed repo-relatively by a narrow policy
reader. It is the sole authority for this behavior: environment variables, hook arguments,
pytest options, runner defaults, and test inputs cannot lengthen or disable it.

Its initial, versioned schema is:

```yaml
schema_version: omnibase-infra.prepush-execution-deadline.v1
impacted_migration_execution:
  pytest_budget_seconds: 2400
  receipt_and_join_budget_seconds: 240
  term_grace_seconds: 30
  kill_reap_seconds: 30
  overall_deadline_seconds: 2700
```

All values are positive integers; the allowed ranges are respectively 1--2400, 1--240, 1--60,
1--60, and 300--2700. Validation requires the initial equality
`overall_deadline_seconds == pytest_budget_seconds + receipt_and_join_budget_seconds +
term_grace_seconds + kill_reap_seconds`; a future policy revision needs a new schema version and
its own review rather than a caller override. The initial 2700-second ceiling is exactly the
bounded `2400 + 240 + 30 + 30 = 2700` execution budget, not an unbounded timeout.

The parent wrapper records one `time.monotonic()` launch instant and computes one absolute
deadline from that overlay. It conveys that exact absolute monotonic deadline, never a relative
timeout, in the authenticated launch/control records to `G` and `S`. Pytest, guardian receipts,
joins, TERM grace, KILL/reap, and teardown all consume that same absolute deadline, additionally
capped by their policy budget. No phase starts a fresh timeout. A completed pytest with a nonzero
child result is `pytest_failed`; expiry begins the bounded deadline-cleanup protocol and yields
`wrapper_deadline_terminated` only after the graceful correlated reap proof. A failed ownership
or protocol proof is `cleanup_uncertain`, never a successful timeout result. Receipt outcome, not
elapsed time or an ambiguous numeric exit code, is authoritative.

The phase budgets are reservations inside this single deadline, not timers that a phase may
restart. At every wait, the implementation computes `remaining = max(0, absolute_deadline -
monotonic_now)` and caps the operation by both `remaining` and its policy reservation. In
particular, `kill_reap_seconds` is the maximum remaining budget for the verified post-KILL reap
and final proof; it is charged against the same `absolute_deadline` and must never become a new
30-second window after TERM, KILL, EOF, receipt failure, or an interrupt. If no budget remains for
the required receipt/reap proof, the only result is `cleanup_uncertain`/125.

The wrapper maps a completed zero child to exit 0 and a completed nonzero pytest child to exit 1
while retaining the exact child result in the receipt. It reserves 124 for a verified graceful
deadline termination, 125 for `cleanup_uncertain` or protocol failure, and 126 for setup failure.
For a caught POSIX interruption with signal number `N` (the supported set is SIGHUP=1,
SIGINT=2, and SIGTERM=15), `wrapper_interrupted` records `interruption_signal_number: N` and
exits with the exact normalized status `128 + N` (129, 130, or 143 respectively), after bounded
cleanup. Receipt process codes use that same normalization for a process terminated by a signal;
they never encode a negative return code or a raw wait status. Thus a pytest failure and a wrapper
failure remain distinguishable even if pytest itself would otherwise choose the same number.

### Stable guardian and ownership protocol

The hook must not implement a raw numeric PID or PGID cleanup fallback. The parent wrapper `P`
creates a direct control guardian `G` through one retained `subprocess.Popen` handle, with owned
control descriptors and a random run identifier established before spawn. `G` creates payload
supervisor `S`; `S` starts a new session and is the only process permitted to signal the payload
group using `os.kill(0, signal)`. `P` and `G` use authenticated framed control messages; `G` and
`S` use a second authenticated channel with independent sequence spaces. `G` survives ordinary
`S` completion, validates `S`'s reap receipt, and sends the final result to `P`; `P` then reaps
only its direct `G` `Popen` handle.

On Linux, a pidfd may provide additional liveness observation for that direct `G` child; absence
of pidfd support must not degrade into `kill(pid)` or `killpg(pgid)`. The retained direct `Popen`
handle, its return code, and authenticated control protocol are the parent-side ownership proof.
Neither `P` nor `G` retains or signals a numeric payload PID/PGID, calls `killpg`, or uses a
process-name matcher. This removes PID/PGID reuse from the parent-side cleanup decision.

The production payload contract is same-group and no-detach: it forbids `setsid`, `setpgid`,
daemonization, double-forking, and inherited uncontrolled descriptors. If `G` or `S` naturally
exits, loses its direct-child identity, sends EOF or an invalid receipt, or cannot prove its
required state, `P` reaps only the direct `G` handle when possible and returns
`cleanup_uncertain`. It must not signal an external numeric group and must not claim a payload
leak was cleaned. Detached descendants are outside this contract; a destructive detached-child
test is permitted only in an explicitly created and verified disposable cgroup scope. Without
that capability it proves the prohibited-contract/uncertain outcome and performs no speculative
cleanup.

### Autonomous supervisor liveness and self-cleanup

`S` is not passive while payload work is running. It independently multiplexes its direct payload
child/reap state, the authenticated `G`--`S` channel, and the shared absolute monotonic deadline.
It treats peer EOF, authenticated-channel failure, a failed terminal correlation, and expiry of
that deadline as a loss of guardian authority; it must not wait for `G` or for `P` to request
cleanup. The payload must not inherit either end of the `G`--`S` channel, so a dead or closed `G`
is observable as EOF rather than being masked by an inherited descriptor.

On guardian loss, channel EOF/failure, or the common deadline, `S` enters its autonomous
fail-closed state machine: it sends TERM only to its own group with `os.kill(0, SIGTERM)`, reaps
its direct payload child for at most the remaining common-deadline/policy grace budget, and exits
with fail-closed status 125 if the group is already empty. If members remain after that bounded
reap, `S` may send `os.kill(0, SIGKILL)` only after re-verifying the self-led same-group contract:
`S` is still both session and process-group leader, the payload remains its direct child in that
same group, no payload detach/leader-loss indicator has occurred, and no `G`/`P` process is in
the group. This is self-signalling only; no parent or guardian ever signals a payload group.

The self-KILL branch necessarily kills `S` with the remaining payload. It therefore cannot emit a
terminal receipt after the KILL; its normalized status is 137 and the externally authoritative
outcome is `cleanup_uncertain`, never a group-empty success. If the contract cannot be verified,
`S` sends no KILL, exits fail-closed where possible, and the outcome remains `cleanup_uncertain`.
If `G` is gone and no terminal receipt reaches `P`, `P` reaps its direct `G` `Popen` handle (even
when that handle has already exited) and returns `cleanup_uncertain`/125. `P` does not attempt to
infer or signal any payload process or group. Residual-process tests must prove that this `S`
self-cleanup leaves neither `S` nor its fixture payload alive.

The TERM-ignore case is deliberately fail-closed. `S` may remain alive long enough to send TERM
to its group and report a clean child exit. If the payload ignores TERM, the autonomous self-KILL
above is permitted only under its verified self-led same-group contract and necessarily prevents
an `S` terminal receipt. The portable outcome is therefore `cleanup_uncertain`, not a successful
group-empty timeout receipt. An optional isolated-cgroup experiment may independently observe
cleanup, but it is not a portable hook success path.

Ownership is registered before spawn: `P` allocates a run-ownership record, control descriptors,
deadline, and cleanup state before calling `Popen`. It assigns the returned handle and enters an
interruption-safe `try`/`finally` before any protocol read. Every setup exception, parent
interruption, receipt error, and child result passes through that `finally` path. The test seam
must inject faults at resource reservation, Popen raising before a handle, Popen returning before
registration, control-FD transfer, `G` acknowledgement, `S` startup, and payload startup. Each
case proves closure/reaping of only the handles actually obtained, a bounded non-success result,
and no numeric signal fallback. The real forward-migrations fixture applies the same ownership
ledger to every shell, SQL client, and disposable service it starts; it never acts on an ambient
service.

### Bounded control receipt

Guardian control messages and the final receipt must be canonical, versioned, bounded framed
records. A v1 record has a literal schema version, random run identifier, per-sender integer
sequence number, message identifier/correlation identifier, absolute monotonic deadline,
bounded payload, and an allowed kind. Parsing rejects duplicate JSON keys, non-integer booleans
or floats, unknown fields, wrong run/correlation values, oversized frames, malformed framing,
duplicate or out-of-order messages, and EOF before the required terminal message.

Every terminal ACK is authenticated and bound to the *exact* terminal message it acknowledges.
The ACK carries the schema version, run token, sender sequence number, terminal message ID,
terminal correlation token, and digest of the canonical terminal frame; its authentication tag is
verified as a keyed MAC (or repository-authorized authenticated equivalent) before it can advance
state. `G` accepts an `S` terminal receipt, and `P` accepts a `G`
terminal receipt, only when all of those values exactly match the prior validated terminal frame.
A generic READY/complete ACK, an ACK for a different sequence or digest, an unauthenticated ACK,
or a missing ACK is a protocol failure and cannot serve as terminal/reap proof.

The terminal receipt is at most 4 KiB and contains only:

| Field | Constraint |
| --- | --- |
| `schema_version` | literal `omnibase-infra.prepush-execution-receipt.v1` |
| `outcome_class` | `pytest_completed`, `pytest_failed`, `wrapper_deadline_terminated`, `cleanup_uncertain`, `wrapper_protocol_error`, `wrapper_setup_error`, or `wrapper_interrupted` |
| `execution_state` | `active`, `lock_wait`, `completed`, or `unknown` |
| `child_exit_code`, `supervisor_exit_code` (`S_code`), `guardian_exit_code` (`G_code`), `wrapper_exit_code` | separately nullable/required normalized process results as specified below; no PID or PGID |
| `interruption_signal_number` | required only for `wrapper_interrupted`: 1, 2, or 15; otherwise null |
| `reap_proof` | `guardian_reaped_group_empty`, `guardian_reaped_unverified`, or `not_started` |
| `cleanup_scope` | `same_group_guardian`, `external_disposable_cgroup`, or `none` |

The receipt contains no argv, environment, endpoint, credential, database, filesystem path,
PID, PGID, traceback, or raw exception. The separately bounded discriminator trace may include
only the sanitized monotonic offsets and correlation/ownership fields specified above; elapsed is
observational only and cannot select a cleanup action. A guardian result is not success until `G`
has validated `S`'s exact terminal correlation, authenticated ACK, and group-empty reap proof, and
`P` has reaped direct `G` with exit 0.

The implementation must enforce this exact outcome/code/nullability matrix. `S_code` and `G_code`
are separate fields: a null `S_code` never implies a null `G_code`, or vice versa. Each present
process result is 0--255, with `128 + N` for signal `N`; no negative result or raw wait status is
accepted.

| Outcome | Child code | `S_code` | `G_code` | Wrapper code | Reap proof |
| --- | --- | --- | --- | --- | --- |
| `pytest_completed` | required 0 | required 0 | required 0 | 0 | `guardian_reaped_group_empty` |
| `pytest_failed` | required nonzero | required 0 after child reap | required 0 after validated `S` receipt | 1 | `guardian_reaped_group_empty` |
| `wrapper_deadline_terminated` | required nonzero termination result | required 0 after TERM and child reap | required 0 after validated `S` receipt | 124 | `guardian_reaped_group_empty` |
| `cleanup_uncertain` | nullable | nullable; required 125 only when `S` can emit its autonomous fail-closed terminal before channel loss | nullable; required 0 only when `G` emits a valid uncertain receipt | 125 | `guardian_reaped_unverified` or `not_started` |
| `wrapper_protocol_error` | nullable | nullable | nullable; required 0 only if it emits the valid protocol-error receipt | 125 | `guardian_reaped_unverified` or `not_started` |
| `wrapper_setup_error` | null | null if `S` was not spawned, otherwise required observed result | null if no `G` handle exists, otherwise required reaped result | 126 | `not_started` or `guardian_reaped_unverified` |
| `wrapper_interrupted` | nullable | nullable | nullable | exactly `128 + interruption_signal_number` (129/130/143) | never `guardian_reaped_group_empty` without the normal receipt proof |

`wrapper_deadline_terminated` is a nonzero failure, never a timeout success. A TERM-ignoring
payload, leader loss, missing receipt, or no verified group must use `cleanup_uncertain`, not that
row.

`G` must not map an arbitrary non-`None` supervisor reason to
`wrapper_deadline_terminated`/124. The only eligible reason is the explicit
`deadline_term_graceful` state, with a validated exact terminal receipt/ACK chain and a verified
process-group-empty proof after TERM (and, if KILL was entered, after the `kill_reap_seconds`
bounded reap). The proof is the authenticated `S` terminal record that attests its direct payload
reap and empty self-led group, validated by `G` against the terminal frame/ACK chain without raw
PID/PGID inspection. Guardian loss, EOF, self-KILL without a terminal record, protocol error,
missing/incorrect ACK, exhausted reap budget, an unverified group, or every other supervisor
reason maps to `cleanup_uncertain`/125. `G` therefore cannot turn a non-empty or merely attempted
cleanup into verified 124. Because self-KILL terminates `S` before it can provide that terminal
proof, a KILL-entered path cannot produce 124; it remains `cleanup_uncertain`/125 even when the
bounded residual test later observes no owned process.

### Cleanup states and escalation

`P` may request deadline cleanup through live `G`, which may request that `S` send TERM only to
`S`'s own group, but `S` must reach the same cleanup state autonomously on `G` loss, channel EOF,
or the common deadline. All waits remain bounded by that one deadline and the 30-second grace cap.
`TERM_SENT` and `PREKILL` are progress records, not success evidence. A clean payload exit during
the grace period is accepted only when `S` reaps it, `G` validates the correlated terminal receipt,
and `P` reaps `G`. A TERM-ignoring payload, `S` loss, or any need for an unverified self-KILL is
`cleanup_uncertain`; no parent-side payload-group signal follows and the portable path does not
claim group-empty cleanup.

### Deterministic short-policy seam

Production computes exactly one launch-time monotonic origin in `P` and derives the immutable
2700-second absolute deadline from the committed overlay. It exposes no CLI argument, hook
argument, environment override, or runner default that can change that origin or deadline. The
only short-policy facility is an in-process test seam: a test supplies a synthetic monotonic
origin and a separately schema-validated short fixture policy, then creates one corresponding
absolute deadline after authenticated `READY` barriers for the intended actors. This seam is
test-only, cannot be reached from the production hook, and never permits a phase to rebase its
deadline.

Short-policy tests use named barriers/events to hold and release each P--G, G--S, payload-start,
TERM, reap, terminal-receipt, and ACK hop. They use finite external watchdogs only as an outer
test bound, never `sleep` as a correctness mechanism. The test assertions consume the synthetic
deadline once, prove the same correlation/reap ordering as production, and explicitly exercise
the `kill_reap_seconds` reservation; they may not make a flaky wall-clock timing assertion stand
in for that proof.

The fixture and hook must use finite descriptor and stdio limits, `close_fds`, and explicit
allowlisted control descriptors. It must close each owned descriptor in `finally`. No signal
handler performs I/O; signal handling only transfers control to the normal cleanup state machine.

## Deterministic regression matrix

| Case | Controlled condition | Required proof |
| --- | --- | --- |
| Normal impacted run | Fast same-group owned child exits zero | `pytest_completed`, `S` then `G` reaped at exit 0, and no watchdog result |
| Failing impacted run | Same-group owned child exits nonzero | `pytest_failed`, retained child result, wrapper exit 1, and correlated `S`/`G` reaping |
| Graceful deadline termination | Same-group child exits after `S` sends TERM | Nonzero `wrapper_deadline_terminated`/124 and group-empty receipt proof; never success |
| TERM-ignore deadline | Same-group payload blocks after TERM | `cleanup_uncertain`/125; self-KILL is allowed only after the verified self-led same-group proof, never as a group-empty claim |
| Exact terminal ACK binding | Substitute a valid-looking ACK with a wrong terminal message ID, correlation token, sequence, digest, or authentication tag | `wrapper_protocol_error` or `cleanup_uncertain`/125; it cannot advance terminal/reap proof or produce 124 |
| Supervisor-reason discriminator | Deliver each non-`deadline_term_graceful` supervisor reason, including EOF, self-KILL, receipt failure, and exhausted reap budget | Never 124; `cleanup_uncertain`/125 and the bounded sanitized trace identifies the reason |
| `G` crash residual cleanup | Kill `G` after `S` and an owned payload are ready, without delivering a terminal receipt | `S` observes channel EOF, autonomously TERM/reaps and self-KILLs only if its contract verifies; `P` reaps `G`, returns `cleanup_uncertain`/125, and no `S` or payload remains |
| `G`--`S` channel EOF residual cleanup | Close the authenticated guardian channel while `G` remains otherwise controlled and payload is live | `S` treats EOF as guardian loss; the same bounded self-cleanup occurs, no parent signal is issued, and residual inspection proves `S` and payload are absent |
| Common-deadline residual cleanup | Hold the control path so `S` reaches the exact shared monotonic deadline with payload live | `S` acts without a `G` command, uses only its self-group proof for any KILL, returns/causes fail-closed 125, and residual inspection proves `S` and payload are absent |
| Fixture setup failure | Each injected partial-resource/Popen boundary after zero or one owned child starts | `wrapper_setup_error`; `finally` closes/reaps only obtained handles; no ambient service is touched |
| Parent interruption | Controlled interruption at reservation, returned-Popen, control-transfer, `G` ACK, `S` start, and payload-start boundaries | `wrapper_interrupted` or fail-closed setup result; bounded owned cleanup and no raw signal |
| Migration lock contention | Isolated fake or disposable resource holds the fixture lock | Existing lock semantics remain meaningful; outer watchdog remains bounded |
| Active, lock wait, completed | Controlled fixture phases | Receipt has the matching state; state changes neither deadline nor outcome semantics |
| `S` or `G` natural exit / identity loss | Supervisor/guardian exits or control proof disappears before terminal receipt | `cleanup_uncertain`, direct `G` reaped if possible, and no raw PID/PGID signal |
| Unverified group / detachment | Payload attempts `setsid`, violates same-group contract, or a KILL is requested without verified `S` group state | `cleanup_uncertain`; `S` sends no KILL; no cleanup claim; destructive cleanup only in an explicit disposable cgroup test scope |
| Receipt faults | Split/coalesced frame, duplicate/out-of-order/wrong-run message, EOF, EPIPE, and terminal-ACK mismatch on both `P`--`G` and `G`--`S` channels | Bounded `wrapper_protocol_error` or `cleanup_uncertain`; no success and no parent signal |
| Descriptor and stdio bounds | Child attempts inherited-FD retention or excessive output | Only allowlisted descriptors are inherited; wrapper exits/reaps within the common deadline |
| PID/PGID reuse guard | Controlled fake reports a stale leader identity | Parent never signals numeric PID/PGID; outcome is uncertain and sentinel is unchanged |
| Unrelated sentinel | Independently created sentinel process/service | Sentinel remains live and receives no signal |

Use events, barriers, controlled fakes, and finite waits; do not use sleep as the correctness
mechanism. Real database coverage must be capability-gated and use a disposable namespace owned
by the test. No test may connect to or mutate a shared runtime service.

Every residual row is bounded by its external watchdog and must inspect, after direct `G` reap,
that all fixture-owned handles are terminal: no residual `S`, payload, control-FD holder, or
fixture-created disposable service. The inspection records logical ownership identities only and
must also prove the unrelated sentinel remained live and unsignalled. A residual or an
unverifiable ownership state is a fail-closed `cleanup_uncertain`/125 result, not a retry.

## Instrumentation and reproducibility

Before code changes, add only the sanitized test-support instrumentation required by the
two-strike discriminator: monotonic phase offsets, exact terminal-message/ACK correlations, and
logical ownership/reap transitions. Do not log command environments, connection strings,
filesystem locations, secret values, raw PID/PGID values, process-tree dumps, or raw wait status.
A bounded wrapper must capture the pytest summary and wrapper exit status separately so a
post-success hang cannot be mistaken for a passing test.

Reproduce on the public base and the candidate with the same isolated fixture capability. Record
whether the forward-migration runner is active, waiting for a lock, or has already completed when
the outer watchdog fires. Do not infer a root cause from elapsed time alone.

## Acceptance gates and rollout

1. Focused hook unit tests prove direct local impacted execution receives the parsed common
   deadline and ordinary small targeted execution retains its intended path.
2. Unit and isolated integration tests cover every matrix row, including the separate `P`--`G`
   and `G`--`S` channel boundaries; exact terminal ACK binding; explicit `G` crash, `G`--`S` EOF,
   and common-deadline residual tests; TERM-ignore uncertainty; `kill_reap_seconds` exhaustion;
   partial Popen resources; setup, receipt, leader-loss, no-verified-group, interruption,
   descriptor, and sentinel boundaries. Repeated runs use finite external watchdogs and inspect
   the bounded residual matrix.
3. The affected migration parity tests and hook tests pass repeatedly under finite wrappers with
   no residual fixture-owned process or service. Real database coverage is capability-gated and
   uses a disposable namespace owned by the test; it never connects to a shared runtime service.
4. Shell syntax and ShellCheck, strict type checking where Python changes, Ruff, and relevant
   pre-commit hooks pass. The governed pre-push suite must then reach a terminal result without a
   bypass.
5. Before any third implementation attempt, independent review records PASS for the amended-plan
   discriminator trace pair, barrier-driven synthetic-origin seam, exact terminal ACK binding,
   single-deadline/`kill_reap_seconds` accounting, verified group-empty 124 gate, and bounded
   residual matrix. It also verifies stable guardian identity, autonomous `S` liveness/EOF/deadline
   cleanup, self-led same-group-only KILL proof, separate `S_code`/`G_code` receipt nullability,
   exact interruption status convention, fail-closed uncertainty, and that migration semantics
   were not weakened.

Roll out the overlay, supervisor, hook wiring, and fixture ownership seam atomically unless their
interface has independently passed the same deterministic matrix. A failed gate remains a
failure; this work only makes its liveness and cleanup deterministic.

### Reversible rollback without restoring an unbounded path

The implementation inventory must name the overlay, policy reader, guardian/supervisor, hook
wiring, and their tests in one remediation series. A rollback is a compensating, reviewed commit
that retains the hook's supervisor entry point and makes it fail closed with a bounded
`wrapper_setup_error` when the new policy or guardian must be withdrawn. It must not restore a
direct unbounded `pytest` invocation, delete the policy parser independently, or use `git revert`
to reactivate the former path. A full removal is permitted only after a replacement bounded
supervisor and its ratchet tests have landed. The rollback check must prove the impacted path
still enters a bounded supervisor/fail-closed verdict and that ordinary unrelated hook paths are
unchanged.

## Related work

The Phase 0 branch remains unpublished while this remediation is incomplete. The dedicated
ticket is OMN-17953. # sanitization-ok: internal ticket identifier is necessary for public planning provenance
