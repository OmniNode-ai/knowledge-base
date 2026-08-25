# OmniNode Documentation Taxonomy

This document is the spec that decides **where any OmniNode document lives**. Every documentation migration PR cites a row of it. It is the contract between this repository and the product repositories: the knowledge base is canonical for external documentation, and product repos keep only what must physically ship beside their code.

Status: **adopted**, all eleven sections open. Content migration is in progress, repo by repo — see [Current state](#current-state-what-is-and-is-not-live-yet) for what has and has not moved yet.

---

## The decision rule

Exactly one bucket per document. Apply the tests in order and stop at the first match — the ordering is the rule, not a suggestion, because several documents match more than one description.

1. **Is it a dated point-in-time artifact?** An evidence bundle, an audit snapshot, a receipt, a run transcript — something whose value is that it records a specific moment. → **Bucket D.** It stays where it is. Updating it destroys the thing that made it worth keeping.
2. **Is it on the closed Bucket-B list below?** The list is closed; being "important" or "frequently read" does not add a document to it. → **Bucket B.** Stays in the repo, trimmed to minimum, carries the pointer.
3. **Is its content sensitive after scrubbing?** Not "does it contain an address" — that is fixed by scrubbing. This asks whether the *substance* discloses something that should not be public: security-scanner configuration, secret-handling flow, or a list of what bypasses a detection control. → **Bucket C.** Never migrates here — routes to a private, teammate-accessible internal documentation home instead.
4. **Everything else** → **Bucket A.** The knowledge base. This is the default, not the exception.

The common error is reaching for Bucket B because a document feels repo-specific. A guide to using one component is still Bucket A: it describes the platform, and a reader should not need to know which repository implements a thing in order to find out how to use it.

---

## Bucket A — Canonical (this repository)

Anything an external reader or contributor consumes to understand *the platform*, independent of any one repository's code tag.

### Provenance sections (live today)

| Section | What belongs there |
|---|---|
| `doctrine/` | Stable platform principles that govern the architecture |
| `adrs/` | Architecture Decision Records — the formal decision ledger |
| `architecture/` | Technical Design Documents — primitives, boundaries, runtime flow, proof requirements |
| `pivots/` | Fundamental changes in understanding, with the assumption that failed |
| `deep-dives/` | Curated narrative records of architectural evolution |
| `experiments/` | Hypothesis-driven experiments with structured outcomes |
| `evidence/` | Links between architectural claims and durable proof artifacts |
| `plans/` | Selected implementation plans showing intended work and proposed paths |
| `indexes/` | Generated browse-by-date/topic/type indexes |
| `schemas/` | Generated frontmatter JSON schema |

### Consumer sections

| Section | What belongs there | Distinguishing test |
|---|---|---|
| `guides/` | Task-oriented how-to: getting started, onboarding, integration walkthroughs, per-component usage guides | The reader is trying to *do* something |
| `reference/` | Cross-repo factual lookup: node inventories, protocol catalogs, event surfaces, the repository registry, terminology | The reader is trying to *look something up* |
| `runbooks/` | Operational procedures, parameterized — never carrying real addresses or credentials | The reader is trying to *operate or recover* something |

### The reference seam — read this before moving anything named "reference"

Two different things are called API reference, and they go to opposite buckets:

- **Versioned API reference generated from a code tag** — the symbol-by-symbol surface of a released package — is **Bucket B**. It stays in its repository. It is only true for the tag it was generated from, and moving it here would strand it from the thing that regenerates it.
- **Conceptual and cross-repo reference** — inventories, catalogs, event surfaces, glossaries, anything spanning more than one repository — is **Bucket A**. No single repository can own a fact about several repositories without one copy immediately drifting from the others.

A document that mixes both is split along that line, not filed under whichever half is larger.

---

## Bucket B — Repo-intrinsic (stays in the repo, thin, with a pointer)

Only what must physically ship beside the code. **This list is closed.**

| Kept in repo | Why it cannot move |
|---|---|
| `README.md` | It is the repository's landing page |
| `CONTRIBUTING.md` | Contribution flow is repo-scoped: branch, CI, review |
| Installer scripts and their manifests | Executable, not prose |
| Versioned API reference | Tied to the exact code tag it documents; regenerated per release |
| `CLAUDE.md` / `AGENT.md` | Agent operating context, read in-tree by tooling |
| `LICENSE`, `SECURITY.md`, `CODE_OF_CONDUCT.md` | Platform-convention files expected at a fixed path |

Every Bucket-B document is trimmed to the minimum needed to serve its one purpose, and carries this pointer verbatim:

```markdown
Full documentation → https://github.com/OmniNode-ai/knowledge-base
```

Verbatim matters: a drift guard matches this string, so a reworded variant reads as a missing pointer.

A bucket-B row may also declare `max_lines` in the migration manifest — a line-count budget for the thinned document. The drift guard fails a row that exceeds its declared budget, the same way it fails one that drops the pointer. `max_lines` is optional; a row without it is not size-checked.

---

## Bucket C — Restricted (private internal home)

Documents whose *content* is sensitive even after every address and path has been scrubbed. Scrubbing removes literals; it does not remove disclosure. A fully parameterized runbook can still describe operational controls or failure-mode internals, and a document listing what a detection control ignores is a map of exactly where to hide.

**Bucket C never publishes to this repository.** A document that reaches test 3 does not land here — it is corrected/annotated in place, or moved to a private, teammate-accessible internal documentation home maintained separately from this public repository (and separate from any individual's personal working repo). Consistent with this repo's own sanitization rule against referencing private repos from public content, the specific internal destination is tracked internally, not named here. Until a document is actually moved, it is recorded in the migration manifest as `sensitivity: restricted`, `destination: private-internal-kb`, `cutover_state: not-started`.

This closes what was previously an open decision (where restricted documents live, and whether a new per-document human sensitivity-review step gates publication here): resolved as above — there is no new review step, because Bucket-C content structurally never targets this repository in the first place. Do not resolve Bucket C by scrubbing harder. Test 3 is about substance.

---

## Bucket D — Dated point-in-time artifacts (stay put)

Evidence bundles, audit snapshots, receipts, run transcripts. These are correct *as snapshots* and are not migrated. Hygiene scrubbing still applies to them — a snapshot may record what happened without recording a live address.

---

## Preconditions on publication

Three gates, all of which apply before a document may land here.

**Scrubbed first.** A document is not eligible to move until its addresses, network topology, machine names, home directory paths, and personal identifiers are replaced with placeholders. Scrubbing is a precondition of migration, not a step within it.

**Placeholder convention.** Use these tokens rather than inventing new ones:

| Token | Replaces |
|---|---|
| `<onex-host>` | A service host address |
| `<kafka-bootstrap-servers>` | A broker bootstrap address |
| `<runner-home>` | A CI runner home directory path |
| `<repo-root>` | A local checkout path |
| `<cluster-ip>` | A cluster address |

Where a procedure needs a real value to be operable, the value belongs in a restricted operational note and the published document stays parameterized.

**Broken documents do not migrate unchanged.** A document that teaches an API that does not exist must be corrected before publication, or landed in a non-indexed quarantine location until it is verified. Publishing it here unchanged would be worse than leaving it in place: it would move a known-false claim onto the surface that is supposed to be authoritative. This exception is scoped to documents assessed as broken — documents assessed as current or stale migrate mechanically and are corrected afterward.

---

## Current state: what is and is not live yet

Honest accounting, so nobody files a document into a section that cannot yet hold it.

- **All eleven sections are live** and validated on every PR — the provenance sections plus `guides/`, `reference/`, and `runbooks/`. The validator recognizes all eleven artifact classes, discovers files recursively within every section, and fails closed on any `.md`/`.yaml`/`.yml` file outside a recognized location (a declared section, a generated-content directory, or the root-file allowlist) rather than silently skipping it.
- **Content migration has begun, one repo at a time.** As of 2026-08-25, `omnibase_core` is the first repository with a fully-migrated `docs/decisions/**` + `docs/standards/**` + `docs/troubleshooting/**` set (38 ADRs, 6 reference documents, and 1 guide now trace to this repository across all contributing repos combined) — its manifest entry is at repo-level `cutover_state: moved` with a per-document row for every candidate. Every other repository's manifest entry is still at `cutover_state: not-started`.
- **The drift guard is built and fixture-proven, but not wired into any product repo yet.** `scripts/docs_drift_guard.py` in this repository enforces both rules — bucket-A re-growth and the bucket-B pointer/size budget — and `.github/workflows/docs-drift-guard-reusable.yml` packages it as one reusable workflow a product repo's own CI can call. No product repo calls it yet, so today nothing actually stops a repository from re-growing a copy of a document that has moved here — the guard has code, tests, and (for `omnibase_core`) real manifest rows to check against, but not live enforcement.

---

## Migration manifest

The per-document mapping lives in [`migration-manifest.yaml`](migration-manifest.yaml) — one row per document, recording its bucket, destination, owner, sensitivity, assessed correctness, the evidence behind that assessment, and its cutover state. The manifest is the single artifact that both the migration and the drift guard read, so the guard enforces a declared mapping rather than guessing from a document's shape.

It currently holds per-repository mappings only. Per-document rows are produced during migration.
