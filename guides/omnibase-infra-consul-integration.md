---
type: guide
status: current
date: "2026-09-02"
title: "Consul Integration Patterns"
topics: [omnibase-infra, consul, integration]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/consul_integration.md on 2026-09-02. -->

# Consul Integration Patterns

This document describes patterns for integrating with HashiCorp Consul in ONEX infrastructure services.

## Overview

Consul is used in the ONEX platform for:

1. **Service Discovery** - Registering and discovering ONEX nodes
2. **Key-Value Storage** - Configuration data and coordination
3. **Health Checking** - Service health status tracking

**Primary Implementation**: `src/omnibase_infra/handlers/handler_consul.py`

## Connection Patterns

### Configuration Model

Use `ModelConsulHandlerConfig` for type-safe configuration:

```python
from omnibase_infra.handlers.models.consul import ModelConsulHandlerConfig

config = ModelConsulHandlerConfig(
    host="consul.example.com",       # Consul server hostname
    port=8500,                        # Consul HTTP API port (default: 8500)
    scheme="https",                   # "http" or "https" (default: "http")
    token=SecretStr("acl-token"),    # ACL token (use SecretStr for security)
    timeout_seconds=30.0,             # Request timeout (default: 30.0)
    datacenter="dc1",                 # Optional datacenter for multi-DC
)
```

### Environment Variable Configuration

**Recommended**: Load configuration from environment variables:

```python
import os
from pydantic import SecretStr
from omnibase_infra.handlers.models.consul import ModelConsulHandlerConfig

config = ModelConsulHandlerConfig(
    host=os.getenv("CONSUL_HOST", "localhost"),
    port=int(os.getenv("CONSUL_PORT", "8500")),
    scheme=os.getenv("CONSUL_SCHEME", "http"),
    token=SecretStr(os.getenv("CONSUL_TOKEN", "")),
    timeout_seconds=float(os.getenv("CONSUL_TIMEOUT", "30.0")),
    datacenter=os.getenv("CONSUL_DATACENTER"),
)
```

### Handler Initialization

```python
from omnibase_infra.handlers import HandlerConsul

handler = HandlerConsul()
await handler.initialize({
    "host": "consul.example.com",
    "port": 8500,
    "scheme": "https",
    "token": os.getenv("CONSUL_TOKEN"),
    "timeout_seconds": 30.0,
})
```

## Health Checks

### Connection Verification

The handler verifies Consul connectivity during initialization:

```python
def _verify_consul_connection(
    self, client: consul.Consul, correlation_id: UUID
) -> None:
    """Verify Consul connection by listing datacenters."""
    try:
        # This is a lightweight, read-only operation
        client.catalog.datacenters()
    except Exception as e:
        raise InfraConnectionError(...) from e
```

### Service Health Monitoring

Use the Consul catalog API to check service health:

```python
# Check if a service is healthy
services = client.health.service("my-service", passing=True)
healthy_instances = len(services[1])
```

### Handler Health Status

The handler exposes health through the `describe()` method:

```python
info = handler.describe()
# Returns:
# {
#     "handler_type": "infra_handler",
#     "handler_category": "effect",
#     "supported_operations": ["consul.deregister", "consul.kv_get", ...],
#     "timeout_seconds": 30.0,
#     "initialized": True,
#     "version": "0.1.0-mvp",
# }
```

## Service Registration

### Registration Payload

Use `ModelConsulRegisterPayload` for service registration:

```python
from omnibase_infra.handlers.models.consul import ModelConsulRegisterPayload

payload = ModelConsulRegisterPayload(
    consul_service_id="node-effect-123",    # Unique service ID
    name="my-onex-node",                     # Service name in catalog
    address="192.0.2.100",                 # Service address
    port=8080,                               # Service port
    tags=["onex", "effect-node"],            # Service tags for filtering
    meta={"version": "1.0.0"},               # Service metadata
)
```

### Registration Operation

Execute registration via the handler:

```python
response = await handler.execute({
    "operation": "consul.register",
    "payload": {
        "consul_service_id": "node-effect-123",
        "name": "my-onex-node",
        "address": "192.0.2.100",
        "port": 8080,
    },
    "correlation_id": str(uuid4()),
})
```

### Deregistration

```python
response = await handler.execute({
    "operation": "consul.deregister",
    "payload": {
        "consul_service_id": "node-effect-123",
    },
    "correlation_id": str(uuid4()),
})
```

## Key-Value Operations

### KV Get

```python
response = await handler.execute({
    "operation": "consul.kv_get",
    "payload": {
        "key": "config/my-service/settings",
        "recurse": False,  # Set True to get all keys under prefix
    },
    "correlation_id": str(uuid4()),
})
```

### KV Put

```python
response = await handler.execute({
    "operation": "consul.kv_put",
    "payload": {
        "key": "config/my-service/settings",
        "value": '{"timeout": 30}',
    },
    "correlation_id": str(uuid4()),
})
```

## Security Patterns

### Token Handling

**CRITICAL**: ACL tokens are sensitive credentials. Follow these practices:

1. **Use SecretStr**: Store tokens as `SecretStr` to prevent accidental logging

```python
from pydantic import SecretStr

# CORRECT: Token protected from logging
token = SecretStr(os.getenv("CONSUL_TOKEN"))

# WRONG: Token may be logged
token = os.getenv("CONSUL_TOKEN")  # Plain string
```

2. **Environment Variables**: Never hardcode tokens in configuration

```python
# CORRECT: Load from environment
config = ModelConsulHandlerConfig(
    token=SecretStr(os.getenv("CONSUL_TOKEN", ""))
)

# WRONG: Hardcoded token
config = ModelConsulHandlerConfig(
    token=SecretStr("actual-token-value")  # Security violation!
)
```

3. **Error Sanitization**: Never include tokens in error messages

```python
# CORRECT: Generic error message
raise InfraAuthenticationError(
    "Consul ACL permission denied - check token permissions",
    context=ctx,
)

# WRONG: Exposes token details
raise InfraAuthenticationError(
    f"Token {token} was rejected by Consul",  # SECURITY VIOLATION
    context=ctx,
)
```

### Error Context

Use `ModelInfraErrorContext` for consistent error reporting:

```python
from omnibase_infra.errors import ModelInfraErrorContext
from omnibase_infra.enums import EnumInfraTransportType

ctx = ModelInfraErrorContext(
    transport_type=EnumInfraTransportType.CONSUL,
    operation="consul.register",
    target_name="consul_handler",
    correlation_id=correlation_id,
)
```

## Resilience Patterns

### Circuit Breaker

The Consul handler implements circuit breaker pattern via `MixinAsyncCircuitBreaker`:

```
CLOSED ──(failures >= threshold)──► OPEN
   ▲                                   │
   │                                   │
   │                    (reset_timeout elapsed)
   │                                   │
   └──(success)── HALF_OPEN ◄──────────┘
```

**Configuration**:

```python
from omnibase_infra.handlers.models.consul import ModelConsulRetryConfig

retry_config = ModelConsulRetryConfig(
    max_attempts=3,              # Maximum retry attempts
    initial_delay_seconds=1.0,   # Initial backoff delay
    max_delay_seconds=30.0,      # Maximum backoff delay
    exponential_base=2.0,        # Backoff multiplier
)
```

**Circuit Breaker States**:

| State | Behavior |
|-------|----------|
| CLOSED | Normal operation, requests pass through |
| OPEN | Requests fail immediately with `InfraUnavailableError` |
| HALF_OPEN | Allows single test request; success closes, failure opens |

### Retry Logic

The handler uses exponential backoff for transient failures:

```
delay = initial_delay * (exponential_base ** attempt)
delay = min(delay, max_delay)
```

**Retryable Errors**:
- Connection timeouts
- Consul server errors (5xx)
- Network transient failures

**Non-Retryable Errors**:
- ACL permission denied (authentication failure)
- Invalid configuration
- Client-side validation errors

### Error Classification

```python
# Timeout errors - retryable
if isinstance(error, (TimeoutError, consul.Timeout)):
    return ModelRetryErrorClassification(
        category=EnumRetryErrorCategory.TIMEOUT,
        should_retry=True,
    )

# Authentication errors - NOT retryable
if isinstance(error, consul.ACLPermissionDenied):
    return ModelRetryErrorClassification(
        category=EnumRetryErrorCategory.AUTHENTICATION,
        should_retry=False,
    )
```

## Thread Pool Management

The handler uses a bounded `ThreadPoolExecutor` for synchronous Consul operations:

```python
# Configuration
max_concurrent_operations = 10  # Default, max: 100

# Thread pool prevents blocking the async event loop
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(self._executor, func)
```

**Graceful Shutdown**:

```python
async def shutdown(self) -> None:
    # Wait for pending operations to complete
    self._executor.shutdown(wait=True)
```

## Multi-Datacenter Support

For multi-datacenter deployments:

```python
config = ModelConsulHandlerConfig(
    host="consul.dc1.example.com",
    datacenter="dc1",  # Explicit datacenter
)
```

**Datacenter Differentiation**:
- Circuit breaker service name: `"consul.dc1"`, `"consul.dc2"`
- Structured logging with datacenter field
- Correlation IDs traced across datacenters

## Supported Operations

| Operation | Description |
|-----------|-------------|
| `consul.kv_get` | Retrieve value from KV store |
| `consul.kv_put` | Store value in KV store |
| `consul.register` | Register service with Consul agent |
| `consul.deregister` | Deregister service from Consul agent |

## Related Documentation

- Circuit Breaker Implementation (`../guides/omnibase-infra-circuit-breaker-implementation.md`)
- Error Handling Patterns (internal knowledge base)
- Error Recovery Patterns (internal knowledge base)
- Security Patterns (internal knowledge base)
- Registration Workflow
- [HashiCorp Consul API Docs](https://developer.hashicorp.com/consul/api-docs)

## See Also

- `src/omnibase_infra/handlers/handler_consul.py` - Main handler implementation
- `src/omnibase_infra/handlers/models/consul/` - Consul-specific models
- `src/omnibase_infra/handlers/mixins/mixin_consul_*.py` - Handler mixins
