---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Handler Contract Schema Evolution Strategy"
topics: [omnibase-infra, adr, handler, contract]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-handler-contract-schema-evolution.md on 2026-09-02. -->

# ADR: Handler Contract Schema Evolution Strategy

**Status**: Accepted
**Date**: 2026-01-13

## Context

The handler plugin loader uses YAML contracts (`handler_contract.yaml`) to define handler metadata for dynamic discovery and loading. As the platform evolves, the contract schema will need to change to support new features, additional metadata, or refined validation requirements.

### Current Schema (v1.0.0)

The current handler contract schema includes the following fields:

```yaml
# Required fields
name: handler-db                                    # Unique handler identifier
handler_class: omnibase_infra.handlers.handler_db.HandlerDb  # Fully qualified class path
handler_type: effect                                # Handler behavioral type

# Optional fields
tags:                                               # Discovery and filtering tags
  - database
  - postgres
security:                                           # Security metadata
  trusted_namespace: omnibase_infra.handlers
  audit_logging: true
  requires_authentication: false                    # Handler-specific
```

### Required Fields

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `string` | Unique identifier for handler discovery |
| `handler_class` | `string` | Fully qualified Python class path for dynamic import |
| `handler_type` | `enum` | Behavioral classification: `effect`, `compute`, `nondeterministic_compute` |

### Optional Fields

| Field | Type | Purpose |
|-------|------|---------|
| `tags` | `list[string]` | Tags for discovery, filtering, and categorization |
| `security` | `object` | Security metadata for loader validation |
| `security.trusted_namespace` | `string` | Expected namespace prefix for validation |
| `security.audit_logging` | `bool` | Enable audit logging for this handler |
| `security.requires_authentication` | `bool` | Handler requires authenticated context |

### Why This ADR Exists

PR #143 review identified the need to document:
1. How the handler contract schema will evolve over time
2. Whether backward compatibility will be maintained
3. How existing contracts should be migrated
4. How schema versions will be validated

## Decision

**Handler contract schemas follow the project's NO backward compatibility policy. Schema changes are always breaking changes.**

### Schema Evolution Strategy

#### 1. Breaking Changes Are Default

Per the project's No Backwards Compatibility policy, all schema changes are treated as breaking changes:

- New required fields are added without deprecation periods
- Field renames happen immediately (old names are not supported)
- Type changes are immediate (no dual-type support)
- Removed fields disappear completely (no deprecation warnings)

This policy applies because:
- Handler contracts are infrastructure configuration, not user-facing APIs
- Contract files are version-controlled alongside code
- Downstream consumers (internal teams) can update immediately
- Maintaining compatibility adds complexity without meaningful benefit

#### 2. Schema Versioning via `schema_version` Field

Handler contracts SHOULD include a `schema_version` field for explicit version tracking:

```yaml
# Recommended: Explicit schema version
schema_version: "1.0.0"
name: handler-db
handler_class: omnibase_infra.handlers.handler_db.HandlerDb
handler_type: effect
```

**Version semantics** (semantic versioning):
- **MAJOR**: Breaking changes to required fields, field renames, type changes
- **MINOR**: New optional fields, new enum values for existing fields
- **PATCH**: Documentation updates, comment changes, no structural changes

**Note**: `schema_version` is currently optional for backward compatibility with existing contracts. Future schema versions may make it required.

#### 3. Loader Validation Strategy

The `HandlerPluginLoader` validates contracts in the following order:

| Step | Validation | Error Code |
|------|------------|------------|
| 1 | File exists and is readable | `HANDLER_LOADER_001` |
| 2 | File size within limits (10MB) | `HANDLER_LOADER_005` |
| 3 | Valid YAML syntax | `HANDLER_LOADER_002` |
| 4 | Required fields present (`name`, `handler_class`, `handler_type`) | `HANDLER_LOADER_004` |
| 5 | Pydantic schema validation | `HANDLER_LOADER_003` |
| 6 | Handler class importable and implements protocol | `HANDLER_LOADER_006` |

**Schema version validation**:
- The loader does NOT enforce a specific `schema_version` value
- Schema version is informational for tooling and auditing
- Validation is performed by Pydantic models which ARE versioned

#### 4. Migration Path for Existing Contracts

When the schema changes, existing contracts MUST be updated immediately:

**Step 1**: Identify affected contracts
```bash
# Find all handler contracts
find . -name "handler_contract.yaml" -type f
```

**Step 2**: Update contracts to new schema
- No migration scripts provided (changes are typically simple)
- No deprecation warnings (old schema immediately invalid)
- Update all contracts in a single commit

**Step 3**: Verify all contracts load successfully
```bash
# Run validation
uv run python -c "
from pathlib import Path
from omnibase_infra.runtime.handler_plugin_loader import HandlerPluginLoader
loader = HandlerPluginLoader()
results = loader.load_from_directory(Path('contracts/handlers'))
print(f'Loaded {len(results)} handlers')
"
```

**Step 4**: Run tests to verify handler discovery
```bash
uv run pytest tests/integration/handlers/ -v
```

### Example Schema Changes

#### Adding a Required Field

When adding a new required field (e.g., `version`):

**Before** (schema v1.0.0):
```yaml
name: handler-db
handler_class: omnibase_infra.handlers.handler_db.HandlerDb
handler_type: effect
```

**After** (schema v2.0.0):
```yaml
schema_version: "2.0.0"
name: handler-db
handler_class: omnibase_infra.handlers.handler_db.HandlerDb
handler_type: effect
version: "1.0.0"  # NEW required field
```

**Migration**: Add `version` field to ALL existing contracts. No transition period.

#### Renaming a Field

When renaming a field (e.g., `handler_class` to `class_path`):

**Before** (schema v1.0.0):
```yaml
name: handler-db
handler_class: omnibase_infra.handlers.handler_db.HandlerDb
handler_type: effect
```

**After** (schema v2.0.0):
```yaml
schema_version: "2.0.0"
name: handler-db
class_path: omnibase_infra.handlers.handler_db.HandlerDb  # RENAMED
handler_type: effect
```

**Migration**: Rename field in ALL contracts. Old field name is immediately invalid.

#### Adding an Optional Field

When adding a new optional field (e.g., `description`):

**Before** (schema v1.0.0):
```yaml
name: handler-db
handler_class: omnibase_infra.handlers.handler_db.HandlerDb
handler_type: effect
```

**After** (schema v1.1.0):
```yaml
schema_version: "1.1.0"
name: handler-db
handler_class: omnibase_infra.handlers.handler_db.HandlerDb
handler_type: effect
description: "PostgreSQL database operations handler"  # NEW optional field
```

**Migration**: Optional - existing contracts continue to work. Recommended to add for completeness.

## Consequences

### Positive

1. **Simplicity**: No complex version negotiation or compatibility layers
2. **Clarity**: Schema is always consistent - no mixed versions in production
3. **Velocity**: Schema improvements are not blocked by compatibility concerns
4. **Tooling**: Validation logic is straightforward (single schema version)
5. **Auditability**: `schema_version` field provides explicit tracking

### Negative

1. **Migration burden**: All contracts must be updated for breaking changes
2. **Coordination required**: Schema changes must be coordinated across teams
3. **No rollback**: Cannot mix old and new schemas during migration

### Neutral

1. **Matches project philosophy**: Consistent with overall no-backward-compatibility policy
2. **Infrastructure scope**: Contract changes are internal, not user-facing

## Implementation

### Pydantic Contract Model

The contract schema is defined via Pydantic:

```python
# src/omnibase_infra/models/runtime/model_handler_contract.py
from pydantic import BaseModel, Field

class ModelHandlerContract(BaseModel):
    """Handler contract schema definition.

    Schema Version: 1.0.0
    """

    # Required fields
    name: str = Field(description="Unique handler identifier")
    handler_class: str = Field(description="Fully qualified class path")
    handler_type: str = Field(description="Handler behavioral type")

    # Optional fields
    schema_version: str | None = Field(
        default=None,
        description="Contract schema version (semver)"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Discovery and filtering tags"
    )
    security: dict[str, object] | None = Field(
        default=None,
        description="Security metadata for loader validation"
    )
```

### CI Validation

Add schema validation to CI pipeline:

```yaml
# .github/workflows/ci.yml
- name: Validate Handler Contracts
  run: |
    uv run python -c "
    from pathlib import Path
    from omnibase_infra.runtime.handler_plugin_loader import HandlerPluginLoader
    loader = HandlerPluginLoader()
    results = loader.load_from_directory(Path('contracts/handlers'))
    print(f'Validated {len(results)} handler contracts')
    "
```

### Schema Change Checklist

When making schema changes:

- [ ] Update `ModelHandlerContract` Pydantic model
- [ ] Update `schema_version` in model docstring
- [ ] Update ALL existing `handler_contract.yaml` files
- [ ] Update this ADR's "Current Schema" section
- [ ] Update `CLAUDE.md` handler contract documentation
- [ ] Update `docs/patterns/handler_plugin_loader.md` examples
- [ ] Run full test suite to verify handler loading
- [ ] Document change in commit message with new schema version

## References

- `contracts/handlers/*/handler_contract.yaml` - Existing handler contracts
- `src/omnibase_infra/runtime/handler_plugin_loader.py` - Loader implementation
- `src/omnibase_infra/models/runtime/model_handler_contract.py` - Contract Pydantic model
- `docs/patterns/handler_plugin_loader.md` - Handler loader pattern documentation
- ADR: Handler Plugin Loader Security Model (`../reference/omnibase-infra-adr-handler-plugin-loader-security.md`) - Security considerations
- CLAUDE.md - Project coding standards and no-backward-compatibility policy
