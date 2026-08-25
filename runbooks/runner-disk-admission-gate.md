---
type: runbook
status: current
date: "2026-08-24"
title: "Runner disk-admission gate (<ticket>)"
topics: [omnibase-infra, runner, disk, admission, gate]
refs: []
---

# Runner disk-admission gate (<ticket>)

Structural fix for the `<onex-host>` runner-fleet ENOSPC write-amplification loop
(<ticket>, recurred twice on 2026-08-22 — see comments on <ticket>).

## Layer 0: filesystem reserve

**What:** `<onex-host>`'s `/data` volume (`/dev/nvme2n1p1`, 3.6TB ext4, backs the
entire runner fleet's Docker storage) ships with ext4's default 5%
root-reserved-blocks allocation — space `mkfs.ext4` sets aside that only
`root` can write into, even when `df` reports the volume as full to
non-root processes. On a 3.6TB volume, 5% is ~180GB permanently
inaccessible to the non-root users that own the runner-fleet Docker writes.
On 2026-08-22 ~22:1xZ, during the live ENOSPC write-amplification incident
(see below), incident responder `disk-recovery-201-4` ran:

```bash
sudo tune2fs -m 1 /dev/nvme2n1p1
```

dropping the reserve from 5% to 1% and surfacing roughly 150GB that
non-root CI writers could not previously touch. This ended the incident's
**hard-zero ENOSPC** condition — writers were hitting a hard 0 bytes
available while `tune2fs -l` showed ~190GB of the volume still existed,
root-reserved. **Operator ruling (2026-08-23): KEEP the 1% reserve and
formalize it as Layer 0** — it is the precondition underneath Layers 1/2
below; a runner mount at the 5% default reaches its effective-zero
condition ~150GB sooner than the same physical fill level does at 1%.

**Why 1% and not 0%:** ext4's root reserve exists so root-owned recovery
tooling (fsck, log rotation, emergency cleanup) can still write when a
volume is nominally full — dropping to 0% would remove that margin
entirely. 1% of 3.6TB (~36GB) preserves a working reserve for root while
still returning the vast majority of the previously-locked space to
non-root writers; this repo's own runner fleet, disk-admission gate
(Layer 1 below), and disk-GC timers all run as non-root.

**When this applies / fault signature:** if `<onex-host>`'s `/data` volume is
ever recreated, reformatted, or replaced (new drive, RAID rebuild, fresh
`mkfs.ext4`), the reserve resets to ext4's 5% default and this fix must be
reapplied — it is a filesystem property, not something any of the
Docker/compose/runner-fleet layers persist. Diagnose a reserve-related
false "out of space" the same way the live incident was diagnosed: `df -h
/data` reports 0 (or near-0) bytes available to a non-root check while
`sudo tune2fs -l /dev/nvme2n1p1 | grep -i reserved` shows a nonzero
`Reserved block count` well above what 1% of the volume should be — that
gap is inaccessible-to-non-root space, not real exhaustion, and a
`resize2fs`/disk-add will not fix it (only `tune2fs -m` will).

**Revert (if ever needed):**

```bash
sudo tune2fs -m 5 /dev/nvme2n1p1
```

Reverting restores ext4's 5% default and re-locks ~150GB from non-root
writers — this reintroduces the exact effective-capacity shortfall that
triggered the 2026-08-22 incident, so only do this on an explicit operator
decision, not as routine maintenance.

**Verification:** `sudo tune2fs -l /dev/nvme2n1p1 | grep -i 'block count\|reserved block count'` —
`Reserved block count` should be ~1% of `Block count`, not ~5%.

## The mechanism this breaks

When the shared Docker storage volume backing the runner fleet runs low, a
job dispatched to a runner fails almost instantly with ENOSPC — but not
before `actions/checkout`, `uv sync`, and docker build/layer writes have
already landed a partial write on disk (ENOSPC is only raised once a write
actually cannot complete; every byte written before that point is real,
already-committed disk consumption). With dozens of runners cycling through
repeated instant-fail-and-reassign, the aggregate partial-write throughput
across the fleet outpaces `docker builder prune`/`docker image prune`,
turning a recoverable low-disk condition into a self-perpetuating
write-amplification loop that drives free space to zero within roughly
15–20 minutes.

## The fix: two layers

### 1. Pre-job disk-admission gate (primary, live immediately, no recreate)

`docker/runners/runner-job-started.sh` now runs `disk_admission_gate()` as
the very first action — before the workspace `rm -rf`, before the git-mirror
pre-seed, before `wire_pypi_cache`. When free space on the runner's own
workspace mount is below `RUNNER_DISK_ADMISSION_MIN_FREE_GB` (default 5 GB,
matching `.github/workflows/runner-disk-preflight.yml`'s
`RUNNER_DISK_WARN_GB` default — <ticket> AC3), the job fails immediately
with a `::error title=RUNNER-DISK-ADMISSION:<free>GB::` annotation, **before
any of the write-heavy steps run**. This caps every rejected job's I/O
contribution to a single `df` call instead of however many megabytes a
partial checkout/cache-write burns before the kernel actually returns
ENOSPC.

This file is bind-mounted read-only from the host
(`docker/runners/runner-job-started.sh` → `~/.omnibase/runners/docker/runners/runner-job-started.sh`
on `<onex-host>`), so **deploying this layer requires no container recreate** —
copying the updated file to the host changes behaviour on every runner at
its next job start.

**What this layer does not do**: a self-hosted runner has no API to
decline/requeue a job GitHub has already dispatched to it, so the runner is
still reassigned immediately after failing. The rapid-reassignment cycling
continues; only the write cost of each cycle drops to ~0, which is the
variable the incident evidence identifies as the amplification driver (write
throughput outpacing reclamation, not reassignment frequency by itself).

### 2. Consecutive-failure self-pause + guarded restore (defense in depth, requires a fleet recreate to activate)

If a runner logs `RUNNER_DISK_ADMISSION_BACKOFF_N` (default 3) consecutive
admission failures, `disk_admission_self_pause()` writes a durable pause
marker and stops its own container via the already-bind-mounted Docker
socket (`docker stop`, never `docker restart`/recreate — the container's
`restart: unless-stopped` policy honors an explicit stop). This is the only
way a self-hosted runner can actually stop accepting new job assignments —
matching fix direction #2 from the ticket ("backoff-on-repeated-instant-
setup-failure guard").

A new host-side timer (`deploy/disk-gc/onex-runner-disk-guard.timer`, every
2 minutes — deliberately far tighter than the hourly `onex-disk-gc.timer`,
because the incident window is ~15–20 minutes) runs
`scripts/runner-disk-admission-restore.sh`, which restores paused runners
using the **slope-plus-canary** criterion documented on <ticket> (a fixed
absolute free-space threshold restored too conservatively during the live
incident; sustained *positive slope* across a small canary batch is what
actually worked): free space must be above `RUNNER_DISK_GUARD_RESTORE_FLOOR_GB`
(default 40 GB) **and climbing** for `RUNNER_DISK_GUARD_CLIMB_TICKS_REQUIRED`
(default 2) consecutive ticks before the first batch (`RUNNER_DISK_GUARD_BATCH_SIZES`,
default `10 20 20 20 20`) releases; each subsequent batch requires the climb
criterion to be re-proven from scratch. A tick where free space is flat or
declining halts further batches without undoing an already-restored one —
the documented stop signal from the live incident.

This layer requires a **new compose volume**
(`${RUNNER_DISK_ADMISSION_PAUSE_HOST_DIR:-./state/disk-admission-pause}` →
`/home/runner/.onex-disk-admission-pause`, added to every `omninode-runner-N`
service in `docker/docker-compose.runners.yml`) so the host-side restore
script can see which runners the gate paused. **Until the fleet is recreated
to pick up this volume, `disk_admission_self_pause()` fails open** (logs
"self-pause skipped: ... not mounted", takes no action) — layer 1 above is
unaffected and is already the primary, immediately-effective mechanism.

## Rollout

0. **Layer 0 (already applied live on `<onex-host>`, no action needed unless the
   `/data` volume is ever recreated)**: `sudo tune2fs -m 1 /dev/nvme2n1p1`
   was run during the 2026-08-22 incident and confirmed by operator ruling
   to stay in place. Re-verify with the command in the Verification
   subsection above if `/data` is ever rebuilt.
1. **Layer 1 (do this first, low risk, no recreate)**: copy the updated
   `docker/runners/runner-job-started.sh` to the host bind-mount path on
   `<onex-host>` (`~/.omnibase/runners/docker/runners/runner-job-started.sh`).
   Effective at each runner's *next* job start.
2. **Install the restore-guard timer** (safe, does not touch any runner
   container):
   ```bash
   bash deploy/disk-gc/install-runner-disk-guard.sh
   ```
3. **Layer 2 (requires a fleet recreate — canary first, per the runner-fleet
   canary-before-roll rule)**: after `docker/docker-compose.runners.yml`'s
   new volume is deployed to `<onex-host>`, recreate a small canary batch first
   (e.g. `omninode-runner-1/2/3`) via
   `docker compose -f docker/docker-compose.runners.yml up -d --force-recreate --no-deps omninode-runner-1 omninode-runner-2 omninode-runner-3`
   with a fresh `RUNNER_TOKEN`, verify they register healthy, then roll the
   remainder in batches using the same safe-bounce recipe `runner-monitor.sh`
   already documents (never an empty service filter, never `docker restart`).

## Verification

- `RUNNER-DISK-ADMISSION` annotations appear in job logs during a low-disk
  window (searchable the same way `RUNNER-DISK:` annotations from the
  existing preflight are).
- `systemctl --user status onex-runner-disk-guard.timer` on `<onex-host>` shows the
  timer firing every 2 minutes.
- `ls ~/.omnibase/runners/docker/state/disk-admission-pause/` (once layer 2
  is rolled out) lists any currently self-paused runners.
- Regression/simulation tests (<ticket> AC2):
  `tests/scripts/test_runner_job_started_disk_admission.py` and
  `tests/scripts/test_runner_disk_admission_restore.py`.

## Threshold consistency (AC3)

| Threshold | Default | Source |
|---|---|---|
| Admission floor (`RUNNER_DISK_ADMISSION_MIN_FREE_GB`) | 5 GB | matches `runner-disk-preflight.yml`'s `RUNNER_DISK_WARN_GB` |
| Backoff count (`RUNNER_DISK_ADMISSION_BACKOFF_N`) | 3 consecutive failures | new (<ticket>) |
| Critical floor (`RUNNER_DISK_GUARD_CRITICAL_FLOOR_GB`) | 15 GB | new (<ticket>) — below this, restore never acts |
| Restore floor (`RUNNER_DISK_GUARD_RESTORE_FLOOR_GB`) | 40 GB | new (<ticket>) — matches the live incident's working range |
| Climb ticks required (`RUNNER_DISK_GUARD_CLIMB_TICKS_REQUIRED`) | 2 | new (<ticket>) |

The two host-side thresholds (admission floor, host-side) and the GH-Actions
workflow threshold cannot share a single config file (different execution
contexts — one runs inside the job on whichever runner picked it up, the
other runs host-side pre-job); they are kept in sync by comment
cross-reference, the same pattern already used for the wedge-detection
thresholds in `docker/runners/runner-monitor.sh`.

## Layer 0b: buildx ephemeral-builder orphan sweep (<ticket>)

A structurally separate leak found during the same 2026-08-22 incident
chain, orthogonal to Layers 0-2 above: `docker/setup-buildx-action` (or a
direct `docker buildx build --driver docker-container` invocation) with no
pinned builder `name` creates a NEW `buildx_buildkit_<name>` container +
`<name>_state` cache volume on every invocation. Self-hosted runners are not
ephemeral VMs, so nothing tears that container down when the job exits, and
because the name is never reused it is never registered again in
`docker buildx ls` — making it invisible to and unreachable by
`docker builder prune`/`docker buildx prune`, which only reclaim cache
belonging to a currently-registered builder. Manual sweeps on
2026-08-22/23 found 3-5 such orphans per pass, several GB each, recurring
within ~20 minutes of the previous cleanup.

**Two-part fix, same pattern as Layers 1/2 above (prevent + reclaim):**

1. **Prevent new orphans** — `.github/workflows/docker-build.yml`'s
   `docker/setup-buildx-action` step (the sole call site in this repo using
   the `docker-container` driver, which is the only driver that creates a
   backing container) now pins `name: onex-shared-buildkit`. A pinned name
   makes the action detect and reuse the existing builder instance instead
   of generating a random one every run, so the fleet converges on ONE
   persistent, always-registered builder instead of leaking one per job.
2. **Reclaim existing orphans** — `scripts/buildx-orphan-sweep.sh`, driven
   by `deploy/disk-gc/onex-buildx-orphan-sweep.timer` (systemd USER unit,
   same install pattern as `onex-runner-disk-guard.timer`: install via
   `bash deploy/disk-gc/install-buildx-orphan-sweep.sh` on `<onex-host>`, no sudo).
   Removes a `buildx_buildkit_*` container (and its own
   `buildx_buildkit_`-prefixed state volume) only when ALL three hold —
   the exact criteria used in the live manual sweeps:
   - **Unregistered**: the node name embedded in the container name is not
     currently listed under `docker buildx ls`.
   - **Idle**: a stopped container is trivially idle; a running one must
     show 0% CPU AND byte-identical cumulative block I/O across two
     samples ~60s apart (never kill a builder mid-build).
   - **>60 minutes old** (`docker inspect .Created`) — gives a
     just-created builder time to be claimed or finish its first job.

   15-minute cadence (looser than the 2-minute admission-guard timer above
   — this leak is continuous but low-grade, not the acute 15-20 minute
   write-amplification window Layer 2 exists for).

**Verification:**
- `systemctl --user status onex-buildx-orphan-sweep.timer` on `<onex-host>` shows
  the timer firing every 15 minutes.
- `bash scripts/buildx-orphan-sweep.sh` (dry-run, default) prints candidates
  without mutating; `--execute` actually removes; `--json` for a
  machine-readable plan/result.
- Regression/simulation tests: `tests/scripts/test_buildx_orphan_sweep.py`.
