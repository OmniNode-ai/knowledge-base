---
type: guide
status: current
date: "2026-09-01"
title: "omnibase_spi Validation Protocols Usage"
topics:
  - omnibase_spi
  - validation
  - protocols
refs: []
---

<!-- Migrated from omnibase_spi:src/omnibase_spi/protocols/validation/USAGE.md on 2026-09-01 -->

# Quick Usage Guide - Validation Protocols

This module is protocol-only (see [README.md](../reference/omnibase-spi-validation-protocols.md)) — there is no
`validate_protocol_implementation()` function, no `validation_decorator()`,
no `ArtifactContainerValidator`, and no `enable_protocol_validation()` toggle
anywhere in `omnibase_spi`. What follows are the real protocols and how a
caller typically uses an implementation obtained from `omnibase_core` or
`omnibase_infra`.

## 1. Generic Protocol Conformance Check

```python
from omnibase_spi.protocols.validation import ProtocolValidator

validator: ProtocolValidator = get_validator()
validator.strict_mode = True

result = await validator.validate_implementation(my_impl, MyProtocol)
if not result.is_valid:
    for error in result.errors:
        print(f"  - {error}")
```

## 2. Import Validation

```python
from omnibase_spi.protocols.validation import ProtocolImportValidator

import_validator: ProtocolImportValidator = get_import_validator()
analysis = await import_validator.validate_import_security("subprocess")
print(f"Security risk: {analysis.security_risk}")
```

## 3. Compliance Validation

```python
from omnibase_spi.protocols.validation import ProtocolComplianceValidator

compliance_validator: ProtocolComplianceValidator = get_compliance_validator()
report = await compliance_validator.validate_file_compliance("src/module.py")
print(f"ONEX compliance: {report.onex_compliance_score:.0%}")
```

## 4. Quality Validation

```python
from omnibase_spi.protocols.validation import ProtocolQualityValidator

quality_validator: ProtocolQualityValidator = get_quality_validator()
report = await quality_validator.validate_file_quality("src/module.py")
print(f"Quality score: {report.overall_score:.1f}/100")
```

## 5. Orchestrating All Three

```python
from omnibase_spi.protocols.validation import ProtocolValidationOrchestrator

orchestrator: ProtocolValidationOrchestrator = get_validation_orchestrator()
scope = await orchestrator.create_validation_scope(
    repository_path="/workspace/omnibase_spi",
    validation_types=["imports", "quality", "compliance"],
)
report = orchestrator.orchestrate_validation(scope)
print(f"Success rate: {report.summary.success_rate:.0%}")
```

## Common Error Types

`ProtocolValidationError` (returned inside `ProtocolValidationResult.errors`,
not raised) carries `error_type`, `message`, `context`, and `severity`.
Common `error_type` values used across the compliance/quality validators
include `missing_method`, `parameter_count_mismatch`, and
`protocol_compliance`.

## Need Help?

- Full signatures: [README.md](../reference/omnibase-spi-validation-protocols.md) and
  ``docs/api-reference/VALIDATION.md`` (in the omnibase_spi repository)
- SPI exception hierarchy (separate from the validation-result errors above):
  ``docs/api-reference/EXCEPTIONS.md`` (in the omnibase_spi repository)
- Concrete node implementations live in `omnibase_core` and `omnibase_infra`,
  not in this package.
