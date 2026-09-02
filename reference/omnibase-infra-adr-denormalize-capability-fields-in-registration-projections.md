---
type: reference
status: current
date: "2026-09-02"
title: "ADR-005: Denormalize Capability Fields in Registration Projections"
topics: [omnibase-infra, adr, denormalize, capability]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-005-denormalize-capability-fields-in-registration-projections.md on 2026-09-02. -->

# ADR-005: Denormalize Capability Fields in Registration Projections

## Status

Accepted

## Date

2026-01-09

## Context

The ONEX registry projection system stores snapshots of node registrations for efficient querying. A critical use case is **capability-based routing**: finding nodes that support specific protocols, intent types, or capability tags.

**Problem Statement**: The original design stored capabilities in the source registration events, requiring one of the following approaches to query by capability:

1. **Event replay**: Replay events to reconstruct capabilities (slow, O(n) per query)
2. **JSON parsing**: Store capabilities as JSON and use JSON operators (complex queries, limited index support)
3. **Separate joins**: Maintain a separate capabilities table and join on queries (join overhead, consistency complexity)

**Use Cases Requiring Fast Capability Lookups**:

1. **Protocol-based routing**: "Find all nodes implementing `ProtocolHealthCheck`"
2. **Intent filtering**: "Find nodes that can handle `registration` intent types"
3. **Tag-based discovery**: "Find all `database-adapter` tagged nodes"
4. **Contract type filtering**: "Find all `EFFECT` nodes"
5. **Version compatibility**: "Find nodes with contract version >= 1.0.0"

**Performance Requirements**:

- Capability lookups must be O(1) or O(log n) for routing decisions
- Queries should not require joins with event tables
- Filtering by multiple capability dimensions must be efficient

## Decision

We denormalized five capability fields directly into the `registration_projections` table:

### 1. Schema Changes

```sql
ALTER TABLE registration_projections ADD COLUMN contract_type VARCHAR(50);
ALTER TABLE registration_projections ADD COLUMN contract_version VARCHAR(20);
ALTER TABLE registration_projections ADD COLUMN intent_types TEXT[];
ALTER TABLE registration_projections ADD COLUMN protocols TEXT[];
ALTER TABLE registration_projections ADD COLUMN capability_tags TEXT[];
```

### 2. Index Strategy

| Column | Index Type | Rationale |
|--------|------------|-----------|
| `contract_type` | B-tree | Low cardinality enum (EFFECT, COMPUTE, REDUCER, ORCHESTRATOR) |
| `contract_version` | None | Typically used in combination with other filters |
| `intent_types` | GIN | Array containment queries (`@>`, `&&`) |
| `protocols` | GIN | Array containment queries (`@>`, `&&`) |
| `capability_tags` | GIN | Array containment queries (`@>`, `&&`) |

```sql
CREATE INDEX idx_registration_projections_contract_type
    ON registration_projections(contract_type);
CREATE INDEX idx_registration_projections_intent_types
    ON registration_projections USING GIN(intent_types);
CREATE INDEX idx_registration_projections_protocols
    ON registration_projections USING GIN(protocols);
CREATE INDEX idx_registration_projections_capability_tags
    ON registration_projections USING GIN(capability_tags);
```

### 3. Data Population

Capability fields are populated by the `RegistryProjectionEffect` node when processing registration events:

```python
async def _extract_capabilities(
    self, event: ModelNodeRegisteredEvent
) -> dict[str, Any]:
    """Extract capability fields from registration event."""
    return {
        "contract_type": event.contract_type.value if event.contract_type else None,
        "contract_version": event.contract_version,
        "intent_types": list(event.intent_types) if event.intent_types else [],
        "protocols": list(event.protocols) if event.protocols else [],
        "capability_tags": list(event.capability_tags) if event.capability_tags else [],
    }
```

### 4. Query Patterns Enabled

**Find nodes by protocol**:
```sql
SELECT * FROM registration_projections
WHERE protocols @> ARRAY['ProtocolHealthCheck'];
```

**Find nodes by multiple capabilities**:
```sql
SELECT * FROM registration_projections
WHERE contract_type = 'EFFECT'
  AND intent_types && ARRAY['registration', 'heartbeat']
  AND capability_tags @> ARRAY['database-adapter'];
```

**Find nodes by any matching tag**:
```sql
SELECT * FROM registration_projections
WHERE capability_tags && ARRAY['critical', 'high-priority'];
```

### 5. Consistency Model

Capability fields are updated **synchronously** during projection writes:

- **On registration**: All capability fields are populated from the event
- **On re-registration**: Capability fields are updated to reflect current state
- **On deregistration**: Record is marked inactive; capability fields remain for historical queries

This ensures capability data is always consistent with the projection state.

## Consequences

### Positive

- **O(1) capability lookups**: GIN indexes enable constant-time array containment checks
- **No join overhead**: All capability data is co-located with projection data
- **Flexible querying**: Supports protocol, intent, tag, and contract type filtering
- **Composable filters**: Multiple capability dimensions can be combined efficiently
- **SQL-native**: Uses standard PostgreSQL operators, no custom query logic needed
- **Historical preservation**: Deregistered nodes retain capabilities for audit queries

### Negative

- **Write amplification**: Every registration write updates 5 additional columns
- **Index maintenance**: 4 indexes must be updated on each write (B-tree + 3 GIN)
- **Storage overhead**: Denormalized data duplicates capability information
- **GIN index size**: Array indexes can grow significantly with high-cardinality tags
- **Schema coupling**: Capability field changes require projection schema migrations

### Neutral

- **Read-heavy workload fit**: The trade-off favors reads over writes, which matches the registry access pattern (many reads, few writes)
- **PostgreSQL dependency**: GIN indexes are PostgreSQL-specific; migration to other databases would require alternative indexing

## Alternatives Considered

### 1. Materialized View with Capabilities

**Approach**: Create a materialized view joining projections with a capabilities table.

```sql
CREATE MATERIALIZED VIEW registration_capabilities_view AS
SELECT p.*, c.protocols, c.intent_types, c.capability_tags
FROM registration_projections p
JOIN registration_capabilities c ON p.node_id = c.node_id;
```

**Why rejected**:

1. **Refresh latency**: Materialized views require explicit refresh, introducing staleness
2. **Full refresh cost**: `REFRESH MATERIALIZED VIEW` is expensive for large tables
3. **Consistency complexity**: Must coordinate refresh with projection updates
4. **No incremental updates**: Cannot update single rows without full refresh

### 2. Separate Capabilities Table with Foreign Key

**Approach**: Store capabilities in a separate table with foreign key to projections.

```sql
CREATE TABLE registration_capabilities (
    node_id UUID PRIMARY KEY REFERENCES registration_projections(node_id),
    protocols TEXT[],
    intent_types TEXT[],
    capability_tags TEXT[]
);
```

**Why rejected**:

1. **Join overhead**: Every capability query requires a join
2. **Consistency risk**: Two tables must be kept in sync
3. **Transaction complexity**: Must coordinate inserts/updates across tables
4. **No performance benefit**: GIN indexes work equally well on denormalized columns

### 3. JSONB Column with GIN Index

**Approach**: Store all capabilities in a single JSONB column with GIN index.

```sql
ALTER TABLE registration_projections
ADD COLUMN capabilities JSONB;

CREATE INDEX idx_capabilities_gin
ON registration_projections USING GIN(capabilities);
```

**Why rejected**:

1. **Query complexity**: JSONB queries are verbose (`capabilities @> '{"protocols": ["ProtocolHealthCheck"]}'`)
2. **Type safety**: No schema enforcement on JSONB structure
3. **Index limitations**: GIN on JSONB indexes all keys, not just capability arrays
4. **Harder to extend**: Adding new capability types requires JSON structure changes

### 4. Event Sourcing with CQRS Read Model

**Approach**: Maintain capabilities purely through event replay with a dedicated read model.

**Why rejected**:

1. **Query latency**: Event replay is O(n) for each query
2. **Complexity**: Requires separate CQRS infrastructure
3. **Overkill**: Registry queries don't need full event sourcing benefits
4. **Projection already exists**: We already have a projection table; denormalization extends it naturally

## Implementation Notes

### Key Files

- `docker/migrations/forward/003_capability_fields.sql`: Schema migration
- `src/omnibase_infra/nodes/registry_projection_effect/node.py`: Capability extraction
- `tests/integration/registry/test_capability_queries.py`: Query pattern tests

### Migration Strategy

The migration is additive and non-breaking:

1. Add nullable columns (no default required)
2. Create indexes (CONCURRENTLY to avoid locks)
3. Backfill existing rows from source events
4. Future registrations populate columns automatically

### Performance Characteristics

Based on PostgreSQL GIN index benchmarks:

- **Array containment** (`@>`): O(1) average case with GIN
- **Array overlap** (`&&`): O(k) where k is the smaller array size
- **B-tree equality**: O(log n) for contract_type lookups

### Monitoring

Track capability query performance via:

```sql
-- Check index usage
SELECT indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE indexrelname LIKE 'idx_registration_projections_%';
```

## References

- **PostgreSQL GIN Documentation**: https://www.postgresql.org/docs/current/gin-intro.html
- **ADR-001**: Graceful Shutdown (related projection lifecycle)
- **ADR-004**: Performance Baseline Thresholds (related performance considerations)
