# OmniNode Knowledge Base

This repository is the public architectural provenance record for OmniNode — the connective tissue between plans, architecture decision records, pivots, doctrine, experiments, and durable evidence. It exists so that the reasoning behind every significant architectural choice is inspectable, replayable, and honest about what was tried and why things changed.

## What This Is

The knowledge base connects plans, ADRs, pivots, doctrine, experiments, and evidence into an inspectable architectural history. Rather than architecture existing only in the heads of contributors or scattered across PR descriptions, this repository makes the full evolutionary arc visible: what was decided, what changed, and what the evidence was. Each artifact type captures a different kind of architectural truth, and together they form a provenance chain from initial assumption to current understanding.

## Artifact Types

| Directory | What it contains |
|-----------|-----------------|
| [`doctrine/`](doctrine/README.md) | Stable platform principles that govern OmniNode's architecture |
| [`adrs/`](adrs/README.md) | Architecture Decision Records — the formal decision ledger |
| [`pivots/`](pivots/README.md) | Architectural pivots capturing fundamental changes in understanding |
| [`deep-dives/`](deep-dives/README.md) | Curated narrative records of architectural evolution |
| [`plans/`](plans/README.md) | Selected implementation plans showing intended work and proposed paths |
| [`experiments/`](experiments/README.md) | Hypothesis-driven experiments with structured outcomes |
| [`evidence/`](evidence/README.md) | Links between architectural claims and durable proof artifacts |
| [`indexes/`](indexes/README.md) | Auto-generated indexes for browsing artifacts by date, topic, or type |

## Core Philosophy

**Truth must be proven.** Architectural claims require durable evidence — PRs, CI runs, replay validation, or benchmarks. Assertions without proof are hypotheses.

**Completion requires durable evidence.** A decision is not accepted, a pivot is not confirmed, and an experiment is not concluded until the evidence artifact exists and is referenced.

**Decisions must be inspectable.** Every ADR records not just what was decided but what was considered and rejected, and why. The reasoning is part of the record.

**Evolution must be replayable.** Pivots capture the before and after state, including which assumptions were wrong and what operational pressure forced the change. Future contributors should be able to reconstruct the reasoning arc from first principles.

## Getting Started

The best entry point is [`doctrine/`](doctrine/README.md) — the stable principles that govern the platform. From there, ADRs show specific decisions that instantiate those principles, and pivots show where the principles themselves evolved.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose new artifacts, the PR process, and sanitization requirements.

## Validation

```bash
uv run python scripts/validate.py
```

This validates frontmatter, cross-references, and ensures no internal information is present in public content.
