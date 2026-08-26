---
type: runbook
status: current
date: "2026-08-26"
title: "omnibase_compat Release"
topics:
  - omnibase-compat
  - release
  - pypi
refs: []
---

# omnibase_compat Release

Canonical procedure for publishing the `omnibase_compat` package to PyPI.

> **Last verified:** 2026-08-26, line by line against the repository's live
> `Release` workflow (`.github/workflows/release.yml`) and `pyproject.toml`.
> Two guarantees the earlier in-repo copy of this runbook omitted — the PyPI
> pin-resolvability check and the automatic `main` fast-forward — are stated
> below and were confirmed present as workflow steps at that commit.

## Preconditions

- The intended version is set in `[project].version` in `pyproject.toml`.
- The working tree is clean before tagging.
- CI passes on the release candidate branch.
- A PyPI publish token is configured as the `PYPI_TOKEN` repository secret.
- The release runs through the repository's `Release` workflow
  (`.github/workflows/release.yml`).
- **`main` advances automatically on a successful non-`rc` release.** There is
  no separate promotion pull request to `main` any more: the release job
  fast-forwards `main` to the released tag's commit SHA as its final step (see
  [Workflow guarantees](#workflow-guarantees)). Do not plan a manual promotion
  step, and do not treat `main` as a branch you land work onto directly —
  releases are cut from the integration branch and `main` follows them.

## Release by tag

1. Confirm the package version:

   ```bash
   rg -n '^version = ' pyproject.toml
   ```

2. Run the local validation path:

   ```bash
   uv sync --dev --frozen
   uv run python scripts/validate_no_upstream_deps.py
   uv run python scripts/check_compat_retention.py
   uv run ruff check src/
   uv run mypy src/omnibase_compat --strict
   uv run pytest -m unit --tb=short
   uv build
   ```

   Run `pytest` with **no positional path** so it inherits `testpaths` from
   `pyproject.toml` (`src/omnibase_compat/tests` and the root `tests/`).
   Passing `src/omnibase_compat/tests/` explicitly silently drops the root
   `tests/` directory from collection.

3. Create and push a matching version tag:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

4. Watch the `Release` workflow run.

## Release by workflow dispatch

Use `workflow_dispatch` only when re-running a release from an existing tag.
Pass the full tag, including the `v` prefix:

```text
vX.Y.Z
```

The workflow checks out that tag and validates it against `pyproject.toml`.

## Workflow guarantees

The release workflow:

- Fails if the working tree is not clean after checkout.
- Fails if the tag does not match `[project].version`.
- Builds a wheel and source distribution with `uv build`.
- Fails if the expected wheel and sdist are not present in `dist/`.
- **Verifies that every declared runtime dependency pin actually resolves
  against the real PyPI index, before publishing.** The check installs the
  just-built wheel into a bare scratch virtualenv with no project
  configuration, using `uv pip install` rather than a project-aware resolve, so
  that a local `[tool.uv.sources]` git-revision override cannot mask a broken
  pin. A pin that does not resolve fails the release *before* `uv publish`
  runs. This exists because a sibling package was once published pinning a
  version of `omnibase-compat` that had never been released: nothing in the
  normal local or CI resolution path ever checked a package's declared
  dependency pins against the real index, because source overrides short-circuit
  it, and `uv build` bakes the unverified pin into the wheel's `Requires-Dist`
  metadata.
- Publishes the wheel and sdist with `uv publish`.
- Generates `SHA256SUMS.txt`.
- Creates a GitHub Release with the artifacts attached.
- Marks releases whose tag contains `rc` as prerelease.
- **Fast-forwards `main` to the released tag's commit SHA on every successful
  non-`rc` release.** This is a non-force push of an already-proven commit
  (release tags are cut from the integration branch, which its own CI plus this
  job have already validated), performed by the release job's own token.
  `rc` releases are skipped by an explicit condition and do not move `main`.

## Dependency policy during release

Do not add OmniNode packages as runtime dependencies to support release or
documentation tooling. The package may use such tooling in CI or dev contexts,
but its runtime dependencies must stay limited to its structural support
dependencies. Adding one to make a validator convenient defeats the entire
purpose of the package.

## Failure handling

| Failure | Fix |
|---|---|
| Tag / version mismatch | Update `pyproject.toml` or create the correct tag, then rerun. |
| Build failure | Fix package metadata or source issues, then create a new commit and tag. |
| **Dependency-pin resolvability check fails** | A declared runtime dependency pin does not exist on the real index. Fix the dependency declaration (and the lockfile) so the pin names a version that is actually published, then cut a new tag. Do not retry the same tag and do not relax the check — it is the only place a bad pin is caught before publication, and a published bad pin cannot be withdrawn from consumers who already resolved it. |
| Publish failure | Verify the publish token, PyPI project permissions, and whether the version already exists. |
| GitHub Release failure after PyPI publish | Rerun workflow dispatch for the same tag after confirming the artifacts exist. |
| `main` fast-forward failure after a successful publish | The release itself succeeded and is live on PyPI; only the branch pointer lagged. Confirm the tag's commit is a descendant of `main`, then fast-forward `main` to it. Never force-push `main` to "fix" this. |

## Related

- [omnibase_compat structural inventory](../reference/omnibase-compat-structural-inventory.md)
