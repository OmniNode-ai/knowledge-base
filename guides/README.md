# Guides

Task-oriented how-to documentation: getting started, onboarding, integration walkthroughs, and per-component usage guides. The distinguishing test is that the reader is trying to **do** something — if they are trying to look a fact up, it belongs in [`reference/`](../reference/README.md); if they are trying to operate or recover a running system, it belongs in [`runbooks/`](../runbooks/README.md).

## Start here

Three guides cover the three ways to run ONEX, and a fourth covers running a combination of them. They are ordered, and the order is the recommendation.

| | Guide | Run it |
|---|---|---|
| **1** | **[Getting started locally](getting-started-local.md)** | **On your own machine, with zero external infrastructure.** One package, one command, and a real event chain you can read back out of a local database file. No broker, no database server, no container runtime, no account, no configuration. **Start here** — this is the first-class entry path, not a demo mode. |
| **2** | [Self-hosting the full stack](getting-started-self-hosted.md) | On your own infrastructure, in containers. The scale-up chapter: a real broker, PostgreSQL, a cache, an identity provider, and the runtime services on top. Read it when you have actually outgrown tier-0 — the page opens with the list of reasons that qualify. |
| **3** | [Connecting to the cloud](connecting-to-the-cloud.md) | On someone else's machines. Get a credential, point a client at the public API, submit a job, read the result back. Optional; nothing in ONEX requires it. |
| **4** | [Combining deployment tiers](combining-deployment-tiers.md) | More than one of the above at once — which is what almost everyone actually runs. The seams between the tiers: which knob moves you across one, what changes when you cross it, and what stays identical. Read it after the three it composes. |

If you are evaluating the platform, guide 1 is the whole evaluation. It runs the same command → handler → terminal-event → projection chain a distributed deployment runs; scaling up later swaps two adapters rather than rewriting your nodes.

## Everything else

## This section is open

Frontmatter `type: guide`, with `status: draft | current | stale | deprecated`. The validator discovers files recursively, so a nested path (e.g. `guides/getting-started/install.md`) is validated the same as a top-level one.

See [docs-taxonomy.md](../docs-taxonomy.md) for what belongs here, and [migration-manifest.yaml](../migration-manifest.yaml) for the planned mapping.
