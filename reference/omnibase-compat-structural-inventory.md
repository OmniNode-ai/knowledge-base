---
type: reference
status: current
date: "2026-08-26"
title: "omnibase_compat Structural Inventory"
topics:
  - omnibase-compat
  - dependency-boundary
  - wire-dtos
  - enums
refs: []
---

# omnibase_compat Structural Inventory

> **Last verified:** 2026-08-26, against the live `omnibase_compat` default
> branch. Every subpackage, class, and script named below was confirmed to
> exist in the package source at that commit; this page is a snapshot of a
> structure that changes, not a generator. Re-derive it from
> `src/omnibase_compat/` rather than trusting it indefinitely.

`omnibase_compat` is a structural compatibility package. It owns values and
wire shapes that must cross repository boundaries without importing OmniNode
runtime packages.

## The dependency rule

```text
Allowed runtime deps:   pydantic, typing-extensions, Python standard library
Forbidden runtime deps: omnibase_core, omnibase_spi, omnibase_infra
```

`omnibase_compat` differs from `omnibase_spi` by owning **data shapes**, not
implementation contracts:

| Layer | Owns |
|---|---|
| `omnibase_spi` | Protocols and abstract interfaces an implementation must satisfy |
| `omnibase_compat` | Shared enums, wire DTOs, event envelopes, and structural types that cross repository boundaries |

Rule of thumb: if a consumer needs a protocol that an implementation must
satisfy, the owner is `omnibase_spi`. If a consumer needs a stable enum, event
envelope, DTO, or primitive shared across repositories, the owner is
`omnibase_compat`.

## Structural surfaces

Current structural surfaces live under `src/omnibase_compat/`:

| Subpackage | Contents |
|---|---|
| `models/` | `event_envelope.py` (`EventEnvelopeV1Minimal`) and `model_project_tracker.py` (`ModelTeam`, `ModelLabel`, `ModelIssueStatus`) |
| `routing/` | Routing policy and degraded-routing event DTOs (`model_routing_policy.py`, `model_routing_degraded_event.py`) |
| `telemetry/` | Sweep result DTO (`model_sweep_result.py`, `ModelSweepResult`) |
| `overseer/` | Routing decision model (`model_routing_decision.py`, `ModelRoutingDecision` plus tier/provider/retry/risk enums) and agent scope presets (`model_agent_scope_presets.py`) |
| `registration/` | Idempotent registration helper (`decorator_idempotent_register.py`) and optional-injectable decorator (`decorator_injectable_optional.py`) |
| `concurrency/` | Synchronous coroutine bridge utility (`util_run_coro_sync.py`) |
| `env/` | Strict-mode environment helper (`util_is_strict_mode.py`) |
| `adapters/` | Protocol adapters (`adapter_project_tracker_linear.py`) |
| `metadata/` | Artifact status and transitional metadata models (`artifact_status.py`, `transitional.py`) |
| `protocols/` | Cross-repo protocol definitions: `protocol_project_tracker.py`, `protocol_projection_database.py`, `protocol_projection_database_sync.py` |
| `tooling/` | Retention-TTL check shim (`shim_ttl_check.py`) |
| `config/` | Contract/overlay config resolver (`overlay_resolver.py`) — a zero-upstream-dependency stand-in for the core runtime's `ModelRuntimeConfig` / overlay resolution |
| `learning/` | Deterministic-learning-layer wire shapes: `model_learning_record.py` (`ModelLearningRecord`, `EnumLearningOutcome`), `enum_failure_class.py` (`EnumFailureClass`), `enum_learning_process_id.py` (`EnumLearningProcessId`) |

The `types/` and `primitives/` subpackages currently hold only their
`__init__.py` placeholders; no JSON typing or primitive modules are present.

### contracts/ sub-modules

Domain-specific wire DTOs live under `src/omnibase_compat/contracts/`:

- `contracts/delegation/` — delegation runtime profile, LLM backend config,
  datastore, event bus endpoint, projection API, security, and secret-reference
  wire models.
- `contracts/evidence/` — contract evidence proof, spec, and provenance models.
- `contracts/evidence_pipeline/wire/` — evidence pipeline wire DTOs: dashboard
  events, pipeline commands, evidence bundles, correlation traces, gap reports,
  change-control PR references, raw payloads, readiness aggregates, topic
  constants, and wire types.
- `contracts/pr_occ_stamp/` — the canonical PR change-control metadata-stamp
  schema (relocated here from the core package): `ModelPrBodySection`,
  `ModelPrEvidenceSource`, `ModelPrOccMetadataStamp`,
  `ModelPrReceiptGateSkipToken`, the `EnumPrEvidenceSourceKind` discriminator,
  and the deterministic `parse_pr_occ_metadata_stamp` /
  `render_pr_occ_metadata_stamp` pair that the receipt gate and the
  change-control autobind effect both consume.
- `contracts/pricing/` — LLM pricing and pricing contract models.
- `contracts/runtime_deployment/wire/` — runtime deployment proof, request, and
  type wire models.

`contracts/delegation/wire/` (the old shim module) was deleted; import from
`contracts/delegation/` directly.

### Retention metadata

Every class-like compatibility artifact must either carry retention metadata or
an explicit retention exemption:

```python
# COMPAT_MIGRATION_TARGET: canonical.repo.module
# COMPAT_REMOVAL_DATE: YYYY-MM-DD
```

Migration truth for a compatibility shim lives in this module-level metadata —
not in a dated plan document. A dated plan is not a migration source unless it
has been promoted into a stable migration document.

## Enums

Enums live under `src/omnibase_compat/enums/`:

- `EnumExecutionStatus`
- `EnumMessageCategory`
- `EnumNodeKind`
- `EnumPrEvidenceSourceKind` — discriminator for the `contracts/pr_occ_stamp/`
  metadata-stamp schema.

Enum copies are intentionally minimal. They carry source provenance comments
and must not copy helper behavior that belongs in the core package.

## Event envelope

`EventEnvelopeV1Minimal` lives in `src/omnibase_compat/models/event_envelope.py`.

It is intentionally narrow:

- `event_id`
- `event_type`
- `payload`
- `schema_version`
- `data_provenance` (optional provenance label)

Do not add runtime tracing, source, timestamp, or helper behavior without a
versioned compatibility decision and downstream consumer evidence.

## Experimental artifact registry

Experimental artifacts register through
`src/omnibase_compat/experimental/_registry.py`. Each registered artifact must
supply:

- `name`
- `status`
- `ticket`
- `review_milestone`

The registry is local scaffolding for governance visibility. If artifacts need
cross-environment discoverability, promote the registry to file-backed or
CI-enforced metadata in a separate change.

## Validation scripts

Scripts under `scripts/` enforce the zero-upstream-dependency and structural
invariants:

| Script | Enforces |
|---|---|
| `scripts/validate_no_upstream_deps.py` | AST scan of `src/` for import statements referencing forbidden upstream packages |
| `scripts/check_compat_retention.py` | `COMPAT_MIGRATION_TARGET` / `COMPAT_REMOVAL_DATE` retention comments on all class-bearing modules |
| `scripts/check_no_infra_edge.py` | Closure scan of `pyproject.toml` and `uv.lock` for any infra/core/spi dependency edge; wired as a pre-commit hook |
| `scripts/ci/` | CI tooling: change-aware test path detection (`detect_test_paths.py`), test selection models, adjacency configuration |

## Testing and validation

Run the repository validation path before changing public compatibility
surfaces:

```bash
uv sync --dev --frozen
uv run python scripts/validate_no_upstream_deps.py
uv run python scripts/check_no_infra_edge.py
uv run python scripts/check_compat_retention.py
uv run ruff check src/
uv run mypy src/omnibase_compat --strict
uv run pytest -m unit --tb=short
uv build
```

`pyproject.toml` lists both `src/omnibase_compat/tests` and the root `tests/`
directory in `testpaths`, and both are exercised by a bare `uv run pytest`.
Passing a positional test path silently drops the other directory from
collection.

The root `tests/` directory holds `test_overseer_exports.py` (integration
export check), `tests/unit/` (event-envelope provenance, no-infra-edge, plus
nested `contracts/` and `protocols/` wire tests), and `tests/experimental/`.

Documentation validation must not add an OmniNode runtime dependency to this
package. Where link validation is needed and no standalone local entrypoint
exists, run it as CI-only tooling or from the repository that owns the
validator.

## Where compatibility decisions are recorded

There is no separate decision log for this package. Its current policy surface
is exactly:

- the dependency boundary stated in the repository README,
- this inventory,
- the retention policy in the repository's agent-context file,
- and the AST validator in `scripts/validate_no_upstream_deps.py`.

A new compatibility policy that affects multiple repositories, or that changes
the allowed dependency shape, is recorded as an ADR — see [`adrs/`](../adrs/README.md).

## Related

- [omnibase_compat release runbook](../runbooks/omnibase-compat-release.md)
- [Shared enum ownership](../architecture/shared-enum-ownership.md)
- [Event envelope field names](event-envelope-field-names.md)
- [Repository registry](repository-registry.md)
