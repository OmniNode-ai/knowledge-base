---
type: runbook
status: current
date: "2026-07-21"
title: "Merge-Triggered Worktree GC — Two-Layer Model (Event-First + Timer-Backstop)"
topics: [omnibase-infra, worktree, reaper, two, layer]
refs: []
---

# Merge-Triggered Worktree GC — Two-Layer Model (Event-First + Timer-Backstop)

**Owners:** runtime host systemd units in `deploy/disk-gc/`; Mac launchd daemon in
`omniclaude/scripts/worktree-reaper-daemon.sh`.

## Why this exists

Stale worktrees for already-merged PRs accumulate under the worktrees root and —
alongside docker images — filled `/data` on the runtime host during a prior demo-day
incident. The fix is to garbage-collect a worktree as soon as its PR
merges, removing ONLY worktrees whose PR is merged (or whose remote branch is
gone) AND that are clean AND fully pushed.

A purely periodic sweep is too slow (a worktree can linger up to an hour) and a
purely event-driven reaper is not durable (events get dropped; the daemon can be
down during a merge). So GC runs as **two layers that converge on the same end
state** — every merged-and-clean worktree removed — using the SAME safety core.

## The two layers

| Layer | What | Trigger | Latency | Cursor |
|-------|------|---------|---------|--------|
| **1 — event-first** | Reap each newly-merged PR's worktree | `onex.evt.github.pr-merged.v1` projection read `?since=<cursor>` | Reaped within one poll interval of the merge event materializing (target 60 s) | Advances a monotonic cursor on a fully-successful execute pass |
| **2 — timer-backstop** | Cursor-INDEPENDENT full reconciliation: reap ALL already-merged worktrees still present | Periodic timer (hourly) + once on daemon start | Up to one backstop interval | None — it is a reconciliation, not a windowed advance |

Layer 1 is the steady-state fast path. Layer 2 is the safety net for events that
were **missed during downtime or dropped before the cursor advanced**: it scans
every worktree directly and lets the prune safety decide, regardless of the
cursor. Because Layer 2 never touches the cursor, it can never regress or skip
Layer 1's watermark — the two layers are independent and both converge.

### Shared safety core (both layers)

Neither layer re-implements GC safety. Both drive the canonical
`omniclaude/scripts/prune-worktrees.sh`, which removes a worktree ONLY when:

- its PR is **MERGED** (or the remote branch is gone), **AND**
- the working tree is **clean** (no uncommitted changes → otherwise SKIP), **AND**
- there are **no unpushed commits** (no-upstream defaults to SKIP, never DELETE).

Detached-HEAD and dirty worktrees are SKIPPED, never deleted. Salvage of dirty worktrees is out of scope for this runbook. Default-SKIP on any ambiguity:
a prune failure, a projection fetch error, or a malformed event leaves the cursor
un-advanced (Layer 1) or the root marked failed for retry (Layer 2).

## Runtime host (systemd, user scope — no sudo)

Two coexisting systemd USER units in `deploy/disk-gc/`, installed independently.
**Both are retained — neither replaces the other.**

| Unit | Role | Cadence | Install |
|------|------|---------|---------|
| `onex-worktree-reaper.timer` → `.service` | Layer 1 event-first reaper | every 2 min (`OnCalendar=*:0/2`) | `bash deploy/disk-gc/install-worktree-reaper.sh` |
| `onex-disk-gc.timer` → `.service` | Layer 2 backstop (worktree GC + docker GC + watermark) | hourly (`OnCalendar=hourly`) | `bash deploy/disk-gc/install-disk-gc.sh` |

`onex-disk-gc.service` runs three conservative passes in order: `worktree-gc.sh`
(drives `prune-worktrees.sh`), `disk-gc.sh` (docker/builder/image GC honoring the
keep-list), and `disk-watermark-check.sh` (emits a bus alert if `/data` crosses
the watermark). The hourly worktree-GC pass IS the Layer 2 backstop on the runtime host.

> **Retention rule (T6):** `onex-disk-gc.timer` must stay installed as the
> hourly backstop. Do NOT remove it when the event-first reaper is running — the
> reaper handles steady state, the hourly timer reconciles missed events. They
> coexist by design.

Verify both are armed:

```bash
systemctl --user list-timers 'onex-*'
systemctl --user status onex-worktree-reaper.timer   # Layer 1, ~2 min
systemctl --user status onex-disk-gc.timer           # Layer 2, hourly
journalctl --user -u onex-disk-gc.service -f          # backstop sweep logs
```

## Mac (launchd KeepAlive daemon)

launchd **periodic** jobs do not fire reliably on this Mac
(`feedback_local_durability`). So the Mac packs BOTH layers into a single
**resident KeepAlive daemon** — `ai.omninode.worktree-reaper.plist` runs
`omniclaude/scripts/worktree-reaper-daemon.sh`, which execs
`omniclaude/scripts/worktree_reaper.py --execute --loop`:

- **Layer 1** runs every `ONEX_REAPER_INTERVAL` seconds (default 60) — the fast
  event poll.
- **Layer 2** runs once on daemon start (reconciling anything missed while the
  daemon was down) and then every `ONEX_REAPER_CATCH_UP_INTERVAL` seconds
  (default 3600 = hourly), the Mac equivalent of the runtime host's `onex-disk-gc.timer`.
  Set `ONEX_REAPER_CATCH_UP_INTERVAL=0` to disable the periodic backstop.

The catch-up sweep is `run_catch_up_sweep()` in `worktree_reaper.py`: it drives
`prune-worktrees.sh` directly across every root (cursor-independent) so it reaps
ALL already-merged worktrees still present, not just the since-cursor window.

Run a one-shot backstop sweep manually (needs no projection URL — it drives prune
directly):

```bash
# dry-run reconciliation (default; reports, never deletes)
python omniclaude/scripts/worktree_reaper.py --catch-up
# real reconciliation
python omniclaude/scripts/worktree_reaper.py --catch-up --execute
```

Install / inspect the daemon:

```bash
bash omniclaude/scripts/install-worktree-reaper-daemon.sh
launchctl list | grep ai.omninode.worktree-reaper
```

## Convergence proof

Both layers are proven to converge on the same end state:

- **Layer 1 (event path)** — proven via integration test: a throwaway merged PR's
  worktree is reaped within one poll interval; the cursor advances; dirty /
  unpushed worktrees SKIP. Tests in `omniclaude/tests/scripts/test_worktree_reaper.py`
  (`test_merged_clean_row_drives_prune_script`, `test_dirty_or_unpushed_worktree_is_skipped`).
- **Layer 2 (backstop / catch-up)** — proven via integration test:
  `test_catch_up_sweep_converges_on_seeded_stale_merged_worktree_and_skips_dirty`
  seeds a stale-but-merged worktree and a dirty merged worktree, runs the catch-up
  sweep through the real prune subprocess path, and asserts the clean one is
  removed while the dirty one is SKIPPED and left intact. The catch-up sweep never
  touches the cursor (`test_catch_up_sweep_never_touches_cursor`), so it cannot
  regress Layer 1.

Convergence: whether a merge is caught by the cursor window (Layer 1) or a full
scan (Layer 2), the worktree is reaped under the same safety. A missed or dropped
event is reconciled within one backstop interval; the event path keeps that
window small in steady state.

## Related docs

- `omniclaude/scripts/worktree_reaper.py` — the Mac reaper (both layers).
- `omniclaude/scripts/prune-worktrees.sh` — the shared safety core.
- `scripts/worktree-gc.sh` — the runtime host driver invoked by `onex-disk-gc.service`.
- `deploy/disk-gc/` — runtime host systemd units (`onex-worktree-reaper.*`,
  `onex-disk-gc.*`) and installers.
