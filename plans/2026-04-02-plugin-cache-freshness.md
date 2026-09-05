---
type: plan
status: completed
date: "2026-04-02"
title: "Plugin cache freshness — preventing stale plugin deployments"
topics: [tooling, plugins, developer-experience, staleness]
---

# Plugin Cache Freshness — Preventing Stale Plugin Deployments

**Triggered by**: Silent data drops in delegation pipeline caused by stale plugin cache emitting `model_used` instead of `delegated_to`

---

## Problem Statement

The Claude Code plugin cache (`~/.claude/plugins/cache/omninode-tools/onex/`) can contain stale code that diverges from the canonical repo (`omniclaude/plugins/onex/`). When schema changes land in the repo (e.g., renaming `model_used` to `delegated_to`), the cache is not refreshed, causing silent data drops downstream.

### Root Cause Analysis

Three gaps converge to create this failure mode:

1. **`pull-all.sh` cache refresh is broken**: The refresh logic (lines 133-162) searches for a `skills/` directory directly under the cache root, but the actual cache structure is versioned: `~/.claude/plugins/cache/omninode-tools/onex/2.2.5/skills/`. The `find` command returns nothing, so the refresh never triggers.

2. **Commit SHA comparison is insufficient**: Even if the path were correct, comparing `git rev-parse HEAD` against `.deployed-commit` only detects when the repo has new commits. It does not detect:
   - Partial deploys (some files copied, others not)
   - Cache corruption or manual edits
   - Version-directory mismatches (cache under `2.2.5/` but repo at a different version)

3. **No pre-flight staleness detection**: There is no check at session start that compares the running plugin code against the repo. A developer can work for days with stale hooks and never know.

### Impact

- **Silent data loss**: Schema mismatches cause fields to be silently dropped (Pydantic `extra="ignore"`)
- **Hard to diagnose**: No error, no warning — data simply disappears from the pipeline
- **Affects all developers**: Anyone who runs `pull-all.sh` expects their plugins to be current

---

## Proposed Fixes

### Fix 1: Repair `pull-all.sh` cache path detection (Quick Win)

**Scope**: `omnibase_infra/scripts/pull-all.sh` lines 133-162

The current detection logic:
```bash
_plugin_cache=$(find "${HOME}/.claude/plugins/cache" -maxdepth 3 -name "skills" -type d 2>/dev/null | head -1)
[[ -n "${_plugin_cache}" ]] && _plugin_cache=$(dirname "${_plugin_cache}")
```

This fails because the versioned directory (`2.2.5/`) adds an extra level. Fix:

1. Increase `maxdepth` to 4, or better, search for `.deployed-commit` instead of `skills/` (more specific)
2. Refresh the **entire plugin tree** (hooks, skills, lib, agents, runtime, scripts), not just `skills/`
3. After refresh, compute and store a content hash alongside the commit SHA

**Content hash approach**:
```bash
# Compute hash of all plugin files (excluding __pycache__, .pyc)
find "${_plugin_cache}" -type f \
  ! -name "*.pyc" ! -path "*/__pycache__/*" ! -name ".deployed-commit" ! -name ".content-hash" \
  -exec shasum {} \; | sort | shasum | cut -d' ' -f1
```

Store in `${_plugin_cache}/.content-hash`. On next pull, compare repo hash against cache hash.

**Effort**: Small (1-2 hours)
**Risk**: Low — only changes the refresh path in an existing script

### Fix 2: Content-hash-based deploy verification

**Scope**: New script or addition to `omniclaude/plugins/onex/scripts/`

Create a `verify-plugin-cache.sh` script that:

1. Computes a content hash of the repo's `plugins/onex/` tree
2. Computes a content hash of the deployed cache directory
3. Compares them and reports drift with specific changed files
4. Optionally auto-refreshes the cache (with `--fix` flag)

This script can be:
- Called by `pull-all.sh` after a refresh to verify it worked
- Called manually by developers to diagnose staleness
- Called by the session-start hook as a pre-flight check (Fix 3)

**Effort**: Medium (2-4 hours)
**Risk**: Low

### Fix 3: Session-start pre-flight staleness warning

**Scope**: `omniclaude/plugins/onex/hooks/scripts/session_start.sh` or a new pre-flight module

At session start, compare the deployed plugin content hash against the repo's current state. If stale:

- Emit a warning to the user via `hookSpecificOutput.additionalContext`
- Log to `~/.claude/hooks.log`
- Emit a `onex.evt.omniclaude.plugin-stale.v1` event for observability

**Must not block**: This check must complete within the SessionStart 50ms budget. Strategy:
- Read pre-computed `.content-hash` file (no recomputation at session start)
- Compare against repo's `.deployed-commit` (fast git operation)
- If mismatch, warn but don't block

**Effort**: Medium (2-4 hours)
**Risk**: Low — warning only, does not block session

---

## Implementation Order

| Order | Fix | Justification |
|-------|-----|---------------|
| 1 | Fix 1: Repair pull-all.sh | Quick win, fixes the immediate broken path |
| 2 | Fix 2: verify-plugin-cache.sh | Foundation for Fix 3, also useful standalone |
| 3 | Fix 3: Session-start warning | Catches staleness even when pull-all.sh isn't run |

---

## Out of Scope

- **Plugin venv fix (PR #1074)**: Already addressed separately. The venv issue (hooks using the wrong Python environment) is orthogonal to the cache staleness issue.
- **Marketplace auto-update**: The marketplace install mechanism (`claude plugin install onex@omninode-tools`) is the long-term solution. These fixes are stopgaps for the local development workflow where the marketplace version may lag.
- **Automated cache invalidation on git push**: Would require a server-side hook, out of scope for local tooling.

---

## Verification

After implementation, the following scenarios must pass:

1. `pull-all.sh` with omniclaude changes correctly refreshes the versioned cache directory
2. `verify-plugin-cache.sh` detects a manually-introduced drift (e.g., edit a cached file)
3. Session start warns when cache content hash differs from repo
4. No performance regression: session start stays under 50ms budget
5. No false positives when cache is current
