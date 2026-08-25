---
type: runbook
status: current
date: "2026-08-01"
title: "Gateway lane deploy (`omninode-gateway` compose project on `<onex-host>`)"
topics: [omnibase-infra, gateway, lane, deploy]
refs: []
---

# Gateway lane deploy (`omninode-gateway` compose project on `<onex-host>`)

This runbook documents the sanctioned deploy path for the `<onex-host>` operator-edge
gateway forwarder — the standalone process that bridges the cloud MSK bus to
the `<onex-host>` local Redpanda listener for cloud→local inference (<ticket> hybrid
gateway). It exists because, before <ticket>, this lane had **no** repo-
resident deploy path at all: it was stood up on 2026-07-29 by hand-copying
`docker/docker-compose.gateway.yml` and `docker/gateway/beta-gateway-canary.yaml`
into a root-owned directory and running compose there directly. That left the
lane invisible to `deploy-runtime.sh` (whose `-p omnibase-infra` scope never
touches it), running an image with an **empty**
`org.opencontainers.image.revision` label, and with no recorded rollback
target.

Ticket: **<ticket>**.

> Scope: this is the `<onex-host>` `omninode-gateway` lane ONLY (container
> `omninode-gateway-forwarder`, systemd unit `onex-gateway-forwarder`). It is
> unrelated to the `omnibase-infra` runtime lane `deploy-runtime.sh` manages —
> no migrations, no `RUNTIME_SERVICES` restart, no broker readiness preflight.
> See `docs/runbooks/cold-lane-full-bringup.md` for that lane instead.

---

## What's already on the host (read this before you "fix" it)

The `<onex-host>` box already has a working, restart-safe supervision layer for this
lane that this runbook does **not** replace:

- systemd unit `/etc/systemd/system/onex-gateway-forwarder.service` (repo copy:
  `docker/gateway/onex-gateway-forwarder.service`) — starts the container via
  `docker compose ... up -d --no-build --wait`, and its `ExecStartPre` **hard
  refuses to start** unless `/etc/omninode/gateway/gateway.env`'s
  `GATEWAY_IMAGE=` line is a real `sha256:<64 hex>` digest. It never builds —
  the image must already exist locally.
- `/etc/omninode/gateway/gateway.env` (root-owned, mode `0444`) — the AWS
  Roles Anywhere / TPM / container-UID variables the compose file requires,
  plus the pinned `GATEWAY_IMAGE` digest.
- `/opt/omninode/gateway/` (root-owned, mode `0444`) — the compose file +
  canary config the systemd unit's `WorkingDirectory` points at.

What was missing is everything **upstream** of that: a repeatable way to
build a new image from merged dev, stamp it with real provenance labels,
update the pinned digest, and sync the host files without hand-editing a
root-owned directory. `scripts/deploy-gateway.sh` is that path.

---

## Procedure

### 0. Pre-flight: sync the canonical clone to the merged-dev tip

Run from the canonical `omnibase_infra` clone on `<onex-host>` (same convention as
`deploy-runtime.sh` and `refresh_stability_lane.sh` — this script is **not**
run from a worktree):

```bash
cd /data/omninode/omni_home/omnibase_infra   # or wherever the canonical clone lives on this host
git pull --ff-only
```

### 1. Preview (dry-run, the default)

```bash
./scripts/deploy-gateway.sh
```

Dry-run prints the resolved version/git SHA and the exact compose build
command it would run, and lists every file/registry mutation it would
perform, without touching anything.

### 2. Inspect the exact build command

```bash
./scripts/deploy-gateway.sh --print-compose-cmd
```

This is the fix for the ticket's core finding: the printed command carries
`--build-arg VCS_REF=<sha> --build-arg RUNTIME_VERSION=<version> --build-arg
COMPOSE_PROJECT=omninode-gateway --build-arg RUNTIME_SOURCE_HASH=<sha>
--build-arg PROMOTION_CLASS=clean-main --build-arg NON_MAIN_LINEAGE=false` —
the same OCI provenance build-args `deploy-runtime.sh`'s `build_images()`
passes for every `omnibase-infra` runtime container. The compose file's own
declared `build.args` block only ever carried `BUILD_SOURCE`/
`EXPECTED_BUILD_SOURCE` (mirroring `docker-compose.infra.yml`'s split between
compose-declared and CLI-supplied build-args) — that split is why the
hand-built image had `rev=(empty)`.

### 3. Execute the deploy

```bash
./scripts/deploy-gateway.sh --execute
```

In order, this:

1. Resolves `repo_root` / `version` (pyproject.toml) / `git_sha` (HEAD).
2. Resolves the CONTAINER's currently running image
   (`docker inspect omninode-gateway-forwarder --format '{{.Image}}'`) as the
   rollback target — **never** `gateway.env`'s `GATEWAY_IMAGE=` line, which can
   go stale relative to what is actually running — and retags it durably as
   `docker-gateway-forwarder:previous` so it survives the build below moving
   the build tag onto the new image. If the previous image no longer resolves
   locally (already pruned), no rollback target is recorded for this deploy
   rather than recording a digest `docker image inspect` cannot find.
3. Sources the env file so the AWS/TPM/UID variables the compose file
   requires resolve for the build.
4. If `BUILD_SOURCE=workspace` (default `release`): stages
   `workspace/sibling-repos/` from `OMNI_HOME` via the SAME
   `scripts/runtime_build/stage_workspace.sh` `deploy-runtime.sh` uses, then
   runs the <ticket> sibling lock-pin preflight. `docker/Dockerfile.runtime`
   unconditionally `COPY`s `workspace/sibling-repos/`, so skipping this step
   in workspace mode silently built against the committed placeholder /
   whatever staging happened to already be in the checkout, while still
   stamping workspace-provenance labels. `BUILD_SOURCE=release` (the default)
   skips this entirely.
5. Builds `docker-gateway-forwarder:build` with the provenance build-args from
   step 2 above, **plus** `OMNIBASE_COMPAT_REF` / `OMNIMARKET_REF` /
   `ONEX_CHANGE_CONTROL_REF` — the same sibling-ref args
   `deploy-runtime.sh`'s `build_images()` passes unconditionally. Omitting
   these silently falls back to the Dockerfile's hardcoded ARG defaults,
   which is how the gateway image's `onex-change-control` pin drifted from
   the `omnibase-infra` runtime image's pin on the same box.
6. Resolves the built image's digest (`docker image inspect --format='{{.Id}}'`).
7. Syncs `docker/docker-compose.gateway.yml` and
   `docker/gateway/beta-gateway-canary.yaml` from **this checkout** into
   `/opt/omninode/gateway/` (`sudo install -m 0444 -o root -g root`, matching
   the existing file posture) — replacing the 2026-07-29 hand-copy as the
   source of truth. Every deploy re-syncs, so the host copy can never drift
   from a merged commit again.
8. Rewrites `/etc/omninode/gateway/gateway.env`'s `GATEWAY_IMAGE=` line to the
   new digest, leaving every other key untouched.
9. Writes `~/.omnibase/gateway/registry.json` recording `active_digest`,
   `previous_digest` (the rollback target), `git_sha`, `deployed_at`, and a
   ready-to-run `rollback_command` — the same convention
   `~/.omnibase/infra/registry.json` uses for the `omnibase-infra` lane.
   `previous_digest` and `rollback_command` are both `null` when there is no
   rollback target (first deploy, or the previous image had already been
   pruned) — never a fabricated digest or a sed command built from an empty
   value.
10. `sudo systemctl reload onex-gateway-forwarder` — the unit's existing
    `ExecReload` force-recreates the container on the new digest.
11. Verifies: the container is actually running the digest just built (a
    reload that silently fails to recreate the container is caught here
    instead of reporting success), labels are non-empty, and the two
    <ticket> files (`service_gateway_delivery.py`, `store_sqlite.py`) are
    present inside the running container.

Pass `--skip-reload` to build + sync + pin the new digest without recreating
the running container yet (the old container keeps running on the old
digest until a manual `sudo systemctl reload onex-gateway-forwarder`).

### 4. Verify

```bash
docker inspect omninode-gateway-forwarder \
  --format='rev={{index .Config.Labels "org.opencontainers.image.revision"}} src={{index .Config.Labels "com.omninode.build_source"}}'
# -> rev=<12-char sha> src=release   (never empty)

docker exec omninode-gateway-forwarder \
  ls /app/src/omnibase_infra/nodes/node_bus_forwarder_effect/services/
# -> must include service_gateway_delivery.py

docker exec omninode-gateway-forwarder \
  ls /app/src/omnibase_infra/idempotency/
# -> must include store_sqlite.py

diff /opt/omninode/gateway/docker-compose.gateway.yml docker/docker-compose.gateway.yml
# -> empty

cat ~/.omnibase/gateway/registry.json | jq .
```

---

## Rollback

`~/.omnibase/gateway/registry.json`'s `previous_digest` names the last-known-
good digest — resolved from the container's own running state at deploy time
and retagged as `docker-gateway-forwarder:previous` so a routine
`docker image prune` cannot silently make it unresolvable before anyone needs
it. `registry.json`'s own `rollback_command` field carries the exact restore
command pre-filled with that digest — run it verbatim, do not reconstruct it
by hand:

```bash
jq -r .rollback_command ~/.omnibase/gateway/registry.json
# -> sudo sed -i "s|^GATEWAY_IMAGE=.*|GATEWAY_IMAGE=sha256:<64 hex>|" /etc/omninode/gateway/gateway.env && sudo systemctl reload onex-gateway-forwarder

# then either paste that command, or:
bash -c "$(jq -r .rollback_command ~/.omnibase/gateway/registry.json)"
```

**`rollback_command` is `null` when there is no rollback target** — the first
deploy ever run against this lane, or a deploy whose previous running image
had already been pruned before this script could retag it. There is nothing
to roll back to in that case; do not reconstruct a sed command from
`.previous_digest` by hand (a JSON `null` printed through `jq -r` renders as
the literal string `null`, which `sed`s straight into `gateway.env`'s
`GATEWAY_IMAGE=` line and corrupts it — the systemd unit's `ExecStartPre`
digest-format assertion then refuses to start on the next restart/reboot).
Deploy forward instead.

This mirrors the `omnibase-infra` lane's own manual rollback-via-
`registry.json` pattern — `deploy-runtime.sh` has no automated `--rollback`
flag either; a prior digest is always restored by hand from the registry.

---

## AC5 — the <ticket> restart/redelivery proof

```bash
./scripts/gateway_restart_safety_proof.sh
```

Confirms the container is reachable via `docker exec` and records its
identity (`Id` + `State.StartedAt`), snapshots the running container's
durable idempotency store row count, reloads `onex-gateway-forwarder` (the
same mechanism `--execute` uses to recreate the container), waits for
Docker-healthy, then asserts the container's identity actually **changed**
(a reload that exits 0 and reports healthy without recreating anything is a
false-green a health check alone cannot catch), re-confirms reachability,
and re-snapshots — failing if any durable marker was lost across the
restart, the container never came back genuinely healthy, was never actually
recreated, or became unreachable. This is a real restart-durability smoke
proof, driven against the actual running container — it is **not** the full
cross-broker at-least-once/exactly-once redelivery proof (a deliberately
killed in-flight message never duplicating or dropping on the far side),
which needs a synthetic in-flight cloud MSK message and is <ticket>'s own
test suite's job.

Per <ticket>'s own AC5 wording ("that receipt lands on <ticket>, not this
ticket"): run the script, then paste its printed receipt into an <ticket>
comment. This runbook and `scripts/gateway_restart_safety_proof.sh` do not
file it anywhere themselves.

## Related runbooks

- `docs/runbooks/cold-lane-full-bringup.md` — the `omnibase-infra` runtime
  lane's own cold bring-up (a different compose project, different scope).
- `docker/gateway/onex-gateway-forwarder.service` — the systemd unit this
  script's `--execute` reloads.
