---
type: reference
status: current
date: "2026-08-25"
title: "Doctrine Coverage Matrix"
topics: [doctrine, ci-gates, truth-doctrine, coverage]
refs: []
---

# Doctrine Coverage Matrix

> **Source**: onex_change_control `docs/standards/doctrine_coverage.md`, auto-generated in that
> repo by `scripts/generate_doctrine_coverage.py` from a machine-readable clause registry
> (`docs/standards/doctrine_clauses.yaml`). Migrated to the knowledge base 2026-08-25 as a
> verified snapshot — regenerated locally against onex_change_control@main and produced a
> byte-identical file, confirming currency. This snapshot can drift as CI gates are added or
> renamed; the source registry and generator stay in `onex_change_control` (they are
> repo-intrinsic tooling, not portable documentation) and are the authority for any future
> refresh of this page.

Tracks which of the 15 clauses of the OmniNode Deterministic Truth Doctrine have a CI gate
that actually blocks a merge, as opposed to clauses that are stated policy with no automated
enforcement yet.

**4 ENFORCED** | **0 ADVISORY** | **11 UNCOVERED**

| Clause | Title | CI Gate | Coverage |
| --- | --- | --- | --- |
| DT-001 | Truth must be proven, not claimed | verify/Run Receipt-Gate | ✅ ENFORCED |
| DT-002 | Clients render truth; they do not create it | — | ❌ UNCOVERED |
| DT-003 | Systems must be deterministic under replay | — | ❌ UNCOVERED |
| DT-004 | Ordering must be explicit and contracted | — | ❌ UNCOVERED |
| DT-005 | Reducers define state progression | — | ❌ UNCOVERED |
| DT-006 | State is a materialized projection | — | ❌ UNCOVERED |
| DT-007 | Contracts define reality | contract-compliance | ✅ ENFORCED |
| DT-008 | Cursors represent projection progress | — | ❌ UNCOVERED |
| DT-009 | Fail fast and loud | verify/Run Receipt-Gate | ✅ ENFORCED |
| DT-010 | Degrade safely | — | ❌ UNCOVERED |
| DT-011 | Ingestion and interpretation are separate | — | ❌ UNCOVERED |
| DT-012 | Runtime complexity must be isolated | — | ❌ UNCOVERED |
| DT-013 | Migration must be staged and recoverable | — | ❌ UNCOVERED |
| DT-014 | Canonical reducers win | — | ❌ UNCOVERED |
| DT-015 | Evidence is a first-class output | verify/Run Receipt-Gate | ✅ ENFORCED |

"Coverage" here means an automated CI gate exists and blocks merge on violation — not that the
clause is unimportant or unenforced by convention/review. A clause reading UNCOVERED is a
candidate for a future automated check, not evidence the platform ignores it.
