---
type: runbook
status: current
date: "2026-09-02"
title: "Database Index Monitoring Runbook"
topics: [omnibase-infra, database, index, monitoring]
refs: []
---

<!-- Migrated from omnibase_infra:docs/operations/DATABASE_INDEX_MONITORING_RUNBOOK.md on 2026-09-02. -->

# Database Index Monitoring Runbook

Operational guide for monitoring GIN index performance on the `registration_projections` table, including write overhead assessment, alerting thresholds, and troubleshooting procedures.

## Overview

The `registration_projections` table uses 4 indexes (3 GIN, 1 B-tree) to enable fast capability-based discovery queries. GIN (Generalized Inverted Index) indexes provide efficient array containment queries but add overhead to write operations.

**Source Migration**: `docker/migrations/forward/003_capability_fields.sql`
**Related Ticket**:  (Registry Projection Extensions for Capabilities)

### Index Inventory

| Index Name | Type | Column(s) | Purpose |
|------------|------|-----------|---------|
| `idx_registration_capability_tags` | GIN | `capability_tags` | Capability-based node discovery |
| `idx_registration_intent_types` | GIN | `intent_types` | Intent routing queries |
| `idx_registration_protocols` | GIN | `protocols` | Protocol-based service discovery |
| `idx_registration_contract_type_state` | B-tree | `contract_type`, `current_state` | Node type + state filtering |

### Expected Write Performance Impact

GIN indexes have inherent write overhead compared to B-tree indexes because they must index individual array elements:

| Operation | Expected Overhead | Notes |
|-----------|------------------|-------|
| INSERT | 15-30% | Each array element indexed separately |
| UPDATE (array column) | 20-40% | May trigger index entry rebuild |
| UPDATE (non-array column) | 5-10% | Minimal impact if array columns unchanged |
| DELETE | 10-20% | Index entries must be removed |

**Impact Factors**:
- Array size: More elements per array = higher overhead
- Concurrent writes: GIN page splits under high write load
- Index maintenance: VACUUM and autovacuum frequency

## Key Metrics to Monitor

### Write Latency Metrics

| Metric | Acceptable Range | Warning Threshold | Critical Threshold |
|--------|-----------------|-------------------|-------------------|
| INSERT latency (p50) | <10ms | >25ms | >50ms |
| INSERT latency (p95) | <50ms | >100ms | >200ms |
| INSERT latency (p99) | <100ms | >200ms | >500ms |
| UPDATE latency (p50) | <15ms | >35ms | >75ms |
| UPDATE latency (p95) | <75ms | >150ms | >300ms |
| UPDATE latency (p99) | <150ms | >300ms | >750ms |
| Index maintenance time | <10% of transaction | >15% | >25% |

### Index Health Metrics

| Metric | Acceptable Range | Warning Threshold | Critical Threshold |
|--------|-----------------|-------------------|-------------------|
| Index bloat ratio | <30% | >50% | >80% |
| Index usage ratio | >70% | <50% | <20% |
| Dead tuples (table) | <5% | >10% | >20% |
| GIN pending entries | <1000 | >5000 | >10000 |

### Query Performance Metrics

| Metric | Acceptable Range | Warning Threshold | Critical Threshold |
|--------|-----------------|-------------------|-------------------|
| Array containment query (p95) | <25ms | >50ms | >100ms |
| Index scan cost | <1000 | >5000 | >10000 |
| Rows scanned vs returned ratio | <10:1 | >50:1 | >100:1 |

## Verification Queries

### Check Index Existence and Validity

```sql
-- Verify all indexes exist and are valid
SELECT
    i.relname AS index_name,
    am.amname AS index_type,
    pg_size_pretty(pg_relation_size(i.oid)) AS index_size,
    idx.indisvalid AS is_valid,
    idx.indisready AS is_ready
FROM pg_class t
JOIN pg_index idx ON t.oid = idx.indrelid
JOIN pg_class i ON i.oid = idx.indexrelid
JOIN pg_am am ON i.relam = am.oid
WHERE t.relname = 'registration_projections'
  AND i.relname LIKE 'idx_registration_%'
ORDER BY i.relname;

-- Expected output (all indexes valid):
-- idx_registration_capability_tags     | gin   | 16 kB | t        | t
-- idx_registration_contract_type_state | btree | 16 kB | t        | t
-- idx_registration_intent_types        | gin   | 16 kB | t        | t
-- idx_registration_protocols           | gin   | 16 kB | t        | t
```

### Verify GIN Index Usage with EXPLAIN ANALYZE

```sql
-- Check capability_tags GIN index usage
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT entity_id, capability_tags
FROM registration_projections
WHERE capability_tags @> ARRAY['kafka_consumer'];

-- Expected plan for tables with >1000 rows:
-- Bitmap Heap Scan on registration_projections
--   Recheck Cond: (capability_tags @> '{kafka_consumer}'::text[])
--   ->  Bitmap Index Scan on idx_registration_capability_tags
--         Index Cond: (capability_tags @> '{kafka_consumer}'::text[])

-- Check intent_types GIN index usage
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT entity_id, intent_types
FROM registration_projections
WHERE intent_types @> ARRAY['postgres.upsert'];

-- Check protocols GIN index usage
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT entity_id, protocols
FROM registration_projections
WHERE protocols @> ARRAY['ProtocolDatabaseAdapter'];

-- Check B-tree composite index usage
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT entity_id, contract_type, current_state
FROM registration_projections
WHERE contract_type = 'effect' AND current_state = 'active';
```

**Note**: For small tables (<1000 rows), PostgreSQL may choose sequential scan over index scan. This is normal behavior - the query planner correctly identifies that sequential scans are faster for small datasets.

### Monitor Write Latency

```sql
-- Table statistics including insert/update counts
SELECT
    schemaname,
    relname,
    n_tup_ins AS inserts,
    n_tup_upd AS updates,
    n_tup_del AS deletes,
    n_live_tup AS live_tuples,
    n_dead_tup AS dead_tuples,
    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_pct,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE relname = 'registration_projections';
```

### Index Size Monitoring

```sql
-- Index sizes and bloat estimation
SELECT
    indexrelname AS index_name,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    idx_scan AS index_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
WHERE relname = 'registration_projections'
  AND indexrelname LIKE 'idx_registration_%'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Table size vs total index size
SELECT
    pg_size_pretty(pg_table_size('registration_projections')) AS table_size,
    pg_size_pretty(pg_indexes_size('registration_projections')) AS total_index_size,
    pg_size_pretty(pg_total_relation_size('registration_projections')) AS total_size,
    ROUND(100.0 * pg_indexes_size('registration_projections') /
          NULLIF(pg_total_relation_size('registration_projections'), 0), 2) AS index_pct;
```

### Index Usage Analysis

```sql
-- Index usage statistics (should show high usage for capability queries)
SELECT
    schemaname,
    relname,
    indexrelname,
    idx_scan AS number_of_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched,
    ROUND(100.0 * idx_scan / NULLIF(
        (SELECT sum(idx_scan) FROM pg_stat_user_indexes
         WHERE relname = 'registration_projections'), 0), 2) AS usage_pct
FROM pg_stat_user_indexes
WHERE relname = 'registration_projections'
ORDER BY idx_scan DESC;
```

### GIN-Specific Monitoring

```sql
-- GIN index pending entries (fastupdate mode)
-- High pending counts indicate index update lag
SELECT
    indexrelid::regclass AS index_name,
    gin_pending_list_limit,
    n_pending_pages,
    pending_pages AS pending_entries
FROM pg_stat_gin_index
WHERE indexrelid::regclass::text LIKE '%registration%';

-- Note: This view may not exist in all PostgreSQL versions.
-- For PostgreSQL < 14, use:
SELECT
    i.relname AS index_name,
    pg_size_pretty(pg_relation_size(i.oid)) AS size
FROM pg_class i
JOIN pg_index idx ON i.oid = idx.indexrelid
JOIN pg_am am ON i.relam = am.oid
WHERE am.amname = 'gin'
  AND i.relname LIKE 'idx_registration_%';
```

## Alerting Recommendations

### Prometheus/Grafana Alert Rules

```yaml
# prometheus-alerts.yaml
groups:
  - name: registration_projections_indexes
    interval: 30s
    rules:
      # Write latency alerts
      - alert: RegistrationInsertLatencyHigh
        expr: |
          histogram_quantile(0.95,
            rate(pg_stat_statements_mean_time_seconds{
              query=~"INSERT INTO registration_projections.*"
            }[5m])
          ) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "INSERT p95 latency > 100ms for 5 minutes"
          description: "GIN index maintenance may be impacting write performance"

      - alert: RegistrationInsertLatencyCritical
        expr: |
          histogram_quantile(0.95,
            rate(pg_stat_statements_mean_time_seconds{
              query=~"INSERT INTO registration_projections.*"
            }[5m])
          ) > 0.2
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "INSERT p95 latency > 200ms for 5 minutes"
          description: "Immediate investigation required - consider index rebuild"

      # Index bloat alerts
      - alert: RegistrationIndexBloatHigh
        expr: |
          (pg_stat_user_indexes_idx_blks_hit{relname="registration_projections"} /
           NULLIF(pg_stat_user_indexes_idx_blks_read{relname="registration_projections"} +
                  pg_stat_user_indexes_idx_blks_hit{relname="registration_projections"}, 0)
          ) < 0.5
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Index bloat >50% of table size"
          description: "Consider REINDEX CONCURRENTLY"

      # Dead tuple alerts
      - alert: RegistrationDeadTuplesHigh
        expr: |
          pg_stat_user_tables_n_dead_tup{relname="registration_projections"} /
          NULLIF(pg_stat_user_tables_n_live_tup{relname="registration_projections"}, 0) > 0.1
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Dead tuples >10% of live tuples"
          description: "VACUUM may not be running frequently enough"
```

### Simple SQL-Based Monitoring (for environments without Prometheus)

```sql
-- Create monitoring view for dashboards
CREATE OR REPLACE VIEW v_registration_index_health AS
SELECT
    'registration_projections' AS table_name,
    pg_size_pretty(pg_table_size('registration_projections')) AS table_size,
    pg_size_pretty(pg_indexes_size('registration_projections')) AS index_size,
    (SELECT n_live_tup FROM pg_stat_user_tables
     WHERE relname = 'registration_projections') AS live_tuples,
    (SELECT n_dead_tup FROM pg_stat_user_tables
     WHERE relname = 'registration_projections') AS dead_tuples,
    ROUND(100.0 * (SELECT n_dead_tup FROM pg_stat_user_tables
                   WHERE relname = 'registration_projections') /
          NULLIF((SELECT n_live_tup + n_dead_tup FROM pg_stat_user_tables
                  WHERE relname = 'registration_projections'), 0), 2) AS dead_pct,
    (SELECT count(*) FROM pg_stat_user_indexes
     WHERE relname = 'registration_projections' AND idx_scan = 0) AS unused_indexes,
    CASE
        WHEN (SELECT n_dead_tup::float / NULLIF(n_live_tup, 0)
              FROM pg_stat_user_tables WHERE relname = 'registration_projections') > 0.2
        THEN 'CRITICAL'
        WHEN (SELECT n_dead_tup::float / NULLIF(n_live_tup, 0)
              FROM pg_stat_user_tables WHERE relname = 'registration_projections') > 0.1
        THEN 'WARNING'
        ELSE 'OK'
    END AS health_status,
    now() AS checked_at;

-- Query the monitoring view
SELECT * FROM v_registration_index_health;
```

### Alert Response Procedures

| Alert | Immediate Action | Root Cause Investigation |
|-------|-----------------|-------------------------|
| INSERT latency >100ms | Check for long-running transactions | Examine pg_stat_activity for blocking |
| INSERT latency >200ms | Consider disabling non-critical indexes temporarily | Analyze array column cardinality |
| Index bloat >50% | Schedule REINDEX CONCURRENTLY | Review VACUUM settings |
| Dead tuples >10% | Manual VACUUM ANALYZE | Check autovacuum configuration |
| Unused index detected | Verify query patterns | Consider removing if unused for 7+ days |

## Troubleshooting

### High Write Latency

**Symptoms**: INSERT/UPDATE operations taking >100ms consistently

**Investigation Steps**:
```sql
-- 1. Check for blocking queries
SELECT
    blocked.pid AS blocked_pid,
    blocked.query AS blocked_query,
    blocking.pid AS blocking_pid,
    blocking.query AS blocking_query,
    now() - blocked.query_start AS blocked_duration
FROM pg_stat_activity blocked
JOIN pg_locks blocked_locks ON blocked.pid = blocked_locks.pid
JOIN pg_locks blocking_locks
    ON blocked_locks.locktype = blocking_locks.locktype
    AND blocked_locks.database IS NOT DISTINCT FROM blocking_locks.database
    AND blocked_locks.relation IS NOT DISTINCT FROM blocking_locks.relation
    AND blocked_locks.page IS NOT DISTINCT FROM blocking_locks.page
    AND blocked_locks.tuple IS NOT DISTINCT FROM blocking_locks.tuple
    AND blocked.pid != blocking_locks.pid
JOIN pg_stat_activity blocking ON blocking_locks.pid = blocking.pid
WHERE NOT blocked_locks.granted;

-- 2. Check autovacuum status
SELECT
    relname,
    n_dead_tup,
    last_autovacuum,
    autovacuum_count
FROM pg_stat_user_tables
WHERE relname = 'registration_projections';

-- 3. Check if GIN fastupdate is causing lag
SHOW gin_pending_list_limit;
```

**Resolution**:
1. If blocking queries found: Investigate and terminate if appropriate
2. If dead tuples high: Run `VACUUM ANALYZE registration_projections;`
3. If GIN pending high: Run `VACUUM registration_projections;` to flush pending entries

### Index Not Being Used

**Symptoms**: Sequential scans instead of index scans for capability queries

**Investigation Steps**:
```sql
-- 1. Check table statistics are current
SELECT
    relname,
    last_analyze,
    last_autoanalyze,
    n_live_tup
FROM pg_stat_user_tables
WHERE relname = 'registration_projections';

-- 2. Force index usage to compare performance
SET enable_seqscan = off;
EXPLAIN ANALYZE SELECT * FROM registration_projections
WHERE capability_tags @> ARRAY['postgres.storage'];
SET enable_seqscan = on;

-- 3. Check index validity
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'registration_projections'
  AND indexname LIKE 'idx_registration_%';
```

**Resolution**:
1. If statistics outdated: Run `ANALYZE registration_projections;`
2. If index invalid: Run `REINDEX INDEX CONCURRENTLY idx_registration_capability_tags;`
3. If table too small (<1000 rows): Sequential scan is expected and optimal

### Index Bloat

**Symptoms**: Index size grows disproportionately to table size

**Investigation Steps**:
```sql
-- Check index vs table size ratio
SELECT
    pg_size_pretty(pg_table_size('registration_projections')) AS table_size,
    pg_size_pretty(pg_indexes_size('registration_projections')) AS index_size,
    ROUND(100.0 * pg_indexes_size('registration_projections') /
          NULLIF(pg_table_size('registration_projections'), 0), 2) AS index_ratio_pct;

-- Healthy ratio: 50-150% of table size
-- Bloated: >200% of table size
```

**Resolution**:
```sql
-- Rebuild specific index without blocking writes
REINDEX INDEX CONCURRENTLY idx_registration_capability_tags;
REINDEX INDEX CONCURRENTLY idx_registration_intent_types;
REINDEX INDEX CONCURRENTLY idx_registration_protocols;
REINDEX INDEX CONCURRENTLY idx_registration_contract_type_state;

-- Or rebuild all indexes on the table
REINDEX TABLE CONCURRENTLY registration_projections;
```

## Performance Tuning

### PostgreSQL Configuration Recommendations

```ini
# postgresql.conf settings for GIN indexes

# Increase maintenance work memory for faster index builds
maintenance_work_mem = 256MB  # Default: 64MB

# GIN-specific settings
gin_pending_list_limit = 4MB  # Default: 4MB (increase for high-write workloads)
gin_fuzzy_search_limit = 0    # Default: 0 (no limit)

# Autovacuum tuning for high-write tables
autovacuum_vacuum_scale_factor = 0.1    # Vacuum when 10% of tuples are dead
autovacuum_analyze_scale_factor = 0.05  # Analyze when 5% of tuples changed
autovacuum_vacuum_cost_delay = 10ms     # Reduce to speed up autovacuum
```

### Table-Specific Autovacuum Settings

```sql
-- Aggressive autovacuum for high-write registration table
ALTER TABLE registration_projections SET (
    autovacuum_vacuum_scale_factor = 0.05,      -- Vacuum at 5% dead tuples
    autovacuum_analyze_scale_factor = 0.02,     -- Analyze at 2% changes
    autovacuum_vacuum_threshold = 50,           -- Minimum 50 dead tuples
    autovacuum_analyze_threshold = 50           -- Minimum 50 changed tuples
);
```

## Related Documentation

- Database Migrations - Migration versioning and execution
- Event Bus Operations (`../runbooks/omnibase-infra-event-bus-operations.md`) - Related Kafka event handling
- Thread Pool Tuning (internal knowledge base) - Connection pool optimization
