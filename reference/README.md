# Reference

Cross-repository factual lookup: node inventories, protocol catalogs, event surfaces, the repository registry, terminology, and shared standards. The distinguishing test is that the reader is trying to **look something up** — if they are trying to accomplish a task, it belongs in [`guides/`](../guides/README.md).

## What does not belong here

Versioned API reference generated from a release tag stays in its own repository. It is only true for the tag it was generated from, and separating it from the tooling that regenerates it guarantees it goes stale. This section is for conceptual and cross-repository reference: facts that span more than one repository, which no single repository can own without its copy immediately drifting from the others.

## This section is declared but not yet open

Do not add documents here yet.

The validation tooling recognizes a closed set of eight artifact types and discovers files with a top-level glob over the provenance sections. A markdown file placed here today is not rejected — it is **silently skipped** by every check, which on a public repository is worse than being rejected.

Extending the tooling to this artifact class, and to recursive discovery, is a tracked prerequisite that lands before the first documentation migration.

See [docs-taxonomy.md](../docs-taxonomy.md) for what will belong here, and [migration-manifest.yaml](../migration-manifest.yaml) for the planned mapping.
