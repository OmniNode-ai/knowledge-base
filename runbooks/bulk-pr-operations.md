---
type: runbook
status: current
date: "2026-09-12"
title: "Bulk PR operations — mandatory throttled path (<ticket>)"
topics: [omnibase-infra, bulk, pr, operations]
refs: []
---

# Bulk PR operations — mandatory throttled path (<ticket>)

## Why this exists

At ~01:45Z on 2026-08-20 a merge-sweep lane armed/update-branched ~108 PRs
in one unthrottled burst. Update-branching triggers a full fresh
check-suite per PR; `onex_change_control` PRs alone carry ~63 checks each
(~19 needing `[self-hosted, omnibase-ci]` runners). Result: OCC's queued-run
count grew to ~1065, the shared org-level runner pool (88 runners,
`visibility=all`, no per-repo fair-share) sat 77-88/88 busy for ~4 hours, and
every landing chain org-wide (core, OCC, infra, omnimarket) starved. The
burst then settled ~95-100% RED from incident-window transients, producing
exactly **1 merge out of ~108**.

This is distinct from <ticket> (self-amplified bot-edit re-triggering —
a debounce fix on the *reactive* side). This runbook is the *dispatch*
side: nothing mechanically capped how many check-suites a bulk operation
could enqueue at once. The rule ("throttle, serialize heavy work") existed
only in prose and did not bind — same failure class documented in memory
`feedback_a_rule_is_not_a_mechanism`.

## The mandatory path

**Every supported bulk PR operation — update-branch, arming/auto-merge sweeps,
and mass reruns — routes through
`scripts/ci/bulk_pr_throttle.py`.** Do not hand-roll a `for pr in $prs; do gh
... ; done` loop for more than a small handful of PRs. That loop is exactly
the failure mode this ticket exists to close.

```bash
# Plan only — no gh calls, no mutation:
uv run scripts/ci/bulk_pr_throttle.py \
  --owner OmniNode-ai --repo onex_change_control \
  --prs 6751,6752,6753,6754,6755 \
  --operation rerun-failed \
  --dry-run

# Real run — processes in wave-size-10 batches by default. Local runs require
# RUNNER_FLEET_STATUS_TOKEN with organization-runner read access. The existing
# CROSS_REPO_PAT is accepted as a fallback in CI-compatible environments:
export RUNNER_FLEET_STATUS_TOKEN="<org-runner-read-token>"
uv run scripts/ci/bulk_pr_throttle.py \
  --owner OmniNode-ai --repo onex_change_control \
  --prs 6751,6752,6753,6754,6755 \
  --operation rerun-failed
```

### Operations supported

| `--operation` | What it does per PR |
| --- | --- |
| `update-branch` | `PUT /repos/{owner}/{repo}/pulls/{pr}/update-branch` — triggers a fresh check-suite. The single highest-cost operation; this is what caused the incident. |
| `arm-automerge` | `gh pr merge <pr> --squash --auto` |
| `rerun-failed` | Resolves the PR's head SHA, lists completed workflow runs, and reruns failed jobs for runs with `conclusion` equal to `failure` or `cancelled`. |
| `noop-dry-run` | No-op outcome, always succeeds — for exercising wave/threshold logic without touching `gh` at all. |

### Flags

| Flag | Default | Notes |
| --- | --- | --- |
| `--owner` / `--repo` | **required, no default** | Fail-fast: never silently assume an org/repo. |
| `--prs` | **required** | Comma-separated PR numbers. |
| `--operation` | **required** | One of the four above. |
| `--wave-size` | 10 | Flag-overridable up to a **hard ceiling of 25** (`MAX_WAVE_SIZE` in the script) — not overridable past that point by any flag. |
| `--queue-depth-threshold` | 150 | Legacy receipt field retained for wire compatibility. Queue depth is observed before and after each wave; it does not authorize or refuse dispatch. |
| `--max-total-prs` | 50 | Batches larger than this are **refused** unless you pass `--max-total-prs <n>` explicitly, raising the cap for that invocation. There is no flag that skips this check entirely — only one that raises the number, so oversized batches are always a stated, visible choice. |
| `--poll-seconds` | 30 | How often to re-poll matching runner capacity while blocked. |
| `--max-wait-seconds` | 1800 | If no matching idle runner appears within this window, the tool **raises and stops** — it does not silently proceed into a saturated fleet. |
| `--dry-run` | off | Prints the wave plan; makes zero `gh` calls. |
| `--receipt` | `.onex_state/bulk-pr-throttle/<owner>-<repo>-<ts>.json` | Where the JSON wave receipt is written. |

## The mechanical guard

Per CLAUDE.md rule 5 ("detection without enforcement gets ignored"), the
throttle is not advisory prose — it is load-bearing in the tool itself:

- The runner-capacity gate (`wait_for_runner_capacity` in
  `bulk_pr_throttle.py`) has
  **no bypass parameter** anywhere in the module or its CLI — no `--force`,
  no `--skip-throttle`, no `--ignore-capacity`. A caller cannot opt out of
  throttling short of not using this tool at all.
- Before every load-creating wave, the tool reuses the shared fleet probe and
  filters for the `omnibase-ci` runner group. At least one online, non-busy
  matching runner is capacity; a deep queued-run count alone is not
  starvation. Queue depth remains visible in logs and receipts as an
  observation.
- Local runs must provide `RUNNER_FLEET_STATUS_TOKEN`; the existing
  `CROSS_REPO_PAT` environment value is the fallback. Missing credentials or
  an unreadable fleet are not treated as spare capacity. The tool refuses and
  names the stable probe error: `missing_token`, `bad_api_scheme`,
  `http_<status>`, `timeout`, `malformed_json`, or `empty_fleet`.
- `--wave-size` is capped at `MAX_WAVE_SIZE` (25) in code, not just by
  default — passing a larger value is a hard refusal
  (`ValueError`/exit code 1), not a warning.
- Processing more than `--max-total-prs` PRs without explicitly raising the
  cap is a hard refusal before any `gh` call is made (`TotalPrLimitExceededError`).
- A valid fleet sample with zero matching idle runners is re-polled only until
  `--max-wait-seconds`, then ends in a hard refusal
  (`RunnerFleetStarvationTimeoutError`), not a silently-skipped wave.

**What is NOT yet wired (controller follow-up, out of scope for this PR):**
a CLAUDE.md pointer to this runbook, and/or a pre-flight lint in the sweep
skills that rejects a raw multi-PR `gh` loop outside this tool. This PR
cannot edit `omni_home/CLAUDE.md` (it lives outside any product-repo
worktree; see CLAUDE.md rule 9's `omni_home`-itself exception) — that
doctrine-wiring step is the controller's follow-up, tracked against this
runbook.

## Wave receipts

Every non-dry-run invocation writes a JSON receipt (default under
`.onex_state/bulk-pr-throttle/`) recording, per wave: wave index, the exact
PR numbers, queue depth before and after, start/completion timestamps, and
the per-PR outcome (`success`, `detail`). Wave progress is also logged to
stdout as it happens:

```text
[bulk-pr-throttle] wave 1/1: depth_before=5 count=3 prs=[6751, 6752, 6753] operation=rerun-failed
[bulk-pr-throttle]   pr=6751 success=True detail=reran=[98765432]
[bulk-pr-throttle]   pr=6752 success=True detail=no completed failed or cancelled runs to rerun
[bulk-pr-throttle]   pr=6753 success=True detail=reran=[98765440]
[bulk-pr-throttle] wave 1/1: depth_after=6
```

## Coordination with other lanes

Bulk operations touch shared fleet capacity. Before running a batch,
claim the specific PR numbers you intend to touch in
`docs/tracking/ROLLING_WORK_LEDGER.md` (§1a) so a concurrent lane's
residual-remediation batch doesn't collide with yours on the same PRs.

## Tests

`scripts/ci/tests/test_bulk_pr_throttle.py` covers wave partitioning
(including the hard ceiling), capacity blocking with mocked fleet samples,
deep-queue admission when matching idle runners exist, named fail-closed probe
errors, dry-run plan output (zero `gh` calls), all input refusal paths, the
`gh` CLI integration seam (mocked `_run_gh`, never the real API), and the CLI
entrypoint end to end.

```bash
uv run pytest scripts/ci/tests/test_bulk_pr_throttle.py -v
```
