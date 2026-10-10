---
type: guide
status: draft
date: "2026-09-26"
title: "Declaring a Runtime Lane"
topics: [runtime, configuration, self-hosting, local]
refs:
  - guides/getting-started-self-hosted.md
---

# Declaring a Runtime Lane

Every ONEX runtime you run belongs to a **lane**: a name you choose for one deployment of the runtime, such as `local` on your laptop or `staging` on a shared host. The runtime learns which lane it is, and what that lane is for, from a small document you supply: the `runtime.lane` overlay document. No package names a lane, and there is no built-in default. A runtime that cannot find its lane's document refuses to start and tells you what is missing.

This page is for anyone running a runtime themselves, whether on one machine or in their own containers.

> **Status: draft.** This describes the lane declaration as it ships in the next releases of the ONEX runtime packages. Until those releases are out, a runtime does not yet read the document.

---

## What you supply

Two things, both set by whoever runs the runtime.

| What | Where | Example |
|---|---|---|
| The lane's name | the `ONEX_RUNTIME_LANE` environment variable of the runtime process | `ONEX_RUNTIME_LANE=local` |
| The lane's document | a `runtime.lane` overlay document in the runtime's one overlay source | below |

The document:

```json
{
  "schema_version": "runtime_lane.v1",
  "lane_id": "local",
  "roles": [],
  "description": "Single-machine install"
}
```

| Field | Meaning |
|---|---|
| `schema_version` | Always `runtime_lane.v1` for this version of the document. |
| `lane_id` | The lane's name. Lowercase letters, digits and hyphens, starting with a letter or digit, at most 64 characters. It must equal `ONEX_RUNTIME_LANE`. |
| `roles` | What the lane is for. **Leave it empty unless you know you need a role.** A role admits node contracts that declare they need it; an empty list means no role-gated contract attaches on this lane, which is right for almost every deployment. |
| `description` | One line for a reader. Required. |

No other field is accepted. The schema ships with the core package (`omnibase_core/schemas/config_overlay/runtime_lane.schema.json`), and the example above ships inside the infrastructure package (`omnibase_infra.examples.config_overlays`).

---

## Where the document goes

> **Naming note.** This book redacts the secrets-manager product name under its own sanitization gate, so the variable that carries the config store's address is described rather than named. Its exact name is in the runtime service manifests and `.env.example` in the infrastructure checkout.

A runtime reads its configuration documents from exactly **one** overlay source. It never reads both, and it never falls back from one to the other.

| Source | Selected by | Where the lane document lives |
|---|---|---|
| **store** | a non-blank secrets-manager address in the runtime's environment (the stack's own config store) | the store path for key `runtime.lane` at your environment and lane |
| **local-home** | `config_source: local-home` in `~/.onex/config.yaml` of the user the runtime runs as | `~/.omninode/config/<environment>/<lane>/runtime.lane.json`, mode `0600` |

`<environment>` is the value of `ONEX_ENVIRONMENT`. One machine can hold documents for several lanes side by side, because each lane has its own directory.

### On one machine

`onex local init` does all of it. It selects the local-home source in `~/.onex/config.yaml` (keeping everything else in that file), and writes the example document above to `~/.omninode/config/local/local/runtime.lane.json` at mode `0600`. Run it once:

```bash
onex local init
```

It prints the lane, the document's path and its sha256. Running it again changes nothing. If a different document is already at that path, or `~/.onex/config.yaml` already selects another source, it refuses and leaves both alone: it never overwrites your own declaration.

The laptop container profile (`make up-local` in the infrastructure repository) runs its runtimes with `ONEX_ENVIRONMENT=local` and `ONEX_RUNTIME_LANE=local`, and mounts those two local-home paths into them read-only. It refuses to start before `onex local init` has run.

### In your own containers

For each runtime container:

1. Set `ONEX_RUNTIME_LANE` to the lane's name, and `ONEX_ENVIRONMENT` to your environment's name.
2. Choose **one** source:
   - **store:** give the runtime the config store's address in its secrets-manager address variable, and write the lane's document to the store under key `runtime.lane` at your environment and lane; or
   - **local-home:** leave that address empty, and mount a `.onex/config.yaml` that says `config_source: local-home` and a `.omninode/config` directory holding `<environment>/<lane>/runtime.lane.json` into the home directory of the user the runtime runs as.

The runtime services in the catalog render refuse to render without a lane, and each renders with exactly one source.

---

## When the runtime refuses to start

The runtime resolves its lane before it discovers any contract. Each case below stops the process with a non-zero exit and a message naming what is missing. None of them lets the runtime run in a degraded state.

| Case | The message names |
|---|---|
| No overlay source is configured, or both are | both sources and what selects each |
| `ONEX_RUNTIME_LANE` is unset, blank, or not a lane name | the variable and the value it read |
| No `runtime.lane` document at your environment and lane | the lane and the exact path or store location looked at |
| The document fails validation | the field and the problem |
| The document's `lane_id` differs from `ONEX_RUNTIME_LANE` | both values |

On a healthy start the runtime logs one line with the lane, its roles, the source, the environment, the document's location and its sha256, so you can tell which document a running process read.

---

## Adding a lane

A new lane needs no code change and no new release: set `ONEX_RUNTIME_LANE` on the new deployment and supply its document. The same applies to changing what a lane is for: edit its `roles` and restart the runtime.
