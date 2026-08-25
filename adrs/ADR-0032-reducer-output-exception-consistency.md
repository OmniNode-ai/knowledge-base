---
type: adr
status: accepted
date: "2025-12-16"
title: "ADR-0032: Reducer Output Exception Consistency"
adr_id: ADR-0032
topics: [omnibase_core, reducers, error-handling, pydantic, sentinel-pattern]
refs: [adrs/ADR-0037-validator-error-handling-modelonexerror.md]
supersedes: []
superseded_by: []
---

# ADR-0032: Reducer Output Exception Consistency

**Status**: Implemented
**Date**: 2025-12-16
**Implementation**: `src/omnibase_core/models/reducer/model_reducer_output.py`
**Source**: omnibase_core `docs/decisions/ADR-003-reducer-output-exception-consistency.md`

> Related: [ADR-0037](ADR-0037-validator-error-handling-modelonexerror.md) covers validator error handling patterns that complement this decision, generalizing the `ModelOnexError` approach to validators across the codebase.

---

## Document Purpose

This decision documents the rationale for using `ModelOnexError` (project-specific structured error) instead of `ValueError` (Pydantic convention) in field validators for `ModelReducerOutput`.

---

## Context

Pydantic `@field_validator` decorators need to raise validation errors when field values violate business rules. `ModelReducerOutput` specifically needs a **sentinel value pattern**: `processing_time_ms` and `items_processed` accept `-1` as a sentinel meaning "measurement unavailable" while rejecting all other negative values.

## Decision

Use `ModelOnexError` (not `ValueError`) in `ModelReducerOutput`'s field validators, consistent with the rest of the ONEX framework's error-handling convention (see [ADR-0037](ADR-0037-validator-error-handling-modelonexerror.md) for the full rationale, which this decision predates and which now supersedes it as the canonical statement of the pattern).

### Sentinel Value Pattern

```python
@field_validator("processing_time_ms")
@classmethod
def validate_processing_time_ms(cls, v: float) -> float:
    """Validate processing_time_ms follows sentinel pattern.

    Enforces that:
    1. Special float values (NaN, Inf, -Inf) are ALWAYS rejected
    2. Negative values are ONLY -1.0 (sentinel for unavailable/failed)
    3. Any other negative value is invalid
    """
    import math

    if math.isnan(v):
        raise ModelOnexError(
            error_code=EnumCoreErrorCode.VALIDATION_ERROR,
            message="processing_time_ms cannot be NaN (not a number)",
            context={"value": str(v), "field": "processing_time_ms"},
        )
    if math.isinf(v):
        raise ModelOnexError(
            error_code=EnumCoreErrorCode.VALIDATION_ERROR,
            message=f"processing_time_ms cannot be {'positive' if v > 0 else 'negative'} infinity",
            context={"value": str(v), "field": "processing_time_ms"},
        )
    if v < 0.0 and v != -1.0:
        raise ModelOnexError(
            error_code=EnumCoreErrorCode.VALIDATION_ERROR,
            message=f"processing_time_ms must be >= 0.0 or exactly -1.0 (sentinel), got {v}",
            context={"value": v, "field": "processing_time_ms", "sentinel_value": -1.0},
        )
    return v
```

## Consequences

- **Positive**: Structured, machine-readable errors (error code + context dict) instead of unstructured strings; consistent with the framework-wide `ModelOnexError` convention.
- **Negative**: Diverges from Pydantic's own recommended `ValueError`/`PydanticCustomError` pattern — see [ADR-0037](ADR-0037-validator-error-handling-modelonexerror.md) for the full compatibility analysis and migration contingency.

---

## References

- [ADR-0037](ADR-0037-validator-error-handling-modelonexerror.md): Validator Error Handling with ModelOnexError (the generalized, canonical statement of this pattern)
- `src/omnibase_core/models/reducer/model_reducer_output.py` — reference implementation

---

## Changelog

| Date | Changes |
|------|---------|
| 2026-08-25 | Migrated to knowledge base; de-linked a product-repo PR URL reference per KB sanitization policy (was PR #205, same PR ADR-0037 originates from) |
| 2025-12-16 | Initial decision |
