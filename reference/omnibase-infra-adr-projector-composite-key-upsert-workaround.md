---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Projector Composite Key Upsert Workaround"
topics: [omnibase-infra, adr, projector, composite]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-projector-composite-key-upsert-workaround.md on 2026-09-02. -->

# ADR: Projector Composite Key Upsert Workaround

**Status**: Accepted
**Date**: 2026-01-15

## Context

The registration projector requires multi-domain support, where the same projection table can store entities across different domain namespaces (e.g., `registration`, `discovery`, `monitoring`). This is achieved through a composite primary key `(entity_id, domain)` in the PostgreSQL schema.

### The Composite Key Design

```sql
-- From 001_registration_projection.sql
PRIMARY KEY (entity_id, domain)
```

This design enables:
- Same `entity_id` to exist in multiple domains (e.g., a node registered in both `registration` and `discovery` domains)
- Domain-specific queries without cross-contamination
- Future extensibility for multi-tenant or domain-partitioned deployments

### The ModelProjectorContract Limitation

The `ModelProjectorContract` class from `omnibase-core` (used by `ProjectorShell`) only supports **single-column** `upsert_key` specifications. The contract validation enforces this constraint:

```python
# omnibase-core behavior
class ModelProjectorContract:
    upsert_key: str  # Single column name, not list
```

When `ProjectorShell.project()` generates the upsert SQL, it produces:

```sql
INSERT INTO registration_projections (...)
VALUES (...)
ON CONFLICT (upsert_key) DO UPDATE SET ...
```

This works for single-column keys but **cannot generate** `ON CONFLICT (entity_id, domain)` for composite keys.

### The Problem

The declarative contract (`registration_projector.yaml`) specifies a composite upsert key:

```yaml
# registration_projector.yaml
behavior:
  upsert_key:
    - entity_id
    - domain
```

However, `ProjectorShell` cannot process this composite key - it expects a single string value.

## Decision

**Add a separate UNIQUE constraint on `entity_id` alone to enable single-column upserts.**

### Implementation

```sql
-- 001_registration_projection.sql (lines 89-94)
PRIMARY KEY (entity_id, domain),
-- UNIQUE constraint on entity_id enables ON CONFLICT (entity_id) upserts.
-- Required because omnibase-core's ModelProjectorContract only supports single-column
-- upsert_key, but we need composite PK for multi-domain support.
UNIQUE (entity_id),
```

This allows `ProjectorShell` to use:

```sql
ON CONFLICT (entity_id) DO UPDATE SET ...
```

### Trade-off: Entity ID Global Uniqueness

**CRITICAL**: This workaround enforces that `entity_id` is globally unique across ALL domains.

| Scenario | Composite PK Allows | With UNIQUE Workaround |
|----------|---------------------|------------------------|
| Same entity_id in different domains | YES | NO (constraint violation) |
| Multi-domain entity registration | Supported | Not supported |
| Domain-partitioned deployments | Full isolation | entity_id collision across domains |

In practice, this means:
- A node with `entity_id=abc123` registered in `domain=registration` **cannot** also be registered in `domain=discovery`
- The `domain` column becomes effectively a metadata field, not a true partition key

## Consequences

### Positive

1. **Enables declarative projector contracts** - ProjectorShell can process the contract without custom code
2. **Maintains database integrity** - Upserts work correctly with idempotency guarantees
3. **No omnibase-core changes required** - Works with existing infrastructure
4. **Clear documentation** - SQL comments and this ADR explain the constraint

### Negative

1. **Multi-domain entity registration blocked** - Same entity cannot exist in multiple domains
2. **Future flexibility reduced** - If multi-domain support is needed later, schema migration required
3. **Design intent obscured** - Composite PK suggests multi-domain support that doesn't fully work
4. **Redundant constraint** - UNIQUE on entity_id is semantically redundant with PK (but required for upsert)

### Neutral

1. **Current use case unaffected** - Registration domain uses single-domain pattern today
2. **Migration path exists** - Can be resolved if omnibase-core adds composite key support

## Alternatives Considered

### 1. Modify omnibase-core ModelProjectorContract

**Description**: Update `ModelProjectorContract` to support composite upsert keys.

```python
# Proposed change
class ModelProjectorContract:
    upsert_key: str | list[str]  # Support both single and composite
```

**Pros**:
- Proper solution at the right abstraction layer
- Enables true multi-domain support
- No workaround constraints

**Cons**:
- Requires cross-repository change (omnibase-core)
- Breaking change to contract validation
- Increases complexity of SQL generation in ProjectorShell

**Decision**: Deferred. Track in omnibase-core backlog for future consideration.

### 2. Domain-Prefixed entity_id

**Description**: Encode domain into entity_id (e.g., `registration:abc123`).

**Pros**:
- Single-column key works naturally
- No schema workarounds

**Cons**:
- Breaks UUID semantics (entity_id is typically a UUID)
- Requires upstream changes to entity ID generation
- Complicates queries and integrations
- Cannot be retrofitted to existing data

**Decision**: Rejected. Too invasive and breaks established patterns.

### 3. Single-Column Primary Key (entity_id only)

**Description**: Remove `domain` from primary key entirely.

**Pros**:
- Simplest approach
- No workaround needed

**Cons**:
- Loses multi-domain design intent
- Future extensibility blocked at schema level
- Cannot add multi-domain later without major migration

**Decision**: Rejected. Preserving composite PK structure allows future migration if omnibase-core is updated.

### 4. Custom ProjectorRegistration Implementation

**Description**: Keep legacy `ProjectorRegistration` class with hand-written SQL instead of using `ProjectorShell`.

**Pros**:
- Full control over SQL generation
- Can use composite `ON CONFLICT` clause

**Cons**:
- Defeats purpose of declarative contracts
- Increases maintenance burden
- Diverges from ONEX contract-driven architecture

**Decision**: Rejected. Declarative contracts are a core ONEX principle.

## Migration Path

If omnibase-core adds composite key support in the future:

1. **Update ModelProjectorContract** to accept `list[str]` for upsert_key
2. **Update ProjectorShell** SQL generation to handle composite ON CONFLICT
3. **Migration SQL**:
   ```sql
   -- Remove the workaround constraint
   ALTER TABLE registration_projections DROP CONSTRAINT registration_projections_entity_id_key;
   ```
4. **Update registration_projector.yaml** to use composite upsert_key (already specified)
5. **Validate** that multi-domain registration works if needed

## References

- `docker/migrations/forward/001_registration_projection.sql` - Schema with workaround (lines 89-94)
- `src/omnibase_infra/projectors/contracts/registration_projector.yaml` - Declarative contract
- `omnibase-core/src/omnibase_core/projectors/projector_shell.py` - ProjectorShell implementation
- `omnibase-core/src/omnibase_core/projectors/models/model_projector_contract.py` - Contract model
- : Convert ProjectorRegistration to declarative contract
- PR #146: Implementation PR with composite key workaround
