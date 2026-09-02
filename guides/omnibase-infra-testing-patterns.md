---
type: guide
status: current
date: "2026-09-02"
title: "Testing Patterns"
topics: [omnibase-infra, testing, patterns]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/testing_patterns.md on 2026-09-02. -->

# Testing Patterns

## Overview

This document provides testing patterns and best practices for ONEX infrastructure development. All tests should follow these patterns to ensure consistency, maintainability, and developer experience.

## Assertion Error Message Patterns

### The "HOW TO FIX" Pattern

The "HOW TO FIX" pattern provides actionable guidance directly in assertion error messages, helping developers quickly understand and resolve test failures without extensive debugging.

#### Purpose

When a test fails, developers often need to:
1. Understand why the test failed
2. Know what the expected behavior is
3. Learn how to fix the underlying issue

The "HOW TO FIX" pattern addresses all three needs in a single error message, reducing the time from failure to fix.

#### Pattern Structure

```python
assert condition, (
    f"Description of what failed.\n"
    f"Expected: {expected_value}\n"
    f"Got: {actual_value}\n"
    f"\n"
    f"HOW TO FIX:\n"
    f"  Step-by-step instructions to resolve the issue.\n"
    f"  Include code examples when helpful.\n"
    f"  Reference documentation or files for more context."
)
```

#### Key Components

| Component | Purpose | Required |
|-----------|---------|----------|
| **Failure description** | Explain what condition failed | Yes |
| **Expected vs Got** | Show the mismatch between expected and actual values | Recommended |
| **HOW TO FIX header** | Clear visual separator for fix instructions | Yes |
| **Fix instructions** | Step-by-step guidance to resolve the issue | Yes |
| **Code examples** | Concrete example of correct implementation | Recommended |
| **References** | Links to documentation, files, or related code | Optional |

### Real-World Examples

#### Example 1: Architectural Constraint Violation

From `tests/unit/nodes/test_orchestrator_no_io.py`:

```python
assert not io_imports_found, (
    f"Orchestrator should not import I/O libraries.\n"
    f"Found I/O imports: {sorted(io_imports_found)}\n\n"
    f"HOW TO FIX: Delegate I/O operations to effect nodes via ProtocolEffect.\n"
    f"Example: Use 'node_registry_effect' for Consul/PostgreSQL operations.\n"
    f"Pattern: orchestrator -> ProtocolEffect.execute_intent(intent) -> effect node\n"
    f"See: nodes/node_registration_orchestrator/protocols.py for ProtocolEffect definition."
)
```

**Why this is effective:**
- States the architectural rule being violated
- Shows exactly which imports violated the rule
- Provides the correct pattern to follow
- Gives a concrete example
- References the file where the correct pattern is defined

#### Example 2: Missing Protocol Method

```python
assert hasattr(ProtocolEffect, "execute_intent"), (
    "ProtocolEffect must have execute_intent() method for I/O delegation.\n\n"
    "HOW TO FIX: Add execute_intent() to ProtocolEffect in protocols.py:\n"
    "  async def execute_intent(\n"
    "      self, intent: ModelIntent, correlation_id: UUID\n"
    "  ) -> ModelEffectResult: ..."
)
```

**Why this is effective:**
- Explains why the method is required
- Shows the exact method signature to add
- Indicates the file to modify

#### Example 3: Method Signature Validation

```python
assert "intent" in params, (
    "execute_intent must accept 'intent' parameter for I/O operation details.\n\n"
    "HOW TO FIX: Update signature to include intent parameter:\n"
    "  async def execute_intent(self, intent: ModelIntent, ...) -> ModelEffectResult"
)
```

**Why this is effective:**
- Explains the purpose of the missing parameter
- Shows the correct signature format

#### Example 4: Direct I/O Calls Detection

```python
assert not io_calls_found, (
    f"Orchestrator should not make direct I/O calls.\n"
    f"Found potential I/O calls: {io_calls_found}\n\n"
    f"HOW TO FIX: Replace direct I/O calls with intent-based delegation.\n"
    f"Instead of: client.get('/service/node'), cursor.execute(query)\n"
    f"Use: await effect_node.execute_intent(ModelConsulReadIntent(...))\n"
    f"The effect node handles the actual I/O and returns results."
)
```

**Why this is effective:**
- Shows the specific calls that violated the rule
- Provides before/after examples
- Explains the reasoning behind the pattern

#### Example 5: Docstring Requirements

```python
assert (
    "MUST NOT perform I/O" in docstring
    or "Reducer MUST NOT perform I/O" in docstring
), (
    "ProtocolReducer docstring must explicitly state reducers perform no I/O.\n\n"
    "HOW TO FIX: Add to ProtocolReducer docstring:\n"
    '  """Protocol for reducer operations.\n\n'
    "  Reducer MUST NOT perform I/O. All I/O operations must be\n"
    '  expressed as intents returned to the orchestrator."""'
)
```

**Why this is effective:**
- Specifies exactly what text is expected
- Provides the complete docstring template to add

### When to Use This Pattern

**Always use the "HOW TO FIX" pattern for:**

| Scenario | Reason |
|----------|--------|
| Architectural constraint tests | Developers may not know the correct alternative pattern |
| API contract validation | Method signatures and interface requirements need specific guidance |
| Configuration validation | Configuration errors often have non-obvious fixes |
| Integration tests | External system requirements need clear setup instructions |
| Migration tests | Deprecated patterns need guidance on new alternatives |

**May use simpler assertions for:**

| Scenario | When Simpler is OK |
|----------|-------------------|
| Simple equality checks | When the fix is obvious from the values |
| Boolean property checks | When the property name is self-documenting |
| Collection emptiness | When an empty result is clearly wrong |

### Good vs Bad Examples

#### Bad: Assertion Without Context

```python
# BAD - No guidance on how to fix
assert len(methods) <= 2
```

#### Good: Assertion With Full Context

```python
# GOOD - Full context and fix instructions
assert len(methods) <= 2, (
    f"__init__ should be minimal (1-2 statements).\n"
    f"Found {len(methods)} statements in __init__ body.\n"
    f"Orchestrator should only call super().__init__(container) and rely on "
    f"base class + contract.yaml for all behavior."
)
```

#### Bad: Vague Error Message

```python
# BAD - Developer doesn't know what to do
assert node_type == "effect", "Wrong node type"
```

#### Good: Specific Error With Fix

```python
# GOOD - Explains why and how to fix
assert node_type == "effect", (
    f"Node '{node_id}' performs I/O but marked as '{node_type}' instead of 'effect'.\n"
    f"Description: {description}\n\n"
    f"HOW TO FIX: Update contract.yaml to set node_type: EFFECT_GENERIC for this node.\n"
    f"All nodes that perform external I/O operations must be effect nodes."
)
```

#### Bad: Missing What Was Actually Found

```python
# BAD - What imports were found?
assert not io_imports_found, "Found I/O imports"
```

#### Good: Shows Expected vs Actual

```python
# GOOD - Shows exactly what was found
assert not io_imports_found, (
    f"Orchestrator should not import I/O libraries.\n"
    f"Found I/O imports: {sorted(io_imports_found)}\n\n"
    f"HOW TO FIX: Delegate I/O operations to effect nodes via ProtocolEffect."
)
```

### Writing Effective "HOW TO FIX" Messages

#### 1. Start with the Rule

Begin by stating the rule or constraint that was violated:

```python
f"Orchestrator should not import I/O libraries.\n"
```

#### 2. Show What Was Found

Include the actual values that caused the failure:

```python
f"Found I/O imports: {sorted(io_imports_found)}\n\n"
```

#### 3. Provide the Fix Pattern

Show the correct pattern to follow:

```python
f"HOW TO FIX: Delegate I/O operations to effect nodes via ProtocolEffect.\n"
```

#### 4. Include a Code Example

Provide concrete code when helpful:

```python
f"Example: Use 'node_registry_effect' for Consul/PostgreSQL operations.\n"
f"Pattern: orchestrator -> ProtocolEffect.execute_intent(intent) -> effect node\n"
```

#### 5. Reference Documentation

Point to files or docs for more context:

```python
f"See: nodes/node_registration_orchestrator/protocols.py for ProtocolEffect definition."
```

### Template for New Tests

Use this template when writing new assertions:

```python
assert condition, (
    f"[Description of the rule/constraint being tested].\n"
    f"[What was expected].\n"
    f"[What was actually found]: {actual_value}\n"
    f"\n"
    f"HOW TO FIX:\n"
    f"  [Step 1: First action to take]\n"
    f"  [Step 2: Second action if needed]\n"
    f"  \n"
    f"  Example:\n"
    f"    [Concrete code example]\n"
    f"  \n"
    f"  See: [path/to/relevant/file.py] for reference."
)
```

### Integration with pytest

The "HOW TO FIX" pattern works seamlessly with pytest's assertion introspection:

```python
class TestArchitecturalConstraints:
    """Tests verifying architectural constraints with helpful error messages."""

    def test_no_io_imports(self, node_ast: ast.Module) -> None:
        """Verify orchestrator has no I/O library imports."""
        io_imports_found = find_io_imports(node_ast)

        assert not io_imports_found, (
            f"Orchestrator should not import I/O libraries.\n"
            f"Found I/O imports: {sorted(io_imports_found)}\n\n"
            f"HOW TO FIX: Delegate I/O operations to effect nodes via ProtocolEffect.\n"
            f"See: docs/patterns/testing_patterns.md for the delegation pattern."
        )
```

When this test fails, pytest displays the full multi-line message, making it easy to understand and fix.

## Best Practices Summary

### DO

- Include the specific values that caused the failure
- Provide step-by-step instructions in the "HOW TO FIX" section
- Reference relevant files and documentation
- Use code examples when the fix involves code changes
- Format messages for readability with newlines and indentation
- Use f-strings for dynamic content

### DON'T

- Write assertions without error messages
- Use vague error messages like "Wrong value" or "Test failed"
- Skip the "HOW TO FIX" section for architectural tests
- Forget to include what was actually found vs expected
- Write single-line error messages for complex failures

## Related Patterns

- **Error Handling Patterns (internal knowledge base)** - Error classification and context
- **Correlation ID Tracking (`../architecture/omnibase-infra-correlation-id-tracking.md`)** - Request tracing in tests
- **Container Dependency Injection (`../architecture/omnibase-infra-container-dependency-injection.md`)** - Testing with DI containers

## See Also

- CLAUDE.md - Quick reference rules
- tests/unit/nodes/test_orchestrator_no_io.py (`../../tests/unit/nodes/test_orchestrator_no_io.py`) - Example implementation
