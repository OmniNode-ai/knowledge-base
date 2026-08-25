---
type: reference
status: stale
date: "2026-08-25"
title: "Standard Documentation Layout (omnibase_core)"
topics: [documentation, doc-layout, cross-repo-standard, omnibase_core]
refs: []
---

# Standard Documentation Layout

Prescriptive structure for the `docs/` directory in omnibase_core, as originally authored.

**Source**: omnibase_core `docs/standards/STANDARD_DOC_LAYOUT.md`

> **2026-08-25 migration note.** This document is migrated as part of the same change that
> makes its own "Required Directories" table partly obsolete for omnibase_core: the
> `decisions/`, `standards/`, and `troubleshooting/` subdirectories it describes are, as of
> this migration, thinned to knowledge-base pointer stubs (their canonical content lives here,
> in the knowledge base's `adrs/`, `reference/`, and `guides/` sections respectively). This
> repo's own copy is marked `status: stale` for that reason — it still describes the
> pre-migration layout, and other repos may still follow this template unmodified. A
> cross-repo reconciliation of this template into one canonical version (the org's other repos
> carry their own, independently-diverged copies) is tracked separately and is not performed
> as part of this migration pass — only the omnibase_core-authored copy is migrated here.

---

## Required Directories (as originally authored)

```text
docs/
├── architecture/          # How ONEX works (system design, data flow, protocols)
├── conventions/           # Coding standards and naming conventions
├── decisions/             # ADRs — why things work the way they do
├── getting-started/       # Installation, quick start, first node
├── guides/                # Step-by-step tutorials and how-to guides
│   ├── node-building/     # Node building tutorial series
│   └── templates/         # Production-ready node templates (canonical location)
├── reference/              # API docs, contract specs, service wrappers
│   └── api/               # Per-module API reference (enums, models, nodes, utils)
└── standards/             # Normative specs (terminology, topic taxonomy, this file)
```

## Optional Directories

```text
docs/
├── ci/                    # CI monitoring, purity failures, deprecation warnings
├── contracts/             # Contract guides (handler, introspection, operation bindings)
├── patterns/              # Implementation patterns (circuit breaker, FSM, anti-patterns)
├── performance/           # Benchmark results and threshold definitions
├── services/              # Service documentation
├── testing/               # Test strategy, parallel testing, performance testing
└── troubleshooting/       # Debugging guides
```

## File Naming

| Pattern | Use |
|---------|-----|
| `UPPER_SNAKE_CASE.md` | All documentation files |
| `README.md` | Directory index files only |
| `ADR-NNN-<slug>.md` | Architecture Decision Records in `decisions/` |
| `NN_<TITLE>.md` | Numbered tutorial series (e.g. `01_WHAT_IS_A_NODE.md`) |

## Doc Authority Model

| Location | Contains | Does NOT Contain |
|----------|----------|------------------|
| **CLAUDE.md** | Hard constraints, invariants, rules, navigation pointers | Tutorials, API reference, architecture explanations, code examples |
| **docs/** | Explanations, tutorials, deep dives, architecture, reference | Rules that override CLAUDE.md |

**No duplication**: `CLAUDE.md` links to `docs/` sections; it does not re-explain what
`docs/` already covers.

## `INDEX.md` Requirements

The root `docs/INDEX.md` must include a Documentation Authority Model table, a
Quick-Navigation table (intent-based), a Documentation Structure table linking every doc, and
a Document Status summary table. All links must use relative paths and resolve to existing
files.

## Deleted Content Policy

Completed plans, stale analyses, and point-in-time reports are deleted outright; no
`archive/` directories — if unused, delete it; inbound links to deleted files must be
removed or updated in the same commit.

---

**Migrated to the knowledge base 2026-08-25, unchanged in substance** — this record documents
the layout as omnibase_core's own standard, correct as a description of that repository's
intent even though this migration itself moves the `decisions/`/`standards/`/`troubleshooting/`
content elsewhere.
