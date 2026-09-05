---
type: plan
status: active
date: "2026-03-18"
title: "Compose required-env coverage guard"
topics: [ci, validators, compose, configuration]
---

# Compose Required-Env Coverage Guard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan phase-by-phase.

**Goal:** Add a CI guard that fails on the PR that introduces a new `:?`-required env var in `docker-compose.infra.yml` without a corresponding entry in the `test_compose_config_valid` fixture dict, preventing silent downstream test breakage.

**Architecture:** A standalone Python script (`scripts/validation/check_compose_required_env_coverage.py`) parses the compose file for all `${VAR:?…}` patterns and cross-checks them against keys extracted via regex from the integration test fixture dict. A matching `tests/ci/` test validates the script logic without needing Docker. A new `onex-validation` step in `test.yml` wires it into CI. A PR template checkbox documents the manual companion rule.

**Tech Stack:** Python 3.12+, `re`, `pathlib`, `yaml` (already installed), pytest, GitHub Actions YAML.

---

## Known Types Inventory

> No new Pydantic models, enums, TypedDicts, or Protocol classes are introduced by this plan.
> All artifacts are: standalone script, CI test, CI workflow step, PR template update.

---

## Task 1: Write the failing CI test

**Files:**
- Create: `tests/ci/test_compose_required_env_coverage.py`

**Step 1: Write the test**

```python
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""CI guard: every :?-required env var in docker-compose.infra.yml must appear
in the test_compose_config_valid fixture dict.

Catches: PRs that add a new service with a required :? env var to compose
without updating the integration test fixture, which previously caused
cascading failures in #886, #890, #895 (root cause analysis).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

COMPOSE_FILE = (
    Path(__file__).parent.parent.parent / "docker" / "docker-compose.infra.yml"
)
FIXTURE_FILE = (
    Path(__file__).parent.parent
    / "integration"
    / "docker"
    / "test_docker_integration.py"
)


def extract_required_compose_vars(compose_path: Path) -> set[str]:
    """Return all variable names that use :? fail-fast syntax in the compose file."""
    text = compose_path.read_text()
    return set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*):\?", text))


def extract_fixture_vars(fixture_path: Path) -> set[str]:
    """Return all string keys in the env.update({...}) dict in test_compose_config_valid."""
    text = fixture_path.read_text()
    # Narrow to the env.update block inside test_compose_config_valid
    # Strategy: find the function, then extract all "KEY": patterns within it
    match = re.search(
        r"def test_compose_config_valid.*?env\.update\s*\(\s*\{(.*?)\}\s*\)",
        text,
        re.DOTALL,
    )
    if not match:
        return set()
    block = match.group(1)
    return set(re.findall(r'"([A-Z_][A-Z0-9_]*)"\s*:', block))


@pytest.mark.unit
def test_all_required_compose_vars_in_fixture() -> None:
    """Every :?-required var in compose must be present in the test fixture dict.

    This is the CI twin for the contract: 'if you add a :? var to compose,
    you must also add it to the test_compose_config_valid fixture dict'.
    Fails on the PR that introduces the gap, not three PRs later.
    """
    required = extract_required_compose_vars(COMPOSE_FILE)
    provided = extract_fixture_vars(FIXTURE_FILE)
    missing = required - provided
    assert not missing, (
        f"These :?-required env vars are in docker-compose.infra.yml but "
        f"NOT in the test_compose_config_valid fixture dict:\n"
        + "\n".join(f"  - {v}" for v in sorted(missing))
        + "\n\nFix: add each missing var to the env.update({{...}}) dict in "
        f"tests/integration/docker/test_docker_integration.py "
        f"(around the 'test_compose_config_valid' method)."
    )
```

**Step 2: Run the test to see it fail**

From a worktree of `omnibase_infra`:

```bash
uv run pytest tests/ci/test_compose_required_env_coverage.py -v --tb=short
```

Expected: FAIL — the test should report missing vars (KEYCLOAK_ADMIN_CLIENT_SECRET, ONEX_REGISTRATION_AUTO_ACK, ONEX_SERVICE_CLIENT_SECRET are currently absent from the fixture).

> If the test passes unexpectedly, `extract_fixture_vars` may have found them already — verify manually by searching `test_docker_integration.py` for each var name.

**Step 3: Commit the failing test**

```bash
git add tests/ci/test_compose_required_env_coverage.py
git commit -m "test(ci): add failing guard for compose :? env var fixture coverage"
```

---

## Task 2: Add missing vars to the fixture dict

**Files:**
- Modify: `tests/integration/docker/test_docker_integration.py` (around line 1085)

**Step 1: Identify current gaps**

Run:
```bash
python3 -c "
import re; from pathlib import Path
compose = Path('docker/docker-compose.infra.yml').read_text()
required = set(re.findall(r'\\\$\{([A-Z_][A-Z0-9_]*):\?', compose))
fixture = Path('tests/integration/docker/test_docker_integration.py').read_text()
import re as r2
m = r2.search(r'def test_compose_config_valid.*?env\.update\s*\(\s*\{(.*?)\}\s*\)', fixture, re.DOTALL)
provided = set(r2.findall(r'\"([A-Z_][A-Z0-9_]*)\"\s*:', m.group(1))) if m else set()
print('Missing:', sorted(required - provided))
"
```

Expected output (as of 2026-03-18):
```
Missing: ['KEYCLOAK_ADMIN_CLIENT_SECRET', 'ONEX_REGISTRATION_AUTO_ACK', 'ONEX_SERVICE_CLIENT_SECRET']
```

**Step 2: Add missing vars to the env.update dict**

In `test_docker_integration.py`, find the `env.update({...})` block inside `test_compose_config_valid` and add the three missing entries with safe placeholder values:

```python
# After OMNIBASE_INFRA_CONTEXT_AUDIT_POSTGRES_DSN, add:
"KEYCLOAK_ADMIN_CLIENT_SECRET": "test-keycloak-secret",
"ONEX_REGISTRATION_AUTO_ACK": "true",
"ONEX_SERVICE_CLIENT_SECRET": "test-service-secret",
```

**Step 3: Run the new CI test to verify it now passes**

```bash
uv run pytest tests/ci/test_compose_required_env_coverage.py -v
```

Expected: PASS — "1 passed"

**Step 4: Run the integration test (if Docker is available) to verify no regression**

```bash
uv run pytest tests/integration/docker/test_docker_integration.py::TestDockerComposeStructure::test_compose_config_valid -v --tb=short
```

Expected: PASS or skip ("Docker daemon not available")

**Step 5: Commit**

```bash
git add tests/integration/docker/test_docker_integration.py
git commit -m "fix(test): add missing :? vars to test_compose_config_valid fixture (KEYCLOAK, ONEX_REGISTRATION, ONEX_SERVICE)"
```

---

## Task 3: Add the CI job to test.yml

**Files:**
- Modify: `.github/workflows/test.yml`

**Step 1: Verify the test runs under the existing test-parallel matrix**

The new test in `tests/ci/` has `@pytest.mark.unit`. The test-parallel job runs:
```
uv run pytest tests/ --ignore=tests/integration/docker ...
```
This already picks up `tests/ci/`. Confirm by checking:
```bash
grep -n "ignore=tests/integration/docker" .github/workflows/test.yml
```
Expected: found at line ~535.

Since `tests/ci/` is already included in the parallel sweep, the new test will run automatically. **No new CI job is needed** — the guard fires via the existing `test-parallel` matrix.

**Step 2: Add a dedicated named step in onex-validation for discoverability**

The `onex-validation` job is the right home for structural compose checks (see `plugin-env-service-completeness` job for the pattern). Add a new job after `plugin-env-service-completeness`:

```yaml
  compose-required-env-coverage:
    name: "Compose Required-Env Coverage"
    runs-on: >-
      ${{
        (vars.USE_SELF_HOSTED_RUNNERS == 'true' &&
         (github.event_name == 'push' ||
          github.event_name == 'workflow_dispatch' ||
          github.event_name == 'schedule'))
        && fromJSON('["self-hosted","omnibase-ci"]')
        || fromJSON('["ubuntu-latest"]')
      }}
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

      - name: Check compose :? env var fixture coverage
        run: |
          echo "================================================================"
          echo "Compose Required-Env Coverage Guard"
          echo "Every :?-required var in compose must be in test fixture dict"
          echo "================================================================"
          uv run pytest tests/ci/test_compose_required_env_coverage.py -v --tb=short
```

**Step 3: Add `compose-required-env-coverage` to the `test-parallel` needs list**

Find:
```yaml
  test-parallel:
    name: Tests (Split ${{ matrix.split }}/10)
    needs: [lint, onex-validation, migration-freeze, fingerprint-check, demo-loop-gate, topic-enum-drift, topic-naming-lint, topic-drift-check, arch-invariants, schema-handshake, plugin-env-service-completeness]
```

Change to:
```yaml
    needs: [lint, onex-validation, migration-freeze, fingerprint-check, demo-loop-gate, topic-enum-drift, topic-naming-lint, topic-drift-check, arch-invariants, schema-handshake, plugin-env-service-completeness, compose-required-env-coverage]
```

**Step 4: Verify test.yml is valid YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml').read()); print('YAML valid')"
```

Expected: `YAML valid`

**Step 5: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "ci: add compose-required-env-coverage job to CI"
```

---

## Task 4: Update the PR template

**Files:**
- Modify: `.github/PULL_REQUEST_TEMPLATE.md`

**Step 1: Add the checkbox to the type safety checklist**

Find the `## Type safety checklist` section. After the existing four checkboxes, add:

```markdown
- [ ] If adding a service to `docker-compose.infra.yml` with required (`:?`) env vars, update `tests/integration/docker/test_docker_integration.py` fixture dict in `test_compose_config_valid`
```

The full checklist should read:
```markdown
## Type safety checklist
- [ ] No new `metadata["key"]` or `metadata.get("key")` string literal access on Pydantic model fields
- [ ] No new `metadata: dict[str, Any]` fields without TypedDict or `# ONEX_EXCLUDE:` comment
- [ ] No new bare `except Exception` — must use narrowed type, or minimal-scope boundary with `logger.exception(...)` + degrade comment, or typed wrap/re-raise
- [ ] If adding a key to a metadata dict, the key is defined in the relevant TypedDict
- [ ] If adding a service to `docker-compose.infra.yml` with required (`:?`) env vars, update `tests/integration/docker/test_docker_integration.py` fixture dict in `test_compose_config_valid`
```

**Step 2: Verify the file looks right**

```bash
cat .github/PULL_REQUEST_TEMPLATE.md
```

**Step 3: Commit**

```bash
git add .github/PULL_REQUEST_TEMPLATE.md
git commit -m "docs(pr-template): add checklist item for compose :? env var fixture coverage"
```

---

## Task 5: Full validation sweep

**Step 1: Run pre-commit on all changed files**

```bash
pre-commit run --all-files
```

Fix any failures before continuing. Do not use `--no-verify`.

**Step 2: Run the full unit test suite to check for regressions**

```bash
uv run pytest tests/ci/ tests/unit/ -m "not slow" -n auto --tb=short -q
```

Expected: all pass, including the new `test_compose_required_env_coverage.py`.

**Step 3: Verify YAML validity of the workflow file**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml').read()); print('YAML valid')"
```

**Step 4: Run mypy on the new test file**

```bash
uv run mypy tests/ci/test_compose_required_env_coverage.py --ignore-missing-imports
```

Expected: no errors.

**Step 5: Confirm all four changed files are staged correctly**

```bash
git status
git diff --stat HEAD
```

Expected: 4 files modified/created:
- `tests/ci/test_compose_required_env_coverage.py` (new)
- `tests/integration/docker/test_docker_integration.py` (fixture additions)
- `.github/workflows/test.yml` (new job + needs update)
- `.github/PULL_REQUEST_TEMPLATE.md` (new checkbox)

---

## Acceptance Criteria

- `uv run pytest tests/ci/test_compose_required_env_coverage.py -v` passes (1 passed)
- Running `uv run pytest tests/ci/test_compose_required_env_coverage.py -v` against a compose file with a `:?` var absent from the fixture exits non-zero and the failure message contains the missing variable name
- `test_compose_config_valid` passes (or skips due to no Docker) with `result.returncode == 0` from the subprocess.run call — no unset variable errors in `result.stderr`
- `.github/workflows/test.yml` is valid YAML and the new job is listed in `test-parallel`'s `needs`
- PR template has exactly 5 checkboxes in the type safety section
- `pre-commit run --all-files` is clean
- No new `Optional[...]` or `Union[...]` — PEP 604 `X | Y` only if types are needed

---

routing: single-repo, sequential → ticket-pipeline
