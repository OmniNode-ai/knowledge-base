---
type: guide
status: current
date: "2026-09-23"
title: "OmniClaude Quickstart"
topics: [omniclaude, plugin, quickstart, delegation]
refs: []
---

<!-- Migrated from omniclaude:QUICKSTART.md on 2026-09-01 -->

# OmniClaude Quickstart

This guide sets up **delegation** on your own computer: you hand a task to a model you choose,
and you get back the answer plus a receipt saying which model answered it. The model is either
one you run yourself or a provider account you pay for (or use for free) on your own key. The
call goes from your machine to that model directly, never through OmniNode.

It takes about 15 minutes. Every step below says what you should see when it worked.

There are two ways to use it, and both use the same `onex` command-line tool:

- **In a terminal**: `onex delegate "<your task>"`. Steps 1 to 5 set this up and prove it works.
- **Inside Claude Code**: the `onex@omninode-tools` plugin adds `/onex:delegate`, which runs the
  same command for you. Step 6 adds it. The plugin ships two skills (`/onex:delegate`, and
  `/onex:cloud_delegate` for the dashboard-key cloud path) and nothing else: no hooks, no agents.

---

## Before you start

| You need | How to get it |
|----------|---------------|
| A terminal | macOS: the **Terminal** app (Applications → Utilities). Linux: any shell. |
| Python 3.12+ and `uv` | macOS: install [Homebrew](https://brew.sh) if you don't have it (it also installs Apple's command line tools, which the steps below need), then run `brew install uv`. Other systems: see [uv's install page](https://docs.astral.sh/uv/getting-started/installation/). |
| A model to send work to | **Either** an account with a model provider and an API key from it (OpenRouter is the simplest: [openrouter.ai](https://openrouter.ai), and it has free models), **or** a model server you run yourself that speaks the OpenAI chat-completions API (llama.cpp, vLLM, or similar). |
| Claude Code (only for step 6) | The [Claude Code CLI](https://claude.com/claude-code), signed in. Steps 1 to 5 do not need it. |

You do not need to install Python yourself. The Python that ships with macOS is too old
(3.9), but that does not matter: `uv` uses a newer Python if you have one (Homebrew's, for
example) and downloads one for itself if you don't.

Check that `uv` is ready: `uv --version` prints a version number.

---

## Step 1 — Install the `onex` tool

```bash
uv tool install --with 'omnibase-infra>=0.38.4' --with 'omnimarket>=0.4.205' 'omnibase-core>=0.46.8'
```

This downloads about 175 packages and takes a minute or two. It ends with a line starting
`Installed 20 executables:` that includes `onex`.

**If the output ends with a warning that `~/.local/bin` is not on your PATH** (on a new
machine it usually does), run this once, then **close the terminal window and open a new one**:

```bash
uv tool update-shell
```

Check it worked, in the new window:

```bash
onex --version
```

It prints `onex version 0.47.x` (or newer). **The first `onex` command takes 10 to 20
seconds** while Python prepares itself; later ones start faster.

What was installed: `omnibase-core` provides the `onex` command, `omnibase-infra` adds its
`delegate` subcommand, and `omnimarket` provides the node that does the delegating. All three
must be in the same environment, which is what the one line above does. There is no source
checkout to clone and no workspace variable to set. The version floors are the oldest
releases this guide supports; the command installs the newest published release of each.

To update later: `uv tool upgrade omnibase-core` (it keeps the other two packages).

If you use `pipx` instead of `uv`, the equivalent is
`pipx install 'omnibase-core>=0.46.8' && pipx inject omnibase-core 'omnibase-infra>=0.38.4' 'omnimarket>=0.4.205'`.
Do not use `uv run onex ...`: `uv run` uses the environment of whatever project folder you are
in, so it only works by coincidence. Call the plain `onex` command.

---

## Step 2 — Give this machine its identity (once)

```bash
onex local init
```

You should see `local deployment tenant identity (minted)` and a `tenant_id`. Every
delegation from this machine is recorded against that identity, which is stored under
`~/.omninode/`. Running it again is safe: it prints `(already present)` and the same id.

---

## Step 3 — Tell `onex` which model to use

`onex` does not guess a model, and it has no endpoint of ours built in. Choose **one** of the
two options below. If you do not run a model server of your own, use option B; it needs only
an account with a provider.

<a id="declare-your-model"></a>

### Option A — a model server you run

Create the file `~/.omninode/delegation/bifrost_overrides.yaml` with exactly this shape,
pointing both entries at your server's chat-completions address. The address must be the
*complete* path, including `/v1/chat/completions`, not just the host:

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

Both entries can point at the same server and the same model; that is the common case.
`endpoint_url` and `model_name` are the only two keys you need: they override just those two
fields of OmniNode's own defaults for the two local rungs `onex delegate` tries first. If you
also register a provider key (option B), your own model is tried first and your provider is
used when the local answer does not clear the quality bar.

### Option B — your own provider key (OpenRouter or GLM)

OmniNode's built-in routing already knows how to reach OpenRouter and GLM; you only supply
your key, once, on this machine.

1. Sign in at [openrouter.ai](https://openrouter.ai), open **Settings → Keys**, create a key,
   and copy it. An OpenRouter key starts with `sk-or-v1-`.
2. Run this command. It reads the key from what you paste, never from the command line or an
   environment variable:

   ```bash
   read -rs KEY && printf '%s' "$KEY" | onex secret set llm.openrouter.api_key && unset KEY
   ```

   **The terminal shows no prompt and nothing appears when you paste. That is on purpose, so
   the key never shows on screen.** Paste the key once and press Return.

You should see `Stored llm.openrouter.api_key in ...` and
`Registered it as your openrouter route key: ...`. For GLM, use `llm.glm.api_key` in the same
command. `onex secret list` shows the names of the keys this machine holds, never the keys.

A provider key alone is enough: with no model server declared, `onex delegate` goes straight
to your provider on your key. With only an OpenRouter key, it uses a **free** OpenRouter model;
free models cost nothing but OpenRouter limits how often you can call them. The key is kept in
a file under `~/.omninode/` that only your user account can read. It is not encrypted, so treat
that folder like any other file holding a password.

Setting `LLM_<PROVIDER>_API_KEY` in your environment does **not** register a key; a
delegation never reads a provider key from the environment. Use `onex secret set`.

### If you skip this step

The first delegation refuses before it reaches any model, and says what to do:

```
[ONEX_CORE_041_INVALID_CONFIGURATION] No local model is declared on this machine: no local
rung (local-coder, local-heavy-reasoning) has an endpoint. Declare yours in
/home/you/.omninode/delegation/bifrost_overrides.yaml, e.g. 'backends: [{backend_id:
local-coder, endpoint_url: http://127.0.0.1:8000/v1/chat/completions, model_name: <served
model id>}]', or register your own provider key on this machine, then retry.
```

---

## Step 4 — Run your first delegation

Run it from a folder you will remember, because that is where the results are written (see
step 5). Your home folder is fine:

```bash
cd ~
onex delegate "say hello in one word"
```

It takes from a few seconds to a minute. You will see a few status lines, then one long line
of JSON, then a last line starting `delegate artifacts:` that lists three files. **It worked if
the JSON contains `"status":"success"`.** If it contains `"status":"failed"`, the
`error_message` in it says why; see [Troubleshooting](#troubleshooting).

---

## Step 5 — Find the answer and the receipt

Each run writes its own folder, `.onex_state/runs/<run id>/`, inside the folder you ran the
command from. The last line of step 4's output names the three files:

| File | What it holds |
|------|---------------|
| `result.txt` | The model's answer. |
| `receipt.json` | The proof of who answered: `backend_id` and `endpoint` name the provider or server, and `model` names the model. `status` is `success` or `failed`. |
| `run.json` | What you asked for: the prompt and the settings the run used. |

`.onex_state` is a hidden folder. If you ran step 4 from your home folder, `open ~/.onex_state/runs`
shows it in Finder on macOS (in Finder, Cmd+Shift+. shows hidden folders anywhere). To read the
newest answer in the terminal:

```bash
cat "$(ls -td ~/.onex_state/runs/*/ | head -1)result.txt"
```

---

## Step 6 — Use it inside Claude Code (optional)

Open a **new** terminal window first, so Claude Code can find the `onex` command from step 1.

```bash
# 1. Register the marketplace (one-time; reads directly from GitHub, no local clone needed)
claude plugin marketplace add OmniNode-ai/omniclaude

# 2. Install the plugin
claude plugin install onex@omninode-tools
```

Each command ends with a `✔ Successfully ...` line. Check with `claude plugin list`: it shows
`onex@omninode-tools` with status `enabled`. Then start Claude Code (`claude`), or restart it if
it was already open, and type:

```
/onex:delegate explain what a calendar app needs
```

Claude asks for permission to run the `onex delegate` command; allow it. It then shows the
answer and the model that produced it. The result files are written exactly as in step 5,
inside the folder Claude Code was started from.

---

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

The overlay file in step 3 (`~/.omninode/delegation/bifrost_overrides.yaml`) is the composable
mechanism: it adds or overrides backend entries on top of OmniNode's committed routing
contract, so the same `onex delegate` command reaches a self-hosted model (Tier 1) or, by
registering your own provider key with `onex secret set`, a cloud model you pay for directly
(Tier 2). See [step 3](#step-3--tell-onex-which-model-to-use) for both.

---

## Troubleshooting

| What you see | What it means and what to do |
|--------------|------------------------------|
| `command not found: brew` | Homebrew is not installed. Install it from [brew.sh](https://brew.sh), then open a new terminal window. |
| `command not found: uv` | Run `brew install uv` (macOS), then open a new terminal window. |
| `command not found: onex` | The install folder is not on your PATH yet. Run `uv tool update-shell`, close the terminal window and open a new one. If that does not fix it, re-run the step 1 install command. |
| The command in step 3 seems to hang | It is waiting for you to paste the key. Nothing shows while you paste; paste once and press Return. |
| `error_message` contains `credential_rejected` and `Missing Authentication header` or `User not found` | The provider refused the key. The text you pasted was not a whole, current key (an OpenRouter key starts with `sk-or-v1-`). Copy it again from the provider's Keys page and re-run the step 3 command; it replaces the stored key. |
| `error_message` mentions `429` or a rate limit | The provider is limiting how often you can call it (free models are limited). Wait a minute and try again, or add credit to your provider account. |
| `No local model is declared on this machine` | You have neither registered a provider key nor declared a model server. Do step 3. |
| `this install has never minted a tenant identity` | Run `onex local init` once (step 2). |
| `Error: No such command 'delegate'. Did you mean 'gate'?` | Only `omnibase-core` is installed. Re-run the step 1 install command exactly as written. |
| `Error: Unknown node 'node_delegate_skill_orchestrator'` | `omnimarket` is missing from the environment. Re-run the step 1 install command exactly as written. |
| `claude plugin install` can't find `onex@omninode-tools` | The marketplace is not registered. Re-run `claude plugin marketplace add OmniNode-ai/omniclaude`; `claude plugin marketplace list` should show `omninode-tools`. |
| A window asks to install "command line developer tools" | macOS needs Apple's developer tools for `git`, which step 6 uses. Click Install, wait for it to finish, and re-run the command. |

`onex delegate --help` answering is not proof that a delegation works: it answers before
anything is checked. Step 4 is the real test.

---

## Next Steps

- `CLAUDE.md` (omniclaude repo) — development/architecture reference for OmniNode's internal tooling (insider-oriented; assumes an OmniNode canonical-clone workspace)
- `plugins/onex-delegate/skills/delegate/SKILL.md` (omniclaude repo) — the delegate skill's full usage reference
- `plugins/onex-delegate/skills/cloud_delegate/SKILL.md` (omniclaude repo) — dashboard-key cloud delegation and receipt-file reference
- `plugins/onex-delegate/plugin-compat.yaml` (omniclaude repo) — the plugin's own `onex` version requirements
