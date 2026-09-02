---
type: reference
status: current
date: "2026-09-02"
title: "ADR-009: LLM Cost Tracking at the Infrastructure Layer"
topics: [omnibase-infra, adr, llm, cost]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-009-llm-cost-tracking-spi.md on 2026-09-02. -->

# ADR-009: LLM Cost Tracking at the Infrastructure Layer

## Status

Accepted

## Date

2026-02-19

## Context

The ONEX platform added LLM inference infrastructure in 0.8.0 with
`HandlerLlmOpenaiCompatible` and `HandlerLlmOllama` for calling local
vLLM and Ollama-compatible servers. These handlers perform chat completions
and embedding requests against the distributed multi-server LLM topology
(Qwen3-Coder on RTX 5090, Qwen3-14B on RTX 4090, Qwen3-Embedding and
DeepSeek-R1 on the M2 Ultra).

Once LLM calls were flowing, two questions became pressing:

**How much do LLM calls cost?** The platform uses local models with zero
per-token API fees, but token consumption still maps to hardware cost,
latency, and context-window utilization. For cloud fallback paths
(e.g., Claude Opus via Anthropic API), real USD costs accrue. Without
per-call accounting, there is no way to compare agent strategies, detect
regressions, or enforce budgets.

**Where should cost tracking live?** Two alternatives were considered:

1. **In the domain layer** (omniintelligence, each service individually).
   Each caller implements its own token extraction and cost formula. Result:
   N implementations, N schemas, no cross-service aggregation.

2. **In the infrastructure layer** (omnibase_infra), as a protocol in the
   SPI (omnibase-spi). All LLM handlers emit a standardized event after
   each call; a single aggregation service consumes those events and
   persists them. Result: one implementation, one schema, cross-service
   aggregation by design.

The infrastructure layer was chosen because cost tracking is a
cross-cutting infrastructure concern, not a business logic concern. The
same argument applies to why circuit breakers, correlation IDs, and error
taxonomy live in omnibase_infra rather than being re-implemented per service.

Work was delivered as part of the 0.8.0 release.

## Decision

**LLM cost tracking is a first-class infrastructure concern defined by SPI
protocol contracts (omnibase-spi 0.9.0) and implemented in omnibase_infra
0.8.0.**

### SPI 0.9.0 protocol contracts

Two protocols are defined in omnibase-spi 0.9.0 and adapted in omnibase_infra:

| Protocol | Purpose |
|----------|---------|
| `ProtocolLlmCostTracker` | Record per-call token usage and estimated cost |
| `ProtocolLlmPricingTable` | Look up per-token costs by model identifier |

The adapter classes implementing these protocols are in
`src/omnibase_infra/adapters/` and wired through `ModelONEXContainer` via
the standard DI registry pattern.

### Token usage extraction

LLM API responses do not have a uniform schema for token counts. The OpenAI
wire format uses `usage.prompt_tokens` and `usage.completion_tokens`. Ollama
uses `prompt_eval_count` and `eval_count`. Some endpoints omit usage entirely.

`MixinLlmHttpTransport` normalizes token counts into a `usage_normalized`
object with a `source` field indicating provenance:

| Source value | Meaning |
|-------------|---------|
| `api` | Counts read directly from API response |
| `estimated` | Counts approximated (e.g., from response length) |
| `missing` | No usage data available |

The `usage_is_estimated` boolean flag is derived from this source field and
persisted alongside the raw usage object for audit purposes.

### ModelPricingTable

`ModelPricingTable` loads per-model token costs from
`src/omnibase_infra/configs/pricing_manifest.yaml`. The manifest is a YAML
file with `schema_version` and a `models` mapping:

```yaml
schema_version: "1"
models:
  claude-opus-4-6:
    input_cost_per_1k: 0.015
    output_cost_per_1k: 0.075
  qwen2.5-coder-14b:
    input_cost_per_1k: 0.0
    output_cost_per_1k: 0.0
```

Local self-hosted models carry zero cost (`input_cost_per_1k: 0.0`,
`output_cost_per_1k: 0.0`). Cloud models carry their published rates.
Unknown model identifiers return `estimated_cost_usd=None` (not zero), making
it explicit that cost data is unavailable rather than silently underreporting.

Cost formula:

```text
estimated_cost_usd =
    (prompt_tokens / 1000 * input_cost_per_1k) +
    (completion_tokens / 1000 * output_cost_per_1k)
```

The table is frozen after loading. To update pricing, deploy a new manifest
and restart the service.

### Static context token attribution

Each LLM call carries a static system prompt derived from injected ONEX
manifests (agent config, CLAUDE.md, patterns). `ServiceLlmCategoryAugmenter`
parses the static context sections and attributes token overhead to specific
categories (manifest injection, patterns, documentation). This overhead is
recorded alongside the call cost so that manifest size regressions are
detectable.

### Database schema

Migration 031 adds two tables:

#### `llm_call_metrics`

Raw append-only record of every LLM call. One row per call.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Auto-generated, idempotency key |
| `correlation_id` | UUID | Trace correlation ID from the call |
| `session_id` | UUID | Agent session identifier |
| `run_id` | text | Workflow run identifier |
| `model_id` | text | LLM model identifier |
| `prompt_tokens` | integer | Input token count |
| `completion_tokens` | integer | Output token count |
| `total_tokens` | integer | Sum of prompt + completion |
| `estimated_cost_usd` | numeric | Cost estimate in USD |
| `latency_ms` | numeric(10,2) | End-to-end call latency |
| `usage_source` | `usage_source_type` enum | `API`, `ESTIMATED`, or `MISSING` |
| `usage_is_estimated` | boolean | True when token counts were approximated |
| `usage_raw` | jsonb | Raw usage object from API response |
| `input_hash` | varchar(71) | SHA-256 of the prompt (`sha256-<64 hex>`) |
| `code_version` | varchar(64) | Code version at call time |
| `contract_version` | varchar(64) | Contract version at call time |
| `source` | varchar(255) | Reporting source identifier |
| `created_at` | timestamptz | Insert timestamp (server default) |

Conflict semantics: `ON CONFLICT (id) DO NOTHING` (idempotent append).

#### `llm_cost_aggregates`

Rolling window aggregations updated via additive upsert. Multiple rows per
event (one per dimension per window).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Auto-generated |
| `aggregation_key` | varchar(512) | Dimension key: `<prefix>:<value>` |
| `window` | `cost_aggregation_window` enum | `24h`, `7d`, or `30d` |
| `total_cost_usd` | numeric | Cumulative cost for this key + window |
| `total_tokens` | bigint | Cumulative token count |
| `call_count` | integer | Number of calls aggregated |
| `estimated_coverage_pct` | numeric(5,2) | Weighted % of calls with estimated usage |
| `updated_at` | timestamptz | Last upsert timestamp |

Conflict semantics: `ON CONFLICT (aggregation_key, window) DO UPDATE SET`
with additive accumulation. `estimated_coverage_pct` is maintained as a
running weighted average.

**Aggregation key format**: `<prefix>:<value>` where prefix is one of:
`session`, `model`, `repo`, `pattern`.

Example: a single call to `qwen2.5-coder-14b` in session `abc` on repo
`omnibase_infra` produces 9 aggregate rows: 3 dimensions × 3 windows.

### Cost aggregation service

`ServiceLlmCostAggregator` is an async Kafka consumer that:

1. Subscribes to `onex.evt.omniintelligence.llm-call-completed.v1`
2. Parses events in configurable batches
3. Writes raw records to `llm_call_metrics` (append-only)
4. Upserts aggregate rows to `llm_cost_aggregates` per dimension and window
5. Commits offsets only for successfully persisted partitions

The service uses `WriterLlmCostAggregationPostgres` which implements
`MixinAsyncCircuitBreaker` for database resilience. An in-memory bounded
LRU dedup cache (50,000 entries) prevents double-counting on consumer replay.
Aggregation write failure is non-fatal: raw metrics are preserved and
aggregates catch up on the next batch.

The service exposes an HTTP health check endpoint (`/health`, `/health/live`,
`/health/ready`) for Kubernetes probes.

### Event flow

```text
LLM handler (HandlerLlmOpenaiCompatible / HandlerLlmOllama)
  └─ normalizes token usage
  └─ estimates cost via ModelPricingTable
  └─ emits ContractLlmCallMetrics event to
       onex.evt.omniintelligence.llm-call-completed.v1

ServiceLlmCostAggregator (Kafka consumer)
  └─ writes llm_call_metrics (raw, append-only)
  └─ upserts llm_cost_aggregates (dimensions × windows)
```

## Consequences

### Positive

- **Single source of truth.** All LLM call data lands in two tables with a
  consistent schema. Cross-agent and cross-session cost comparisons are SQL
  queries.
- **No per-service implementation.** Services emit a standard event; the
  aggregation service handles persistence. Adding a new LLM handler does
  not require new cost-tracking code.
- **Replay safety.** Per-partition offset commits and the in-memory dedup
  cache ensure idempotent processing across consumer restarts and rebalances.
- **Rolling windows.** Pre-computed 24h/7d/30d aggregates support dashboard
  queries without full-table scans.
- **Protocol-based extensibility.** `ProtocolLlmPricingTable` allows swapping
  the pricing data source (YAML manifest today; a live API tomorrow) without
  changing call sites.

### Negative

- **Eventual consistency.** `llm_cost_aggregates` lags raw events by up to
  one batch window (default: configurable). Real-time cost views read raw
  `llm_call_metrics` directly.
- **In-memory dedup cache.** The 50,000-entry bounded cache is lost on
  consumer restart. A brief window after restart may double-count events
  whose offsets were not yet committed. The database-level `ON CONFLICT DO
  NOTHING` constraint on `llm_call_metrics` provides a safety net.
- **Pricing manifest is static.** To update model pricing, a new manifest
  must be deployed and the service restarted. Dynamic pricing APIs are not
  supported.
- **Unknown models report null cost.** `estimated_cost_usd=None` is explicit
  but may surprise dashboards that expect a numeric value. Consumers must
  handle null.

### Neutral

- `usage_source_type` and `cost_aggregation_window` are PostgreSQL custom
  enum types added in migration 031. Schema evolution follows the standard
  migration process.
- The `input_hash` column (`sha256-<64 hex>`, max 71 characters) provides a
  content-addressable dedup key for repeat prompts and enables prompt-level
  cost attribution.
- `omnibase-spi` version 0.9.0 is the minimum required to use
  `ProtocolLlmCostTracker` and `ProtocolLlmPricingTable`.

## References

- **Aggregation consumer**: `src/omnibase_infra/services/observability/llm_cost_aggregation/consumer.py`
- **PostgreSQL writer**: `src/omnibase_infra/services/observability/llm_cost_aggregation/writer_postgres.py`
- **Pricing table**: `src/omnibase_infra/models/pricing/model_pricing_table.py`
- **Pricing manifest**: `src/omnibase_infra/configs/pricing_manifest.yaml`
- **SPI**: omnibase-spi 0.9.0 (`ProtocolLlmCostTracker`, `ProtocolLlmPricingTable`)
