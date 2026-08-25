---
type: runbook
status: current
date: "2026-07-31"
title: "Apply Migrations Runbook"
topics: [omnibase-infra, apply, migrations]
refs: []
---

# Apply Migrations Runbook

## When to Run This

- After pulling new code that contains new migration files
- After environment rebuild / fresh Docker volume
- After incident recovery — DB may have been restored from backup
- When `check_schema_fingerprint.py verify` fails with a count mismatch

## Prerequisites

```bash
# Always source credentials before any DB operation
source ~/.omnibase/.env

# Verify the DB URL is set
echo "DB URL: ${OMNIBASE_INFRA_DB_URL:-(not set)}"
```

If `OMNIBASE_INFRA_DB_URL` is not set, the migration runner will exit with an error.
Set it in `~/.omnibase/.env` (see `docs/getting-started/` for setup instructions).

## Check Current State

Connect to the database and inspect what has already been applied:

```bash
# Connect to DB
source ~/.omnibase/.env
psql -h localhost -p 5436 -U postgres -d omnibase_infra
```

```sql
-- List all applied migrations in order
SELECT migration_id, source_set, applied_at
FROM schema_migrations
ORDER BY applied_at;

-- Count applied migrations
SELECT COUNT(*) FROM schema_migrations;
```

If the `schema_migrations` table does not exist yet, the migration runner will create it
automatically on first run. You will see:

```
psql: error: relation "schema_migrations" does not exist
```

This is expected on a fresh database — proceed with the apply step below.

## Dry Run (see what would be applied without changing anything)

```bash
source ~/.omnibase/.env
uv run python scripts/run-migrations.py --dry-run
```

Expected output shows each pending migration prefixed with `[dry-run]`:

```
Applying 3 pending migration(s)...
  [dry-run] would apply: docker/034_some_migration.sql
  [dry-run] would apply: docker/035_another_migration.sql
  [dry-run] would apply: docker/036_create_schema_migrations.sql
```

If output is `No pending migrations.` — the database is already up to date.

## Apply All Pending Migrations

```bash
source ~/.omnibase/.env
uv run python scripts/run-migrations.py
```

The runner:
1. Creates `schema_migrations` table if it does not exist
2. Compares pending files against the `schema_migrations` table
3. Applies each pending migration in sequence-number order
4. Records each applied migration in `schema_migrations`
5. Automatically restamps `docker/migrations/schema_fingerprint.sha256`

Expected output:

```
Applying 2 pending migration(s)...
  applied: docker/035_another_migration.sql
  applied: docker/036_create_schema_migrations.sql
  fingerprint restamped.
```

## Apply Up To a Specific Sequence Number

To apply only up to a given sequence number (e.g., stop before 036):

```bash
source ~/.omnibase/.env
uv run python scripts/run-migrations.py --target 035
```

This is useful when rolling out migrations incrementally or when investigating a regression
introduced by a specific migration.

## Verify Schema Fingerprint

After applying migrations, verify the fingerprint artifact matches the migration files:

```bash
python scripts/check_schema_fingerprint.py verify
```

Expected: exit 0 with no output (silent success).

If the fingerprint is stale (exit code 2), the committed artifact does not match the current
migration files. This typically means:
- A migration file was added or modified without restamping
- The runner was interrupted before restamping completed

## If Fingerprint Mismatch Persists After Restart

Manually restamp the artifact:

```bash
uv run python -m omnibase_infra.runtime.util_schema_fingerprint stamp
```

Or use the check script directly:

```bash
python scripts/check_schema_fingerprint.py stamp
```

Commit the updated `docker/migrations/schema_fingerprint.sha256` artifact:

```bash
git add docker/migrations/schema_fingerprint.sha256
git commit -m "chore: restamp schema fingerprint"
```

## Emergency Rollback

Rollback scripts are in `docker/migrations/rollback/`. Each script reverses exactly one
forward migration. Apply manually via psql:

```bash
source ~/.omnibase/.env
psql -h localhost -p 5436 -U postgres -d omnibase_infra \
  -f docker/migrations/rollback/rollback_036_create_schema_migrations.sql
```

After rolling back, remove the tracking row from `schema_migrations` if the table still
exists:

```sql
DELETE FROM schema_migrations WHERE migration_id = 'docker/036_create_schema_migrations.sql';
```

If rolling back migration 036 itself (the `schema_migrations` table creation), the table
will be dropped by the rollback script — no DELETE is required.

### Rolling back multiple migrations

Apply rollbacks in reverse sequence-number order:

```bash
source ~/.omnibase/.env
PSQL="psql -h localhost -p 5436 -U postgres -d omnibase_infra"
$PSQL -f docker/migrations/rollback/rollback_036_create_schema_migrations.sql
$PSQL -f docker/migrations/rollback/rollback_035_another_migration.sql
```

After rollback, restamp the fingerprint to reflect the new state:

```bash
python scripts/check_schema_fingerprint.py stamp
```

## Writer-Migration Bypass Comment

CI enforces that any PR touching a `writer_postgres.py` or `handler_*_postgres.py` file
must include a corresponding migration file. If a PR modifies one of these files but truly
requires no schema change, add this comment near the top of the file:

```python
# no-migration: <reason explaining why no schema change is needed>
```

This bypasses the `check_migration_required.py` CI gate for that file.

Example valid reasons:
- `# no-migration: refactoring query logic only, schema unchanged`
- `# no-migration: adding index hint via query parameter, no DDL needed`

## Troubleshooting

### `asyncpg.exceptions.ConnectionDoesNotExistError`

The database is not running. Start it:

```bash
docker compose -f docker/docker-compose.infra.yml up -d omnibase-infra-postgres
```

### `OMNIBASE_INFRA_DB_URL required`

The environment variable is not set. Source credentials:

```bash
source ~/.omnibase/.env
```

### `duplicate sequence number` error

Two migration files share a leading sequence number (e.g., `035_foo.sql` and `035_bar.sql`).
This is a development error — rename one of the files and update the fingerprint artifact.

### Migration applied but `schema_migrations` row missing

Treat this as an indeterminate apply and stop the lane. Do not hand-insert a
tracking row: that would claim content, owner, and apply provenance that the
runner did not durably record. Preserve the database catalogs and runner logs,
prove whether the DDL committed, then repair through a reviewed deterministic
import or a new idempotent migration. Application/node history follows
the application migration ledger procedure.

## Omnidash Read-Model Migrations

Omnidash maintains its own `omnidash_analytics` read-model database with SQL migrations
in `omnidash/migrations/`. These are wired into the bootstrap pipeline as **Step 1d**.

### Canonical projection database

The delegation projection (`node_projection_delegation`, omnimarket) writes to
**`omnidash_analytics.delegation_events`** — the live, growing table. Node-owned
migrations vendored under `docker/migrations/forward/nodes/<node>/` are applied by
`run-forward-migrations.sh` against `NODE_POSTGRES_DB` (compose sets
`omnidash_analytics`), NOT the flat infra `omnibase_infra` DB.

> **Probe the live table in `omnidash_analytics`, never `omnibase_infra`.** A stale
> `delegation_events` decoy used to exist in the `omnibase_infra` DB (a historical
> artifact from before the node-migration runner was repointed to
> `omnidash_analytics`; last write 2026-05-13, read by nothing). Querying that decoy
> caused the 2026-06-19 Gate-Zero "writes stopped May 13" misdiagnosis. Forward
> migration `087_drop_stale_delegation_events_decoy.sql` drops it. Future probes:
>
> ```bash
> # Correct: live delegation projection
> psql -d omnidash_analytics -c "SELECT count(*), max(timestamp) FROM delegation_events;"
> ```

### Bootstrap (advisory -- warn and continue)

During the secrets-bootstrap script, Step 1d runs the omnidash migration runner if both
`OMNIDASH_DIR` and `OMNIDASH_ANALYTICS_DB_URL` are set. Failures are non-fatal:

```bash
# Step 1d runs automatically during bootstrap when env vars are set:
OMNIDASH_DIR=/path/to/omnidash
OMNIDASH_ANALYTICS_DB_URL=postgresql://postgres:<password>@localhost:5436/omnidash_analytics
```

If the omnidash database is not yet provisioned or the checkout is not available, the
bootstrap logs a warning and continues. The read-model may be stale until migrations
are applied manually.

### Manual run

```bash
source ~/.omnibase/.env
cd "${OMNIDASH_DIR}"
npx tsx scripts/run-migrations.ts
```

### Deploy-time enforcement (future -- fail closed)

When omnidash moves to containerized deployment, the init container MUST run migrations
and **fail closed** -- the pod should not start if the schema is not up to date.

The enforcement boundary:

| Context | Behavior | Rationale |
|---------|----------|-----------|
| the secrets-bootstrap script (Step 1d) | Warn and continue | Local dev may not have omnidash DB |
| Container init (future) | Fail closed | Production must have correct schema |

Implementation notes for the init container:

1. Run `npx tsx scripts/run-migrations.ts` as an init container
2. Exit non-zero on any migration failure (the runner already does this)
3. The main omnidash container depends on the init container succeeding
4. No `|| true` or similar suppression -- failures must block pod startup

### Parity check

After applying migrations, verify parity between the migrations directory and the
`schema_migrations` tracking table:

```bash
cd "${OMNIDASH_DIR}"
npx tsx scripts/check-migration-parity.ts
```

This tool (added in ) ensures no migrations are missing from either the
filesystem or the database.
