---
type: guide
status: current
date: "2026-08-26"
title: "Combining Deployment Tiers"
topics:
  - getting-started
  - local
  - self-hosting
  - cloud
  - event-bus
  - runtime
  - configuration
refs:
  - guides/getting-started-local.md
  - guides/getting-started-self-hosted.md
  - guides/connecting-to-the-cloud.md
---

# Combining Deployment Tiers

The three preceding guides each describe one way to run ONEX. Almost nobody runs
exactly one.

The realistic shape is a **combination**: you author and test on tier-0 because the
loop is fast and needs nothing, you keep a self-hosted stack up because that is
where cross-process behaviour is actually provable, and you may also talk to a
hosted deployment as a client. This chapter is about the seams between those tiers
— which knob moves you across one, what changes when you cross it, and what
stays exactly the same.

It **composes** the three guides and does not restate them. Read them first:

- [Getting started locally](getting-started-local.md) — tier-0: the in-process bus, the local file-backed store, zero external infrastructure.
- [Self-hosting the full stack](getting-started-self-hosted.md) — the broker, the database, the cache, the identity provider, the runtime services.
- [Connecting to the cloud](connecting-to-the-cloud.md) — the hosted deployment as a client.

Everything below assumes you have seen the tier-0 loop in guide 1 succeed. That is
the baseline every claim on this page is measured against.

---

## The one thing that makes combining tiers possible

Before the patterns, the property they all rest on.

The event bus is chosen at **runtime construction**, from one small set of
values, behind a protocol. `omnibase_core.runtime.runtime_local` declares the
whole accepted set in one place:

```python
SUPPORTED_EVENT_BUS_VALUES: frozenset[str] = frozenset({"inmemory", "kafka"})
```

— `omnibase_core/src/omnibase_core/runtime/runtime_local.py:111`

`RuntimeLocal._create_event_bus()`
(`omnibase_core/src/omnibase_core/runtime/runtime_local.py:1539`) reads
`backend_overrides["event_bus"]`, defaults it to `"inmemory"`, and returns either
`EventBusInmemory(environment="local", group="runtime-local")` or — for `"kafka"` —
a bus class discovered through an entry-point group. Your nodes, contracts and
models are on the other side of that call and never see which one won.

That is the whole basis for a hybrid setup: **moving between tiers is a change to
one construction argument, not a change to your code.**

### Why the Kafka bus is an entry point and not an import

`omnibase_core` cannot import `omnibase_infra` — the dependency layering runs
compat → core → spi → infra, and core importing infra would invert it. So core
resolves the Kafka bus by name at runtime instead:

```python
_BACKEND_ENTRY_POINT_GROUP: str = "onex.backends"
_KAFKA_EVENT_BUS_ENTRY_POINT: str = "event_bus_kafka"
```

— `omnibase_core/src/omnibase_core/runtime/runtime_local.py:102`

and `omnibase_infra` supplies it from its own `pyproject.toml`:

```toml
[project.entry-points."onex.backends"]
event_bus_kafka = "omnibase_infra.event_bus.event_bus_kafka:EventBusKafka"
state_postgres = "omnibase_infra.backends.backend_probe:probe_postgres"
```

— `omnibase_infra/pyproject.toml:174`

The practical consequence is the first rule of a hybrid setup: **asking for the
Kafka bus in an environment where `omnibase-infra` is not installed is an error,
not a downgrade.** Verified in a clean `omnibase-core`-only virtual environment:

```
[ONEX_CORE_044_CONFIGURATION_ERROR] Requested event_bus=kafka but no entry point
named 'event_bus_kafka' is registered under 'onex.backends'. Install
omnibase-infra to provide EventBusKafka.
```

A typo is refused on the same terms, rather than silently falling back to
in-memory — also verified:

```
[ONEX_CORE_044_CONFIGURATION_ERROR] Unsupported backend override
event_bus='kafak'. Supported values: inmemory, kafka.
```

Silent fallback would be the worst possible behaviour here: you would believe you
were proving cross-process behaviour while running everything in one process.

### The CLI grows when you install the second package

The `onex` command comes from `omnibase_core`
(`omnibase_core/pyproject.toml:68`). It also loads any `click` group registered
under the `onex.cli` entry-point group
(`omnibase_core/src/omnibase_core/cli/cli_commands.py:733`), and `omnibase_infra`
registers seven (`omnibase_infra/pyproject.toml:165`).

Verified by installing the two packages in order into one clean environment and
diffing `onex --help`. With `omnibase-core` alone, none of the following exist.
After `uv pip install omnibase-infra`, all seven appear, on the same binary:

| Command | Entry point |
|---|---|
| `auth` | `omnibase_infra.cli.cli_auth:auth_group` |
| `delegate` | `omnibase_infra.cli.cli_delegate:delegate_command` |
| `kafka` | `omnibase_infra.cli.cli_kafka:kafka` |
| `node` | `omnibase_infra.cli.cli_node:run_node_by_name` |
| `occ` | `omnibase_infra.cli.cli_occ:occ` |
| `run` | `omnibase_infra.cli.cli_node:run_node_by_name` |
| `skill` | `omnibase_infra.cli.cli_skill:run_skill_by_name` |

This is the shape of the combination at the tooling level: **one binary, two
packages, and the tier-crossing commands only exist once the infra package is
present.** Note that `node` and `run` are two names for the same command.

---

## Pattern A — tier-0 dev loop, self-hosted stack for integration proof

The most common combination. You iterate on tier-0 all day because it starts
instantly and proves the contract chain; you cross to your self-hosted broker only
to prove the things tier-0 structurally cannot.

### When to flip

Guide 2 already lists the reasons to stand a full stack up at all. The narrower
question here — *when does an individual run need to cross?* — has a short answer:
flip when the property you are trying to prove **only exists between processes.**

| Prove this | Tier |
|---|---|
| The contract resolves, the handler chain runs, a terminal event closes it, the projection materialises | tier-0 |
| Replay determinism from a recorded completion | tier-0 |
| A validation or refusal fires | tier-0 |
| A second process sees the event | self-hosted |
| Consumer groups, partitioning, ordering across processes | self-hosted |
| Durability across a restart | self-hosted |
| A deployed runtime consumer picks the command up and dispatches it | self-hosted |

Anything in the top half that you run on the broker is a slower version of a test
you already had.

### How the flip is actually expressed

There are **three** mechanisms, they are not equivalent, and the differences
between them are the main source of confusion in a hybrid setup.

**1. The explicit `--backend` flag** (`onex node` / `onex run`):

```bash
onex node <node-name> --backend event_bus=inmemory
onex node <node-name> --backend event_bus=kafka
onex node <node-name> --backend event_bus=kafka --backend kafka_bootstrap=<host:port>
```

The flag is declared at `omnibase_infra/src/omnibase_infra/cli/cli_node.py:147`
and parsed by `parse_backend_overrides`
(`omnibase_core/src/omnibase_core/runtime/runtime_local.py:169`). Verified: it
accepts `key=value` pairs and refuses anything else —

```
[ONEX_CORE_007_INVALID_INPUT] Invalid --backend format 'event_bus'.
Expected key=value (e.g. --backend event_bus=inmemory).
```

Omitting `kafka_bootstrap` lets the Kafka bus resolve its broker from
`KAFKA_BOOTSTRAP_SERVERS`.

**2. The explicit `--bus` flag** (`onex delegate`), declared at
`omnibase_infra/src/omnibase_infra/cli/cli_delegate.py:453`, with the accepted
values and the guardrail in `build_backend_overrides`
(`omnibase_infra/src/omnibase_infra/cli/cli_delegate.py:240`). Verified behaviour:

```
BUS_CHOICES: ('inmemory', 'kafka')   DEFAULT_BUS: inmemory
--bus kafka --kafka-bootstrap <host:port>  ->  {'event_bus': 'kafka', 'kafka_bootstrap': '<host:port>'}
--bus inmemory                            ->  {'event_bus': 'inmemory'}
--bus inmemory --kafka-bootstrap <host:port>  ->  REJECTED:
    "--kafka-bootstrap is only valid with --bus kafka (got --bus inmemory)."
```

That last refusal is worth noticing. Passing a broker address alongside the
in-memory bus is exactly the mistake that would otherwise leave you running
in-process while believing you were on the broker, so it fails loudly instead.

**3. Auto-resolution, when you pass no flag at all.** This is the one that will
surprise you, and it is the reason this section exists.

### The ambient-environment hazard

Omit `--bus` on `onex delegate` and the bus is **probed for, not defaulted**.
`resolve_default_bus` (`omnibase_infra/src/omnibase_infra/cli/cli_delegate.py:194`)
calls the shared resolver `resolve_bus_type`
(`omnibase_infra/src/omnibase_infra/backends/auto_configure.py:116`), whose last
tier is `probe_kafka` — which reads `KAFKA_BOOTSTRAP_SERVERS` from the
environment when no bootstrap is passed
(`omnibase_infra/src/omnibase_infra/backends/backend_probe.py:131`).

That probe has **three** outcomes, not two, and only two of them resolve a bus at
all:

| Environment | Probe state | Resolved bus |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` unset | `DISCOVERED` — short-circuits with no network call | `inmemory` |
| Set; broker healthy, a live consumer group bound to the delegation request topic | `AUTHORITATIVE` | `kafka` |
| Set, but the broker answers weakly — TCP connects and the metadata call times out or the topic list fails | `REACHABLE` | **none — the command refuses** |

The first two, verified on one machine changing nothing but the environment:

```
# KAFKA_BOOTSTRAP_SERVERS unset
resolved bus -> inmemory
reason      -> DISCOVERED: KAFKA_BOOTSTRAP_SERVERS not set

# KAFKA_BOOTSTRAP_SERVERS set, broker up, a live consumer group bound
resolved bus -> kafka
reason      -> Kafka healthy with <N> topics; a Stable consumer group is bound to
               'onex.cmd.omnibase-infra.delegation-request.v1'
```

`<N>` stands in for the broker's topic count, which the real `reason` string
carries as a number. It is the only value elided from that output.

Read that carefully, because it is the first hazard of a hybrid workstation:
**the same command, in the same directory, on the same machine, ran on two
different transports — and the only difference was an environment variable.**

On a machine that is *only* tier-0 this never bites; the variable is not set and
auto-resolution always lands on in-memory. It bites precisely on the machine this
chapter is written for — the one where you also run a self-hosted stack, and
therefore have `KAFKA_BOOTSTRAP_SERVERS` exported in your shell profile or
sourced from an env file.

### The third outcome: an indeterminate probe refuses instead of guessing

The `REACHABLE` row is the one that turns a surprise into a real hazard, because
reaching it does not require you to change anything at all.

`probe_kafka` is a live network call with a timeout. Against a genuinely healthy
broker it can still time out on the metadata request, and that timeout is not an
answer — it means TCP connected but the broker's serving state was never
established. Measured here by probing one healthy broker twenty times in a row
with the environment unchanged, the probe itself did not agree with itself:

```
counts: {'kafka': 14, 'inmemory': 6}
  kafka:    Kafka healthy with <N> topics; a Stable consumer group is bound to
            'onex.cmd.omnibase-infra.delegation-request.v1'
  inmemory: REACHABLE: TCP reachable but topic list failed:
            KafkaError{code=_TIMED_OUT,val=-185,str="Failed to get metadata: Local: Timed out"}
```

Fourteen of twenty calls resolved the broker; six timed out. Nothing about the
environment differed between them, and the exact ratio is a property of one
broker on one network — treat it as evidence that the probe's outcome varies, not
as a rate you can plan around.

Because that variation is real, the resolver does not translate it into a
transport. A `REACHABLE` probe is **indeterminate**, and `resolve_bus_type`
refuses rather than picking a bus from an unknown state:

```
Error: Kafka probe returned REACHABLE (TCP reachable but topic list failed: ...);
the broker accepted a TCP connection but its serving state could not be
established, so the transport cannot be resolved repeatably. Select one
explicitly: pass the bus argument (e.g. '--bus kafka' / '--bus inmemory') or set
ONEX_EVENT_BUS_TYPE=kafka|inmemory.
```

This is the deliberate trade. Degrading a timeout to the in-process bus would
keep the command running, and for a one-off interactive call that is defensible —
but it means a delegation you believed landed on the broker may have run entirely
in-process, with no trace but a `reason` string you never looked at. Refusing
costs you a re-run and one decision; guessing costs you a result you cannot
trust. Only the two conclusive outcomes still resolve on their own: a broker that
answered, and a broker that is definitively not there.

The auto-resolution default is deliberate too: the flag's own help text says
omitting it resolves to "the SAME bus the rest of the system is configured with,
so the delegation lands in the shared delegation_events projection". That is the
right default for operating a stack. It is the wrong default for a quick
iteration you believed was local.

### The fix

Both paths — the delegate CLI and the service-side selector — resolve through one
authority, in one order:

1. **An explicit bus** — `--bus inmemory`, `--backend event_bus=inmemory`, or the
   in-process `bus_type=` argument. Never second-guessed, and never probed for.
2. **`ONEX_EVENT_BUS_TYPE`** — `inmemory`, `kafka`, or `cloud`, case-insensitive.
   Read once, in `auto_configure.py:192`, and honoured by both paths. An
   unrecognised value is an error, not a shrug.
3. **The probe**, with the three outcomes above.

**In a script, or anywhere the answer must be repeatable, use tier 1 or tier 2.**
Both remove the ambient-environment hazard and the timing hazard together, since
neither reaches `probe_kafka` at all. Tier 1 is the right choice for a single
command; tier 2 is the right choice for a whole shell session or a container,
where you want every ONEX process on that machine pinned to the same transport.

### Crossing back: what your self-hosted stack must already be

One asymmetry to plan around. Tier-0 needs nothing. The moment a run crosses to
the broker it inherits **every** precondition in guide 2 — most sharply the
migration gate, which the runtime will not start without, and the broker's
advertised address, which is what makes an off-box client fail on the second hop
rather than the first. Neither is visible from the tier-0 side of the flip, and
both will present as "my run hangs" rather than as a configuration error.

The practical sequencing is therefore: bring the stack up and verify it *on its
own terms* using guide 2's step 5, and only then start flipping individual runs
onto it. Debugging a flipped run against a stack you have not independently
verified means debugging two things at once.

---

## Pattern B — self-hosted stack, hosted API as a client

Here the hosted deployment is not a replacement for your stack. It is another
service your stack talks to, the same way it talks to any external API.

### The documented connection surface

The platform's own REST connection configuration is
`ModelRestApiConnectionConfig`
(`omnibase_core/src/omnibase_core/models/configuration/model_rest_api_connection_config.py:18`).
Its `apply_environment_overrides()` method
(same file, line 391) declares the exact variable-to-field mapping:

| Variable | Field |
|---|---|
| `ONEX_API_BASE_URL` | `base_url` |
| `ONEX_API_KEY` | `api_key` |
| `ONEX_API_BEARER_TOKEN` | `bearer_token` |
| `ONEX_API_TIMEOUT_SECONDS` | `timeout_seconds` |
| `ONEX_API_MAX_RETRIES` | `max_retries` |

Those are the five names guide 3 lists, and this is the code that gives them
meaning. Three details that guide 3 does not cover, and that matter as soon as
you are wiring this into your own stack rather than typing `curl`:

- **The overrides are applied, not absorbed.** `apply_environment_overrides()` is
  an explicit method call returning a **new** config object. Nothing reads these
  variables at import time or at construction. Exporting `ONEX_API_KEY` and
  constructing the model does not pick the key up; the calling code has to invoke
  the method. If you are embedding this, call it.
- **`base_url` is required on the model.** It is declared `default=...` (same
  file, line 35) — Pydantic's marker for a required field, so there is no
  in-model fallback to a public address. Nor is there one elsewhere in either
  package: `https://api.omninode.ai` appears exactly once across
  `omnibase_core/src` and `omnibase_infra/src`, as example text in the help for
  `onex auth --base-url`
  (`omnibase_infra/src/omnibase_infra/cli/cli_auth.py:103`), and that option is
  itself `required=True`. Nothing in these two packages reads
  `ONEX_API_BASE_URL` other than the mapping above. Whatever supplies the
  default base URL guide 3 describes, it is not `omnibase-core` or
  `omnibase-infra` — so if you are embedding this model, construct it with an
  explicit base URL rather than expecting one.
- **`timeout_seconds` and `max_retries` are parsed as integers, and a value that
  does not parse is skipped rather than raising** (same file, line 408). A typo in
  `ONEX_API_TIMEOUT_SECONDS` leaves the previous timeout in force silently. This
  is the one place in this chapter where a bad input is absorbed instead of
  refused, so check the value you set.

The credential shapes themselves — `X-API-Key` versus `Authorization: Bearer` —
are selected at `get_request_headers()` (same file, line 223), matching the two
header shapes guide 3 documents.

### The credential command guide 3 does not mention

`omnibase_infra` ships an `onex auth` group
(`omnibase_infra/src/omnibase_infra/cli/cli_auth.py`) with four commands —
`login`, `status`, `token`, `logout` — that store a gateway credential under
`~/.onex` and mint tokens from it. It appears on the `onex` binary once
`omnibase-infra` is installed, per the entry-point table above.

Two properties worth stating because they change how you script around it:

- **The secret is read from stdin only.** There is deliberately no
  `--client-secret <value>` option; the module's own docstring gives the reason —
  an argv flag puts the credential in the process table, in shell history, and in
  any exec log. `--client-secret-stdin` is a required flag.
- **`login`, `status` and `logout` perform no network I/O at all** — they are file
  operations over `~/.onex`. Only `token` reaches the network. So you can stage a
  credential on a machine that cannot currently reach the gateway.

`login` requires `--tenant-slug`, `--client-id`, `--token-endpoint` and
`--base-url` (`omnibase_infra/src/omnibase_infra/cli/cli_auth.py:88`); none are
defaulted.

> **Unverified.** This chapter did not execute `onex auth login`, `status`,
> `token` or `logout` against a live gateway — doing so requires a tenant
> credential, which is waitlist-gated per guide 3 step 1. The command's presence
> on the CLI, its options, and its stdin-only secret handling were read from the
> source and confirmed on `onex --help`; the authentication round trip was not
> exercised.

### The genuinely composable piece: verify a hosted receipt on your own machine

This is the most useful thing in this pattern, and it is available to you offline.

Guide 3 step 5 documents the receipt a completed workflow returns, including a
`terminal_event_hash` presented as the receipt's integrity claim. That hash is
recomputable, and the function that computes it ships in `omnibase-infra`:

`omnibase_infra/src/omnibase_infra/verification/workflow_receipt/receipt_hash.py`
exposes `terminal_event_payload()` (line 30) and `sha256_of()` (line 26). The
payload shape is five fields, and they are exactly five fields the receipt hands
back to you. Run it yourself:

```python
from omnibase_infra.verification.workflow_receipt.receipt_hash import (
    sha256_of,
    terminal_event_payload,
)

payload = terminal_event_payload(
    correlation_id="11111111-2222-3333-4444-555555555555",
    status="completed",
    terminal_model_used="a-model",
    terminal_total_tokens=456,
    terminal_latency_ms=1234,
)
print(list(payload))
print(sha256_of(payload))
```

```
['correlation_id', 'status', 'terminal_model_used', 'terminal_total_tokens', 'terminal_latency_ms']
179e74b0877198fd9165181f801f364192e5b54fb0534aac375d9722489eabf5
```

Those exact inputs produce that exact digest — 64 hex characters, byte-stable
across repeated runs, both confirmed here. Note that the payload's own key order
is deliberately *not* the order that gets hashed: the encoding is
`json.dumps(payload, sort_keys=True, default=str)` UTF-8 encoded, SHA-256
hexdigest, so the keys are sorted on the way in. That is what makes the hash
independent of field order — and it is why you can rebuild the payload out of a
receipt's fields in whatever order you read them and still reproduce the digest.

So the hybrid pattern is: **the hosted service executes the work and issues the
receipt; your own machine independently recomputes the hash from the receipt's own
fields and compares.** A receipt whose `terminal_event_hash` does not reproduce
from its own `correlation_id`, `status`, `terminal_model_used`,
`terminal_total_tokens` and `terminal_latency_ms` is not internally consistent,
and you can establish that without asking the service to confirm anything about
itself.

Combine it with the check guide 3 already gives you — that a well-formed receipt's
two hashes are computed over different field sets and must therefore **differ from
each other** — and you have two independent integrity assertions, both computable
locally.

> **Unverified.** The recomputation was proven against synthetic field values, not
> against a receipt issued by the production API. Guide 3 states that the workflow
> routes are not currently listed in the production OpenAPI document, so no live
> receipt was available to check. The hash function is described in its own
> module docstring as a pinned mirror of the renderer that issues these receipts,
> with a parity test asserting they agree; that is a strong claim but it is a
> claim about the code, not a live end-to-end comparison.

### What is live, and what is not

Guide 3's availability table is the authority and this chapter does not restate
it. The one thing to carry across into a hybrid design: the **workflow submit /
poll / receipt routes are not advertised in the production OpenAPI document**,
while the API-key routes and the health check are. That was re-checked for this
chapter, unauthenticated, and still held — but the point of the check is that it
can change without warning, so run guide 3's `GET /openapi.json` yourself before
you build a dependency on any route rather than trusting either page's snapshot
of it.

Treat a `401` as evidence of nothing. Authentication is refused ahead of routing,
so every `/v1/` path returns `401` whether or not it exists — confirmed here by
requesting a real route and a route invented for the test and getting the same
`401` from both. The OpenAPI document is the only signal about what exists.

---

## Pattern C — author locally, execute in the cloud

**This combination is not available today.** Stating that plainly is more useful
than describing a flow you cannot run.

Guide 1 step 7 covers local authoring, and it works: `onex init` creates a
project, `onex new node <name> --type compute` writes a contract and a handler
skeleton. Both were re-executed for this chapter and both produced the documented
files.

The submission side does not connect to it, for two independent reasons:

1. **The hosted API takes a declared `workflow_type`, not a node.** Guide 3 step 4
   documents that a `workflow_type` the gateway has not declared is refused at
   ingress with `400`, and that the refusal lists the types that *are* accepted.
   There is no route that accepts a contract, a node package, or a handler. A node
   you scaffolded on your laptop is not a `workflow_type` the gateway knows.
2. **The submission routes are not advertised in production anyway**, per guide 3's
   availability table.

There is no environment variable, flag, or endpoint in `omnibase_core` or
`omnibase_infra` that submits a locally authored node to a hosted deployment. This
chapter searched for one and did not find it; if you see a recipe claiming
otherwise, check it against `GET /openapi.json` before believing it.

### What you *can* do with a locally authored node

The honest boundary, and it is narrower than guide 1 might leave you expecting.

A freshly scaffolded node is **not** runnable by `onex node` as generated.
Verified, on a clean scaffold, with the packaged-node lookup bypassed by pointing
`--contract` straight at the generated file:

```
ERROR omnibase_core.runtime.runtime_local — Workflow contract missing
'terminal_event' topic and no handler spec found (need
handler_routing.default_handler or handler.module/class).
```

The cause is a concrete mismatch between what the scaffold writes and what the
runtime reads. `onex new node --type compute` generates:

```yaml
handler_routing:
  default: my_onex_project.nodes.my_first_node.handlers.handler_my_first_node
```

while `RuntimeLocal._resolve_default_handler()`
(`omnibase_core/src/omnibase_core/runtime/runtime_local.py:1366`) reads
`handler_routing.default_handler` and requires a `module_ref:ClassName` value. The
generated handler is additionally a module-level `async def handle(input_data)`
function rather than a class, so the key name is not the only gap.

Separately, invoking `onex node <name>` **without** `--contract` resolves against
nodes packaged into the installed distribution, not against your project
directory; a scaffolded node is reported as `Unknown node` with a list of the
packaged ones.

This confirms and extends guide 1's own stated limit at the end of its step 7 —
that it verified the scaffold is generated correctly but did not verify running a
hand-written node. The scaffold gives you a correct contract to read and edit. It
does not give you a runnable node in one step, on any tier.

---

## Which tier for which activity

The decision table. "Author" means writing contracts and handlers; "test" means
proving your own logic; "integrate" means proving behaviour between components;
"operate" means running something others depend on.

| Activity | Tier | Why |
|---|---|---|
| **Author** a contract or handler | tier-0 | Nothing about writing a contract needs a broker. The scaffold and the contract read are offline operations. |
| **Test** handler logic, refusals, replay determinism | tier-0 | Fastest loop, and these properties are fully present in-process. A recorded completion makes the run deterministic and offline. |
| **Integrate** — second consumer, ordering, durability, consumer groups | self-hosted | Structurally absent from tier-0; the in-memory bus is per-process by construction. |
| **Integrate** — a deployed runtime consumer dispatching your command | self-hosted | Requires the runtime services and the migration gate from guide 2. |
| **Operate** something others depend on | self-hosted, or hosted | tier-0 has no durability and no second process. |
| **Operate** without running infrastructure yourself | hosted | The entire reason the hosted tier exists. |
| **Verify** a hosted receipt's integrity | tier-0 | The hash function runs offline, on the receipt's own fields. |
| **Evaluate** the platform | tier-0 | Guide 1 is the whole evaluation. |

### What changes when you cross a tier, and what does not

This is the part worth internalising, because it determines how much of your work
survives a move.

**Identical across all three tiers:**

| | Why it is invariant |
|---|---|
| Your `contract.yaml` | The contract is the specification the runtime resolves against. Nothing in it names a transport. |
| Your typed input and output models | Referenced by the contract by import path; the bus carries them, it does not define them. |
| Your handler code | It sits behind the runtime, on the far side of `_create_event_bus()`. It cannot observe which bus was constructed. |
| Topic names | Declared in the contract's `event_bus.subscribe_topics` / `publish_topics`. The same strings appear in the tier-0 evidence packet's `emitted_topics` and on the broker. |
| The `onex` binary and its command surface | One binary. Installing `omnibase-infra` adds commands; it does not replace or reshape the ones core provides. |
| The three-primitive model — contract, node, handler | Architectural, not deployment-specific. |

**Changes when you cross:**

| | tier-0 | self-hosted | hosted |
|---|---|---|---|
| Bus construction argument | `event_bus=inmemory` (default) | `event_bus=kafka` + a bootstrap address | not yours to set |
| Packages required | `omnibase-core` | `omnibase-core` + `omnibase-infra` + a checkout for `scripts/` and `docker/` | a client and a credential |
| Preconditions before a run | none | migration gate healthy, secrets present, broker advertising a reachable address | an account and an API key |
| Failure surface | one process, one traceback | dependency ordering, gate health, broker reachability | HTTP status codes |
| What proves success | the evidence packet plus an independent read of the projection row | the same, plus behaviour visible only between processes | a terminal status, then a receipt |
| Configuration required | none | per guide 2 | the `ONEX_API_*` variables |

The row that matters most is the first one, and it is deliberately one row.

---

## Troubleshooting

Rows marked **expected** are correct behaviour, not defects. Confirming them is
how you tell a working hybrid setup from a broken one.

| Symptom | Cause and what to do |
|---|---|
| `Requested event_bus=kafka but no entry point named 'event_bus_kafka' is registered` | **Expected** in a `omnibase-core`-only environment. The Kafka bus ships in `omnibase-infra`. Install it; do not treat this as a fallback path. |
| `Unsupported backend override event_bus='...'` | **Expected** for a typo. Only `inmemory` and `kafka` are accepted, and no other value silently degrades. Fix the spelling. |
| `Invalid --backend format '...'. Expected key=value` | **Expected.** `--backend` takes `key=value`, e.g. `--backend event_bus=inmemory`. |
| `--kafka-bootstrap is only valid with --bus kafka` | **Expected**, and a useful refusal — it catches the case where you would have run in-process while believing you were on the broker. Pick one. |
| `onex delegate` ran on Kafka when you expected in-process | Auto-resolution probed and found a broker, because `KAFKA_BOOTSTRAP_SERVERS` is set in your environment. Pass `--bus inmemory` explicitly. |
| `Kafka probe returned REACHABLE ...; the transport cannot be resolved repeatably` | **Expected**, and the most useful refusal on this page. `KAFKA_BOOTSTRAP_SERVERS` is set and TCP connects, but the metadata call timed out, so the broker's serving state is unknown — and it is not sticky, since the next identical run may resolve cleanly. Decide it yourself: `--bus kafka` or `--bus inmemory`. See [an indeterminate probe refuses](#the-third-outcome-an-indeterminate-probe-refuses-instead-of-guessing). |
| You set `ONEX_EVENT_BUS_TYPE` and want to know whether it applies here | It does, on both paths, and it outranks the probe. An explicit `--bus` still outranks it. |
| `auth`, `delegate`, `node`, `run`, `skill`, `kafka`, `occ` missing from `onex --help` | `omnibase-infra` is not installed in the interpreter answering `onex`. Confirm with `onex --verbose info`, which prints the interpreter path and the installed ONEX packages. |
| A flipped run hangs against your self-hosted stack | Verify the stack on its own terms first — guide 2 step 5, gate before kernel. A flipped run cannot distinguish "broker unreachable" from "gate never went healthy". |
| External client connects, then fails on the next call | The broker's advertised address, per guide 2. Presents identically whether the client is a flipped local run or anything else. |
| `Workflow contract missing 'terminal_event' topic and no handler spec found` on a fresh scaffold | **Expected.** The scaffold writes `handler_routing.default`; the runtime reads `handler_routing.default_handler` in `module_ref:ClassName` form. See Pattern C. |
| `Unknown node '<your-node>'` from `onex node` | `onex node` resolves nodes packaged into the installed distribution. A project-directory scaffold is not one. |
| `ONEX_API_TIMEOUT_SECONDS` appears to have no effect | A value that does not parse as an integer is skipped silently rather than raising. Check the value. |
| Exported `ONEX_API_KEY` but the client is unauthenticated | The env mapping is applied by an explicit `apply_environment_overrides()` call, not absorbed at construction. Call it. |
| A hosted route returns `401` and you cannot tell if it exists | Authentication is refused ahead of routing. Read `GET /openapi.json` — unauthenticated, and authoritative. |

---

## Verification posture for this page

Same posture as the three guides it composes. Executed and proven here:

- The tier-0 baseline from guide 1, in a clean virtual environment against the
  packages as published on the public index — `bus_impl: EventBusInmemory`,
  three emitted topics, `terminal_status: success`, exit `0`.
- The entry-point CLI composition, by installing `omnibase-core` then
  `omnibase-infra` into one clean environment and diffing `onex --help`: exactly
  seven commands added, none replaced.
- Every refusal quoted above: the missing-entry-point error, the unsupported-value
  error, the `--backend` format error, and the `--kafka-bootstrap` guardrail.
- All three outcomes of bus auto-resolution — the two environment-driven branches
  isolated by changing only the environment, and the timeout branch by repeating
  one call twenty times against a live broker.
- The resolution order and the refusal on an indeterminate probe, against the
  `omnibase_infra` unit suite that pins them, with the probe mocked so each tier
  and each probe state is exercised in isolation. The refusal message quoted above
  is the one the resolver raises; it was not re-measured against a live broker,
  because reproducing the timeout branch on demand is exactly what this section
  says you cannot do.
- Local recomputation of a receipt hash, for shape and stability, from the inputs
  printed alongside it.
- The scaffold, and the two distinct ways a scaffolded node fails to run.
- Every source citation on this page, re-resolved line by line against both the
  repository and the installed distributions — the cited `runtime_local.py` is
  byte-identical between them.

Read-only against the live production API, with no account and no credential:
`GET /health` answered, `GET /openapi.json` was read for the current route list —
the workflow submit/poll/receipt routes are still absent from it while the
API-key routes and the health check are present — and the `401`-ahead-of-routing
claim was confirmed directly, since a real `/v1/` route and a route invented for
the test returned the same `401`.

Marked unverified in place, with the reason: the `onex auth` network round trip
(needs a waitlist-gated tenant credential), and recomputing a hash against a
receipt issued by the production API (the workflow routes are not advertised
there, so no live receipt was obtainable).

Not exercised: Linux and Windows. Every command here was run on macOS.

---

## Related pages

- [Getting started locally](getting-started-local.md) — tier-0 in full.
- [Self-hosting the full stack](getting-started-self-hosted.md) — the stack a flipped run lands on.
- [Connecting to the cloud](connecting-to-the-cloud.md) — the hosted tier as a client.
- [Handler authoring guide](handler-authoring-guide.md) — writing the logic behind the contract.
