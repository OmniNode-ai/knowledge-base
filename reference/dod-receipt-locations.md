---
type: reference
status: current
date: "2026-09-02"
title: "DoD Receipt Locations"
topics: [occ, dod-evidence, receipts, enforcement]
refs: []
---

> **Source**: onex_change_control `docs/RECEIPT_LOCATIONS.md`. Migrated to the knowledge base 2026-09-02.

# DoD Receipt Locations

> **Status:** the legacy shape below is permanently retired — hard cutoff 2026-06-01 has passed.

---

## Canonical receipt location

```
drift/dod_receipts/<TICKET>/<ITEM_ID>/<CHECK_TYPE>.yaml
```

* The leaf filename is the **check type** of the `dod_evidence` check the
  receipt answers — in practice `command.yaml`. This is not cosmetic:
  `omnibase_core.validation.validator_occ_merge_eligibility` builds the path
  as `receipts_dir / ticket_id / evidence_item_id / f"{check_type}.yaml"` and
  reads that exact filename, so a receipt under any other name is invisible to
  the gate and the PR fails `missing_receipt` with an empty `receipt_ids`
  list, even though the file is present, PASS, and correctly hash-bound
  (observed live on a real change-control PR). Earlier revisions of this document
  specified `<run_timestamp>.yaml`; that shape has never matched the resolver
  and is corrected here. The run timestamp lives in the receipt's own
  `run_timestamp` field.
* Schema: `omnibase_core.ModelDodReceipt` (one file per probe run).
* Granularity matches the `dod_evidence` items declared in the ticket
  contract — one canonical receipt directory per `dod_evidence` item.
* YAML aligns with `contracts/<TICKET>.yaml` so a reader does not need to
  swap formats mid-flow.
* Aggregation (PASS / FAIL roll-up) is computed by the gate from the per-
  receipt files. It is **not** a stored field in the receipt itself.

This is the only receipt shape the gate accepts.

---

## Legacy receipt location (retired)

```
.evidence/<TICKET>/dod_report.json
```

A single roll-up JSON that hid per-item evidence behind one `failed == 0`
boolean — deprecated 2026-04-26, and rejected outright by
`check_receipt_exists` in both `scripts/check_dod_compliance.py` and
`src/onex_change_control/handlers/handler_dod_sweep.py` since the 2026-06-01
cutoff. A ticket presenting only this shape now fails
`no receipt at <canonical> or <legacy>`; there is no reconciliation window
left to fall back into.

---

## Where this is enforced

* `scripts/check_dod_compliance.py::check_receipt_exists` — direct CLI path
  used by `pre-commit` and CI markdown summary mode.
* `src/onex_change_control/handlers/handler_dod_sweep.py::check_receipt_exists`
  — structured `ModelDodSweepResult` path used by `--json` mode and other
  programmatic consumers.

Both share the `_LEGACY_RECEIPT_CUTOFF` constant (`date(2026, 6, 1)`) and
the same logic. The handler-test `test_handler_cutoff_constant_matches_script`
asserts the constants stay in lock-step; if you change one, you change both,
or CI breaks.
