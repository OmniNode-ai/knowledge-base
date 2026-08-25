---
type: adr
status: accepted
date: "2025-12-10"
title: "ADR-0038: CI Workflow Modification Risk (Transport Import Branch Protection)"
adr_id: ADR-0038
topics: [omnibase_core, ci, transport-imports, dependency-inversion, risk-mitigation]
refs: [adrs/ADR-0034-core-infra-dependency-boundary.md]
supersedes: []
superseded_by: []
---

# ADR-0038: CI Workflow Modification Risk (Transport Import Branch Protection)

**Status**: Mitigated
**Date**: 2025-12-10
**Related**: [ADR-0034](ADR-0034-core-infra-dependency-boundary.md) — Core-Infra Dependency Boundary
**Source**: omnibase_core `docs/decisions/RISK-009-ci-workflow-modification-risk.md`

> Filed in omnibase_core as a risk record (`RISK-009`) rather than a numbered ADR; migrated
> here as an ADR-shaped record because its content — a decision to protect a specific piece
> of CI logic via CODEOWNERS — is a decision record, not a dated snapshot.

---

## Summary

Future changes to the CI workflow that enforces [ADR-0034](ADR-0034-core-infra-dependency-boundary.md)'s
transport-import boundary could accidentally disable the full-scan mode on protected
branches, potentially allowing dependency-inversion violations to be merged.

## Risk Details

The CI workflow implements a hybrid mode for transport-import validation: a fast
changed-files-only scan on feature branches, and a comprehensive full scan on protected
branches. This protection relies on conditional branch-detection logic in the workflow file.
A future edit to that workflow could accidentally remove or alter the conditional, disable
the full-scan step, get the branch-detection logic wrong, or remove the transport-import
check step altogether.

**Severity**: High — if full scan is disabled on protected branches, transport-import
violations could merge to the default branch, compromising the dependency-inversion
architecture and letting omnibase_core gain unwanted dependencies on higher-level packages.

**Likelihood**: Medium — workflow files are modified during CI optimization, GitHub Actions
version updates, and new-check additions; without explicit protection these edits may not
receive review focus on the transport-import logic specifically.

## Mitigation Strategy

1. **CODEOWNERS protection (primary)** — `/.github/workflows/` requires platform-team
   review for any change. Verified live: `.github/CODEOWNERS` carries
   `/.github/workflows/ @OmniNode-ai/platform-team`.
2. **Inline documentation (secondary)** — the workflow step carries a comment pointing back
   to this risk record so an editor understands why the branch-detection logic exists before
   changing it. Verified live: `.github/workflows/ci.yml`'s transport-import step still
   carries this cross-reference (see migration note below on the filename it points at).
3. **Architecture documentation (tertiary)** — dependency-inversion rules and CI-specific
   documentation cross-reference each other; this risk register provides the traceability.
4. **Test coverage (supporting)** — the transport-import checker's own unit tests cover
   changed-files mode, full-scan mode, and branch-detection logic.

## Acceptance Criteria

- [x] CODEOWNERS includes workflow protection
- [x] Workflow file includes inline documentation referencing this risk record
- [x] Risk documented in the architecture decision set
- [ ] Platform team trained on transport-import requirements (ongoing at authoring time; not re-verified during migration)

---

## 2026-08-25 Migration Corrections

Two claims in the original record no longer match live `omnibase_core@dev` and are corrected
here rather than migrated unchanged:

1. **Workflow filename**: the original names `.github/workflows/test.yml`. Live, this file
   was renamed to `.github/workflows/ci.yml`. The workflow's own inline comment (mitigation
   #2 above) still says `See: docs/decisions/RISK-009-ci-workflow-modification-risk.md` and
   correctly lives inside `ci.yml` — only the *filename this record itself cites* was stale.
2. **Protected-branch names**: the original conditional example reads
   `github.ref == 'refs/heads/main' || github.ref == 'refs/heads/master'`. Live, the
   workflow's actual branch check is `github.base_ref == 'main' || github.base_ref == 'develop'`
   (pull-request full-scan trigger) with an equivalent `github.ref` check for pushes — `master`
   is not a live branch name in this check; `develop` is, and the original record omits it.

The core risk, its severity/likelihood assessment, and the CODEOWNERS-based mitigation are
still accurate and were independently re-verified live during this migration (CODEOWNERS
entry confirmed present; workflow inline comment confirmed present).

---

## Related Documentation

- [ADR-0034](ADR-0034-core-infra-dependency-boundary.md) — Core-Infra Dependency Boundary (the invariant this risk protects)
- `.github/CODEOWNERS` (omnibase_core) — verified live: `/.github/workflows/ @OmniNode-ai/platform-team`
- `.github/workflows/ci.yml` (omnibase_core) — the "Check for transport import violations" step

---

## Changelog

| Date | Changes |
|------|---------|
| 2026-08-25 | Migrated to knowledge base as an ADR-shaped record. Corrected the workflow filename (`test.yml` → `ci.yml`) and the protected-branch names (`main`/`master` → `main`/`develop`), both verified live. |
| 2025-12-10 | Initial risk documentation |
