---
type: runbook
status: current
date: "2026-08-26"
title: "Starting OmniMemory Services"
topics:
  - omnimemory
  - runbook
  - docker
  - qdrant
  - memgraph
refs:
  - reference/omnimemory-environment-variables.md
  - reference/omnimemory-runtime-plugins.md
---

# Starting OmniMemory Services

**Owner:** `omnimemory`

> **Last verified:** 2026-08-26 — migrated from the `omnimemory` repository. Triage verdict `GENERICIZE_THEN_MIGRATE`. The procedure itself was verified against the repository's `docker-compose.yml`: all four container names and every port below (`6333`, `6334`, `7687`, `7444`, `6379`, `8090`) match the compose file, and each service declares a healthcheck.
>
> **Genericized on migration.** The source runbook drove the platform-infra layer through in-house shell helpers (`infra-up`, `infra-status`, `infra-up-memory`, `infra-down`) that wrap a private compose project, and it sourced the embedding endpoint from an operator-specific dotfile path. Neither exists for a self-hoster. Those steps are replaced below with the plain `docker compose` equivalent and a generic environment-file reference; the `omnimemory`-owned steps were already generic and are unchanged. One factual correction was also applied: the troubleshooting table said the plugin activates on `OMNIMEMORY_ENABLED`. The runtime checks `OMNIMEMORY_MEMGRAPH_HOST` first and honours `OMNIMEMORY_ENABLED` only as a legacy fallback.
>
> **Followability check performed.** Every step below was re-read as an operator with none of OmniNode's infrastructure. No step now depends on a shell function, a private compose project, a named lab host, or a personal dotfile path. The one step a self-hoster must supply themselves — their own Kafka and PostgreSQL deployment — is called out explicitly with its required outputs (a bootstrap address and a connection URL) rather than assumed.

---

## Overview

OmniMemory requires two infrastructure layers:

1. **Platform infra** — Kafka (or a Kafka-compatible broker such as Redpanda) plus PostgreSQL. These are platform-wide services shared by every ONEX component; OmniMemory consumes them but does not own them.
2. **Memory services** — Qdrant, Memgraph, Valkey and the Kreuzberg document parser. These are owned by `omnimemory` and are declared in its own `docker-compose.yml`.

Both layers must be running for full memory operation. Unit tests (`uv run pytest -m unit`) require neither — they run fully in-process against mock adapters. The memory services are needed only for integration tests and for workflows that exercise real storage backends.

Throughout this runbook, `<repo-root>` is your local checkout of `omnimemory`.

---

## 1. Start platform infra first

Bring up a Kafka-compatible broker and a PostgreSQL instance however you normally run them — a compose file you maintain, an existing cluster, or a managed service. OmniMemory only needs two facts out of this layer:

| What OmniMemory needs | Where it goes |
|---|---|
| A broker bootstrap address | `<kafka-bootstrap-servers>` — the platform bus configuration |
| A PostgreSQL connection URL | `OMNIMEMORY_DB_URL` |

A minimal self-hosted platform-infra compose file looks like this:

```yaml
# platform-infra/docker-compose.yml — supplied by the operator, not by omnimemory
services:
  redpanda:
    image: redpandadata/redpanda:latest
    command:
      - redpanda start
      - --smp 1
      - --overprovisioned
      - --kafka-addr PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr PLAINTEXT://localhost:9092
    ports:
      - "9092:9092"

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: onex
      POSTGRES_PASSWORD: <choose-a-password>
      POSTGRES_DB: onex
    ports:
      - "5432:5432"
```

Start and verify it:

```bash
docker compose -f platform-infra/docker-compose.yml up -d
docker compose -f platform-infra/docker-compose.yml ps
```

Expected: the broker and the PostgreSQL container both in `running` state.

> If your organisation wraps this layer in its own tooling, use that instead — the only requirement is that a broker and a PostgreSQL instance are reachable at the addresses OmniMemory is configured with.

---

## 2. Start the memory services

```bash
cd <repo-root>
docker compose up -d
```

Verify all four services are healthy:

```bash
docker compose ps
```

Expected: `omnimemory-qdrant`, `omnimemory-memgraph`, `omnimemory-valkey` and `omnimemory-kreuzberg-parser` all in running/healthy state.

### Service health checks

```bash
# Qdrant
curl -fsS http://localhost:6333/healthz && echo "Qdrant OK"

# Memgraph (Bolt protocol — use mgconsole or a Bolt client)
docker exec omnimemory-memgraph echo "Memgraph container up"

# Valkey
docker exec omnimemory-valkey valkey-cli ping

# Kreuzberg
curl -fsS http://localhost:8090/health && echo "Kreuzberg OK"
```

Each service also declares a compose healthcheck, so `docker compose ps` reporting `healthy` is sufficient on its own; the commands above are for diagnosing a service that will not reach that state.

---

## 3. Stop the services

```bash
cd <repo-root>
docker compose down
```

To stop the platform-infra layer, bring down whatever you started in step 1:

```bash
docker compose -f platform-infra/docker-compose.yml down
```

---

## Run the tests

Unit tests need no external services:

```bash
cd <repo-root>
uv sync --group dev
uv run pytest tests/ -m unit
```

The full suite does:

```bash
uv run pytest tests/ -v
```

Integration tests require both the memory services and the platform-infra layer to be running.

---

## Configuration

All service ports and connection strings are configurable through the repository's `.env` file. See [OmniMemory Environment Variables](../reference/omnimemory-environment-variables.md) for the complete variable list, types, defaults and constraints.

Default ports:

| Service | Endpoint | Default |
|---|---|---|
| Qdrant | REST | `localhost:6333` |
| Qdrant | gRPC | `localhost:6334` |
| Memgraph | Bolt | `localhost:7687` |
| Memgraph | HTTP | `localhost:7444` |
| Valkey | — | `localhost:6379` |
| Kreuzberg parser | HTTP | `localhost:8090` |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Qdrant returns 503 | Container not healthy yet | Wait 10s and retry; check `docker compose logs qdrant` |
| Memgraph connection refused | Memgraph not started, or a port conflict | Check `docker compose ps`; ensure port 7687 is free |
| Embedding failures | The embedding service is unreachable | Verify `LLM_EMBEDDING_URL` in your environment file points at a running embedding endpoint |
| Memory plugin never activates | The runtime did not detect memory-domain configuration | The plugin activates when `OMNIMEMORY_MEMGRAPH_HOST` is set; `OMNIMEMORY_ENABLED` is honoured only as a legacy fallback. Set the host variable in `.env` or export it before starting the runtime — see [OmniMemory Environment Variables](../reference/omnimemory-environment-variables.md) |
| `OMNIMEMORY__QDRANT__URL` validation error at startup | Qdrant is enabled but the URL is unset | That field has no default and is required whenever `qdrant_enabled` is true — set it explicitly |
