---
type: reference
status: current
date: "2026-09-02"
title: "Migration Versioning Convention"
topics: [omnibase-infra, migration, versioning, convention]
refs: []
---

<!-- Migrated from omnibase_infra:docker/migrations/README.md on 2026-09-02. -->

# Migration Versioning Convention

This document describes the versioning scheme and directory convention for database migrations in the ONEX infrastructure.

## Directory Structure

Migrations are separated into `forward/` and `rollback/` directories to prevent rollback scripts from being auto-applied by PostgreSQL's `docker-entrypoint-initdb.d` mechanism.

```
docker/migrations/
  forward/                                # ONLY this directory is mounted to docker-entrypoint-initdb.d
    000_create_multiple_databases.sh      # Database initialization (runs first)
    NNN_description.sql                   # Forward migrations (auto-applied on first start)
  rollback/                               # NEVER auto-applied
    rollback_NNN_description.sql          # Rollback scripts (manual execution only)
  README.md                               # This file
  validate_migration_state.sql            # Validation utility
  MIGRATION_UPGRADE_003a_to_004.md        # Historical upgrade notes
```

**Why this matters**: PostgreSQL's Docker image executes ALL `.sql` and `.sh` files in `docker-entrypoint-initdb.d` alphabetically on first start. If rollback scripts (which contain `DROP TABLE`) live alongside forward migrations, they will execute and destroy the tables that were just created.

**Rule**: Only `forward/` is volume-mounted. Rollback scripts in `rollback/` are never auto-applied and must be run manually when needed.

## File Naming Pattern

### Forward Migrations (`forward/NNN_description.sql`)

Forward migrations follow the format: `NNN[a-z]_description[_modifier].sql`

| Component | Format | Example | Description |
|-----------|--------|---------|-------------|
| **Sequence** | `NNN` | `001`, `002`, `003` | Three-digit main migration number |
| **Sub-sequence** | `[a-z]` | `003a`, `003b` | Optional letter suffix for related migrations |
| **Description** | `_snake_case` | `_capability_fields` | Descriptive name of the change |
| **Modifier** | `_concurrent` | `_concurrent` | Optional suffix indicating special execution mode |

### Rollback Migrations (`rollback/rollback_NNN_description.sql`)

Rollback files always use the `rollback_` prefix followed by the migration number they reverse:

| Forward | Rollback |
|---------|----------|
| `forward/020_create_agent_actions_table.sql` | `rollback/rollback_020_agent_actions_table.sql` |
| `forward/026_injection_effectiveness_tables.sql` | `rollback/rollback_026_injection_effectiveness_tables.sql` |

## Migration Types

### Main Migrations (`NNN_description.sql`)

Main migrations represent a logical unit of schema change. They are numbered sequentially:

- `001_registration_projection.sql` - Initial projection schema
- `002_updated_at_audit_index.sql` - Audit query indexes
- `003_capability_fields.sql` - Capability discovery columns and standard indexes
- `004_capability_fields_concurrent.sql` - Production concurrent indexes (companion to 003)
- `005_create_contracts_topics.sql` - Contract and topic tracking tables
- `020-027` - Agent observability and analytics tables
- `028_absorb_omniclaude_columns.sql` - Absorb project context columns + agent_activity_realtime view

**When to increment the main number:**
- New tables or major schema changes
- Independent features that don't depend on a companion script
- Changes that represent a distinct logical unit
- Production-recommended variants (e.g., concurrent indexes for large tables)

### Sub-Migrations (`NNNa_description.sql`)

Sub-migrations are companion scripts related to a main migration. They share the same numeric prefix with a letter suffix.

> **Historical Note**: Migration `003a_capability_fields_concurrent.sql` was renamed to `004_capability_fields_concurrent.sql` to use main sequence numbering for production-recommended variants. See `MIGRATION_UPGRADE_003a_to_004.md` for upgrade details.

**When to use letter suffixes:**
- Alternative implementations for specific environments
- Split migrations that must run in a specific order

**When to use main sequence instead:**
- Production-recommended variants (e.g., concurrent indexes) should use the next main number
- Independent features should use the next main number

## Modifier Suffixes

### `_concurrent` Suffix

Indicates a migration designed for **production environments with live traffic**:

```
forward/003_capability_fields.sql              # Standard version (may lock tables)
forward/004_capability_fields_concurrent.sql   # Production version (non-blocking)
```

**Characteristics of `_concurrent` migrations:**
- Uses `CREATE INDEX CONCURRENTLY` instead of `CREATE INDEX`
- Cannot run inside a transaction block (requires autocommit)
- Longer execution time but no table locks
- May leave indexes in INVALID state if interrupted (must be dropped and recreated)

**When to use which:**

| Environment | Migration Type | Notes |
|-------------|----------------|-------|
| Development | Standard (`003`) | Faster, can run in transactions |
| CI/CD | Standard (`003`) | Transactions required for rollback |
| Staging | Either | Depends on table size and requirements |
| Production (<100K rows) | Standard (`003`) | Brief locks acceptable |
| Production (>100K rows) | Concurrent (`004`) | Avoid blocking writes |
| Production (>1M rows) | Concurrent (`004`) | **Required** for zero-downtime |

## Determining the Next Migration Number

**For a new independent feature:**
- Use the next sequential number in `forward/`: e.g., `forward/028_new_feature.sql`

**For a rollback script:**
- Place in `rollback/` with `rollback_` prefix: e.g., `rollback/rollback_028_new_feature.sql`

**Current state:**
```
forward/
  001_registration_projection.sql        # Main: initial schema
  002_updated_at_audit_index.sql         # Main: audit indexes
  003_capability_fields.sql              # Main: capability columns + standard indexes
  004_capability_fields_concurrent.sql   # Main: concurrent indexes (production)
  005_create_contracts_topics.sql        # Main: contract/topic tables
  020_create_agent_actions_table.sql                  # Main: agent actions
  021_create_agent_routing_decisions_table.sql        # Main: routing decisions
  022_create_agent_transformation_events_table.sql    # Main: transformation events
  023_create_router_performance_metrics_table.sql     # Main: router metrics
  024_create_agent_detection_failures_table.sql       # Main: detection failures
  025_create_agent_execution_logs_table.sql           # Main: execution logs
  026_injection_effectiveness_tables.sql              # Main: injection effectiveness
  027_create_agent_status_events_table.sql            # Main: agent status events
  028_absorb_omniclaude_columns.sql                   # Main: absorb omniclaude columns
```

**Next available:** `029_*.sql`

## Migration Header Requirements

Every migration should include a header comment with:

```sql
-- =============================================================================
-- MIGRATION: Brief Description
-- =============================================================================
-- Ticket: (Feature Name)
-- Version: 1.0.0
-- Companion to: NNN_parent_migration.sql (if sub-migration)
--
-- PURPOSE:
--   What this migration does and why
--
-- PRODUCTION DATABASE SAFETY:
--   1. BACKUP your database before running
--   2. TEST on staging environment first
--   3. MONITOR execution time and locks
--
-- ROLLBACK:
--   See rollback/rollback_NNN_description.sql
--
-- =============================================================================
```

## Execution Guidelines

### Standard Migrations

```bash
# Can run in a transaction (for CI/CD with rollback support)
psql -h $HOST -d $DB -f forward/003_capability_fields.sql
```

### Concurrent Migrations

```bash
# MUST run outside transaction block (autocommit mode)
psql -h $HOST -d $DB -f forward/004_capability_fields_concurrent.sql

# DO NOT wrap in BEGIN/COMMIT - will error:
# "CREATE INDEX CONCURRENTLY cannot run inside a transaction block"
```

### Running Rollbacks (Manual Only)

```bash
# Rollbacks are NEVER auto-applied. Run manually when reverting a migration:
psql -h $HOST -d $DB -f rollback/rollback_020_agent_actions_table.sql
```

### Monitoring Concurrent Index Creation

```sql
-- Check progress (PostgreSQL 12+)
SELECT
    p.phase,
    ROUND(100.0 * p.blocks_done / NULLIF(p.blocks_total, 0), 1) AS pct_complete,
    i.relname AS index_name
FROM pg_stat_progress_create_index p
JOIN pg_class i ON i.oid = p.index_relid;

-- Check for invalid indexes after failure
SELECT indexrelid::regclass AS index_name, indisvalid
FROM pg_index
WHERE NOT indisvalid;
```

## Summary

| Pattern | Location | Example | Use Case |
|---------|----------|---------|----------|
| `NNN_desc.sql` | `forward/` | `forward/028_new_table.sql` | New independent feature |
| `NNNa_desc.sql` | `forward/` | `forward/003a_variant.sql` | Companion to NNN |
| `NNN_*_concurrent.sql` | `forward/` | `forward/004_*_concurrent.sql` | Non-blocking production variant |
| `rollback_NNN_desc.sql` | `rollback/` | `rollback/rollback_028_new_table.sql` | Revert a forward migration |

**Decision tree for next migration:**

1. Is this a forward migration? -> Place in `forward/` with next main number
2. Is this a rollback? -> Place in `rollback/` with `rollback_` prefix matching the forward migration number
3. Is this a production-optimized variant? -> Use next main number with `_concurrent` suffix in `forward/`

## Migration Validation

Before applying migrations or troubleshooting issues, validate the current database state:

```bash
# Run the validation script
psql -h $HOST -d $DB -f validate_migration_state.sql
```

This script checks:
- Table existence (migration 001)
- Audit index presence (migration 002)
- Capability columns (migration 003)
- GIN indexes and their validity (migration 004)
- Invalid index detection (for interrupted concurrent index creation)

See the "Migration Gap Detection" section in `MIGRATION_UPGRADE_003a_to_004.md` for detailed validation queries and remediation steps.

## Upgrade Notes

### 003a to 004 Migration Renaming

The `003a_capability_fields_concurrent.sql` migration was renamed to `004_capability_fields_concurrent.sql`.

- **If you have 003a applied**: No database changes needed; the SQL is identical
- **For new deployments**: Use `forward/004_capability_fields_concurrent.sql`
- **Full details**: See `MIGRATION_UPGRADE_003a_to_004.md`
- **Validation**: Run `validate_migration_state.sql` to check current state
