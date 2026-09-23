---
type: guide
status: current
date: "2026-09-22"
title: "OmniClaude Quickstart"
topics: [omniclaude, plugin, quickstart, delegation]
refs: []
---

<!-- Migrated from omniclaude:QUICKSTART.md on 2026-09-01 -->

# OmniClaude Quickstart

OmniClaude ships as a single Claude Code plugin, **`onex@omninode-tools`**. It exposes two
customer delegation siblings: `/onex:delegate` for customer-local work and
`/onex:cloud_delegate` for the dashboard-key gateway path. It has no hooks and no agents. It does **not**
inject a SessionStart capability banner or auto-load 100+ skills — that described an older,
larger plugin (`plugins/onex`, now `NO_AUTOLOAD`/dead source) that this file used to document.
If you're looking for that plugin's hooks/agents/routing architecture, see
the omniclaude repo's `CLAUDE.md` — it is internal OmniNode tooling, not part of the public plugin below.

---

## Install (5 min)

Requires the [Claude Code CLI](https://claude.com/claude-code) and Python 3.12+.

```bash
# 1. Register the marketplace (one-time; reads directly from GitHub, no local clone needed)
claude plugin marketplace add OmniNode-ai/omniclaude

# 2. Install the plugin
claude plugin install onex@omninode-tools

# 3. Restart your Claude Code session to load the skill
```

Verify: `claude plugin list` shows `onex@omninode-tools` with status `enabled`.

---

## Configure — install the `onex` CLI and dashboard key

Both skills shell out to the `onex` CLI. The CLI is **not** bundled with the
plugin and must be installed separately into an environment on `PATH`:

```bash
uv tool install --with 'omnibase-infra>=0.38.4' --with 'omnimarket>=0.4.203' 'omnibase-core>=0.46.8'
# or:
pipx install 'omnibase-core>=0.46.8' && pipx inject omnibase-core 'omnibase-infra>=0.38.4' 'omnimarket>=0.4.203'
```

`omnibase-core` provides the `onex` console script; `omnibase-infra` provides the `delegate`
subcommand; `omnimarket` provides `node_delegate_skill_orchestrator`, the node the command
actually dispatches to — all three are required in the same environment. Node
lookup resolves via `onex.nodes` entry points over installed distributions, so installing the
package is sufficient — there is **no** source checkout to clone and no workspace variable to
export, despite what an earlier revision of this file said.

The `omnimarket>=0.4.203` floor is not cosmetic: below it, a clean install's very first
`onex delegate` refused at startup, before your prompt was even read, because an internal
routing-config path had nothing packaged to fall back to. At or above it, that path resolves
to the packaged default with no configuration from you — the only thing left to set up is
which model you want to use, which is [Declare your model](#declare-your-model) below.

Pins above are the current values from
`plugins/onex-delegate/plugin-compat.yaml` in the omniclaude repo, the
source of truth — check that file if these look stale.

Package presence checks: `onex delegate --help` and `onex cloud delegate --help` exit 0 from
any directory. **These are not proof a live run works** — they establish only that both customer
command paths are registered in the installed CLI.

**`--help` exiting 0 does not mean the command works.** Click answers `--help` before any
dispatch happens, so `--help` succeeds even with `omnimarket` missing entirely. The first real
failure only shows up on an actual invocation — see Troubleshooting below for what those look
like. The real verification step is running a real delegation —
`onex delegate "say hello in one word"` — not `--help`.

**Do not run `uv run onex delegate`.** `uv run` resolves the venv of whatever project the
current directory belongs to, so it only works by coincidence inside a repo that happens to
co-install `omnibase-infra`. Install the CLI as a tool (above) and call the bare `onex` on
`PATH`.

---

## Run — local (start here)

Local is the first-class path, not a fallback. It needs no account, no dashboard key, and no
network service of ours — only a model you can reach, running on your own machine or your own
network.

```
/onex:delegate explain what a calendar app needs
```

which runs `onex delegate "<prompt>"` under the hood. With zero Kafka/Postgres configuration,
delegation runs the orchestrator in-process against an in-memory event bus, with SQLite as the
evidence fallback.

### One-time setup: mint this install's identity

Before the first delegation, run once:

```bash
onex local init
```

This mints a local tenant identity for this machine (stored under `~/.omninode/`) and every
subsequent `onex delegate` run is attributed to it. It is safe to run more than once — a repeat
call reports the identity it already minted rather than making a new one.

### Declare your model

`onex delegate` does not guess which model to use, and it ships with no endpoint of ours wired
in for you to reach by default — you tell it. That declaration is exactly one file, and it is
never a required environment variable:

```
~/.omninode/delegation/bifrost_overrides.yaml
```

If the file is missing or declares no local model, and you have registered no provider key
(see the provider example below), the very first delegation refuses before it reaches any model — with a message naming the file and giving you a working line to start from:

```
[ONEX_CORE_041_INVALID_CONFIGURATION] No local model is declared on this machine: no local
rung (local-coder, local-heavy-reasoning) has an endpoint. Declare yours in
/home/you/.omninode/delegation/bifrost_overrides.yaml, e.g. 'backends: [{backend_id:
local-coder, endpoint_url: http://127.0.0.1:8000/v1/chat/completions, model_name: <served
model id>}]', then retry.
```

**Minimal example — a local OpenAI-compatible server (llama.cpp, vLLM, or similar) on your own
machine.** Create the file with exactly this shape, naming the two local rungs `onex delegate`
tries first (`local-coder` and `local-heavy-reasoning`) and pointing both at your server's
chat-completions route — the URL must be the *complete* path, including `/v1/chat/completions`,
not just the host:

```yaml
# ~/.omninode/delegation/bifrost_overrides.yaml
backends:
  - backend_id: local-coder
    endpoint_url: "http://127.0.0.1:8000/v1/chat/completions"
    model_name: "<the model id your server reports, e.g. from GET /v1/models>"
  - backend_id: local-heavy-reasoning
    endpoint_url: "http://127.0.0.1:8000/v1/chat/completions"
    model_name: "<the model id your server reports, e.g. from GET /v1/models>"
```

Both entries can point at the same server and the same model — that is the common case for a
single-machine setup. `endpoint_url` and `model_name` are the only two keys you need here:
they override just those two fields on OmniNode's own committed defaults for `local-coder` and
`local-heavy-reasoning`, which is why the file can be this short.

**Provider example — bring your own key, with or without a local model.** OmniNode's shipped
routing already declares cloud rungs for the providers you can bring a key for (GLM and
OpenRouter today); you do not add them to the overlay file yourself. What you supply is your own
key, registered once on this machine with `onex secret set`, which reads the key from stdin and
never from an argument or an environment variable (this needs omnimarket 0.4.205 or later;
upgrade with `pipx inject --force omnibase-core 'omnimarket>=0.4.205'`):

```bash
read -rs KEY && printf '%s' "$KEY" | onex secret set llm.glm.api_key
# or, for OpenRouter:
read -rs KEY && printf '%s' "$KEY" | onex secret set llm.openrouter.api_key
```

The key is stored in this machine's local store (`onex secret list` shows the references it holds,
never the values). A provider key alone is enough to delegate: with no local model declared,
`onex delegate` goes straight to your provider on your key, and the run's `receipt.json` names the
provider's backend and model. If you also declare a local model, it is tried first and your
provider key is used when the local answer does not clear the quality bar. Either way the call is
made from your machine to your provider, on your account, never through OmniNode.

Setting `LLM_<PROVIDER>_API_KEY` in your environment does **not** register a key — a delegation
never reads a provider key from the environment. Use `onex secret set`.

Once the file is in place, delegate for real:

```
/onex:delegate explain what a calendar app needs
```

## Run — cloud, for a dashboard-only customer

Create an `onxk_` key in the dashboard, then give it to the CLI through stdin — never put the
key in a Claude prompt, command argument, or environment variable:

```bash
read -rs ONXK && printf '%s' "$ONXK" | \
  onex cloud login --base-url https://dev.api.omninode.ai --api-key-stdin
```

Inside Claude Code, run:

```
/onex:cloud_delegate --task-type summarization summarize this changelog
```

The CLI, not the plugin, submits over HTTPS. It prints the result and writes
`result.txt`, `receipt.json`, and `run.json` under `onex-delegations/<workflow_id>/` by default.
Keep and report those paths; they are the run evidence. A missing or rejected dashboard key is a
typed refusal, never a fallback to a direct provider call or to Claude answering the task.

---

## Tier 1 (self-hosted) / Tier 2 (cloud)

The overlay file documented above (`~/.omninode/delegation/bifrost_overrides.yaml`) is exactly
this composable mechanism: it adds or overrides backend entries on top of OmniNode's committed
routing contract, so the same `onex delegate` command reaches a self-hosted model (Tier 1) or,
by registering your own provider key with `onex secret set`, a cloud model you pay for
directly (Tier 2) — see [Declare your model](#declare-your-model) above for both. (This section
previously described a different, older full-ONEX Docker Compose stack — Redpanda +
omnimemory + omniintelligence — bundled with the `plugins/onex` hooks plugin above. That stack
is unrelated to the plugin this file now describes; the old instructions were removed rather
than left stale.)

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| `onex: command not found` | The `uv tool install`/`pipx` step above hasn't run, or its install bin dir isn't on `PATH`. |
| `Error: No such command 'delegate'. Did you mean 'gate'?` | Only `omnibase-core` is installed — `omnibase-infra` provides the `delegate` subcommand; both must be in the same environment (see Configure above). |
| `Error: Unknown node 'node_delegate_skill_orchestrator'` | `omnimarket` is not installed in the same environment as `omnibase-core`; re-run the install command above. |
| `this install has never minted a tenant identity` | Run `onex local init` once, before your first delegation — see "Run — local" above. |
| `No local model is declared on this machine` | You have declared no local model and registered no provider key. Either write `~/.omninode/delegation/bifrost_overrides.yaml` with an endpoint on `local-coder`/`local-heavy-reasoning`, or register your own provider key with `onex secret set llm.<provider>.api_key` (omnimarket 0.4.205 or later). The refusal names the exact file path and a working example line — see [Declare your model](#declare-your-model) above. |
| `claude plugin install` can't find `onex@omninode-tools` | Marketplace not registered — re-run the `marketplace add` step above; `claude plugin marketplace list` should show `omninode-tools`. |

---

## Next Steps

- `CLAUDE.md` (omniclaude repo) — development/architecture reference for OmniNode's internal tooling (insider-oriented; assumes an OmniNode canonical-clone workspace)
- `plugins/onex-delegate/skills/delegate/SKILL.md` (omniclaude repo) — the delegate skill's full usage reference
- `plugins/onex-delegate/skills/cloud_delegate/SKILL.md` (omniclaude repo) — dashboard-key cloud delegation and receipt-file reference
- `plugins/onex-delegate/plugin-compat.yaml` (omniclaude repo) — source of truth for the `onex` CLI version pins above
