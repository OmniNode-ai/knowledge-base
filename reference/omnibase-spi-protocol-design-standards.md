---
type: reference
status: current
date: "2026-09-01"
title: "omnibase_spi Protocol Design Standards"
topics:
  - omnibase_spi
  - protocols
  - standards
refs: []
---

<!-- Migrated from omnibase_spi:docs/standards/README.md on 2026-09-01 -->

# Standards and Guidelines

## Protocol Design Standards

### Naming Conventions

- **Protocol Prefix**: All protocols must use `Protocol*` prefix
- **Descriptive Names**: Use clear, descriptive names that indicate purpose
- **Method Names**: Use verb-noun patterns for method names
- **Parameter Names**: Use descriptive parameter names with type hints

### Protocol Structure

```python
@runtime_checkable
class ProtocolExample(Protocol):
    """
    Brief description of the protocol's purpose.

    Detailed description covering:
    - Primary use cases and scenarios
    - Key features and capabilities
    - Integration patterns and usage
    - Implementation requirements
    """

    async def method_name(
        self,
        param: str,
        optional_param: Optional[int] = None
    ) -> str:
        """
        Method description with clear purpose.

        Args:
            param: Description of required parameter
            optional_param: Description of optional parameter

        Returns:
            Description of return value

        Raises:
            ValueError: When parameter validation fails
        """
        ...
```

### Type Annotations

- **Complete Coverage**: All parameters and return values must have type hints
- **No Any Types**: Avoid `Any` types in public interfaces
- **PEP 604 Unions**: Use `X | Y`, not `Union[X, Y]`
- **PEP 604 Optionals**: Use `X | None`, not `Optional[X]`
- **Generic Types**: Use generic types where appropriate

## Code Quality Standards

### Code Style

1. **Formatting**
   - Use `ruff format` for code formatting (this repo is ruff-only; there is
     no `black` dependency or configuration anywhere in the tree)
   - Follow PEP 8 style guidelines
   - Maintain consistent indentation

2. **Imports**
   - Use absolute imports
   - Group imports logically
   - Remove unused imports

3. **Comments**
   - Use clear, concise comments
   - Explain complex logic
   - Document non-obvious decisions

### Documentation Standards

1. **Docstrings**
   - Use Google-style docstrings
   - Include comprehensive descriptions
   - Document all parameters and return values
   - Include usage examples

2. **Type Hints**
   - Use proper type annotations
   - Include return type annotations
   - Use `Optional` for optional parameters
   - Use `Union` for multiple possible types

3. **Examples**
   - Provide clear usage examples
   - Show integration patterns
   - Demonstrate error handling

## Testing Standards

### Unit Testing

1. **Coverage Requirements**
   - Minimum 90% code coverage
   - Test all public methods
   - Cover edge cases and error conditions

2. **Test Structure**
   - Use descriptive test names
   - Group related tests in classes
   - Use fixtures for common setup

3. **Mock Implementation**
   - Create mock implementations for testing
   - Verify protocol compliance
   - Test error handling

### Integration Testing

1. **Protocol Interactions**
   - Test protocol combinations
   - Verify end-to-end workflows
   - Check performance characteristics

2. **Error Handling**
   - Test error conditions
   - Verify recovery mechanisms
   - Check error propagation

3. **Performance Testing**
   - Test under load conditions
   - Verify scalability
   - Check memory usage

## Validation Standards

### Protocol Compliance

1. **Runtime Checkable**
   - All protocols must use `@runtime_checkable` decorator
   - Support `isinstance(obj, Protocol)` validation
   - Enable duck typing patterns

2. **Type Safety**
   - Full mypy compatibility with strict checking
   - No `Any` types in public interfaces
   - Comprehensive type coverage

3. **Namespace Isolation**
   - Complete separation from implementation packages
   - No concrete implementations in protocol files
   - Zero runtime dependencies

### Quality Gates

1. **Automated Validation**
   - All tests must pass
   - Type safety validation must pass
   - Protocol compliance must be verified

2. **Manual Review**
   - Code review by maintainers
   - Protocol design review
   - Documentation review

3. **Performance Validation**
   - No performance regressions
   - Memory usage within limits
   - Response time requirements met

## Best Practices

### Protocol Design

1. **Single Responsibility**
   - Each protocol should have a clear, focused purpose
   - Avoid mixing unrelated concerns
   - Keep interfaces cohesive

2. **Composition over Inheritance**
   - Prefer composition for complex behaviors
   - Use protocol aggregation patterns
   - Avoid deep inheritance hierarchies

3. **Interface Segregation**
   - Keep interfaces focused and cohesive
   - Avoid large, monolithic protocols
   - Split complex protocols into smaller ones

### Implementation Guidelines

1. **Error Handling**
   - Define specific exception types
   - Provide clear error messages
   - Include context information

2. **Performance**
   - Use async/await patterns
   - Implement efficient data structures
   - Consider memory usage

3. **Security**
   - Validate all inputs
   - Use secure defaults
   - Implement proper access controls

## API Reference

- **`Core Protocols` (in the omnibase_spi repository)** - System fundamentals
- **`Container Protocols` (in the omnibase_spi repository)** - Dependency injection
- **`Workflow Orchestration` (in the omnibase_spi repository)** - Event-driven FSM
- **`MCP Integration` (in the omnibase_spi repository)** - Multi-subsystem coordination

---

*For detailed protocol documentation, see the `API Reference` (in the omnibase_spi repository).*
