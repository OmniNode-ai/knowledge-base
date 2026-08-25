---
type: runbook
status: current
date: "2026-07-21"
title: "Vendored Node Migration Runbook"
topics: [omnibase-infra, vendored, node, migrations]
refs: []
---


# Vendored Node Migration Runbook

Operator guide for the vendored-node-migration pattern: how it works, when to use it, how to run the sync, and how the CI gate enforces consistency.

---

## Table of Contents

1. Why This Pattern Exists
2. Directory Layout
3. When to Run the Sync
4. Running the Sync
5. Sentinel Discipline and Idempotency
6. CI Gate: node-migration-sync
7. Pre-Commit Hook: onex-check-node-migration-sync
8. Vendored Migrations vs Flat Alembic Migrations
9. Troubleshooting

---

## Why This Pattern Exists

Omnimarket projection nodes ship SQL that creates their backing tables. Before this pattern was introduced, landing a node-owned view in the runtime required:

1. Manually copying the SQL into `docker/migrations/forward/` (infra repo).
2. Manually renumbering the file to avoid a numeric collision with the flat infra migration sequence.

That renumber is a footgun: the source SQL and the infra copy drift, and every new node migration repeats the dance. The `node_projection_pattern_learning` node exposed this when its migration was merged to omnimarket without a vendored copy, causing `pattern_learning_artifacts` to be absent from `omnidash_analytics` on a clean redeploy.

The vendored-node-migration pattern was introduced to fix this:

- Omnimarket projection nodes ship SQL under `src/omnimarket/nodes/<node>/migrations/*.sql`.
- `scripts/sync-node-migrations.sh` mirrors those files 1:1 into `docker/migrations/forward/nodes/<node>/`.
- The forward-migration runner applies them under namespaced IDs (`node:<node>:<file>`) — no renumber ever needed.
- The CI gate (`node-migration-sync.yml`) enforces that infra and omnimarket are always in sync.

---

## Directory Layout

```text
docker/migrations/forward/
├── 001_baseline.sql        # Flat infra migrations (numeric, never renumbered)
├── 002_...sql
├── ...
└── nodes/                  # Vendored node migrations (namespaced, never collide with flat)
    ├── node_projection_delegation_summary/
    │   └── 001_create_view.sql
    ├── node_projection_pattern_learning/
    │   └── 001_create_artifacts_table.sql
    └── ...
```

**Namespaced migration IDs**: The forward-migration runner records applied migrations as `node:<node_name>:<filename>` (e.g., `node:node_projection_pattern_learning:001_create_artifacts_table.sql`). These live in a separate namespace from the flat `001_baseline.sql` → `001` IDs, so no collision is possible.

---

## When to Run the Sync

Run `scripts/sync-node-migrations.sh` whenever:

- An omnimarket node adds a new migration file.
- An existing node migration file is changed.
- The CI gate (`node-migration-sync`) fails on an infra PR.

The node-migration-sync CI gate re-checks on every infra pull request against the current omnimarket `dev` tip, so drifted vendor copies will also surface there.

---

## Running the Sync

```bash
# From the omnibase_infra repo root.
# The script resolves omnimarket source in this order:
#   1. $OMNIMARKET_SRC (explicit override; set to the repo root)
#   2. $OMNI_HOME/omnimarket (canonical clone registry)
#   3. installed package (python import)

# Default (uses $OMNI_HOME/omnimarket):
./scripts/sync-node-migrations.sh

# Explicit source:
OMNIMARKET_SRC=/path/to/omnimarket ./scripts/sync-node-migrations.sh

# Dry-run (show what would change, no writes):
./scripts/sync-node-migrations.sh --check
```

After the sync runs successfully, stage and commit the changes under `docker/migrations/forward/nodes/`:

```bash
git add docker/migrations/forward/nodes/
git commit -m "chore: vendor omnimarket node migrations"
```

---

## Sentinel Discipline and Idempotency

The forward-migration runner applies migrations under a `migration_log` table. Each namespaced ID is recorded exactly once. Re-running the runner against an already-migrated database is safe: applied IDs are skipped.

**Wait-for-postgres**: The `forward-migration` Docker service uses `depends_on: postgres: condition: service_healthy` and an exponential-backoff loop before running migrations. Do not remove or shorten this wait.

**Skip-manifest**: The node migration runner respects a `skip_manifest.yaml` file at `docker/migrations/forward/nodes/skip_manifest.yaml`. Only use this to skip migrations that are superseded by a later node migration in the same node — do not use it to permanently skip required tables.

---

## CI Gate: node-migration-sync

**File**: `.github/workflows/node-migration-sync.yml`
**Triggers**: `pull_request` (dev/main), `push` to `main`, `merge_group`

On every infra PR the gate:

1. Checks out the current omnibase_infra PR branch.
2. Clones the current omnimarket `dev` tip.
3. Runs `./scripts/sync-node-migrations.sh --check`.
4. Fails if any file in `docker/migrations/forward/nodes/` is absent, stale, or has been removed from omnimarket.

**Failure symptom**: `sync-node-migrations.sh --check` exits non-zero, listing the files that are out of sync.

**Fix**: Run the sync locally (see above), commit the updated vendor files, and push.

---

## Pre-Commit Hook: onex-check-node-migration-sync

A pre-commit hook (`onex-check-node-migration-sync`) runs the sync `--check` on infra commits that touch `docker/migrations/forward/nodes/` or `src/omnibase_infra/nodes/`. The hook only fires in the infra repo; it does not run in omnimarket. This means an omnimarket PR that adds a node migration can land without triggering the hook — the CI gate fills that gap.

---

## Vendored Migrations vs Flat Alembic Migrations

| Aspect | Flat infra migrations (`docker/migrations/forward/*.sql`) | Vendored node migrations (`docker/migrations/forward/nodes/<node>/*.sql`) |
|--------|---------------------------------------------------------|-------------------------------------------------------------------------|
| Owned by | omnibase_infra team | Individual omnimarket projection node authors |
| Namespacing | Numeric sequence (`001_`, `002_`, ...) | `node:<node>:<file>` — never collides with flat sequence |
| Renumber required? | Yes, when inserting out-of-order | Never |
| Source of truth | `docker/migrations/forward/` in infra repo | `src/omnimarket/nodes/<node>/migrations/` in omnimarket |
| How they get to infra | Hand-authored in infra | Auto-vendored via `sync-node-migrations.sh` |
| CI enforcement | `ci.yml` migration tests | `node-migration-sync.yml` drift check |

Use the **flat infra migration** pattern for schema changes to core infra tables (e.g., `node_registrations`, `event_ledger`). Use the **vendored node migration** pattern for projection tables owned by omnimarket nodes.

---

## Troubleshooting

### CI gate fails: "migration file missing in infra"

The omnimarket repo has a node migration that has not been vendored into infra. Run the sync locally and commit the result.

### CI gate fails: "migration file differs from omnimarket source"

The omnimarket migration was modified after the vendor copy was committed. Re-run the sync to pick up the updated content and commit.

### Migration table already exists on redeploy

The `migration_log` table records that `node:<node>:<file>` was already applied. The runner skips it. This is correct behavior — the table was created by a previous deployment.

### Migration fails: table/view already exists without a migration record

A previous manual deployment created the table outside the migration runner. Options:

1. If the schema matches, insert a record into `migration_log` for the namespaced ID to mark it as applied.
2. If the schema does not match, drop the table/view and let the migration re-create it.

---

## See Also

- `scripts/sync-node-migrations.sh` — vendor sync script
- `.github/workflows/node-migration-sync.yml` — CI gate
- `docker/migrations/forward/` — migration directory
- CI Test Strategy — node-migration-sync gate
- [Current Node Architecture — vendored migration pattern](../architecture/2026-07-21-current-node-architecture.md#vendored-node-migration-pattern)
