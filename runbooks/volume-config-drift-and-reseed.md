---
type: runbook
status: current
date: "2026-07-21"
title: "Volume Config Drift Gate + Re-seed Procedure"
topics: [omnibase-infra, volume, config, drift, reseed]
refs: []
---

# Volume Config Drift Gate + Re-seed Procedure

## Problem

The Bifrost delegation contract is rendered once at container startup to a Docker
named volume at `/app/data/delegation/bifrost_delegation.yaml`. That volume
survives `docker compose build` and container recreate, so the **deployed (volume)
copy can silently diverge from the packaged source** shipped in the image. Two
prior incidents were caused by exactly this:

- a stale gemini backend binding persisted on the volume after the packaged
  source was updated, and
- an empty `frontier_api` endpoint persisted on the volume.

There are two competing authorities:

1. **Packaged source** — `omnimarket/configs/bifrost_delegation.yaml` baked into
   the image (canonical home; legacy fallback
   `omnibase_infra/configs/bifrost_delegation.yaml`).
2. **Volume copy** — `/app/data/delegation/bifrost_delegation.yaml`, written once
   and then trusted on subsequent boots when it already has populated endpoints
   (see `render_bifrost_delegation_contract` short-circuit).

Additionally, `BIFROST_CONTRACT_PATH=""` (empty) silently **disables** packaged
rendering entirely (the renderer returns `None`).

> **Scope note.** Reconciling the two authorities into one (the secrets manager > bootstrap
> overlay precedence) is ongoing work. This runbook is the tactical drift
> **gate + re-seed** stopgap: it makes drift *visible and ticketed*, and gives
> operators a deterministic re-seed step. It does not change which authority wins
> at render time.

## Ratchet shipped with this runbook

| Ratchet | Where |
|---------|-------|
| (a) Re-seed volume config from packaged source with ledgered overlay diffs only | this runbook (procedure below) |
| (b) Runtime startup logs config provenance (path + sha); health exposes it | `runtime/config_provenance.py`, `runtime/health/health_config_provenance.py`, `runtime/render_bifrost_delegation_contract.py::main` |
| (c) Sweep compares volume sha vs packaged sha → drift = auto-ticket | omnimarket `node_volume_config_drift_sweep` |
| (d) Config provenance appears in proof packets | provenance sidecar `/app/data/delegation/.config_provenance.json` + sweep output |

## Provenance at runtime

On every boot, after the contract is rendered, the entrypoint logs a single-line
provenance summary and writes a sidecar JSON next to the deployed contract:

```
[entrypoint] config_provenance config=bifrost_delegation status=in-sync \
  deployed_path=/app/data/delegation/bifrost_delegation.yaml \
  deployed_sha256=<sha> source_path=<packaged> source_sha256=<sha>
```

- `status=DRIFT` and an additional `WARNING` line are emitted when the deployed
  sha differs from the packaged-source sha.
- The sidecar `/app/data/delegation/.config_provenance.json` is the machine
  surface the drift sweep and proof packets read (no need to re-resolve the
  packaged source path inside the container).
- The health component `config_provenance`
  (`check_config_provenance_health`) reports:
  - `unhealthy` — deployed contract absent,
  - `degraded` — drift detected (re-seed required) or packaged source absent,
  - `healthy` — deployed sha == source sha.

> The deployed sha reflects the **post-render** contract (endpoint_url values
> populated from env). Treat the sweep's drift signal as "investigate", then use
> the source-vs-volume diff below to decide whether the divergence is an intended
> overlay or stale config that must be re-seeded.

## Re-seed procedure (operator)

> **Live-lane safety.** Re-seeding mutates the named volume. Do **not** run the
> overwrite steps against stability (`18085/18086`), dev (`8085/8086`), or prod
> (`28085/28086`) without the lane's deploy approval. The diff/inspection steps
> are read-only and always safe.

### 1. Inspect drift (read-only)

```bash
# On the runtime host, against the target lane's runtime container:
docker exec <runtime-container> cat /app/data/delegation/.config_provenance.json
```

If `has_drifted` is `true`, diff the deployed volume copy against the packaged
source to capture the **explicit overlay** before overwriting:

```bash
docker exec <runtime-container> sh -c \
  'diff -u <packaged-source-path> /app/data/delegation/bifrost_delegation.yaml || true'
```

### 2. Ledger the overlay (mandatory)

Re-seed overwrites the volume with packaged source. Any divergence that must be
**kept** (an intentional per-lane overlay) has to be recorded first, or it is
lost. Record the diff and the keep/drop decision in the deploy evidence / proof
packet:

```
config: bifrost_delegation
deployed_sha256: <from sidecar>
source_sha256:   <from sidecar>
overlay_diff: <paste unified diff>
decision: re-seed from packaged source; overlay <kept via env|dropped as stale>
```

Overlays are expressed through **env-driven render inputs** (e.g. `base_url_env`
backends) or the secrets manager — never by hand-editing the volume copy. A hand-edited
volume copy is exactly the drift this runbook exists to eliminate.

### 3. Re-seed (mutating — requires lane approval)

```bash
# Remove the stale volume copy + sidecar so the next render writes fresh from source:
docker exec <runtime-container> sh -c \
  'rm -f /app/data/delegation/bifrost_delegation.yaml /app/data/delegation/.config_provenance.json'

# Re-render from packaged source (re-runs the entrypoint render path):
docker exec <runtime-container> \
  python -m omnibase_infra.runtime.render_bifrost_delegation_contract
```

Then restart the runtime container per the lane's standard deploy step so the
freshly rendered contract is loaded.

### 4. Verify

```bash
docker exec <runtime-container> cat /app/data/delegation/.config_provenance.json
# expect: has_drifted == false, deployed_sha256 == source_sha256
```

Re-run the drift sweep (below) and confirm zero drift findings.

## Drift sweep (continuous)

```bash
cd omnimarket
uv run python -m omnimarket.nodes.node_volume_config_drift_sweep --dry-run
```

The sweep reads the provenance sidecar on each runtime lane (or computes
provenance from a probed volume copy + packaged source), classifies
`IN_SYNC` / `DRIFTED` / `DEPLOYED_ABSENT` / `SOURCE_ABSENT`, and — outside
`--dry-run` — auto-creates a Linear ticket for any `DRIFTED` lane. Its JSON output
is suitable for inclusion in proof packets.
