---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Custom `__bool__` for Result Models"
topics: [omnibase-infra, adr, custom, bool]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-custom-bool-result-models.md on 2026-09-02. -->

# ADR: Custom `__bool__` for Result Models

**Status**: Accepted
**Date**: 2026-01-09

## Context

Standard Pydantic models always return `True` when evaluated in a boolean context (`bool(model)`), regardless of the model's field values. This is because Pydantic inherits from `BaseModel`, and `BaseModel` instances are always considered truthy.

However, result-oriented models often need **semantic truthiness** - where `if result:` should check whether the operation was successful or produced meaningful output, not just whether the model instance exists.

### The Problem

Without custom `__bool__`, developers must write verbose conditional checks:

```python
# Verbose and error-prone
result = validator.validate(input_data)
if result.is_valid:  # Must remember exact field name
    process_valid(result)

# Easy to make mistakes
if result:  # Always True! Bug waiting to happen
    process_valid(result)  # Processes even invalid results
```

### The Solution

Allow result models to override `__bool__` to enable idiomatic Python conditionals:

```python
# Idiomatic and clear
result = validator.validate(input_data)
if result:  # Checks semantic validity
    process_valid(result)
```

## Decision

**Allow `__bool__` override in result models with strict documentation requirements.**

Result models MAY override `__bool__` when:
1. The model represents an operation result with clear success/failure semantics
2. The model represents an optional value wrapper with presence/absence semantics
3. The model contains a collection where emptiness is meaningful

**Documentation Requirement**: Every model that overrides `__bool__` MUST include a `Warning` section in the docstring explaining the non-standard behavior.

### Standard Docstring Pattern

```python
def __bool__(self) -> bool:
    """Allow using result in boolean context.

    Warning:
        **Non-standard __bool__ behavior**: This model overrides ``__bool__`` to
        return ``True`` only when <condition>. This differs from typical
        Pydantic model behavior where ``bool(model)`` always returns ``True``.

    Returns:
        True if <semantic meaning>, False otherwise.
    """
    return self.<field>
```

## Affected Models

### Category 1: Validity/Success Results

These models return `True` when the operation was successful.

| Model | Location | Condition | Use Case |
|-------|----------|-----------|----------|
| `ModelSecurityValidationResult` | `models/security/` | `valid=True` | Security validation passed |
| `ModelValidationOutcome` | `models/validation/` | `is_valid=True` | General validation passed |
| `ModelExecutionShapeValidationResult` | `models/validation/` | `passed=True` | Execution shape validation |
| `ModelCategoryMatchResult` | `models/validation/` | `matched=True` | Category matching succeeded |
| `ModelRegistrationResult` | `handlers/service_discovery/models/` | `success=True` | Service registration succeeded |
| `ModelLifecycleResult` | `runtime/models/` | `success=True` | Lifecycle operation succeeded |
| `ModelValidationResult` | `nodes/architecture_validator/models/` | `passed=True` | Architecture validation passed |
| `ModelArchitectureValidationResult` | `nodes/architecture_validator/models/` | `passed=True` | Architecture validation passed |

**Usage Pattern**:
```python
result = security_validator.validate(handler)
if result:  # True only when valid=True
    handler.execute()
else:
    log_security_errors(result.errors)
```

### Category 2: Optional Value Wrappers

These models return `True` when a value is present.

| Model | Location | Condition | Use Case |
|-------|----------|-----------|----------|
| `ModelOptionalString` | `runtime/models/` | `value is not None` | Optional string with metadata |
| `ModelOptionalUUID` | `runtime/models/` | `value is not None` | Optional UUID with metadata |
| `ModelOptionalCorrelationId` | `runtime/models/` | `value is not None` | Optional correlation ID |
| `ModelPolicyTypeFilter` | `runtime/models/` | `filter_value is set` | Optional type filter |

**Usage Pattern**:
```python
correlation_id = ModelOptionalCorrelationId.from_context(ctx)
if correlation_id:  # True only when value present
    headers["X-Correlation-ID"] = str(correlation_id.value)
```

### Category 3: Collection-Based Results

These models return `True` when an internal collection is non-empty.

| Model | Location | Condition | Use Case |
|-------|----------|-----------|----------|
| `ModelReducerExecutionResult` | `nodes/node_registration_orchestrator/models/` | `has_intents=True` (intents tuple non-empty) | Reducer produced intents to execute |
| `ModelDispatchOutputs` | `models/dispatch/` | `topics` list non-empty | Dispatch has output topics |

**Usage Pattern**:
```python
result = reducer.reduce(state, event)
if result:  # True only if there are intents to process
    for intent in result.intents:
        execute_intent(intent)
```

## Consequences

### Positive

1. **Idiomatic Python** - Enables natural `if result:` conditional checks
2. **Reduced Bugs** - Developers cannot accidentally treat failed results as successful
3. **Cleaner Code** - Eliminates verbose `if result.is_valid:` patterns
4. **Self-Documenting** - The boolean check conveys semantic meaning

### Negative

1. **Non-Standard Behavior** - Differs from typical Pydantic model behavior
2. **Documentation Overhead** - Every override requires explicit documentation
3. **Learning Curve** - Developers must understand which models have custom `__bool__`
4. **Potential Confusion** - May surprise developers expecting standard Pydantic behavior

### Mitigation Strategies

1. **Mandatory Warning in Docstring** - Ensures the non-standard behavior is documented
2. **Consistent Pattern** - All overrides follow the same documentation template
3. **CLAUDE.md Reference** - Listed in coding guidelines for awareness
4. **ADR Reference in CLAUDE.md** - Points developers to this decision document

## Verification

### Finding Models with Custom `__bool__`

```bash
# Find all models with custom __bool__
grep -rn "def __bool__" src/omnibase_infra/ | grep -v __pycache__

# Verify all have Warning section
grep -A 10 "def __bool__" src/omnibase_infra/**/*.py | grep -B5 "Warning:"
```

### Code Review Checklist

When reviewing models with `__bool__`:

- [ ] Does the model represent a result, optional value, or collection?
- [ ] Is there a clear semantic meaning for truthiness?
- [ ] Does the docstring include the mandatory `Warning` section?
- [ ] Does the Warning explain the non-standard behavior?
- [ ] Is the return condition clearly documented?

## Implementation Guidelines

### When to Implement Custom `__bool__`

**DO implement** when:
- Model represents operation success/failure (validation, registration, lifecycle)
- Model wraps an optional value with presence/absence semantics
- Model contains a collection where emptiness is semantically meaningful
- `if result:` would be more readable than `if result.some_field:`

**DO NOT implement** when:
- Model is a data transfer object (DTO) without operation semantics
- There's no clear "successful" vs "unsuccessful" interpretation
- The boolean meaning would be ambiguous
- Multiple fields could reasonably determine truthiness

### Template for New Models

```python
from pydantic import BaseModel, Field


class ModelMyResult(BaseModel):
    """Result of my operation.

    This model supports boolean evaluation for semantic truthiness.
    """

    success: bool = Field(description="Whether the operation succeeded")
    message: str = Field(description="Result message")

    def __bool__(self) -> bool:
        """Allow using result in boolean context.

        Warning:
            **Non-standard __bool__ behavior**: This model overrides ``__bool__`` to
            return ``True`` only when ``success`` is True. This differs from typical
            Pydantic model behavior where ``bool(model)`` always returns ``True``.

        Returns:
            True if the operation succeeded, False otherwise.
        """
        return self.success
```

## References

- CLAUDE.md "Custom `__bool__` for Result Models" section
- `src/omnibase_infra/models/security/model_security_validation_result.py`
- `src/omnibase_infra/models/validation/model_category_match_result.py`
- `src/omnibase_infra/nodes/node_registration_orchestrator/models/model_reducer_execution_result.py`
- `src/omnibase_infra/runtime/models/model_lifecycle_result.py`
