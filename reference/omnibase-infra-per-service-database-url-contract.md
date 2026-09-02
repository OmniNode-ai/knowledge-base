---
type: reference
status: current
date: "2026-09-02"
title: "Per-Service Database URL Contract"
topics: [omnibase-infra, per, service, database]
refs: []
---

<!-- Migrated from omnibase_infra:docs/patterns/db_url_contract.md on 2026-09-02. -->

# Per-Service Database URL Contract

## Overview

Each OmniNode service owns its own PostgreSQL database and connects via a
dedicated role. The canonical connection method is a single `*_DB_URL`
environment variable containing a full PostgreSQL DSN.

## The Contract

| Environment Variable | Database | Role |
|---|---|---|
| `OMNIBASE_INFRA_DB_URL` | `omnibase_infra` | `role_omnibase_infra` |
| `OMNIINTELLIGENCE_DB_URL` | `omniintelligence` | `role_omniintelligence` |
| `OMNICLAUDE_DB_URL` | `omniclaude` | `role_omniclaude` |
| `OMNIMEMORY_DB_URL` | `omnimemory` | `role_omnimemory` |
| `OMNINODE_CLOUD_DB_URL` | `omninode_cloud` | `role_omninode_cloud` |
| `OMNIDASH_ANALYTICS_DB_URL` | `omnidash_analytics` | `role_omnidash` |

### URL Format

```
postgresql://<role>:<password>@<host>:<port>/<database>
```

Example:

```bash
OMNIBASE_INFRA_DB_URL=postgresql://role_omnibase_infra:<contact-address>:5432/omnibase_infra
```

## Resolution Order

`ModelPostgresPoolConfig.from_env(db_url_var=...)` reads a single `*_DB_URL`
environment variable. The `db_url_var` parameter defaults to
`"OMNIBASE_INFRA_DB_URL"` but each service passes its own variable name:

1. **Read `db_url_var`** - Full DSN (required). Host, port, user,
   password, and database are parsed from the URL.
2. **Error** - If the variable is not set, a `ValueError` is raised
   with a clear message. There is no silent fallback.

Pool sizing is optionally controlled by `POSTGRES_POOL_MIN_SIZE` (default 2)
and `POSTGRES_POOL_MAX_SIZE` (default 10).

> **Note**: The test helper `PostgresConfig.from_env()` (in
> `tests/helpers/util_postgres.py`) additionally falls back to individual
> `POSTGRES_*` variables (`POSTGRES_HOST`, `POSTGRES_PORT`, etc.) for
> convenience in local development. The production `from_env()` does not.

## Fail-Fast Behavior

The implicit `omninode_bridge` default has been removed. Code that previously
connected to the shared `omninode_bridge` database by default now raises an
error unless explicitly configured.

The conceptual change is:

```python
# Before
database = os.getenv("POSTGRES_DATABASE", "omninode_bridge")  # silent coupling

# After — production code requires OMNIBASE_INFRA_DB_URL with no
# fallback.  The test helper (PostgresConfig.from_env) additionally falls
# back to individual POSTGRES_* variables for local convenience.
db_url = os.getenv("OMNIBASE_INFRA_DB_URL")
if not db_url:
    raise ValueError("Set OMNIBASE_INFRA_DB_URL")
```

## Migration from `omninode_bridge`

### For `.env` files

```bash
# Old
POSTGRES_DATABASE=omninode_bridge

# New (preferred)
OMNIBASE_INFRA_DB_URL=postgresql://role_omnibase_infra:<pw>@<host>:5432/omnibase_infra

# New (legacy individual vars)
POSTGRES_DATABASE=omnibase_infra
```

### For Docker Compose

Docker Compose files use the standard PostgreSQL image variable `POSTGRES_DB`
(not `POSTGRES_DATABASE`). Defaults have been updated from `omninode_bridge`
to `omnibase_infra`:

```yaml
# docker-compose.infra.yml / docker-compose.e2e.yml
POSTGRES_DB: omnibase_infra
```

### For Tests

The shared test helper `PostgresConfig.from_env()` checks
`OMNIBASE_INFRA_DB_URL` first, then falls back to individual `POSTGRES_*`
variables. Some test conftest files (e.g., injection_effectiveness) build
DSNs directly from individual `POSTGRES_*` variables with a default
database of `omnibase_infra`. All tests skip gracefully when no database
is configured.
