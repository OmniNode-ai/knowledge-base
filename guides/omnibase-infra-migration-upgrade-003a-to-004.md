---
type: guide
status: current
date: "2026-09-02"
title: "Migration Upgrade Guide: 003a to 004"
topics: [omnibase-infra, migration, upgrade, 003a]
refs: []
---

<!-- Migrated from omnibase_infra:docker/migrations/MIGRATION_UPGRADE_003a_to_004.md on 2026-09-02. -->

# Migration Upgrade Guide: 003a to 004

This document explains the migration renumbering from `003a_capability_fields_concurrent.sql` to `004_capability_fields_concurrent.sql` and provides upgrade instructions for existing deployments.

## Summary of Change

| Before | After | Reason |
|--------|-------|--------|
| `003a_capability_fields_concurrent.sql` | `004_capability_fields_concurrent.sql` | Standardize on main sequence numbering |

## Why the Renumbering?

The original naming (`003a`) followed a sub-migration convention where letter suffixes indicated companion scripts to a parent migration. However, this created confusion:

1. **Ambiguous execution order**: Sub-migrations (`003a`, `003b`) imply optional/alternative paths, but `003a` was actually the **recommended** production migration for large tables.

2. **Documentation consistency**: The production concurrent variant should be a first-class migration, not a sub-variant.

3. **Tooling compatibility**: Some migration tracking tools don't handle letter suffixes well.

The renumbering to `004` makes it explicit that this is a standalone migration that can be applied instead of (or in addition to) `003`.

## Migration Relationship

```
003_capability_fields.sql
    |
    |-- Adds columns: contract_type, intent_types, protocols, capability_tags, contract_version
    |-- Creates indexes with standard CREATE INDEX (may lock tables briefly)
    |
004_capability_fields_concurrent.sql (formerly 003a)
    |
    |-- Creates the SAME indexes as 003, but using CREATE INDEX CONCURRENTLY
    |-- Does NOT add columns (assumes 003 was already applied)
    |-- Use for production deployments with >100K rows
```

## Upgrade Scenarios

### Scenario 1: Fresh Deployment (No Migrations Applied Yet)

For **new databases** or databases where **no ONEX migrations have been applied yet** (empty `registration_projections` table or table does not exist).

**Key point**: Fresh deployments only need migrations 001-003. Migration 004 is NOT required because standard indexes on empty tables complete instantly.

```bash
# Apply all migrations in sequence
psql -h $HOST -d $DB -f forward/001_registration_projection.sql
psql -h $HOST -d $DB -f forward/002_updated_at_audit_index.sql
psql -h $HOST -d $DB -f forward/003_capability_fields.sql

# Done - migration 003 creates columns AND indexes
# Migration 004 is NOT needed for fresh deployments
```

> **Why migration 003 is sufficient**: On an empty table, `CREATE INDEX` completes instantly with no blocking. The concurrent index variant (migration 004) is only needed when adding indexes to **existing tables with data** where you cannot afford brief write locks.

**When to use migration 004 instead**: Only if you are adding migrations to a database that **already has data** in the `registration_projections` table (>100K rows). See Scenario 3 for that upgrade path.

### Scenario 2: Production Database with 003a Already Applied

If your database already has `003a_capability_fields_concurrent.sql` applied:

**Good news**: No action required. The migration `004_capability_fields_concurrent.sql` is functionally identical to the old `003a`. Your indexes are already in place.

**Verification steps**:

```sql
-- Verify capability columns exist
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'registration_projections'
  AND column_name IN ('contract_type', 'intent_types', 'protocols', 'capability_tags', 'contract_version');

-- Expected: 5 rows

-- Verify GIN indexes exist
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'registration_projections'
  AND indexname IN (
    'idx_registration_capability_tags',
    'idx_registration_intent_types',
    'idx_registration_protocols',
    'idx_registration_contract_type_state'
  );

-- Expected: 4 rows (all indexes valid)

-- Verify all indexes are valid (not in failed state)
SELECT indexrelid::regclass AS index_name, indisvalid
FROM pg_index
WHERE indrelid = 'registration_projections'::regclass
  AND NOT indisvalid;

-- Expected: 0 rows (no invalid indexes)
```

### Scenario 3: Production Database with Only 003 Applied (Standard Indexes)

If you applied `003_capability_fields.sql` and want to upgrade to concurrent indexes:

```bash
# Drop existing standard indexes
psql -h $HOST -d $DB -c "DROP INDEX IF EXISTS idx_registration_capability_tags;"
psql -h $HOST -d $DB -c "DROP INDEX IF EXISTS idx_registration_intent_types;"
psql -h $HOST -d $DB -c "DROP INDEX IF EXISTS idx_registration_protocols;"
psql -h $HOST -d $DB -c "DROP INDEX IF EXISTS idx_registration_contract_type_state;"

# Apply concurrent indexes (cannot run in transaction block)
psql -h $HOST -d $DB -f forward/004_capability_fields_concurrent.sql
```

### Scenario 4: Migration Tracking System Records "003a"

If your deployment tracking (manual logs, wiki, etc.) shows "003a" as applied:

1. **Update your records**: Note that `003a` is now `004`
2. **No database changes needed**: The underlying SQL is identical
3. **Document the alias**: In your tracking system, note:
   ```
   003a_capability_fields_concurrent.sql (RENAMED to 004)
   Status: Applied
   Notes: Renamed in PR #143. Same SQL content as original 003a.
   ```

## Migration File Checksums

To verify you have the correct version of each migration, compare SHA-256 checksums:

```bash
# Generate checksums for your forward migration files
cd docker/migrations/
sha256sum forward/*.sql
```

The index creation SQL in `003_capability_fields.sql` and `004_capability_fields_concurrent.sql` should produce identical indexes (just using different creation methods).

## Version Compatibility Matrix

| Migration Version | Creates Columns | Creates Indexes | Index Method | Suitable For |
|-------------------|-----------------|-----------------|--------------|--------------|
| 003 only | Yes | Yes | Standard | Dev/Staging, <100K rows |
| 003 + 004 | Yes (003) | Yes (004) | Concurrent | Production, >100K rows |
| 003a (legacy) | No | Yes | Concurrent | **DEPRECATED** - use 004 |

## Migration Gap Detection

Before applying migrations, operators should validate the current migration state to detect gaps or inconsistencies.

### Why Migration Gap Detection Matters

| Scenario | Risk | Detection |
|----------|------|-----------|
| Missing 003 (columns) | 004 will fail - columns don't exist | Column check fails |
| Missing 002 (audit index) | No immediate failure, but audit queries slow | Index check fails |
| 003a applied, 004 not tracked | Documentation mismatch, no functional issue | Manual record check |
| Partial 004 (interrupted) | Invalid indexes in database | `indisvalid` check |

### Pre-Migration Validation SQL

Run this validation query before applying any migration to detect gaps:

```sql
-- =============================================================================
-- MIGRATION STATE VALIDATION QUERY
-- Run this before applying migrations to detect gaps
-- =============================================================================

WITH expected_state AS (
    SELECT * FROM (VALUES
        -- (migration_id, description, validation_type, validation_target)
        ('001', 'registration_projections table', 'table', 'registration_projections'),
        ('002', 'updated_at audit index', 'index', 'idx_registration_projections_updated_at'),
        ('003', 'capability columns', 'columns', 'contract_type,intent_types,protocols,capability_tags,contract_version'),
        ('004', 'concurrent GIN indexes', 'indexes', 'idx_registration_capability_tags,idx_registration_intent_types,idx_registration_protocols,idx_registration_contract_type_state')
    ) AS t(migration_id, description, validation_type, validation_target)
),
table_check AS (
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'registration_projections'
          AND table_schema = 'public'
    ) AS table_exists
),
column_check AS (
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'registration_projections'
      AND column_name IN ('contract_type', 'intent_types', 'protocols', 'capability_tags', 'contract_version')
),
index_check AS (
    SELECT indexname, indisvalid
    FROM pg_indexes i
    JOIN pg_class c ON c.relname = i.indexname
    JOIN pg_index idx ON idx.indexrelid = c.oid
    WHERE tablename = 'registration_projections'
      AND indexname IN (
        'idx_registration_projections_updated_at',
        'idx_registration_capability_tags',
        'idx_registration_intent_types',
        'idx_registration_protocols',
        'idx_registration_contract_type_state'
      )
)
SELECT
    '001' AS migration,
    CASE WHEN (SELECT table_exists FROM table_check) THEN 'APPLIED' ELSE 'MISSING' END AS status,
    'registration_projections table' AS description
UNION ALL
SELECT
    '002' AS migration,
    CASE WHEN EXISTS (SELECT 1 FROM index_check WHERE indexname = 'idx_registration_projections_updated_at')
         THEN 'APPLIED' ELSE 'MISSING' END AS status,
    'updated_at audit index' AS description
UNION ALL
SELECT
    '003' AS migration,
    CASE WHEN (SELECT COUNT(*) FROM column_check) = 5 THEN 'APPLIED'
         WHEN (SELECT COUNT(*) FROM column_check) > 0 THEN 'PARTIAL'
         ELSE 'MISSING' END AS status,
    'capability columns (contract_type, intent_types, etc.)' AS description
UNION ALL
SELECT
    '004' AS migration,
    CASE
        WHEN (SELECT COUNT(*) FROM index_check
              WHERE indexname IN ('idx_registration_capability_tags', 'idx_registration_intent_types',
                                  'idx_registration_protocols', 'idx_registration_contract_type_state')
                AND indisvalid = true) = 4 THEN 'APPLIED'
        WHEN (SELECT COUNT(*) FROM index_check
              WHERE indexname IN ('idx_registration_capability_tags', 'idx_registration_intent_types',
                                  'idx_registration_protocols', 'idx_registration_contract_type_state')
                AND indisvalid = false) > 0 THEN 'INVALID_INDEXES'
        WHEN (SELECT COUNT(*) FROM index_check
              WHERE indexname IN ('idx_registration_capability_tags', 'idx_registration_intent_types',
                                  'idx_registration_protocols', 'idx_registration_contract_type_state')) > 0 THEN 'PARTIAL'
        ELSE 'MISSING'
    END AS status,
    'capability GIN indexes (concurrent)' AS description
ORDER BY migration;
```

**Expected Output for Fully Migrated Database:**

```
 migration |  status  |               description
-----------+----------+------------------------------------------
 001       | APPLIED  | registration_projections table
 002       | APPLIED  | updated_at audit index
 003       | APPLIED  | capability columns (contract_type, ...)
 004       | APPLIED  | capability GIN indexes (concurrent)
```

### Interpreting Validation Results

| Status | Meaning | Action |
|--------|---------|--------|
| `APPLIED` | Migration successfully applied | No action needed |
| `MISSING` | Migration not applied | Apply the migration |
| `PARTIAL` | Migration partially applied | Review and complete |
| `INVALID_INDEXES` | Concurrent index creation interrupted | Drop invalid indexes, re-run 004 |

### Detecting 003a vs 004 Ambiguity

If your deployment history shows "003a" was applied, verify the actual database state:

```sql
-- Check if 003a/004 content is present (they are functionally identical)
SELECT
    CASE
        WHEN COUNT(*) = 4 THEN 'GIN indexes present (003a or 004 content applied)'
        WHEN COUNT(*) > 0 THEN 'Partial GIN indexes (' || COUNT(*) || ' of 4)'
        ELSE 'No GIN indexes - neither 003a nor 004 applied'
    END AS status
FROM pg_indexes
WHERE tablename = 'registration_projections'
  AND indexname IN (
    'idx_registration_capability_tags',
    'idx_registration_intent_types',
    'idx_registration_protocols',
    'idx_registration_contract_type_state'
  );
```

**Result Interpretation:**
- "GIN indexes present" → Database is current; update your tracking records to show "004"
- "Partial GIN indexes" → Interrupted migration; drop invalid indexes and re-run
- "No GIN indexes" → Apply 003 (columns) then 004 (indexes)

### Automated Validation Script

For CI/CD pipelines, use this exit-code-based validation:

```bash
#!/bin/bash
# validate_migrations.sh - Exit 0 if all migrations applied, non-zero otherwise

result=$(psql "$OMNIBASE_INFRA_DB_URL" -t -c "
SELECT COUNT(*) FROM (
    SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'registration_projections')
    UNION ALL
    SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_registration_projections_updated_at')
    UNION ALL
    SELECT 1 WHERE (SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name = 'registration_projections'
                      AND column_name IN ('contract_type', 'intent_types', 'protocols', 'capability_tags', 'contract_version')) < 5
    UNION ALL
    SELECT 1 WHERE (SELECT COUNT(*) FROM pg_indexes
                    WHERE tablename = 'registration_projections'
                      AND indexname IN ('idx_registration_capability_tags', 'idx_registration_intent_types',
                                        'idx_registration_protocols', 'idx_registration_contract_type_state')) < 4
) missing;
")

missing_count=$(echo "$result" | tr -d '[:space:]')

if [ "$missing_count" -eq 0 ]; then
    echo "All migrations applied successfully"
    exit 0
else
    echo "ERROR: $missing_count migration(s) missing or incomplete"
    echo "Run the validation query for details"
    exit 1
fi
```

## Troubleshooting

### "Index already exists" Error

If `004` fails because indexes already exist from `003`:

```sql
-- Drop existing indexes first
DROP INDEX IF EXISTS idx_registration_capability_tags;
DROP INDEX IF EXISTS idx_registration_intent_types;
DROP INDEX IF EXISTS idx_registration_protocols;
DROP INDEX IF EXISTS idx_registration_contract_type_state;
```

### Invalid Index State

If a concurrent index creation was interrupted, it may be left in an invalid state:

```sql
-- Check for invalid indexes
SELECT indexrelid::regclass AS index_name
FROM pg_index
WHERE NOT indisvalid
  AND indrelid = 'registration_projections'::regclass;

-- Drop invalid index and recreate
DROP INDEX <invalid_index_name>;
-- Then re-run forward/004_capability_fields_concurrent.sql
```

### Missing Columns

If `004` fails because columns don't exist:

```
ERROR: Missing columns: contract_type, intent_types, protocols, capability_tags
```

You need to apply `forward/003_capability_fields.sql` first to create the columns.

## Related Documentation

- `README.md` - Migration versioning conventions
- `validate_migration_state.sql` - **Run this to validate current migration state**
- `forward/003_capability_fields.sql` - Column and standard index creation
- `forward/004_capability_fields_concurrent.sql` - Concurrent index creation
- `ADR-005-denormalize-capability-fields-in-registration-projections.md` - Design rationale

## Changelog

| Date | Change |
|------|--------|
| 2026-01-13 | Simplified Scenario 1: removed PATH B, clarified fresh deployments always use 003 only |
| 2026-01-13 | Added Migration Gap Detection section with validation SQL script |
| 2026-01-13 | Renamed `003a` to `004` per PR #143 review feedback |
| 2026-01-12 | Initial `003a_capability_fields_concurrent.sql` created |
