---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Handler Plugin Loader Security Model"
topics: [omnibase-infra, adr, handler, plugin]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-handler-plugin-loader-security.md on 2026-09-02. -->

# ADR: Handler Plugin Loader Security Model

**Status**: Accepted
**Date**: 2026-01-10

## Context

The `HandlerPluginLoader` is a core runtime component that dynamically loads Python handler classes from YAML contract specifications. This enables contract-driven handler discovery without hardcoding handler references, supporting the ONEX principle of declarative node configuration.

The loader uses Python's `importlib.import_module()` to dynamically import handler classes specified in contract files:

```yaml
# handler_contract.yaml
handler_name: "AuthHandler"
handler_class: "myapp.handlers.auth.AuthHandler"
handler_type: "effect"
```

This dynamic import mechanism introduces security considerations that must be understood and mitigated in production deployments.

### Why This ADR Exists

PR #134 reviewers flagged the need for comprehensive security documentation covering:

1. What security controls are implemented in the loader
2. What attack vectors remain unmitigated
3. How to securely deploy systems using the handler plugin loader

This ADR serves as the authoritative security reference for the `HandlerPluginLoader`.

## Decision

**YAML contracts are treated as executable code, not mere configuration.**

The `HandlerPluginLoader` implements the following security model:

### 1. Contract Files = Code

Any YAML contract file that specifies a `handler_class` path has the same security implications as a Python script. When the loader processes a contract:

1. It reads the `handler_class` fully-qualified path (e.g., `myapp.handlers.AuthHandler`)
2. It calls `importlib.import_module()` on the module path
3. The module's top-level code executes during import

This means:
- **Module-level side effects execute immediately** when a contract is loaded
- **Malicious contracts can execute arbitrary code** if an attacker can write to contract directories
- **Import-time vulnerabilities** in handler modules are triggered by contract discovery

### 2. Contract Content Security: No Secrets

**Handler contracts must NEVER contain secrets, credentials, or sensitive configuration values.**

This is a fundamental security principle separate from dynamic import security:

| Prohibited Content | Why | Risk |
|--------------------|-----|------|
| Passwords, API keys, tokens | Git history exposure | Credential theft |
| Connection strings with credentials | Log leakage | Full system access |
| Private keys, certificates | Repository access | Cryptographic compromise |
| Environment-specific secrets | Cross-environment sharing | Lateral movement |

#### Correct Pattern

```yaml
# handler_contract.yaml - NO secrets, only handler metadata
handler_name: "db.query"
handler_class: "myapp.handlers.DatabaseHandler"
handler_type: "effect"
capability_tags:
  - database
  - pooled
# Credentials loaded at runtime from Vault/env vars
```

#### Why This Matters

1. **Git history is permanent**: Secrets committed once remain in history forever
2. **Contracts are shared**: Same contracts used across dev/staging/prod
3. **Logging exposure**: Contracts may be logged during deployment
4. **Access control mismatch**: Repository access != secret access authorization

**See Also**: Handler Plugin Loader Pattern - Contract Content Security

### 3. Built-in Security Controls

The loader implements several protections:

| Protection | Implementation | Mitigates | Code Location |
|------------|----------------|-----------|---------------|
| **YAML safe loading** | `yaml.safe_load()` | YAML deserialization attacks (`!!python/object` tags) | `load_from_contract()` line ~381 |
| **File size limits** | `MAX_CONTRACT_SIZE = 10MB` | Memory exhaustion, DoS via oversized files | `_validate_file_size()` |
| **Protocol validation** | Duck typing checks for all 5 `ProtocolHandler` methods | Loading arbitrary non-handler classes | `_validate_handler_protocol()` |
| **Error containment** | Graceful failure per contract | Single bad contract doesn't crash system | `load_from_directory()` |
| **Correlation ID tracking** | UUID4 for all operations | Audit trail for security events | All public methods |
| **Class type verification** | `isinstance(handler_class, type)` check | Loading non-class objects (functions, etc.) | `_import_handler_class()` line ~1169 |
| **Error message sanitization** | `_sanitize_exception_message()` | Information disclosure via paths in errors | Lines ~150-181 |

#### Protocol Validation Details

The loader validates that loaded classes implement `ProtocolHandler` by checking for these **5 required methods**:

| Method | Type | Validation Check |
|--------|------|------------------|
| `handler_type` | Property | `hasattr(handler_class, "handler_type")` |
| `initialize` | Async method | `callable(getattr(handler_class, "initialize", None))` |
| `shutdown` | Async method | `callable(getattr(handler_class, "shutdown", None))` |
| `execute` | Async method | `callable(getattr(handler_class, "execute", None))` |
| `describe` | Sync method | `callable(getattr(handler_class, "describe", None))` |

A class **fails validation** if ANY of these methods are missing (error code: `HANDLER_LOADER_006`).

#### Error Message Sanitization

The `_sanitize_exception_message()` function strips filesystem paths from exception messages before including them in user-facing errors:

```python
# Example: Before sanitization
"[Errno 13] Permission denied: '/etc/secrets/key.pem'"

# After sanitization
"[Errno 13] Permission denied: '<path>'"
```

This prevents information disclosure about internal directory structures.

### 4. Optional Security Controls

The loader provides the following **optional** security controls that must be explicitly enabled:

| Control | Implementation | Mitigates | Status |
|---------|----------------|-----------|--------|
| **Namespace allowlisting** | `allowed_namespaces` constructor parameter | Untrusted module imports, path traversal | **IMPLEMENTED (OPTIONAL)** |

**Namespace Allowlisting Usage:**
```python
# Restrict imports to trusted namespaces only
loader = HandlerPluginLoader(
    allowed_namespaces=["omnibase_infra.", "omnibase_core.", "mycompany.handlers."]
)

# This succeeds:
loader.load_from_contract(Path("valid.yaml"))  # handler_class: omnibase_infra.handlers.Auth

# This fails with NAMESPACE_NOT_ALLOWED (HANDLER_LOADER_013):
loader.load_from_contract(Path("bad.yaml"))  # handler_class: malicious_pkg.EvilHandler
```

**Security Trade-off:**
- **Default (None)**: No namespace restriction - any importable module can be loaded. Suitable for trusted environments with strict file access controls.
- **Explicit allowlist**: Only modules starting with specified prefixes can be loaded. Recommended for production deployments.
- **Empty list**: Blocks ALL namespaces - effectively disables the loader.

**Path Traversal Protection:**

The `allowed_namespaces` parameter includes **package boundary validation** that prevents path traversal attacks:

- Prefix `"foo."` only matches `foo.bar`, NOT `foobar.module`
- Implementation validates that namespace boundaries are respected
- Recommendation: Always use trailing dots (e.g., `"omnibase_infra."`) for maximum security

### 5. What the Loader Does NOT Protect Against

**CRITICAL**: The following protections require deployment-level mitigation:

| Gap | Risk Level | Description | Required Mitigation |
|-----|------------|-------------|---------------------|
| **Arbitrary code execution** | CRITICAL | Any module on `sys.path` can be imported (unless namespace allowlisting is enabled) | Enable `allowed_namespaces` OR deployment-level file access controls |
| **Path traversal** | HIGH | No validation of module path structure (unless namespace allowlisting is enabled) | Enable `allowed_namespaces` |
| **Module signature verification** | HIGH | No cryptographic validation of handler code | Signed container images |
| **Import hook filtering** | MEDIUM | No interception of `importlib` calls | Custom `MetaPathFinder` |
| **Runtime isolation** | MEDIUM | Handlers run in same process as loader | Subprocess isolation |
| **Mutation prevention** | MEDIUM | Loaded modules can modify global state | Process/container isolation |

## Security Threat Model

### Attack Vectors and Mitigations

| # | Attack Vector | Description | Risk | Mitigation Status | Control |
|---|---------------|-------------|------|-------------------|---------|
| 1 | **YAML deserialization attack** | Malicious YAML constructs like `!!python/object` execute arbitrary code | CRITICAL | **MITIGATED** | `yaml.safe_load()` blocks unsafe tags |
| 2 | **Memory exhaustion** | Oversized contract files consume memory, causing DoS | HIGH | **MITIGATED** | 10MB file size limit enforced before parsing |
| 3 | **Arbitrary class loading** | Contract specifies class that doesn't implement handler protocol | HIGH | **MITIGATED** | Protocol validation requires 5 methods |
| 4 | **Malicious contract injection** | Attacker writes contract pointing to malicious module | CRITICAL | **OPTIONALLY MITIGATED** | Enable `allowed_namespaces` OR deployment-level file access controls |
| 5 | **Module path manipulation** | Contract specifies path to unintended system module | CRITICAL | **OPTIONALLY MITIGATED** | Enable `allowed_namespaces` parameter |
| 6 | **Import-time code execution** | Module-level code executes during `import_module()` | CRITICAL | **OPTIONALLY MITIGATED** | Enable `allowed_namespaces` to restrict to trusted modules |
| 7 | **Handler instantiation exploits** | Malicious `__init__` runs when handler is instantiated | HIGH | **OPTIONALLY MITIGATED** | Enable `allowed_namespaces` to restrict to trusted modules |
| 8 | **Path information disclosure** | Exception messages expose filesystem paths | MEDIUM | **MITIGATED** | `_sanitize_exception_message()` strips paths |
| 9 | **Non-class object loading** | Contract points to function/variable, not class | MEDIUM | **MITIGATED** | `isinstance(handler_class, type)` check |
| 10 | **Probing attacks** | Attacker submits contracts to discover installed modules | LOW | **PARTIALLY MITIGATED** | Error codes reveal module existence; requires log monitoring |

### Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TRUSTED ZONE                                    │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │ Contract Files  │───>│ HandlerPlugin   │───>│ Handler Modules │  │
│  │ (YAML)          │    │ Loader          │    │ (Python)        │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘  │
│         │                        │                      │           │
│         ▼                        ▼                      ▼           │
│  Filesystem access       importlib.import_module   Arbitrary code   │
│  controls                                          execution        │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ TRUST BOUNDARY: Everything entering this zone must be trusted
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      UNTRUSTED ZONE                                  │
│  User input, external APIs, unverified sources                       │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Principle**: Contract files and handler modules MUST come from trusted sources. The loader cannot distinguish between legitimate and malicious module paths.

## Consequences

### Positive

- Clear security model: contracts = code
- Enables flexible, declarative handler configuration
- Existing protections prevent common attack vectors (YAML injection, memory exhaustion, non-handler classes)
- Audit trail via correlation IDs for incident response
- Error message sanitization prevents path disclosure

### Negative

- Requires strict access control on contract directories
- Cannot safely load contracts from untrusted sources
- No runtime isolation between handlers
- Side effects during import may cause unexpected behavior

### Neutral

- Security posture matches other plugin systems (e.g., pytest plugins, Django apps)
- Responsibility for handler security shifts to deployment configuration

## Deployment Checklist

### Minimum Requirements Checklist

All production deployments MUST complete these items:

- [ ] **1. File Permissions Configured**
  ```bash
  chmod 755 /app/contracts
  chmod 644 /app/contracts/**/*.yaml
  chown -R appuser:appgroup /app/contracts
  ```

- [ ] **2. Write Protection Enabled**
  ```yaml
  # Kubernetes volume mount example
  volumeMounts:
    - name: handler-contracts
      mountPath: /app/contracts
      readOnly: true
  ```

- [ ] **3. Contract Source Validation**
  - Contracts come from version-controlled repositories with code review
  - Container images are signed
  - Artifact registries verify provenance
  - **Contracts contain NO secrets** (passwords, API keys, tokens)
  - CI pipeline includes secret scanning (gitleaks, detect-secrets)

- [ ] **4. Handler Loading Logging Enabled**
  ```python
  import logging
  logging.getLogger("omnibase_infra.runtime.handler_plugin_loader").setLevel(logging.INFO)
  ```

- [ ] **5. Contract Validation in CI**
  - Run `onex validate` in CI pipeline to catch malformed contracts before deployment
  - Validate handler classes exist and implement protocol

- [ ] **6. Monitoring Configured**
  - Alert on unexpected `handler_class` module paths
  - Monitor for high contract load failure rates
  - Track file system changes to contract directories

### High-Security Environment Checklist

For elevated security requirements, also complete:

- [ ] **7. Namespace Allowlisting Enabled**
  - Use the built-in `allowed_namespaces` parameter (see below)
  - Validates `handler_class` against allowed prefixes BEFORE import

- [ ] **8. Import Audit Hook Installed**
  - Custom `MetaPathFinder` logs all dynamic imports
  - Alerts on imports outside expected namespaces

- [ ] **9. Process Isolation Evaluated**
  - Consider subprocess isolation for untrusted handlers
  - Container-level isolation for multi-tenant deployments

- [ ] **10. Incident Response Plan Documented**
  - Procedure for handling suspected malicious contracts
  - Rotation plan for secrets that may have been exposed

## High-Security Mitigations

### Namespace Allowlisting (Built-in)

The loader has **built-in namespace allowlisting** via the `allowed_namespaces` constructor parameter.
This is the recommended approach for production deployments:

```python
from omnibase_infra.runtime.handler_plugin_loader import HandlerPluginLoader

# Define trusted namespace prefixes
ALLOWED_NAMESPACES = [
    "omnibase_infra.handlers.",     # First-party handlers
    "omnibase_core.handlers.",      # Core handlers
    "myapp.handlers.",              # Application handlers
    "approved_plugins.",            # Vetted third-party
]

# Create loader with namespace restriction
loader = HandlerPluginLoader(allowed_namespaces=ALLOWED_NAMESPACES)

# This succeeds (handler_class: omnibase_infra.handlers.AuthHandler):
handler = loader.load_from_contract(Path("auth_contract.yaml"))

# This fails with NAMESPACE_NOT_ALLOWED (HANDLER_LOADER_013):
# (handler_class: malicious_pkg.EvilHandler)
handler = loader.load_from_contract(Path("malicious_contract.yaml"))
```

**Error Code**: `HANDLER_LOADER_013` (`NAMESPACE_NOT_ALLOWED`) is raised when a handler module
path does not start with any of the allowed namespace prefixes.

**Security Trade-offs:**

| Configuration | Behavior | Use Case |
|---------------|----------|----------|
| `allowed_namespaces=None` (default) | All namespaces allowed | Development, trusted environments |
| `allowed_namespaces=["omnibase_.", "myapp."]` | Only specified prefixes allowed | Production deployments |
| `allowed_namespaces=[]` | ALL namespaces blocked | Effectively disables loader |

**Legacy Wrapper Pattern** (for environments needing custom validation logic):

For environments requiring additional validation beyond namespace prefixes, you can wrap the loader:

```python
from pathlib import Path
from typing import Final

import yaml

from omnibase_infra.runtime.handler_plugin_loader import HandlerPluginLoader
from omnibase_infra.models.runtime import ModelLoadedHandler

# Define trusted namespace prefixes
ALLOWED_MODULE_PREFIXES: Final[tuple[str, ...]] = (
    "omnibase_infra.handlers.",     # First-party handlers
    "myapp.handlers.",              # Application handlers
    "approved_plugins.",            # Vetted third-party
)


from omnibase_infra.errors import ProtocolConfigurationError, ModelInfraErrorContext
from omnibase_infra.enums import EnumInfraTransportType


class SecurityValidationError(ProtocolConfigurationError):
    """Raised when security validation fails.

    Extends ProtocolConfigurationError to integrate with ONEX error handling.
    """
    pass


def secure_load_from_contract(
    loader: HandlerPluginLoader,
    path: Path,
    correlation_id: str | None = None,
) -> ModelLoadedHandler:
    """Load handler with additional custom validation."""
    with open(path) as f:
        contract_data = yaml.safe_load(f)

    handler_class = contract_data.get("handler_class", "")
    if not any(handler_class.startswith(prefix) for prefix in ALLOWED_MODULE_PREFIXES):
        raise SecurityValidationError(
            f"Handler module path '{handler_class}' not in allowlist. "
            f"Allowed prefixes: {ALLOWED_MODULE_PREFIXES}"
        )

    # Additional custom validation can go here
    return loader.load_from_contract(path, correlation_id)
```

**Note**: The built-in `allowed_namespaces` parameter is preferred over wrapper functions
as it validates BEFORE any import occurs, providing defense-in-depth.

### Import Hook Monitoring

Use Python's import system to audit dynamic imports:

```python
import logging
import sys
from importlib.abc import MetaPathFinder

logger = logging.getLogger("security.imports")


class SecurityAuditFinder(MetaPathFinder):
    """Meta path finder that logs all dynamic imports."""

    def find_module(self, fullname: str, path=None):
        logger.info(
            "Dynamic import: %s",
            fullname,
            extra={"module": fullname, "path": path},
        )
        return None  # Allow import to proceed

# Install at application startup
sys.meta_path.insert(0, SecurityAuditFinder())
```

### Subprocess Isolation

For complete isolation, run handlers in separate processes:

```python
import multiprocessing
from typing import Any


def run_handler_isolated(
    handler_module: str,
    handler_class: str,
    method: str,
    args: tuple[Any, ...],
) -> Any:
    """Execute handler in isolated subprocess."""
    def worker(queue, module, cls, method, args):
        import importlib
        mod = importlib.import_module(module)
        handler = getattr(mod, cls)()
        result = getattr(handler, method)(*args)
        queue.put(result)

    queue = multiprocessing.Queue()
    process = multiprocessing.Process(
        target=worker,
        args=(queue, handler_module, handler_class, method, args),
    )
    process.start()
    process.join(timeout=30)

    if process.is_alive():
        process.terminate()
        raise TimeoutError("Handler execution timed out")

    return queue.get()
```

## Monitoring and Incident Response

### Security Event Logging

The loader logs security-relevant events with correlation IDs:

| Event | Log Level | When |
|-------|-----------|------|
| Contract load success | INFO | Handler successfully loaded |
| Contract load failure | WARNING | Individual contract failed |
| Protocol validation failure | WARNING | Class missing required methods |
| Module import error | WARNING | `importlib.import_module()` failed |
| File size exceeded | WARNING | Contract exceeds 10MB limit |
| Ambiguous configuration | WARNING | Both contract types in same directory |

### Error Codes for Security Events

| Code | Enum | Security Relevance |
|------|------|-------------------|
| HANDLER_LOADER_010 | `MODULE_NOT_FOUND` | May indicate probing for installed modules |
| HANDLER_LOADER_011 | `CLASS_NOT_FOUND` | Module exists but class missing; potential typosquatting |
| HANDLER_LOADER_012 | `IMPORT_ERROR` | Import failed; may indicate dependency issues or malformed code |
| HANDLER_LOADER_006 | `PROTOCOL_NOT_IMPLEMENTED` | Class doesn't implement handler protocol; blocks arbitrary class loading |

### Incident Response Steps

If a malicious contract is suspected:

1. **Isolate**: Stop loading new contracts immediately
2. **Identify**: Check logs for correlation IDs of suspicious loads
3. **Contain**: Remove compromised contract files
4. **Analyze**: Review what code was executed during import
5. **Remediate**: Rotate any secrets that may have been exposed
6. **Prevent**: Implement additional controls (allowlisting, monitoring)

## Rationale

### Why dynamic import is necessary

1. **Contract-driven architecture**: ONEX uses declarative contracts to define handler bindings without code changes
2. **Plugin extensibility**: Third-party handlers can be loaded without modifying core runtime
3. **Deployment flexibility**: Different environments can use different handlers via contract configuration
4. **Zero coupling**: Runtime has no compile-time dependency on handler implementations

### Why contracts are treated as code

Attempting to "sanitize" import paths creates a false sense of security:

1. **Any valid Python module can have side effects** at import time
2. **Attackers who can write contracts** already have significant system access
3. **Path validation is insufficient** when the module itself may be compromised
4. **Defense in depth** requires treating the entire contract source as trusted

### Why safe_load is not sufficient

`yaml.safe_load()` prevents YAML deserialization attacks (e.g., `!!python/object` tags) but does NOT prevent:

- Malicious `handler_class` values that point to attacker-controlled modules
- Module side effects during `import_module()` execution
- Post-import exploitation via handler instantiation

## Implementation

### File Structure

```
src/omnibase_infra/runtime/
    handler_plugin_loader.py        # Main loader implementation
    protocol_handler_plugin_loader.py  # Protocol definition
```

### Security-Relevant Code Sections

```python
# Safe YAML loading (line ~381)
raw_data = yaml.safe_load(f)

# Error message sanitization (lines ~150-181)
def _sanitize_exception_message(exception: BaseException) -> str:
    """Sanitize exception message to prevent information disclosure."""
    ...

# Dynamic import (line ~1117)
module = importlib.import_module(module_path)

# Protocol validation (lines ~972-1075)
def _validate_handler_protocol(self, handler_class: type) -> tuple[bool, list[str]]:
    # Duck typing checks for 5 ProtocolHandler methods
    ...

# Class type verification (line ~1169)
if not isinstance(handler_class, type):
    ...
```

## References

- `src/omnibase_infra/runtime/handler_plugin_loader.py` - Main implementation
- `src/omnibase_infra/runtime/protocol_handler_plugin_loader.py` - Protocol definition
- `src/omnibase_infra/models/runtime/model_loaded_handler.py` - Result model
- `docs/patterns/handler_plugin_loader.md` - Usage patterns and security section
- `docs/patterns/security_patterns.md` - General ONEX security guidance
- Python `importlib` documentation: https://docs.python.org/3/library/importlib.html
