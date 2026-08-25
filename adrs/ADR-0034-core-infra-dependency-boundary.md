---
type: adr
status: accepted
date: "2025-12-26"
title: "ADR-0034: Core-Infra Dependency Boundary"
adr_id: ADR-0034
topics: [omnibase_core, dependency-inversion, architecture-boundary, ci-enforcement]
refs: [adrs/ADR-0030-protocol-based-di-architecture.md]
supersedes: []
superseded_by: []
---

# ADR-0034: Core-Infra Dependency Boundary

**Status**: Implemented
**Date**: 2025-12-26
**Related**: [ADR-0030](ADR-0030-protocol-based-di-architecture.md) — Protocol-Based DI Architecture
**Source**: omnibase_core `docs/decisions/ADR-005-core-infra-dependency-boundary.md`

---

## Purpose

Documents the architectural boundary between `omnibase_core` (abstractions) and
`omnibase_infra` (implementations), specifically regarding external I/O dependencies such
as HTTP clients, message brokers, and database drivers.

## Executive Summary

`omnibase_core` is the foundational abstraction layer of the ONEX framework. It MUST contain
only protocol definitions (interfaces), domain models (Pydantic BaseModel subclasses), pure
computation logic (no side effects), and base node implementations using injected services.

Direct dependencies on transport/I/O libraries (`aiohttp`, `httpx`, `kafka`, `redis`,
`asyncpg`, etc.) are **FORBIDDEN** in omnibase_core. These libraries belong in
`omnibase_infra`, which provides concrete implementations of core protocols.

**Decision**: Remove `aiohttp` and all similar transport libraries from omnibase_core,
enforce via CI validation.

## Background

### ONEX Layering Model

```text
Service Layer (Applications, APIs, Workers)
        │
        v
omnibase_infra   — concrete implementations, transport integrations, Kafka/Postgres adapters
        │
        v
omnibase_spi     — service provider interface; depends on Core, not the reverse
        │
        v
omnibase_core    — abstractions: protocol definitions, domain models, base nodes; NO
                    transport/infrastructure dependencies
```

Dependencies flow **downward only**: Services → Infra → SPI → Core. Core has no upward and
no sibling transport-library dependencies.

`aiohttp` was listed in `pyproject.toml` as a direct dependency of omnibase_core prior to
this decision, violating the boundary even though it was not imported at module level in
most files. The fix commit removed the dependency and updated protocol documentation to
clarify where implementations belong.

## Decision

### Forbidden Dependencies in Core

| Category | Forbidden Libraries | Protocol Alternative |
|----------|--------------------|--------------------|
| HTTP Clients | `aiohttp`, `httpx`, `requests` | `ProtocolHttpClient` |
| Message Queues | `kafka`, `aiokafka` | `ProtocolEventBus` |
| Databases | `asyncpg`, `psycopg`, `psycopg2` | `ProtocolRepository` |
| Caches | `redis`, `valkey` | `ProtocolCache` |
| Secret Stores | `hvac` | `ProtocolSecretStore` |
| Service Discovery | `consul` | `ProtocolServiceDiscovery` |

### Allowed Patterns

1. **`TYPE_CHECKING` imports** — type-only imports create no runtime dependency and are allowed.
2. **Protocol definitions** — protocols that abstract a transport are the point of the exercise.
3. **Documentation examples in docstrings** — illustrative adapter code in a docstring, clearly
   labeled as belonging in `omnibase_infra`, is allowed.

### Correct vs Incorrect

**INCORRECT (in omnibase_core)** — direct transport import at module scope:
```python
import aiohttp

class HealthCheckMixin:
    async def check_health(self, url: str) -> bool:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return response.status == 200
```

**CORRECT (in omnibase_core)** — protocol-based injection:
```python
from omnibase_core.protocols.http import ProtocolHttpClient

class HealthCheckMixin:
    def __init__(self, http_client: ProtocolHttpClient):
        self._http_client = http_client

    async def check_health(self, url: str) -> bool:
        response = await self._http_client.get(url, timeout=5.0)
        return response.status == 200
```

**CORRECT (in omnibase_infra)** — the concrete adapter implementing the protocol lives here.

## Enforcement

**2026-08-25 migration note — enforcement has moved since this decision was written.** The
decision as originally authored named a single grep-based shell script
(`scripts/validate-no-transport-imports.sh`) as both the CI check and the pre-commit hook,
wired into a workflow file named `.github/workflows/test.yml`. Verified live against
omnibase_core@dev:

- The workflow file was renamed `.github/workflows/ci.yml` (the `test.yml` name is stale).
- The **CI** enforcement step ("Check for transport import violations") now runs
  `scripts/check_transport_imports.py` — an AST-based scanner, not the original grep-based
  `.sh` script.
- The **pre-commit** hook (`validate-no-transport-imports`) now runs
  `scripts/validate_no_transport_imports.py` — also AST-based; its own module docstring
  states it is "Unlike the grep-based predecessor" and correctly detects imports inside
  `TYPE_CHECKING` blocks (a documented limitation of the original grep-based script, which
  could not see multi-line `TYPE_CHECKING` blocks).
- The original `scripts/validate-no-transport-imports.sh` still exists in the tree and is
  still referenced from at least one other workflow (`omni-standards-compliance.yml`), so it
  is not fully retired — but it is no longer the primary enforcement path this decision
  describes for CI and pre-commit.

The forbidden-imports catalog and the exclusion rules described in this decision (HTTP
clients, Kafka clients, Redis clients, database clients, message queues, gRPC, WebSocket;
file-level and line-level exclusions) were not individually re-verified line-by-line against
the current AST-based scripts during this migration — the underlying policy (no transport/IO
in core) remains current and is independently corroborated by
[ADR-0030](ADR-0030-protocol-based-di-architecture.md) and by the omnibase_core CLAUDE.md's
own layering rule.

### Exit Codes (as originally documented)

| Code | Meaning |
|------|---------|
| 0 | No violations found |
| 1 | Transport import violations detected (blocks PR) |

## Trade-offs

- **Indirection Overhead**: code goes through protocols rather than direct library calls; mitigated by container-based DI.
- **Developer Learning Curve**: standard clean-architecture investment.
- **Split Implementation Locations**: protocol in core, implementation in infra — two places to look, but a clear separation of concerns.

### Benefits Realized

Testability without I/O mocks, HTTP-library swappability without core changes, minimal core
dependency footprint, unambiguous layer responsibilities.

---

## References

- [ADR-0030](ADR-0030-protocol-based-di-architecture.md): Protocol-Based Dependency Injection Architecture
- [SOLID — Dependency Inversion Principle](https://en.wikipedia.org/wiki/Dependency_inversion_principle)
- [PEP 544 — Structural Subtyping (Protocols)](https://peps.python.org/pep-0544/)

---

## Changelog

| Date | Changes |
|------|---------|
| 2026-08-25 | Migrated to knowledge base. Corrected the CI-workflow filename (`test.yml` → `ci.yml`) and the enforcement scripts (documented `.sh` scripts have been superseded by AST-based `check_transport_imports.py` / `validate_no_transport_imports.py`) — all verified live against omnibase_core@dev. Did not re-verify the full forbidden-library catalog line-by-line. |
| 2025-12-26 | Initial decision documenting core-infra boundary and aiohttp removal |
