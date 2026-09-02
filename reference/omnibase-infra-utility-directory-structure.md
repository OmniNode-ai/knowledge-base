---
type: reference
status: current
date: "2026-09-02"
title: "Utility Directory Structure"
topics: [omnibase-infra, utility, directory, structure]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/utility_directory_structure.md on 2026-09-02. -->

# Utility Directory Structure

This document clarifies the distinction between `utils/` and `shared/utils/` directories in `omnibase_infra`.

## Quick Reference

| Directory | Status | Import Path |
|-----------|--------|-------------|
| `utils/` | **CANONICAL** | `from omnibase_infra.utils import ...` |
| `shared/utils/` | **REMOVED** | ~~`from omnibase_infra.shared.utils import ...`~~ (will raise ImportError) |

**Migration**: Update all imports from `shared.utils` to `utils`. The deprecated location has been removed per no-backwards-compatibility policy.

## Overview

The infrastructure package has a single canonical utility location (`utils/`). The legacy `shared/utils/` location has been removed:

```
src/omnibase_infra/
├── utils/                    # Cross-cutting infrastructure utilities
│   ├── __init__.py
│   ├── correlation.py        # Correlation ID generation/propagation
│   ├── util_dsn_validation.py
│   ├── util_env_parsing.py
│   ├── util_error_sanitization.py
│   └── util_semver.py
│
└── shared/
    └── utils/                # Legacy/transitional utilities (deprecated)
        └── __init__.py       # Re-exports from utils/ for compatibility
```

## Directory Purposes

### `utils/` - Cross-Cutting Infrastructure Utilities

**Location**: `src/omnibase_infra/utils/`

**Purpose**: General-purpose utilities used across multiple infrastructure components.

**Characteristics**:
- No dependencies on specific nodes or handlers
- Stateless, pure functions preferred
- Used by multiple modules across the package
- Part of the public API (`omnibase_infra.utils`)

**Current Utilities**:

| Module | Purpose |
|--------|---------|
| `correlation.py` | Correlation ID generation and context propagation for distributed tracing |
| `util_dsn_validation.py` | PostgreSQL DSN validation and credential sanitization |
| `util_env_parsing.py` | Type-safe environment variable parsing with validation |
| `util_error_sanitization.py` | Error message sanitization for secure logging and DLQ |
| `util_semver.py` | Semantic versioning validation utilities |

**Usage**:
```python
from omnibase_infra.utils import (
    generate_correlation_id,
    sanitize_error_message,
    parse_env_int,
)
```

### `shared/utils/` - REMOVED

**Location**: Previously `src/omnibase_infra/shared/utils/` (now removed)

**Status**: **REMOVED** - Per CLAUDE.md, no backwards compatibility is maintained.

> **Note**: This directory has been removed entirely. All code must use the canonical `utils/` location.
> Attempting to import from `omnibase_infra.shared.utils` will raise an `ImportError`.

**Migration**: Update imports from `omnibase_infra.shared.utils` to `omnibase_infra.utils`.

## Migration Guide

### Step-by-Step Migration

1. **Search for deprecated imports**:
   ```bash
   grep -r "from omnibase_infra.shared.utils" --include="*.py" .
   ```

2. **Update each import** following the mapping:

   | Old Import (Deprecated) | New Import (Canonical) |
   |------------------------|------------------------|
   | `from omnibase_infra.shared.utils import sanitize_backend_error` | `from omnibase_infra.utils import sanitize_backend_error` |
   | `from omnibase_infra.shared.utils import sanitize_error_message` | `from omnibase_infra.utils import sanitize_error_message` |
   | `from omnibase_infra.shared.utils import sanitize_error_string` | `from omnibase_infra.utils import sanitize_error_string` |

3. **Verify no deprecation warnings** by running tests:
   ```bash
   uv run pytest -W error::DeprecationWarning
   ```

### Before/After Examples

**Before** (deprecated):
```python
# DO NOT USE - emits DeprecationWarning
from omnibase_infra.shared.utils import (
    sanitize_backend_error,
    sanitize_error_message,
)

error_msg = sanitize_error_message(raw_error)
```

**After** (canonical):
```python
# CORRECT - canonical import path
from omnibase_infra.utils import (
    sanitize_backend_error,
    sanitize_error_message,
)

error_msg = sanitize_error_message(raw_error)
```

### Removal Timeline

The `shared/utils/` directory will be removed in **v2.0.0**. Plan migrations before:

| Version | Status | Action Required |
|---------|--------|-----------------|
| **v1.x (Current)** | Deprecated | `DeprecationWarning` emitted on import |
| **v1.x (Minor)** | No changes | Warnings continue; update imports now |
| **v2.0.0** | **REMOVED** | Breaking change; imports will fail |

**Deadline**: All code must migrate to `omnibase_infra.utils` before upgrading to v2.0.0.

The deprecation warning explicitly states:
```
DeprecationWarning: Importing from 'omnibase_infra.shared.utils' is deprecated.
Use 'omnibase_infra.utils' instead.
This module will be removed in v2.0.0.
```

## Node-Specific Utilities

Nodes may have their own utility modules for node-specific helper functions:

```
nodes/node_registry_effect/
├── contract.yaml
├── node.py
├── handlers/
├── models/
└── utils/                    # Node-specific utilities (if needed)
    └── util_service_id.py    # Example: Service ID generation for this node
```

**Principle**: If a utility is only used by a single node, it belongs in that node's `utils/` directory. If it's used by multiple nodes, it belongs in the top-level `utils/`.

## Decision Matrix

| Utility Type | Location | Example |
|--------------|----------|---------|
| Cross-cutting (many consumers) | `utils/` | Correlation IDs, error sanitization |
| Node-specific (one consumer) | `nodes/<name>/utils/` | Node-specific formatting |
| Legacy (deprecated) | `shared/utils/` | Do not add new code |

## Import Conventions

**Preferred**:
```python
# Direct import from utils/
from omnibase_infra.utils import sanitize_error_message

# Or import the module for namespacing
from omnibase_infra.utils import util_error_sanitization
```

**Deprecated**:
```python
# Do not use - legacy import path
from omnibase_infra.shared.utils import sanitize_error_message  # DEPRECATED
```

## Related

- Error Sanitization Patterns (internal knowledge base) - Uses `util_error_sanitization`
- Correlation ID Tracking (`../architecture/omnibase-infra-correlation-id-tracking.md`) - Uses `correlation.py`
- Container Dependency Injection (`../architecture/omnibase-infra-container-dependency-injection.md`) - Service resolution patterns
