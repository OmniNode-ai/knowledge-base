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

The authority for the implementation inventory is the freshly fetched
`origin/dev` source at `e201622802db08bb2a0cbbd8ea4627ad0bb0b24e`. The observed governed
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

## Prerequisite A0 — non-ambient resolution and image provenance gate

The current runner receives database endpoints and passwords through process
environment/compose injection, and no existing non-ambient descriptor channel
or credential-capability resolver owns this use case. `TransportConfigMap`
intentionally excludes database credentials; its overlay helpers are not an
authority to put credentials into another process environment. Therefore no
Slice A runner, fixture, image, or behavior change is authorized until A0
lands a dedicated `prepush-migration-runner-resolution.v1` contract and its
typed resolver. This is a prerequisite gate, not an environment-to-descriptor
adapter and not a compatibility path.

The committed overlay names only logical authority references. A0 defines the
exact provider protocol: `resolve(ResolutionRequest, WorkloadIdentityHandle)
-> ResolutionResult`, where the request is the canonical authority ref plus
the ordered target/secret refs from the overlay and no caller-provided target
or secret field. The result is only in-memory
`ResolvedTargetCapability`/`SecretStr` values or a closed failure code; it
never returns or writes an environment mapping, a connection string, a file
path, or a serializable descriptor. Endpoint coordinates are fields of the
capability, not ambient configuration. The execution platform hands the
provider client one nonserializable `WorkloadIdentityHandle` at runner
bootstrap; the runner neither reads nor forwards an identity token, and the
handle is absent from environment, argv, files, logs, receipts, and mounts.

A0 must commit one reviewed provider-selection artifact before the protocol is
used. Its schema records `schema_version`, provider kind and protocol version,
the workload-identity audience/subject-class, allowed authority reference,
ordered logical-reference grammar versions, and the SHA-256 of the selected
provider client and its policy bundle—never a provider endpoint, token, target,
or secret. The resolver emits only a sanitized
`prepush-migration-resolution-receipt.v1` containing schema version, canonical
request hash, provider-selection-artifact hash, ordered logical-reference
hashes, closed outcome codes, and canonical receipt SHA-256. A receipt lacking
any required hash fails closed. Compose configuration, process/image
inspection, `.env` files, logs, command arguments, and mounted plaintext
configuration must contain no password or secret material. Endpoint
capabilities are non-ambient in-memory authority objects, not
committed/configured defaults; a fixed child argv may carry only the resolved
non-secret target coordinates required by libpq. Tests use an in-memory fake
provider and synthetic capabilities only. Until the selection artifact exists,
this direct gate definition is authoritative; no separate A0 plan is cited.

A0 also generates and commits an image-lock/provenance artifact before any
image is referenced. The artifact must record the exact base-image digest,
Python minor, PostgreSQL-16 client package/version, package repository
snapshot and hash provenance, and wheel/source version plus SHA-256 for the
YAML parser, Pydantic/`SecretStr` implementation, selected provider client,
and every transitive dependency. It records SHA-256 for each baked runner,
seam, resolver, overlay artifact, the complete recursively sorted migration
tree, `_ledger` bootstrap/alias/adoption inputs, and every staged COPY input.
The tree record contains each logical relative name and content hash plus a
canonical aggregate hash, so a changed or omitted input cannot inherit an
image receipt. It verifies that the runtime image contains those hashes and
has no source-volume fallback. The build emits an immutable digest receipt;
the consumer-config audit proves every catalog, compose, infrastructure,
judge, Lakshman, stability, and production reference equals that receipt, uses
no mutable tag, and has no stale bind mount or alternate image/client path.
There are no trustworthy current pins for this new image, so a generated,
reviewed lock is an A0 acceptance artifact—not a placeholder to be filled in
during Slice A.

## Shared contract and threat boundary

`config/overlays/prepush-execution-deadline.v1.yaml` is the sole committed
authority for timing constants and for the runner's configuration references.
It is parsed repo-relatively, strictly typed, canonicalized before use, and
rejects unknown fields, non-integers, zero/negative values, and any caller or
environment override of a resolved value. The existing fixed budget remains
exactly:

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
  resolution:
    authority_ref: "authority://prepush-migration-runner-resolution.v1"
    target_capability_refs:
      primary: "capability://prepush-migration/primary-target.v1"
      node: "capability://prepush-migration/node-target.v1"
      analytics_reconnect: "capability://prepush-migration/analytics-reconnect-target.v1"
    optional_source_target_capability_refs:
      cloud_history:
        capability_ref: "capability://prepush-migration/cloud-history-source-target.v1"
        required: false
    secret_refs:
      migration_admin: "secret://prepush-migration/admin-password.v1"
      cloud_history_read:
        secret_ref: "secret://prepush-migration/cloud-history-read-password.v1"
        required: false
      login_reassertions:
        runtime_login:
          secret_ref: "secret://prepush-migration/runtime-login-password.v1"
          required: false
        tenant_writer_login:
          secret_ref: "secret://prepush-migration/tenant-writer-login-password.v1"
          required: false
```

The `resolution` mapping is the canonical contract-overlay authority. Its
logical `authority://`, `capability://`, and `secret://` values are closed
allowlists, are opaque identifiers rather than resolver locations, and never
embed a password, endpoint, connection string, path, inline default, or
environment variable name. A required reference that cannot resolve fails
closed; the two explicitly optional login references retain absent-means-no-
login-reassertion behavior, while the optional cloud target/read-secret pair
is atomically both absent or both resolved. A0's typed resolver is the only
authority allowed to turn those names into capabilities or `SecretStr` values.
It replaces all password-bearing runner environment, `.env`, compose
interpolation, and
process/image-inspect inputs; endpoint selection is likewise capability-owned
and non-ambient. No `TransportConfigMap`, generic overlay environment-apply,
service discovery, or command-line fallback participates.

The v1 schema permits exactly the mappings and keys shown above; timing fields
are JSON/YAML integers, with no null, string, float, implicit default, or
unknown key accepted. Reference fields use the three closed logical-reference
grammars and are not timing values. The displayed numeric values are the v1
defaults and are therefore part of the contract, not examples. Validation requires
`2400 + 240 + 30 + 30 == 2700`; each database cap must be positive and no
greater than `overall_deadline_seconds`, and
`migration_lock_wait_seconds <= server_lock_timeout_seconds`. The database
caps are charged within that fixed 2700 seconds, never additive execution
allowances or replacement phase deadlines. In particular, the current ambient
`FORWARD_MIGRATION_LOCK_ID=100010`, `MIGRATION_LOCK_WAIT_SECONDS=300`, and
`PG_WAIT_RETRIES=30` are removed as environment controls and are supplied only
by `forward_migration_lock_id`, `migration_lock_wait_seconds`, and
`readiness_attempts` above. `analytics_reconnect` is the only capability that
may satisfy a manifest-approved native reconnect. `cloud_history` is absent
only when the declared optional source capability and its paired read secret
are both absent; a declared-but-unresolvable source fails closed. There is no
default source target and no compatibility alias or fallback, including no
`OMNINODE_CLOUD_HISTORY_DB` environment input.

Values are passed directly to the runner; `.env` files, inherited
`PGCONNECT_TIMEOUT`, shell defaults, and tool discovery/fallbacks are not
policy inputs. The runner parses the overlay once before work, canonicalizes
it, and carries that immutable typed object to every child and wait.

All timing arithmetic is integer monotonic nanoseconds. At every transition,
`R_ns = max(0, deadline_ns - monotonic_ns())`. For an operation with overlay
cap `O_s`, its retained-child process allowance is
`P_ns = min(R_ns, O_s * 1_000_000_000)`; a zero `P_ns` fails before spawn and
the child/reap sequence cannot receive a replacement allowance. Separately,
the libpq connect cap is exactly
`C_s = min(floor(R_ns / 1_000_000_000),
pgconnect_timeout_seconds, floor(P_ns / 1_000_000_000))`. The validated v1
default for `pgconnect_timeout_seconds` is 10, but the formula uses the typed
overlay field rather than a literal. The call fails before spawn when `C_s <
2`, because libpq's minimum valid connect timeout is two seconds; it never
rounds up or emits zero/one. Thus remaining values of 1.999 seconds, 2.000
seconds, and 2.999 seconds produce respectively fail-closed, `2`, and `2` for
`PGCONNECT_TIMEOUT` when the process allowance and overlay cap are at least
those values.

`O_s` comes from a closed operation map, not a caller choice: connection-only
`readiness` and `database_exists` use `pgconnect_timeout_seconds`; migration
application, migration/ledger records and probes, and controlled create/drop
use `overall_deadline_seconds`; and every advisory holder probe, verify,
terminate, wait, or reap uses `advisory_holder_verify_seconds`. The server
lock and statement settings are intentionally absent from that map: they are
per-connection server caps, not a replacement process window. An operation
may use only its listed cap and the one run deadline; it cannot borrow another
operation's cap or restart after an internal reconnect.

The two server caps are also independent of process allowance:
`L_ms = min(floor(R_ns / 1_000_000), server_lock_timeout_seconds * 1000)` and
`S_ms = min(floor(R_ns / 1_000_000), server_statement_timeout_seconds * 1000)`.
If either is zero, the call fails before spawn. Holder verification uses
`V_ns = min(R_ns, advisory_holder_verify_seconds * 1_000_000_000)` and has no
right to start a new wait after `V_ns` expires. The operation cap is a
client-side elapsed-time allowance, not a second server budget. The seam
retains and reaps the direct `psql` child against `P_ns`; `L_ms` and `S_ms`
bound one lock wait or statement on every connection but never add time to
that child allowance or create a new multi-connection budget.

Tests use exact integer-boundary clocks: at remaining 1.999, 2.000, and 2.999
seconds, `P_ns` is respectively 1,999,000,000, 2,000,000,000, and
2,999,000,000 (subject only to the smaller operation cap); `C_s` is fail,
2, and 2; `L_ms`/`S_ms` are 1999, 2000, and 2999 before their configured
maximum; and `V_ns` is 1,999,000,000, 2,000,000,000, and 2,999,000,000 before
its configured maximum. They also prove a smaller `O_s` or verification cap
only lowers its own formula and never increases another allowance. No wall
clock, float, ceiling, rounding-up, or post-expiry fresh deadline is allowed.

The seam generates `PGOPTIONS` in exactly this token order:
`-c lock_timeout=<L_ms>ms -c statement_timeout=<S_ms>ms`; a fixture holder
appends only `-c application_name=<generated-nonce>`. No value is rounded up,
parsed from a caller, or inherited from the environment.

`PGOPTIONS` is safe here only as a seam-generated value: its tokens are
rendered solely from validated integers (and, for a fixture holder, a
generated restricted-alphabet nonce) and never parsed from a caller. libpq
uses it for every connection opened by that `psql` process, including a native
positional `\connect`. A fresh exact environment makes it the only libpq
default source; fixed argv supplies the initial target, the descriptor supplies
authentication, and the approved corpus supplies no conninfo which could
override `PGOPTIONS`. There is no impossible production claim to inspect
settings after an arbitrary file-driven reconnect. The preflight scanner proves
the only allowed reconnect form, and libpq applies the fixed startup options to
each connection opened by that `psql` process. A controlled test stream with
an explicit fixed `SHOW` template verifies that startup behavior for the
initial and approved reconnect paths; production migration streams do not add
an after-every-connect query.

Before Slice A implementation, a checked-in
`config/validation/prepush-migration-psql-corpus.v1.yaml` is generated against
source commit `e201622802db08bb2a0cbbd8ea4627ad0bb0b24e`. It covers **every**
SQL file in the recursive forward migration tree and all ledger SQL, including
`_ledger/bootstrap.sql`, not merely files containing `\connect`. Every entry
contains logical relative path, SHA-256, artifact class (`flat`, `node`, or
`ledger`), expected initial target capability, expected reconnect target
capability when present, and its exact permitted psql token set. An unlisted
SQL file, byte change, target-capability mismatch, or psql token fails closed;
a source update requires a new reviewed manifest, never an automatic allowlist
update. The five native-reconnect entries are:

| Migration path | SHA-256 |
| --- | --- |
| `docker/migrations/forward/083_create_log_entries.sql` | `f6c0dc58ef0c26138cb89fae29b4f0cec3d133d7cc6e3f2d5db83d7238df7417` |
| `docker/migrations/forward/096_grant_role_omnidash_omnidash_analytics.sql` | `a5d933f1ef58dc92ad46f92ac9d6cbe061b873165170cb5d6d200a489cb02fe2` |
| `docker/migrations/forward/097_grant_app_dashboard_connect_omnidash_analytics.sql` | `591898102e9b092c89194b4e9398cbb926eee546e6099232131b0b3184a7a154` |
| `docker/migrations/forward/098_create_omninode_internal_schema.sql` | `3f6bdaaad85108b10438002aae2a5c4b8f4550eb8e2a400c7b769589d45142b6` |
| `docker/migrations/forward/099_create_omninode_internal_live_events.sql` | `f601eab00c2d069590304a5aa511513f4bb2c3425239a58aee8541edbc87f598` |

Each of those five entries declares `primary` as its expected initial target
capability and `analytics_reconnect` as its expected reconnect capability;
the manifest stores logical capability IDs, never endpoint values. Every other
entry must declare its expected initial `primary` or `node` capability and has
no reconnect capability.

The audit uses a real psql/SQL lexical scanner, not a grep or regular
expression: it recognizes quoted identifiers, SQL strings, dollar-quoted
strings, quoted and nested comments, statement boundaries, and psql
line-metacommands. It permits only a manifest-listed single-token positional
`\connect`, which must resolve to that entry's expected target capability;
every conninfo/URI/option alias and every other `\connect` argument fails. It
rejects `\set`, `\setenv`, `\!`, `\i`, `\ir`, `\o`, `\g`, `\gexec`, `\gset`,
`\copy`, shell/file/read/write escapes, and every other psql metacommand,
except the one byte-pinned `_ledger/bootstrap.sql` form `\set ON_ERROR_STOP
on` (SHA-256 `977581136aeec828378ecbf75f096816c894ff41617f0ec58f82a5543697dd92`).
It rejects `\set ON_ERROR_STOP off` in every spelling. It also rejects SQL
`COPY ... PROGRAM`, every `SET`, `SET LOCAL`, `RESET`, `ALTER ROLE`, or `ALTER
DATABASE` which changes, clears, or aliases `lock_timeout` or
`statement_timeout`. The manifest's pin is deliberately stricter than a
semantic exception: no migration may lower, raise, reset, or replace either
seam cap. Corpus tests contain comments/quoted/dollar-quoted lookalikes plus
real aliases and injection forms to prove the lexer—not textual coincidence—
makes the decision. This preserves the known trusted reconnect behavior
without letting a migration or caller replace the cap.

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

Slice A replaces the direct-`psql` shell runner with one
`PrepushDatabaseRunner` and one `DatabaseCallSeam`, but it cannot start until
A0's reviewed image lock exists. A0 must lock a minimal Debian/bookworm final
image by exact digest, Python **3.12.x** minor-and-patch version, PostgreSQL 16
client package/version, package-repository snapshot identifier and SHA-256,
and all A0-locked parser, Pydantic/`SecretStr`, provider-client, and transitive
dependency versions/hashes. The image has only that client, the fixed
interpreter, seam/overlay/resolver/runner artifacts whose baked SHA-256s
appear in the lock, and those locked dependencies. It has no source mount
fallback and must not reuse a broad runtime or CI image. The gate's build
receipt supplies the one immutable `tag@digest`; only after review may every
catalog, compose, infrastructure, judge, Lakshman, stability, and production
reference be changed to exactly that receipt. Until then, the plan authorizes
neither an unpinned image nor a guessed package pin. Compose uses the fixed
interpreter and `psql` paths from the locked image directly, never finding
Python, `psql`, `timeout`, or another executable through `PATH`. CI first
asserts the exact locked Python/`psql` versions, module import, baked hashes,
and reference equality, then runs behavior tests. This changes neither the
server image nor service topology and does not take on Slice B lifecycle work.
The direct shell runner is removed rather than retained as a fallback.

`DatabaseCallSeam` is the sole database-child dispatcher for the migration
runner and the two governed script fixtures:
`tests/scripts/test_forward_migration_advisory_lock.py` and
`tests/scripts/test_node_migration_fence_parity.py`. Every `psql` readiness,
migration application, ledger probe/write, create/drop, advisory probe,
holder start, holder verification, and controlled backend termination in those
three owners enters through this seam. A request contains only a closed
operation enum, a validated `DatabaseTargetDescriptor`, a typed payload
(`stdin`, a validated migration file, or scalar-query mode), and an absolute
monotonic deadline. It has no arbitrary argv, environment, connection string,
executable, or target-override field.

`DatabaseTargetDescriptor` is an in-memory, non-serializable projection of a
`ResolvedTargetCapability`: logical capability identifier plus validated host,
integer port, database, and user fields, with no password or connection string.
The fixed argv is exactly
`[locked_psql_absolute_path, "-X", "-v", "ON_ERROR_STOP=1", "-h", host,
"-p", canonical_decimal_port, "-U", user, "-d", database]` followed only by
the closed mode tail: `("-f", validated_manifest_file)` for a byte-pinned
migration, or no tail for fixed scalar/stdin SQL. `locked_psql_absolute_path`
is an exact image-lock field, never a `PATH` lookup. SQL travels on stdin or a
validated migration file, never an arbitrary `-c`/argv value. Only the seam
may spawn/reap a `psql` child.

Scalar mode is not an arbitrary query escape hatch. The complete closed map
below covers every non-stream `psql` expression in the 19-call inventory.
`flat_apply` and `node_apply` are byte-pinned file mode; canonical-ledger and
cloud-history movement use the separately specified typed COPY streams below.

| Operation | Fixed template | Typed parameters | Allowed `-v` names |
| --- | --- | --- | --- |
| `readiness` | `SELECT_ONE_V1` | none | none |
| `migration_lock_held`, `acquire_migration_lock` | `MIGRATION_LOCK_HELD_V1`, `MIGRATION_LOCK_ACQUIRE_V1` | `Int64LockId` | `lock_id` |
| `database_exists`, `controlled_database_drop` | `DATABASE_EXISTS_V1`, `DATABASE_DROP_V1` | `DatabaseIdentifier` | `database_name` |
| `ensure_directive_database` | `DATABASE_EXISTS_V1` then `DATABASE_CREATE_V1` only when absent | `DatabaseIdentifier` | `database_name` |
| `ensure_service_ledger` | `SERVICE_LEDGER_ENSURE_V1` | `StreamName` where declared | `stream_name` where declared |
| `migration_is_applied`, `already_applied_probe` | `MIGRATION_APPLIED_V1` | `StreamName`, `MigrationVersion` | `stream_name`, `migration_version` |
| `record_migration`, `flat_ledger_record`, `skip_manifest_record` | `MIGRATION_RECORD_V1`, `FLAT_LEDGER_RECORD_V1`, `SKIP_MANIFEST_RECORD_V1` | `StreamName`, `MigrationVersion`, `MigrationChecksum` | `stream_name`, `migration_version`, `migration_checksum` |
| `reassert_login_only_role_credential` | `ROLE_LOGIN_PASSWORD_REASSERT_V1` | `RoleIdentifier`, `SecretStr` | `role_name` only; never the secret |
| `top_level_sentinel_clear`, `top_level_sentinel_final` | `TOP_LEVEL_SENTINEL_CLEAR_V1`, `TOP_LEVEL_SENTINEL_FINAL_V1` | `StreamName`, `MigrationVersion` | `stream_name`, `migration_version` |
| `advisory_holder_probe`, `advisory_holder_verify`, `advisory_holder_absence` | `ADVISORY_HOLDER_PROBE_V1`, `ADVISORY_HOLDER_VERIFY_V1`, `ADVISORY_HOLDER_ABSENCE_V1` | `Int64LockId`, `RunNonce` | `lock_id`, `run_nonce` |
| `advisory_holder_terminate_verified` | `ADVISORY_HOLDER_TERMINATE_VERIFIED_V1` | `Int64LockId`, `RunNonce`, opaque backend-start identity | `lock_id`, `run_nonce` |

These are the only scalar templates. `ON_ERROR_STOP=1` is the one fixed
seam-owned `-v` value; it cannot be changed or duplicated. The sole permitted
caller-parameter variable names are exactly `database_name`, `stream_name`,
`migration_version`, `migration_checksum`, `role_name`, `lock_id`, and
`run_nonce`, and each template declares its subset; no caller may add `-v`,
change a key, provide SQL, or select a format/query flag. Values are parsed
into named types before rendering through psql's typed quoting form, not string
concatenation. A `SecretStr` is never a `-v` value: the reassertion template's
secret slot is rendered by a tested SQL-literal encoder to its one-time stdin
payload and the pipe is closed/reaped with the child. Tests try quotes,
backslashes, dollar signs, newlines, metacommands, option-looking values,
invalid identifiers, unlisted `-v` keys, raw SQL, and secret-shaped payloads
to prove rejection or safe stdin-only binding before spawn.

`ensure_directive_database` is intentionally a two-operation replacement for
the current generated-SQL/`\gexec` call: `DATABASE_EXISTS_V1` returns a
`BoolValue`, and only `false` permits the separate mutating
`DATABASE_CREATE_V1` with the same validated `DatabaseIdentifier`. It has no
`\gexec`, dynamic SQL result, arbitrary command string, or caller-selected
target. A failed/timeout read is not evidence of absence; a dispatched create
that lacks a well-formed success result is `unknown_commit`.

The checked-in semantic inventory makes the 19-source-call baseline executable
by recording this exact replacement map, including target capability and
mutability:

| Baseline line | Replacement operation | Target capability | Mutability |
| --- | --- | --- | --- |
| 411 | `readiness` | `primary` | `read_only` |
| 458 | `migration_lock_held` | `primary` | `read_only` |
| 505 | `acquire_migration_lock` | `primary` | `mutating` |
| 574 | `ensure_directive_database` → exists/create pair | `primary` | read/mutating pair |
| 794 | `canonical_ledger_session` | `node` | `mutating` |
| 868 | `migration_is_applied` | `node` | `read_only` |
| 932 | `record_migration` | `node` | `mutating` |
| 954 | `database_exists` | `primary` | `read_only` |
| 970 | `ledger_stage_import` | `node` | `mutating` |
| 1068 | `cloud_history_export` | `cloud_history` | `read_only` |
| 1338 | `reassert_login_only_role_credential` | `primary` | `mutating` |
| 1384 | `ensure_service_ledger` | `primary` | `mutating` |
| 1402 | `top_level_sentinel_clear` | `primary` | `mutating` |
| 1437 | `skip_manifest_record` | `primary` | `mutating` |
| 1446 | `already_applied_probe` | `primary` | `read_only` |
| 1459 | `flat_apply` | `primary`, plus manifest-approved `analytics_reconnect` only | `mutating` |
| 1462 | `flat_ledger_record` | `primary` | `mutating` |
| 1564 | `node_apply` | `node` | `mutating` |
| 1593 | `top_level_sentinel_final` | `primary` | `mutating` |

`canonical_ledger_session` replaces the current multi-`-c`/`\copy` sequence
as one mutating stdin session to `node`. It writes the fixed temporary-table
DDL, then exactly six text/tab frames in this order:
`COPY onex_application_migration_manifest FROM STDIN WITH (FORMAT text,
DELIMITER E'\t')`; `COPY onex_legacy_node_migration_declarations FROM STDIN
WITH (FORMAT text, DELIMITER E'\t')`; and the same `FORMAT text, DELIMITER
E'\t'` protocol for `onex_verified_checksum_adoptions`,
`onex_verified_divergent_adoptions`, `onex_verified_cross_source_adoptions`,
and `onex_verified_canonical_adoptions`. Each source is a `BoundedCopyInput`
with a declared schema, delimiter, maximum bytes/rows, canonical content
SHA-256, and pre-parse validation; an unknown column, malformed row, oversize
stream, or hash mismatch fails before `Popen`. The frame data is emitted
through a private stdin pipe followed by the generated psql `\.` terminator,
then the preflight-pinned ledger bootstrap bytes. The terminator is transport
framing generated solely by the seam—not a corpus metacommand a
migration/caller can supply. There is no `-c`, `\copy`, filesystem read by
`psql`, or caller file path in this session.

Cloud history is a paired, non-ambient stream protocol. When the optional
`cloud_history` capability is present, `cloud_history_export` connects only to
that source capability, uses a bounded/hashed alias `BoundedCopyInput`, and
first sends `COPY onex_cloud_migration_alias FROM STDIN WITH (FORMAT text,
DELIMITER E'\t')`, then runs one fixed read-only stream ending `COPY
onex_cloud_migration_export TO STDOUT WITH (FORMAT csv)`. The seam parses the private output as a
`BoundedCopyStream` with exactly the declared CSV columns, maximum bytes/rows,
validated checksums/enums/timestamps, row count, and content SHA-256; raw
stdout never reaches a caller or file. `ledger_stage_import` then accepts only
that internal typed stream on the `node` destination capability, emits `COPY
onex_migration_import_stage FROM STDIN WITH (FORMAT csv)` and its generated
`\.` terminator, then executes the fixed validation/insert template in the
same mutating session. Source export timeout/failure is `timed_out`/`failed`; once
destination import is dispatched, every abnormal terminal state is
`unknown_commit`. There is no temporary stage file, `\copy`, source-database
environment variable, default source database, arbitrary `-c`, or user-supplied
COPY command.

Bootstrap calls A0's `prepush-migration-runner-resolution.v1` resolver once;
it has no ambient target, role, password, `.env`, compose, service-discovery,
or command-line input. The resolver returns only the policy-requested
in-memory `ResolvedTargetCapability` and `SecretStr` values. The runner
validates their fields and creates a closeable `RunnerCredentialDescriptor`.
It must not export a password-bearing runner environment variable or write a
password to an environment file; the production resolver transport is outside
the runner's process/compose/image-inspection boundary. Optional
login-reassertion secrets remain in memory only long enough to produce one
stdin payload; they are never argv values, child-environment values, receipts,
or raw output.

The descriptor creates a new private directory with mode `0700`, then creates
its `PGPASSFILE` using `O_CREAT|O_EXCL|O_NOFOLLOW`, applies and verifies mode
`0600` **before** writing, and never follows or reuses a name. For every
required primary/node/analytics-reconnect tuple and the optional resolved
cloud-history-source tuple `(host, port, database, user, password)`, it rejects
LF, CR, and NUL in every field, rejects an exact duplicate tuple (including a
duplicate password target with a different password), and emits rows in a
deterministic ascending UTF-8 byte order of `(host, canonical-decimal port,
database, user)`; a tie on those four connection fields is rejected before a
password could choose an order. It emits no wildcards; it escapes backslash and
colon per libpq before its one row write. The implementation checks that each
required primary and node target yields exactly one distinct row and that each
optional tuple appears only with its paired resolved capability and secret.
`PGPASSFILE` is the channel because libpq consults it
for both the initial connection and native `\connect`; unlike an inherited FD
or `/proc` path, this private-file mechanism works on macOS, Linux, and CI. It
remains until every child that can consult it has been reaped.

Any mkdir/open/mode-check/write/flush/fsync/close failure before a child is
started attempts close → unlink → rmdir immediately. A setup error is reported
only when that cleanup is proven; a partial create, missing cleanup proof, or
failure in normal/exception/signal cleanup is `cleanup_uncertain` and forbids a
success receipt. The descriptor never logs its path or contents and permits no
inherited-FD, `/proc`, stale-file scavenger, credential receipt, debug dump,
or secret-bearing error echo.

Each database child receives a freshly constructed environment with exactly
three keys and no inherited parent mapping:
`PGPASSFILE=<descriptor-private-path>`,
`PGCONNECT_TIMEOUT=<C_s decimal>`, and
`PGOPTIONS=<seam-generated tokens>`. `LANG`, `LC_ALL`, `HOME`, and `TZ` are
absent; the seam uses fixed ASCII/byte serialization so its outputs do not
depend on locale or timezone. The fixed absolute executable paths mean `PATH`
is absent too. In particular, `PGPASSWORD`, `PGHOST`, `PGHOSTADDR`, `PGPORT`,
`PGDATABASE`, `PGUSER`, `PGSERVICE`, `PGSERVICEFILE`, `PGSYSCONFDIR`,
`PGOPTIONS`, `PGSSL*`, `PGTARGETSESSIONATTRS`, `PGREQUIREAUTH`, every other
`PG*` system/configuration variable, and all target/timeout aliases are absent
rather than stripped after inheritance. The fixed argv supplies the target.
Acceptance tests assert the complete three-key map and inject each hostile
variable above (including system-configuration variables) to prove it cannot
change target, authentication, TLS, timeout, or SQL behavior.

A holder's restricted-alphabet nonce is appended by the seam to generated
`PGOPTIONS`, not supplied as a fourth environment exception. Hostile ambient
libpq inputs therefore cannot change target, authentication source, timeout,
or SQL behavior.

Every closed operation declares `mutability` as either `read_only` or
`mutating`. `read_only` includes readiness, `database_exists`, ledger/already-
applied probes, lock-held probes, holder proof/absence verification, and cloud
history export. `mutating` includes lock acquisition, database/ledger/sentinel
create-or-write, role reassertion, every migration application, every COPY
import, and verified backend termination. The inventory records that class per
callsite; there is no inferred default.

The seam returns the closed, discriminated `DatabaseCallResult` protocol with
`schema_version="prepush-database-call-result.v1"`: closed `operation`,
`mutability`, `dispatch_state`, `terminal_state`, normalized child result,
bounded elapsed monotonic milliseconds, logical child-reap state, and one
closed `LogicalPayload` union. `not_dispatched` means no child was created;
`dispatched` means `Popen` returned successfully and is recorded immediately,
before any stdin byte is written or migration file is interpreted. This
conservative process-start transition is the only commit-knowledge boundary for
every mode. `terminal_state` is one of `completed`, `failed`, `timed_out`,
`setup_error`, `unknown_commit`, or `cleanup_uncertain`; normalized child result
is only `zero`, `nonzero`, `signal`, `eof`, `partial_stdin`,
`malformed_result`, or `not_started`.

`LogicalPayload` is exactly `None`, `BoolValue`, bounded `IntValue`, bounded
validated `TextValue`, `LedgerProbeRow`, `HolderProofRow`, or
`TargetIdentityValue`, or private `BoundedCopyStreamHandle`. `BoolValue` serves
`database_exists`; `LedgerProbeRow` contains only validated
stream/version/checksum-kind/checksum/owner/provenance fields needed for ledger
decisions; `HolderProofRow` contains only the holder proof booleans and
nonce/capability identities; and `TargetIdentityValue` contains only a logical
capability identity comparison. `BoundedCopyStreamHandle` is an opaque,
single-consumer seam handle carrying only schema ID, row count, byte count, and
content SHA-256 in the result; its validated bytes remain private to the seam
and can feed only its paired destination operation. The seam captures a bounded
private wire stream, parses it against the operation's exact schema, and
returns this union; it never exposes raw stdout, stderr, descriptor, endpoint,
command, raw PID, backend ID, environment, SQL, or credential.

Only a well-formed, reaped, zero child result may be `completed`. After
`dispatched`, a `mutating` operation with nonzero exit, signal, timeout, stdin
EOF, partial stdin write, missing/malformed result, or runner interruption is
`unknown_commit`; if cleanup/reap is not proven, its enclosing result is
`cleanup_uncertain`. The enclosing migration/run result is also
`cleanup_uncertain` whenever a member is `unknown_commit`, even if its child
was reaped: commit knowledge, not merely process ownership, is uncertain. It
stops immediately and performs no later ledger write, success/sentinel write,
completion claim, or retry. A `read_only` operation
with a deadline expiry is explicitly `timed_out`; its nonzero, signal, EOF, or
malformed result is `failed` unless cleanup itself is unproven. It never claims
`unknown_commit`. Before dispatch, a failure is `setup_error` only if descriptor
cleanup is proven; otherwise it is `cleanup_uncertain`. A long-lived advisory
holder is represented by a typed owned capability whose only lifecycle
operations are seam-mediated verify, wait, and reap.

The advisory-lock fixture creates a holder only through a private
`FixtureOwnershipCapability`. Its factory is available only while it creates a
fixture-owned disposable target; it issues an unguessable 256-bit opaque token
held in a private registry and never serializes it into configuration, a
result, or a public fixture API. A configured external target can never obtain
that capability, so a test double cannot forge lifecycle authority merely by
claiming a target class. Each holder additionally creates
`run_nonce = "pmh_" + 32 lowercase hexadecimal characters` from 128 bits of
cryptographic entropy. The closed holder-proof result schema is
`prepush-db-holder-proof.v1` with `outcome` (`verified`, `absent`,
`ambiguous`, or `cleanup_uncertain`), `run_nonce`, logical target-capability
identifier, and booleans `fixture_capability_live`, `direct_child_live`,
`exact_lock_held`, `matching_activity`, `backend_start_matches`, and `reaped`;
it contains no endpoint, PID, backend ID, secret, or command.

This capability binds only an already-created fixture-owned disposable target;
it neither introduces a new server process nor changes server lifecycle. The
direct-`postgres` ownership and stop mechanics remain exclusively Slice B.

Before any server action, one seam query must establish exactly one row
correlating the exact advisory lock, matching activity row, validated target
capability identity, live direct-holder capability, nonce, and backend-start
identity. Immediately before termination, the seam repeats that verification
inside the fixed atomic verify-and-terminate template: it conditions the
termination on the same lock, nonce, target identity, and backend-start value.
The backend-start value makes a recycled numeric PID insufficient. It then
proves lock absence and reaps the direct holder on every normal, error,
timeout, and interruption path, with server action, client wait, and reap all
charged to the same remaining deadline. Any zero/multiple rows, stale/reused
nonce, target/handle mismatch, failed recheck, lock persistence, failed reap,
or ambiguity is `cleanup_uncertain`.

A `configured_external` or otherwise non-disposable target has no
holder-termination capability: it is never sent a server signal,
backend-termination request, lifecycle command, TERM, KILL, or cleanup signal.
An independently created external sentinel must remain live and unsignalled on
normal, timeout, setup-failure, and uncertain-cleanup paths.

The Slice A structural audit has a finite, checked-in semantic inventory:
`config/validation/prepush-migration-callsite-inventory.v1.yaml`. It pins
source commit `e201622802db08bb2a0cbbd8ea4627ad0bb0b24e` and runner SHA-256
`18085c3fabf1c27dc76070dd16c623828e9d38b12115645923c8a37b2f85b31c`, plus
the governed advisory and parity fixture SHA-256s respectively
`0f9394d754d3558b671fea571e91b99a8bea935b9aef6a9a366e441fe7b29619` and
`f9d39fc6c6eeb250d90f06a620e748e81b599352129ae8c8d638fbc75a84224a`.
At that baseline, `scripts/run-forward-migrations.sh` contains exactly **19**
executable `psql` expressions—19, not 17—at source lines
`411, 458, 505, 574, 794, 868, 932, 954, 970, 1068, 1338, 1384, 1402, 1437,
1446, 1459, 1462, 1564, 1593`. The inventory records for each its operation
enum and expected seam dispatch, rather than treating a text match in a comment
or echo as executable. Source/hash drift requires an explicit reviewed
inventory update before the audit can pass.

The audit parses the shell AST and Python AST, then fails closed on direct
database command construction or unclassified process execution. Its search
set covers shell command words/expansions and Python `subprocess.Popen`,
`run`, `call`, `check_call`, `check_output`, `os.system`, `os.popen`,
`os.posix_spawn*`, `asyncio.create_subprocess_exec`,
`asyncio.create_subprocess_shell`, `multiprocessing`, imported aliases,
module aliases, dynamic attribute lookup, `eval`/`exec`, `shell=True`, and
direct executable/argv strings. A newly observed alias, dynamic spawn, or
database executable is a failure, not an inferred seam call. After Slice A,
all 19 runner sites become seam dispatches and the only allowed production
`psql` spawn is inside `DatabaseCallSeam`. In the two named script fixtures,
every AST-recognized database-client spawn routes through the fixture adapter
to the same seam; `initdb`, direct `postgres`, and `pg_isready` remain
separately classified lifecycle/readiness executables and are not disguised as
`psql` calls. Direct `psql` in the runner or either fixture, a new
unclassified database executable there, or inventory drift fails the audit.

The audit expressly excludes `tests/integration/**` (including migration
fixtures), all other `tests/**`, CI/workflow files, and unrelated operational
scripts. They are neither rewritten nor claimed to use this seam in Slice A,
and cannot be a pretext to weaken the closed scope.

Slice A acceptance tests include:

- A0's fake resolver proves that only the committed logical authority,
  capability, and secret references resolve. Static and runtime tests prove no
  password enters runner env, `.env`, compose interpolation, process
  inspection, image inspection, argv, logs, or a mount; an absent A0 resolver
  blocks Slice A rather than falling back to current injection. Separate tests
  prove the non-secret endpoint comes only from its capability, never ambient
  configuration or an overlay default. They also validate the provider
  selection hash, workload-identity-handle handoff, sanitized resolution
  receipt schema/hash, and exact locked dependency/image consumer receipt.
- Primary and node descriptor tests prove `0700`/`0600` modes before write,
  `O_EXCL|O_NOFOLLOW`, deterministic row order, colon/backslash escaping,
  duplicate-tuple rejection, LF/CR/NUL rejection in every field, partial-create
  cleanup, cleanup failure uncertainty, and no descriptor path/content log.
  They assert the complete three-key child env, absent `LANG`/`LC_ALL`/`HOME`/
  `TZ`/`PATH`, and rejection of hostile `PGSSL*`, `PGTARGETSESSIONATTRS`,
  `PGREQUIREAUTH`, service/configuration, target, and timeout variables.
- Connection, lock, statement, native-reconnect, and verification stalls use
  the one absolute deadline. Exact clock cases 1.999/2.000/2.999 seconds prove
  the separate process, connect, server-millisecond, and verification formulas;
  in particular connect fails below two seconds and never emits one; a smaller
  configured `pgconnect_timeout_seconds` or process allowance can only lower
  `C_s`. Dispatched mutating nonzero, signal, EOF, partial write, malformed
  result, and interruption prove `unknown_commit`/`cleanup_uncertain`, no
  ledger/success, and no retry. Read-only readiness/probe/holder-verification
  deadline expiry proves `timed_out`, never `unknown_commit`, and all result
  payload variants reject raw/malformed output.
- The byte-pinned corpus covers every migration and ledger SQL file, including
  bootstrap's sole allowed `\set ON_ERROR_STOP on`. It proves manifest target
  capabilities and startup `PGOPTIONS` behavior for controlled initial/native
  reconnect streams, and rejects unlisted reconnects, conninfo/options aliases,
  metacommand/file/shell escapes, timeout-changing SQL, and quoted/comment
  lookalikes.
- Fixed scalar-template tests prove every operation/typed parameter subset and
  reject raw query/argv, injected values, and unauthorized `-v` keys before
  spawn. COPY tests prove the exact six canonical input frames and paired cloud
  source/export-to-destination/import stream, bounded schema/hash validation,
  absence of `-c`/`\copy`/stage file, and read-only versus mutating uncertainty.
  The semantic inventory test proves exactly 19 runner sites and all scoped
  fixture spawn APIs/aliases/eval/direct-executable paths are classified.
- A controlled disposable lock holder proves nonce schema/format, capability
  non-forgeability, immediate atomic reverify before termination, PID reuse
  defense, lock absence, and reap on every path. A configured external target
  and unrelated sentinel prove the no-signal rule.

## Slice B — parity fixture with directly retained `postgres`

Replace the daemonizing `pg_ctl` lifecycle in the parity fixture with a direct,
retained foreground `postgres` `Popen`. `pg_ctl`'s default 60-second wait is
ambient and leak-prone, so it is not used for lifecycle control. The fixture
runner creates its own session before starting fixture-owned children and
resolves `initdb`, `postgres`, and `pg_isready` as coherent binaries from one
validated bin directory, never from an ambient `PATH` search. Every `psql`
operation remains in Slice A's fixed-client seam rather than acquiring a
fixture-local client binary. It records the direct process handle,
session/group identity, random data-dir and server nonces, and a sanitized
logical ownership receipt before readiness begins.

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
4. Before each slice's behavioral tests, run its structural audit. Slice A's
   closed scope is the runner plus the advisory/parity script fixtures, with
   the 19-call baseline and exclusions defined above; it proves every allowed
   `psql` use routes through the seam and all other database executables are
   classified. Slice B extends that audit only to its fixture lifecycle,
   proving no `pg_ctl` lifecycle remains and only coherent-bin resolution is
   used. Slice C audits only the hook/launcher boundary. Each audit preserves
   committed migration skip manifests and fails on an unclassified call.
5. Run Ruff, strict mypy for changed Python, shell syntax/ShellCheck for the
   hook, the image smoke check, focused tests above, relevant migration parity
   tests, pre-commit, and the governed pre-push path under a finite external
   watchdog.
6. Independent review verifies the three ownership boundaries, canonical
   overlay parsing, no ambient override/fallback, typed uncertainty, exact
   direct-`postgres` stop paths, external-target containment, stale-marker
   proof guard, `unknown_commit` containment, static-audit completeness, and
   absence of skip/retry/quarantine behavior.

No deployment, shared runtime mutation, database mutation, service stop, or
activation is authorized by this plan. # sanitization-ok: plan identifies a governed remediation without runtime authority
