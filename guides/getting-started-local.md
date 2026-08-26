---
type: guide
status: current
date: "2026-08-26"
title: "Getting Started Locally"
topics: [getting-started, local, runtime, event-bus, projection, sqlite]
refs: []
---

# Getting Started Locally

This is the shortest complete path to a running ONEX system: one package, one command, and a real event chain you can read back out of a database file. No broker, no database server, no container runtime, no cloud account, no API key.

It works because the platform's defaults are already local. The event bus defaults to an **in-process, in-memory** implementation, and the projection store defaults to **SQLite**. Neither is a mock and neither is a special "demo mode" — they are the transport and the store, selected by default, running the same command → handler → terminal-event → projection chain that a distributed deployment runs. Scaling up later means swapping those two adapters, not rewriting your nodes.

Read this guide first even if you intend to run the full stack. Everything in the scale-up path assumes you have already seen the loop below succeed.

---

## What this tier is, and is not

| | Local (this guide) | Full stack |
|---|---|---|
| Event transport | In-memory bus, in-process | Distributed broker |
| Projection store | SQLite (file or `:memory:`) | Server-hosted relational database |
| External services | none | broker, database, container runtime |
| Configuration | none required | connection settings per service |
| What it proves | contracts, handler chain, terminal events, projections, replay of a recorded run | all of that, plus partitioning, ordering across processes, durability, multi-consumer fan-out |

Local is a genuine ONEX runtime, not a simulator. What it does **not** exercise is anything that only exists once more than one process is involved: cross-process ordering, consumer groups, broker durability, and server-side database behaviour. Those are the subject of the full-stack guide.

---

## 1. Prerequisites

| Requirement | Detail |
|---|---|
| CPython | 3.12 or newer. The core package declares `requires-python = ">=3.12"`; this guide was executed end to end on both CPython 3.12 and 3.13. |
| An environment manager | `uv` is what the project uses. The standard library's `venv` plus `pip` works identically — both are shown below and both were executed. |
| A version-specific interpreter on `PATH` | Only for the standard-library install path, which invokes `python3.12` by name. If your `python3` is already 3.12 or newer, substitute it; `uv` does not need this, because it resolves and downloads the interpreter itself. |
| Disk | A few hundred megabytes for the virtual environment. |
| `sqlite3` command-line tool | **Optional.** Only for the manual read-back in step 5. Python's bundled `sqlite3` module does the actual storing, and that ships with CPython — you do not need to install SQLite. |

**Not required, and not used anywhere in this guide:** Docker or any container runtime, a Kafka-compatible broker, PostgreSQL or any database server, a cloud account, a model provider key, or any environment variable.

One caveat stated plainly: every command below was executed on macOS. Nothing in the path is platform-specific — it is CPython, one pure-Python dependency tree, and the bundled `sqlite3` module — but Linux and Windows were not exercised for this guide.

---

## 2. Install

One package. `omnibase_core` carries the runtime, the contracts, the in-memory bus, the SQLite projection store, and the `onex` command-line tool.

With `uv`:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python omnibase-core
```

Or with the standard library:

```bash
python3.12 -m venv .venv
./.venv/bin/pip install omnibase-core
```

The distribution name on the package index is `omnibase-core` (hyphen); the importable module is `omnibase_core` (underscore). Both installs were run from a clean, empty environment against the public package index — no source checkout, no private index, no git dependency.

Confirm the install:

```bash
./.venv/bin/onex --version
./.venv/bin/onex --verbose info
```

`onex --version` prints `onex version <version>`.

`onex --verbose info` prints the package version, the interpreter version, the interpreter path, the working directory, and the list of installed ONEX packages — useful later for proving *which* interpreter actually answered. Plain `onex info` prints only the first two of those; the interpreter path and the package list are the verbose-only lines, which is exactly the information you need when diagnosing an import failure.

Note the flag's position. `--verbose` is an option on the `onex` group, not on the `info` subcommand, so it goes **before** the subcommand. `onex info --verbose` fails with `Error: No such option '--verbose'`.

---

## 3. Configure

There is nothing to configure.

That is the whole step, and it is worth being explicit about rather than leaving as an absence: the local path reads **no environment variable and no configuration file**. The runtime harness, the in-memory bus, and the SQLite store take their settings from command-line arguments and constructor defaults only. If you are used to frameworks that need a `.env` before they will start, the correct action here is to skip ahead.

Two things you may encounter and should **not** do at this tier:

- `onex init --user-config` writes a user configuration file with credential placeholders. Those credentials address external services. They are for connected operation, not for this guide, and the loop below runs without that file existing.
- `onex doctor` and `onex health` are **full-stack and contributor diagnostics, not local health checks.** `onex health` probes broker reachability; `onex doctor` additionally probes a container runtime, a database, an issue-tracker API, and the state of local repository checkouts. Neither one tells you anything about the loop in this guide, in either direction — and both are worth understanding before you read a result off them.

  On a machine with none of that infrastructure, `onex health` fails its broker check and `onex doctor` reports most of its checks red. **That is the expected result and it does not mean your local runtime is broken.** Equally: if your machine happens to have a broker or database reachable for unrelated reasons, `onex health` can print `All health checks passed!` — and that green is not evidence about your tier-0 loop either, because nothing in this guide touched the services it probed. Both commands read the surrounding environment, so their output describes your machine, not the runtime you are about to start. The correct local health check is step 5.

---

## 4. First run

The runtime harness is the smallest real success loop the platform ships. It publishes a typed command onto the in-memory bus, pumps it through the registered orchestrator → effect → reducer handlers to a terminal event, materialises a projection row into SQLite, and prints a JSON evidence packet describing exactly what happened.

```bash
./.venv/bin/python -m omnibase_core.runtime.harness.harness_cli delegation \
  --prompt "hello onex" \
  --inference fixture \
  --fixture-completion "A recorded completion from a real model call." \
  --sqlite-path ./onex-local.db
```

### The arguments that matter

**The workflow** is the first positional word. Two ship: `delegation` and `sea`. Both run the identical three-handler chain; they differ in the topics they publish on. Either one proves the loop.

**`--inference`** selects how the effect step obtains a completion, and it has exactly two settings:

- `fixture` — replay a completion you recorded from a real model call. Requires `--fixture-completion`.
- `curl` — call a live, OpenAI-compatible chat-completions endpoint. Requires `--endpoint`. See step 6.

There is deliberately **no third option that echoes the prompt back**. A run with neither real nor recorded inference fails rather than reporting success on nothing. This is the fail-fast principle applied to your very first command: the framework would rather refuse than hand you a green result that proves nothing.

**`--sqlite-path`** defaults to `:memory:`, which is ephemeral — the projection is written and read within the process and then vanishes. Pass a file path, as above, when you want an artifact you can inspect afterwards. Step 5 assumes you did.

**`--prompt`**, **`--task-type`**, **`--max-tokens`**, and **`--correlation-id`** all have working defaults; `--max-tokens` defaults to `512`, and `--correlation-id` defaults to a freshly generated identifier.

Supplying your own correlation identifier is the way to tie a run to something outside the runtime — but **it must be a UUID.** The value is parsed as one, and a non-UUID string aborts the run with `ValueError: badly formed hexadecimal UUID string` before any handler executes. The identifier is not free-form text, and it does not fall back to a generated value when it cannot be parsed. Pass something like `11111111-2222-3333-4444-555555555555`, or a UUID your own system already uses as the correlation key.

Run `./.venv/bin/python -m omnibase_core.runtime.harness.harness_cli delegation --help` for the full argument list; the two positional workflows have their own help under `--help` on the top-level command.

---

## 5. Verify it worked

Four independent signals. Check them in order; each one rules out a different way a "successful" run could be lying to you.

### 5.1 The process exit code

```bash
echo $?
```

`0`. The harness returns the terminal status of the chain as its exit code, so a non-zero result means the chain itself failed, not that the command was malformed.

### 5.2 The evidence packet

The command prints a JSON packet to standard output. The fields that carry the proof are below.

This is an **excerpt**, and your real output will be longer: the packet opens with build-provenance fields (including a `runtime_sha`, which reads `unknown` for a package install rather than a source checkout) and the generated `correlation_id`, and it closes with a full `projection_row` object. Those are not omitted because they are unimportant — `projection_row` is the same row step 5.3 reads back out of the database — but because the five fields shown here are the ones that carry the argument. Extra keys you see are expected; missing keys from this list are not.

```json
{
  "workflow": "delegation",
  "bus_impl": "EventBusInmemory",
  "inference_adapter": "fixture",
  "projection_backend": "sqlite:./onex-local.db",
  "terminal_topic": "onex.evt.omnibase-core.harness-delegation-completed.v1",
  "terminal_status": "success",
  "emitted_topics": [
    "onex.cmd.omnibase-core.harness-delegation-request.v1",
    "onex.evt.omnibase-core.harness-delegation-infer.v1",
    "onex.evt.omnibase-core.harness-delegation-completed.v1"
  ],
  "infra_free": true,
  "exit_code": 0
}
```

Read it as five separate assertions:

- **`bus_impl`** names the in-memory bus. This is where you confirm that the default transport is what actually carried the message — you did not configure it, and you did not get a stub.
- **`projection_backend`** names SQLite and the exact database it wrote to.
- **`emitted_topics`** is the chain, in order: a command was published, an effect event followed it, and a terminal event closed it. Three entries means all three handlers ran. Fewer means the chain stopped early.
- **`terminal_status`** is `success` — the terminal event, not merely the process.
- **`infra_free`** asserts the run required no external infrastructure.

### 5.3 The projection row, read back independently

The evidence packet is written by the same process that ran the workflow. Reading the database with a separate tool is what makes it independent proof of durability:

```bash
sqlite3 ./onex-local.db \
  "SELECT correlation_id, workflow, status, terminal_topic FROM harness_projection;"
```

One row per correlation identifier, in table `harness_projection`, whose columns are `correlation_id`, `workflow`, `terminal_topic`, `status`, `payload`, and `created_at`. The write is an upsert keyed on `correlation_id`, so re-running with the same identifier updates the row rather than duplicating it — the projection is idempotent by construction, which is the property that makes replay safe.

### 5.4 The negative control

A verification step that cannot fail proves nothing. Run the same command with the recorded completion removed:

```bash
./.venv/bin/python -m omnibase_core.runtime.harness.harness_cli delegation --inference fixture
```

It **fails**, and exits `1`.

Be ready for the shape of that failure, because it is not a tidy one-line usage message: you get a Python traceback, ten or so frames deep, terminating in a typed validation error whose message states that `--fixture-completion` is required when `--inference=fixture`, and that a fixture run with no recorded completion is a false-green stub. The traceback is the expected output here — read the last line, not the first. It is the error being raised rather than swallowed, which is the entire point of the check.

If that command succeeds, something is wrong with your installation. A framework that refuses to fabricate a result is the behaviour you want; confirming it now means you can trust the green in 5.2.

---

## 6. Optional: point it at a local model

Still zero external infrastructure, provided the model server runs on your own machine. Start any server exposing an OpenAI-compatible chat-completions route, then:

```bash
./.venv/bin/python -m omnibase_core.runtime.harness.harness_cli delegation \
  --prompt "hello onex" \
  --inference curl \
  --endpoint http://127.0.0.1:<port>/v1/chat/completions \
  --model <model-name>
```

The adapter posts `{"model": ..., "max_tokens": ..., "messages": [{"role": "user", "content": ...}]}` and reads the completion from `choices[0].message.content`. Anything speaking that dialect works; substitute your server's port and model name. The evidence packet then reports `"inference_adapter": "curl"` and the completion in the projection payload is the model's, not a replay.

This is also how you produce the recorded completions that `--inference fixture` replays: run it live once, keep the completion, and every subsequent run of that scenario is deterministic and offline.

---

## 7. Author your own node

The harness runs workflows that ship with the platform. Writing your own starts with a scaffold, and needs nothing beyond what you already installed.

```bash
./.venv/bin/onex init my-onex-project
cd my-onex-project
../.venv/bin/onex new node my-first-node --type compute
```

`onex init` creates a project directory with a `pyproject.toml`, a `src/<package>/nodes/` tree, a `contracts/` directory and a `tests/` directory. `onex new node` then writes four files into it:

```
src/my_onex_project/nodes/my_first_node/
├── contract.yaml
├── node_my_first_node_compute.py
├── handlers/handler_my_first_node.py
└── models/models_my_first_node.py
```

`--type` accepts `compute`, `effect`, `reducer`, or `orchestrator` — the four node archetypes. The generated `contract.yaml` declares the node's name, archetype, contract and node versions, its typed input and output models, its handler routing, a descriptor block (purity, runtime profiles, idempotency, timeout), and the topics it subscribes to and publishes on. The generated handler raises `NotImplementedError` on purpose: the contract is complete, the behaviour is yours to write, and the node fails loudly until you do.

Read the contract file before you touch the handler. It is the specification the runtime resolves against, and the ordering — contract first, implementation second — is the working habit the rest of the platform assumes.

Two honest limits on this section. First, `onex validate` on a freshly scaffolded, still-unimplemented project reports failures; treat validation as something to run once your handler exists, not as a smoke test of the scaffold. Second, this guide verified that the scaffold is generated correctly and that its contract is well-formed — it did **not** verify running a hand-written node through the harness command above, because that harness wires two specific built-in workflows. Executing your own node is the subject of the handler-authoring and full-stack material below.

---

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: omnibase_core` | A different interpreter answered than the one you installed into. Run `onex --verbose info` — with the flag, and with the flag *before* `info` — and compare its reported `Python path` against your virtual environment. Plain `onex info` will not show you the path. An inherited `PYTHONPATH` can shadow the environment; clearing it for the command (`env -u PYTHONPATH ...`) resolves that case. |
| Traceback ending in a `--fixture-completion` validation error | Working as designed — see 5.4. Supply a recorded completion, or switch to `--inference curl`. |
| `ValueError: badly formed hexadecimal UUID string` | You passed a non-UUID value to `--correlation-id`. It must parse as a UUID — see step 4. |
| `Error: No such option '--verbose'` | The flag belongs to the `onex` group, not the subcommand. Write `onex --verbose info`, not `onex info --verbose`. |
| `onex doctor` / `onex health` report failures | Expected on a local-only machine. Both probe full-stack services and local checkouts. Neither is the local health check; step 5 is. A green result from either is not evidence about the local loop either — see step 3. |
| No row from the `sqlite3` query | You almost certainly ran with the default `:memory:` store, which leaves no file behind. Re-run with `--sqlite-path ./onex-local.db`. |
| `onex validate` fails on a new project | Expected on an unimplemented scaffold — see the note at the end of step 7. |

---

## 9. Where to go next

**Scale up to the full stack.** When you need cross-process ordering, broker durability, consumer groups, or a server-hosted projection database, [self-hosting the full stack](getting-started-self-hosted.md) covers standing those services up and repointing the same nodes at them. Nothing you wrote here is discarded — the bus and the store are adapters behind a protocol, and the swap is a configuration change, not a rewrite.

**Connect to hosted infrastructure.** If you would rather consume a managed deployment than operate one, [connecting to the cloud](connecting-to-the-cloud.md) covers that path.

**Understand what you just ran.** The behaviour above is not incidental; each part of it is a stated principle with a page of its own:

- [Contracts define reality](../doctrine/contracts-define-reality.md) — why the `contract.yaml` you scaffolded is the specification and not documentation.
- [State is a materialized projection](../doctrine/state-is-materialized-projection.md) — why the SQLite row is derived from the event chain rather than written directly.
- [Fail fast and loud](../doctrine/fail-fast-and-loud.md) — the principle behind the negative control in 5.4.
- [Deterministic under replay](../doctrine/deterministic-under-replay.md) — why recorded completions and idempotent upserts matter together.
- [ONEX runtime overview](../architecture/onex-runtime-overview.md) and [event bus integration](../architecture/event-bus-integration.md) — the runtime and transport in full.

**Write real handler logic.** The [handler authoring guide](handler-authoring-guide.md) picks up where step 7 stops.
