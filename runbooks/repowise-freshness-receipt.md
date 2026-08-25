---
type: runbook
status: current
date: "2026-07-21"
title: "Repowise Freshness Receipt"
topics: [omnibase-infra, repowise, freshness, receipt]
refs: []
---

# Repowise Freshness Receipt

**Script:** `scripts/emit_repowise_freshness_receipt.py`

## Purpose

The Repowise freshness-receipt script reads `.repowise-workspace.yaml` and
live git HEAD SHAs to emit a per-repo receipt showing index age, stale status,
and any failure flags (no index, mismatched HEAD).

This receipt provides a durable audit trail that binds Repowise index metadata
to exact git state, so tech-debt findings can cite the repository SHAs and
freshness state that produced them.

## When to Run

Run **manually after `pull-all.sh`** to capture the post-sync freshness state,
and again after a Repowise reindex to confirm the index is current.

> **Follow-up:** No automated closeout flow yet wires this script. Invoke it
> manually until a closeout flow adopts it as an automatic post-reindex step.

## Prerequisites

- `git` on PATH
- `$OMNI_HOME` set (or pass `--omni-home`)
- `.repowise-workspace.yaml` present at the omni_home root

The script is **stdlib-only** — no venv or `uv` required.

## Invocation

### Basic (use `$OMNI_HOME`)

```bash
python3 "$OMNI_HOME/omnibase_infra/scripts/emit_repowise_freshness_receipt.py"
```

### With explicit omni-home

```bash
python3 /path/to/omnibase_infra/scripts/emit_repowise_freshness_receipt.py \
  --omni-home /path/to/omni_home
```

### Machine-readable output only

```bash
python3 "$OMNI_HOME/omnibase_infra/scripts/emit_repowise_freshness_receipt.py" \
  --json-only
```

Prints the path to the written JSON receipt and suppresses the human-readable
summary table.

### Custom output path

```bash
python3 "$OMNI_HOME/omnibase_infra/scripts/emit_repowise_freshness_receipt.py" \
  --out /tmp/my-receipt.json
```

## Output

### File location

```text
$OMNI_HOME/.onex_state/repowise-sync/freshness-<ISO8601-timestamp>.json
```

A `latest-freshness.json` symlink is updated in the same directory on each run.

### Receipt schema

```json
{
  "run_id": "freshness-20260530T120000Z",
  "generated_at": "<ISO8601>",
  "omni_home": "<resolved path>",
  "repos": [
    {
      "alias": "omnibase_core",
      "path": "omnibase_core",
      "exists": true,
      "branch": "main",
      "head_sha": "abc123def",
      "indexed_at": "2026-05-29T10:00:00+00:00",
      "index_age_days": 1.08,
      "index_head_sha": "abc123def",
      "stale": false,
      "no_index": false,
      "docs_mode": "generated",
      "failure": null
    }
  ],
  "summary": {
    "total": 12,
    "indexed": 11,
    "stale": 0,
    "no_index": 1,
    "failures": 1
  },
  "failure_summaries": [
    "omnistream: never indexed by Repowise"
  ]
}
```

### Field reference

| Field | Type | Description |
|-------|------|-------------|
| `alias` | string | Repo alias from `.repowise-workspace.yaml` |
| `path` | string | Path relative to `omni_home` |
| `exists` | bool | Whether the repo directory exists on disk |
| `branch` | string \| null | Current git branch |
| `head_sha` | string \| null | Live `HEAD` SHA |
| `indexed_at` | string \| null | ISO8601 timestamp of last Repowise index |
| `index_age_days` | float \| null | Days since last index |
| `index_head_sha` | string \| null | `HEAD` SHA at last index |
| `stale` | bool | `true` when `head_sha != index_head_sha` |
| `no_index` | bool | `true` when `indexed_at` is missing |
| `docs_mode` | string | `"generated"`, `"skipped"`, or `"none"` |
| `failure` | string \| null | Human-readable failure summary, or `null` |

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Receipt written successfully |
| `1` | Fatal error (e.g. `.repowise-workspace.yaml` not found) |

## Typical workflow

```bash
# 1. Sync all repos to latest main
bash "$OMNI_HOME/omnibase_infra/scripts/pull-all.sh"

# 2. Trigger Repowise reindex (via Repowise UI or CLI)

# 3. Emit freshness receipt
python3 "$OMNI_HOME/omnibase_infra/scripts/emit_repowise_freshness_receipt.py"

# 4. Review stale/failure entries
cat "$OMNI_HOME/.onex_state/repowise-sync/latest-freshness.json" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); [print(f) for f in d['failure_summaries']]"
```
