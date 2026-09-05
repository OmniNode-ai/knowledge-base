---
type: plan
status: active
date: "2026-03-24"
title: "Environment variable lifecycle fix"
topics: [configuration, ci, validators, runtime-health]
---

# Env Var Lifecycle Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan phase-by-phase.

**Goal:** Fix missing env vars, build CI prevention, and add runtime warnings so env var gaps never silently break features again

**Architecture:** Three workstreams -- immediate config fix, per-repo CI validator, omniclaude runtime health check

**Tech Stack:** Python, bash, pytest, ruff, GitHub Actions CI

---

## Known Types Inventory

### omniclaude

| Type / Module | Path | Relevance |
|---|---|---|
| `ContextInjectionConfig` (Pydantic BaseSettings) | `src/omniclaude/hooks/context_config.py` | Resolves `INTELLIGENCE_SERVICE_URL` via `resolve_api_url_from_env()` validator; auto-disables `api_enabled` when missing |
| `SessionStartInjectionConfig` (Pydantic BaseModel) | `src/omniclaude/hooks/context_config.py` | SessionStart injection config; `from_env()` classmethod |
| `OmniClaudeSettings` (Pydantic BaseSettings) | `src/omniclaude/config/settings.py` | Central settings; `intelligence_service_url: HttpUrl | None` field; warns on missing at startup |
| `is_production_environment()` / `validate_required_env_vars()` | `scripts/env_validation.py` | Production-only env validation (not used in hooks) |
| `.env.example` | root `.env.example` | 360-line registry with REQUIRED/OPTIONAL/CONDITIONAL annotations; `INTELLIGENCE_SERVICE_URL` is commented out |
| `plugins/onex/.env.example` | `plugins/onex/.env.example` | Plugin-level env example (separate scope) |
| `session-start.sh` | `plugins/onex/hooks/scripts/session-start.sh` | SessionStart hook entry; sources `.env`, starts emit daemon; <50ms budget |

### omnidash

| Type / Module | Path | Relevance |
|---|---|---|
| `FeatureNotEnabledBanner` | `client/src/components/FeatureNotEnabledBanner.tsx` | Shows "Feature Not Enabled" with optional `flagHint` prop |
| `ContextEffectivenessDashboard` | `client/src/pages/ContextEffectivenessDashboard.tsx` | Uses `flagHint="ENABLE_CONTEXT_UTILIZATION"` -- phantom flag (does not exist in omniclaude) |
| `ContextEnrichmentDashboard` | `client/src/pages/ContextEnrichmentDashboard.tsx` | Uses `flagHint="ENABLE_CONTEXT_ENRICHMENT"` -- real flag (exists in `~/.omnibase/.env`) |
| `PatternEnforcement` | `client/src/pages/PatternEnforcement.tsx` | Uses `flagHint="ENABLE_PATTERN_ENFORCEMENT"` -- real flag |

### omnibase_infra

| Type / Module | Path | Relevance |
|---|---|---|
| `plugin-env-service-completeness` CI job | `.github/workflows/test.yml` line 465 | Existing CI guard: validates `*_HOST` env vars in `x-runtime-env` have matching Docker services |
| `env-example-full.txt` | `docker/env-example-full.txt` | 600+ line full env reference; should include `INTELLIGENCE_SERVICE_URL` |
| `audit-env-files.sh` | `scripts/audit-env-files.sh` | Scans repos for stale .env files |

### ~/.omnibase/.env (current state)

92 active env vars. **Missing**: `INTELLIGENCE_SERVICE_URL`, `SEMANTIC_SEARCH_URL`, `MAIN_SERVER_URL`. **Present**: `ENABLE_PATTERN_ENFORCEMENT=true`, `ENABLE_CONTEXT_ENRICHMENT=true`, `ENABLE_LOCAL_INFERENCE_PIPELINE=true`.

---

## Task Sequence

## Task 1: [Env Fix] Add INTELLIGENCE_SERVICE_URL to ~/.omnibase/.env

**Goal:** Add the missing env var so context injection and intelligence features activate.

**Worktree:** N/A -- editing `~/.omnibase/.env` directly (not a repo file).

**Steps:**

1. Source current env and verify `INTELLIGENCE_SERVICE_URL` is unset:
   ```bash
   source ~/.omnibase/.env
   echo "${INTELLIGENCE_SERVICE_URL:-(not set)}"
   # Expected: (not set)
   ```

2. Add the following block to `~/.omnibase/.env` after the existing `METADATA_STAMPING_SERVICE_URL` line (around line 79):
   ```bash
   # OmniIntelligence HTTP API (context injection, pattern discovery)
   INTELLIGENCE_SERVICE_URL=http://localhost:8053
   ```

3. Verify it loads:
   ```bash
   source ~/.omnibase/.env
   echo "INTELLIGENCE_SERVICE_URL=${INTELLIGENCE_SERVICE_URL}"
   # Expected: INTELLIGENCE_SERVICE_URL=http://localhost:8053
   ```

4. Verify the intelligence service is reachable (if infra is running):
   ```bash
   curl -sf http://localhost:8053/health || echo "Service not running (OK if infra-down)"
   ```

**Done when:** `source ~/.omnibase/.env && echo $INTELLIGENCE_SERVICE_URL` prints `http://localhost:8053`.

---

## Task 2: [Env Fix] Verify context injection activates with the new env var

**Goal:** Confirm that `ContextInjectionConfig.from_env()` now has `api_enabled=True`.

**Worktree:** Use existing omniclaude worktree or create one.

**Steps:**

1. Create a small verification script (temporary, run once):
   ```bash
   cd <omniclaude-worktree>
   source ~/.omnibase/.env
   uv run python -c "
   from omniclaude.hooks.context_config import ContextInjectionConfig
   c = ContextInjectionConfig.from_env()
   print(f'api_enabled: {c.api_enabled}')
   print(f'api_url: {c.api_url}')
   assert c.api_enabled is True, 'api_enabled should be True'
   assert 'localhost:8053' in c.api_url, f'Unexpected api_url: {c.api_url}'
   print('PASS: Context injection is enabled')
   "
   ```

2. Expected output:
   ```
   api_enabled: True
   api_url: http://localhost:8053
   PASS: Context injection is enabled
   ```

**Done when:** The verification script prints PASS.

---

## Task 3: [Env Fix] Verify omnidash context injection pages populate

**Goal:** Confirm that the 5 context-related omnidash pages show data (or at least no longer show the "Feature Not Enabled" banner for context injection).

**Precondition:** `infra-up-runtime` running, omnidash dev server running.

**Steps:**

1. Start infra and omnidash if not running:
   ```bash
   infra-up-runtime
   cd <omnidash-worktree> && npm run dev:local
   ```

2. Use Playwright to check pages:
   - `/enrichment` -- should NOT show `FeatureNotEnabledBanner` (ENABLE_CONTEXT_ENRICHMENT is set)
   - `/enforcement` -- should NOT show `FeatureNotEnabledBanner` (ENABLE_PATTERN_ENFORCEMENT is set)
   - `/effectiveness/utilization` -- may still show banner (depends on event flow, not just env var)

3. Check `/decisions` and `/pipeline-health` for data population (these depend on `INTELLIGENCE_SERVICE_URL` being set for the intelligence API to respond).

**Done when:** Enrichment and Enforcement pages load without the FeatureNotEnabledBanner when events are flowing.

---

## Task 4: [Env Fix] Remove phantom ENABLE_CONTEXT_UTILIZATION flag hint from omnidash

**Goal:** The `ContextEffectivenessDashboard` references `ENABLE_CONTEXT_UTILIZATION` in its `flagHint` prop, but this env var does not exist anywhere in omniclaude. Replace with the correct hint or remove.

**Worktree:** `omnidash` worktree.

**Investigation:**

The `ENABLE_CONTEXT_UTILIZATION` flag does not exist in omniclaude code (grep returned zero results). The page shows context utilization data which is derived from `onex.evt.omniclaude.context-utilization.v1` events emitted by the context injection system. The actual gate is whether context injection is enabled at all, which depends on `INTELLIGENCE_SERVICE_URL` being set.

**Steps:**

1. In `client/src/pages/ContextEffectivenessDashboard.tsx` line 292, change:
   ```tsx
   flagHint="ENABLE_CONTEXT_UTILIZATION"
   ```
   to:
   ```tsx
   flagHint="INTELLIGENCE_SERVICE_URL"
   ```

2. Run omnidash type check:
   ```bash
   npm run check
   ```

3. Run omnidash tests:
   ```bash
   npm run test
   ```

**Test:** Verify the page renders with the corrected flag hint text.

**Done when:** `npm run check` passes, `npm run test` passes, and the banner text references `INTELLIGENCE_SERVICE_URL` instead of the phantom flag.

---

## Task 5: [Env Fix] Update omnibase_infra env-example-full.txt

**Goal:** Add `INTELLIGENCE_SERVICE_URL` to the full env reference file so future env audits catch it.

**Worktree:** `omnibase_infra` worktree.

**Steps:**

1. Open `docker/env-example-full.txt` and add in the service URLs section:
   ```bash
   # OmniIntelligence HTTP API (context injection, pattern discovery)
   INTELLIGENCE_SERVICE_URL=http://localhost:8053
   ```

2. Verify no duplicate:
   ```bash
   grep -c INTELLIGENCE_SERVICE_URL docker/env-example-full.txt
   # Expected: 1
   ```

**Done when:** `grep INTELLIGENCE_SERVICE_URL docker/env-example-full.txt` returns the new line.

---

## Task 6: [CI Validator] Write the env var registry scanner script

**Goal:** Create a Python script that scans production Python code for `os.getenv()` / `os.environ.get()` references and compares them against `.env.example` as the canonical registry.

**Worktree:** `omniclaude` worktree.

**TDD approach:**

1. **Write failing test first** at `tests/ci/test_env_var_registry.py`:
   ```python
   """CI guard: every os.getenv/os.environ reference in production code
   must be registered in .env.example (OMN-XXXX)."""

   import subprocess
   import sys
   from pathlib import Path

   import pytest

   REPO_ROOT = Path(__file__).resolve().parents[2]

   @pytest.mark.unit
   class TestEnvVarRegistry:
       def test_scanner_output_has_required_keys(self):
           """Scanner JSON output must contain registered, unregistered, allowlisted keys."""
           result = subprocess.run(
               [sys.executable, "scripts/ci/check_env_var_registry.py",
                "--scan-dirs", "src/omniclaude", "plugins/onex/hooks/lib",
                "--registry", ".env.example",
                "--format", "json"],
               capture_output=True, text=True, cwd=REPO_ROOT,
           )
           import json
           data = json.loads(result.stdout)
           assert "unregistered" in data
           assert "registered" in data
           assert "allowlisted" in data
           # registered should contain known vars from .env.example
           assert "KAFKA_BOOTSTRAP_SERVERS" in data["registered"]

       def test_scanner_exits_zero_when_clean(self, tmp_path):
           """Scanner exits 0 when all referenced vars are in the registry."""
           # Create minimal .env.example with one var
           registry = tmp_path / ".env.example"
           registry.write_text("MY_VAR=default\n")

           # Create minimal Python file referencing that var
           scan_dir = tmp_path / "src"
           scan_dir.mkdir()
           (scan_dir / "app.py").write_text('import os\nv = os.getenv("MY_VAR")\n')

           result = subprocess.run(
               [sys.executable, str(REPO_ROOT / "scripts/ci/check_env_var_registry.py"),
                "--scan-dirs", str(scan_dir),
                "--registry", str(registry),
                "--format", "json"],
               capture_output=True, text=True,
           )
           assert result.returncode == 0

       def test_scanner_exits_one_when_gap_found(self, tmp_path):
           """Scanner exits 1 when a referenced var is not in the registry."""
           registry = tmp_path / ".env.example"
           registry.write_text("REGISTERED_VAR=yes\n")

           scan_dir = tmp_path / "src"
           scan_dir.mkdir()
           (scan_dir / "app.py").write_text('import os\nv = os.getenv("UNREGISTERED_VAR")\n')

           result = subprocess.run(
               [sys.executable, str(REPO_ROOT / "scripts/ci/check_env_var_registry.py"),
                "--scan-dirs", str(scan_dir),
                "--registry", str(registry),
                "--format", "json"],
               capture_output=True, text=True,
           )
           assert result.returncode == 1
   ```

2. **Run test, confirm it fails** (script does not exist yet):
   ```bash
   uv run pytest tests/ci/test_env_var_registry.py -v
   # Expected: FAILED (FileNotFoundError or similar)
   ```

3. **Implement the scanner** at `scripts/ci/check_env_var_registry.py` (see Task 7).

**Done when:** Test file exists and fails because the script does not yet exist.

---

## Task 7: [CI Validator] Implement the env var registry scanner

**Goal:** Implement `scripts/ci/check_env_var_registry.py` that passes the tests from Task 6.

**Worktree:** `omniclaude` worktree (same as Task 6).

**Implementation details:**

The script must:

1. **Parse `.env.example`** to extract registered var names:
   - Lines matching `^[A-Z_][A-Z0-9_]*=` (active vars)
   - Lines matching `^#\s*[A-Z_][A-Z0-9_]*=` (commented-out vars -- still registered)
   - Skip blank lines and pure comments

2. **Scan Python files** in `--scan-dirs` for env var references:
   - Pattern: `os\.getenv\((?:"|')([A-Z_][A-Z0-9_]*)(?:"|')` captures the var name
   - Pattern: `os\.environ\.get\((?:"|')([A-Z_][A-Z0-9_]*)(?:"|')` captures the var name
   - Pattern: `os\.environ\[(?:"|')([A-Z_][A-Z0-9_]*)(?:"|')\]` captures the var name
   - Exclude test files (`tests/`, `test_*.py`, `*_test.py`)
   - Exclude docstrings / comments (best-effort: skip lines starting with `#`)

3. **Allowlist** for framework/system vars that should never be in `.env.example`:
   ```python
   BUILTIN_ALLOWLIST = {
       "PATH", "HOME", "USER", "SHELL", "TERM", "LANG", "LC_ALL",
       "PYTHONPATH", "VIRTUAL_ENV", "UV_CACHE_DIR",
       "DEBUG", "LOG_LEVEL", "ENVIRONMENT", "DEPLOYMENT_ENV", "ENV",
       "REPL_ID", "CI", "GITHUB_ACTIONS",
       "CLAUDE_SESSION_ID", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR",
       "OMNICLAUDE_PROJECT_ROOT", "PLUGIN_PYTHON_BIN",
       "DISABLE_MANIFEST_DB_LOGGING",
   }
   ```

4. **Output formats:**
   - `--format json`: `{"registered": [...], "unregistered": [...], "allowlisted": [...]}`
   - `--format text`: Human-readable list of gaps
   - Exit 0 if no unregistered vars; exit 1 if gaps found

5. **CLI interface:**
   ```
   usage: check_env_var_registry.py [-h] --scan-dirs DIR [DIR ...]
                                     --registry FILE
                                     [--format {json,text}]
                                     [--allowlist-file FILE]
   ```

**Verification:**
```bash
uv run pytest tests/ci/test_env_var_registry.py -v
# Expected: All 3 tests pass
```

**Secondary verification -- run against actual codebase:**
```bash
uv run python scripts/ci/check_env_var_registry.py \
  --scan-dirs src/omniclaude plugins/onex/hooks/lib \
  --registry .env.example \
  --format text
```

This should show currently-unregistered vars (if any remain after `.env.example` is updated).

**Done when:** All 3 tests pass and the scanner runs successfully against the real codebase.

---

## Task 8: [CI Validator] Baseline the scanner -- register missing vars or add to allowlist

**Goal:** Make the scanner exit 0 on the current codebase by registering any missing env vars in `.env.example` or adding them to the allowlist.

**Worktree:** `omniclaude` worktree (same).

**Steps:**

1. Run the scanner in text mode to see all gaps:
   ```bash
   uv run python scripts/ci/check_env_var_registry.py \
     --scan-dirs src/omniclaude plugins/onex/hooks/lib \
     --registry .env.example \
     --format text
   ```

2. For each unregistered var, decide:
   - **Add to `.env.example`** if it is a user-configurable setting (even if optional)
   - **Add to allowlist** if it is a framework/system var or test-only var

3. Re-run until exit code is 0:
   ```bash
   uv run python scripts/ci/check_env_var_registry.py \
     --scan-dirs src/omniclaude plugins/onex/hooks/lib \
     --registry .env.example \
     --format json
   echo "Exit: $?"
   # Expected: Exit: 0
   ```

4. Run full test suite to ensure nothing broke:
   ```bash
   uv run pytest tests/ci/test_env_var_registry.py -v
   ```

**Done when:** Scanner exits 0 on the real codebase and all tests pass.

---

## Task 9: [CI Validator] Add CI job to omniclaude GitHub Actions

**Goal:** Add the env var registry check as a CI job in `.github/workflows/ci.yml`.

**Worktree:** `omniclaude` worktree (same).

**Steps:**

1. Add a new job in `.github/workflows/ci.yml` after the existing `exports-validation` job:

   ```yaml
   env-var-registry:
     name: "Env Var Registry (OMN-XXXX)"
     runs-on: ubuntu-latest
     timeout-minutes: 5
     steps:
       - name: Checkout code
         uses: actions/checkout@v6

       - name: Setup Python and uv
         uses: ./.github/actions/setup-python-uv
         with:
           python-version: ${{ env.PYTHON_VERSION }}
           uv-version: ${{ env.UV_VERSION }}
           cache-version: ${{ env.CACHE_VERSION }}

       - name: Check env var registry completeness
         run: |
           echo "================================================================"
           echo "Env Var Registry: os.getenv refs vs .env.example (OMN-XXXX)"
           echo "================================================================"
           uv run python scripts/ci/check_env_var_registry.py \
             --scan-dirs src/omniclaude plugins/onex/hooks/lib \
             --registry .env.example \
             --format text
   ```

2. Add `env-var-registry` to the Quality Gate aggregator `needs` list.

3. Add `env-var-registry` to the `test-parallel` job's `needs` list (so tests don't run if the registry check fails).

4. Verify CI YAML is valid:
   ```bash
   python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
   ```

**Done when:** CI YAML parses cleanly and the job definition is in place. Full validation happens when the PR is pushed.

---

## Task 10: [Runtime Check] Design the env var health check module

**Goal:** Create a module that checks critical env vars at session start and emits warnings for missing ones.

**Worktree:** `omniclaude` worktree.

**TDD approach:**

1. **Write failing test first** at `tests/hooks/test_env_health_check.py`:
   ```python
   """Tests for session-start env var health check."""

   import os
   from unittest.mock import patch

   import pytest

   @pytest.mark.unit
   class TestEnvHealthCheck:
       def test_missing_intelligence_url_warns(self):
           """When INTELLIGENCE_SERVICE_URL is not set, emit a warning."""
           from omniclaude.hooks.env_health_check import check_critical_env_vars

           with patch.dict(os.environ, {}, clear=True):
               result = check_critical_env_vars()
           assert any("INTELLIGENCE_SERVICE_URL" in w for w in result.warnings)

       def test_all_vars_present_no_warnings(self):
           """When all critical vars are set, no warnings."""
           from omniclaude.hooks.env_health_check import check_critical_env_vars

           env = {
               "INTELLIGENCE_SERVICE_URL": "http://localhost:8053",
               "KAFKA_BOOTSTRAP_SERVERS": "localhost:19092",
           }
           with patch.dict(os.environ, env, clear=True):
               result = check_critical_env_vars()
           assert len(result.warnings) == 0

       def test_missing_kafka_warns(self):
           """When KAFKA_BOOTSTRAP_SERVERS is not set, emit a warning."""
           from omniclaude.hooks.env_health_check import check_critical_env_vars

           with patch.dict(os.environ, {}, clear=True):
               result = check_critical_env_vars()
           assert any("KAFKA_BOOTSTRAP_SERVERS" in w for w in result.warnings)

       def test_result_never_raises(self):
           """Health check must never raise -- it returns a result object."""
           from omniclaude.hooks.env_health_check import check_critical_env_vars

           # Even with bizarre env state, should not raise
           with patch.dict(os.environ, {"INTELLIGENCE_SERVICE_URL": ""}, clear=True):
               result = check_critical_env_vars()
           assert result is not None
   ```

2. **Run test, confirm it fails**:
   ```bash
   uv run pytest tests/hooks/test_env_health_check.py -v
   # Expected: ImportError (module does not exist)
   ```

**Done when:** Test file exists and fails on import.

---

## Task 11: [Runtime Check] Implement the env var health check module

**Goal:** Implement `src/omniclaude/hooks/env_health_check.py` that passes the tests from Task 10.

**Worktree:** `omniclaude` worktree (same).

**Implementation:**

```python
# src/omniclaude/hooks/env_health_check.py
"""Session-start env var health check.

Checks critical environment variables and returns warnings (never errors)
for missing or misconfigured values. Used by the SessionStart hook to
surface configuration issues to the user.

Design principle: NEVER block. NEVER raise. Always return a result.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field


class ModelEnvHealthResult(BaseModel):
    """Result of an env var health check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    warnings: list[str] = Field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return len(self.warnings) == 0


# Critical env vars and their impact descriptions.
# Format: (var_name, impact_description)
CRITICAL_ENV_VARS: list[tuple[str, str]] = [
    (
        "INTELLIGENCE_SERVICE_URL",
        "Context injection disabled -- omniclaude cannot fetch learned patterns from omniintelligence",
    ),
    (
        "KAFKA_BOOTSTRAP_SERVERS",
        "Event emission disabled -- session events will not reach Kafka or omnidash",
    ),
]


def check_critical_env_vars() -> ModelEnvHealthResult:
    """Check critical env vars and return warnings for missing ones.

    This function NEVER raises. All errors are caught and converted to
    warnings in the result.

    Returns:
        ModelEnvHealthResult with warnings for any missing critical vars.
    """
    try:
        warnings: list[str] = []
        for var_name, impact in CRITICAL_ENV_VARS:
            value = os.environ.get(var_name, "").strip()
            if not value:
                warnings.append(
                    f"[env-health] {var_name} is not set. Impact: {impact}"
                )
        return ModelEnvHealthResult(warnings=warnings)
    except Exception:
        # Never crash the hook
        return ModelEnvHealthResult()
```

**Verification:**
```bash
uv run pytest tests/hooks/test_env_health_check.py -v
# Expected: All 4 tests pass
```

**Done when:** All 4 tests pass.

---

## Task 12: [Runtime Check] Wire health check into SessionStart hook

**Goal:** Call `check_critical_env_vars()` during SessionStart and log warnings to `hooks.log` and stderr.

**Worktree:** `omniclaude` worktree (same).

**Steps:**

1. The SessionStart hook is a bash script (`plugins/onex/hooks/scripts/session-start.sh`). It already calls Python modules via the `find_python` + exec pattern. Add the health check call after the emit daemon startup, but before the script exits.

2. The session-start.sh script uses the `$PYTHON_CMD` and `$HOOKS_LIB` pattern for all Python calls. Create a standalone script at `plugins/onex/hooks/lib/env_health_check_wrapper.py` that imports from the installed package and prints warnings:

   ```python
   # plugins/onex/hooks/lib/env_health_check_wrapper.py
   """Thin wrapper for env var health check, called from session-start.sh."""
   import sys

   def main() -> None:
       try:
           from omniclaude.hooks.env_health_check import check_critical_env_vars
           result = check_critical_env_vars()
           for w in result.warnings:
               print(w, file=sys.stderr)
       except Exception:
           pass  # Never block SessionStart

   if __name__ == "__main__":
       main()
   ```

3. Add the call in `session-start.sh` near the end, before the final JSON output assembly. Use the existing pattern:

   ```bash
   # --- Env var health check (non-blocking) ---
   if [[ -f "${HOOKS_LIB}/env_health_check_wrapper.py" ]]; then
       "$PYTHON_CMD" "${HOOKS_LIB}/env_health_check_wrapper.py" 2>>"${LOG_FILE:-/dev/null}" || true
   fi
   ```

4. Key constraints:
   - The `|| true` ensures exit 0 regardless of errors
   - Output goes to `LOG_FILE` (hooks.log) via stderr redirect
   - The entire block must complete in <10ms (just env var lookups)
   - No network calls, no imports of heavy modules
   - Uses `$PYTHON_CMD` (the hook's resolved Python) not raw `python3`

5. **Test the integration** by running the hook manually:
   ```bash
   echo '{"session_id":"test-123","cwd":"/tmp"}' | \
     bash plugins/onex/hooks/scripts/session-start.sh
   # Check hooks.log for any warnings
   grep "env-health" ~/.claude/hooks.log
   ```

6. **Verify hook still exits 0**:
   ```bash
   echo '{"session_id":"test-123","cwd":"/tmp"}' | \
     bash plugins/onex/hooks/scripts/session-start.sh
   echo "Exit: $?"
   # Expected: Exit: 0
   ```

**Done when:** Hook exits 0, and when `INTELLIGENCE_SERVICE_URL` is unset, a warning appears in hooks.log.

---

## Task 13: [Runtime Check] Add visible session-start warning for missing env vars

**Goal:** When critical env vars are missing, emit a visible warning in the session-start output so the user sees it in their Claude Code session.

**Worktree:** `omniclaude` worktree (same).

**Design decision:** The SessionStart hook outputs JSON with `additionalContext` to inject text into the session. The final JSON assembly happens near the end of `session-start.sh` (around the `COMBINED_OUTPUT` / `HANDSHAKE_CONTEXT` / `SKILL_SUGGESTIONS` section, roughly lines 1187+). We add the env health warnings there.

**Steps:**

1. Modify `env_health_check_wrapper.py` to output a JSON fragment instead of just stderr:

   ```python
   # In env_health_check_wrapper.py, add JSON output mode:
   import json
   import sys

   def main() -> None:
       try:
           from omniclaude.hooks.env_health_check import check_critical_env_vars
           result = check_critical_env_vars()
           # Print warnings to stderr for hooks.log
           for w in result.warnings:
               print(w, file=sys.stderr)
           # Print JSON to stdout for session-start.sh to capture
           if not result.healthy:
               warning_text = "\n".join([
                   "--- Env Var Health Check ---",
                   *result.warnings,
                   "Set missing vars in ~/.omnibase/.env and restart.",
                   "---",
               ])
               json.dump({"warning": warning_text}, sys.stdout)
           else:
               json.dump({"warning": ""}, sys.stdout)
       except Exception:
           json.dump({"warning": ""}, sys.stdout)
   ```

2. In `session-start.sh`, capture the wrapper output and append to the `additionalContext` string that is assembled before the final `jq` output (near the `COMBINED_OUTPUT` block around line 1190):

   ```bash
   # --- Env var health check (non-blocking) ---
   ENV_HEALTH_WARNING=""
   if [[ -f "${HOOKS_LIB}/env_health_check_wrapper.py" ]]; then
       ENV_HEALTH_JSON=$("$PYTHON_CMD" "${HOOKS_LIB}/env_health_check_wrapper.py" 2>>"${LOG_FILE:-/dev/null}") || ENV_HEALTH_JSON='{}'
       ENV_HEALTH_WARNING=$(echo "$ENV_HEALTH_JSON" | jq -r '.warning // ""' 2>/dev/null) || ENV_HEALTH_WARNING=""
   fi
   ```

3. Then append `ENV_HEALTH_WARNING` to the existing `additionalContext` in the final JSON output block.

3. **Test:** Start a new Claude Code session with `INTELLIGENCE_SERVICE_URL` unset, and verify the warning appears in the session start context.

4. **Test with var set:** Start a session with all vars set and verify no warning appears.

**Done when:** Missing env vars produce a visible warning at session start. All vars present produces no warning.

---

## Task 14: [CI Validator] Run quality checks and create PR for omniclaude changes

**Goal:** Ensure all omniclaude changes pass quality gates before PR.

**Worktree:** `omniclaude` worktree.

**Steps:**

1. Run the full quality suite:
   ```bash
   uv run ruff check src/ tests/ scripts/ plugins/
   uv run ruff format --check src/ tests/ scripts/ plugins/
   uv run mypy src/omniclaude/
   uv run pytest tests/ -m unit -v --tb=short
   ```

2. Run the new CI validator against the codebase:
   ```bash
   uv run python scripts/ci/check_env_var_registry.py \
     --scan-dirs src/omniclaude plugins/onex/hooks/lib \
     --registry .env.example \
     --format text
   ```

3. Run pre-commit hooks:
   ```bash
   pre-commit run --all-files
   ```

4. Create PR targeting `main`.

**Done when:** All quality checks pass and PR is created.

---

## Task 15: [Env Fix] Create PR for omnidash phantom flag fix

**Goal:** Ship the `ENABLE_CONTEXT_UTILIZATION` -> `INTELLIGENCE_SERVICE_URL` fix.

**Worktree:** `omnidash` worktree.

**Steps:**

1. Make the change from Task 4.
2. Run quality checks:
   ```bash
   npm run check
   npm run test
   ```
3. Create PR targeting `main`.

**Done when:** PR created and CI passes.

---

## Verification Checklist

After all tasks complete:

- [ ] `source ~/.omnibase/.env && echo $INTELLIGENCE_SERVICE_URL` prints `http://localhost:8053`
- [ ] `ContextInjectionConfig.from_env().api_enabled` is `True`
- [ ] omnidash `/enrichment` page loads without FeatureNotEnabledBanner
- [ ] omnidash `/effectiveness/utilization` page shows `INTELLIGENCE_SERVICE_URL` as the flag hint (not `ENABLE_CONTEXT_UTILIZATION`)
- [ ] `scripts/ci/check_env_var_registry.py` exits 0 on omniclaude codebase
- [ ] CI job `env-var-registry` is defined in `.github/workflows/ci.yml`
- [ ] `check_critical_env_vars()` returns warnings for missing `INTELLIGENCE_SERVICE_URL`
- [ ] SessionStart hook shows env health warnings when critical vars are missing
- [ ] SessionStart hook exits 0 even when all vars are missing
- [ ] omnibase_infra `env-example-full.txt` includes `INTELLIGENCE_SERVICE_URL`
