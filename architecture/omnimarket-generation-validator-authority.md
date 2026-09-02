---
type: architecture
status: accepted
date: "2026-09-01"
title: "OmniMarket Generation Validator Authority"
topics:
  - omnimarket
  - generation
  - validation
refs: []
---

<!-- Migrated from omnimarket:docs/migrations/sea-generation-validator-authority.md on 2026-09-01 -->

# SEA Generation: Canonical Validator Authority Boundary

This document names the single canonical validator authority that
`node_generation_consumer` invokes when validating generated ONEX node packages,
and records the invocation path. It is the Phase 1 gate output for the SEA ->
canonical migration: the validator authority must be named before the
model-class-name check is ported into it.

`node_generation_consumer` **invokes** canonical validators; it does **not**
become the long-term owner of validation logic. Validation logic lives in the
validator platform (aligns with validator-standardization). This boundary keeps
the generation node a thin coordinator and the validator platform the single
authoritative home for reusable checks.

## Canonical validator authority

**Authority:** the **omnibase_core validation platform**, package
`omnibase_core.validation`.

| Authority surface | File-path citation |
| --- | --- |
| Validator platform package (the authority) | `omnibase_core/src/omnibase_core/validation/__init__.py` |
| Unified suite facade | `ServiceValidationSuite` -- `omnibase_core/src/omnibase_core/services/service_validation_suite.py` |
| Contract-validation engine (model-level checks) | `ValidatorContractLinter` -- `omnibase_core/src/omnibase_core/validation/validator_contract_linter.py` |
| Directory-level contract validation function | `validate_contracts_directory` -- `omnibase_core/src/omnibase_core/validation/validator_contracts.py` |
| Shared base for all platform validators | `ValidatorBase` -- `omnibase_core/src/omnibase_core/validation/validator_base.py` |

The model-class-name check (a generated node's contract must reference a model
class that exists in the declared model namespace) is a **contract-level** check.
Its canonical home is `ValidatorContractLinter`, which already owns the
contract-level model checks -- see `_validate_model_prefix`
(`validator_contract_linter.py`), the existing check that the `input_model` /
`output_model` declared in a contract follow the `Model*` convention. The
model-class-existence check is added alongside it in the same contract linter
(Phase 1.1), not in `node_generation_consumer`.

## The authority is wired (not just present)

The validator platform is enforced as a gate, not advisory detection:

- **CLI surface.** `onex validate` routes into the platform facade
  `ServiceValidationSuite` -- `omnibase_core/src/omnibase_core/cli/cli_commands.py`
  (`from omnibase_core.validation.validator_cli import ServiceValidationSuite`,
  `suite = ServiceValidationSuite()`). The module is runnable as
  `python -m omnibase_core.validation`.
- **Pre-commit.** Contract validation is a pre-commit hook:
  `validate-contracts` (`ONEX Contract Validation`) in
  `omnibase_core/.pre-commit-config.yaml`, which scans `contract.yaml` files.
  Additional platform validators run as pre-commit hooks from the same package
  (`python -m omnibase_core.validation.checker_naming_convention`,
  `... .validator_requirements_consumer`, `... .validator_rollup_coverage`).
- **CI.** Platform validators run as required CI gates, e.g.
  `omnibase_core/.github/workflows/check-handshake.yml`
  (`python -m omnibase_core.validation.validator_requirements_consumer`,
  `... .validator_rollup_coverage`) and the cross-repo / DB validation workflows
  under `omnibase_core/.github/workflows/`.

## Invocation path -- how `node_generation_consumer` calls the authority

Generation lives in
`omnimarket/src/omnimarket/nodes/node_generation_consumer/`. The contract /
schema validation step today is the in-handler `_validate_generation`
(`handlers/handler_generation_consumer.py`), invoked from the generation attempt
loop. It currently calls three local helpers -- `_check_contract_schema`,
`_check_handler_syntax`, `_check_handler_security` -- and the semantic checks in
`semantic_validation.py`. None of these invoke the canonical validator platform
yet; the contract-level checks are still bespoke and node-local.

Target invocation path (the boundary this gate establishes; built in Phase 1.1):

1. The generation attempt loop in `handler_generation_consumer.py` produces a
   candidate `contract.yaml` for the generated node.
2. `_validate_generation` invokes the canonical authority on that candidate
   contract -- `ValidatorContractLinter` (directly, or via
   `validate_contracts_directory` / `ServiceValidationSuite`) from
   `omnibase_core.validation`.
3. The contract linter returns typed `ModelValidationIssue` results
   (`omnibase_core.validation`); the generation node maps platform failures into
   its `errors` / `checks_passed` verdict and retries or terminates per its
   contract's retry budget.
4. The model-class-name check is one of the platform checks returned in step 3.
   It is added to `ValidatorContractLinter` (Phase 1.1) -- never re-implemented in
   `node_generation_consumer`.

This keeps the validator platform the single authority: `node_generation_consumer`
is a caller of `omnibase_core.validation`, and reusable checks (including the
model-class-name check) live in the contract linter, where the existing
contract-level model checks already live.

## Gate status

- Validator authority named with file-path citation: **yes** (table above).
- Invocation path documented: **yes** (section above).
- No new validator platform logic created here: **correct** -- this is a name-only
  gate. The model-class-name check is added to `ValidatorContractLinter` in
  Phase 1.1, not in this change.
