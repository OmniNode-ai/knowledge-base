---
type: runbook
status: current
date: "2026-07-21"
title: "Stability-Lane Refresh (<ticket> / <ticket>)"
topics: [omnibase-infra, stability, lane, refresh]
refs: []
---

# Stability-Lane Refresh (<ticket> / <ticket>)

Canonical procedure for refreshing the `<onex-host>` stability-test proof lane
(compose project `omnibase-infra-stability-test`, ports 18085/18086) to a
named ref, with a health-gate and automatic rollback-on-failure. Supersedes
the tribal-knowledge manual recipe (memory `reference_workspace_deploy_gotchas`,
`reference_stability_lane_stale_no_refresh_cadence`) — those memories remain
useful history, but the mechanism below is the durable, checked-in surface.

For the lane's initial setup / compose-overlay contents, see
`docs/runbooks/stability-test-runtime-lane.md`. This runbook is about
**refreshing** an already-provisioned lane, not standing one up.

## Why this exists

The stability-test lane is the "preferred proof lane for synthetic
integration evidence" (CLAUDE.md), but had no refresh cadence: it silently ran
whatever code happened to be there the last time someone manually rebuilt it.
<ticket>'s 2026-07-10 readback found the lane running an image 7 days stale,
predating the very seam merge it was supposed to prove (<ticket>). Manual
refreshes since then have worked, but relied on operator memory of an
undocumented gotcha (4 release-only services fail to build in workspace mode)
and had no rollback or health-gate — a failed manual refresh could leave the
lane silently unhealthy for the next session to discover cold.

## The command

```bash
export OMNI_HOME=/data/omninode/omni_home   # <onex-host> path; do not hardcode elsewhere

# Dry-run (default): prints the plan, mutates nothing.
omnibase_infra/scripts/runtime_build/refresh_stability_lane.sh --ref origin/dev

# Execute:
omnibase_infra/scripts/runtime_build/refresh_stability_lane.sh --ref origin/dev --execute
```

Run this **on `<onex-host>`, from the canonical `omnibase_infra` clone** — the same
way `deploy-runtime.sh` and `cut-lab-ref.sh` already run. It is not a
worktree operation and does not ssh-wrap individual commands; it drives
Docker/git directly against the live lane.

Flags:

| Flag | Default | Meaning |
|---|---|---|
| `--ref <ref>` | `origin/dev` | The ref to refresh the lane to (branch, tag, or SHA). |
| `--min-contracts <n>` | `288` | Manifest contract-count floor for the health-gate. Never lower this without a documented reason — it should only ever ratchet up as the platform grows. |
| `--manifest-url` | `http://localhost:18085/v1/introspection/manifest` | Override for a non-default lane host/port. |
| `--health-url` | `http://localhost:18085/health` | Override for a non-default lane host/port. |
| `--execute` | off | Actually mutate. Omit for a dry-run plan. |

There is deliberately **no `--lane` flag**. This script is hardcoded to the
stability-test lane only (mirrors `cut-lab-ref.sh`'s lane refusal for
prod/judge) — it is not a generic multi-lane tool.

## What it does

1. **Captures pre-state**: running image ID + `org.opencontainers.image.revision`
   label for the 4 core services, and the current HEAD SHA of every tracked
   repo (`omnibase_infra`, `omnibase_core`, `omnibase_compat`,
   `onex_change_control`, `omnimarket`).
2. **Tags a preflight rollback anchor**: `<project>-<service>:latest` ->
   `<project>-<service>:preflight-<UTC>` for the 4 core services, captured
   *before* any build can overwrite `:latest` in place.
3. **Refreshes the `omnibase_infra` ambient clone itself** to `--ref` (this is
   the repo `deploy-runtime.sh` reads its own `git_sha`/build context from —
   it is NOT one of the `DEPLOY_REF`-pinned siblings).
4. **Builds + restarts, scoped to the 4 known-good core services**
   (`omninode-runtime`, `runtime-effects`, `runtime-worker`, `projection-api`)
   via `deploy-runtime.sh`, using the new `RUNTIME_BUILD_SERVICES_OVERRIDE` env
   var (additive; every other caller is unaffected — see below). This routes
   around the still-open BUILD_SOURCE selector-mismatch defect on the 4
   release-only services (`agent-actions-consumer`, `skill-lifecycle-consumer`,
   `intelligence-api`, `omninode-contract-resolver`; <ticket> residual) as a
   **controlled decision**, not a side effect of a partial build failure the
   way the manual recipe worked.
5. **Asserts forward progress**: `git merge-base --is-ancestor <prior> <new>`
   for every tracked repo. A regression (a stale/tampered ref that would move
   the lane BACKWARD) does not get certified as a success even if the
   health-gate happens to pass.
6. **Runs the health-gate** (`verify_stability_refresh.py`): digest changed,
   manifest contract-count floor, `/health`, `rpk cluster health`, declared
   consumer groups Stable (`consumer_groups_stability.yaml`), and
   image-revision readback.
7. **On PASS**: prunes old `preflight-*` tags (keeps last 3) and writes a
   `SUCCESS` receipt.
8. **On FAIL**: rolls back all 4 core services to the preflight tag, targeted-
   recreates them, and re-runs the health-gate against the rolled-back state
   (this second pass skips the digest-changed check via
   `--no-require-digest-change`, since the rolled-back image is deliberately
   the OLD one). If that PASSes, the receipt records `FAILED_ROLLED_BACK`
   (refresh failed, but the lane is healthy). If it also fails, the receipt
   records `FAILED` and the script prints a STOP-AND-REPORT block — **this is
   not a retry-until-green loop**; per operating rules a still-unhealthy lane
   after rollback is a human escalation, and (per
   `feedback_auto_file_tickets_on_breakage`) should get a Linear ticket filed
   the same session it is discovered.

## The `RUNTIME_BUILD_SERVICES_OVERRIDE` mechanism

`deploy-runtime.sh` builds/restarts a hardcoded `RUNTIME_SERVICES` array (8
services). `RUNTIME_BUILD_SERVICES_OVERRIDE` (space-separated service names)
scopes both `build_images()` and `restart_services()` to a subset when set;
unset (the default), behavior is byte-for-byte unchanged for every existing
caller (prod, dev, `cut-lab-ref.sh`, the `--cold` full bring-up). Only
`refresh_stability_lane.sh` sets it, to the 4 known-good core services.

## The receipt

Every run (via `--execute`) writes:

- **Latest pointer**: `~/.omnibase/state/stability_lane_refresh/latest.json`
  (overwritten each run) — the cheap read for "is the lane fresh right now."
- **History**: `~/.omnibase/state/stability_lane_refresh/history/<UTC>-<shortsha>.json`
  (append-only, one per run).

These are host-local operational telemetry on `<onex-host>` (same category as
`.onex_state/`), never git-committed by the script.

Schema:

```json
{
  "ts_utc": "2026-07-20T23:00:00Z",
  "lane": "stability-test",
  "prior_refs": {"omnibase_infra": "...", "omnibase_core": "...", "...": "..."},
  "new_refs": {"omnibase_infra": "...", "omnibase_core": "...", "...": "..."},
  "ancestry_proof": {"merge_base_is_ancestor": true, "commands": ["git merge-base --is-ancestor ..."]},
  "build_scope": ["omninode-runtime", "runtime-effects", "runtime-worker", "projection-api"],
  "health_gate": {
    "digest_changed": true, "manifest_count": 291, "manifest_ok": true,
    "health_ok": true, "cluster_healthy": true,
    "consumer_groups": {"<group>": "Stable"}, "consumer_groups_stable": true,
    "revision_readback_ok": true, "overall": "PASS"
  },
  "rollback": {"triggered": false, "gate": null},
  "result": "SUCCESS"
}
```

`result` is one of `SUCCESS`, `FAILED_ROLLED_BACK`, or `FAILED`.

**Trusting freshness without re-probing**: `ssh omni-201-ts 'cat ~/.omnibase/state/stability_lane_refresh/latest.json'`
replaces the whole forensic chain (label diffing, `merge-base`, live health
probe) that prior sessions had to do by hand to answer "is this lane
current." Read the receipt FIRST; only fall back to live probing if the
receipt is missing, stale beyond a reasonable window, or its `result` is not
`SUCCESS`.

## Cadence: NOT yet wired

There is deliberately no cron/GHA trigger for this script yet. Per
`feedback_no_landing_automation_before_process_measured` and the
graded-escalating-eval doctrine (`feedback_delegation_graded_benchmarks`), a
single clean run does not qualify a mechanism for unattended cadence. The bar
before opening a follow-up ticket to wire cadence: **>= 5 consecutive
operator-invoked refreshes**, each either a clean health-gate PASS or a
proven rollback-to-healthy on an induced failure, with zero silent false
greens. Track progress in the parent ticket (<ticket>) or its refresh-cadence
follow-up child ticket.

Recommended cadence once that bar is met: a scheduled pull-to-`origin/dev`
refresh every 4-6h (or nightly) on `<onex-host>` — not a per-repo dev-push webhook.
The lane depends on 5 tracked repos; a merge to any one of them can leave it
stale, and a scheduled refresh bounds staleness by a fixed ceiling regardless
of which repo merged. A repo-push fast-path trigger is a reasonable
supplement later, not a substitute.

## Manual rollback (if the script itself is unavailable)

The preflight tags this script creates (`<project>-<service>:preflight-<UTC>`)
are ordinary Docker tags and can be restored by hand if needed:

```bash
docker images --format '{{.Repository}}:{{.Tag}}' | grep 'omnibase-infra-stability-test-.*:preflight-'
# pick the desired preflight-<UTC> tag, then for each of the 4 core services:
docker tag omnibase-infra-stability-test-<service>:preflight-<UTC> omnibase-infra-stability-test-<service>:latest
docker compose -p omnibase-infra-stability-test \
  -f docker/docker-compose.infra.yml -f docker/docker-compose.stability-test.yml \
  --profile runtime up -d --no-deps --no-build --force-recreate \
  omninode-runtime runtime-effects runtime-worker projection-api
```

## Tests

`scripts/runtime_build/tests/test_verify_stability_refresh.py` unit-tests the
health-gate module (mocked docker/HTTP, no live lane required): the
PASS/FAIL boundary at exactly `min_contracts`, digest-unchanged -> FAIL,
revision-mismatch (exists-but-wrong, not a silent pass), and the
rollback-re-verification receipt logic (including the "rollback ALSO fails"
branch staying `FAILED`, never masked as success).
