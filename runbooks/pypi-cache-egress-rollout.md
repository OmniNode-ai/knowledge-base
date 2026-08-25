---
type: runbook
status: current
date: "2026-08-19"
title: "PyPI pull-through cache (egress) rollout — <ticket> C1"
topics: [omnibase-infra, pypi, cache, egress, rollout]
refs: []
---

# PyPI pull-through cache (egress) rollout — <ticket> C1

**Status (2026-08-14): IN EXECUTION — steps 1–3 DONE, step 4 soak IN PROGRESS,
step 5 fleet rollout NOT STARTED (gated on step 4).**

| Step | State | Evidence |
|---|---|---|
| 1. Freeze the pins | DONE | base `python:3.12-slim@sha256:dd293726…88e65`; `devpi-server==6.20.3`, `devpi-web==4.3.0` (readback from the running cache) |
| 2. Stand up devpi | DONE (pre-existing) | `omninode-pypi-cache` **Up 2 weeks (healthy)**; index HTTP **200**, 41,517,006 B; corpus **22G**; volume `omninode-pypi-cache-data` |
| 3. Wire canary subset | DONE | `omninode-runner-2/4/5` recreated 2026-08-14T06:45–06:46Z; container-env readback shows all four index vars; controls (`runner-1/3`) confirmed clean |
| 4. Measure on the canary | **IN PROGRESS** | mechanism proven (see "Canary evidence"); load-soak under high concurrency not yet accumulated |
| 5. Fleet rollout | **NOT STARTED** | blocked on step 4 acceptance; `pypi_cache.active` stays `false` |

Earlier revisions of this file said "do **not** run these steps until the
<ticket> execution gate trips." That gate has tripped and steps 1–3 have been
executed against the live runner host. The soak gate on step 5 is **unchanged and
still binding** — do not flip the fleet on step-3 success.

## What this is

64 self-hosted runners NAT through one home uplink. Under concurrent `merge_group`
full-suite load, each runner independently cold-downloads the same PyPI wheels,
saturating egress and tripping `uv sync` download timeouts (the <ticket> failure
class). A devpi pull-through cache fetches each wheel from PyPI **once**, then serves
all 64 runners from the LAN — removing the redundant bytes from the shared uplink.
This is the independent-throughput lever; it complements the C3 stampede cap that is
already active fleet-wide (see below).

Sibling of the §3.19 Docker Hub pull-through mirror (images vs wheels; same host,
same non-disruptive rollback discipline). Land together or sequence — not mutually
exclusive.

## Artifacts in this repo (already landed by the design/canary PR)

| Artifact | Role | State |
|---|---|---|
| `docker/pypi-cache/Dockerfile` + `entrypoint.sh` | devpi-server image (build-at-rollout) | inert |
| `docker/docker-compose.pypi-cache.yml` | standalone cache service (NOT in the runner fleet) | inert |
| `config/runner_fleet.yaml` → `pypi_cache:` | endpoint source-of-truth | `active: false` |
| `docker/docker-compose.runners.yml` → commented `UV_DEFAULT_INDEX` block | fleet wiring | inert (commented) |
| `docker/docker-compose.runners.yml` → `UV_CONCURRENT_*` / `UV_HTTP_TIMEOUT` | C3 stampede cap | **active** |

## C3 (already active — not gated)

The fleet-wide uv concurrency cap ships active in the canary PR because it cannot
regress any path: the hardened `setup-python-uv` composite already pins
`UV_CONCURRENT_DOWNLOADS=${...:-1}` = 1, so a fleet default of 1 leaves that path
unchanged while capping the raw-`uv` paths (the <ticket> workflows) down from uv's
built-in default. **Do not raise the fleet cap to 2 until C1 below is active and the
canary metrics below are green** — 2 doubles the composite path's download fan under
a still-saturated uplink.

## Rollout (gated — run only after the gate trips)

Run on the runner host (`<onex-host>` / `<onex-host>`). This is a NEW
service; it does not mutate any prod daemon or the runner containers.

### 1. Freeze the pins

- Pin the `python:3.12-slim` base image to a `@sha256:` digest in
  `docker/pypi-cache/Dockerfile` (match the runner-image reproducibility discipline).
- Freeze `DEVPI_SERVER_SPEC` / `DEVPI_WEB_SPEC` to exact versions.

### 2. Stand up devpi

```bash
docker compose -f docker/docker-compose.pypi-cache.yml up -d --build
# wait for healthy:
docker inspect --format '{{.State.Health.Status}}' omninode-pypi-cache
# prove the pull-through index answers:
curl -fsS http://localhost:3141/root/pypi/+simple/ >/dev/null && echo "cache index OK"
```

### 3. Wire a small canary runner subset (leave the rest on direct egress)

Recreate a NAMED SUBSET of runner containers with the cache env set on those
containers only — do **not** uncomment the fleet-wide block.

> **CORRECTED 2026-08-14 — the previous recipe here was a silent no-op.** It read:
>
> ```bash
> # DOES NOT WORK — kept only so nobody re-derives it
> UV_DEFAULT_INDEX="http://.../root/pypi/+simple/" \
>   docker compose -f docker/docker-compose.runners.yml up -d \
>     --no-deps --force-recreate omninode-runner-1
> ```
>
> Compose injects a variable into a container only when the service's
> `environment:` block *names* it. The fleet `UV_DEFAULT_INDEX` block in
> `docker/docker-compose.runners.yml` is deliberately commented out, so nothing
> consumes those shell variables and the container comes up on **direct egress**.
> There is no error — the canary reports itself as a canary and measures nothing.
> Any "canary green" produced by the old recipe is vacuous and must be re-run.
>
> Readback proof (rendered on the runner host, both forms, same fleet file):
>
> ```
> shell-env form   -> omninode-runner-1: {UV_CONCURRENT_BUILDS, UV_CONCURRENT_DOWNLOADS,
>                                         UV_CONCURRENT_INSTALLS, UV_HTTP_TIMEOUT}
>                                        # no UV_DEFAULT_INDEX, no PIP_INDEX_URL
> override-file    -> omninode-runner-2: {..., UV_DEFAULT_INDEX, UV_INDEX_STRATEGY,
>                                         PIP_INDEX_URL, PIP_EXTRA_INDEX_URL}
> ```

Use the tracked override file `docker/docker-compose.pypi-canary.yml`, which
names the canary members and carries the cache env. From the runner host's deploy
directory:

```bash
cd ~/.omnibase/runners
# these are required for compose to interpolate the full fleet file at all —
# omitting them fails with "required variable DEPLOY_RUNNER_* is missing a value"
export DEPLOY_RUNNER_OMNI_HOME=/data/omninode/runner_omni_home
export DEPLOY_RUNNER_OPERATOR_ENV_FILE="$HOME/.omnibase/.env"
export DEPLOY_RUNNER_TOKEN=""
set -a; . ./docker/.env; set +a          # RUNNER_TOKEN

docker compose \
  -f docker/docker-compose.runners.yml \
  -f docker/docker-compose.pypi-canary.yml \
  up -d --no-deps --force-recreate \
  omninode-runner-2 omninode-runner-4 omninode-runner-5
```

**Recreate only IDLE runners.** Check first — recreating a busy runner kills its
job:

```bash
gh api /orgs/OmniNode-ai/actions/runners --paginate \
  -q '.runners[] | select(.name|test("omninode-runner-(2|4|5)$")) | "\(.name) busy=\(.busy)"'
```

**Verify the wiring actually landed — never skip this**, it is the check that
distinguishes a real canary from the vacuous one above:

```bash
for n in 2 4 5; do
  echo "runner-$n:"
  docker inspect omninode-runner-$n \
    --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | grep -E '^(UV_DEFAULT_INDEX|UV_INDEX_STRATEGY|PIP_INDEX_URL|PIP_EXTRA_INDEX_URL)='
done
```

PyPI stays configured as the fallback (`PIP_EXTRA_INDEX_URL` +
`UV_INDEX_STRATEGY=unsafe-best-match`) so a cache miss/outage degrades, not
fails-closed.

### 3a. Durability trap — a canary reverts silently unless it is layered

**Every** tool that recreates runner containers does so from
`docker-compose.runners.yml` **alone**: `scripts/deploy-runners.sh`, the runner
host's `remote_roll.sh`, and — the one that bites, because it is unattended —
`docker/runners/runner-monitor.sh`, which the `*/10` `runner-repair-check` cron
runs with `MONITOR_AUTO_BOUNCE=1` and force-recreates any offline-idle runner.

A canary expressed only as a host-local override file is therefore reverted to
direct egress by the next auto-bounce, **with no log line, no alert, and no
diff** — mid-soak, while the soak keeps reporting. This is not hypothetical: the
first canary attempt was authored on the host 2026-08-08 and its wiring was gone
by 2026-08-10, unrecorded.

The fix is layering, kept as config-as-code:

- `docker/docker-compose.pypi-canary.yml` is a **tracked repo artifact**, not a
  file hand-written on the host.
- `docker/compose-overrides.list` names the override files that must be layered
  on every recreate.
- `docker/runners/runner-monitor.sh` reads that list and layers each entry into
  its `docker compose ... up --force-recreate`, so auto-repair preserves canary
  wiring instead of stripping it.

After any fleet roll, monitor bounce, or host reboot, re-run the step-3 readback
before trusting a measurement. Treat a canary whose env readback is empty as
**zero soak time accumulated**, not as a green result.

### 4. Measure on the canary (short soak)

- Wheel-cache hit rate on the canary → target ≥ ~90% steady-state
  (`config/runner_fleet.yaml` `pypi_cache.target_hit_rate`).
- p95 `uv sync` wall time vs a direct-egress runner under the same load.
- Zero `UV_HTTP_TIMEOUT` / `virtualenv download` failures on `merge_group`
  full-suite jobs under 64/64-busy load.
- No throughput regression vs direct egress.

#### Canary evidence — mechanism (2026-08-14T06:47Z)

A real resolve executed **inside** `omninode-runner-2`, taking its index purely
from container env (no `--index-url` flag), with `--no-cache` so uv could not
satisfy anything from its local wheel cache:

```
uv pip install --no-cache pydantic==2.12.5 httpx==0.28.1 pytest==8.4.2
  -> Prepared 16 packages in 86ms / Installed 16 packages in 11ms
  -> real 0m3.033s
```

devpi log slice for that window attributes **every** fetch to the cache — 16
`+simple/<pkg>/` index lookups and 16 `+f/<hash>/<wheel>` wheel fetches, 48
requests total, zero upstream-refetch or error lines:

```
2 GET /root/pypi/+f/e56/1593fccf61e8a/pydantic-2.12.5-py3-none-any.whl
2 GET /root/pypi/+f/d90/9fcccc110f8c7/httpx-0.28.1-py3-none-any.whl
2 GET /root/pypi/+f/872/f880de3fc3a5b/pytest-8.4.2-py3-none-any.whl
... (16 wheels)
1 GET /root/pypi/+simple/pydantic/
... (16 index lookups)
```

This proves the resolve path, the LAN reachability, and the pull-through serve.
It does **not** discharge the acceptance criteria above, which are all
*under-load* measurements. Do not treat it as step-4 completion.

#### What is still missing before step 5

The acceptance criteria are written against 64/64-busy `merge_group` full-suite
load. The canary has not yet run under that load — the PR queue is currently
serialized and the fleet is lightly loaded (9/72 busy at canary start), which is
the right window to *wire* a canary but the wrong window to *measure* one. Let
the canary accumulate real jobs across a busy period, then compare canary vs
control (`omninode-runner-1/3`, deliberately left on direct egress) on hit rate,
p95 `uv sync` wall time, and timeout-failure count before touching step 5.

### 5. Fleet rollout (only if the canary is green)

- Set `pypi_cache.active: true` in `config/runner_fleet.yaml`.
- Uncomment the `UV_DEFAULT_INDEX` / `UV_INDEX_STRATEGY` / `PIP_INDEX_URL` /
  `PIP_EXTRA_INDEX_URL` block in `docker/docker-compose.runners.yml`.
- Optionally raise `UV_CONCURRENT_*` from 1 to 2 now that egress pressure is
  removed (tune from the canary measurement).
- Roll the env to the full fleet via runner-image rebuild + rolling recreate
  (idle-only, same care as fleet-heal). C2 (Actions/uv-binary acceleration) folds
  in with the same rebuild — see the ticket.

## Rollback (non-disruptive)

Fallback is to drop the cache wiring; the cache is additive, so removing it returns
the fleet to direct egress.

1. Re-comment the `UV_DEFAULT_INDEX` block in `docker-compose.runners.yml` (and set
   `pypi_cache.active: false`), rebuild the runner image, rolling-recreate.
2. Tear down the cache service (its own project — not a runtime lane, so the
   no-bare-compose-teardown gate does not apply):

   ```bash
   docker compose -f docker/docker-compose.pypi-cache.yml down
   ```

The named volume `omninode-pypi-cache-data` persists the warmed corpus across a
recreate; add `-v` only to discard the cache entirely.

## References

- <ticket> (this work), parent <ticket>
- <ticket> — Layer-A per-workflow `uv` timeout band-aid this makes non-load-bearing
- <ticket> — 18 workflows bypassing the hardened composite (the raw-`uv` class C3 caps)
- <ticket> — sibling Docker Hub pull-through mirror (§3.19)
- Plan: `omni_home/docs/plans/2026-07-05-runner-fleet-permanent-fix-plan.md`
