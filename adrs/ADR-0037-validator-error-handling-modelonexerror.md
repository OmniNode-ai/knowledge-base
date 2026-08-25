---
type: adr
status: accepted
date: "2026-01-18"
title: "ADR-0037: Validator Error Handling with ModelOnexError"
adr_id: ADR-0037
topics: [omnibase_core, pydantic, error-handling, validators]
refs: [adrs/ADR-0032-reducer-output-exception-consistency.md]
supersedes: []
superseded_by: []
---

# ADR-0037: Validator Error Handling with ModelOnexError

**Status**: Accepted
**Date**: 2026-01-18
**Source**: omnibase_core `docs/decisions/ADR-012-VALIDATOR-ERROR-HANDLING.md`

---

## Decision

Use `ModelOnexError` in Pydantic `@field_validator`/`@model_validator` decorators instead of
`ValueError` or `PydanticCustomError`. This applies to all Pydantic models in
`src/omnibase_core/models/`.

**Key benefits**: consistent error handling across the framework, structured error context
with correlation tracking, machine-readable error codes via `EnumCoreErrorCode`.

**Trade-off**: diverges from Pydantic's recommended `ValueError` pattern; may complicate a
future migration to a Pydantic major version that changes validator-exception handling.

## Context

Pydantic offers three options for a `@field_validator` to signal invalid input:

1. **Pydantic standard** — `raise ValueError(...)`.
2. **Pydantic custom** — `raise PydanticCustomError('code', 'template {value}', {'value': v})`.
3. **ONEX standard** — `raise ModelOnexError(error_code=..., message=..., context={...})`.

At authoring time, validators across the codebase used `ModelOnexError` as the uniform
pattern — see [ADR-0032](ADR-0032-reducer-output-exception-consistency.md) for the concrete
sentinel-value example this decision generalizes from.

## Rationale

1. **Framework consistency**: one error-handling pattern to learn, rather than `ValueError`
   inside validators and `ModelOnexError` everywhere else.
2. **Structured error context**: `ModelOnexError` carries `error_code`, `message`, a
   structured `context: dict`, and is correlation-ready — `ValueError` carries only a string.
3. **Machine-readable error codes**: `EnumCoreErrorCode` enables programmatic handling
   (retry logic, alerting thresholds, error-class routing) without fragile string parsing.
4. **Zero-boilerplate integration**: validators using `ModelOnexError` integrate directly
   with ONEX's `@standard_error_handling` decorator pattern without a manual
   `ValueError → ModelOnexError` conversion step.

### Standard Validator Pattern

```python
from omnibase_core.models.errors.model_onex_error import ModelOnexError
from omnibase_core.enums.enum_core_error_code import EnumCoreErrorCode

class ModelExample(BaseModel):
    value: float

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: float) -> float:
        if v < 0.0:
            raise ModelOnexError(
                error_code=EnumCoreErrorCode.VALIDATION_ERROR,
                message=f"value must be >= 0.0, got {v}",
                context={"value": v, "field": "value", "constraint": "non_negative"},
            )
        return v
```

**Error-context conventions**: always include `field`, `value` (stringified if not
serializable), and `constraint`; optionally `expected`, `validator`, `related_fields`.

## Pydantic Compatibility Analysis

Pydantic's own documentation recommends validators raise `ValueError` or `AssertionError`
(caught and wrapped into `ValidationError`). Pydantic v2 does **not** wrap other exception
types — a validator that raises `ModelOnexError` propagates it directly to the caller with
all structured context intact (`error_code`, `message`, `context` all preserved, no
`ValidationError` wrapping). This is Pydantic v2's documented behavior for custom exception
types, not a workaround.

**Known risk**: a future Pydantic major version could change this. Documented fallback
strategies, in order of preference:

1. **Adapter pattern** (recommended): a `to_pydantic_error()` conversion function that wraps
   `ModelOnexError` into `PydanticCustomError` only at the raise site, preserving the
   `ModelOnexError` construction pattern everywhere else.
2. **Validation abstraction**: extract validator bodies into standalone functions, callable
   independent of the Pydantic decorator.
3. **Direct migration** (last resort): replace `ModelOnexError` with `PydanticCustomError`
   throughout — loses the `EnumCoreErrorCode` machine-readable codes and framework
   consistency; only if options 1–2 are incompatible with a future Pydantic version.

## Consequences

**Positive**: framework-wide consistency, structured/machine-readable errors, correlation-
tracking readiness, a single pattern for new contributors to learn.

**Negative**: divergence from Pydantic's own documented best practice; a future Pydantic
breaking change could require updating every validator that follows this pattern; the
divergence itself needs to be documented and justified to new contributors (this decision
record is that documentation).

---

## References

- [ADR-0032](ADR-0032-reducer-output-exception-consistency.md): Reducer Output Exception Consistency (the concrete precedent this decision generalizes)
- `src/omnibase_core/models/errors/model_onex_error.py` — `ModelOnexError` (verified live)
- `src/omnibase_core/enums/enum_core_error_code.py` — `EnumCoreErrorCode` (verified live)
- [Pydantic Validators](https://docs.pydantic.dev/latest/concepts/validators/)
- [Pydantic Error Handling](https://docs.pydantic.dev/latest/errors/errors/)

---

## Changelog

| Date | Changes |
|------|---------|
| 2026-08-25 | Migrated to knowledge base. Verified `model_onex_error.py` and `enum_core_error_code.py` exist live at the stated paths. Condensed the original's extended worked examples and Pydantic-v3-contingency test listings while preserving the decision, rationale, and fallback strategies in full. |
| 2026-01-18 | Initial decision |
