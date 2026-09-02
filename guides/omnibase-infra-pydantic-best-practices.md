---
type: guide
status: current
date: "2026-09-02"
title: "Pydantic Best Practices"
topics: [omnibase-infra, pydantic, best, practices]
refs: []
---

<!-- Migrated from omnibase_infra:docs/conventions/PYDANTIC_BEST_PRACTICES.md on 2026-09-02. -->

# Pydantic Best Practices

> **Status**: Current | **Last Updated**: 2026-02-19

Pydantic usage standards for `omnibase_infra` models. These rules apply to every Pydantic model in the package — inputs, outputs, payloads, configs, error contexts, and projections.

---

## Table of Contents

1. [ConfigDict Requirements](#configdict-requirements)
2. [Field Patterns](#field-patterns)
3. [PEP 604 Type Unions](#pep-604-type-unions)
4. [Immutable Models (frozen=True)](#immutable-models-frozentrue)
5. [Mutable Defaults and Collections](#mutable-defaults-and-collections)
6. [Custom __bool__ Documentation Requirement](#custom-__bool__-documentation-requirement)
7. [Validators](#validators)
8. [Common Mistakes](#common-mistakes)

---

## ConfigDict Requirements

### Standard Pattern

The standard `ConfigDict` for infrastructure models is:

```python
from pydantic import BaseModel, ConfigDict

class ModelInfraErrorContext(BaseModel):
    model_config = ConfigDict(
        frozen=True,           # Immutable after creation — required for error contexts
        extra="forbid",        # Reject unknown fields — catches schema drift early
        from_attributes=True,  # Required for pytest-xdist parallel workers
    )
```

All three flags together (`frozen=True`, `extra="forbid"`, `from_attributes=True`) are the **default choice** for infrastructure models. Deviate only when there is an explicit reason documented below.

### When to Deviate

| Scenario | Change | Reason |
|----------|--------|--------|
| External YAML/JSON contract parsing | `extra="ignore"` | Forward-compatibility with schema evolution |
| Extension point (plugin metadata) | `extra="allow"` | Vendor-specific fields are intentional |
| Accumulator / builder model | `frozen=False` | Model is mutated during construction |
| ORM row → model (mutable source) | Omit `from_attributes` or add synchronization | Race condition risk; see note below |

**`frozen=True` + `from_attributes=True` is a required pair.** When `frozen=True` is set, always include `from_attributes=True`. The reason: pytest-xdist runs tests in parallel workers that import model classes independently. Without `from_attributes=True`, Pydantic rejects valid model instances when class identity differs across workers. `frozen=True` alone is insufficient.

### Checklist by Model Category

| Model Category | `frozen` | `extra` | `from_attributes` |
|---------------|----------|---------|-------------------|
| Error context (`ModelInfraErrorContext`) | `True` | `"forbid"` | `True` |
| Input/output (node I/O) | `True` | `"forbid"` | `True` |
| Intent payload (`ModelPayload*`) | `True` | `"forbid"` | `True` |
| Projection (`ModelRegistrationProjection`) | `True` | `"forbid"` | `True` |
| Config/settings (mutable at startup) | `False` | `"forbid"` | `True` |
| External contract parsed from YAML | `False` | `"ignore"` | optional |

---

## Field Patterns

### Required Fields

Use `...` (Ellipsis) when the field must always be provided:

```python
correlation_id: UUID = Field(..., description="Request correlation ID for distributed tracing")
node_id: str = Field(..., description="Unique node identifier")
```

### Optional Fields

**Prefer an empty sentinel value over `None` for string fields** to avoid `None`-checks throughout the codebase:

```python
# Preferred: empty string as sentinel
error_message: str = Field(default="", description="Empty string if no error")

# Acceptable when None has semantic meaning (field not yet known vs. explicitly absent)
target_name: str | None = Field(default=None, description="Target resource name")
```

Use `None` when `None` genuinely means "not provided / unknown" rather than "empty."

### Mutable Collections

Always use `default_factory` for list, dict, set, and tuple fields. Never use bare mutable literals as defaults:

```python
# Correct
events: list[str] = Field(default_factory=list)
tags: tuple[str, ...] = Field(default_factory=tuple)
metadata: dict[str, str] = Field(default_factory=dict)

# Wrong — shared state bug across all instances
events: list[str] = []
```

### Immutable Collections in Frozen Models

For frozen models, prefer `tuple[T, ...]` over `list[T]` for sequences that should never be mutated after creation:

```python
class ModelHandlerOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    events: tuple[str, ...] = Field(default_factory=tuple)
    errors: tuple[ModelHandlerValidationError, ...] = Field(default_factory=tuple)
```

`tuple` is hashable (enabling use as a dict key or in sets), signals immutability at the type level, and is consistent with `frozen=True`.

### Field Naming Conventions

| Suffix | Meaning | Examples |
|--------|---------|---------|
| `_id` | Identifier (UUID or str) | `node_id`, `correlation_id` |
| `_at` | Timestamp | `created_at`, `registered_at` |
| `_count` | Counter | `retry_count`, `error_count` |
| `is_*` | Boolean flag | `is_active`, `is_healthy` |
| `has_*` | Boolean existence | `has_errors`, `has_children` |
| `_config` | Configuration sub-object | `retry_config`, `kafka_config` |
| `_type` | Enum discriminator | `intent_type`, `handler_type` |

### Literal Fields for Intent Routing

Intent payload models use a `Literal` field as a discriminator so the orchestrator can route without isinstance checks:

```python
from typing import Literal

class ModelPayloadConsulRegister(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    intent_type: Literal["consul.register"] = Field(default="consul.register")
    service_id: str = Field(..., description="Consul service ID")
    service_name: str = Field(..., description="Consul service name")
```

---

## PEP 604 Type Unions

Always use PEP 604 union syntax. Never use `Optional[X]` or `Union[X, Y]`.

```python
# Correct (PEP 604)
correlation_id: UUID | None = None
transport_type: EnumInfraTransportType | None = None
result: str | int | None = None

# Wrong
from typing import Optional, Union
correlation_id: Optional[UUID] = None          # banned
result: Union[str, int, None] = None           # banned
```

This applies to all type annotations: field declarations, function signatures, return types, and local variables.

---

## Immutable Models (frozen=True)

### When to Use

Use `frozen=True` for:

- All models crossing a node boundary (input/output envelopes, event payloads)
- Error context models (`ModelInfraErrorContext`)
- Intent payloads (`ModelPayload*`)
- Projection snapshots
- Any model that may be read by multiple async tasks concurrently

**Rule**: If a model crosses a layer boundary or is shared across async tasks, it must be frozen.

### Example: ModelInfraErrorContext

```python
class ModelInfraErrorContext(BaseModel):
    """Configuration model for infrastructure error context.

    Thread Safety:
        frozen=True ensures this model cannot be modified after creation,
        making it safe to share across async tasks and parallel workers.
        from_attributes=True is required for pytest-xdist compatibility.
    """
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    transport_type: EnumInfraTransportType | None = None
    operation: str | None = None
    target_name: str | None = None
    correlation_id: UUID | None = None

    @classmethod
    def with_correlation(
        cls,
        correlation_id: UUID | None = None,
        **kwargs: object,
    ) -> "ModelInfraErrorContext":
        """Create context with auto-generated correlation_id if not provided."""
        return cls(correlation_id=correlation_id or uuid4(), **kwargs)
```

### When NOT to Use frozen=True

- Builder or accumulator models that collect results before finalizing
- Configuration objects populated incrementally at startup
- Models with `add_*`, `mark_*`, or `set_*` methods

---

## Mutable Defaults and Collections

The frozen/mutable default rule:

```python
# frozen=True model — use tuple for sequences
class ModelNodeCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    supported_operations: tuple[str, ...] = Field(default_factory=tuple)
    tags: tuple[str, ...] = Field(default_factory=tuple)

# frozen=False model — list is acceptable, but still needs default_factory
class ModelBuildContext(BaseModel):
    model_config = ConfigDict(frozen=False, extra="forbid", from_attributes=True)

    collected_events: list[str] = Field(default_factory=list)
```

**Never** write `items: list[str] = []`. Pydantic copies the default for each instance but the bare literal in the annotation signals shared-state intent to readers.

---

## Custom __bool__ Documentation Requirement

Result models may override `__bool__` so callers can write `if result:` idiomatically. When doing so, the docstring **must** include a `Warning` section describing the non-standard behavior.

```python
class ModelValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    is_valid: bool = Field(..., description="Whether validation passed")
    error_message: str = Field(default="")

    def __bool__(self) -> bool:
        """Allow using result in boolean context.

        Warning:
            **Non-standard __bool__ behavior**: Returns ``True`` only when
            ``is_valid`` is ``True``. This differs from the default Pydantic
            behavior where any non-empty model instance is truthy. Always
            check ``is_valid`` explicitly if you need the full result object.
        """
        return self.is_valid
```

The `Warning` section is non-optional. Without it, readers cannot distinguish intentional behavior from an accidental override.

---

## Validators

### Field Validators

Use `@field_validator` with `@classmethod` for single-field validation:

```python
from pydantic import field_validator

class ModelEventBusConfig(BaseModel):
    topic: str

    @field_validator("topic")
    @classmethod
    def validate_topic_prefix(cls, v: str) -> str:
        """Ensure topic uses the expected prefix."""
        if not v.startswith("onex."):
            raise ValueError(f"Topic must start with 'onex.', got '{v}'")
        return v
```

### Model Validators

Use `@model_validator(mode="after")` for cross-field validation:

```python
from pydantic import model_validator

class ModelRetryConfig(BaseModel):
    max_retries: int
    retry_delay_seconds: float

    @model_validator(mode="after")
    def validate_retry_config(self) -> "ModelRetryConfig":
        """Ensure retry_delay_seconds is positive when retries are enabled."""
        if self.max_retries > 0 and self.retry_delay_seconds <= 0:
            raise ValueError("retry_delay_seconds must be > 0 when max_retries > 0")
        return self
```

---

## Common Mistakes

| Wrong | Correct | Rule |
|-------|---------|------|
| `Optional[UUID]` | `UUID | None` | PEP 604 unions only |
| `frozen=True` without `from_attributes=True` | Add `from_attributes=True` | Required pair for pytest-xdist |
| `items: list[str] = []` | `items: list[str] = Field(default_factory=list)` | No mutable literals as defaults |
| `items: list[str] = Field(...)` in frozen model | `items: tuple[str, ...] = Field(...)` | Use tuple in frozen models |
| `__bool__` without Warning docstring | Add Warning section | Documents non-standard behavior |
| `Field(default=None)` with no other args | `= None` directly | Avoid unnecessary Field() wrapper |
| `extra="allow"` for internal models | `extra="forbid"` | Unknown fields on internal models are bugs |

---

## Related Documentation

- `CLAUDE.md` — ConfigDict and field patterns (Pydantic Model Standards section)
- `docs/conventions/NAMING_CONVENTIONS.md` — File and class naming
- `docs/patterns/container_dependency_injection.md` — Container and service model patterns
- `omnibase_core/docs/conventions/PYDANTIC_BEST_PRACTICES.md` — Core-level Pydantic guide (ConfigDict decision matrix, from_attributes safety)
