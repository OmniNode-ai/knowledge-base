---
type: runbook
status: current
date: "2026-07-21"
title: "Cold-lane full bring-up (deps + migration one-shots + full `--profile runtime`)"
topics: [omnibase-infra, cold, lane, full, bringup]
refs: []
---

# Cold-lane full bring-up (deps + migration one-shots + full `--profile runtime`)

This runbook documents how to bring a **cold** runtime lane all the way back up
from merged-dev source, and how that differs from the **warm** runtime refresh.
It exists because the dev lane is ephemeral — it is GC/idle-reclaimed and can be
torn down to **zero containers** between sessions — and bringing a fully cold
lane up is materially harder than the documented "recreate the runtime services"
warm path.

Ticket: **<ticket>** (parent epic <ticket>).
Evidence baseline: `.onex_state/runtime-e2e-2026-06-21/02-dev-deploy/`.

> Scope: this is the **dev** lane procedure (compose project `omnibase-infra`,
> the fully mutable test platform). Prod / judge / stability-test lanes are
> separate compose projects and are **not** brought up this way — a cold lane
> build is a workspace (non-main-lineage) image that the prod-promotion gate
> refuses. Promote a clean-main release to prod via the gated node path
> (`node_redeploy_orchestrator`), never via `--cold`.

---

## Cold vs warm — which path do I want?

| | **Warm** (`--restart`) | **Cold** (`--cold`) |
|---|---|---|
| Lane state going in | deps + broker already running | zero containers (GC-reclaimed / torn down) |
| What the final `up` touches | `RUNTIME_SERVICES` subset only, `up -d --no-deps` | the WHOLE `--profile runtime` project, `up -d` (honors `depends_on`) |
| Build source | whatever `BUILD_SOURCE` selects (default `release`) | forced `workspace` (merged-dev siblings) |
| Requires `OMNI_HOME` | only if `BUILD_SOURCE=workspace` | yes (workspace build) |
| Command | `./scripts/deploy-runtime.sh --execute --restart` | `OMNI_HOME=… ./scripts/deploy-runtime.sh --execute --cold` |

Both paths share the same cold-start preflight (core-infra readiness, broker
partition cap, the forward/intelligence migration one-shots, and a raised
`KAFKA_TIMEOUT_SECONDS` consumer-join budget). They differ **only** in the final
`up` step and in the build source.

---

## The two gotchas this path encodes

Two undocumented gotchas cost real time during the 2026-06-21 runtime-e2e run.
The `--cold` path now encodes both so an operator does not have to rediscover
them.

### Gotcha 1 — the runtime profile is mandatory

Every runtime service in `docker/docker-compose.infra.yml` is gated behind a
compose profile:

```yaml
profiles: ["runtime", "full"]
```

A bare `docker compose up -d` matches **no** profiled service and **starts
nothing** — the deps may come up but the kernel, effects, projection-api, and
the consumer/projection fleet all stay down. `--profile runtime` (or `full`) is
**mandatory**. `bringup_full_stack()` always passes `--profile "${COMPOSE_PROFILE}"`
(default `runtime`).

### Gotcha 2 — workspace build-args, not the default `release`

`deploy-runtime.sh` defaults `BUILD_SOURCE=release`, which builds the runtime
image from the **published PyPI packages**. A release image cannot carry
**un-released merged-dev code**, which is exactly what a cold/GC-reclaimed lane
must be rebuilt from. Workspace mode needs explicit build-args:

- `BUILD_SOURCE=workspace`
- `OMNI_HOME=<omni_home>`
- the sibling REF args (`OMNIBASE_COMPAT_REF`, `OMNIMARKET_REF`,
  `ONEX_CHANGE_CONTROL_REF`) + `RUNTIME_VERSION`
- and `scripts/runtime_build/stage_workspace.sh` must vendor the local siblings
  into `workspace/sibling-repos/` before the build.

`--cold` forces `BUILD_SOURCE=workspace` (so a contradictory
`BUILD_SOURCE=release` is rejected up front), `build_images()` stamps all the
workspace build-args, and `stage_workspace_if_needed()` runs `stage_workspace.sh`
automatically inside `sync_files`.

---

## Procedure

### 0. Pre-flight: sync the canonical clones to the merged-dev tips

A workspace build vendors the **local** sibling clones, so they must be at the
intended merged-dev SHAs first. On the deploy host:

```bash
cd "$OMNI_HOME"
bash ./omnibase_infra/scripts/pull-all.sh
```

The build is gated by the **sibling lock-pin preflight** (<ticket>): every
vendored sibling's version/SHA must match `omnimarket/uv.lock`. If a sibling
drifted from the lock (e.g. an OCC receipt PR merged after the lock was last
written), `stage_workspace.sh` aborts with exit 3. The correct fix is to advance
`omnimarket/uv.lock` to the current sibling SHAs and re-merge — **not** to set
`ALLOW_SIBLING_PIN_DRIFT=1`. See `.onex_state/runtime-e2e-2026-06-21/02-dev-deploy/02-BLOCKED-summary.md`.

### 1. Preview (dry-run)

```bash
OMNI_HOME="$OMNI_HOME" ./scripts/deploy-runtime.sh --cold
```

Dry-run stops before any mutation and shows what would be deployed (version, SHA,
compose project, profile, and the workspace build source).

### 2. Inspect the exact compose commands

```bash
OMNI_HOME="$OMNI_HOME" ./scripts/deploy-runtime.sh --cold --print-compose-cmd
```

This prints the build command (with `BUILD_SOURCE=workspace` and the sibling REF
build-args) and the "Full stack up" command
(`docker compose -p omnibase-infra -f …infra.yml --profile runtime up -d`).

### 3. Execute the cold full bring-up

```bash
OMNI_HOME="$OMNI_HOME" ./scripts/deploy-runtime.sh --execute --cold
```

This will, in order:

1. stage the workspace siblings (`stage_workspace.sh` + sibling lock-pin guard),
2. rsync + write the registry,
3. build the workspace-mode images (`BUILD_SOURCE=workspace`),
4. raise the cold-start `KAFKA_TIMEOUT_SECONDS` budget,
5. `ensure_core_infra_ready` — bring up + wait on postgres/valkey,
6. `warm_broker_topic_provisioning` — bring up redpanda + apply the partition cap,
7. `run_runtime_migration_preflight` — run the forward + intelligence migration
   one-shots and assert the projection tables exist,
8. `bringup_full_stack` — `docker compose … --profile runtime up -d` over the
   WHOLE project, and
9. `verify_deployment` — health endpoint + image-label + log-sentinel checks.

### 4. Verify

```bash
docker compose -p omnibase-infra ps
curl -fsS "http://${INFRA_HOST}:8085/health"
docker inspect omninode-runtime \
  --format='{{index .Config.Labels "com.omninode.build_source"}}'   # -> workspace
```

---

## Known cold-DB caveat (out of scope for <ticket>)

On a **truly cold DB**, the forward-migration one-shot can fail on a migration
that does `CREATE OR REPLACE VIEW` with reordered columns (Postgres forbids
renaming view columns in place). This is a **migration-source** defect that only
manifests on a from-scratch DB; incremental redeploys never re-run the offending
migration. It is tracked separately and is **not** something `--cold` can paper
over — the bring-up correctly fails fast at the migration preflight rather than
booting the kernel against a half-migrated schema. See
`.onex_state/runtime-e2e-2026-06-21/02-dev-deploy/99-result-summary.md`.

---

## Related runbooks

- `docs/runbooks/emergency-runtime-refresh.md` — surgical warm runtime refresh
  that must not touch core infra.
- `docs/runbooks/stability-test-runtime-lane.md` — the stability-test lane prep.
- `docs/runbooks/apply-migrations.md` / `vendored-node-migrations.md` — migration
  mechanics referenced by the preflight.
