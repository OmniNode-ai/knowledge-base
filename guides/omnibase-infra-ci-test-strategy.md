---
type: guide
status: current
date: "2026-09-02"
title: "CI Test Strategy"
topics: [omnibase-infra, ci, test, strategy]
refs: []
---

<!-- Migrated from omnibase_infra:docs/testing/CI_TEST_STRATEGY.md on 2026-09-02. -->

# CI Test Strategy

> **Status**: Current | **Last Updated**: 2026-06-16

Test organization, pytest markers, coverage requirements, and common test commands for `omnibase_infra`. Read this before writing new tests or diagnosing CI failures.

---

## Table of Contents

1. [Overview](#overview)
2. [Test Directory Structure](#test-directory-structure)
3. [Pytest Markers](#pytest-markers)
4. [Auto-Applied Markers](#auto-applied-markers)
5. [Coverage Requirement](#coverage-requirement)
6. [Common Commands](#common-commands)
7. [Parallel Execution](#parallel-execution)
8. [See Also](#see-also)

---

## Overview

All tests live under `tests/`. The test suite runs with `pytest` via `uv run pytest`. Parallel execution uses `pytest-xdist` (`-n auto`). Coverage is enforced at 60% minimum (`fail_under = 60`).

The framework: **pytest** with **pytest-asyncio** in `auto` mode (all async test functions are automatically treated as coroutines).

---

## Test Directory Structure

```text
tests/
├── conftest.py              # Root conftest: shared fixtures, marker auto-application
├── infrastructure_config.py # Shared infrastructure constants (DEFAULT_CONSUL_PORT, etc.)
├── helpers/                 # Test helper utilities
│   ├── deterministic.py     # DeterministicClock for time-controlled tests
│   ├── util_kafka.py        # KafkaTopicManager, topic factory, consumer wait utilities
│   └── util_postgres.py     # PostgresConfig DSN builder
├── unit/                    # Unit tests — auto-marked with `unit`
├── integration/             # Integration tests — auto-marked with `integration`
│   ├── registration/
│   │   └── e2e/             # End-to-end registration tests (53 tests, 3 files)
│   └── runtime/
│       └── db/              # PostgreSQL integration tests
├── chaos/                   # Chaos engineering tests — auto-marked with `chaos`
├── replay/                  # Event replay and recovery tests — auto-marked with `replay`
├── performance/             # Performance and benchmark tests — auto-marked with `performance`
└── ci/                      # CI/CD-specific tests
```

---

## Pytest Markers

All markers are declared in `pyproject.toml` under `[tool.pytest.ini_options]`. Tests are run with `--strict-markers`, so using an undeclared marker fails the test collection.

### Infrastructure Requirement Markers

These markers indicate tests that require real external services. Tests decorated with these markers skip gracefully when the corresponding service is unavailable.

| Marker | Requirement | Skip Condition |
|--------|-------------|----------------|
| `@pytest.mark.consul` | Real Consul instance | `CONSUL_HTTP_ADDR` not set or unreachable |
| `@pytest.mark.postgres` | Real PostgreSQL instance | `POSTGRES_DSN` or `OMNIBASE_INFRA_DB_URL` not set |
| `@pytest.mark.kafka` | Real Kafka instance | `KAFKA_BOOTSTRAP_SERVERS` not set |
| `@pytest.mark.e2e` | Full infrastructure (Kafka + Consul + PostgreSQL + ServiceRegistry) | `ALL_INFRA_AVAILABLE` is False |
| `@pytest.mark.runtime` | ONEX runtime container running | Runtime health check fails |
| `@pytest.mark.llm` | Real LLM inference endpoints | Endpoints not reachable |

### Execution Characteristic Markers

| Marker | Meaning | Usage |
|--------|---------|-------|
| `@pytest.mark.slow` | Test takes more than 1 second | Apply manually to known-slow tests |
| `@pytest.mark.serial` | Must not run in parallel with other tests | Apply to resource-intensive tests that conflict under xdist |
| `@pytest.mark.heavy` | Requires real infrastructure; skipped by default | Run with `RUN_HEAVY_TESTS=1` env var |

### Domain Markers

| Marker | Meaning |
|--------|---------|
| `@pytest.mark.unit` | Tests individual components in isolation |
| `@pytest.mark.integration` | Tests multiple components together |
| `@pytest.mark.chaos` | Chaos engineering and fault injection |
| `@pytest.mark.replay` | Event replay and recovery scenarios |
| `@pytest.mark.smoke` | Quick smoke tests for basic functionality |
| `@pytest.mark.performance` | Performance and benchmark tests |
| `@pytest.mark.benchmark` | Benchmark tests for measurement |
| `@pytest.mark.infrastructure` | Infrastructure-specific tests |
| `@pytest.mark.validation` | Validation framework tests |

### Protocol Markers

| Marker | Meaning |
|--------|---------|
| `@pytest.mark.real_mcp` | Tests using real MCP SDK server/client (requires available port) |
| `@pytest.mark.mcp_protocol` | Mock-based MCP JSON-RPC protocol tests (no real SDK) |
| `@pytest.mark.database` | Tests requiring a database connection |

---

## Auto-Applied Markers

The root `conftest.py` applies markers automatically based on test file location. You do not need to add these markers manually to tests in the correct directories.

| Directory | Auto-Applied Marker |
|-----------|---------------------|
| `tests/unit/` | `unit` |
| `tests/integration/` | `integration` |
| `tests/chaos/` | `chaos` |
| `tests/replay/` | `replay` |
| `tests/performance/` | `performance` |

**Convention**: Even though markers are auto-applied by directory, you should still decorate individual test functions and classes with the relevant marker for explicit documentation and to support filtering in IDEs.

---

## Coverage Requirement

**Minimum 60% coverage required** across `src/omnibase_infra/`.

Configuration in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["src/omnibase_infra"]
branch = true
parallel = true

[tool.coverage.report]
fail_under = 60
```

Coverage is measured with branch coverage (`branch = true`). The `parallel = true` setting supports coverage aggregation across xdist workers.

**Excluded from coverage**:
- `def __repr__`
- `if TYPE_CHECKING:` blocks
- `raise AssertionError` / `raise NotImplementedError`
- `if __name__ == "__main__":` blocks
- `@abstractmethod` / `@abc.abstractmethod`

---

## Common Commands

```bash
# All tests
uv run pytest tests/

# With coverage report (enforces 60% minimum)
uv run pytest tests/ --cov=omnibase_infra --cov-report=html

# Unit tests only
uv run pytest -m unit

# Integration tests only
uv run pytest -m integration

# E2E tests only (requires full infrastructure)
uv run pytest -m e2e

# Exclude slow tests
uv run pytest -m "not slow"

# Exclude infrastructure-requiring tests (fast local development)
uv run pytest -m "not (consul or postgres or kafka or e2e or runtime)"

# Type checking
uv run mypy src/omnibase_infra/

# Linting
uv run ruff check src/ tests/

# All pre-commit hooks
pre-commit run --all-files
```

---

## Parallel Execution

`pytest-xdist` enables parallel test execution. Most tests support parallelism by default.

```bash
# Auto-detect CPU count and parallelize
uv run pytest tests/ -n auto

# Fixed worker count
uv run pytest tests/ -n 4

# Disable parallelism (debug mode)
uv run pytest tests/ -n 0 -xvs
```

**Serial tests**: Tests decorated with `@pytest.mark.serial` must not run in parallel. These are typically resource-intensive tests that share external state (e.g., Consul services, PostgreSQL sequences).

**E2E topic isolation**: E2E tests that create Kafka topics use UUID-suffixed topic names (via the `ensure_test_topic` fixture) to prevent cross-test pollution when running in parallel.

**asyncio loop scope**: The default loop scope is `function` (each test gets its own event loop). Tests needing session-scoped async fixtures must set:

```python
pytestmark = [pytest.mark.asyncio(loop_scope="session")]
```

---

## CI Gate Inventory

The following CI workflows ship as merge gates in addition to the standard `ci.yml` test suite. All are wired to the `pull_request` and `merge_group` triggers unless noted.

### dispatcher-route-coverage

**File**: `.github/workflows/dispatcher-route-coverage.yml`

Asserts that every `contract.yaml` in omnibase_infra and omnimarket that subscribes to a command topic (`onex.cmd.*`) also declares a dispatcher route via `handler_routing` or `runtime_dispatch`. Missing wiring causes commands to go to DLQ silently. Introduced after two incidents: a June 9 2026 DLQ regression and the DEL-01 delegation live finding (June 12 2026). In changed-command-topic mode the gate rescans only changed contracts on PRs for faster feedback.

**Failure**: Means a subscribed command topic has no dispatcher route — commands will silently DLQ in the runtime. Fix: add `handler_routing` or `runtime_dispatch` entries to the relevant contract.

### transport-mock-lint

**File**: `.pre-commit-config.yaml` (hook `transport-mock-lint` from `omnibase_core`) + `.github/workflows/ci.yml`

Detects test code that directly imports or instantiates live Kafka/EventBus/transport surfaces instead of mock substitutes. The existing violation count is frozen in `config/validation/transport_mock_baseline.yaml` (218 violations across 63 files as of introduction). New violations are blocked; existing ones are drained per-site.

**Failure**: A new test file directly uses a real transport surface. Fix: replace with the appropriate mock or in-memory bus fixture.

### node-migration-sync

**File**: `.github/workflows/node-migration-sync.yml`

Checks that every node migration SQL file under `src/omnimarket/nodes/<node>/migrations/*.sql` has been vendored into `docker/migrations/forward/nodes/<node>/` via `scripts/sync-node-migrations.sh`. An un-vendored node migration was the root cause of `pattern_learning_artifacts` being absent from `omnidash_analytics` on a clean redeploy. The gate re-runs the `--check` against the current omnimarket dev tip on every infra PR.

**Failure**: An omnimarket node migration exists that has not been vendored into the infra forward-migration directory. Fix: run `scripts/sync-node-migrations.sh` and commit the vendored files.

### stale-todo-gate

**File**: `.github/workflows/stale-todo-gate.yml`

Checks that `TODO`/`FIXME`/`HACK` comments in changed Python files do not reference Linear tickets in terminal states (Done or Canceled). Requires `LINEAR_API_KEY` as a repository secret; gracefully skips (exit 0 with a warning) if the secret is absent.

**Failure**: A changed file contains a TODO referencing a ticket that is already Done or Canceled. Fix: remove or update the comment.

### seed-provenance-check

**File**: `.github/workflows/seed-provenance-check.yml`

**Advisory only** (`continue-on-error: true`). Warns when seed or demo scripts publish Kafka events without setting `data_provenance` in the payload. This gate never blocks a merge.

---

## See Also

| Topic | Document |
|-------|----------|
| E2E integration testing | INTEGRATION_TESTING.md (`../guides/omnibase-infra-integration-testing.md`) |
| Infrastructure topology | `~/.claude/CLAUDE.md` (Shared Standards) |
| Pytest configuration | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Coverage configuration | `pyproject.toml` (`[tool.coverage.*]`) |
| Vendored node migrations runbook | ../runbooks/vendored-node-migrations.md |
