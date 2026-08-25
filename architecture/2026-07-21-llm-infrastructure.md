---
type: architecture
status: accepted
date: "2026-07-21"
title: "LLM Infrastructure Architecture"
topics: [omnibase-infra, llm, infrastructure]
refs: []
---

# LLM Infrastructure Architecture

> **Status**: Current | **Last Updated**: 2026-02-19

The LLM infrastructure provides two ONEX Effect nodes for communicating with external language model servers: one for text embeddings and one for chat/completion inference. Both nodes share a common HTTP transport layer (`MixinLlmHttpTransport`) that enforces security boundaries, handles retries, and exposes typed error classification.

Introduced across  (transport),  (inference handler),  (embedding node),  (token usage),  (security layer).

---

## Table of Contents

1. Overview: Two Nodes, Shared Transport
2. Physical Server Topology
3. MixinLlmHttpTransport — The Shared Transport Layer
4. Security: CIDR Allowlist and HMAC Signing
5. HandlerLlmOpenaiCompatible — Inference Handler
6. HandlerEmbeddingOpenaiCompatible — Embedding Handler
7. LLM Cost Tracking
8. Error Handling and HTTP Status Mapping
9. Retry and Circuit Breaker Behavior
10. Configuration
11. Extending: Adding a New LLM Target
12. See Also

---

## Overview: Two Nodes, Shared Transport

```text
+-----------------------------+    +-------------------------------+
| node_llm_embedding_effect   |    | node_llm_inference_effect     |
| (embeddings / RAG)          |    | (chat completion / text gen)  |
+-----------------------------+    +-------------------------------+
         |                                      |
         | HandlerEmbeddingOpenaiCompatible      | HandlerLlmOpenaiCompatible
         |                                      |
         +----------------+  +------------------+
                          |  |
                          v  v
              +-------------------------------+
              |   MixinLlmHttpTransport        |
              | - CIDR allowlist check         |
              | - HMAC-SHA256 signing          |
              | - Retry loop (exponential)     |
              | - Circuit breaker              |
              | - HTTP status -> typed errors  |
              | - httpx.AsyncClient (lazy)     |
              +-------------------------------+
                          |
                    HTTP POST (JSON)
                          |
         +----------------+------------------+
         |                                   |
         v                                   v
  Embedding server                   Inference server
  :8002 (Qwen3-Embedding-8B)         :8000 (Qwen3-Coder-30B)
                                     :8001 (Qwen3-14B)
                                     :8101 (DeepSeek-R1)
```

The two nodes are structurally independent ONEX Effect nodes with their own contracts, models, registries, and handlers. They share `MixinLlmHttpTransport` as a common base.

---

## Physical Server Topology

| Endpoint Env Var | Server | Port | Model | Context | Best For |
|------------------|--------|------|-------|---------|----------|
| `LLM_CODER_URL` | `<onex-host>` (RTX 5090) | 8000 | Qwen3-Coder-30B-A3B AWQ-4bit | 64K tokens | Long-context code analysis, repo-level tasks |
| `LLM_CODER_FAST_URL` | `<onex-host>` (RTX 4090) | 8001 | Qwen3-14B-AWQ | 40K tokens | Mid-tier inference, routing classification |
| `LLM_EMBEDDING_URL` | `<onex-host>` (RTX 4090) | 8002 | Alibaba-NLP/gte-Qwen2-1.5B-instruct | — | Embeddings for RAG and semantic search |
| `LLM_DEEPSEEK_R1_URL` | `<onex-host>` (M2 Ultra) | 8101 | DeepSeek-R1-Distill-Qwen-32B-bf16 | — | Async reasoning, code review, analysis |

All endpoints are on the local-network subnet configured via `LLM_ENDPOINT_CIDR_ALLOWLIST` (default CIDR allowlist). Requests to any IP outside this range are rejected before an HTTP call is made.

---

## MixinLlmHttpTransport — The Shared Transport Layer

`MixinLlmHttpTransport` is a Python mixin that subclasses of `NodeEffect` or handler classes add to gain resilient HTTP transport to LLM endpoints. It composes `MixinAsyncCircuitBreaker` and `MixinRetryExecution`.

### Initialization

```python
class MyLlmHandler(MixinLlmHttpTransport):
    def __init__(self) -> None:
        self._init_llm_http_transport(
            target_name="my-llm-server",      # used in error context and logs
            max_timeout_seconds=120.0,         # per-call timeout upper bound
            max_retry_after_seconds=30.0,      # cap on Retry-After header values
            http_client=None,                  # None = lazy singleton; inject for testing
        )
```

The `_init_circuit_breaker` call inside `_init_llm_http_transport` uses defaults:
- threshold: 5 consecutive failures
- reset_timeout: 60 seconds
- transport_type: HTTP

Custom circuit breaker settings can be applied by calling `_init_circuit_breaker()` again after `_init_llm_http_transport()`.

### Core method: `_execute_llm_http_call`

```python
result: dict[str, JsonType] = await self._execute_llm_http_call(
    url="http://<onex-host>:8000/v1/chat/completions",
    payload={"model": "qwen3-coder", "messages": [...]},
    correlation_id=correlation_id,
    max_retries=3,          # total attempts = 1 + max_retries = 4
    timeout_seconds=30.0,   # clamped to [0.1, max_timeout_seconds]
)
```

Execution sequence per attempt:

```
1. _validate_endpoint_allowlist(url)   -- DNS resolve + CIDR check (fail-closed)
2. _compute_hmac_signature(payload)    -- HMAC-SHA256 with LOCAL_LLM_SHARED_SECRET
3. Retry loop begins
   a. _check_circuit_if_enabled()     -- raise InfraUnavailableError if circuit OPEN
   b. httpx POST with x-omn-node-signature header
   c. Check HTTP status:
      - 2xx  -> validate content-type (must contain "json") -> parse JSON -> return
      - 429  -> parse Retry-After, honor delay, retry
      - 4xx/5xx -> map to typed exception, decide retry/no-retry
   d. On success: _reset_circuit_if_enabled()
   e. On retriable error: exponential backoff -> next iteration
4. If all retries exhausted: raise InfraUnavailableError
```

### HTTP client lifecycle

The `httpx.AsyncClient` is created lazily on the first call using double-checked locking (`asyncio.Lock`). It uses:
- `timeout=httpx.Timeout(30.0)` (overridden per-call by the timeout parameter)
- `max_connections=100`, `max_keepalive_connections=20`

When a caller injects its own `http_client`, the mixin does not own that client and will not close it. When the mixin creates its own client, `_close_http_client()` closes it.

---

## Security: CIDR Allowlist and HMAC Signing

Both security checks run before the retry loop and before any HTTP call. They are fail-closed: if either check fails, the request is rejected immediately with no HTTP traffic.

### CIDR Allowlist

```
LLM_ENDPOINT_CIDR_ALLOWLIST=<your-lan-cidr>   # default; comma-separate for multiple
```

The allowlist is parsed once at **module import time** and stored as `MixinLlmHttpTransport.LOCAL_LLM_CIDRS`. This is intentional: network topology changes require a process restart, which is expected for infrastructure changes.

For each call, `_validate_endpoint_allowlist(url)` does:
1. Extract hostname from URL
2. If IP literal: check directly
3. If hostname: async DNS resolve (`getaddrinfo`) to IPv4
4. Check that the resolved IPv4 falls within at least one of `LOCAL_LLM_CIDRS`
5. IPv6 addresses are rejected unconditionally

On failure: `InfraAuthenticationError` (no retry, no circuit breaker failure).

Known limitation: there is a TOCTOU gap between DNS resolution here and httpx's own DNS resolution on the actual request. This is acceptable for a local-network trust boundary where DNS is controlled.

For testing, call `MixinLlmHttpTransport._reload_cidr_allowlist()` after modifying `LLM_ENDPOINT_CIDR_ALLOWLIST` in the environment.

### HMAC Signing

```
LOCAL_LLM_SHARED_SECRET=<shared-secret-value>
```

The HMAC secret is read from `os.environ` on **every call** (not cached), allowing hot secret rotation without a process restart.

`_compute_hmac_signature(payload, correlation_id)` computes:
- Canonical JSON of the payload: `json.dumps(payload, sort_keys=True, separators=(",", ":"))`
- `hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()`
- Signature is sent in the `x-omn-node-signature` header

On missing secret: `ProtocolConfigurationError` (no retry, no circuit breaker failure).

Known limitation: no timestamp/nonce in the signature, so there is no replay protection. Acceptable for a private LAN segment.

---

## HandlerLlmOpenaiCompatible — Inference Handler

`HandlerLlmOpenaiCompatible` translates between `ModelLlmInferenceRequest` and the OpenAI wire format. It does not inherit from `MixinLlmHttpTransport` — instead it receives a `MixinLlmHttpTransport` instance via constructor injection.

```python
# In the node's registry or setup:
transport = SomeNodeThatMixesInTransport()
handler = HandlerLlmOpenaiCompatible(transport=transport)

response: ModelLlmInferenceResponse = await handler.handle(
    request=ModelLlmInferenceRequest(
        base_url="http://<onex-host>:8000",
        model="qwen3-coder-30b",
        operation_type=EnumLlmOperationType.CHAT_COMPLETION,
        messages=[{"role": "user", "content": "Explain this code"}],
        system_prompt="You are a code reviewer",
        max_tokens=2000,
        temperature=0.1,
        timeout_seconds=60.0,
    ),
    correlation_id=correlation_id,
)
```

### Operation types and URL paths

| `operation_type` | URL path suffix |
|-----------------|-----------------|
| `CHAT_COMPLETION` | `/v1/chat/completions` |
| `COMPLETION` | `/v1/completions` |

URL is built as `{base_url.rstrip("/")}{path}`.

### Authentication (Bearer token)

When `request.api_key` is set, the handler temporarily injects a dedicated `httpx.AsyncClient` with `Authorization: Bearer {api_key}` into the transport. An `asyncio.Lock` serializes client-swap operations across concurrent calls on the same transport instance.

```python
async with auth_lock:
    # Swap transport's http_client with auth_client
    await self._transport._execute_llm_http_call(...)
    # Restore original http_client
```

This avoids mutating the transport's default client for non-auth calls.

### Tool calling

`ModelLlmToolDefinition` and `ModelLlmToolChoice` are serialized to the OpenAI wire format:

```python
# mode="function" -> {"type": "function", "function": {"name": "..."}}
# mode="auto"     -> "auto"
# mode="none"     -> "none"
# mode="required" -> "required"
```

Text and tool calls are mutually exclusive in the response (text-XOR-tool_calls invariant). When tool calls are present in the response, any `content` field is discarded.

### Response parsing

Unknown `finish_reason` values are mapped to `EnumLlmFinishReason.UNKNOWN` — no crash. An empty or malformed `choices` array returns an empty response with `finish_reason=UNKNOWN`.

---

## HandlerEmbeddingOpenaiCompatible — Embedding Handler

`HandlerEmbeddingOpenaiCompatible` directly inherits `MixinLlmHttpTransport` (unlike the inference handler which uses injection). This is because embeddings have a simpler, fixed request/response format with no auth variation.

```python
handler = HandlerEmbeddingOpenaiCompatible(target_name="qwen3-embedding")
# handler._init_llm_http_transport() called in __init__

response: ModelLlmEmbeddingResponse = await handler.execute(
    ModelLlmEmbeddingRequest(
        base_url="http://<onex-host>:8002",
        model="qwen3-embedding-8b",
        texts=("text to embed", "another text"),
        dimensions=1024,           # optional
        correlation_id=uuid4(),
        execution_id=uuid4(),
        max_retries=2,
        timeout_seconds=30.0,
    )
)

for embedding in response.embeddings:
    print(f"index={embedding.id}, vector_dim={len(embedding.vector)}")
```

Request payload:
```json
{"model": "qwen3-embedding-8b", "input": ["text1", "text2"], "dimensions": 1024}
```

Expected response:
```json
{"data": [{"index": 0, "embedding": [0.1, 0.2, ...]}, ...], "usage": {...}}
```

Each embedding item becomes a `ModelEmbedding(id=str(index), vector=[...], metadata={})`.

Usage parsing for embeddings: for embedding endpoints, `prompt_tokens` and `total_tokens` are typically the same value. If `prompt_tokens` is 0 but `total_tokens` > 0, `prompt_tokens` is set to `total_tokens` to avoid under-reporting.

The handler exposes `close()` to shut down the `httpx.AsyncClient`:
```python
await handler.close()
```

---

## LLM Cost Tracking

After each successful inference call, `HandlerLlmOpenaiCompatible` builds a `ContractLlmCallMetrics` object via `_build_usage_metrics()`. This object captures:

- `model_id`: the model identifier from the request
- `prompt_tokens`, `completion_tokens`, `total_tokens`: from the provider's usage block
- `latency_ms`: end-to-end call latency
- `usage_raw`: raw provider usage dict (preserved for auditing)
- `usage_normalized`: normalized `ModelLlmUsage` with provenance source
- `usage_is_estimated`: whether token counts were estimated (not reported by API)
- `input_hash`: SHA-256 hash of request inputs for reproducibility tracking
- `reporting_source`: `"handler-llm-openai-compatible"`

### Token normalization (5 fallback cases)

`ServiceLlmUsageNormalizer.normalize_llm_usage()` handles 5 cases for token count extraction:

1. **API-reported** — provider returned valid `usage.prompt_tokens` and `usage.completion_tokens`
2. **Total-only** — provider returned only `usage.total_tokens`; split estimated 50/50
3. **Generated-text estimation** — count tokens in generated text to estimate completion count
4. **Prompt-text estimation** — count tokens in prompt text to estimate input count
5. **Full estimation** — both prompt and completion estimated from text

When at least one case succeeds, `usage_is_estimated=False` (for API-reported) or `usage_is_estimated=True`. The `ContractEnumUsageSource` enum tracks provenance: `API`, `ESTIMATED`, or `MISSING`.

### Publishing metrics

**Handlers MUST NOT publish events directly.** The `last_call_metrics` attribute on `HandlerLlmOpenaiCompatible` is set after each call, but publishing the corresponding `llm-call-completed` event is the responsibility of the caller (node or dispatcher layer). The handler stores the metrics for the caller to pick up.

```python
response = await handler.handle(request, correlation_id)

# Caller publishes metrics separately:
if handler.last_call_metrics is not None:
    await event_bus.publish(handler.last_call_metrics.to_event())
```

Warning: `last_call_metrics` is not safe for concurrent access. When a handler instance is shared across concurrent tasks, use the return value from `response.usage` instead.

---

## Error Handling and HTTP Status Mapping

`_map_http_status_to_error` converts HTTP status codes to typed infrastructure exceptions:

| HTTP Status | Exception | Retried | CB Failure |
|-------------|-----------|---------|------------|
| 401, 403 | `InfraAuthenticationError` | No | No |
| 404 | `ProtocolConfigurationError` | No | No |
| 429 | `InfraRateLimitedError` | Yes (Retry-After) | No |
| 400, 422 | `InfraRequestRejectedError` | No | No |
| 500–504 | `InfraUnavailableError` | Yes | Yes |
| other non-2xx | `InfraUnavailableError` | Yes | Yes |
| `httpx.ConnectError` | `InfraConnectionError` (after retries) | Yes | Yes |
| `httpx.TimeoutException` | `InfraTimeoutError` (after retries) | Yes | Yes |
| bad JSON in 2xx response | `InfraProtocolError` | No | Yes |
| non-JSON content-type in 2xx | `InfraProtocolError` | No | Yes |

Response bodies in errors are passed through `sanitize_error_string()` before inclusion to prevent leakage of sensitive LLM output through error propagation.

`Retry-After` header parsing: supports delta-seconds format only. Non-finite values (NaN, Inf) and unparseable values fall back to `1.0s`. Values are clamped to `[0.0, max_retry_after_seconds]` (default cap: 30s).

---

## Retry and Circuit Breaker Behavior

### Retry loop

- **Total attempts** = `1 + max_retries` (default 3 retries = 4 total attempts)
- **Backoff**: exponential, managed by `ModelRetryState`
- **Per-attempt timeout** is fixed; not extended on retries
- 429 responses use the `Retry-After` value as the delay instead of exponential backoff

### Circuit breaker states

```
CLOSED (normal) -> OPEN (after 5 consecutive failures) -> HALF_OPEN (after 60s) -> CLOSED (on success)
```

When the circuit is OPEN, `_check_circuit_if_enabled()` raises `InfraUnavailableError` immediately, without making an HTTP call. This prevents cascading failures when a model server is down.

Auth failures (401/403) and rate limits (429) do NOT count as circuit breaker failures — they represent policy errors, not infrastructure failures.

---

## Configuration

All LLM endpoints are configured via environment variables sourced from `.env`. No hardcoded fallbacks.

```bash
# Inference endpoints
LLM_CODER_URL=http://<onex-host>:8000        # Qwen3-Coder-30B (64K context)
LLM_CODER_FAST_URL=http://<onex-host>:8001   # Qwen3-14B (40K context)
LLM_DEEPSEEK_R1_URL=http://<onex-host>:8101  # DeepSeek-R1 (reasoning)

# Embedding endpoint
LLM_EMBEDDING_URL=http://<onex-host>:8100    # gte-Qwen2-1.5B embeddings

# Security
LOCAL_LLM_SHARED_SECRET=<rotate-regularly>       # HMAC signing key
LLM_ENDPOINT_CIDR_ALLOWLIST=<your-lan-cidr>      # comma-separated CIDRs
```

### CIDR allowlist configuration details

- Parsed once at module import time
- Multiple CIDRs: comma-separated (e.g. `10.0.0.0/8,172.16.0.0/12`)
- Malformed entries are logged and skipped; if all are malformed, the allowlist falls back to the configured default CIDR
- To change at runtime without restarting: set env var, then call `MixinLlmHttpTransport._reload_cidr_allowlist()`

---

## Extending: Adding a New LLM Target

To add a new inference target (e.g., a fine-tuned model on a different port):

1. Set the URL in `.env`:
   ```bash
   LLM_MYMODEL_URL=http://<onex-host>:8100
   ```

2. Ensure the target IP is within `LLM_ENDPOINT_CIDR_ALLOWLIST`.

3. The `base_url` in `ModelLlmInferenceRequest` is per-request — no code changes are needed if the new server is OpenAI-compatible. Pass `base_url=os.environ["LLM_MYMODEL_URL"]` at call time.

4. If the server uses a different wire format, implement a new handler class that:
   - Inherits `MixinLlmHttpTransport` or accepts a transport instance
   - Calls `_execute_llm_http_call()` with the appropriate URL and payload
   - Parses the response into `ModelLlmInferenceResponse` or `ModelLlmEmbeddingResponse`

To add a new embedding target: same pattern, but use `ModelLlmEmbeddingRequest` and return `ModelLlmEmbeddingResponse`.

---

## See Also

- `src/omnibase_infra/mixins/mixin_llm_http_transport.py` — transport mixin source
- `src/omnibase_infra/nodes/node_llm_inference_effect/` — inference node
- `src/omnibase_infra/nodes/node_llm_embedding_effect/` — embedding node
- `src/omnibase_infra/adapters/llm/` — higher-level adapters (code analysis, summarization, etc.) built on top of inference
- `docs/patterns/circuit_breaker_implementation.md` — circuit breaker mechanics
- `docs/patterns/error_recovery_patterns.md` — retry and error classification
- `docs/patterns/error_handling_patterns.md` — error context and sanitization
- `~/.claude/CLAUDE.md` — server topology and LLM endpoint reference
