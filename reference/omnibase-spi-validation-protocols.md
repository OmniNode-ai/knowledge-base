---
type: reference
status: current
date: "2026-09-01"
title: "omnibase_spi Validation Protocols"
topics:
  - omnibase_spi
  - validation
  - protocols
refs: []
---

<!-- Migrated from omnibase_spi:src/omnibase_spi/protocols/validation/README.md on 2026-09-01 -->

# Validation Protocols

Protocol interface definitions for ONEX validation nodes.

## What This Module Is

`omnibase_spi.protocols.validation` is a **pure protocol module**: every
public name is a `typing.Protocol` decorated with `@runtime_checkable`, with
`...` method bodies. It contains **no concrete implementations, no runtime
validation engine, and no concrete decorators** — consistent with the rest of
`omnibase_spi` and the repo's protocol-only rule (see the root
``CLAUDE.md`` (in the omnibase_spi repository) and
[`docs/architecture/DEPENDENCY-DIRECTION.md`](../architecture/omnibase-spi-dependency-direction.md)):
SPI defines the contracts, concrete implementations live in `omnibase_core`
(the ONEX validation nodes) or `omnibase_infra`.

> An earlier revision of this file described a concrete
> `validate_protocol_implementation()` function, a `ProtocolValidator` class
> with runtime introspection logic, `ArtifactContainerValidator`,
> `enable_protocol_validation()`, and decorator-based auto-validation. The
> similarly named `ProtocolValidationDecorator.validate_protocol_implementation()`
> and `.validation_decorator()` members are protocol method requirements only;
> `omnibase_spi` does not implement them. This rewrite describes
> the real, protocol-only surface; every import below resolves against the live
> package.

## What's In This Module

Four ONEX validation node protocol families, plus a generic
protocol-conformance validator:

| Protocol | Node archetype | Purpose |
|---|---|---|
| `ProtocolImportValidator` | `NodeImportValidatorCompute` | Import/dependency validation |
| `ProtocolQualityValidator` | `NodeQualityValidatorEffect` | Code quality and complexity |
| `ProtocolComplianceValidator` | `NodeComplianceValidatorReducer` | ONEX naming/architecture compliance |
| `ProtocolValidationOrchestrator` | `NodeValidationOrchestratorOrchestrator` | Coordinates the three above |
| `ProtocolValidator` | — | Generic "does X implement protocol Y" check |
| `ProtocolValidationProvider` | — | Session-based validation-rule management |
| `ProtocolConstraintValidator` | `NodeConstraintValidatorCompute` | Execution-constraint conflict detection |

Full signatures, data-protocol shapes (`ProtocolValidationResult`,
`ProtocolComplianceReport`, `ProtocolQualityReport`, etc.), and usage
examples are documented in
``docs/api-reference/VALIDATION.md`` (in the omnibase_spi repository).

## Quick Start

```python
from omnibase_spi.protocols.validation import ProtocolValidator

async def check(implementation: object, protocol: type) -> bool:
    validator: ProtocolValidator = get_validator()  # from your own implementation repo
    result = await validator.validate_implementation(implementation, protocol)
    if not result.is_valid:
        for error in result.errors:
            print(f"  - [{error.severity}] {error.error_type}: {error.message}")
    return result.is_valid
```

`get_validator()` above is a placeholder for whatever concrete
implementation your repository (typically `omnibase_core` or
`omnibase_infra`) provides — this module never instantiates anything itself.

## Import Path

Import from the domain package, not individual submodules:

```python
from omnibase_spi.protocols.validation import (
    ProtocolComplianceValidator,
    ProtocolImportValidator,
    ProtocolQualityValidator,
    ProtocolValidationOrchestrator,
    ProtocolValidationProvider,
    ProtocolValidator,
)
```

## See Also

- `API Reference: Validation` (in the omnibase_spi repository) — full protocol reference
- [Dependency Direction](../architecture/omnibase-spi-dependency-direction.md) — compat → core → spi → infra layering
- `Exceptions` (in the omnibase_spi repository) — SPI exception hierarchy
