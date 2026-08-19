# OmniNode Knowledge Base

This repository is the canonical home for OmniNode's external documentation — the single source of truth for how the platform works, how to use it, and why it is shaped the way it is. Product repositories keep only what must physically ship beside their code, and point here for everything else.

## What This Is

Two kinds of documentation live here, and telling them apart is what makes the collection navigable.

**Consumer documentation** answers *how do I use this*: guides, cross-repository reference, and operational runbooks. It is written for someone building against OmniNode, and it is deliberately independent of any single repository's release tag — so that finding out how something works never requires first knowing which repository implements it.

**Architectural provenance** answers *why is it like this*: plans, technical designs, decision records, pivots, doctrine, experiments, and durable evidence. Rather than architecture existing only in the heads of contributors or scattered across pull request descriptions, this repository makes the full evolutionary arc visible — what was decided, what changed, and what the evidence was.

## The charter

The knowledge base is canonical for all external product, platform, architecture, and how-to documentation.

A product repository keeps a closed set of documents that cannot meaningfully live anywhere else: its landing README, its contribution guide, its executable installers, its versioned API reference tied to a release tag, its agent operating context, and the platform-convention files expected at fixed paths. Each of those is trimmed to the minimum that serves its purpose and carries a pointer here. Everything else is canonical, lives here, and exists in exactly one place.

That last clause is the whole point. The same claim — a node count, a version badge, a workflow name, a base-branch instruction — was previously copy-pasted into many repositories, where each copy then drifted independently. Fixing each copy in place guarantees they re-drift. One canonical copy is the only arrangement where a correction stays correct.

The rule for deciding where any individual document belongs is written down, not left to judgment: see **[docs-taxonomy.md](docs-taxonomy.md)**.

## Sections

| Directory | What it contains |
|-----------|-----------------|
| [`doctrine/`](doctrine/README.md) | Stable platform principles that govern OmniNode's architecture |
| [`adrs/`](adrs/README.md) | Architecture Decision Records — the formal decision ledger |
| [`architecture/`](architecture/README.md) | Technical Design Documents describing platform architecture — primitives, boundaries, runtime flow, and proof requirements |
| [`pivots/`](pivots/README.md) | Architectural pivots capturing fundamental changes in understanding |
| [`deep-dives/`](deep-dives/README.md) | Curated narrative records of architectural evolution |
| [`plans/`](plans/README.md) | Selected implementation plans showing intended work and proposed paths |
| [`experiments/`](experiments/README.md) | Hypothesis-driven experiments with structured outcomes |
| [`evidence/`](evidence/README.md) | Links between architectural claims and durable proof artifacts |
| [`indexes/`](indexes/README.md) | Auto-generated indexes for browsing artifacts by date, topic, or type |
| [`guides/`](guides/README.md) | Task-oriented how-to documentation — **declared, not yet open** |
| [`reference/`](reference/README.md) | Cross-repository factual reference — **declared, not yet open** |
| [`runbooks/`](runbooks/README.md) | Parameterized operational procedures — **declared, not yet open** |

The three consumer sections are declared by the charter but are **not yet accepting content**. The validation tooling does not recognize their artifact classes and does not discover files recursively, so a document placed there today would be silently unvalidated rather than rejected. Extending the tooling is a tracked prerequisite that lands before the first migration. Each section README states this at the point where someone would otherwise add a file.

No documentation has migrated yet. [`migration-manifest.yaml`](migration-manifest.yaml) records the planned mapping; every row is at `not-started`.

## Core Philosophy

**Truth must be proven.** Architectural claims require durable evidence — pull requests, CI runs, replay validation, or benchmarks. Assertions without proof are hypotheses.

**Completion requires durable evidence.** A decision is not accepted, a pivot is not confirmed, and an experiment is not concluded until the evidence artifact exists and is referenced.

**Decisions must be inspectable.** Every decision record captures not just what was decided but what was considered and rejected, and why. The reasoning is part of the record.

**Evolution must be replayable.** Pivots capture the before and after state, including which assumptions were wrong and what operational pressure forced the change. Future contributors should be able to reconstruct the reasoning arc from first principles.

## Getting Started

The best entry point is [`doctrine/`](doctrine/README.md) — the stable principles that govern the platform. From there, decision records show specific choices that instantiate those principles, and pivots show where the principles themselves evolved.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose new artifacts, the PR process, and sanitization requirements. See [docs-taxonomy.md](docs-taxonomy.md) for deciding whether a document belongs here at all.

## Validation

```bash
uv run python scripts/validate.py
```

`scripts/validate.py` runs five checks over every artifact file: frontmatter schema (a discriminated Pydantic union, one model per artifact type), `refs:` cross-reference integrity, sanitization (no internal information in public content), index freshness (committed `indexes/` match generated output), and broken relative markdown links. A separate gate, `scripts/check_text_sanitization.py`, scans commit messages and PR title/body against the same forbidden-pattern list — both share `scripts/sanitization_patterns.py` as the single source of patterns.

Two coverage limits are worth knowing before relying on a green run: the checks cover the eight provenance sections only, discovered at their top level, so nested subdirectories and the three declared consumer sections are not scanned; and repository-root documents — this README, `CONTRIBUTING.md`, `CLAUDE.md`, the taxonomy, and the manifest — are outside the artifact scan entirely. The sanitization discipline applies to them regardless of whether a script checks it.

<!-- verified against scripts/validate.py, scripts/check_text_sanitization.py, scripts/sanitization_patterns.py, and .github/workflows/ci.yml on the 2026-08-19 charter refresh -->
