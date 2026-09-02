---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Error Context Factory Pattern with `with_correlation`"
topics: [omnibase-infra, adr, error, context]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-error-context-factory-pattern.md on 2026-09-02. -->

# ADR: Error Context Factory Pattern with `with_correlation()`

**Status**: Accepted
**Date**: 2026-01-16
**Follow-up Tickets**:  (validator),  (migration)

## Context

### The Problem: Inconsistent Correlation ID Handling

Infrastructure errors require correlation IDs for distributed tracing. Without consistent handling, errors become untraceable across service boundaries. The codebase exhibited three problematic patterns:

1. **Manual `uuid4()` calls at every call site**:
   ```python
   # Repeated boilerplate across the codebase
   context = ModelInfraErrorContext(
       transport_type=EnumInfraTransportType.HTTP,
       operation="process_request",
       correlation_id=uuid4(),  # Manual generation everywhere
   )
   ```

2. **Conditional generation with `or` pattern**:
   ```python
   # Cognitive load: developers must remember this pattern
   context = ModelInfraErrorContext(
       correlation_id=existing_id or uuid4(),  # Easy to forget the `or uuid4()` part
       operation="query",
   )
   ```

3. **Missing correlation IDs entirely**:
   ```python
   # Untraceable errors in production
   context = ModelInfraErrorContext(
       transport_type=EnumInfraTransportType.DATABASE,
       operation="connect",
       # correlation_id omitted - error cannot be traced
   )
   ```

### Consequences of Inconsistent Handling

| Issue | Impact |
|-------|--------|
| Untraceable errors | Production debugging requires manual log correlation |
| Repeated boilerplate | Developers copy-paste `uuid4()` calls, prone to errors |
| Cognitive load | Must remember "always generate if not provided" rule |
| Inconsistent patterns | Code review burden to catch missing correlation IDs |

## Decision

**`ModelInfraErrorContext` MUST be constructed via `with_correlation()` factory method unless propagating an existing correlation_id.**

### The Factory Pattern

The `with_correlation()` class method auto-generates a UUID4 correlation_id if not provided:

```python
@classmethod
def with_correlation(
    cls,
    correlation_id: UUID | None = None,
    **kwargs: object,
) -> "ModelInfraErrorContext":
    """Create context with auto-generated correlation_id if not provided."""
    return cls(correlation_id=correlation_id or uuid4(), **kwargs)
```

**Location**: `src/omnibase_infra/models/errors/model_infra_error_context.py`

### Usage Rules

| Scenario | Pattern | Rationale |
|----------|---------|-----------|
| New error (no existing ID) | `ModelInfraErrorContext.with_correlation(...)` | Auto-generate ID |
| Propagating existing ID | `ModelInfraErrorContext.with_correlation(correlation_id=existing_id, ...)` | Preserve trace chain |
| Direct constructor | **AVOID** unless correlation_id is explicitly provided | Risk of untraceable errors |

## Trade-offs

### Intentional `**kwargs: object` Design

The factory uses `**kwargs: object` which is intentionally permissive:

```python
def with_correlation(
    cls,
    correlation_id: UUID | None = None,
    **kwargs: object,  # Permissive to avoid churn during migration
) -> "ModelInfraErrorContext":
```

**Why permissive**:
- Reduces churn during codebase migration to factory pattern
- Allows gradual adoption without breaking existing call sites
- Model's `extra="forbid"` config still rejects unknown fields at runtime

**Constraints**:
- Only pass keys that are actual `ModelInfraErrorContext` fields
- Unknown fields are rejected by Pydantic validation (`extra="forbid"`)
- Runtime errors catch misuse; static analysis cannot

**Valid fields**: `correlation_id`, `transport_type`, `operation`, `target_name`, `namespace`

### Two Patterns Coexist During Migration

Until full codebase migration, both patterns may exist:

```python
# NEW pattern (preferred)
context = ModelInfraErrorContext.with_correlation(
    transport_type=EnumInfraTransportType.HTTP,
    operation="request",
)

# OLD pattern (deprecated, but may exist in legacy code)
context = ModelInfraErrorContext(
    transport_type=EnumInfraTransportType.HTTP,
    operation="request",
    correlation_id=uuid4(),  # Manual - should use factory
)
```

## Lint/Validator Enforcement

### Proposed Validator: `scripts/validate.py correlation_patterns`

Following the existing `any_types` validator pattern, implement AST-based detection of anti-patterns.

**Integration Points**:
- **Pre-commit hook**: Add to `.pre-commit-config.yaml` alongside `any_types`
- **CI Pipeline**: Run as part of `ONEX Validators` job
- **Exit codes**: Non-zero on violations (blocks merge)

### Anti-Patterns to Flag

| Pattern | Detection | Severity |
|---------|-----------|----------|
| `correlation_id=uuid4()` in call sites | AST: `uuid4()` as kwarg value outside factory | ERROR |
| `correlation_id or uuid4()` | AST: `BoolOp` with `uuid4()` outside factory | ERROR |
| `ModelInfraErrorContext(...)` without `correlation_id` | AST: Constructor call missing `correlation_id` kwarg | WARNING |

**Exemption**: Patterns inside `with_correlation()` method itself are allowed (the factory implementation).

### Validator Implementation Sketch

```python
# scripts/validators/correlation_validator.py
import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Violation:
    """Represents a validation violation."""
    file: Path
    line: int
    message: str
    code: str


def is_uuid4_call(node: ast.expr) -> bool:
    """Check if node is a call to uuid4()."""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "uuid4":
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr == "uuid4":
            return True
    return False


def is_uuid4_or_pattern(node: ast.expr) -> bool:
    """Check if node is `x or uuid4()` pattern."""
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        return any(is_uuid4_call(value) for value in node.values)
    return False


def is_model_infra_error_context_call(node: ast.Call) -> bool:
    """Check if call is to ModelInfraErrorContext constructor."""
    if isinstance(node.func, ast.Name):
        return node.func.id == "ModelInfraErrorContext"
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == "ModelInfraErrorContext"
    return False


def has_correlation_id_kwarg(node: ast.Call) -> bool:
    """Check if call has correlation_id keyword argument."""
    return any(kw.arg == "correlation_id" for kw in node.keywords)


@dataclass
class CorrelationPatternVisitor(ast.NodeVisitor):
    """Visitor that tracks scope for correlation pattern detection.

    Uses proper scope tracking to skip violations ONLY within the
    `with_correlation()` factory method, not all subsequent nodes.

    Note: ast.walk() cannot track scope because it visits nodes in arbitrary
    order without parent/child context. NodeVisitor.generic_visit() traverses
    the tree depth-first, allowing us to track entry/exit of function scopes.
    """

    file_path: Path
    violations: list[Violation] = field(default_factory=list)
    _in_factory_method: bool = field(default=False, repr=False)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track entry/exit of with_correlation method scope."""
        # Save current state before entering function
        was_in_factory = self._in_factory_method

        # Mark if we're entering the factory method
        if node.name == "with_correlation":
            self._in_factory_method = True

        # Visit all children (function body)
        self.generic_visit(node)

        # Restore state after leaving function scope
        self._in_factory_method = was_in_factory

    # Handle async functions the same way
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        """Check call nodes for anti-patterns, unless in factory method."""
        if not self._in_factory_method:
            self._check_call_for_violations(node)

        # Continue visiting children (e.g., nested calls in arguments)
        self.generic_visit(node)

    def _check_call_for_violations(self, node: ast.Call) -> None:
        """Check a Call node for correlation ID anti-patterns."""
        # Check for uuid4() as correlation_id kwarg value
        for keyword in node.keywords:
            if keyword.arg == "correlation_id":
                # Pattern 1: correlation_id=uuid4()
                if is_uuid4_call(keyword.value):
                    self.violations.append(
                        Violation(
                            file=self.file_path,
                            line=node.lineno,
                            message="Use ModelInfraErrorContext.with_correlation() instead of manual uuid4()",
                            code="CORR_001",
                        )
                    )
                # Pattern 2: correlation_id=x or uuid4()
                elif is_uuid4_or_pattern(keyword.value):
                    self.violations.append(
                        Violation(
                            file=self.file_path,
                            line=node.lineno,
                            message="Use ModelInfraErrorContext.with_correlation() instead of 'x or uuid4()' pattern",
                            code="CORR_002",
                        )
                    )

        # Pattern 3: ModelInfraErrorContext() without correlation_id
        if is_model_infra_error_context_call(node):
            if not has_correlation_id_kwarg(node):
                self.violations.append(
                    Violation(
                        file=self.file_path,
                        line=node.lineno,
                        message="ModelInfraErrorContext() missing correlation_id; use with_correlation() factory",
                        code="CORR_003",
                    )
                )


def validate_correlation_patterns(file_path: Path) -> list[Violation]:
    """Detect anti-patterns in correlation ID handling.

    Uses CorrelationPatternVisitor with proper scope tracking to:
    1. Skip violations ONLY within the with_correlation() method body
    2. Correctly detect violations in all other parts of the file
    3. Handle nested function definitions properly
    """
    source = file_path.read_text()
    tree = ast.parse(source)

    visitor = CorrelationPatternVisitor(file_path=file_path)
    visitor.visit(tree)

    return visitor.violations
```

### Validator Limitations

The AST-based validator has inherent limitations:

**What IS Detected** (will trigger violations):
- Direct `uuid4()` as `correlation_id` kwarg value
- `x or uuid4()` pattern as `correlation_id` kwarg value
- `ModelInfraErrorContext()` constructor calls without `correlation_id` kwarg

**What is NOT Detected** (validator limitations):
1. **Indirect uuid4 calls**: When `uuid4()` result is assigned to variable first:
   ```python
   new_id = uuid4()  # Assigned to variable
   context = ModelInfraErrorContext(correlation_id=new_id)  # NOT detected
   ```

2. **Factory functions returning uuid4**: When helper functions wrap uuid4:
   ```python
   def get_id() -> UUID:
       return uuid4()
   context = ModelInfraErrorContext(correlation_id=get_id())  # NOT detected
   ```

3. **Dynamic attribute access**: When class/method names are computed at runtime:
   ```python
   cls = get_context_class()  # Returns ModelInfraErrorContext
   context = cls(...)  # NOT detected - name resolved at runtime
   ```

4. **String-based imports**: `importlib.import_module` patterns are not traced.

**Design Rationale**: The validator prioritizes low false-positive rates over complete detection. The common anti-patterns (direct `uuid4()` in kwarg) are detected, while edge cases require code review.

### Exemption Mechanism

For legitimate cases requiring direct constructor:

```python
# ONEX_EXCLUDE: correlation_pattern - Reason: <documented reason>
context = ModelInfraErrorContext(
    correlation_id=some_special_id,
    ...
)
```

## Usage Patterns

### Pattern 1: Auto-generate (New Error, No Existing ID)

When creating an error context with no existing correlation ID:

```python
from omnibase_infra.models.errors import ModelInfraErrorContext
from omnibase_infra.errors import InfraConnectionError
from omnibase_infra.enums import EnumInfraTransportType

def connect_to_database(host: str, connection_pool: object) -> None:
    """Attempt database connection with proper error context."""
    try:
        # Attempt connection using injected pool
        connection_pool.get_connection(host)
    except ConnectionRefusedError as e:
        # Factory auto-generates correlation_id
        context = ModelInfraErrorContext.with_correlation(
            transport_type=EnumInfraTransportType.DATABASE,
            operation="execute_query",
            target_name="omnibase_infra",
        )
        raise InfraConnectionError("Connection refused", context=context) from e
```

### Pattern 2: Propagate (Preserve Existing ID Through Call Chain)

When an error occurs in a context that already has a correlation ID:

```python
async def handle_request(request: ModelRequest) -> ModelResponse:
    try:
        return await process(request)
    except Exception as e:
        # Propagate the existing correlation_id from the request
        context = ModelInfraErrorContext.with_correlation(
            correlation_id=request.correlation_id,  # Preserve trace chain
            transport_type=EnumInfraTransportType.HTTP,
            operation="handle_request",
            target_name=request.endpoint,
        )
        raise InfraUnavailableError("Service unavailable", context=context) from e
```

### Pattern 3: Helper Function Pattern (Centralized Context Creation)

For modules with repeated error context creation (e.g., `runtime/wiring.py`):

```python
# In a module-level helper or class method
def _make_error_context(
    operation: str,
    correlation_id: UUID | None = None,
    target_name: str | None = None,
) -> ModelInfraErrorContext:
    """Create infrastructure error context with defaults for this module."""
    return ModelInfraErrorContext.with_correlation(
        correlation_id=correlation_id,
        transport_type=EnumInfraTransportType.KAFKA,  # Module default
        operation=operation,
        target_name=target_name,
    )

# Usage within the module
context = _make_error_context("publish_event", correlation_id=envelope.correlation_id)
```

### Anti-Pattern: Direct Constructor Without Correlation ID

```python
# WRONG: Missing correlation_id - error is untraceable
context = ModelInfraErrorContext(
    transport_type=EnumInfraTransportType.HTTP,
    operation="request",
)

# WRONG: Manual uuid4() - should use factory
context = ModelInfraErrorContext(
    transport_type=EnumInfraTransportType.HTTP,
    operation="request",
    correlation_id=uuid4(),  # Use with_correlation() instead
)
```

## Consequences

### Positive

| Benefit | Description |
|---------|-------------|
| **100% error traceability** | Every error has a correlation_id, either generated or propagated |
| **Consistent codebase** | Single pattern for error context creation |
| **Reduced cognitive load** | Developers don't need to remember `or uuid4()` pattern |
| **Easier code review** | One pattern to check, not three variations |
| **Future-proof** | Factory can be extended with additional defaults without breaking call sites |

### Negative

| Drawback | Mitigation |
|----------|------------|
| Two patterns coexist during migration | Lint validator will gradually enforce factory usage |
| `**kwargs` permits loose typing | Runtime validation via `extra="forbid"` catches misuse |
| Slight indirection | Factory is simple and well-documented |
| Learning curve for new developers | CLAUDE.md and this ADR provide clear guidance |

## Future Work

### Tighten `**kwargs` Typing

Once migration is complete, consider replacing `**kwargs: object` with explicit parameters or `Unpack[TypedDict]`:

```python
# Option 1: Explicit parameters (most type-safe)
@classmethod
def with_correlation(
    cls,
    correlation_id: UUID | None = None,
    transport_type: EnumInfraTransportType | None = None,
    operation: str | None = None,
    target_name: str | None = None,
    namespace: str | None = None,
) -> "ModelInfraErrorContext": ...

# Option 2: TypedDict with Unpack (Python 3.12+)
class ErrorContextKwargs(TypedDict, total=False):
    transport_type: EnumInfraTransportType | None
    operation: str | None
    target_name: str | None
    namespace: str | None

@classmethod
def with_correlation(
    cls,
    correlation_id: UUID | None = None,
    **kwargs: Unpack[ErrorContextKwargs],
) -> "ModelInfraErrorContext": ...
```

### Propagate Correlation ID Through Envelopes

Architecture decision deferred: Should `ModelEventEnvelope` always carry a `correlation_id` that gets auto-propagated to error contexts?

```python
# Potential future pattern
async def handle_envelope(envelope: ModelEventEnvelope[T]) -> None:
    try:
        await process(envelope)
    except Exception as e:
        # Automatic propagation from envelope
        context = ModelInfraErrorContext.from_envelope(envelope, operation="handle")
        raise InfraError("Failed", context=context) from e
```

This requires broader architectural consensus and is tracked separately.

## Verification

### Finding Direct Constructor Usage

These are quick manual checks for ad-hoc verification. The `correlation_patterns` validator provides robust AST-based detection with proper exemption handling.

```bash
# Quick check: Find potential violations (direct constructor without with_correlation)
# Excludes: factory method definition, test files, __pycache__
grep -rn "ModelInfraErrorContext(" src/ --include="*.py" \
    | grep -v "with_correlation" \
    | grep -v "__pycache__" \
    | grep -v "def with_correlation" \
    | grep -v "# Example" \
    | grep -v '"""'

# Quick check: Find manual uuid4() in correlation_id
# Excludes: factory method implementation, comments
grep -rn "correlation_id=uuid4()" src/ --include="*.py" \
    | grep -v "__pycache__" \
    | grep -v "model_infra_error_context.py" \
    | grep -v "# "

# Quick check: Find or-pattern
grep -rn "correlation_id.*or.*uuid4()" src/ --include="*.py" \
    | grep -v "__pycache__" \
    | grep -v "model_infra_error_context.py"
```

**Note**: These grep commands are for quick manual verification only. They may produce false positives (e.g., comments, string literals, docstrings) and miss complex patterns (e.g., multiline expressions, indirect variable assignment). Use the AST-based validator for authoritative enforcement once  is implemented.

### Code Review Checklist

When reviewing code with `ModelInfraErrorContext`:

- [ ] Is `with_correlation()` factory used (not direct constructor)?
- [ ] If propagating existing ID, is it passed explicitly?
- [ ] If no existing ID, is `correlation_id` parameter omitted (auto-generate)?
- [ ] For helper functions, do they use `with_correlation()` internally?

## References

- CLAUDE.md "Error Context" section
- `src/omnibase_infra/models/errors/model_infra_error_context.py`
- `scripts/validate.py` - Existing validator framework

### Planned Follow-up Work

- **Validator Implementation**: Implement `scripts/validate.py correlation_patterns` validator with pre-commit and CI integration (see "Lint/Validator Enforcement" section above)
- **Migration**: Migrate existing codebase to use `with_correlation()` factory pattern consistently
