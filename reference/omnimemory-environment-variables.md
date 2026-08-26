---
type: reference
status: current
date: "2026-08-26"
title: "OmniMemory Environment Variables"
topics:
  - omnimemory
  - configuration
  - environment-variables
  - pydantic-settings
refs:
  - reference/omnimemory-runtime-plugins.md
  - reference/omnimemory-memory-data-ownership.md
---

> **Last verified:** 2026-08-26 — migrated from the `omnimemory` repository. Triage verdict `CORRECT_THEN_MIGRATE`, verified field-by-field against `src/omnimemory/settings.py`: the field names, types, defaults and constraints for `MemoryServiceSettings`, `PostgresSettings`, `QdrantSettings` and the single-underscore `OMNIMEMORY_DB_URL` exception all matched the source. **One correction was applied on migration:** `OMNIMEMORY__QDRANT__URL` was documented with a default of `http://localhost:6333`; the live field is declared with no default and is therefore required whenever `qdrant_enabled` is true. The same stale default is also asserted in the settings module's own docstring, so the error was not unique to this document.

# OmniMemory Environment Variables

This document describes all environment variables used to configure OmniMemory.

## Overview

OmniMemory uses [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) for configuration management. All environment variables use the `OMNIMEMORY__` prefix with `__` as the nested delimiter, **except** `OMNIMEMORY_DB_URL` which uses a single underscore and is read as a top-level variable via a `validation_alias` in pydantic-settings (not as a nested `OMNIMEMORY__POSTGRES__` variable).

**Example**: `OMNIMEMORY__FILESYSTEM__BASE_PATH=/data/memory`

## Configuration Hierarchy

```
MemoryServiceSettings (top-level)
|-- postgres_enabled (bool)
|-- qdrant_enabled (bool)
|-- service_name (str)
|-- enable_metrics (bool)
|-- enable_logging (bool)
|-- debug_mode (bool)
|
|-- filesystem (required)
|   |-- base_path (required)
|   |-- max_file_size_bytes
|   |-- allowed_extensions
|   |-- create_if_missing
|   |-- enable_compression
|   +-- buffer_size_bytes
|
|-- postgres (optional, requires postgres_enabled=true)
|   |-- OMNIMEMORY_DB_URL (required if enabled, top-level env var)
|   |-- pool_size
|   |-- pool_timeout_seconds
|   |-- pool_recycle_seconds
|   |-- statement_timeout_seconds
|   |-- lock_timeout_seconds
|   |-- ssl_mode
|   +-- schema_name
|
|-- qdrant (optional, requires qdrant_enabled=true)
|   |-- url
|   |-- api_key
|   |-- collection_name
|   |-- vector_size
|   |-- timeout_seconds
|   |-- grpc_port
|   |-- prefer_grpc
|   |-- default_limit
|   |-- score_threshold
|   |-- distance_metric
|   +-- on_disk
|
+-- embedding (optional, requires embedding_enabled=true)
    |-- server_url (REQUIRED - no default)
    |-- timeout_seconds
    |-- max_retries
    +-- dimension
```

## Archive Handler Configuration

Variables used by `HandlerMemoryArchive` for cold-storage archival.

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `OMNIMEMORY_ARCHIVE_PATH` | Path | `{tempdir}/omnimemory/archives` | Must be writable | Base directory for archive files. Overridden by the `archive_base_path` constructor argument. |
| `OMNIMEMORY_ARCHIVE_COMPRESSION_LEVEL` | int | `6` | 1–9 | Gzip compression level for `.jsonl.gz` archive files. Level 1 is fastest (lowest ratio); level 9 is slowest (highest ratio). Level 6 is the balanced default. Overridden by the `compression_level` constructor argument. |

> **Note — naming exception**: These variables use a single underscore (`OMNIMEMORY_ARCHIVE_*`) because they are read directly by `os.environ.get()` inside the handler, not via pydantic-settings. They do **not** use the `OMNIMEMORY__` double-underscore prefix.

## Required Variables (Phase 1 Minimal)

These variables MUST be set for OmniMemory to start:

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `OMNIMEMORY__FILESYSTEM__BASE_PATH` | Path | Base directory for memory file storage (must be absolute) | `/data/omnimemory` |

## Service-Level Configuration

Top-level settings that control service behavior.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OMNIMEMORY_ENABLED` | bool | unset (disabled) | Activate the OmniMemory plugin in the ONEX kernel. When set to `true`, the `PluginMemory` domain plugin initializes and subscribes to Kafka topics. When unset or `false`, the plugin is skipped entirely, allowing graceful degradation in kernels that do not require the memory domain. Expected values: `true` or `false`. See also: [OmniMemory Runtime Plugin System](omnimemory-runtime-plugins.md). |
| `OMNIMEMORY__POSTGRES_ENABLED` | bool | `false` | Enable PostgreSQL backend |
| `OMNIMEMORY__QDRANT_ENABLED` | bool | `false` | Enable Qdrant vector backend |
| `OMNIMEMORY__EMBEDDING_ENABLED` | bool | `false` | Enable real embedding server (requires `EMBEDDING__SERVER_URL`) |
| `OMNIMEMORY__SERVICE_NAME` | str | `omnimemory` | Name of the memory service instance |
| `OMNIMEMORY__ENABLE_METRICS` | bool | `true` | Enable performance metrics collection |
| `OMNIMEMORY__ENABLE_LOGGING` | bool | `true` | Enable operation logging |
| `OMNIMEMORY__DEBUG_MODE` | bool | `false` | Enable debug mode for verbose output |

## Filesystem Configuration

Filesystem backend is **required** for Phase 1. All memory operations use filesystem storage as the foundation.

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `OMNIMEMORY__FILESYSTEM__BASE_PATH` | Path | **required** | Must be absolute | Base directory for memory storage |
| `OMNIMEMORY__FILESYSTEM__MAX_FILE_SIZE_BYTES` | int | `10485760` (10MB) | 1 - 1073741824 (1GB) | Maximum file size in bytes |
| `OMNIMEMORY__FILESYSTEM__ALLOWED_EXTENSIONS` | list | `[".json", ".txt", ".md"]` | JSON array format | Allowed file extensions (e.g., `'[".json", ".txt"]'`) |
| `OMNIMEMORY__FILESYSTEM__CREATE_IF_MISSING` | bool | `true` | - | Create base_path if it doesn't exist |
| `OMNIMEMORY__FILESYSTEM__ENABLE_COMPRESSION` | bool | `false` | - | Enable gzip compression for stored files |
| `OMNIMEMORY__FILESYSTEM__BUFFER_SIZE_BYTES` | int | `65536` (64KB) | 4096 - 1048576 (1MB) | I/O buffer size in bytes |

## PostgreSQL Configuration (Optional)

Set `OMNIMEMORY__POSTGRES_ENABLED=true` to enable PostgreSQL backend for persistent memory storage.

**Connection URL** (required when enabled):

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `OMNIMEMORY_DB_URL` | str | **required if enabled** | Valid PostgreSQL URL | Full PostgreSQL connection URL with credentials |

> **Important — naming convention exception**: While all other OmniMemory variables use the `OMNIMEMORY__` prefix with `__` as the nested delimiter (see [Overview](#overview)), `OMNIMEMORY_DB_URL` is the **one exception**: it uses a **single underscore** between `OMNIMEMORY` and `DB`. It is read as a top-level environment variable via a `validation_alias` in pydantic-settings, not as a nested `OMNIMEMORY__POSTGRES__` variable. Setting `OMNIMEMORY__POSTGRES__DB_URL` will have no effect.

The service fails fast on startup if `OMNIMEMORY_DB_URL` is not set when postgres is enabled. No silent fallback to shared databases.

**URL Format**:

```
postgresql://user:password@host:port/database
```

When using the `asyncpg` driver (used internally for health checks and lifecycle handlers), the `postgresql+asyncpg://` scheme is a SQLAlchemy dialect specifier and is **not** accepted directly by `asyncpg.connect()`. OmniMemory normalizes the URL before passing it to asyncpg, stripping the `+asyncpg` suffix so that asyncpg receives the standard `postgresql://` form it expects. The standard `postgresql://` scheme is sufficient and preferred for the pydantic-settings `PostgresDsn` field.

**Examples**:

```bash
# Local development
OMNIMEMORY_DB_URL=postgresql://omnimemory:dev_password@localhost:5432/omnimemory_dev

# Remote shared infrastructure (OmniNode standard)
OMNIMEMORY_DB_URL=postgresql://postgres:secret@<db-host>:<db-port>/omnimemory
```

> **Breaking change (0.2.0 → 0.3.0)**: The database connection URL is now read **exclusively** from `OMNIMEMORY_DB_URL`. Any previous mechanism for supplying the database URL no longer applies. Update your `.env` file to include this variable before upgrading.

**Tuning variables** (prefix: `OMNIMEMORY__POSTGRES__`):

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `OMNIMEMORY__POSTGRES__POOL_SIZE` | int | `5` | 1 - 50 | Connection pool size |
| `OMNIMEMORY__POSTGRES__POOL_TIMEOUT_SECONDS` | int | `30` | 1 - 300 | Pool connection acquisition timeout |
| `OMNIMEMORY__POSTGRES__POOL_RECYCLE_SECONDS` | int | `3600` | 60 - 86400 | Connection recycle time in seconds |
| `OMNIMEMORY__POSTGRES__STATEMENT_TIMEOUT_SECONDS` | int | `30` | 1 - 300 | Maximum query execution time |
| `OMNIMEMORY__POSTGRES__LOCK_TIMEOUT_SECONDS` | int | `10` | 1 - 60 | Maximum time to wait for locks |
| `OMNIMEMORY__POSTGRES__SSL_MODE` | str | `prefer` | Valid SSL mode | SSL mode (disable, allow, prefer, require, verify-ca, verify-full) |
| `OMNIMEMORY__POSTGRES__SCHEMA_NAME` | str | `omnimemory` | - | PostgreSQL schema name for memory tables |

## Qdrant Configuration (Optional)

Set `OMNIMEMORY__QDRANT_ENABLED=true` to enable Qdrant vector backend for semantic memory storage.

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `OMNIMEMORY__QDRANT__URL` | HttpUrl | **REQUIRED, no default** | Valid HTTP(S) URL | Qdrant server URL. Declared `url: HttpUrl = Field(...)` — there is no fallback, so enabling Qdrant without setting this raises a validation error at startup. |
| `OMNIMEMORY__QDRANT__API_KEY` | SecretStr | `None` | - | Qdrant API key (optional) |
| `OMNIMEMORY__QDRANT__COLLECTION_NAME` | str | `omnimemory` | - | Default collection name for memory vectors |
| `OMNIMEMORY__QDRANT__VECTOR_SIZE` | int | `1024` | 1 - 65536 | Vector embedding dimensions |
| `OMNIMEMORY__QDRANT__TIMEOUT_SECONDS` | int | `30` | 1 - 300 | Request timeout in seconds |
| `OMNIMEMORY__QDRANT__GRPC_PORT` | int | `None` | 1 - 65535 | gRPC port for high-performance operations |
| `OMNIMEMORY__QDRANT__PREFER_GRPC` | bool | `false` | - | Prefer gRPC over HTTP for operations |
| `OMNIMEMORY__QDRANT__DEFAULT_LIMIT` | int | `10` | 1 - 1000 | Default number of results to return |
| `OMNIMEMORY__QDRANT__SCORE_THRESHOLD` | float | `0.7` | 0.0 - 1.0 | Minimum similarity score threshold |
| `OMNIMEMORY__QDRANT__DISTANCE_METRIC` | str | `Cosine` | Cosine, Euclid, Dot | Distance metric for vector similarity |
| `OMNIMEMORY__QDRANT__ON_DISK` | bool | `false` | - | Store vectors on disk instead of RAM |

## Embedding Configuration (Optional)

Set `OMNIMEMORY__EMBEDDING_ENABLED=true` to enable the real embedding server for semantic search operations. This is used by the memory retrieval handlers when `use_real_embeddings=True`.

**IMPORTANT**: The `SERVER_URL` has NO default value and MUST be provided explicitly. This prevents accidental use of wrong/hardcoded URLs.

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `OMNIMEMORY__EMBEDDING__SERVER_URL` | str | **REQUIRED** | Valid HTTP(S) URL | URL of the embedding server (set from `LLM_EMBEDDING_URL` in `.env`) |
| `OMNIMEMORY__EMBEDDING__TIMEOUT_SECONDS` | float | `5.0` | > 0 | Request timeout in seconds |
| `OMNIMEMORY__EMBEDDING__MAX_RETRIES` | int | `3` | 0 - 10 | Maximum retry attempts for transient failures |
| `OMNIMEMORY__EMBEDDING__DIMENSION` | int | `1024` | > 0 | Expected embedding vector dimension |

**Example**:
```bash
# Enable real embeddings with explicit server URL.
# Set LLM_EMBEDDING_URL to the URL of your embedding server.
export OMNIMEMORY__EMBEDDING_ENABLED=true
export OMNIMEMORY__EMBEDDING__SERVER_URL=${LLM_EMBEDDING_URL:-http://localhost:8100}
```

**Note**: When using `ModelHandlerQdrantMockConfig` with `use_real_embeddings=True`, the `embedding_server_url` must be provided explicitly (typically loaded from this environment variable). The handler will fail fast with a clear error if the URL is missing or invalid.

## Example Configurations

### Minimal (Phase 1 Local Development)

```bash
# .env.local
OMNIMEMORY__FILESYSTEM__BASE_PATH=/tmp/omnimemory
```

### Development with All Backends

```bash
# .env.development
OMNIMEMORY__FILESYSTEM__BASE_PATH=/data/omnimemory
OMNIMEMORY__FILESYSTEM__CREATE_IF_MISSING=true
OMNIMEMORY__FILESYSTEM__ENABLE_COMPRESSION=false

# Service settings
OMNIMEMORY__SERVICE_NAME=omnimemory-dev
OMNIMEMORY__DEBUG_MODE=true

# PostgreSQL
OMNIMEMORY__POSTGRES_ENABLED=true
OMNIMEMORY_DB_URL=postgresql://omnimemory:dev_password@localhost:5432/omnimemory_dev
OMNIMEMORY__POSTGRES__POOL_SIZE=3
OMNIMEMORY__POSTGRES__SCHEMA_NAME=omnimemory_dev

# Qdrant
OMNIMEMORY__QDRANT_ENABLED=true
OMNIMEMORY__QDRANT__URL=http://localhost:6333
OMNIMEMORY__QDRANT__COLLECTION_NAME=omnimemory_dev
OMNIMEMORY__QDRANT__VECTOR_SIZE=1024

# Embedding (for real semantic search - configure LLM_EMBEDDING_URL in .env)
OMNIMEMORY__EMBEDDING_ENABLED=true
OMNIMEMORY__EMBEDDING__SERVER_URL=<LLM_EMBEDDING_URL>
```

### Production

```bash
# .env.production
OMNIMEMORY__FILESYSTEM__BASE_PATH=/var/lib/omnimemory
OMNIMEMORY__FILESYSTEM__MAX_FILE_SIZE_BYTES=52428800  # 50MB
OMNIMEMORY__FILESYSTEM__CREATE_IF_MISSING=false
OMNIMEMORY__FILESYSTEM__ENABLE_COMPRESSION=true
OMNIMEMORY__FILESYSTEM__BUFFER_SIZE_BYTES=131072  # 128KB

# Service settings
OMNIMEMORY__SERVICE_NAME=omnimemory-prod
OMNIMEMORY__ENABLE_METRICS=true
OMNIMEMORY__ENABLE_LOGGING=true
OMNIMEMORY__DEBUG_MODE=false

# PostgreSQL (credentials via Vault in production - see Secrets Management)
OMNIMEMORY__POSTGRES_ENABLED=true
OMNIMEMORY_DB_URL=postgresql://omnimemory:<from-vault>@db.prod.internal:5432/omnimemory
OMNIMEMORY__POSTGRES__POOL_SIZE=20
OMNIMEMORY__POSTGRES__POOL_TIMEOUT_SECONDS=10
OMNIMEMORY__POSTGRES__POOL_RECYCLE_SECONDS=1800
OMNIMEMORY__POSTGRES__STATEMENT_TIMEOUT_SECONDS=60
OMNIMEMORY__POSTGRES__SSL_MODE=require
OMNIMEMORY__POSTGRES__SCHEMA_NAME=omnimemory

# Qdrant
OMNIMEMORY__QDRANT_ENABLED=true
OMNIMEMORY__QDRANT__URL=https://qdrant.prod.internal:6333
OMNIMEMORY__QDRANT__API_KEY=<from-vault>
OMNIMEMORY__QDRANT__COLLECTION_NAME=omnimemory_prod
OMNIMEMORY__QDRANT__VECTOR_SIZE=1024
OMNIMEMORY__QDRANT__TIMEOUT_SECONDS=60
OMNIMEMORY__QDRANT__PREFER_GRPC=true
OMNIMEMORY__QDRANT__GRPC_PORT=6334
OMNIMEMORY__QDRANT__ON_DISK=true
```

## Utilities

### `safe_db_url_display`

**Module**: `omnimemory.adapters.adapter_db_url` (re-exported from `omnimemory.adapters`)
**Import**: `from omnimemory.adapters import safe_db_url_display`

A helper that strips credentials from a PostgreSQL connection URL so the result is safe to include in log messages, error text, and diagnostic output.

**Signature**:

```python
def safe_db_url_display(url: str) -> str: ...
```

**What it does**:

- Parses the URL with `urllib.parse.urlparse` (no fragile string splitting)
- Validates that the URL scheme starts with `postgres` — returns `"(unparseable URL)"` for any other scheme (e.g. `https://`) to prevent misleading output
- Strips the username and password from the result entirely
- Wraps IPv6 host addresses in brackets to avoid ambiguous `host:port` output
- Returns a string in the form `host:port/database`

**When to use it**: Any time you need to log or display the value of `OMNIMEMORY_DB_URL` — whether in startup banners, health-check output, or error messages. Never log the raw URL; always pass it through `safe_db_url_display` first.

**Example**:

```python
from omnimemory.adapters import safe_db_url_display

url = "postgresql://omnimemory:super_secret@<db-host>:5436/omnimemory"
print(safe_db_url_display(url))
# Output: <db-host>:5436/omnimemory
```

**Edge cases**:

| Input | Output |
|-------|--------|
| `postgresql://user:pass@localhost:5432/mydb` | `localhost:5432/mydb` |
| `postgresql://user:pass@<db-host>:5436/omnimemory` | `<db-host>:5436/omnimemory` |
| `postgresql://user:pass@[::1]:5432/mydb` (IPv6) | `[::1]:5432/mydb` |
| `postgresql://host_only/mydb` (no port) | `host_only/mydb` |
| `https://not-a-db-url` (wrong scheme) | `(unparseable URL)` |
| Malformed / unparseable string | `(unparseable URL)` |

**Which env var it masks**: `OMNIMEMORY_DB_URL`. The full URL (including password) must never appear in logs; `safe_db_url_display` is the only approved way to surface connection target information.

## Type Reference

| Type | Description | Example |
|------|-------------|---------|
| `Path` | Filesystem path (must be absolute) | `/data/omnimemory` |
| `PostgresDsn` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `HttpUrl` | HTTP(S) URL | `http://localhost:6333` |
| `SecretStr` | Sensitive string (not logged) | Password, API key |
| `bool` | Boolean (`true`/`false`, `1`/`0`, `yes`/`no`) | `true` |
| `int` | Integer | `10485760` |
| `float` | Floating point number | `0.7` |
| `str` | String | `omnimemory` |
| `list` | JSON array format (see note below) | `[".json", ".txt"]` |

**Note on List Values**: List-type environment variables must use JSON array format. Comma-separated strings (e.g., `.json,.txt,.md`) are **not supported** by pydantic-settings by default.

```bash
# Correct - JSON array format
export OMNIMEMORY__FILESYSTEM__ALLOWED_EXTENSIONS='[".json", ".txt", ".md"]'

# Incorrect - comma-separated (will fail to parse as a list)
export OMNIMEMORY__FILESYSTEM__ALLOWED_EXTENSIONS=".json,.txt,.md"
```

> **Note**: Comma-separated value support could be added using a `@field_validator` with `mode='before'` to parse comma-separated strings. The current implementation uses the pydantic-settings v2 default behavior which expects JSON array format for list-type fields.

## Secrets Management

### Phase 1: Environment Variables

Database credentials are embedded in the `OMNIMEMORY_DB_URL` connection URL. Other secrets (e.g., Qdrant API keys) use `SecretStr` to prevent accidental logging.

```python
# Qdrant API key - password is never exposed
config.qdrant.api_key  # SecretStr('**********')
config.qdrant.api_key.get_secret_value()  # Only way to access raw value
```

The `SecretStr` type ensures that:
- Secrets are never printed in logs or stack traces
- `repr()` and `str()` show masked values
- Explicit `.get_secret_value()` call required to access the actual secret

### Future: Vault Integration

OmniMemory is designed to support HashiCorp Vault via `ProtocolSecretsProvider`. The interface is defined in `src/omnimemory/protocols/secrets_provider.py`.

```python
from omnimemory.protocols import ProtocolSecretsProvider

class VaultSecretsProvider:
    """Future Vault implementation."""

    async def get_secret(self, key: str) -> SecretStr:
        # Fetch from Vault
        ...

    async def get_secret_or_default(self, key: str, default: str) -> SecretStr:
        # Fetch with fallback
        ...

    async def has_secret(self, key: str) -> bool:
        # Check existence
        ...
```

## Validation Behavior

### Fail-Fast

Missing required configuration fails immediately at startup with clear error messages:

```
pydantic.ValidationError: 1 validation error for FilesystemSettings
OMNIMEMORY__FILESYSTEM__BASE_PATH
  Field required [type=missing, input_value={}, input_type=dict]
```

### Extra Variables Rejected

Unknown environment variables with the relevant prefix are rejected (`extra="forbid"`):

```python
# This will raise ValidationError
OMNIMEMORY__UNKNOWN_SETTING=value
# Error: extra fields not permitted

# Typos are also caught
OMNIMEMORY__FILESYTEM__BASE_PATH=/data  # Note: FILESYTEM vs FILESYSTEM
# Error: extra fields not permitted
```

This prevents typos from silently being ignored and ensures configuration correctness.

### Constraint Validation

All fields with constraints are validated:

```python
# Pool size out of range
OMNIMEMORY__POSTGRES__POOL_SIZE=100
# Error: Input should be less than or equal to 50

# Invalid URL scheme
OMNIMEMORY__QDRANT__URL=ftp://localhost:6333
# Error: URL scheme should be 'http' or 'https'

# Negative buffer size
OMNIMEMORY__FILESYSTEM__BUFFER_SIZE_BYTES=-1
# Error: Input should be greater than or equal to 4096
```

## Bootstrap Validation

Beyond settings validation, the `bootstrap()` function performs runtime validation:

1. **Filesystem**: Verifies `base_path` exists (or creates it if `create_if_missing=true`), is a directory, and is writable
2. **PostgreSQL**: Validates DSN format (does not test actual connection at bootstrap)
3. **Qdrant**: Validates URL format, warns if API key missing

```python
from omnimemory.settings import load_settings
from omnimemory.bootstrap import bootstrap

# Load and validate settings from environment
settings = load_settings()  # Validates env vars, raises ValidationError on failure

# Convert to config model
config = settings.to_config()

# Bootstrap validates runtime requirements
result = await bootstrap(config)

if result.success:
    print(f"Initialized backends: {result.initialized_backends}")

if result.warnings:
    for warning in result.warnings:
        print(f"Warning: {warning}")
```

### Bootstrap Error Handling

```python
from omnimemory.bootstrap import BootstrapError

try:
    result = await bootstrap(config)
except BootstrapError as e:
    print(f"Bootstrap failed for {e.config_block}: {e}")
    if e.cause:
        print(f"Underlying error: {e.cause}")
```

## Troubleshooting

### "Field required" Error

```
pydantic.ValidationError: 1 validation error for FilesystemSettings
OMNIMEMORY__FILESYSTEM__BASE_PATH
  Field required [type=missing, input_value={}, input_type=dict]
```

**Solution**: Set the required environment variable:
```bash
export OMNIMEMORY__FILESYSTEM__BASE_PATH=/data/omnimemory
```

### "extra fields not permitted" Error

```
pydantic.ValidationError: 1 validation error for MemoryServiceSettings
OMNIMEMORY__TYPO_SETTING
  extra fields not permitted [type=extra_forbidden]
```

**Solution**: Check for typos in environment variable names. Use the exact variable names documented in this file.

### "Invalid URL" Error

```
pydantic.ValidationError: 1 validation error for QdrantSettings
OMNIMEMORY__QDRANT__URL
  URL scheme should be 'http' or 'https' [type=url_scheme]
```

**Solution**: Use proper URL format including scheme:
```bash
export OMNIMEMORY__QDRANT__URL=http://localhost:6333
```

### "Input should be greater/less than" Error

```
pydantic.ValidationError: 1 validation error for PostgresSettings
OMNIMEMORY__POSTGRES__POOL_SIZE
  Input should be less than or equal to 50 [type=less_than_equal]
```

**Solution**: Use a value within the documented constraints.

### Bootstrap "does not exist" Error

```
omnimemory.bootstrap.BootstrapError: Bootstrap failed [filesystem]: base_path '/nonexistent' does not exist and create_if_missing=False
```

**Solution**: Either create the directory manually, or set:
```bash
export OMNIMEMORY__FILESYSTEM__CREATE_IF_MISSING=true
```

### Bootstrap "is not writable" Error

```
omnimemory.bootstrap.BootstrapError: Bootstrap failed [filesystem]: base_path '/data/omnimemory' is not writable: [Errno 13] Permission denied
```

**Solution**: Ensure the user running OmniMemory has write permissions to the base_path directory.

### PostgreSQL Settings Ignored

If you set PostgreSQL environment variables but they seem to have no effect:

**Solution**: Ensure you enable the backend:
```bash
export OMNIMEMORY__POSTGRES_ENABLED=true
```

Without this flag, PostgreSQL settings are not loaded.

### Qdrant Warning About Missing API Key

```
Bootstrap warning: Qdrant API key not configured - using unauthenticated access
```

**Solution**: This is a warning, not an error. For production, set:
```bash
export OMNIMEMORY__QDRANT__API_KEY=your-api-key
```

## Quick Reference

### Minimum Viable Configuration

```bash
export OMNIMEMORY__FILESYSTEM__BASE_PATH=/tmp/omnimemory
```

### Enable All Backends

```bash
export OMNIMEMORY__FILESYSTEM__BASE_PATH=/data/omnimemory
export OMNIMEMORY__POSTGRES_ENABLED=true
export OMNIMEMORY_DB_URL=postgresql://user:secret@localhost:5432/omnimemory
export OMNIMEMORY__QDRANT_ENABLED=true
```

### Verify Configuration

```python
from omnimemory.settings import load_settings

try:
    settings = load_settings()
    config = settings.to_config()
    print("Configuration valid!")
    print(f"Filesystem base: {config.filesystem.base_path}")
    print(f"PostgreSQL enabled: {config.postgres is not None}")
    print(f"Qdrant enabled: {config.qdrant is not None}")
except Exception as e:
    print(f"Configuration error: {e}")
```
