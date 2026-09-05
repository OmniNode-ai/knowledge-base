---
type: plan
status: active
date: "2026-05-29"
title: "Canonical Python .gitignore baseline and cross-repo enforcement"
topics: [validators, ci, propagation, repo-hygiene]
---

# Canonical Python `.gitignore` baseline + cross-repo enforcement

## Problem (observed, not inferred)

`pull-all.sh` fails on canonical clones going "dirty" from build/test artifacts. Root cause survey (2026-05-29) across all Python repos:

| Symptom | Repos |
|---|---|
| **No `.gitignore` at all** | `omnibase_compat`, `omnigemini` |
| Has file, **no `__pycache__` rule** | a private infra repo, `omnibase` |
| **Committed `.pyc` tracked in git** | `omnibase_compat` (44 files) |
| `.env` / `test-results/` / `playwright-report/` not ignored | `omnidash` (only `.env.local*`) |
| `.gitignore` line counts | range **8 → 431** — every repo hand-rolled |

There is **no shared `.gitignore` and no validator enforcing one**. The platform standardized validators (ruff, mypy, omnibase_core validator suite) but never brought `.gitignore` under that umbrella. Per OP5: detection that isn't a gate gets ignored; per the validator doctrine, this should be a propagated CI/pre-commit gate.

## Approach (matches existing validator pattern)

Mirror `contract_config_compliance` / `handler_di_gate`:

- Validator code: `omnibase_core/src/omnibase_core/validators/gitignore_baseline.py`
- Canonical asset: `omnibase_core/architecture-handshakes/gitignore-baseline.yaml`
- Pre-commit: `.pre-commit-hooks.yaml` (`id: validate-gitignore-baseline`) + `.pre-commit-config.yaml`
- CI: mirror workflow under `.github/workflows/`
- Propagation: add entry to `.github/propagation-targets.yaml`; `scripts/propagate-config.sh` opens auto-merge PRs to all 11 repos on release/`workflow_dispatch`. **No hand-editing 11 repos.**
- Suppression marker: `# gitignore-ok: <reason>`

### Canonical managed blocks (universal + language sections)

The baseline asset defines a **universal block** enforced on EVERY repo, plus a **Python block** enforced on Python repos. The validator detects repo language (presence of `pyproject.toml` / `package.json`) and asserts the relevant blocks are present verbatim between markers; it does NOT touch lines outside the markers (repos keep their bespoke rules).

Universal block (all repos):
```
# === onex-managed: universal (do not edit inside markers) ===
.env
.env.*
!.env.example
.DS_Store
*.log
.idea/
.vscode/
test-results/
playwright-report/
# === end onex-managed: universal ===
```

Python block (repos with pyproject.toml):
```
# === onex-managed: python (do not edit inside markers) ===
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
env/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
# === end onex-managed: python ===
```

## Scope: all repos

The universal block applies to every repo, so `omnidash` (Vite/React/TS) is now **in-scope for the gate** — its `.env` / `test-results/` / `playwright-report/` gaps are covered by the universal block. Python repos additionally get the Python block. Propagation targets all repos, not just Python ones.

## Tickets

1. **Canonical baseline asset** — author `architecture-handshakes/gitignore-baseline.yaml` with universal + python managed blocks. (omnibase_core)
2. **Validator + unit tests** — `validators/gitignore_baseline.py` reads asset, detects repo language, asserts relevant managed blocks present verbatim, exit 1 on miss, `# gitignore-ok:` suppression; `tests/unit/validators/test_gitignore_baseline.py`. (omnibase_core)
3. **Wire pre-commit + CI gate** — `.pre-commit-hooks.yaml`, `.pre-commit-config.yaml`, mirror `.github/workflows/validator-gitignore-baseline.yml`. (omnibase_core)
4. **Add propagation target** — entry in `.github/propagation-targets.yaml` for all repos (Python + non-Python). (omnibase_core)
5. **Remediate omnibase_compat** — create `.gitignore`, `git rm -r --cached **/__pycache__` (44 .pyc), add universal+python blocks. (omnibase_compat)
6. **Remediate omnigemini** — create `.gitignore` with universal+python blocks. (omnigemini)
7. **Remediate the private infra repo** — add universal+python blocks.
8. **Remediate omnibase** — add universal+python blocks. (omnibase)
9. **Remediate omnidash** — add universal block (`.env`, `test-results/`, `playwright-report/`). Now in validator scope via universal block. (omnidash)

Dependencies: 1 → 2 → 3 → 4. Remediation tickets (5-9) depend on 1 (baseline defined) but can run parallel to each other. Once 3/4 land + propagate, the gate is live and remediation PRs must pass it.

## DoD evidence

- Validator unit tests green; self-scan of omnibase_core passes.
- Each remediation PR: `git status` clean after `git clean`/checkout; `pull-all.sh` runs green across all repos.
- Propagation PR merged; gate appears as required check on a sample downstream repo.
