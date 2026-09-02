> Migrated from omnimarket:src/omnimarket/adapters/codex/README.md on 2026-09-01 (OMN-16613)

# Codex Adapter - OmniMarket

## Overview

Codex adapters are thin `SKILL.md` shims packaged in a Codex plugin. Each
skill describes how Codex should invoke one OmniMarket node through the
runtime-owned Codex request adapter path. No business logic lives in the skill.

## How it works

1. Codex loads the skill metadata.
2. When the user requests the operation, Codex invokes the matching skill.
3. The skill dispatches to `scripts/run_codex_runtime_request.py`
4. The request may include `--target-runtime-address runtime://...` or
   `ONEX_TARGET_RUNTIME_ADDRESS` when the caller needs a specific runtime
5. The runtime owns execution and returns a typed JSON response
6. Codex renders `output_payloads[0]` when present, or falls back to
   `dispatch_result` without reimplementing workflow logic

## File conventions

| File | Purpose |
|------|---------|
| `template.md` | Generic Codex `SKILL.md` template |
| `skills/<skill-slug>/SKILL.md` | Generated Codex skill shim |
| `runtime_client.py` | Stdlib-friendly Codex runtime request adapter |
| `../../../../scripts/run_codex_runtime_request.py` | Repo-local request wrapper that bootstraps `src/` import resolution |
| `../../../../plugins/onex/.codex-plugin/plugin.json` | Repo-local Codex plugin manifest |

The repo-local plugin mirrors the Claude Code `onex` plugin surface while using
Codex-native plugin and skill metadata.

## Current install path

The repo now ships a real Git marketplace source:

- marketplace root: `.agents/plugins/marketplace.json`
- plugin manifest: `plugins/onex/.codex-plugin/plugin.json`

`codex plugin marketplace add OmniNode-ai/omnimarket --ref <branch>` now
clones and validates the marketplace correctly.

On this machine, `codex exec` still reliably loads ONEX skills only from
`~/.codex/skills`. The Git marketplace sync path does not yet surface ONEX
skills in `codex exec` or `codex debug prompt-input`, even though the cloned
plugin metadata is valid and the synced tree contains the expected `SKILL.md`
files.

The current working bridge path is therefore:

1. `codex plugin marketplace add ...` to sync the Git marketplace source
2. symlink the synced `plugins/onex/skills/*` entries into `$CODEX_HOME/skills`

In isolated `CODEX_HOME` testing, the ONEX skills appeared in
`codex debug prompt-input` immediately after those symlinks were created.

Install the current ONEX skills with:

```bash
uv run python scripts/install_codex_skills.py --source auto --force
```

This creates symlinks into `~/.codex/skills/`, preferring the synced Git
marketplace tree when it is present and falling back to the repo-local
`plugins/onex/skills/*` tree otherwise.

To force the marketplace-backed bridge explicitly after `codex plugin
marketplace add ...`:

```bash
uv run python scripts/install_codex_skills.py --source marketplace --force
```

## Shim responsibilities

1. **Argument collection and validation** - Parse user-provided arguments and map
   them to fields from `contract.yaml`.
2. **Command options mapping** - Translate arguments into the structured JSON
   payload expected by the node.
3. **Adapter dispatch** - Run the backing node through the runtime-owned
   Codex request adapter path instead of direct CLI execution or a second dispatch
   implementation in the skill layer.
4. **Runtime targeting** - Preserve an optional `runtime://...` address on the
   adapter command so the runtime layer can route work to a concrete runtime
   without treating a lane such as stability-test as a special flag.
5. **Response handling** - Prefer `output_payloads[0]` for the business result
   and fall back to `dispatch_result` when the handler did not emit a typed
   output payload.
6. **Output formatting** - Transform the runtime response into a clear reply
   for the user.
7. **Timeout and error handling** - Use the node's `descriptor.timeout_ms` as
   the timeout budget and surface structured runtime adapter errors directly.

## Creating new skills

1. Generate a skill with `scripts/generate_adapter.py --formats codex`
2. Replace all `{{PLACEHOLDER}}` values using the node's `contract.yaml`
3. Copy generated `skills/<skill-slug>/SKILL.md` into `plugins/onex/skills/`
4. Keep the skill as a thin shim; move behavior changes into the backing node
