---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Soft Validation for Environment Variable Parsing"
topics: [omnibase-infra, adr, soft, validation]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-soft-validation-env-parsing.md on 2026-09-02. -->

# ADR: Soft Validation for Environment Variable Parsing

**Status**: Implemented
**Date**: 2025-12-28
**PR**: #106

## Context

ONEX infrastructure handlers require environment variable configuration for operational parameters like timeouts, pool sizes, and buffer limits. These values have valid ranges (e.g., HTTP timeout must be between 1.0 and 300.0 seconds) to ensure reasonable operation.

The question arose: what should happen when an environment variable is set to a value **outside** the valid range?

Two concerns were in tension:
1. **Operational Safety**: Invalid configuration could cause unexpected behavior
2. **Application Availability**: Strict validation could prevent application startup due to misconfiguration, potentially causing outages

In production environments, a misconfigured environment variable should not prevent the application from starting entirely. This is especially important in containerized deployments where environment variables may be set incorrectly during rollout.

## Decision

**Soft validation**: When an environment variable value is parseable but outside the valid range, the system logs a WARNING and uses the default value. The application does NOT fail to start.

This differs from:
- **Type validation** (strict): If a value cannot be parsed as the expected type (e.g., "abc" for an integer), a `ProtocolConfigurationError` is raised
- **Range validation** (soft): If a value is parseable but outside min/max bounds, a warning is logged and the default is used

### Validation Matrix

| Scenario | Behavior | Example |
|----------|----------|---------|
| Env var not set | Use default silently | `ONEX_HTTP_TIMEOUT` unset -> 30.0 |
| Value within range | Use parsed value | `ONEX_HTTP_TIMEOUT=60.0` -> 60.0 |
| Value below minimum | Log warning, use default | `ONEX_HTTP_TIMEOUT=0.5` -> 30.0 + warning |
| Value above maximum | Log warning, use default | `ONEX_HTTP_TIMEOUT=999.0` -> 30.0 + warning |
| Invalid type | Raise exception | `ONEX_HTTP_TIMEOUT=abc` -> `ProtocolConfigurationError` |

## Implementation

The soft validation pattern is implemented in `src/omnibase_infra/utils/util_env_parsing.py`:

### `parse_env_int`

```python
def parse_env_int(
    env_var: str,
    default: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
    transport_type: EnumInfraTransportType | None = None,
    service_name: str = "unknown",
) -> int:
```

### `parse_env_float`

```python
def parse_env_float(
    env_var: str,
    default: float,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
    transport_type: EnumInfraTransportType | None = None,
    service_name: str = "unknown",
) -> float:
```

Both functions:
1. Return the default if the env var is not set
2. Raise `ProtocolConfigurationError` if the value cannot be parsed as the expected type
3. Log a warning and return the default if the value is outside the valid range

### Warning Message Format

The format specifier differs by type:

**For `parse_env_float`** (uses `%f` for float values):
```python
logger.warning(
    "Environment variable %s value %f is below minimum %f, using default %f",
    env_var, parsed, min_value, default,
)
```

**For `parse_env_int`** (uses `%d` for integer values):
```python
logger.warning(
    "Environment variable %s value %d is below minimum %d, using default %d",
    env_var, parsed, min_value, default,
)
```

## Alternatives Considered

### 1. Strict Validation (Rejected)

Throw exceptions for any invalid value, including out-of-range values.

**Pros:**
- Clear feedback during deployment
- Prevents misconfigured deployments from running

**Cons:**
- Application won't start on misconfiguration
- Could cause cascading outages in production
- Rollback may be difficult if deployment infrastructure is also affected

### 2. Silent Fallback (Rejected)

Use defaults without any logging for out-of-range values.

**Pros:**
- Application always starts
- No log noise

**Cons:**
- Configuration errors go completely unnoticed
- Operators have no visibility into misconfiguration
- Debugging becomes difficult

### 3. Soft Validation (Chosen)

Log warning and use default for out-of-range values.

**Pros:**
- Application availability preserved
- Clear warning messages for operators
- Graceful degradation to safe defaults
- Debugging is possible through log analysis

**Cons:**
- Misconfiguration may reach production if logs aren't monitored
- Operators must actively watch for configuration warnings

## Consequences

### Positive

- **Application availability preserved**: A misconfigured environment variable won't prevent startup
- **Clear operator feedback**: Warning logs provide actionable information
- **Safe defaults**: The system degrades gracefully to known-good values
- **Type safety maintained**: Invalid types still fail fast with exceptions
- **Security**: Type errors redact values in error messages (`value="[REDACTED]"`) to prevent credential exposure; range validation warnings do log the actual numeric value since it has already been successfully parsed as the expected type. **Rationale**: Once a value has been successfully parsed as a number (int or float), it cannot contain credentials like passwords, API keys, or connection strings - those would have failed type parsing. A successfully parsed numeric value (e.g., `0.5`, `999`) is inherently non-sensitive and safe to log for debugging purposes.

### Negative

- **Requires log monitoring**: Operators must watch for configuration warnings
- **Delayed feedback**: Misconfiguration may not be noticed until logs are reviewed
- **Potential confusion**: Different validation behaviors for type vs range errors

## Verification

### Log Messages to Monitor

Operators should configure alerts for these log patterns:

```
Environment variable {VAR} value {VALUE} is below minimum {MIN}, using default {DEFAULT}
Environment variable {VAR} value {VALUE} is above maximum {MAX}, using default {DEFAULT}
```

### Example Alert Configuration

```yaml
# Example Prometheus/Loki alert
- alert: ConfigurationRangeWarning
  expr: |
    count_over_time({app="onex"} |= "is below minimum" or "is above maximum" [5m]) > 0
  labels:
    severity: warning
  annotations:
    summary: "ONEX configuration value out of range"
```

### Testing Verification

The behavior is verified in `tests/unit/handlers/test_handler_http_env.py`:

```python
# Constants matching the HTTP handler configuration
_HTTP_TIMEOUT_DEFAULT: float = 30.0
_HTTP_TIMEOUT_MIN: float = 1.0
_HTTP_TIMEOUT_MAX: float = 300.0

def test_timeout_below_minimum_uses_default(
    self, caplog: pytest.LogCaptureFixture
) -> None:
    """Test timeout below minimum (1.0s) uses default with warning logged."""
    with patch.dict(os.environ, {"ONEX_HTTP_TIMEOUT": "0.5"}, clear=True):
        with caplog.at_level(logging.WARNING):
            result = parse_env_float(
                "ONEX_HTTP_TIMEOUT",
                _HTTP_TIMEOUT_DEFAULT,
                min_value=_HTTP_TIMEOUT_MIN,
                max_value=_HTTP_TIMEOUT_MAX,
                transport_type=EnumInfraTransportType.HTTP,
                service_name="http_handler",
            )

        assert result == 30.0
        assert "ONEX_HTTP_TIMEOUT" in caplog.text
        assert "below minimum" in caplog.text
```

## References

- `src/omnibase_infra/utils/util_env_parsing.py` - Implementation
- `.env.example` lines 353-366 - Documentation of soft validation behavior
- `tests/unit/handlers/test_handler_http_env.py` - Comprehensive test coverage
- `tests/unit/handlers/test_handler_http.py` - Integration with HTTP handler
