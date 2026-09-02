---
type: guide
status: current
date: "2026-09-02"
title: "Integration Testing"
topics: [omnibase-infra, integration, testing]
refs: []
---

<!-- Migrated from omnibase_infra:docs/testing/INTEGRATION_TESTING.md on 2026-09-02. -->

# Integration Testing

> **Status**: Current | **Last Updated**: 2026-02-19

E2E test infrastructure for `omnibase_infra`: two-layer environment loading, the 53-test E2E suite, runtime container alignment, and infrastructure requirements.

---

## Table of Contents

1. [Overview](#overview)
2. [Two-Layer Environment Loading](#two-layer-environment-loading)
3. [E2E Test Suite](#e2e-test-suite)
4. [Infrastructure Requirements](#infrastructure-requirements)
5. [ALL_INFRA_AVAILABLE Flag](#all_infra_available-flag)
6. [Runtime Container Alignment](#runtime-container-alignment)
7. [Topic Management in E2E Tests](#topic-management-in-e2e-tests)
8. [Fixture Dependency Graph](#fixture-dependency-graph)
9. [RUNTIME_E2E_* Flags](#runtime_e2e_-flags)
10. [See Also](#see-also)

---

## Overview

The E2E registration test suite tests the full registration orchestration pipeline against real infrastructure: Kafka/Redpanda, Consul, and PostgreSQL. Tests skip gracefully when infrastructure is unavailable.

The test directory is `tests/integration/registration/e2e/` and contains 53 tests across 3 files.

---

## Two-Layer Environment Loading

The E2E conftest (`tests/integration/registration/e2e/conftest.py`) loads environment configuration in two layers:

```python
# Layer 1: Load project .env as base (credentials, shared settings)
load_dotenv(_project_env_file)

# Layer 2: Override with .env.docker for infrastructure endpoints
load_dotenv(_docker_env_file, override=True)
```

**Layer 1**: `<project_root>/.env`
- Contains credentials: `POSTGRES_PASSWORD`, `OPENAI_API_KEY`, etc.
- Points to remote infrastructure by default (`<onex-host>`)
- Never committed — contains secrets

**Layer 2**: `tests/integration/registration/e2e/.env.docker`
- Overrides infrastructure endpoints to point to local Docker containers
- Does NOT duplicate credentials (inherits from Layer 1)
- Committed to the repository

**Why two layers**: Credentials live in `.env` (not committed). Endpoint overrides for local Docker testing live in `.env.docker` (committed). No secrets are duplicated.

### .env.docker Contents

```bash
# PostgreSQL - local Docker container
POSTGRES_HOST=localhost
POSTGRES_PORT=5436

# Consul - local Docker container
CONSUL_HOST=localhost
CONSUL_PORT=28500

# Kafka/Redpanda - local Docker container
KAFKA_BOOTSTRAP_SERVERS=localhost:19092

# Runtime container
RUNTIME_HOST=localhost
RUNTIME_PORT=8085

# Topics are derived from each node's contract.yaml event_bus declaration
#. ONEX_INPUT_TOPIC / ONEX_OUTPUT_TOPIC env vars were removed and
# setting them now raises ProtocolConfigurationError at kernel bootstrap.

# Enable runtime E2E processing tests
RUNTIME_E2E_PROCESSING_ENABLED=true
RUNTIME_E2E_OUTPUT_EVENTS_ENABLED=true
RUNTIME_E2E_CONSUL_ENABLED=true
```

**To switch back to remote infrastructure**: Delete or rename `.env.docker`. Layer 1 (`.env`) then governs all endpoints.

### DSN Synthesis

If `OMNIBASE_INFRA_DB_URL` is not set, the conftest synthesizes it from individual `POSTGRES_*` variables:

```python
if not os.getenv("OMNIBASE_INFRA_DB_URL"):
    # Builds: postgresql://<user>:<pass>@<host>:<port>/<db>
    os.environ["OMNIBASE_INFRA_DB_URL"] = f"postgresql://..."
```

The `PostgresConfig.from_env()` utility in `tests/helpers/util_postgres.py` handles this canonically.

---

## E2E Test Suite

**Location**: `tests/integration/registration/e2e/`

**Total tests**: 53 across 3 test files

| File | Description |
|------|-------------|
| `test_full_orchestrator_flow.py` | Full registration orchestration pipeline tests |
| `test_runtime_e2e.py` | Runtime container tests (auto-enabled when runtime is healthy via `_default_enabled`) |
| `test_two_way_registration_e2e.py` | Two-way registration acknowledgment flow tests |

**Support files**:

| File | Purpose |
|------|---------|
| `conftest.py` | Fixtures, infrastructure availability checks, two-layer env loading |
| `performance_utils.py` | Performance measurement utilities for E2E tests |
| `verification_helpers.py` | Assertion helpers shared across E2E test files |

---

## Infrastructure Requirements

All E2E tests require **all four** of the following:

| Service | Environment Variable | Check |
|---------|---------------------|-------|
| **Kafka/Redpanda** | `KAFKA_BOOTSTRAP_SERVERS` | Variable set (non-empty) |
| **Consul** | `CONSUL_HOST` | TCP reachable at `CONSUL_HOST:CONSUL_PORT` |
| **PostgreSQL** | `OMNIBASE_INFRA_DB_URL` or `POSTGRES_HOST`+`POSTGRES_PASSWORD` | `PostgresConfig.from_env().is_configured` |
| **ServiceRegistry** | (internal) | `check_service_registry_available()` — guards against circular import bug in omnibase_core |

Missing any one causes all 53 E2E tests to skip with a descriptive message identifying which service is unavailable.

### Starting Local Docker Infrastructure

```bash
# Start all infrastructure services (Kafka, Consul, PostgreSQL)
docker compose --env-file .env -f docker/docker-compose.infra.yml up -d

# Start with the runtime container
docker compose --env-file .env -f docker/docker-compose.infra.yml --profile runtime up -d
```

---

## ALL_INFRA_AVAILABLE Flag

Defined in `tests/integration/registration/e2e/conftest.py`:

```python
ALL_INFRA_AVAILABLE = (
    KAFKA_AVAILABLE
    and CONSUL_AVAILABLE
    and POSTGRES_AVAILABLE
    and SERVICE_REGISTRY_AVAILABLE
)
```

Individual availability flags:

| Flag | How Checked |
|------|-------------|
| `KAFKA_AVAILABLE` | `bool(os.getenv("KAFKA_BOOTSTRAP_SERVERS"))` |
| `CONSUL_AVAILABLE` | TCP socket connect to `CONSUL_HOST:CONSUL_PORT` with 5s timeout |
| `POSTGRES_AVAILABLE` | `PostgresConfig.from_env().is_configured` |
| `SERVICE_REGISTRY_AVAILABLE` | `check_service_registry_available()` from `tests/conftest.py` |

The module-level `pytestmark` applies to all tests in the E2E directory:

```python
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not ALL_INFRA_AVAILABLE, reason="..."),
]
```

---

## Runtime Container Alignment

The runtime container reads its configuration from the project `.env` (which defaults to remote infrastructure at `<onex-host>`). E2E tests read from both `.env` and `.env.docker` (which overrides to local Docker).

**The misalignment**: Tests talk to local Docker but the runtime container talks to remote infra.

**To align**: Restart the runtime container with Docker-internal addresses:

```bash
KAFKA_BOOTSTRAP_SERVERS=redpanda:9092 \
POSTGRES_HOST=postgres \
POSTGRES_PORT=5432 \
CONSUL_HOST=consul \
CONSUL_PORT=8500 \
docker compose --env-file .env \
  -f docker/docker-compose.infra.yml \
  --profile runtime \
  up -d omninode-runtime
```

**Runtime image rebuild** (required after source code changes — source is COPIED into the image, not mounted):

```bash
docker compose --env-file .env \
  -f docker/docker-compose.infra.yml \
  --profile runtime \
  build omninode-runtime
```

**Runtime hostname resolution**: The runtime container resolves Docker-internal hostnames (`redpanda`, `postgres`, `consul`) via macOS Docker Desktop's host DNS, which reads `/etc/hosts`. Confirm `/etc/hosts` has the required entries:

```text
<onex-host> omninode-bridge-redpanda
<onex-host> omninode-bridge-postgres
<onex-host> omninode-bridge-consul
```

---

## Topic Management in E2E Tests

### Platform Topics

Platform topics (`onex.evt.platform.*`, etc.) must exist before E2E tests run. The runtime container handles topic creation via `TopicProvisioner` at startup. If tests bypass the runtime, topics must be pre-created manually.

**Test-specific topic** (`e2e-test.node.introspection.v1`): Create manually if missing:

```bash
docker exec omninode-bridge-redpanda \
  rpk topic create e2e-test.node.introspection.v1 --partitions 3
```

### UUID-Suffixed Test Topics

The `ensure_test_topic` fixture creates topics with UUID suffixes for parallel test isolation:

```python
async def test_publish_subscribe(ensure_test_topic):
    # Creates "test.e2e.introspection-<uuid>" and deletes it after the test
    topic = await ensure_test_topic("test.e2e.introspection", partitions=3)
```

The `KafkaTopicManager` from `tests/helpers/util_kafka.py` manages topic lifecycle (create on enter, delete on exit).

### aiokafka Compatibility Note

`aiokafka.describe_topics()` returns a `list` (not `dict`) in the current version. Topic existence validation must handle both formats.

---

## Fixture Dependency Graph

```text
postgres_pool
    -> wired_container
        -> registration_orchestrator
        -> projection_reader
        -> handler_node_introspected
    -> real_projector
        -> timeout_emitter
        -> heartbeat_handler

real_kafka_event_bus
    -> registration_orchestrator (via wired_container)
    -> introspectable_test_node
    -> timeout_emitter

ensure_test_topic
    -> ensure_test_topic_exists (pre-created UUID-suffixed topic)

real_consul_handler (mock_container)
    -> cleanup_consul_services

projection_reader
    -> timeout_scanner
        -> timeout_emitter
        -> timeout_coordinator

timeout_scanner + timeout_emitter
    -> timeout_coordinator
```

---

## RUNTIME_E2E_* Flags

Set in `.env.docker` to enable runtime-specific E2E test subsets. The `test_runtime_e2e.py` file checks these before running each test group:

| Flag | Controls |
|------|---------|
| `RUNTIME_E2E_PROCESSING_ENABLED=true` | Tests that publish events and verify runtime processes them |
| `RUNTIME_E2E_OUTPUT_EVENTS_ENABLED=true` | Tests that verify output events are published by the runtime |
| `RUNTIME_E2E_CONSUL_ENABLED=true` | Tests that verify the runtime registers nodes in Consul |

When the runtime container is healthy (`_default_enabled` check passes), `test_runtime_e2e.py` tests are auto-enabled even without the explicit flag. The flags provide fine-grained control when the runtime is reachable but specific subsystems are disabled.

---

## See Also

| Topic | Document |
|-------|----------|
| Test markers and commands | CI_TEST_STRATEGY.md (`../guides/omnibase-infra-ci-test-strategy.md`) |
| E2E conftest | `tests/integration/registration/e2e/conftest.py` |
| Environment file | `tests/integration/registration/e2e/.env.docker` |
| Kafka helper utilities | `tests/helpers/util_kafka.py` |
| PostgreSQL config helper | `tests/helpers/util_postgres.py` |
| Infrastructure topology | `~/.claude/CLAUDE.md` (Shared Standards) |
| Topic taxonomy | ../standards/TOPIC_TAXONOMY.md |
