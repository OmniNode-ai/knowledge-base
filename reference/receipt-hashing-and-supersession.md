---
type: reference
status: current
date: "2026-08-25"
title: "DoD Receipt Hashing, Append-Only, and Supersession"
topics: [dod-receipts, append-only, supersession, contract-hashing, occ]
refs: []
---

# DoD Receipt Hashing, Append-Only, and Supersession

> **Source**: onex_change_control `docs/standards/receipt_hashing_and_supersession.md`.
> Migrated to the knowledge base 2026-08-25 with the append-only wiring status corrected
> against the live repo (see the migration note before §3).

This document describes how DoD receipts bind to their contract, how existing
receipts are protected from rewrites, and how a receipt is corrected without
editing any merged file. It supersedes the whole-file-hash binding described in
earlier receipt-gate notes.

## 1. Per-entry contract hashing

A receipt binds to **one `dod_evidence` item**, not the whole contract file.
`omnibase_core.validation.validator_receipt_gate.compute_contract_entry_sha256`
computes a canonical hash over:

- an immutable header subset — `ticket_id` + `schema_version` only, and
- the parsed `dod_evidence` item itself (id + description + source + status +
  all `checks[]`).

The input is the parsed contract (`yaml.safe_load`) and the output is canonical
JSON (sorted keys, no whitespace), so a `yamlfmt` reflow / reindent / requote
that preserves parsed semantics yields an identical hash. Receipts record this
value in the `contract_entry_sha256` field.

**Why:** appending `dod_evidence` entry N+1 does not change the hash of entries
1..N, so prior receipts stay valid. This removes the Nth-consumer lockout where
appending one entry forced a rewrite of every prior merged receipt.

## 2. Dual-accept transition (grandfathering)

Both OCC gates (`validator_occ_merge_eligibility` and the receipt gate) accept:

| Receipt binding | Rule |
|-----------------|------|
| `contract_entry_sha256` present | Strict — must equal the recomputed per-entry hash (a forged receipt fails). Takes precedence over `contract_sha256`. |
| Legacy `contract_sha256` only, bound to THIS PR | Whole-file check — must match the current contract file hash. |
| Legacy `contract_sha256` only, a PRIOR merged PR | Grandfathered — never re-hashed against the since-grown file. |

A receipt with **neither** binding is a hard fail.

## 3. Append-only enforcement

`omnibase_core.validation.validator_occ_append_only` rejects, given the contract
at the merge base and at the PR head:

- editing an existing `dod_evidence` item (its per-entry hash changed), and
- removing an existing `dod_evidence` item.

Appending a brand-new item id is allowed; a net-new contract passes trivially.
Separately, any `M`/`D`/`R` git diff of an existing receipt file under
`drift/dod_receipts/<TICKET>/` is a violation — corrections are net-new
`.supersede.<NNNN>.yaml` add-only files.

> **2026-08-25 migration correction.** The source document described this
> validator as "invokable but advisory," pending a follow-up PR after
> `omnibase_core` 0.46.5 released and was repinned. Verified live against
> onex_change_control@main: `pyproject.toml` pins `omnibase-core>=0.46.8,<0.47.0`
> (past that threshold), and `.github/workflows/ci.yml` wires an `append-only-gate`
> job (`OCC Append-Only Gate`) that runs
> `validator_occ_append_only` on every changed ticket and exits non-zero on a
> violation. That job is listed in `STRICT_GATE_JOBS` in
> `scripts/ci/ci_summary_gate.py`, which means a failure blocks the required
> `CI Summary` context. The append-only invariant is enforced, not advisory.

## 4. Supersession / tombstones

A receipt key `<TICKET>/<EVIDENCE_ITEM>/<CHECK_TYPE>` may be corrected by
appending net-new records alongside the immutable base file:

```
drift/dod_receipts/<TICKET>/<EVIDENCE_ITEM>/<CHECK_TYPE>.yaml               # base (immutable)
drift/dod_receipts/<TICKET>/<EVIDENCE_ITEM>/<CHECK_TYPE>.supersede.<NNNN>.yaml   # append-only chain
```

The highest `NNNN` record is authoritative (`ModelReceiptSupersession`):

- **tombstone** (`tombstone: true`, no `replacement`) → the key has no active
  receipt (invalidation).
- **rebind** (`replacement:` receipt) → the key resolves to the replacement,
  which must key-match and carry a `contract_entry_sha256`.

A later record can un-tombstone a key by supplying a replacement at a higher
`NNNN`. The base file is never edited. Resolution is honored by:

- `validator_occ_merge_eligibility` and the receipt gate (via
  `validator_receipt_supersession.resolve_supersession`), and
- omnimarket `DurableEvidenceGate` (via `apply_supersessions`, ordered by
  `created_at` since payloads carry no filename), so a re-bound / invalidated PR
  citation no longer feeds the MERGED-PR check.

## 5. dod_verify dev-resolution rider

OCC governance is dev-first (contracts/receipts land on `dev`, batch to `main`
later), but the canonical clones track `main`. `EvidenceCollector` therefore
materialises an `origin/dev` worktree of the OCC repo when a contract is absent
from the working tree, and runs both the contract load and the receipt greps
inside it. An override environment variable lets the resolution target a
different ref when needed.
