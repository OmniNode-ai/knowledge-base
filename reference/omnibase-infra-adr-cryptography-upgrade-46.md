---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Cryptography Library Upgrade to v46.0.3"
topics: [omnibase-infra, adr, cryptography, upgrade]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-cryptography-upgrade-46.md on 2026-09-02. -->

# ADR: Cryptography Library Upgrade to v46.0.3

**Status**: Accepted
**Date**: 2026-01-06
**Priority**: Security Update

## Context

The `omnibase_infra` package uses the `cryptography` library for secure operations including TLS/SSL handling, certificate validation, and cryptographic primitives used by infrastructure adapters (Vault, Consul, PostgreSQL with SSL).

The previous version constraint was not explicitly documented. This upgrade pins to `cryptography ^46.0.3`.

### Why This Upgrade

1. **Security Patches**: The cryptography library is a critical security dependency. Version 46.x includes fixes for vulnerabilities discovered in earlier versions.

2. **Python 3.12 Compatibility**: Full compatibility with Python 3.12, which is the minimum Python version for this package.

3. **Dependency Chain Requirements**: Several dependencies in the ONEX ecosystem (including `hvac` for Vault integration, `aiohttp`, and OpenTelemetry exporters) benefit from updated cryptography primitives.

4. **OpenSSL 3.x Support**: Version 46.x has improved support for OpenSSL 3.x backends, which is the default on modern Linux distributions.

## Decision

Upgrade to `cryptography ^46.0.3` as specified in `pyproject.toml` (System utilities section).

### API Compatibility Assessment

The cryptography library maintains strong backwards compatibility guarantees. Version 46.x is compatible with code written for v45.x and earlier for all public APIs:

| API Surface | Compatibility | Notes |
|------------|---------------|-------|
| `hazmat.primitives` | Stable | Symmetric/asymmetric encryption unchanged |
| `hazmat.backends` | Stable | OpenSSL backend compatible |
| `x509` certificates | Stable | Certificate handling unchanged |
| FIPS mode | N/A | Not used by omnibase_infra |

### APIs Used by omnibase_infra

The package uses cryptography indirectly through:

- **hvac (Vault client)**: TLS connections to Vault
- **aiohttp**: HTTPS connections
- **asyncpg**: SSL connections to PostgreSQL
- **OpenTelemetry exporters**: OTLP over TLS

No direct `cryptography` imports exist in the codebase; the library is a transitive dependency requirement.

## Consequences

### Positive

- Improved security posture with latest vulnerability patches
- Better performance on modern systems (optimized for OpenSSL 3.x)
- Maintains compatibility with all existing functionality
- No code changes required

### Negative

- Slightly larger binary wheel (Rust compilation artifacts)
- Build time increase for source installations (minimal impact - wheels available)

### Migration

**Breaking Changes**: None

All existing code continues to work without modification.

## Alternatives Considered

### 1. Stay on older version
**Rejected**: Security risk from known vulnerabilities in older versions.

### 2. Remove cryptography as direct dependency
**Rejected**: Explicit version pinning ensures consistent behavior across installations and prevents dependency resolution from selecting incompatible versions.

## References

- [cryptography changelog](https://cryptography.io/en/latest/changelog/)
- [Python Cryptographic Authority](https://github.com/pyca/cryptography)
- Related: `pyproject.toml` dependency security guidance (ONEX Internal Dependencies and External Dependency Security Guidance sections)
