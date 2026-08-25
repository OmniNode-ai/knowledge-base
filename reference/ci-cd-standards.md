---
type: reference
status: stale
date: "2026-02-14"
title: "CI/CD Standards"
topics: [ci, branch-protection, gate-check-contract, cross-repo-standard]
refs: []
---

# CI/CD Standards

**Purpose**: Organization-wide CI/CD standards for all OmniNode repositories
**Source**: omnibase_core `docs/standards/CI_CD_STANDARDS.md`

> **2026-08-25 migration correction — read this before the rest of the document.**
> This document describes a **v2** `required-checks.yaml` schema (three operational gates:
> `Quality Gate`, `Tests Gate`, `Security Gate`, plus a conditional `CI Summary`). Verified
> live against omnibase_core@dev: `.github/required-checks.yaml` is now **schema v3**
> (upgraded under an internal tracking epic), and its own header comment states outright that
> the v2 model was *already stale* before the v3 upgrade — live branch protection on the
> default branch required 61 individual contexts at the time v3 was authored, not the small
> gate set v2 documented as "the operational contract." The v3 file is the OPERATIONAL input
> to a required-check skip-vector guard script, a role this document's v2 schema never had.
> Separately, live `omnibase_core` classification is `toolchain`, not `library-core` as this
> document's own "Example 1: omnibase_core" section states — a direct factual contradiction,
> also verified live. The tiering concepts below (four check tiers, the four-gate contract,
> the three-phase rename procedure, CI Summary semantics) are still a reasonable design
> **pattern**, and nothing here contradicts v3's shape at the conceptual level, but the v2
> schema and the worked `omnibase_core` example are demonstrably out of date and this document
> is marked `status: stale` for that reason. Full reconciliation against the live v3 schema is
> out of scope for this migration pass — flagged here rather than silently republished.

---

## Overview

This document defines the CI/CD standards intended to apply to all OmniNode repositories. It
establishes: a **tier system** for classifying CI checks by scope and enforcement policy;
**repository classifications** that determine which tiers apply; a **gate check name
contract** treating certain check names as API-stable identifiers; a schema for
`required-checks.yaml` separating operational gates from documentation; and invariants that
must hold across CI configurations.

These standards exist because GitHub branch protection rules reference check names as opaque
strings. Renaming a check without coordinating the branch-protection update breaks merging.

## Repository Classifications

| Classification | Description | Examples |
|---------------|-------------|----------|
| **library-core** | Shared libraries consumed by other repos. Breaking changes affect the entire org. Strictest CI requirements. | `omnibase_spi` |
| **toolchain** | Developer tools, CLI utilities, and build infrastructure. Must not break developer workflows. | `omniclaude`, `omnibase_core` (verified live 2026-08-25) |
| **deployable-service** | Services that run in production. Require deployment-specific checks. | `omninode_bridge`, `omniintelligence` |
| **infrastructure-as-code** | Terraform, Docker Compose, infrastructure definitions. Require plan validation and drift detection. | `omninode_infra` |

A repository has exactly one classification, declared under the `classification` key. If not
declared, it defaults to `deployable-service`.

## Check Tier System

**Tier A-Org** (universal, every repo, no path filtering, cannot be skipped): linting/
formatting, license headers, secret scanning, branch-protection compliance.

**Tier A-Runtime** (per-technology, mandatory for repos using that stack): Python type
checking (mypy strict, pyright), Python test suite, Python exports validation, TypeScript
`tsc --noEmit`, Docker container build.

**Tier B** (conditional — specific repos/paths, MAY use path filtering, MUST NOT be a
branch-protection required check if path-filtered): architecture handshake checks, DB
ownership CI twin, transport-import boundary, schema-migration validity.

**Tier C** (profile — optional, informational, non-blocking): documentation-link validation,
node-purity check, coverage threshold, performance benchmarks.

| Tier | library-core | toolchain | deployable-service | infrastructure-as-code |
|------|-------------|-----------|-------------------|----------------------|
| **A-Org** | Required | Required | Required | Required |
| **A-Runtime** | Required (per stack) | Required (per stack) | Required (per stack) | Required (per stack) |
| **B** | As applicable | As applicable | As applicable | As applicable |
| **C** | Optional | Optional | Optional | Optional |

## Gate Check Name Contract

Branch protection is intended to reference exactly four **API-stable** gate names:

| Gate Name | Purpose | Scope |
|-----------|---------|-------|
| `Quality Gate` | Aggregates lint, type checking, exports | All repos |
| `Tests Gate` | Aggregates test execution (the single aggregator branch protection references instead of individual matrix shards) | All repos with tests |
| `Security Gate` | Aggregates secret detection, dependency audit, SAST | All repos |
| `CI Summary` | Final aggregator, enumerates gate status; required when path filtering can cause a Tier A gate job to be skipped | Conditional |

**Design principles**: gates are aggregators, not executors; branch protection references
gates, never individual jobs (which may be freely renamed/split/merged); each gate covers
exactly one concern.

```text
Branch Protection          Gate (aggregator)           Individual Checks
─────────────────          ─────────────────           ─────────────────
requires: "Tests Gate" --> tests-gate job      ------> Tests (Split 1/20)
                           (if: always())              Tests (Split 2/20)
                           checks needs result         ...
                                                       Tests (Split 20/20)
```

## Invariants

1. **Check name stability** — gate names are opaque, API-stable strings referenced by GitHub
   branch protection; renaming one without a coordinated branch-protection update makes every
   PR unmergeable. Individual (non-gate) check names can be renamed freely.
2. **Single source of truth** — the `gates` list is the only operational contract for branch
   protection; a documentary `checks` listing (if present) has no operational effect.
3. **Path-filtered checks and branch protection** — a path-filtered check MUST NOT be a
   branch-protection required check (it won't report status on PRs that don't touch its
   paths, permanently blocking them). Promote it to Tier A-Runtime (remove the path filter)
   before requiring it.
4. **CI Summary requirement condition** — `CI Summary` is required if and only if path
   filtering can skip any Tier A gate job; it must distinguish skipped-by-policy (path filter
   matched no files, expected) from a genuinely missing/misconfigured gate.

## Branch Protection Migration Safety

When a gate name must be renamed, use a three-phase procedure to avoid a window where PRs
become unmergeable: **Phase 1 (dual-require)** — add the new gate, keep the old one running,
require both in branch protection, merge. **Phase 2 (verify)** — confirm both report status
on a live PR. **Phase 3 (remove old)** — drop the old gate job and its branch-protection
requirement. Single-step renames create a window where either the old name is required but no
longer reported, or the new name is required but not yet reported — either blocks every PR.

```bash
gh api -X PUT repos/OmniNode-ai/<REPO>/branches/main/protection --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["Quality Gate", "Tests Gate", "Security Gate", "CI Summary"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {"required_approving_review_count": 1},
  "restrictions": null
}
EOF
```

## CI Summary Semantics

```text
For each gate in required-checks.yaml.gates:
  status = lookup_gate_status(gate.name)
  success                                        -> PASSED
  failure                                         -> FAILED, exit 1
  skipped and gate.condition == "required_iff_path_filtering" -> SKIPPED_BY_POLICY
  skipped and gate.condition is None              -> MISSING_GATE, exit 1
  not found                                       -> MISSING_GATE, exit 1
```

The distinction between SKIPPED_BY_POLICY (path filter intentionally matched nothing) and
MISSING_GATE (the workflow is misconfigured) is the reason `CI Summary` exists at all.

---

## Related Documentation

- Current live required-checks configuration: `.github/required-checks.yaml` in each repo (now v3, see the correction above)
- [Merge Dependency Graph](merge-dependency-graph.md)
- [ADR-0034](../adrs/ADR-0034-core-infra-dependency-boundary.md)
- [GitHub branch protection API](https://docs.github.com/en/rest/branches/branch-protection)

---

**Original Document Version**: 1.0.0, created 2026-02-14, ONEX Framework Team. Migrated to
the knowledge base 2026-08-25 with the v2→v3 schema drift and the `omnibase_core`
classification error corrected in a prominent note; the detailed v2 schema field reference,
full worked YAML examples, and the gate-aggregator workflow-job example were trimmed from
this migrated copy rather than republished as if still literally accurate — they describe the
now-superseded v2 shape. Consult the live `required-checks.yaml` v3 schema and its own header
comments for the current operational contract.
