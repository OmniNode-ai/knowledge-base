---
type: runbook
status: current
date: "2026-08-19"
title: "Stability-Test Runtime Lane"
topics: [omnibase-infra, stability, test, runtime, lane]
refs: []
---

# Stability-Test Runtime Lane

This runbook defines the first non-deploying prep slice for a separate
stability-test runtime lane. It does not start, restart, deploy, or mutate any
runtime host. In particular, it must not mutate the runtime host.

## Purpose

The stability-test lane exists so runtime proof can be prepared without sharing
production runtime names, state paths, or consumer groups. It is the bridge from
the two-phase runtime build plan into a concrete runtime lane:

- The overlay inherits the release runtime image build from the base compose
  file instead of declaring a lane-specific workspace image.
- `ONEX_ENVIRONMENT=stability-test` separates derived node consumer groups from
  the production/local `ONEX_ENVIRONMENT=local` group prefix.
- Explicit `ONEX_GROUP_ID` values use the `onex-stability-test-` prefix for the
  coarse runtime group settings.
- `ONEX_RUNTIME_ADDRESS` gives each runtime a routable address instead of
  treating stability-test as a special runtime flag.
- `ONEX_RUNTIME_ID`, `ONEX_BOX_ID`, and `ONEX_RUNTIME_CAPABILITIES` describe
  the concrete runtime target that orchestration can select later.
- `KAFKA_INSTANCE_ID` values are stability-test specific, so selector-aware
  event-bus consumers can append a lane-specific instance discriminator.
- Runtime state is mounted on stability-test volumes and uses
  `/app/data/.onex_state_stability_test`.
- The runtime image exports `OMNI_HOME=/app` and includes the `ssh`, `git`, and
  `uv` probe toolchain required by ONEX runtime-owned health, repo-sync, and
  golden-chain dry-run checks.
- The overlay does not expose inherited production host ports in the rendered
  stability-test config.
- The overlay does not render inherited out-of-lane runtime services such as
  observability consumers, contract resolver, Phoenix, autoheal, or the secrets manager.

## What Is Defined

- Compose overlay: `docker/docker-compose.stability-test.yml`
- Compose project name: `omnibase-infra-stability-test`
- Runtime image: inherited from the base runtime build.
- Runtime containers:
  - `omninode-stability-test-runtime`
  - `omninode-stability-test-runtime-effects`
  - `omninode-stability-test-runtime-worker`
- Runtime addresses:
  - `runtime://omninode-pc/stability-test/main`
  - `runtime://omninode-pc/stability-test/effects`
  - `runtime://omninode-pc/stability-test/worker`
- Runtime IDs:
  - `stability-test-main`
  - `stability-test-effects`
  - `stability-test-worker`
- Runtime box ID: `omninode-pc`
- Runtime group IDs:
  - `onex-stability-test-runtime-main`
  - `onex-stability-test-runtime-effects`
  - `onex-stability-test-runtime-workers`
- Runtime state root: `/app/data/.onex_state_stability_test`
- Published host ports:
  - Postgres: `15436`
  - Redpanda Kafka: `39092`
  - Redpanda admin: `29644`
  - Valkey: `26379`
  - Runtime main: `18085`
  - Runtime effects: `18086`
- Build args: inherited from the base runtime build.
- Networks:
  - `omnibase-infra-stability-test-network`
  - `omnibase-infra-stability-test-omnimemory-network`

## Contract-Owned Kafka Access

The stability-test Redpanda external listener must advertise one address that is
reachable by every authorized stability-test operator. Do not advertise
`localhost` or a private LAN-only address for this lane: Kafka
clients bootstrap on the supplied broker, then reconnect to the broker address
returned in metadata.

The stability-test broker advertise identity is owned by the
`x-omninode-contract-overlay` block in `docker/docker-compose.stability-test.yml`.
Do not set `STABILITY_TEST_REDPANDA_ADVERTISE_HOST` or any
`STABILITY_TEST_REDPANDA_*` port variable for this path.

Operators should then bootstrap with the same connected-network endpoint:

```bash
export KAFKA_BOOTSTRAP_SERVERS=<onex-host>:39092
kcat -L -b "$KAFKA_BOOTSTRAP_SERVERS" | sed -n '1,5p'
```

The metadata must report broker `0` at the connected-network host and port. If
it reports `localhost` or a private LAN address, off-LAN clients can open the TCP port
but fail when Kafka redirects them to the advertised broker address.

## Validation Only

Render the config only:

```bash
STABILITY_TEST_REDPANDA_ADVERTISE_HOST=<onex-host> \
docker compose \
  -f docker/docker-compose.infra.yml \
  -f docker/docker-compose.stability-test.yml \
  --profile runtime \
  config
```

The overlay requires Docker Compose v2.24.4 or later because it uses Compose
`!override` merge semantics to replace inherited port and profile lists.

List the rendered services and confirm the stability-test runtime services are
present:

```bash
STABILITY_TEST_REDPANDA_ADVERTISE_HOST=<onex-host> \
docker compose \
  -f docker/docker-compose.infra.yml \
  -f docker/docker-compose.stability-test.yml \
  --profile runtime \
  config --services
```

Run static validation:

```bash
uv run pytest tests/unit/infra/test_stability_test_runtime_lane.py -q
uv run pytest tests/integration/infra/test_stability_test_runtime_compose_render.py -q
```

## Worker Replica Census

The base compose used to set the runtime-worker deploy replicas to a bare
`${WORKER_REPLICAS:-0}` — a soft default of **zero** that no surface exported
(<ticket> replaced it with the lane-prefixed, fail-closed
`${DEV_WORKER_REPLICAS:?...}`). The stability lane's
required state includes a running worker (`GATE_ZERO_PROOF.md`: 4 runtime
containers — main, effects, worker, projection-api). Any plain
`docker compose up`/`recreate` that does not supply the worker replica count
silently scales the worker to zero with no error and no signal.

The lane override now references the ledgered policy value fail-fast:
`replicas: ${STABILITY_TEST_WORKER_REPLICAS:?...}`. The value lives in
`docker/runtime-policy.env` (rendered from
`contracts/services/runtime_policy.contract.yaml`,
`profiles.stability-test.services.worker.replicas`). A recreate that forgets to
pass `--env-file docker/runtime-policy.env` aborts loudly instead of dropping the
worker.

Expected-container census for the lane (a missing worker is a FAILURE, not
silence):

- `omninode-stability-test-runtime`
- `omninode-stability-test-runtime-effects`
- `omninode-stability-test-runtime-worker`
- `omnimarket-stability-test-projection-api`

Confirm the rendered config keeps the worker before any recreate (validation
only — this does not run `docker compose up`):

```bash
docker compose \
  --env-file docker/runtime-policy.env \
  -f docker/docker-compose.infra.yml \
  -f docker/docker-compose.stability-test.yml \
  --profile runtime \
  config | grep -A2 'runtime-worker:' | grep -q 'replicas' && echo "worker replicas pinned"
```

After an operator-approved recreate, assert the running census matches the
expected set (the worker must be present):

```bash
uv run python -m omnibase_infra.scripts.verify_container_manifest \
  --catalog-dir docker/catalog \
  --bundles runtime \
  --json
```

A non-zero exit (missing `omninode-stability-test-runtime-worker`) is a census
failure that must block the deploy/verify procedure.

## Explicit Non-Goals For This PR

- It does not run `docker compose up`.
- It does not deploy, restart, or change the runtime host.
- It does not install launchd, cron, systemd, or autoheal hooks.
- It does not prove runtime health, Redpanda membership, or build-loop to
  ticket-pipeline processing.
- It does not prove workspace image provenance; this lane intentionally follows
  the release runtime build until a separately approved selector change lands.

## Operator Gate

Any command that starts containers, restarts services, deploys to a host, or
changes the runtime host requires explicit operator approval and must produce a separate
runtime proof record.
