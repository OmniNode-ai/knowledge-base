---
type: adr
status: accepted
date: "2026-04-27"
title: "ADR-0028: Receipt Type Consolidation onto ModelDodReceipt"
adr_id: ADR-0028
topics: [omnibase_core, receipts, dod-evidence, schema-consolidation]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0028: Receipt Type Consolidation onto ModelDodReceipt

**Date:** 2026-04-27
**Status:** Accepted
**Source:** omnibase_core `docs/decisions/ADR-006-receipt-consolidation.md`

## Context

A scan on 2026-04-26 identified two near-duplicate receipt-shaped types that diverged
from the canonical `ModelDodReceipt`:

- `omniclaude.EvidenceReceipt` — a `@dataclass` in the DoD evidence runner with
  7 fields: `ticket_id`, `timestamp`, `git_sha`, `branch`, `working_dir`,
  `contract_path`, `result`.
- `onex_change_control.ModelVerifierCheckResult` — a Pydantic model used as items
  in `ModelVerifierOutput.checks` with fields: `name`, `passed`, `message`,
  `failure_class`.

Leaving both in place creates ongoing schema drift and forces callers to maintain
knowledge of three distinct receipt types with overlapping semantics.

## Decision

### EvidenceReceipt → ModelDodReceipt

Extend `ModelDodReceipt` with two optional fields (`branch`, `working_dir`) to
absorb the extra provenance information carried by `EvidenceReceipt`. The `result`
field is intentionally **not** migrated — it is an aggregate run summary, not a
per-check receipt. The runner constructs one `ModelDodReceipt` per evidence check
using the field mappings below:

| EvidenceReceipt field | ModelDodReceipt field |
|-----------------------|-----------------------|
| `ticket_id` | `ticket_id` |
| `timestamp` | `run_timestamp` |
| `git_sha` | `commit_sha` |
| `branch` | `branch` (new optional field) |
| `working_dir` | `working_dir` (new optional field) |
| `contract_path` | `check_value` |
| `result.details[i].checks[j].status` | `status` (mapped to `EnumReceiptStatus`) |

### ModelVerifierCheckResult → ModelDodReceipt

`ModelVerifierOutput.checks` is re-typed from `tuple[ModelVerifierCheckResult, ...]`
to `tuple[ModelDodReceipt, ...]`. The `failure_class` field on `ModelVerifierCheckResult`
is encoded in `probe_stdout` (the captured stderr/stdout of the verification command).
The `passed` field is derived from `status == PASS`.

The `ModelVerifierCheckResult` class was deleted in the downstream
onex_change_control PR (follow-up); no backwards-compat re-exports were added
per the org's no-shim policy. The omnibase_core PR only added the `branch` and
`working_dir` fields — the deletion landed in onex_change_control separately.

### Forward-compatibility with post-merge probe extension

A planned follow-up extends `ModelDodReceipt` with a required `post_merge_probe` field
(`ModelPostMergeProbe`). That field was intentionally not added here to preserve
the non-breaking nature of this PR.

## Consequences

- Single receipt type across omnibase_core, omniclaude, and onex_change_control.
- `EvidenceReceipt` dataclass deleted from omniclaude.
- `ModelVerifierCheckResult` deleted from onex_change_control.
- `ModelDodReceipt` gains two optional fields; all existing receipts remain valid
  (no migration required — both fields default to `None`).
- `ModelVerifierOutput.checks` type changed from `tuple[ModelVerifierCheckResult, ...]`
  to `tuple[ModelDodReceipt, ...]`; callers were updated.

## Verification (2026-08-20, at migration)

`src/omnibase_core/models/contracts/ticket/model_dod_receipt.py` on `omnibase_core@dev`
carries both `branch: str | None` and `working_dir: str | None` fields with the
validators described above (per the field docstring's migration note) — decision
confirmed implemented as written.
