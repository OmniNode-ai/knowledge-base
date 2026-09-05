---
type: guide
status: current
date: "2026-08-26"
title: "Connecting to the OmniNode Cloud"
topics: [cloud, api, authentication, workflows, delegation, getting-started]
refs: []
---

# Connecting to the OmniNode Cloud

This guide is for someone who wants to send work to **the hosted OmniNode service** rather than run the platform themselves: get an account, get a credential, install the client, submit a job, and read the result back.

## Read this first: the hosted service is the second option, not the first

This knowledge base is the self-hoster's book. The first-class way to start with ONEX is to run it yourself in its **zero-external-infrastructure configuration** — the in-process event bus and local file-backed state, no broker, no cluster, no account, no network dependency. That path needs nothing from us, and it is the one to reach for when you are evaluating the platform, developing against it, or running it in your own environment. Scaling that up to the full stack (a real broker, a real database, real projections) is a later chapter, not a prerequisite.

The hosted service exists for people who want the workload run on someone else's machines. That is what this page covers, and only that. Nothing here is required to use ONEX.

## Use the client, not hand-written HTTP

The supported way to reach the hosted service is the `onex cloud` client: `onex cloud login` stores your credential by reference, `onex cloud delegate` submits a task and waits for it, and `onex cloud receipt` collects a run afterwards. The client is what the four steps below use.

The API it calls is a documented HTTP surface, and the [appendix](#appendix--the-raw-http) records it call by call for anyone building their own client or debugging a step the client wraps. That appendix is a reference, not the recommended path — everything in it, the client already does.

## Availability of each step, stated honestly

The steps below are at different levels of readiness. This table is the summary; each section repeats its own status in place. Nothing on this page is described as working unless it was checked.

| Step | Status |
|---|---|
| Create an account | **Live, waitlist-gated.** Signing up joins a list; accounts are granted by the OmniNode team, not self-served. |
| Sign in to the dashboard | **Live.** |
| Create an API key in the dashboard | **Intended flow described; browser click-through not yet confirmed.** The creation path was recently repaired and the repaired build deployed, but no end-to-end click-through by a signed-in user has been recorded. See the section for what to do if it fails. |
| Create an API key over the API | **Live.** `POST /v1/api-keys` is advertised by the production API's own OpenAPI document. |
| Install the client and log in | **Live.** The published `omnimarket` package contributes `onex cloud` to the `onex` CLI. Logging in stores a credential locally and contacts nothing. |
| Reach the API base URL, unauthenticated health check | **Live, verified.** |
| Authenticate with an API key or a bearer token | **Live, verified** — both header shapes are accepted by the gateway, and unauthenticated calls are refused. |
| Delegate a task and read its receipt | **Proven working, not yet advertised on the production API.** The full submit, poll, receipt loop — which is exactly what `onex cloud delegate` performs — has been run end to end against a pre-production build of the same gateway. The production API's OpenAPI document does **not** currently list the workflow routes. Treat this as the intended and proven flow, and confirm availability against the live OpenAPI document before you build on it — see [Check what the API actually offers today](#check-what-the-api-actually-offers-today). |

---

## 1. Get an account

The public sign-up page is at `https://omninode.ai/signup`. (`/waitlist` is an older link that redirects there.)

**The account path is waitlist-gated today.** The site ships with waitlist mode switched on in its checked-in feature contract, which means the sign-up form registers your interest rather than provisioning a tenant on the spot. Someone on the OmniNode side then creates the account. There is an environment override for that switch, so the honest statement is: *the shipped default is waitlist mode* — if the form signs you straight in instead, the override is set on that deployment.

Practically, this means:

- You do not self-serve a tenant. Expect a wait and an out-of-band reply.
- Your credential may be handed to you directly during a beta, rather than created by you in the dashboard.
- Everything from step 3 onward works identically no matter how you obtained the key.

Once your account exists, the dashboard is at `https://app.omninode.ai`. Sign-in is OpenID Connect against the public identity provider at `https://auth.omninode.ai/realms/omninode`.

---

## 2. Get an API key

An OmniNode API key is a long random string with the stable prefix `onxk_`. It identifies your **tenant**, and every workflow you submit is scoped to it.

### The dashboard flow

1. Sign in at `https://app.omninode.ai`.
2. Go to **API Keys** (`/app/api-keys`).
3. Enter a name for the key and create it.
4. **Copy the key immediately.** The full value is returned exactly once, at creation. After that the dashboard only ever shows the key's name, id, active flag, creation time, and last-used time — never the secret again. If you lose it, revoke it and make a new one.

Key names are validated: 1–128 characters, and only letters, digits, spaces, hyphens, underscores and periods. Leading and trailing whitespace is stripped before the length check.

> **Availability — read before relying on this.** This is the intended flow, and the page is enabled in the shipped feature contract, but its click-through has not been confirmed end to end by a signed-in user since the creation path was last repaired. The repair is deployed and structurally verified; the missing evidence is a person actually pressing the button. Two consequences worth knowing:
>
> - If creation fails with an authorization error, sign out fully (or use a private window) and sign in again before retrying. A stale browser session can forward an expired token, which the API refuses in a way that looks identical to the bug that was fixed.
> - If it still fails after a clean sign-in, use [the API route in the appendix](#c-manage-api-keys-over-the-api), or ask for a key to be issued to you directly.

### Handling the key

Treat it like a password. Never type it into a command-line argument, never commit it, and never echo it into logs or into a prompt you hand to an agent. The next step reads it from stdin for exactly this reason.

---

## 3. Install the client and log in

```bash
uv tool install --python 3.12 --upgrade --with omnimarket omnibase-core
```

**Name the interpreter.** `omnimarket` currently declares `requires-python = ">=3.12,<3.13"`, so an unqualified install resolves against whatever default interpreter the machine happens to have and fails outright on 3.13. Passing `--python 3.12` makes `uv` fetch a matching interpreter rather than depending on what is already there.

The `omnimarket` package is what contributes the `cloud` command to the `onex` CLI — it is advertised through an entry-point group and discovered over the installed distributions, not hand-wired. Confirm it registered:

```bash
onex cloud --help
```

If that says `No such command 'cloud'`, `omnimarket` is not installed in the same tool environment as `onex`. Re-run the install line exactly as written, including `--with omnimarket`.

Now store the credential. It is read from stdin; there is no option that takes the key as a value, because a flag value lands in the process table, the shell history, and every exec log:

```bash
read -rs ONXK && printf '%s' "$ONXK" | \
  onex cloud login --base-url https://api.omninode.ai --api-key-stdin
```

`https://api.omninode.ai` is the public production address of the ONEX control-plane API. The client has **no built-in default origin** — a default would mean sending a live customer key to whatever host the release happened to ship with — so `--base-url` is how it learns where to go, and it remembers it.

Check what is configured without revealing the key:

```bash
onex cloud status
```

```
gateway base_url: https://api.omninode.ai
profile:          default
api_key:          stored by reference (not shown)
```

That is the command to paste into a support thread: it prints identity and endpoints only. The key itself is stored by reference under `~/.onex/credentials.json`, mode `0600`.

`onex cloud logout` removes it again.

### Check what the API actually offers today

The gateway publishes its own machine-readable route list, unauthenticated, and it is the authoritative answer to "is this available yet":

```
GET https://api.omninode.ai/openapi.json
```

Fetch it and read the `paths` object. Note that a `401` is **not** evidence a route exists — authentication is refused ahead of routing, so every `/v1/` path returns `401` unauthenticated, real or not. The OpenAPI document is the signal, and it is the check that produced the availability table at the top of this guide. The [appendix](#appendix--the-raw-http) has a one-liner for it.

---

## 4. Delegate a task and read the result

> **Availability.** This is the step the availability table marks *proven, not yet advertised*. The full loop has been run end to end from outside the cluster against a pre-production build of this same gateway, with a real model executing the job. The production API's OpenAPI document does not currently list the workflow routes. Run the check above before you depend on it.

```bash
onex cloud delegate "Write a one-sentence description of what delegation is." \
  --task-type reasoning
```

The client submits the task, polls it to a terminal state, fetches the signed receipt, prints the generated output, and writes three files under `onex-delegations/<workflow-id>/`:

| File | What it holds |
|---|---|
| `result.txt` | The generated output, as text. |
| `receipt.json` | The signed receipt — which model ran it, token count, latency, and the two integrity hashes. |
| `run.json` | What you asked for: prompt, task type, token budget, and the gateway you sent it to. |

The command prints those paths and a summary line naming the model, the token count and the latency.

**A run that produced no content still writes its receipt**, and the command exits non-zero rather than reporting an empty success. A terminal failure with no content is a real outcome — the submit was accepted and the runtime could not answer — so it is named, saved, and never silently retried.

`--task-type` is one of: `test`, `document`, `research`, `code_generation`, `code_review`, `refactor`, `reasoning`, `complex_reasoning`, `planning`, `review`, `summarization`. Add `--max-tokens` to cap the response; omit it and the platform resolves the budget from its own routing contract rather than a client-side default.

### Collecting a run later

A delegation that outlives the client's poll budget is still running on the platform. Its workflow id is all you need to collect it afterwards, and this is also how you re-download a receipt whose local copy was lost:

```bash
onex cloud receipt <workflow-id>
```

### What a receipt says

```json
{
  "workflow_id": "<uuid>",
  "tenant_id": "<uuid>",
  "correlation_id": "<uuid>",
  "workflow_type": "delegation-inference",
  "status": "completed",
  "submitted_at": "<timestamp>",
  "completed_at": "<timestamp>",
  "terminal_model_used": "<model id>",
  "terminal_total_tokens": 456,
  "terminal_latency_ms": 1234,
  "result_content": "Delegation is handing a task to the platform ...",
  "event_count": 1,
  "projection_row_hash": "<64 hex characters>",
  "terminal_event_hash": "<64 hex characters>",
  "verifier": "onex-cloud-delegate@<your hostname>"
}
```

| Field | What it is |
|---|---|
| `workflow_id`, `tenant_id`, `correlation_id`, `workflow_type`, `status`, `submitted_at` | Read straight from the workflow's own record. `status` is always `completed` or `failed` — a receipt cannot exist for anything else. |
| `completed_at` | When the terminal status was written. |
| `terminal_model_used`, `terminal_total_tokens`, `terminal_latency_ms` | Which model ran the work, how many tokens it used, how long it took. |
| `result_content` | **The actual output** — your work product. Genuinely optional: `null` for workflow shapes that carry no content, and for a terminal event that omitted it. |
| `event_count` | Always `1` today. Exactly one terminal event is ever durably applied per workflow, so this records that fact rather than counting a journal — there is no event journal behind it yet. |
| `projection_row_hash` | SHA-256 over the canonical form of the receipt's projection fields. |
| `terminal_event_hash` | SHA-256 over just the terminal-outcome subset. |
| `verifier` | Who asked for this receipt. The client stamps `onex-cloud-delegate@<hostname>` unless you pass `--runner-identity`. It is deliberately not server-derived: the receipt's job is to record who *verified* a workflow, which is a different fact from who *ran* it. |

The two hashes are the receipt's integrity claim, and they are computed over **different** field sets. A well-formed receipt has two 64-character hashes that are **not equal to each other**; identical hashes would mean the renderer hashed one source twice. If you are gating anything on a receipt, assert that inequality rather than settling for an exit code of zero.

---

## Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `onex cloud --help` says `No such command 'cloud'` | `omnimarket` is not in the same tool environment as `onex` | Re-run the step 3 install line, including `--with omnimarket`. |
| The install fails resolving `omnimarket` | The interpreter is out of range | Pass `--python 3.12` as shown; `omnimarket` declares `>=3.12,<3.13`. |
| A refusal naming `onex cloud login` | No credential is configured for this shell | Run `onex cloud login`, or point `--api-key-file` at a `0600` file holding the key. |
| `onex cloud login` refuses the key | The key must arrive on stdin and start with `onxk_` | Create a fresh key if the old one was lost or revoked. |
| `401` on every call | Key revoked, or the wrong plane | Confirm the key is listed and active, and that `onex cloud status` names the host that issued it. If the key was handed to you, ask for it to be reissued. |
| `401` from a bearer token that worked earlier | Token expired, or the browser session behind it went stale | Mint a fresh token. In the dashboard, sign out completely or use a private window. |
| `400` naming an extra or forbidden field | You sent a routing field such as `topic` or `tenant_id`, or a payload key outside the declared schema | Remove it. The refusal is deliberate: callers submit workflows, not routing instructions. |
| A route returns `401` and you cannot tell whether it exists | Authentication is refused ahead of routing | Read `GET /openapi.json`. It is unauthenticated, and it is the authoritative route list. |
| The run stays `published` past the timeout | Slow execution, or something stuck upstream | Keep the workflow id and run `onex cloud receipt <workflow-id>` later. If it never terminates, report it with that id. |
| A receipt comes back with two identical hashes | The receipt's integrity claim is not intact | Do not accept it as proof. Report it with the `workflow_id`. |

---

## Where to go next

- [`guides/`](README.md) — the rest of the task-oriented documentation, including running the platform yourself.
- [`docs-taxonomy.md`](../docs-taxonomy.md) — what belongs in this book and what deliberately does not. OmniNode's own cloud topology is out of scope here; *connecting to it as a user*, which is this page, is in.

<!-- primary-path-ends -->

---

# Appendix — the raw HTTP

**Everything above this line is the supported customer path.** This appendix records the HTTP surface the client calls, for two audiences: someone building their own client, and someone debugging a step the client wraps. It is a reference, not a recommendation — the client already does all of it.

## Environment variables

These are the names the platform's own REST connection configuration reads, so using them keeps a hand-rolled setup consistent with the tooling. `onex cloud` itself reads `ONEX_API_BASE_URL` and `ONEX_API_KEY_FILE`.

| Variable | Meaning |
|---|---|
| `ONEX_API_BASE_URL` | API base URL. |
| `ONEX_API_KEY` | Your `onxk_`-prefixed API key. |
| `ONEX_API_KEY_FILE` | Path to a `0600` file holding the key — the client's non-interactive/CI form. |
| `ONEX_API_BEARER_TOKEN` | An OIDC access token, as an alternative to the API key. |
| `ONEX_API_TIMEOUT_SECONDS` | Request timeout. |
| `ONEX_API_MAX_RETRIES` | Retry budget. |

The examples below use `ONEX_API_KEY` and a shell-local `ONEX_API_BASE`:

```bash
export ONEX_API_KEY="onxk_..."
export ONEX_API_BASE="https://api.omninode.ai"
```

## A. Health and route discovery, unauthenticated

```bash
curl -sS https://api.omninode.ai/health
```

```json
{"ok": true, "service": "onex-api", "version": "0.1.0", "time": "<timestamp>"}
```

```bash
curl -sS https://api.omninode.ai/openapi.json | python3 -c \
  'import json,sys; [print(p) for p in sorted(json.load(sys.stdin)["paths"])]'
```

## B. Auth header shapes

The gateway accepts **two** credential shapes on the same routes. Pick one.

**API key** — the simpler path, and the shape a beta credential will be:

```
x-api-key: onxk_...
```

**OIDC bearer token** — for machine clients that mint their own short-lived tokens, via the OAuth 2.0 client-credentials grant:

```bash
TOKEN=$(printf %s "$CLIENT_SECRET" | curl -sS \
  "https://auth.omninode.ai/realms/omninode/protocol/openid-connect/token" \
  -d grant_type=client_credentials \
  -d client_id="$CLIENT_ID" \
  --data-urlencode client_secret@- \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
```

```
Authorization: Bearer <token>
```

> **Gotcha, learned the hard way.** Feeding the client secret from a file or from `echo` appends a trailing newline, which is percent-encoded into the form body and produces a flat `401 invalid_client` with no other clue. Pipe the value with `printf %s` — no newline — as shown above. The same applies to any `--data-urlencode ...@-` usage.

Access tokens are short-lived by design; there is nothing to revoke after use. Unset both the secret and the token when you are done with them.

Confirm the credential works, whichever shape you chose:

```bash
curl -sS -H "x-api-key: $ONEX_API_KEY" "$ONEX_API_BASE/v1/whoami"
curl -sS -H "x-api-key: $ONEX_API_KEY" "$ONEX_API_BASE/v1/tenants"
```

`/v1/whoami` returns your resolved identity. `/v1/tenants` returns a single-element array — your own tenant record. A missing or bad credential returns `401` with `{"detail":"Unauthorized"}` on every `/v1/` route.

## C. Manage API keys over the API

If you already hold a bearer token for your tenant, you can create a key without the dashboard. This route **is** advertised by the production API:

```bash
curl -sS -X POST "https://api.omninode.ai/v1/api-keys" \
  -H "Authorization: Bearer $ONEX_API_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-first-key"}'
```

The response carries the plaintext key once:

```json
{
  "id": "<uuid>",
  "name": "my-first-key",
  "is_active": true,
  "created_at": "<timestamp>",
  "last_used_at": null,
  "plaintext_key": "onxk_..."
}
```

Listing and revoking:

```bash
# List your keys — names and ids only, never the secret
curl -sS "https://api.omninode.ai/v1/api-keys" -H "x-api-key: $ONEX_API_KEY"

# Revoke one by id
curl -sS -X DELETE "https://api.omninode.ai/v1/api-keys/<key-id>" \
  -H "x-api-key: $ONEX_API_KEY"
```

Revocation returns `{"ok": true}`. Revoking a key you are currently authenticating with is allowed — the key simply stops working afterwards.

## D. Submit, poll, and fetch a receipt by hand

This is the loop `onex cloud delegate` performs for you.

The unit of work is a **workflow**: a declared `workflow_type` plus a `payload` that must match that type's contract-declared schema. You never name a topic, a queue, or a route — the platform resolves all of that from the contract. A `workflow_type` the gateway has not declared is refused at ingress with `400` before anything is published, and the refusal lists the types that *are* accepted.

### Submit

```bash
curl -sS -X POST "$ONEX_API_BASE/v1/workflows" \
  -H "x-api-key: $ONEX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_type": "delegation-inference",
    "payload": {
      "prompt": "Write a one-sentence description of what delegation is.",
      "task_type": "reasoning",
      "max_tokens": 200
    }
  }'
```

The `delegation-inference` payload schema, exactly as declared:

| Field | Required | Rules |
|---|---|---|
| `prompt` | yes | string, 1 to 32768 characters |
| `task_type` | yes | one of `test`, `document`, `research`, `code_generation`, `code_review`, `refactor`, `reasoning`, `complex_reasoning`, `planning`, `review`, `summarization` |
| `max_tokens` | no | integer, minimum 1 |
| `context_pack` | no | string, up to 65536 characters |

Two envelope-level fields may also ride at the **top** level of the request body, beside `workflow_type` and `payload`: `correlation_id` and `causation_id`, both UUIDs. Omit `correlation_id` and one is generated for you.

Both the request body and the payload reject unknown fields outright rather than ignoring them. That is deliberate: a caller-supplied `topic`, `command_topic`, or `tenant_id` is an attempt to steer routing, and it is refused with `400`, not silently dropped. If you get a `400` naming an extra field, remove the field — do not try to make it fit.

A successful submission returns **HTTP 202** *after* the command has been durably published, never before:

```json
{
  "workflow_id": "<uuid>",
  "envelope_id": "<uuid>",
  "correlation_id": "<uuid>",
  "workflow_type": "delegation-inference",
  "status": "published",
  "accepted_at": "<timestamp>"
}
```

### Poll status

```bash
curl -sS -H "x-api-key: $ONEX_API_KEY" \
  "$ONEX_API_BASE/v1/workflows/$WORKFLOW_ID/status"
```

Re-run every few seconds until `status` reaches a terminal value.

| `status` | Meaning |
|---|---|
| `accepted` | Recorded, not yet published to the bus. |
| `published` | On the bus, awaiting or undergoing execution. |
| `completed` | Terminal, succeeded. |
| `failed` | Terminal, failed. |
| `failed_publish` | Terminal. The submission was recorded but could not be published — you would have received a `503`, not a `202`. |

The response is metadata only: `workflow_id`, `workflow_type`, `status`, `envelope_id`, `correlation_id`, `command_topic` (resolved by the platform, not by you), `submitted_at`, `updated_at`, and the three `terminal_*` fields, which are `null` until the workflow closes out. **Status never carries the output** — that is by design, and retrieving the actual result requires the receipt call below.

### Fetch the receipt

```bash
curl -sS --get \
  -H "x-api-key: $ONEX_API_KEY" \
  --data-urlencode "runner_identity=my-manual-test" \
  "$ONEX_API_BASE/v1/workflows/$WORKFLOW_ID/receipt"
```

`runner_identity` is **required and has no default** — omit it and you get a `422` before the handler ever runs. It becomes the receipt's `verifier` field. `onex cloud` supplies it for you; a hand-rolled client must choose one.

Use `--data-urlencode` rather than pasting the value into the query string: the value is free text and may contain spaces or `&`, `+`, `#`, which would otherwise corrupt the request or silently record the wrong verifier.

A receipt is rendered only for a **terminal** workflow. Asking for one before the workflow has completed or failed returns `409` — go back to polling.

> **What this endpoint is, honestly.** The receipt route was built as an internal definition-of-done and verification tool, not as an advertised customer surface, and the team that owns it says so in its own documentation. It is live, it is reachable by any authenticated tenant, and it is the only way to retrieve a workflow's actual output today — which is why it is documented here. But its contract is aimed at a verifier, not at an application. If your product depends on retrieving results, expect this shape to be superseded by something designed for that purpose.

## E. Response codes

| Code | Where | Meaning, and what to do |
|---|---|---|
| `202` | submit | Accepted **and published**. Save the `workflow_id`. |
| `400` | submit | Malformed body, unrecognised field, unknown `workflow_type`, or a type that is declared but not currently submittable. The body lists the accepted types. Fix the request; do not retry it unchanged. |
| `400` | status, receipt | `workflow_id` is not a UUID, or `runner_identity` was present but blank. |
| `401` | any `/v1/` route | Missing, malformed, or rejected credential. Check the header name and value. If it is a bearer token, check it has not expired. |
| `404` | status, receipt | No such workflow **for your tenant**. Another tenant's workflow also returns `404`, never `403` — telling you a row exists elsewhere would itself be a cross-tenant leak. |
| `409` | receipt | The workflow has not reached a terminal state. Keep polling status. |
| `422` | receipt | `runner_identity` was omitted entirely. Add it. |
| `429` | submit | A limit was hit, in one of two distinct cases. A per-minute rate limit returns a body carrying `limit_per_minute`, `burst_capacity` and `retry_after_seconds` — honour the retry hint. A monthly execution quota returns a body carrying `plan_code`, `limit_value`, `used`, `remaining` and `window_start` — retrying will not help until the window rolls over. |
| `503` | any | A dependency was unavailable and the gateway refused rather than guess. On submit this specifically means nothing was published — you never get a `202` for work that did not reach the bus. Retry with backoff. |
