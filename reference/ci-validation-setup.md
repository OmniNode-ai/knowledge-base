---
type: reference
status: current
date: "2026-08-25"
title: "CI Documentation Validation Setup"
topics: [ci, markdown-link-check, cross-repo-standard]
refs: []
---

# CI Documentation Validation Setup

How to add markdown link validation to an ONEX repository.

**Source**: omnibase_core `docs/standards/CI_VALIDATION_SETUP.md`. Verified live against
omnibase_core@dev 2026-08-25: the `onex-validate-links` console-script entry point, the
pre-commit hook, `.github/workflows/validate-docs.yml`, and `.markdown-link-check.json` all
exist as described — no drift found.

## Pre-commit Hook (repos with omnibase_core dependency)

Add to `.pre-commit-config.yaml` in a `- repo: local` block:

```yaml
- id: onex-validate-links
  name: Validate markdown links
  entry: uv run onex-validate-links --verbose
  language: system
  types: [markdown]
  pass_filenames: false
  stages: [pre-commit]
```

Repos with this hook: omnibase_core, omnibase_infra, omnibase_spi, omniclaude,
omniintelligence, omnimemory, onex_change_control.

## CI via Reusable Workflow (all repos)

```yaml
jobs:
  docs:
    uses: OmniNode-ai/omnibase_core/.github/workflows/validate-docs.yml@main
    with:
      check-external: true
```

For repos **without** omnibase_core as a dependency (omnidash, omninode_infra, omniweb,
omnibase_compat):

```yaml
jobs:
  docs:
    uses: OmniNode-ai/omnibase_core/.github/workflows/validate-docs.yml@main
    with:
      check-external: true
      standalone: true
```

`standalone: true` installs the validator via `uv tool install omnibase_core` instead of
expecting it in the project's own dependencies.

## Configuration File

Create `.markdown-link-check.json` in the repository root:

```json
{
    "ignorePatterns": [
        {"pattern": "^https://linear\\.app"},
        {"pattern": "^https://github\\.com/OmniNode-ai"},
        {"pattern": "^http://localhost"},
        {"pattern": "^https://localhost"}
    ],
    "excludeFiles": [
        ".pytest_cache/**",
        ".venv/**",
        "venv/**",
        "node_modules/**",
        "archived/**"
    ],
    "checkExternal": false,
    "externalTimeout": 5000
}
```

- `ignorePatterns`: regex patterns for URLs to skip (`{"pattern": "regex"}` per entry).
- `excludeFiles`: glob patterns for files to skip entirely.
- `checkExternal`: whether to check HTTP/HTTPS links (overridden by `--check-external`).
- `externalTimeout`: timeout in milliseconds for external link checks.

## Cross-Repo Validation

To validate links that reference other repos (e.g. `omnibase_spi/docs/REGISTRY.md`):

```bash
uv run onex-validate-links --verbose --cross-repo-root /path/to/workspace
```

## CLI Reference

```bash
uv run onex-validate-links                              # Validate all internal links
uv run onex-validate-links --verbose                    # Show all checked links
uv run onex-validate-links --check-external             # Also check HTTP/HTTPS links
uv run onex-validate-links docs/                        # Validate specific directory
uv run onex-validate-links --config path/to/config.json # Custom config file
uv run onex-validate-links --cross-repo-root /path      # Cross-repo link resolution
```

Exit codes: `0` = all valid, `1` = broken links, `2` = script error.

## Versioning

Callers use `@main` by default. If the reusable workflow interface changes incompatibly, a
tagged release will be created (e.g. `@v1`) and all callers updated to pin to the tag.
