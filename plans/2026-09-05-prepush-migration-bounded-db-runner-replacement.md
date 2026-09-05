---
type: plan
status: draft
date: "2026-09-05"
title: "Pre-push migration bounded database runner replacement"
topics:
  - test-infrastructure
  - process-lifecycle
  - migration-validation
  - postgresql
refs: []
---

# Pre-push migration bounded database runner replacement

## Decision and evidence boundary

This replaces the uncommittable P/G/S watchdog proposal with three narrow,
independently testable slices. The P/G/S guardian, authenticated receipt
protocol, and its uncommitted tests are abandoned: they must not be committed,
revived, simplified, or used as a fallback. Their two-strike diagnosis and the
one-shot trace evidence remain preserved as historical evidence of the liveness
failure and of the rejected design, not as authorization for another behavior
patch.

The authority for the implementation inventory is the current `origin/dev`
source at `47aa19a3152b194df97dd8d52aea59d008aa34d1`. The observed governed
local selection remains exactly:

```text
uv run pytest scripts/tests/ tests/ci/ tests/scripts/ tests/unit/scripts/ --ignore=tests/integration --tb=short
```

The historical invocation remained non-terminal for more than 32 minutes. The
new work makes the database fixture and this one impacted invocation bounded;
it does not weaken migration correctness, skip a test, reduce the selected
scope, retry a failure, quarantine a test, bypass the hook, or alter unrelated
pre-push paths.

The three slices are deliberately ordered A → B → C. Each requires its own
focused proof before the next slice changes behavior. A failed proof remains a
failure; it is not a reason to increase a timeout, add a fallback executable,
or restore the P/G/S prototype.

## Shared contract and threat boundary

`config/overlays/prepush-execution-deadline.v1.yaml` is the sole committed
authority for all timing constants. It is parsed repo-relatively, strictly
typed, canonicalized before use, and rejects unknown fields, non-integers,
zero/negative values, and any caller or environment override. The existing
fixed budget remains exactly:

```yaml
schema_version: omnibase-infra.prepush-execution-deadline.v1
impacted_migration_execution:
  pytest_budget_seconds: 2400
  receipt_and_join_budget_seconds: 240
  term_grace_seconds: 30
  kill_reap_seconds: 30
  overall_deadline_seconds: 2700
database_runner:
  pgconnect_timeout_seconds: 10
  server_lock_timeout_seconds: 300
  server_statement_timeout_seconds: 300
  advisory_holder_verify_seconds: 30
  readiness_attempts: 30
  readiness_interval_seconds: 2
  forward_migration_lock_id: 100010
  migration_lock_wait_seconds: 300
  postgres_sigint_grace_seconds: 30
  postgres_sigquit_grace_seconds: 30
```

The v1 schema permits exactly the two mappings and keys shown above; every
field is a JSON/YAML integer, with no null, string, float, implicit default,
or unknown key accepted. The displayed values are the v1 defaults and are
therefore part of the contract, not examples. Validation requires
`2400 + 240 + 30 + 30 == 2700`; each database cap must be positive and no
greater than `overall_deadline_seconds`, and
`migration_lock_wait_seconds <= server_lock_timeout_seconds`. The database
caps are charged within that fixed 2700 seconds, never additive execution
allowances or replacement phase deadlines. In particular, the current ambient
`FORWARD_MIGRATION_LOCK_ID=100010`, `MIGRATION_LOCK_WAIT_SECONDS=300`, and
`PG_WAIT_RETRIES=30` are removed as environment controls and are supplied only
by `forward_migration_lock_id`, `migration_lock_wait_seconds`, and
`readiness_attempts` above. There is no compatibility alias or fallback.

Values are passed directly to the runner; `.env` files, inherited
`PGCONNECT_TIMEOUT`, shell defaults, and tool discovery/fallbacks are not
policy inputs. The runner parses the overlay once before work, canonicalizes
it, and carries that immutable typed object to every child and wait.

Every owned operation records one monotonic start and derives
`remaining = max(0, deadline - monotonic_now)` before a connection, wait, or
reap. A call receives `min(remaining, its overlay cap)` and fails closed when
that value is exhausted. No connection, readiness poll, advisory-lock wait,
database command, graceful stop, KILL/reap, receipt write, or teardown may
start a new relative window.

Migration dispatch is a distinct commit-knowledge boundary. If a migration has
been dispatched and then the runner sees timeout, EOF, signal interruption, or
a lost/malformed receipt before it obtains its required post-dispatch result,
the typed outcome is `unknown_commit` and the enclosing outcome is
`cleanup_uncertain`. It stops immediately: it does not retry or continue
migrations, write a ledger row, set a success sentinel, or make a completion
claim. A later independently designed reconciliation is out of scope; this
plan authorizes no inference from a missing receipt.

This plan does not claim the impossible universal property that a launcher
survives an unexpected launcher `SIGKILL`, kernel panic, host crash, or power
loss without an orphan. In those events there may be no final receipt. The
only claim is bounded cleanup while the runner is alive and retains verified
ownership. A later invocation may perform stale-owned-resource detection only
when it can prove the resource belongs to the prior fixture identity using a
nonce-bound, fixture-local identity record plus a still-matching direct
process/service proof. Otherwise it reports `cleanup_uncertain`, does not
signal, and leaves external resources untouched. It never uses a PID matcher,
numeric-PID reuse guess, process name, broad port scan, or ambient Postgres
configuration as ownership proof.

## Slice A — one runner-owned `psql` seam

Introduce one narrow database-call seam used by every migration fixture DB
operation: readiness, migration invocation, create/drop, advisory-lock probe,
holder verification, and controlled holder termination. No fixture or shell
runner may call `psql` directly after this slice; a structural test rejects new
direct call sites outside the seam.

The seam accepts an already validated target descriptor and the caller's
absolute monotonic deadline. It constructs a fixed argv with `-X` and
`ON_ERROR_STOP`, passes `PGCONNECT_TIMEOUT` explicitly in a minimal child
environment as the integer derived from the per-call remaining budget, and
sets server `lock_timeout` and `statement_timeout` only from the immutable
overlay constants. Before each child launch it strips inherited `PGOPTIONS`,
`PGSERVICE`, `PGSERVICEFILE`, `PGSYSCONFDIR`, every `PG*TIMEOUT` other than its
computed `PGCONNECT_TIMEOUT`, and all `PGHOST`, `PGPORT`, `PGDATABASE`,
`PGUSER`, `PGAPPNAME`, and other target-selection variables. The target is
argv/descriptor data, not environment authority; credentials use the approved
non-ambient descriptor channel and are never rendered in a receipt. No broad
parent environment is copied into a database child.

The seam's child environment contains only the computed
`PGCONNECT_TIMEOUT` plus the fixed, contract-owned server-setting inputs; it
does not merge ambient values. An adversarial `PGOPTIONS` test must prove it
cannot alter server timeout, target, or SQL behavior. Target data is supplied
through the validated descriptor, never resolved from an environment fallback,
a service-discovery probe, or a command-line tool fallback. The seam returns a
typed result with the operation class, bounded normalized exit, elapsed
monotonic observation, and one of `completed`, `timed_out`, `setup_error`,
`unknown_commit`, or `cleanup_uncertain`; it does not expose a connection
string, credential, raw backend PID, or command environment in a receipt.

The advisory-lock contention fixture starts its holder through the same seam,
retains its direct `Popen` handle, and generates a fresh random per-run
`application_name` nonce. Before acting, one query must establish exactly one
row correlating the exact advisory lock in `pg_locks`, the matching
`pg_stat_activity` row, the validated target database identity, the live
direct-holder handle, and that nonce. `pg_terminate_backend` is permitted only
for that one verified holder in the fixture-owned disposable cluster; it is
forbidden for every external configured target. After termination, the runner
must prove lock absence and reap the retained handle. The server-side
termination, client wait, and process reap each use the caller's remaining
budget. Zero/multiple rows, a stale/reused nonce, database or handle mismatch,
lock persistence, failed reap, or any ambiguity is `cleanup_uncertain`; it
never terminates a different backend.

Slice A acceptance tests include:

- `tests/scripts/test_forward_migration_advisory_lock.py` proves every DB call
  uses the seam, explicit `PGCONNECT_TIMEOUT`, and server lock/statement
  settings; hostile `PGOPTIONS`, service files, timeout, and target variables
  cannot change the child invocation.
- A controlled lock holder proves verify → terminate → direct-holder reap only
  after the exactly-one `pg_locks`/`pg_stat_activity`/target/direct-handle/
  nonce proof, including holder exit, timeout, lock-absence, and
  identity-mismatch paths.
- A connection stall, lock stall, and statement stall each consume the one
  absolute deadline and return a typed non-success result without retry.
- An independently created Postgres sentinel is never signalled, even when a
  fixture-owned holder is terminated or an owned cleanup is uncertain.

## Slice B — parity fixture with directly retained `postgres`

Replace the daemonizing `pg_ctl` lifecycle in the parity fixture with a direct,
retained foreground `postgres` `Popen`. `pg_ctl`'s default 60-second wait is
ambient and leak-prone, so it is not used for lifecycle control. The fixture
runner creates its own session before starting fixture-owned children and
resolves `initdb`, `postgres`, `pg_isready`, and `psql` as coherent binaries
from one validated bin directory, never from an ambient `PATH` search. It
records the direct process handle, session/group identity, random data-dir and
server nonces, and a sanitized logical ownership receipt before readiness
begins.

Each fixture owns a unique Unix-socket directory with permissions that exclude
foreign writers and passes that exact socket identity to its direct server and
every client descriptor. Readiness proves the expected data-directory/server
nonce through that socket (or, on a platform where the socket cannot be used,
through a provably reserved listener with equivalent ownership evidence).
Binding, readiness, and client use re-check the ownership receipt so a bind
TOCTOU, stale socket, or foreign endpoint fails closed without a signal.
Readiness is bounded `pg_isready` followed by bounded seam `psql`; neither is
an unbounded sleep/retry loop. `initdb`, direct `postgres`, readiness, every
`psql` call, database create/drop, and stop each use Slice A's validated
descriptor and remaining-budget rule.

It checks only the direct, fixture-created instance. Create/drop executes
through the same `psql` seam. For an owned runner session, teardown is exact
and ordered: SIGINT for the verified direct `postgres` group, bounded wait and
scoped descendant census for only retained owned descendants, SIGQUIT if it is
still live, bounded wait/census again, then SIGKILL only as last-resort cleanup
failure, followed by reap of every retained handle. SIGKILL can never support
a clean-success receipt. Every phase consumes the original deadline. It
records `cleanup_uncertain` if group/leader identity cannot be verified, the
census has an unknown descendant, a child cannot be reaped, or the deadline
expires. No success receipt is issued until retained owned handles are reaped
and the scoped census is empty.

An externally configured Postgres target is a DB-call target only. It has no
fixture-owned direct `Popen`, session, nonce, or leader proof and therefore is
never sent TERM, KILL, `pg_terminate_backend`, `pg_ctl`, or any cleanup signal.
The fixture may fail closed against it but must not claim to have cleaned it.

Slice B acceptance tests include:

- `tests/scripts/test_forward_migration_advisory_lock.py` and
  `tests/scripts/test_node_migration_fence_parity.py` cover init, readiness,
  create, migration, drop, normal stop, TERM-resistant owned child, and
  partial setup boundaries under finite external watchdogs.
- The tests prove `pg_ctl` is absent from the fixture lifecycle and `postgres`
  is retained as a direct child; they assert coherent-bin resolution, owned
  socket/data-directory/server-nonce readiness, bind-TOCTOU fail-closed
  handling, the exact SIGINT → wait/census → SIGQUIT → wait/census →
  last-resort-SIGKILL → reap sequence, and no residual owned
  data/process/control-descriptor holder.
- An external configured target and an unrelated sentinel remain live and
  unsignalled on normal, timeout, setup-failure, and lock-contention paths.
- Capability absence is reported as an explicit unmet local test prerequisite;
  it is not converted into `skip`, retry, quarantine, or a shared-service
  fallback. CI supplies the required disposable capability for mandatory
  coverage.

## Slice C — narrow impacted-pytest launcher

Keep the historical impacted-file predicate, selected directories, exact pytest
argv, `--ignore=tests/integration`, and `--tb=short` unchanged. Only when that
existing predicate selects the historical invocation, call a narrow
POSIX/macOS-compatible launcher. All other hook selections retain their direct
pytest path and are covered by regression tests.

The supported launcher platform list is macOS/Darwin and Linux only; each must
provide the POSIX `setsid`/session and process-group identity semantics
exercised by the platform test matrix. Unsupported platforms, missing
primitives, or any unverifiable leader/session/group relation fail closed
before launching. The launcher reads the canonical overlay once, computes
exactly one launch-time monotonic deadline of 2700 seconds, and starts the
selected pytest command as its retained direct child in a new owned session.
Before TERM or KILL it must prove the retained child is still the session/group
leader it created; it never uses `kill(0)`, signals its parent group, or
signals a group it did not start and verify. It does not invoke `timeout`,
`gtimeout`, `perl`, a shell alias, a process-name matcher, or an ambient tool
fallback. On ordinary completion it preserves pytest's result. On deadline, it
sends TERM only to its verified owned child session/group, waits only for the
remaining `term_grace_seconds`, sends KILL only if the original owned-session
proof remains valid, reaps the direct child within the remaining
`kill_reap_seconds`, and emits a bounded sanitized typed receipt. The receipt
is `timeout` only with verified owned cleanup; missing ownership, missing reap,
launcher interruption, or unavailable receipt is `cleanup_uncertain` and a
non-success exit. No parent-side or launcher-side signal is ever directed at a
payload group it did not start and verify.

The launcher receipt contains only the schema version, run nonce, selected
path class, monotonic outcome, typed outcome, normalized child result, and
logical cleanup proof. It contains no argv, environment, path, raw PID/PGID,
endpoint, credential, SQL, or traceback. A next invocation first checks for a
stale nonce-bound owned-resource marker. It handles that marker only with the
safe identity proof described above; otherwise it reports uncertainty and
does not signal.

Slice C acceptance tests include:

- `tests/unit/scripts/test_prepush_smart_tests_seam.py` proves the unchanged
  historical predicate and exact argv; focused ordinary selections do not
  enter the launcher.
- `tests/ci/test_prepush_hook_pinned_interpreter.py` proves the existing
  interpreter/hook contract remains intact.
- A controlled owned pytest child verifies normal zero/nonzero propagation,
  timeout with graceful TERM/reap, TERM-resistant owned KILL/reap, partial
  spawn/receipt failure, launcher interruption, unsupported/unverifiable
  platform failure, and no numeric PID/PGID, `kill(0)`, parent-group, or
  tool-fallback path.
- A simulated launcher `SIGKILL`/host-loss marker proves no false cleanup
  claim; a later run handles it only with safe nonce/ownership proof and leaves
  an unrelated sentinel untouched otherwise.
- The governed historical selection is exercised under a finite external
  watchdog with migration parity coverage and no residual fixture-owned
  process or service. It may not skip, retry, or quarantine the migration
  test.

## Historical evidence retained, not revived

The following diagnosis invocations and results remain attached to the
abandoned prototype record and must not be reframed as production proof:

```text
gtimeout -k 2 30 uv run pytest tests/unit/scripts/test_prepush_impacted_migration_watchdog.py -q --tb=short -k synthetic_origin_ready_barrier_produces_paired_deterministic_traces
gtimeout -k 2 30 uv run pytest tests/unit/scripts/test_prepush_impacted_migration_watchdog.py -q --tb=short -k trace_loss_and_incomplete_terminal_markers_invalidate_evidence
gtimeout -k 2 90 uv run pytest tests/unit/scripts/test_prepush_impacted_migration_watchdog.py -q --tb=short -k shared_pytest_deadline_uses_term_then_a_correlated_group_empty_receipt
```

Those tests produced bounded evidence for the rejected design, including the
one-shot `wrapper_deadline_terminated`/124 capture. They do not authorize an
implementation change and are not copied into the replacement launcher. The
new slices must establish their own direct ownership and residual-cleanup
proofs without P/G/S correlation machinery.

## Rollout and completion gates

1. Land Slice A with its seam and tests before any fixture lifecycle or hook
   change. The canonical overlay validator and no-ambient-input tests pass.
2. Land Slice B only after Slice A passes in disposable CI coverage. The direct
   `postgres` fixture and external-target non-signalling proof pass repeatedly.
3. Land Slice C only after A and B are stable. Historical selection/argv and
   unrelated hook paths remain byte-for-byte equivalent at their seam.
4. Before behavioral tests, add a static audit that enumerates every `psql`,
   `pg_ctl`, `PATH` lookup/mutation, and skip-control call in the migration
   runner, parity fixture, and hook. It must prove every allowed `psql` use
   routes through the one seam, no `pg_ctl` lifecycle remains, only
   coherent-bin resolution is used, and committed migration skip manifests are
   unchanged and cannot be bypassed; an unclassified call fails the audit.
5. Run Ruff, strict mypy for changed Python, shell syntax/ShellCheck for the
   hook, focused tests above, relevant migration parity tests, pre-commit, and
   the governed pre-push path under a finite external watchdog.
6. Independent review verifies the three ownership boundaries, canonical
   overlay parsing, no ambient override/fallback, typed uncertainty, exact
   direct-`postgres` stop paths, external-target containment, stale-marker
   proof guard, `unknown_commit` containment, static-audit completeness, and
   absence of skip/retry/quarantine behavior.

No deployment, shared runtime mutation, database mutation, service stop, or
activation is authorized by this plan. # sanitization-ok: plan identifies a governed remediation without runtime authority
