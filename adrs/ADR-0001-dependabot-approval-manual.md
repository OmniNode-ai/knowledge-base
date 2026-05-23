---
type: adr
status: accepted
date: "2026-03-25"
title: "ADR-0001: Dependabot PR Approval Remains Manual"
adr_id: ADR-0001
topics: [ci, dependabot, automation, github-actions]
refs:
  - doctrine/fail-fast-and-loud.md
  - doctrine/evidence-is-first-class-output.md
supersedes: []
superseded_by: []
---

# ADR-0001: Dependabot PR Approval Remains Manual

## Context

GitHub requires explicit approval for Dependabot workflow runs before CI will execute on those PRs. While the GitHub REST API does support programmatic approval via `POST /repos/{owner}/{repo}/actions/runs/{run_id}/approve`, and the `gh` CLI can invoke this endpoint, organization policy requires UI-based approval for the Dependabot actor. The `gh` CLI has no dedicated `gh run approve` subcommand, though the raw API call works.

The practical frequency is low — a handful of dependency bump PRs per week across all repositories.

## Decision

Accept Dependabot PR CI approval as a manual step. This is a GitHub platform limitation, not an OmniNode pipeline gap. The automated merge-sweep classifies Dependabot PRs as requiring manual approval and skips them without looping or attempting workarounds.

## Alternatives Considered

1. **Playwright browser automation** — Rejected: fragile, depends on GitHub UI structure, breaks on UI changes, requires browser session management. The fragility cost exceeds the time saved on low-frequency PRs.

2. **Personal access token with workflow scope** — Technically feasible: GitHub supports programmatic approval using a PAT with `actions: write` scope via the `POST /repos/{owner}/{repo}/actions/runs/{run_id}/approve` endpoint. However, organization policy enforces UI-based approval for the Dependabot actor, so this path requires a policy change before it can be automated.

3. **Disable required CI for Dependabot PRs** — Rejected: security risk; bypasses CI validation for dependency changes.

## Consequences

- Dependabot PRs require a brief manual approval step during daily triage (approximately two minutes for all repositories in a batch).
- Automated merge tooling explicitly skips Dependabot PRs rather than attempting workarounds, making the boundary visible rather than silent.
- If GitHub adds first-class API support for Dependabot approval, this decision should be revisited and the manual step automated.

## Related Doctrine

## Derived From

Friction triage review identifying Dependabot PRs as consistently blocked at the CI approval gate.

## Evidence

GitHub REST API documentation confirms the `POST .../runs/{run_id}/approve` endpoint exists but does not bypass the organization-level policy for the Dependabot actor.

## Supersedes

## Superseded By
