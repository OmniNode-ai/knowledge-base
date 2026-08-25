---
type: reference
status: current
date: "2026-08-25"
title: "Repository Registry"
topics:
  - org-registry
  - repositories
refs: []
---

# Repository Registry

> **Last verified:** 2026-08-25. Three surfaces used to disagree on the org's
> public repositories — the organization profile (`OmniNode-ai/.github`
> `profile/README.md`), the platform installer manifest
> (`OmniNode-ai/omnibase` `repos.yaml`), and the installer's own README
> "What's Included" table. This page reconciles them: **`omnibase/repos.yaml`
> is the single canonical source** for the platform-component list below
> (it is the one machine-read surface — `make install` parses it directly),
> and both the organization profile table and this page are generated from
> it. Names, types, and descriptions came from `repos.yaml` at the commit
> current as of the verification date above; re-derive rather than trusting
> this table as it ages. Repositories are named here without a link — see
> "Why no repository links" below.

## Platform Components

The repositories `make install` clones when you run the `omnibase`
installer. This is the literal content of `repos.yaml`.

| Repository | Type | Description |
|---|---|---|
| `omnibase_core` | python | Core models, contracts, validators, CLI |
| `omnibase_infra` | python | Infrastructure services, Kafka, Postgres |
| `omnibase_spi` | python | Service provider interface protocols |
| `omnibase_compat` | python | Shared structural package for cross-repo enums and DTOs |
| `omniclaude` | python | Claude Code agent plugin, hooks, skills |
| `omnidash` | node | Composable widget dashboard (Vite + React) |
| `omniintelligence` | python | Intelligence nodes — intent, drift, review |
| `omnimemory` | python | Document ingestion and semantic retrieval |
| `omnimarket` | python | Market skill nodes (`onex skill`), co-installed into the `omnibase_infra` venv |
| `onex_change_control` | python | Drift detection and governance |

## Other Public Repositories

Public repositories that are not part of the installer's clone set — the
installer itself, the documentation home, and adjacent products.

| Repository | Description |
|---|---|
| `omnibase` | The flagship installer — one command to clone, build, and run the full platform. This table's canonical `repos.yaml` lives here. |
| `knowledge-base` | This repository — canonical home for OmniNode's external documentation: architecture, guides, reference, runbooks, and provenance |
| `omnigemini` | Gemini-native ONEX skill execution runtime — whole-project grounding via Gemini's long context window |

## Private Repositories

Real org repositories that are intentionally not part of the public
installer's clone set. They are named here so the registry is complete —
not silently omitted — but carry no repository link, consistent with the
public installer never referencing private repos by name (see "Why
`repos.yaml`" below).

| Repository | Description |
|---|---|
| `omninode_infra` *(private)* | API service, Kubernetes manifests, and Terraform infrastructure |
| `omniweb` *(private)* | Public landing page and waitlist site |

## Why no repository links

This page names repositories by their bare identifier, not as GitHub links.
Every other reference page in this knowledge base follows the same
convention: the only cross-repo GitHub URL anywhere in this tree is the
fixed "Full documentation" pointer back to this repository itself. A
registry page is exactly the place that convention would otherwise get
violated by design, so it is stated here explicitly rather than left
implicit.

## Why `repos.yaml` and not the org profile or the README table

Before this reconciliation, `repos.yaml` itself carried two private-repo
rows (`omninode_infra`, `omniweb`) that made the public installer's first
command — `git clone` against a private URL — fail for every public user.
The 2026-08-18 operator resolution for that defect was to **remove private
repos from the public installer manifest entirely**, not merely tolerate the
failed clone. That resolution is why the Platform Components table above
carries no private rows: `repos.yaml` is executable-adjacent (`make
install` parses it), so it stays public-repo-only. The Private
Repositories table above is sourced separately, from the org's live repo
list, specifically so annotating private repos here (a descriptive page, not
an installer) doesn't reintroduce that disclosure risk while still keeping
the registry honest about what exists.

## Keeping this page current

1. Edit `repos.yaml` in `OmniNode-ai/omnibase` first — it is the source of
   truth for the Platform Components table.
2. Regenerate this page's Platform Components table to match.
3. Regenerate the `OmniNode-ai/.github` `profile/README.md` Core
   Repositories table to match — it carries no independently-maintained
   descriptions of its own.
