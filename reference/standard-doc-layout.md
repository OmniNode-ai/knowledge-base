---
type: reference
status: current
date: "2026-08-25"
title: "Standard Documentation Layout"
topics: [documentation, doc-layout, cross-repo-standard]
refs: []
---

# Standard Documentation Layout

Org-wide prescriptive structure for a repository's `docs/` directory. Every OmniNode
repository carried its own copy of this document, and the copies had independently
diverged — different directory lists, different naming rules, different `INDEX.md`
requirements. This is the single reconciled version; repositories point here instead
of carrying a copy (Wave 2 plan §7 item C7).

**Reconciled from four independently-diverged repository copies**: omniclaude,
omnibase_core, omnibase_infra, omniintelligence. Where the four agreed in substance
(the authority model, file naming, deleted-content policy, `INDEX.md` requirements)
this document states the shared rule once. Where they genuinely differed (which
directories a repository needs) this document gives the union as a menu, not a
mandate — a repository adopts the subset that matches what it actually has.

---

## Directory Structure

No single fixed directory list is imposed org-wide — the four source repositories
used real but different subsets, and this document does not collapse that into one
required list. Directories that recurred across three or more of the source repos
(role, not folder name):

| Directory | Role |
|-----------|------|
| `architecture/` | System design, data flow, component/protocol topology |
| `decisions/` | ADRs — why things work the way they do |
| `getting-started/` | Installation, quick start, first run |
| `guides/` | Step-by-step tutorials and how-to documents |
| `reference/` | API docs, contract/schema specs, module and topic reference |
| `standards/` | Normative specs for how the repo is structured and operated (this file, before a repo thins it to a pointer) |
| `conventions/` | Naming and coding-style conventions |

Directories one or two repos used, adopted only when a repo has content that
warrants them: `operations/` (runbooks, bootstrap procedures), `patterns/`
(implementation patterns — circuit breaker, FSM, error handling), `testing/` (test
strategy, integration/E2E infrastructure), `troubleshooting/` (debugging guides),
`migration/`, `performance/`, `plugins/`, `validation/`, `ci/`, `contracts/`,
`services/`.

A repository's own `docs/INDEX.md` is the authoritative statement of which
directories that repository actually uses — this file is the naming/policy
standard, not a per-repo directory census.

---

## File Naming

| Pattern | Use |
|---------|-----|
| `UPPER_SNAKE_CASE.md` | All documentation files (default) |
| `README.md` | Directory index files only |
| `ADR-NNN-<slug>.md` | Architecture Decision Records in `decisions/` |

No other lowercase or hyphenated filenames. A repo that inherited legacy
`kebab-case.md` files from before this rule was adopted may keep them but must not
create new ones in that form.

**Never**:
- Create versioned directories (`v1/`, `v2_0_0/`) — version through `contract.yaml` fields, not directory names.
- Use spaces in documentation filenames.

---

## Documentation Authority Model

Documents have two distinct purposes. Never mix them, and never duplicate content
between them — if the same fact appears in both, one of them is wrong.

| Location | Contains | Does NOT contain |
|----------|----------|-------------------|
| **`CLAUDE.md`** | Hard constraints, invariants, operational rules, performance budgets, failure modes, navigation pointers | Tutorials, architecture deep dives, full API reference, how-to content |
| **`docs/`** | Explanations, tutorials, architecture, guides, reference | Rules that override `CLAUDE.md` |

Rules:
- A rule Claude (or any agent) must follow during execution belongs in `CLAUDE.md`.
- Explanatory or educational content belongs in `docs/`.
- A reference table (topics, modules, schemas) belongs in `docs/reference/`.
- `CLAUDE.md` is read on every hook invocation / every session start — tutorials
  bloat that budget and belong in `docs/` instead.
- `CLAUDE.md` links to `docs/` sections; it does not re-explain what `docs/`
  already covers.

---

## Required Sections in Every Doc File

Every substantive documentation file should open with a one- or two-sentence
purpose statement — what this document covers and who it is for — before the body.
An index file (`README.md`) follows a simplified template: purpose sentence, then a
table listing every document in the directory with a one-line description.

---

## Deleted Content Policy

- Completed plans, stale analyses, point-in-time verification reports, and old
  proof-of-concept writeups are **deleted outright** when no active file
  references them by path.
- If a stale document still holds current guidance, promote that guidance into a
  live doc first, then delete the stale file.
- **Never** create `archive/` or `old/` directories. Stale content belongs in git
  history, not in the working tree.
- Inbound links to a deleted file must be removed or updated in the same commit
  that deletes it.

---

## `INDEX.md` Requirements

The root `docs/INDEX.md` must include:

1. **Documentation Authority Model** table (`CLAUDE.md` vs `docs/` roles — see above).
2. **Quick Navigation by Intent** — a table organized by what a reader is trying to
   do ("I want to... → go to...").
3. **Per-Section Structure Tables** — one table per directory, listing every
   document in that directory with a one-line description.
4. **Document Status Summary** — a table of documents with status `Current`,
   `Draft`, or `Deprecated`.

All links in `INDEX.md`, and in documentation generally, use relative paths and
must resolve to files that actually exist.

---

## Document Quality Standards

| Standard | Rule |
|----------|------|
| Purpose statement | Every doc opens with a single-sentence statement of what it covers |
| No duplication | Each fact lives in exactly one document; others link to it |
| Relative links | Cross-doc links use relative paths, never absolute filesystem paths |
| Link verification | All links resolve to existing files before committing |

---

## Checklist for New Documents

- [ ] Is this content appropriate for `docs/` (educational) vs `CLAUDE.md` (operational)?
- [ ] Does a document covering this topic already exist?
- [ ] Does the filename follow `UPPER_SNAKE_CASE.md` (or `ADR-NNN-<slug>.md` in `decisions/`)?
- [ ] Is it placed in the correct subdirectory?
- [ ] Is `docs/INDEX.md` updated to reference the new document?
- [ ] If in `reference/`: is the content authoritative and kept in sync with code?

---

**Migrated to the knowledge base 2026-08-25 as one reconciled document**, replacing
four independently-diverged per-repository copies (omniclaude, omnibase_core,
omnibase_infra, omniintelligence). Each source repository's `docs/standards/`
directory now carries a pointer stub at this location instead of its own copy.
