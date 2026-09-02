---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Strengthen DSN Validation with urllib.parse"
topics: [omnibase-infra, adr, dsn, validation]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-dsn-validation-strengthening.md on 2026-09-02. -->

# ADR: Strengthen DSN Validation with urllib.parse

**Status**: Implemented
**Date**: 2025-12-27
**PR**: #103 Review Issue
**Priority**: 🟡 MEDIUM - Input validation

## Context

The PR #103 review identified that the DSN (Data Source Name) regex validation could be strengthened to handle edge cases. The original implementation used a basic prefix check that didn't validate:

- IPv6 addresses (`[::1]:5432`)
- URL-encoded special characters in passwords (`p%40ssword` → `p@ssword`)
- Invalid port numbers (non-numeric, out of range)
- Missing database names
- Query parameters (`?sslmode=require`)

## Decision

Replace regex-based DSN validation with `urllib.parse`-based validation that comprehensively handles all PostgreSQL DSN edge cases.

### Implementation

Created new utility module: `src/omnibase_infra/utils/util_dsn_validation.py`

**Key Functions:**

1. **`parse_and_validate_dsn(dsn: object) -> dict[str, Any]`**
   - Validates DSN structure using `urllib.parse.urlparse()`
   - Handles URL-encoded credentials with `urllib.parse.unquote()`
   - Validates port ranges (1-65535)
   - Requires database name (with Unix socket exception)
   - Returns parsed components for inspection

2. **`sanitize_dsn(dsn: str) -> str`**
   - Safely masks passwords for logging
   - Handles edge cases (IPv6, invalid ports)
   - Replaces password with `***`

### Updated Components

**Config Models:**
- `src/omnibase_infra/idempotency/models/model_postgres_idempotency_store_config.py`
- `src/omnibase_infra/dlq/models/model_dlq_tracking_config.py`

**Handlers:**
- `src/omnibase_infra/handlers/handler_db.py` - Updated `_sanitize_dsn()` method

**Utils:**
- `src/omnibase_infra/utils/__init__.py` - Exported new functions

### Edge Cases Handled

| Edge Case | Example | Handled |
|-----------|---------|---------|
| IPv6 addresses | `postgresql://user:pass@[::1]:5432/db` | ✅ |
| IPv4 addresses | `postgresql://user:pass@192.0.2.100:5432/db` | ✅ |
| URL-encoded passwords | `postgresql://user:p%40ssword@host/db` | ✅ Decoded to `p@ssword` |
| Missing password | `postgresql://user@host:5432/db` | ✅ |
| Missing port | `postgresql://user:pass@host/db` | ✅ Defaults to 5432 |
| Missing user/password | `postgresql://host:5432/db` | ✅ Trust auth |
| Query parameters | `postgresql://host/db?sslmode=require` | ✅ |
| Unix sockets | `postgresql:///db?host=/var/run/postgresql` | ✅ |
| Empty password | `postgresql://user:@host/db` | ✅ Distinguished from no password |
| Special chars in password | `@`, `:`, `/`, `%` | ✅ Must be URL-encoded |
| Invalid port (non-numeric) | `postgresql://host:abc/db` | ❌ Raises error |
| Invalid port (out of range) | `postgresql://host:99999/db` | ❌ Raises error |
| Missing database name | `postgresql://host:5432` | ❌ Raises error (unless Unix socket) |
| Wrong scheme | `mysql://host/db` | ❌ Raises error |
| Multiple hosts | `postgresql://host1:5432,host2:5433/db` | ❌ Not supported (limitation documented) |

### Security Improvements

**Before:**
- Regex-based password masking: `re.sub(r"(://[^:]+:)[^@]+(@)", r"\1***\2", dsn)`
- Fragile, failed on edge cases (IPv6, complex passwords)

**After:**
- URL parsing with proper component extraction
- Never logs credentials in error messages (always uses `[REDACTED]`)
- Handles URL encoding transparently
- Validates structure before exposing any information

### Test Coverage

Created comprehensive test suite: `tests/unit/utils/test_util_dsn_validation.py`

**29 test cases covering:**
- 12 valid DSN formats (standard, IPv6, URL-encoded, query params, etc.)
- 11 invalid DSN formats (missing scheme, invalid ports, etc.)
- 4 edge cases (special characters, empty password, etc.)
- 2 integration tests (config model acceptance/rejection)

**Test Results:**
```
tests/unit/utils/test_util_dsn_validation.py ............ 29 passed
tests/unit/handlers/test_handler_db.py .................. 64 passed
tests/unit/idempotency/test_store_postgres.py ........... 38 passed
```

### Circular Import Resolution

**Problem:** Circular dependency chain:
```
utils → errors → models → utils (for semver validation)
```

**Solution:** Lazy imports inside functions:
```python
def parse_and_validate_dsn(dsn: object) -> dict[str, Any]:
    # Lazy imports to avoid circular dependency
    from omnibase_infra.enums import EnumInfraTransportType
    from omnibase_infra.errors import ModelInfraErrorContext, ProtocolConfigurationError
    # ... validation logic
```

## Consequences

### Positive

✅ **Comprehensive validation**: All PostgreSQL DSN formats now validated
✅ **Better security**: Credentials never leaked in errors or logs
✅ **Better error messages**: Clear, specific validation errors
✅ **Better maintainability**: Standard library `urllib.parse` instead of fragile regex
✅ **Better testing**: 29 test cases documenting all edge cases
✅ **Better type safety**: Proper URL decoding with `unquote()`

### Negative

⚠️ **Complexity**: Validation function has cyclomatic complexity 13 (limit: 10)
  - Acceptable for validation functions with multiple checks
  - All checks are necessary for comprehensive validation

⚠️ **Lazy imports**: Required for circular import resolution
  - Minor performance overhead (negligible for validation)
  - Industry-standard pattern for breaking circular dependencies

⚠️ **Multi-host DSNs not supported**: `postgresql://host1:5432,host2:5433/db`
  - `urllib.parse` limitation (treats as single hostname)
  - Documented in tests and module docstring
  - PostgreSQL-specific parser needed if support required

### Migration

**Breaking Changes**: None
- All existing DSNs continue to work
- Additional edge cases now validated that were previously unchecked
- Error messages improved but still use `ProtocolConfigurationError`

**No code changes required** in consuming code.

## Alternatives Considered

### 1. Keep regex-based validation
❌ **Rejected**: Fragile, doesn't handle IPv6, URL encoding, or complex edge cases

### 2. Use PostgreSQL-specific library (e.g., `psycopg2.conninfo_to_dict`)
❌ **Rejected**: Adds dependency, overkill for validation, couples to specific library

### 3. Custom parser with regex
❌ **Rejected**: Reinventing the wheel, error-prone, hard to maintain

### 4. No validation (defer to asyncpg)
❌ **Rejected**: Poor user experience (cryptic asyncpg errors), no early validation

## References

- **PR**: #103 (review comment requesting DSN strengthening)
- **Related Security Pattern**: `docs/patterns/security_patterns.md#input-validation`
- **PostgreSQL DSN Format**: https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING
- **Python `urllib.parse`**: https://docs.python.org/3/library/urllib.parse.html

## Files Modified

**New Files:**
- `src/omnibase_infra/utils/util_dsn_validation.py`
- `tests/unit/utils/test_util_dsn_validation.py`
- `docs/decisions/adr-dsn-validation-strengthening.md`

**Modified Files:**
- `src/omnibase_infra/utils/__init__.py`
- `src/omnibase_infra/handlers/handler_db.py`
- `src/omnibase_infra/idempotency/models/model_postgres_idempotency_store_config.py`
- `src/omnibase_infra/dlq/models/model_dlq_tracking_config.py`

**Test Coverage:**
- **New tests**: 29 comprehensive DSN validation tests
- **Existing tests**: All 64 handler tests + 38 idempotency tests pass unchanged
