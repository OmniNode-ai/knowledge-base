# PR Validation Path

> Migrated from omniclaude:docs/reference/PR_VALIDATION_PATH.md on 2026-09-01 (OMN-16609). Corrected against the live `.github/workflows/ci.yml` and `.github/required-checks.yaml` at migration time — the original table had drifted from the shipped workflow.

The complete ordered list of checks a PR in `omniclaude` goes through, local and CI. Every REQUIRED context on the `dev` branch is tracked in `.github/required-checks.yaml`, which fails closed if it and live branch protection diverge.

## Local (before push)

| Order | Check | Tool | What It Catches |
|-------|-------|------|----------------|
| 1 | `ruff format` | pre-commit | Formatting |
| 2 | `ruff check` | pre-commit | Lint violations |
| 3 | `mypy` | pre-commit | Type errors |

## CI (after push) — `ci.yml`

### Quality Gate

Aggregates the following jobs (all REQUIRED to pass, `if: always()` triage):

Code Quality (ruff + mypy) · Pyright Type Checking · Architecture Handshake (vs `omnibase_core`) · Canonical Handler-Shape Ratchet · Enum Governance · Exports Validation · Env Var Registry · Cross-Repo Boundary Parity (validation leg) · Migration Freeze · ONEX Compliance (naming, contracts, signatures) · 14 "Arch:" architecture-invariant checks (no DB in orchestrator/compute, no git/gh outside effects, no LinearClient outside effects, no repo-adapter imports in orchestrator/compute, no direct adapter imports in business logic, no direct EventBus instantiation, no raw `sqlite3.connect` in handlers, no localhost/env fallbacks, cost-ledger isolation + structure, `onex.*` topic naming, omnidash DB role provisioning, no direct Kafka producer outside publisher, no `datetime.utcnow()`, no hardcoded internal IPs) · F5.1 No compact cmd topic · Architecture Invariants (CDQA-07) · Version Pin Compliance · Skill Hygiene · Mode Metadata Integrity · Merge-Sweep Contract · Skill Contract Validation · Golden Chain Integrity · Aislop Sweep · Agent Contract Validation · Skill Monorepo-Ref Gate · No-Polymorphic-Agent guard.

### Tests Gate

| Order | Check | Workflow Job | What It Catches |
|-------|-------|--------------|----------------|
| 1 | Unit Tests (5-way split) | `test` | Functional regressions |
| 2 | Hooks System Tests | `hooks-tests` | Hook registration/execution |
| 3 | Agent Framework Tests | `agent-framework-tests` | Agent YAML loading |
| 4 | Database Schema Validation | `database-validation` | Schema drift |
| 5 | Golden Chain Live | `golden-chain-live` | Live end-to-end chain break |
| 6 | Registry Consistency | `registry-consistency` | Registry drift |

### Security Gate

| Order | Check | Workflow Job | What It Catches |
|-------|-------|--------------|----------------|
| 1 | Python Security Scan (Bandit) | `security-python` | Security vulnerabilities |
| 2 | Secret Detection | `detect-secrets` | Leaked credentials |

`AI-Slop Pattern Check (strict, PR diff)` runs as its own top-level job outside the three named gates.

### Other REQUIRED contexts feeding CI Summary

DoD Evidence Check · Merge Test Coverage · Contract Compliance Check · OCC Companion Merged Gate · `no-noncanonical-lifecycle-classes` · Markdown Link Check.

### Omni Standards Gate — `omni-standards-compliance.yml`

| Order | Check | Job | What It Catches |
|-------|-------|-----|----------------|
| 1 | Repository Structure Validation | — | Missing required directories |
| 2 | Agent YAML Compliance | — | Schema version, naming |
| 3 | Ecosystem Integration Validation | — | CLAUDE.md, hooks.json |
| 4 | Legacy Compatibility Check | — | Forbidden patterns |
| 5 | PR Safety Mutation Surface Enforcement | — | Unauthorized PR mutations |
| 6 | CI Naming Convention | — | Job/workflow naming drift |

Aggregated into `Omni Standards Gate`.

### Cross-Repo Checks

| Order | Check | Workflow | What It Catches |
|-------|-------|----------|----------------|
| 1 | Contract Validation | `contract-validation.yml` | Invalid ticket contracts |
| 2 | Schema Compatibility | `onex-schema-compat.yml` | Breaking schema changes |

## Branch Protection

All REQUIRED contexts (Quality Gate, Tests Gate, Security Gate, Omni Standards Gate, plus the standalone contexts listed above) must pass before merge. The authoritative, machine-verified list lives in `.github/required-checks.yaml` (v3, OMN-14854), which is reconciled against live GitHub branch protection by a dedicated job and fails closed on divergence.
