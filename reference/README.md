# Reference

Cross-repository factual lookup: node inventories, protocol catalogs, event surfaces, the repository registry, terminology, and shared standards. The distinguishing test is that the reader is trying to **look something up** — if they are trying to accomplish a task, it belongs in [`guides/`](../guides/README.md).

## What does not belong here

Versioned API reference generated from a release tag stays in its own repository. It is only true for the tag it was generated from, and separating it from the tooling that regenerates it guarantees it goes stale. This section is for conceptual and cross-repository reference: facts that span more than one repository, which no single repository can own without its copy immediately drifting from the others.

## This section is open

Frontmatter `type: reference`, with `status: draft | current | stale | deprecated`. The validator discovers files recursively, so a nested path is validated the same as a top-level one.

See [docs-taxonomy.md](../docs-taxonomy.md) for what belongs here, and [migration-manifest.yaml](../migration-manifest.yaml) for the planned mapping.

## ONEX kernel reference (omnibase_core)

Conventions, the validation framework and its ownership map, node archetypes, and the
hand-maintained API surface pages, migrated out of the `omnibase_core` repository. The
"versioned API reference stays in its own repository" rule above is about reference that a
release tag regenerates; these pages have no generator and were maintained by hand, so leaving
them beside the code would not have kept them true to any tag.

- [`onex-capability-naming.md`](onex-capability-naming.md) — ONEX Capability Naming Conventions
- [`onex-docstring-templates.md`](onex-docstring-templates.md) — ONEX Contract Model Docstring Templates
- [`onex-error-code-standards.md`](onex-error-code-standards.md) — ONEX Error Code Standards
- [`onex-file-headers.md`](onex-file-headers.md) — File Header Conventions
- [`onex-naming-conventions.md`](onex-naming-conventions.md) — ONEX Naming Conventions
- [`onex-terminology-guide.md`](onex-terminology-guide.md) — Terminology Guide
- [`onex-version-semantics.md`](onex-version-semantics.md) — Version Field Semantics in ONEX Models
- [`omnibase-core-api-documentation.md`](omnibase-core-api-documentation.md) — ONEX Core Public API Reference
- [`omnibase-core-contract-validator-api.md`](omnibase-core-contract-validator-api.md) — Contract Validator API
- [`omnibase-core-manifest-models.md`](omnibase-core-manifest-models.md) — Manifest Models
- [`omnibase-core-mixin-discovery-api.md`](omnibase-core-mixin-discovery-api.md) — Mixin Discovery API
- [`omnibase-core-service-wrappers.md`](omnibase-core-service-wrappers.md) — ONEX Service Wrappers - Pre-Composed Production-Ready Node Classes
- [`omnibase-core-validation-framework.md`](omnibase-core-validation-framework.md) — Omnibase Core Validation Tools
- [`omnibase-core-validation-ownership.md`](omnibase-core-validation-ownership.md) — Validation Ownership
- [`omnibase-core-api-enums.md`](omnibase-core-api-enums.md) — Enums API Reference - omnibase_core
- [`omnibase-core-api-models.md`](omnibase-core-api-models.md) — Models API Reference - omnibase_core
- [`omnibase-core-api-nodes.md`](omnibase-core-api-nodes.md) — Nodes API Reference - omnibase_core
- [`omnibase-core-api-utils.md`](omnibase-core-api-utils.md) — Utils API Reference - omnibase_core
- [`omnibase-core-contracts.md`](omnibase-core-contracts.md) — Contract.yaml Reference
- [`onex-node-archetypes.md`](onex-node-archetypes.md) — Node Archetypes Reference
- [`omnibase-core-example-contracts.md`](omnibase-core-example-contracts.md) — Example Contracts
- [`omnibase-core-example-effect-contracts.md`](omnibase-core-example-effect-contracts.md) — NodeEffect Contract Examples
