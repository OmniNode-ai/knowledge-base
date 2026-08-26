---
type: guide
status: current
date: "2026-08-26"
title: "Connecting to the OmniNode Cloud"
topics: [cloud, api, authentication, workflows, delegation, getting-started]
refs: []
---

# Connecting to the OmniNode Cloud

This guide is for someone who wants to send work to **the hosted OmniNode service** rather than run the platform themselves: get an account, get a credential, point a client at the public API, submit a job, and read the result back.

## Read this first: the hosted service is the second option, not the first

This knowledge base is the self-hoster's book. The first-class way to start with ONEX is to run it yourself in its **zero-external-infrastructure configuration** — the in-process event bus and local file-backed state, no broker, no cluster, no account, no network dependency. That path needs nothing from us, and it is the one to reach for when you are evaluating the platform, developing against it, or running it in your own environment. Scaling that up to the full stack (a real broker, a real database, real projections) is a later chapter, not a prerequisite.

The hosted service exists for people who want the workload run on someone else's machines. That is what this page covers, and only that. Nothing here is required to use ONEX.

## Availability of each step, stated honestly

The steps below are at different levels of readiness. This table is the summary; each section repeats its own status in place. Nothing on this page is described as working unless it was checked.

| Step | Status |
|---|---|
| Create an account | **Live, waitlist-gated.** Signing up joins a list; accounts are granted by the OmniNode team, not self-served. |
| Sign in to the dashboard | **Live.** |
| Create an API key in the dashboard | **Intended flow described; browser click-through not yet confirmed.** The creation path was recently repaired and the repaired build deployed, but no end-to-end click-through by a signed-in user has been recorded. See the section for what to do if it fails. |
| Create an API key over the API | **Live.** `POST /v1/api-keys` is advertised by the production API's own OpenAPI document. |
| Reach the API base URL, unauthenticated health check | **Live, verified.** |
| Authenticate with an API key or a bearer token | **Live, verified** — both header shapes are accepted by the gateway, and unauthenticated calls are refused. |
| Submit a workflow, poll status, fetch a receipt | **Proven working, not yet advertised on the production API.** The full loop has been run end to end against a pre-production build of the same gateway. The production API's OpenAPI document does **not** currently list the workflow routes. Treat this section as the intended and proven flow, and confirm availability against the live OpenAPI document before you build on it — see [Check what the API actually offers today](#check-what-the-api-actually-offers-today). |

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
> - If it still fails after a clean sign-in, use the API path below, or ask for a key to be issued to you directly.

### The API flow

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

### Handling the key

Treat it like a password. Set it as an environment variable rather than typing it into commands you paste into shared places, never commit it, and never echo it into logs or into a prompt you hand to an agent.

---

## 3. Configure your endpoint

### Base URL

```
https://api.omninode.ai
```

This is the public production address of the ONEX control-plane API, and it is the value the platform's own code falls back to when no base URL is configured. Confirm reachability with no credential at all:

```bash
curl -sS https://api.omninode.ai/health
```

```json
{"ok": true, "service": "onex-api", "version": "0.1.0", "time": "<timestamp>"}
```

### Environment variables

If you are driving the API from a shell or from your own scripts, these are the names the platform's own REST connection configuration reads, so using them keeps your setup consistent with the tooling:

| Variable | Meaning |
|---|---|
| `ONEX_API_BASE_URL` | API base URL. Defaults to `https://api.omninode.ai`. |
| `ONEX_API_KEY` | Your `onxk_`-prefixed API key. |
| `ONEX_API_BEARER_TOKEN` | An OIDC access token, as an alternative to the API key. |
| `ONEX_API_TIMEOUT_SECONDS` | Request timeout. |
| `ONEX_API_MAX_RETRIES` | Retry budget. |

The `curl` examples below use `ONEX_API_KEY` and a shell-local `ONEX_API_BASE` for brevity:

```bash
export ONEX_API_KEY="onxk_..."
export ONEX_API_BASE="https://api.omninode.ai"
```

### Auth header shape

The gateway accepts **two** credential shapes on the same routes. Pick one.

**API key** — the simpler path, and the shape a beta credential will be:

```
x-api-key: onxk_...
```

**OIDC bearer token** — for machine clients that mint their own short-lived tokens. Get one from the public identity provider with the OAuth 2.0 client-credentials grant:

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

> **Gotcha, learned the hard way.** Feeding the client secret to `curl` from a file or from `echo` appends a trailing newline, which is percent-encoded into the form body and produces a flat `401 invalid_client` with no other clue. Pipe the value with `printf %s` — no newline — as shown above. The same applies to any `--data-urlencode ...@-` usage.

Access tokens are short-lived by design; there is nothing to revoke after use. Unset both the secret and the token when you are done with them.

Confirm the credential works, whichever shape you chose:

```bash
curl -sS -H "x-api-key: $ONEX_API_KEY" "$ONEX_API_BASE/v1/whoami"
curl -sS -H "x-api-key: $ONEX_API_KEY" "$ONEX_API_BASE/v1/tenants"
```

`/v1/whoami` returns your resolved identity. `/v1/tenants` returns a single-element array — your own tenant record. A missing or bad credential returns `401` with `{"detail":"Unauthorized"}` on every `/v1/` route.

### Check what the API actually offers today

The gateway publishes its own machine-readable route list, unauthenticated:

```bash
curl -sS https://api.omninode.ai/openapi.json | python3 -c \
  'import json,sys; [print(p) for p in sorted(json.load(sys.stdin)["paths"])]'
```

Run this before building against any route on this page. It is the authoritative answer to "is this available yet", and it is the check that produced the availability table at the top of this guide. Note that a `401` is **not** evidence a route exists — authentication is refused ahead of routing, so every `/v1/` path returns `401` unauthenticated, real or not. The OpenAPI document is the signal.

---

## 4. Submit work and read it back

> **Availability.** The three routes in this section are proven — the full submit, poll, receipt loop has been run end to end from outside the cluster against a pre-production build of this same gateway, with a real model executing the job. They are **not currently listed in the production API's OpenAPI document.** Run the check above before you depend on them. What follows is the flow as it works, with the schemas as the gateway actually validates them.

The unit of work is a **workflow**: a declared `workflow_type` plus a `payload` that must match that type's contract-declared schema. You never name a topic, a queue, or a route — the platform resolves all of that from the contract. A `workflow_type` the gateway has not declared is refused at ingress with `400` before anything is published, and the refusal lists the types that *are* accepted.

### Step 1 — submit

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

Keep the `workflow_id`. You need it for both remaining steps.

### Step 2 — poll status

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

The response is metadata only:

```json
{
  "workflow_id": "<uuid>",
  "workflow_type": "delegation-inference",
  "status": "completed",
  "envelope_id": "<uuid>",
  "correlation_id": "<uuid>",
  "command_topic": "<resolved by the platform, not by you>",
  "submitted_at": "<timestamp>",
  "updated_at": "<timestamp>",
  "terminal_model_used": "<model id>",
  "terminal_total_tokens": 456,
  "terminal_latency_ms": 1234
}
```

The three `terminal_*` fields are `null` until the workflow closes out. **Status never carries the output** — that is by design, and retrieving the actual result requires the receipt call below.

### Step 3 — fetch the receipt

```bash
curl -sS --get \
  -H "x-api-key: $ONEX_API_KEY" \
  --data-urlencode "runner_identity=my-manual-test" \
  "$ONEX_API_BASE/v1/workflows/$WORKFLOW_ID/receipt"
```

`runner_identity` is **required and has no default**. It is free text you choose, naming *whoever is asking for this receipt* — an operator label, a session id, a CI run id. It becomes the receipt's `verifier` field. It is deliberately not defaulted and never derived from the server, because the receipt's whole job is to record who *verified* a workflow, which is a different fact from who *ran* it. Omit it and you get a `422` before the handler ever runs.

Use `--data-urlencode` rather than pasting the value into the query string: the value is free text and may contain spaces or `&`, `+`, `#`, which would otherwise corrupt the request or silently record the wrong verifier.

> **What this endpoint is, honestly.** The receipt route was built as an internal definition-of-done and verification tool, not as an advertised customer surface, and the team that owns it says so in its own documentation. It is live, it is reachable by any authenticated tenant, and it is the only way to retrieve a workflow's actual output today — which is why it is documented here. But its contract is aimed at a verifier, not at an application. If your product depends on retrieving results, expect this shape to be superseded by something designed for that purpose.

---

## 5. What you get back

A receipt is rendered only for a **terminal** workflow. Asking for one before the workflow has completed or failed returns `409` — go back to polling.

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
  "verifier": "my-manual-test"
}
```

| Field | What it is |
|---|---|
| `workflow_id`, `tenant_id`, `correlation_id`, `workflow_type`, `status`, `submitted_at` | Read straight from the workflow's own record. `status` is always `completed` or `failed` — a receipt cannot exist for anything else. |
| `completed_at` | When the terminal status was written. |
| `terminal_model_used`, `terminal_total_tokens`, `terminal_latency_ms` | Which model ran the work, how many tokens it used, how long it took. |
| `result_content` | **The actual output** — your work product. Genuinely optional: `null` for workflow shapes that carry no content, and for a terminal event that omitted it. This is the one field the receipt exposes that the status route does not. |
| `event_count` | Always `1` today. Exactly one terminal event is ever durably applied per workflow, so this records that fact rather than counting a journal — there is no event journal behind it yet. |
| `projection_row_hash` | SHA-256 over the canonical form of the receipt's projection fields. |
| `terminal_event_hash` | SHA-256 over just the terminal-outcome subset. |
| `verifier` | The `runner_identity` you supplied. Never defaulted, never server-derived. |

The two hashes are the receipt's integrity claim, and they are computed over **different** field sets. A well-formed receipt has two 64-character hashes that are **not equal to each other**; identical hashes would mean the renderer hashed one source twice. If you are gating anything on a receipt, assert that inequality rather than settling for an HTTP 200.

---

## Response codes you should expect

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

---

## Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `401` on every call, including `/v1/whoami` | Header name or value wrong, or the key was revoked | Confirm the header is exactly `x-api-key` and the value starts with `onxk_`. Confirm the key is still listed and active via `GET /v1/api-keys`. If the key was handed to you, ask for it to be reissued. |
| `401` from a bearer token that worked earlier | Token expired, or the browser session behind it went stale | Mint a fresh token. In the dashboard, sign out completely or use a private window. |
| `401 invalid_client` when minting a token | A trailing newline in the client secret | Pipe the secret with `printf %s` — never `echo`, and never from a file that ends in a newline. |
| `400` naming an extra or forbidden field | You sent a routing field such as `topic` or `tenant_id`, or a payload key outside the declared schema | Remove it. The refusal is deliberate: callers submit workflows, not routing instructions. |
| A route returns `401` and you cannot tell whether it exists | Authentication is refused ahead of routing | Read `GET /openapi.json`. It is unauthenticated, and it is the authoritative route list. |
| Status stuck on `accepted` or `published` for minutes | Slow execution, or something stuck upstream | Wait a little longer, then report it with the `workflow_id`. |
| `409` on the receipt, or an empty result | The workflow is not terminal yet | Poll status until `completed` or `failed`, then re-fetch. |
| Receipt returns two identical hashes | The receipt's integrity claim is not intact | Do not accept it as proof. Report it with the `workflow_id`. |

---

## Handing the whole flow to a coding agent

The loop above is small enough to delegate. If you do, set the credential in the environment first and instruct the agent not to print it:

```bash
export ONEX_API_KEY="onxk_..."
export ONEX_API_BASE="https://api.omninode.ai"
```

Then ask it to: confirm `GET $ONEX_API_BASE/health` with no auth; confirm the credential with `GET $ONEX_API_BASE/v1/tenants` using the `x-api-key` header; submit the `delegation-inference` body from step 1 and save the `workflow_id`; poll `GET $ONEX_API_BASE/v1/workflows/<id>/status` until terminal; then fetch `GET $ONEX_API_BASE/v1/workflows/<id>/receipt?runner_identity=<a label you choose>` and report every HTTP status along the way — while never echoing the value of `$ONEX_API_KEY`.

---

## Where to go next

- [`guides/`](README.md) — the rest of the task-oriented documentation, including running the platform yourself.
- [`docs-taxonomy.md`](../docs-taxonomy.md) — what belongs in this book and what deliberately does not. OmniNode's own cloud topology is out of scope here; *connecting to it as a user*, which is this page, is in.
