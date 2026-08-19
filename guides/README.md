# Guides

Task-oriented how-to documentation: getting started, onboarding, integration walkthroughs, and per-component usage guides. The distinguishing test is that the reader is trying to **do** something — if they are trying to look a fact up, it belongs in [`reference/`](../reference/README.md); if they are trying to operate or recover a running system, it belongs in [`runbooks/`](../runbooks/README.md).

## This section is declared but not yet open

Do not add documents here yet.

The validation tooling recognizes a closed set of eight artifact types and discovers files with a top-level glob over the provenance sections. A markdown file placed here today is not rejected — it is **silently skipped** by frontmatter validation, cross-reference checking, the sanitization guard, index generation, and broken-link detection alike. On a public repository, an unscanned document is a worse outcome than a rejected one.

Extending the tooling to this artifact class, and to recursive discovery, is a tracked prerequisite that lands before the first documentation migration.

See [docs-taxonomy.md](../docs-taxonomy.md) for what will belong here, and [migration-manifest.yaml](../migration-manifest.yaml) for the planned mapping.
