---
type: guide
status: current
date: "2026-09-02"
title: "Handler Integration Tests"
topics: [omnibase-infra, handler, integration, tests]
refs: []
---

<!-- Migrated from omnibase_infra:tests/integration/handlers/README.md on 2026-09-02. -->

# Handler Integration Tests

Integration tests for ONEX infrastructure handlers (Database, Consul, Vault, HTTP).

## Overview

This directory contains integration tests that validate handler behavior against real
infrastructure services. The tests ensure that handlers correctly:

- Connect to and communicate with infrastructure services
- Handle operations (CRUD, health checks, service registration)
- Report errors and handle edge cases gracefully
- Manage connection lifecycle (initialize, execute, shutdown)

### Test Suites

| Handler | Test File | Description |
|---------|-----------|-------------|
| **HandlerDb** | `test_db_handler_integration.py` | PostgreSQL operations (query, execute, DDL) |
| **HandlerConsul** | `test_consul_handler_integration.py` | Service discovery, KV store operations |
| **HandlerVault** | `test_vault_handler_integration.py` | Secret management (read/write/delete/list) |
| **HttpRestHandler** | `test_http_handler_integration.py` | HTTP client operations (uses local mock server) |

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** for dependency management
- **Access to remote infrastructure** (for DB, Consul, Vault tests) - see `tests/infrastructure_config.py`
- **pytest-httpserver** (installed via uv, for HTTP tests only)

### Infrastructure Services

The following services must be available for full test coverage:

| Service | Environment Variable | Default Port | Required For |
|---------|---------------------|--------------|--------------|
| PostgreSQL | `POSTGRES_HOST` | 5432 | HandlerDb tests |
| Consul | `CONSUL_HOST` | 8500 | HandlerConsul tests |
| Vault | `VAULT_ADDR` | 8200 | HandlerVault tests |

The default infrastructure server IP is defined in `tests/infrastructure_config.py`.
You can override it by setting the `REMOTE_INFRA_HOST` environment variable.

**Note**: HTTP handler tests use `pytest-httpserver` to create a local mock server and do
not require external infrastructure.

## Environment Setup

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Configure the required environment variables in `.env`:

### Remote Infrastructure Host (Optional)

```bash
# Override the default infrastructure server hostname (see tests/infrastructure_config.py)
# Default is localhost; set to your infrastructure server IP for remote testing
REMOTE_INFRA_HOST=localhost  # or your-server-ip for remote infrastructure
```

### PostgreSQL (HandlerDb)

```bash
# Preferred: full DSN (overrides all individual vars)
OMNIBASE_INFRA_DB_URL=postgresql://postgres:your_secure_password@${REMOTE_INFRA_HOST}:5432/omnibase_infra

# Fallback: individual vars (used only if OMNIBASE_INFRA_DB_URL is not set)
POSTGRES_HOST=${REMOTE_INFRA_HOST}  # or localhost, or specific IP
POSTGRES_PASSWORD=your_secure_password

# Optional (defaults shown)
POSTGRES_PORT=5432
POSTGRES_USER=postgres
```

### Consul (HandlerConsul)

```bash
# Required
CONSUL_HOST=${REMOTE_INFRA_HOST}  # or localhost, or specific IP

# Optional (defaults shown)
CONSUL_PORT=8500
CONSUL_SCHEME=http
CONSUL_TOKEN=  # Only if ACLs are enabled
```

### Vault (HandlerVault)

```bash
# Required
VAULT_ADDR=http://${REMOTE_INFRA_HOST}:8200  # or http://localhost:8200
VAULT_TOKEN=your_vault_token

# Optional
VAULT_NAMESPACE=  # For Vault Enterprise
```

## Running Tests

### Run All Handler Integration Tests

```bash
uv run pytest tests/integration/handlers/ -v
```

### Run Specific Handler Tests

```bash
# Database handler tests
uv run pytest tests/integration/handlers/test_db_handler_integration.py -v

# Consul handler tests
uv run pytest tests/integration/handlers/test_consul_handler_integration.py -v

# Vault handler tests
uv run pytest tests/integration/handlers/test_vault_handler_integration.py -v

# HTTP handler tests (no external infrastructure needed)
uv run pytest tests/integration/handlers/test_http_handler_integration.py -v
```

### Run with Markers

```bash
# Run only integration tests
uv run pytest -m integration tests/integration/handlers/ -v

# Run integration tests with verbose output
uv run pytest tests/integration/handlers/ -v --tb=short
```

## CI/CD Behavior

Tests are designed to **skip gracefully** when infrastructure is unavailable:

| Condition | Behavior |
|-----------|----------|
| `POSTGRES_PASSWORD` not set | DB tests skipped with message |
| PostgreSQL unreachable | DB tests skipped with message |
| `VAULT_TOKEN` not set | Vault tests skipped with message |
| Vault server unreachable | Vault tests skipped with message |
| `CONSUL_HOST` not set | Consul tests skipped with message |
| Consul server unreachable | Consul tests skipped with message |

**No test failures occur** when infrastructure is unavailable. This allows CI/CD pipelines
to run without requiring access to the remote infrastructure server.

Example skip output:

```
SKIPPED [1] tests/integration/handlers/test_db_handler_integration.py:47:
    PostgreSQL not available (POSTGRES_PASSWORD not set)
SKIPPED [1] tests/integration/handlers/test_vault_handler_integration.py:47:
    Vault not available (VAULT_TOKEN not set)
SKIPPED [1] tests/integration/handlers/test_consul_handler_integration.py:43:
    Consul not available (cannot connect to remote infrastructure)
```

## Infrastructure Notes

### Remote Infrastructure Server

The ONEX development/staging infrastructure server hosts:

- **PostgreSQL** on port 5436 (external) / 5432 (internal)
- **Consul** on port 28500
- **Vault** on port 8200
- **Redpanda (Kafka)** on port 19092

The default server IP is configured in `tests/infrastructure_config.py`. To override:

```bash
export REMOTE_INFRA_HOST=your-server-ip
```

See the root `CLAUDE.md` for complete infrastructure topology documentation.

### Local Development Alternative

For local development without access to the remote server, you can run equivalent
services via Docker:

```bash
# PostgreSQL
docker run -d --name postgres-local \
    -e POSTGRES_PASSWORD=testpass \
    -p 5432:5432 \
    postgres:15

# Consul
docker run -d --name consul-local \
    -p 8500:8500 \
    consul:1.15

# Vault (dev mode)
docker run -d --name vault-local \
    -e VAULT_DEV_ROOT_TOKEN_ID=root \
    -p 8200:8200 \
    vault:1.15 server -dev
```

Then update your `.env` to point to `localhost` with appropriate ports.

## Test Cleanup

All fixtures use **idempotent cleanup patterns**:

- **Database tests**: Tables created during tests are dropped in `finally` blocks
- **Vault tests**: Secrets are deleted after each test via cleanup fixtures
- **Consul tests**: KV entries and service registrations are cleaned up automatically
- **UUID-based isolation**: Test resources use unique identifiers to prevent conflicts

### Cleanup Guarantees

1. Cleanup occurs in `finally` blocks regardless of test outcome
2. Cleanup errors are silently ignored (test resources may not exist)
3. Tests are isolated and do not interfere with each other
4. Parallel test execution is supported via unique resource names

### Example Cleanup Pattern

```python
@pytest.fixture
async def cleanup_table(initialized_db_handler):
    """Track and cleanup test tables."""
    tables_to_cleanup: list[str] = []

    yield tables_to_cleanup

    # Cleanup: drop all tracked tables
    for table in tables_to_cleanup:
        try:
            await initialized_db_handler.execute({
                "operation": "db.execute",
                "payload": {"sql": f'DROP TABLE IF EXISTS "{table}"', "parameters": []},
            })
        except Exception:
            pass  # Ignore cleanup errors
```

## Troubleshooting

### Tests Skipped Unexpectedly

1. Verify `.env` file exists and contains required variables
2. Source the environment: `source .env`
3. Check connectivity: `ping $REMOTE_INFRA_HOST` (or your infrastructure server IP)
4. Test service directly:
   ```bash
   # PostgreSQL
   psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -c "SELECT 1"

   # Consul
   curl http://$CONSUL_HOST:$CONSUL_PORT/v1/status/leader

   # Vault
   curl $VAULT_ADDR/v1/sys/health
   ```

### Connection Timeouts

- Default timeout is 30 seconds for all handlers
- Check network connectivity to your infrastructure server
- Verify no firewall blocking the ports

### Authentication Errors

- **PostgreSQL**: Verify `POSTGRES_PASSWORD` matches the database configuration
- **Vault**: Ensure `VAULT_TOKEN` has appropriate permissions
- **Consul**: If ACLs are enabled, set `CONSUL_TOKEN`

## Related Documentation

- `conftest.py` - Fixture definitions and environment configuration
- `../../infrastructure_config.py` - Central infrastructure configuration and REMOTE_INFRA_HOST
- `../../.env.example` - Complete environment variable reference
- `../../../CLAUDE.md` - Infrastructure topology and service details
- `../../../docs/patterns/error_handling_patterns.md` - Error handling conventions
