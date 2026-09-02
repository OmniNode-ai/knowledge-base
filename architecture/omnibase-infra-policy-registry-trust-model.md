---
type: architecture
status: accepted
date: "2026-09-02"
title: "Policy Registry Trust Model"
topics: [omnibase-infra, policy, registry, trust]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/policy_registry_trust_model.md on 2026-09-02. -->

# Policy Registry Trust Model

This document describes the trust model and security considerations for `PolicyRegistry`, which manages policy plugin registration in ONEX infrastructure.

## Overview

PolicyRegistry accepts arbitrary policy classes for registration. This document clarifies:
- What validation the registry performs
- What the registry does NOT validate
- Trust assumptions policy authors must understand
- Mitigation strategies for high-security environments

## Validation Summary

### What PolicyRegistry VALIDATES

| Validation | Method | Error Type |
|------------|--------|------------|
| Async method detection | `_validate_sync_enforcement()` | `PolicyRegistryError` |
| Policy type (enum value) | `_normalize_policy_type()` | `PolicyRegistryError` |
| Version format (semver) | `_parse_semver()` | `ProtocolConfigurationError` |
| Non-empty policy_id | `ModelPolicyRegistration` | `ValidationError` |
| Thread-safe registration | `threading.Lock` | N/A (implicit) |

### What PolicyRegistry Does NOT Validate

| Aspect | Risk | Caller Responsibility |
|--------|------|----------------------|
| Protocol conformance | Runtime failures when invoking missing methods | Verify class implements ProtocolPolicy |
| Code safety | Malicious code executes with host privileges | Code review, static analysis |
| Behavior correctness | Incorrect decisions, non-determinism | Testing, monitoring |
| Import side effects | Resource exhaustion, network calls on import | Vet dependencies |
| Runtime behavior | Hangs, memory exhaustion, exceptions | Timeouts, resource limits |
| Idempotency | Inconsistent results on retry | Design review |

## Trust Assumptions

PolicyRegistry operates under the following trust assumptions:

### 1. Trusted Source Assumption

Policy classes MUST come from trusted sources:

```python
# TRUSTED: Internal codebase modules
from myapp.policies.retry import ExponentialBackoffPolicy

# TRUSTED: Vetted first-party packages
from omnibase_policies.orchestrator import RateLimiterPolicy

# TRUSTED: Audited third-party packages (explicit approval required)
from approved_vendor.policies import ThrottlePolicy

# UNTRUSTED: Never do this
user_input = request.get("policy_class")
policy_class = eval(user_input)  # CRITICAL SECURITY VULNERABILITY
```

### 2. Safe Registration Assumption

Policy classes must not execute arbitrary code when referenced:

```python
# SAFE: Standard class definition
class SafePolicy:
    def evaluate(self, context: dict) -> PolicyResult:
        return PolicyResult(decision=True)

# UNSAFE: Metaclass with side effects
class UnsafeMeta(type):
    def __new__(mcs, name, bases, namespace):
        # Executes when class is defined or imported
        send_telemetry_to_external_server()  # BAD
        return super().__new__(mcs, name, bases, namespace)

class UnsafePolicy(metaclass=UnsafeMeta):
    pass

# UNSAFE: __init_subclass__ side effects
class BaseWithSideEffects:
    def __init_subclass__(cls):
        # Executes when subclass is defined
        establish_database_connection()  # BAD
```

### 3. Trust Boundary Assumption

Policy instances must stay within trust boundaries:

```python
# CORRECT: Single-tenant registry
tenant_registry = PolicyRegistry()
tenant_registry.register(tenant_policy)

# INCORRECT: Shared registry across tenants (security risk)
shared_registry = PolicyRegistry()
shared_registry.register(tenant_a_policy)
shared_registry.register(tenant_b_policy)  # Can tenant B access tenant A's logic?
```

### 4. Purity Contract Assumption

Policy implementers must follow the purity contract:

```python
# CORRECT: Pure decision logic
class PurePolicy:
    def evaluate(self, context: dict) -> PolicyResult:
        # No I/O, no side effects, deterministic
        threshold = context.get("threshold", 0.5)
        score = context.get("score", 0.0)
        return PolicyResult(decision=score >= threshold)

# INCORRECT: Violates purity contract
class ImpurePolicy:
    def evaluate(self, context: dict) -> PolicyResult:
        # BAD: Database I/O
        user = database.query("SELECT * FROM users WHERE id = ?", context["user_id"])

        # BAD: Network call
        external_score = requests.get(f"https://api.example.com/score/{context['id']}").json()

        # BAD: File I/O
        with open("/var/log/policy.log", "a", encoding="utf-8") as f:
            f.write(f"Evaluated at {datetime.now()}\n")

        # BAD: Side effect (state mutation)
        self.evaluation_count += 1

        return PolicyResult(decision=True)
```

## Security Mitigations for High-Security Environments

### Policy Registry Error Class

Following ONEX error conventions, `PolicyRegistryError` extends `RuntimeHostError` to integrate with the standard error handling infrastructure:

```python
from omnibase_infra.errors import RuntimeHostError, ModelInfraErrorContext
from omnibase_infra.enums import EnumPolicyType, EnumInfraTransportType


class PolicyRegistryError(RuntimeHostError):
    """Raised when policy registration or execution fails.

    Extends RuntimeHostError to integrate with ONEX error handling.
    Provides policy-specific context for debugging and monitoring.

    Error Codes (POLICY_REG domain):
        POLICY_REG_001: Policy not registered (lookup failure)
            - Use when: get() called for unregistered policy_id
            - Context: Include policy_id in error
        POLICY_REG_002: Policy has async methods (sync enforcement violation)
            - Use when: policy class has async methods but allow_async=False
            - Context: Include policy_id and method names
        POLICY_REG_003: Invalid policy type identifier
            - Use when: policy_type not in EnumPolicyType
            - Context: Include provided policy_type value
        POLICY_REG_004: Policy protocol not implemented
            - Use when: policy class missing required ProtocolPolicy methods
            - Context: Include policy class name and missing methods
        POLICY_REG_005: Policy registration limit exceeded
            - Use when: registry capacity exceeded (if limits configured)
            - Context: Include current count and limit
        POLICY_REG_006: Code review not approved
            - Use when: ReviewedPolicyRegistry rejects unreviewed policy
            - Context: Include policy_id and code_hash
        POLICY_REG_007: Static analysis failed
            - Use when: SecureRegistryWrapper security scan fails
            - Context: Include policy_id and scan issues
        POLICY_REG_008: Not in allowlist
            - Use when: AllowlistEnforcedRegistry rejects non-allowlisted policy
            - Context: Include policy_id
        POLICY_REG_009: Timeout exceeded
            - Use when: execute_policy_safely() times out
            - Context: Include policy_id and timeout_seconds
        POLICY_REG_010: Memory exceeded
            - Use when: execute_policy_safely() exceeds memory limit
            - Context: Include policy_id and max_memory_mb

    All errors should include:
        - correlation_id: For request tracing (required in ModelInfraErrorContext)
        - policy_id: The policy that caused the error (when available)
        - error_code: The POLICY_REG_xxx code for categorization
    """

    def __init__(
        self,
        message: str,
        policy_id: str | None = None,
        policy_type: str | EnumPolicyType | None = None,
        context: ModelInfraErrorContext | None = None,
        error_code: str | None = None,
        **kwargs: object,
    ) -> None:
        """Initialize PolicyRegistryError with policy-specific context.

        Args:
            message: Human-readable error message
            policy_id: The policy ID that caused the error
            policy_type: The policy type (EnumPolicyType or string)
            context: Infrastructure error context with correlation ID
            error_code: Error code for categorization (e.g., "POLICY_REG_001")
            **kwargs: Additional context fields
        """
        super().__init__(message, context=context, **kwargs)
        self.policy_id = policy_id
        self.policy_type = (
            policy_type.value if isinstance(policy_type, EnumPolicyType) else policy_type
        )
        self.error_code = error_code
```

### 1. Code Review Gate

Require mandatory code review for all policy implementations:

```python
from typing import Protocol
from uuid import uuid4

from omnibase_infra.errors import PolicyRegistryError, ModelInfraErrorContext
from omnibase_infra.enums import EnumInfraTransportType


class PolicyReviewGate(Protocol):
    """Protocol for policy review integration."""

    def is_approved(self, policy_id: str, code_hash: str) -> bool:
        """Check if policy code has been reviewed and approved."""
        ...

class ReviewedPolicyRegistry:
    """Registry wrapper that enforces code review."""

    def __init__(
        self,
        registry: PolicyRegistry,
        review_gate: PolicyReviewGate,
    ) -> None:
        self._registry = registry
        self._review_gate = review_gate

    def register(self, registration: ModelPolicyRegistration) -> None:
        # Compute hash of policy class source
        import hashlib
        import inspect
        source = inspect.getsource(registration.policy_class)
        code_hash = hashlib.sha256(source.encode()).hexdigest()

        if not self._review_gate.is_approved(registration.policy_id, code_hash):
            context = ModelInfraErrorContext(
                transport_type=EnumInfraTransportType.RUNTIME,
                operation="validate_code_review",
                correlation_id=uuid4(),
            )
            raise PolicyRegistryError(
                f"Policy has not been reviewed. Code hash: {code_hash}",
                policy_id=registration.policy_id,
                context=context,
                error_code="POLICY_REG_006",  # Code review not approved
            )

        self._registry.register(registration)
```

### 2. Static Analysis Integration

Run security scanners before registration:

```python
import subprocess
import tempfile
import inspect
from pathlib import Path

from omnibase_infra.errors import PolicyRegistryError, ModelInfraErrorContext
from omnibase_infra.enums import EnumInfraTransportType


def run_security_scan(policy_class: type) -> tuple[bool, list[str]]:
    """Run bandit and semgrep on policy source code.

    Returns:
        Tuple of (passed: bool, issues: list[str])
    """
    source = inspect.getsource(policy_class)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
    ) as f:
        f.write(source)
        temp_path = Path(f.name)

    try:
        issues = []

        # Run bandit (Python security linter)
        bandit_result = subprocess.run(
            ["bandit", "-f", "json", str(temp_path)],
            capture_output=True,
            text=True,
            check=False,
            shell=False,  # Explicit for security - prevents shell injection
        )
        if bandit_result.returncode != 0:
            issues.append(f"Bandit: {bandit_result.stdout}")

        # Run semgrep with security ruleset
        semgrep_result = subprocess.run(
            ["semgrep", "--config=p/security-audit", "--json", str(temp_path)],
            capture_output=True,
            text=True,
            check=False,
            shell=False,  # Explicit for security - prevents shell injection
        )
        if semgrep_result.returncode != 0:
            issues.append(f"Semgrep: {semgrep_result.stdout}")

        return len(issues) == 0, issues
    finally:
        temp_path.unlink()


class SecureRegistryWrapper:
    """Registry wrapper with static analysis enforcement."""

    def __init__(self, registry: PolicyRegistry) -> None:
        self._registry = registry

    def register(self, registration: ModelPolicyRegistration) -> None:
        from uuid import uuid4

        passed, issues = run_security_scan(registration.policy_class)

        if not passed:
            context = ModelInfraErrorContext(
                transport_type=EnumInfraTransportType.RUNTIME,
                operation="validate_static_analysis",
                correlation_id=uuid4(),
            )
            raise PolicyRegistryError(
                f"Policy failed security scan: {issues}",
                policy_id=registration.policy_id,
                context=context,
                error_code="POLICY_REG_007",  # Static analysis failed
            )

        self._registry.register(registration)
```

### 3. Policy Allowlist

Maintain explicit allowlist of approved policies:

```python
from dataclasses import dataclass
from typing import FrozenSet
from uuid import uuid4

from omnibase_infra.errors import PolicyRegistryError, ModelInfraErrorContext
from omnibase_infra.enums import EnumInfraTransportType


@dataclass(frozen=True)
class PolicyAllowlist:
    """Immutable allowlist of approved policy IDs."""

    approved_ids: FrozenSet[str]

    def is_allowed(self, policy_id: str) -> bool:
        return policy_id in self.approved_ids


# Production allowlist (load from secure configuration)
PRODUCTION_ALLOWLIST = PolicyAllowlist(
    approved_ids=frozenset({
        "exponential_backoff",
        "rate_limiter",
        "retry_with_jitter",
        "circuit_breaker_policy",
        "timeout_policy",
    })
)


class AllowlistEnforcedRegistry:
    """Registry that only accepts allowlisted policy IDs."""

    def __init__(
        self,
        registry: PolicyRegistry,
        allowlist: PolicyAllowlist,
    ) -> None:
        self._registry = registry
        self._allowlist = allowlist

    def register(self, registration: ModelPolicyRegistration) -> None:
        if not self._allowlist.is_allowed(registration.policy_id):
            context = ModelInfraErrorContext(
                transport_type=EnumInfraTransportType.RUNTIME,
                operation="validate_allowlist",
                correlation_id=uuid4(),
            )
            raise PolicyRegistryError(
                "Policy is not in the approved allowlist. "
                "Contact security team to request approval.",
                policy_id=registration.policy_id,
                context=context,
                error_code="POLICY_REG_008",  # Not in allowlist
            )

        self._registry.register(registration)
```

### 4. Runtime Monitoring and Timeouts

Wrap policy execution with resource limits:

```python
import asyncio
import resource
from contextlib import contextmanager
from typing import TypeVar, Callable
from uuid import UUID, uuid4

from omnibase_infra.errors import PolicyRegistryError, ModelInfraErrorContext
from omnibase_infra.enums import EnumInfraTransportType

T = TypeVar("T")


@contextmanager
def resource_limits(
    max_memory_mb: int = 100,
    max_cpu_seconds: float = 1.0,
):
    """Context manager to enforce resource limits on policy execution."""
    # Set memory limit
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(
        resource.RLIMIT_AS,
        (max_memory_mb * 1024 * 1024, hard),
    )

    # Set CPU time limit
    resource.setrlimit(
        resource.RLIMIT_CPU,
        (int(max_cpu_seconds), int(max_cpu_seconds) + 1),
    )

    try:
        yield
    finally:
        # Restore original limits
        resource.setrlimit(resource.RLIMIT_AS, (soft, hard))


async def execute_policy_safely(
    policy: ProtocolPolicy,
    context: dict,
    timeout_seconds: float = 1.0,
    max_memory_mb: int = 100,
    correlation_id: UUID | None = None,
) -> PolicyResult:
    """Execute policy with timeout and resource limits.

    Args:
        policy: Policy instance to execute
        context: Evaluation context
        timeout_seconds: Maximum execution time
        max_memory_mb: Maximum memory allocation
        correlation_id: Optional correlation ID for tracing

    Returns:
        Policy evaluation result

    Raises:
        PolicyRegistryError: If policy exceeds limits (POLICY_REG_009, POLICY_REG_010)
    """
    corr_id = correlation_id or uuid4()
    policy_id = getattr(policy, "policy_id", "unknown")

    try:
        with resource_limits(max_memory_mb=max_memory_mb):
            result = await asyncio.wait_for(
                asyncio.to_thread(policy.evaluate, context),
                timeout=timeout_seconds,
            )
        return result
    except asyncio.TimeoutError:
        error_context = ModelInfraErrorContext(
            transport_type=EnumInfraTransportType.RUNTIME,
            operation="execute_policy",
            correlation_id=corr_id,
        )
        raise PolicyRegistryError(
            f"Policy exceeded timeout of {timeout_seconds}s",
            policy_id=policy_id,
            context=error_context,
            error_code="POLICY_REG_009",  # Timeout exceeded
        )
    except MemoryError:
        error_context = ModelInfraErrorContext(
            transport_type=EnumInfraTransportType.RUNTIME,
            operation="execute_policy",
            correlation_id=corr_id,
        )
        raise PolicyRegistryError(
            f"Policy exceeded memory limit of {max_memory_mb}MB",
            policy_id=policy_id,
            context=error_context,
            error_code="POLICY_REG_010",  # Memory exceeded
        )
```

## Safe Usage Patterns

### DO

```python
# 1. Register policies from known, reviewed source modules
from myapp.policies.reviewed import ApprovedPolicy
registry.register(ModelPolicyRegistration(
    policy_id="approved_policy",
    policy_class=ApprovedPolicy,
    policy_type=EnumPolicyType.ORCHESTRATOR,
))

# 2. Use container-based DI for better lifecycle management
async def bootstrap(container: ModelONEXContainer) -> None:
    wire_infrastructure_services(container)
    registry = await container.service_registry.resolve_service(PolicyRegistry)
    # Policies registered via container lifecycle

# 3. Document policy dependencies and requirements
class DocumentedPolicy:
    """Rate limiting policy.

    Requirements:
        - Requires 'rate_limit' in context (float, requests/second)
        - Requires 'window_seconds' in context (int)

    Dependencies:
        - None (pure logic only)

    Thread Safety:
        - Stateless, thread-safe
    """

    def evaluate(self, context: dict) -> PolicyResult:
        ...

# 4. Test policies in isolation before registration
def test_policy_correctness():
    policy = MyPolicy()
    result = policy.evaluate({"input": "test"})
    assert result.decision is True
    assert result.metadata["reason"] == "expected_reason"

# 5. Monitor policy execution metrics
from prometheus_client import Histogram, Counter

policy_latency = Histogram(
    "policy_evaluation_seconds",
    "Policy evaluation latency",
    ["policy_id"],
)
policy_errors = Counter(
    "policy_evaluation_errors_total",
    "Policy evaluation errors",
    ["policy_id", "error_type"],
)
```

### DON'T

```python
# 1. NEVER register policy classes from untrusted users
user_class_name = request.get("class")
policy_class = globals()[user_class_name]  # CRITICAL VULNERABILITY

# 2. NEVER allow dynamic policy class construction from user input
user_code = request.get("policy_code")
exec(user_code)  # CRITICAL VULNERABILITY
policy_class = eval(request.get("class_name"))  # CRITICAL VULNERABILITY

# 3. NEVER skip code review for new policy implementations
def auto_register_all_policies():
    # BAD: No review gate
    for module in discover_policy_modules():
        for cls in module.get_policy_classes():
            registry.register(cls)  # What if cls is malicious?

# 4. NEVER assume policies are safe because they're in the registry
policy_cls = registry.get("unknown_policy")
# BAD: Trusting the policy without validation
result = policy_cls().evaluate(sensitive_context)

# 5. NEVER share registries across trust boundaries
global_registry = PolicyRegistry()  # Shared across all tenants
tenant_a.use_registry(global_registry)  # Can access tenant_b policies?
tenant_b.use_registry(global_registry)  # Security boundary violated
```

## Comparison with Alternative Approaches

| Approach | Validation Level | Performance | Complexity | Use Case |
|----------|-----------------|-------------|------------|----------|
| PolicyRegistry (current) | Minimal | Excellent | Low | Trusted internal code |
| + Code Review Gate | Medium | Good | Medium | Enterprise environments |
| + Static Analysis | Medium-High | Moderate | High | Security-conscious orgs |
| + Allowlist | High | Excellent | Low | Production lockdown |
| + Sandboxing | Very High | Poor | Very High | Multi-tenant, untrusted |

## Related Patterns

- Security Patterns (internal knowledge base) - Comprehensive security guide including policy security, input validation, and authentication
- Container Dependency Injection (`../architecture/omnibase-infra-container-dependency-injection.md`) - How to properly inject PolicyRegistry
- Error Handling Patterns (internal knowledge base) - PolicyRegistryError usage
- Correlation ID Tracking (`../architecture/omnibase-infra-correlation-id-tracking.md`) - Tracing policy evaluations

## Architecture Layer Enforcement

PolicyRegistry operates within the `omnibase_infra` layer. The architecture layer
validation ensures proper separation between `omnibase_core` (pure, no I/O) and
`omnibase_infra` (infrastructure, owns all I/O).

**CI Enforcement:**
- Pre-push hook: `onex-validate-architecture-layers` in `.pre-commit-config.yaml`
- GitHub Actions: `ONEX Validators` job in `.github/workflows/test.yml`
- Python tests: `tests/ci/test_architecture_compliance.py`

**Known Issues Tracking:**
Known violations are tracked internally and use pytest.mark.xfail markers. See
`scripts/validate.py` for the KNOWN_ISSUES registry.

**Validation Limitations:**
The regex-based validators cannot detect inline imports inside functions. For
comprehensive AST-based analysis, use the Python tests directly:
```bash
pytest tests/ci/test_architecture_compliance.py -v
```

## See Also

- `PolicyRegistry` class docstring for inline documentation
- `ProtocolPolicy` for interface requirements
- `ModelPolicyRegistration` for registration model validation
