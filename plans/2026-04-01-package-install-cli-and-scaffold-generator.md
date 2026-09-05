---
type: plan
status: active
date: "2026-04-01"
title: "Package install CLI and channel-adapter scaffold generator"
topics: [cli, packaging, contracts, scaffolding]
---

# OmniClaw MVP Part 2B: Package Install CLI + Scaffold Generator

**Goal**: Build `onex install` CLI for contract package installation with security validation, and `onex scaffold-channel-adapter` for generating new adapter packages from templates.
**Architecture**: `onex install` wraps `pip install` with contract validation, provenance checks, and local registry tracking. The scaffold generator uses Jinja2 templates to emit compilable contract package skeletons.
**Tech stack**: Python 3.12+, click, importlib.metadata, Jinja2, PyYAML.
**Prerequisite**: Part 1 (the contract package pattern) must be complete.

---

## Already Completed (DO NOT re-implement)

- **Contract packages with auto-wiring**
- **Part 1**: ModelChannelEnvelope, contract package layout pattern

---

## Known Types Inventory

Types from Part 1 referenced by install/scaffold:

| Type | Location | Usage |
|------|----------|-------|
| `contract.yaml` schema | `omniintelligence/docs/architecture/contract-package-spec.md` | Install validates against this schema |
| `onex.nodes` entry point group | Defined in each package's `pyproject.toml` | Install discovers nodes via this entry point |
| Contract auto-wiring | `omniintelligence/docs/architecture/contract-package-spec.md` | Scaffold generates packages following this pattern |

---

## Task 12: Create `onex install` CLI command

Thin wrapper around `pip install` that verifies the installed package contains a valid `contract.yaml`, validates provenance, runs optional analysis, and registers the node in the local registry.

### Threat Model and Safety

The install command handles untrusted third-party packages. Security considerations:

- **Provenance / signature validation**: MVP checks for a `onex-signature` entry in package metadata (if present, validates; if absent, warns but allows install with `--allow-unsigned`). Post-MVP: enforce signature requirement for all non-dev installs.
- **No arbitrary test execution by default**: `--test` flag runs the package's golden chain test, but defaults to `--no-test` for untrusted packages. Use `--dry-run` to analyze the package without installing (inspects metadata, contract, and entry points without executing any package code).
- **Install isolation**: Packages are installed into the active virtual environment only. No system-wide installs. The install command refuses to run outside a venv.
- **Rollback behavior**: If contract validation fails after `pip install`, the command runs `pip uninstall -y <package>` and exits non-zero. The local registry is only updated after all validation passes.
- **Schema validation depth**: `contract.yaml` is validated against the contract JSON schema (not just "file exists"). Invalid contracts are rejected with specific error messages.
- **Version conflict handling**: If a package with the same `contract_name` but different version is already registered, the command warns and requires `--upgrade` flag to proceed. Without `--upgrade`, it exits non-zero.
- **Uninstall story**: `onex uninstall <package>` removes the package via pip, deregisters from the local node registry, and logs the removal. Uninstall is idempotent.
- **Update story**: `onex install <package> --upgrade` reinstalls the package, re-validates the contract, and updates the registry entry.

### Files

- **New**: `omnibase_core/src/omnibase_core/cli/cli_install.py`
- **Edit**: `omnibase_core/src/omnibase_core/cli/cli_commands.py` (register the subcommand)

### Steps (TDD)

1. **Test first**: Write `tests/unit/cli/test_cli_install.py`
   - Given a package name `omniclaw-discord-adapter`, command runs `pip install omniclaw-discord-adapter`
   - Assert: after install, command checks `entry_points("onex.nodes")` for the package
   - Assert: command verifies `contract.yaml` exists in the package's node directory
   - Assert: `contract.yaml` is validated against the contract JSON schema (not just existence check)
   - Assert: if `contract.yaml` has `event_bus_enabled: true`, command validates topic format
   - Assert: command registers the node name in the local file registry (`~/.omnibase/installed_nodes.json`)
   - Assert: if `--test` flag is passed, command runs `pytest` on the package's golden chain test
   - Assert: command exits non-zero if `contract.yaml` is missing or malformed
   - Assert: on validation failure, package is uninstalled (rollback)
   - Assert: command refuses to run outside a virtual environment
   - Assert: `--dry-run` analyzes without installing
   - Assert: version conflict without `--upgrade` exits non-zero
2. **Implement** (`cli_install.py`, ~150 LOC):
   ```python
   import subprocess
   import importlib.metadata
   import click
   import sys

   @click.command("install")
   @click.argument("package_name")
   @click.option("--test/--no-test", default=False, help="Run golden chain test after install (default: off for untrusted packages)")
   @click.option("--dry-run", is_flag=True, help="Analyze package without installing")
   @click.option("--upgrade", is_flag=True, help="Allow upgrading existing registered packages")
   @click.option("--allow-unsigned", is_flag=True, help="Allow packages without onex-signature metadata")
   def cli_install(package_name: str, test: bool, dry_run: bool, upgrade: bool, allow_unsigned: bool) -> None:
       # Step 0: Verify we're in a venv
       if sys.prefix == sys.base_prefix:
           raise click.ClickException("onex install must be run inside a virtual environment")

       # Step 1: pip install (skip for dry-run)
       if not dry_run:
           subprocess.check_call(["pip", "install", package_name])

       # Step 2: Discover entry points
       eps = importlib.metadata.entry_points(group="onex.nodes")
       matching = [ep for ep in eps if ep.dist and ep.dist.name == package_name]
       if not matching:
           click.echo(f"Warning: {package_name} has no onex.nodes entry points", err=True)

       # Step 3: Validate contract.yaml (schema validation, not just existence)
       for ep in matching:
           module = importlib.import_module(ep.module)
           contract_path = Path(module.__file__).parent / "contract.yaml"
           if not contract_path.exists():
               _rollback(package_name, dry_run)
               raise click.ClickException(f"Missing contract.yaml in {ep.module}")
           with open(contract_path) as f:
               contract = yaml.safe_load(f)
           # Validate against schema...
           click.echo(f"Validated: {contract.get('name', 'unknown')} v{contract.get('contract_version', {})}")

       # Step 4: Check version conflicts
       # ... check registry for existing entry with same contract_name ...

       # Step 5: Register
       registry_path = Path.home() / ".omnibase" / "installed_nodes.json"
       # ... append to registry ...

       # Step 6: Golden chain test (opt-in)
       if test:
           subprocess.check_call(["pytest", "-x", "-q", "--tb=short"])
   ```
3. **Register subcommand** in `cli_commands.py`
4. **Verify**: `uv run pytest tests/unit/cli/test_cli_install.py -v`

### Commit

```
feat(cli): add onex install command for contract package installation [OMN-XXXX]
```

---

## Task 14: Write channel adapter scaffold generator

Generates a new channel adapter contract package from Jinja2 templates. The command is explicitly named `scaffold-channel-adapter` (not a generic `scaffold` with a `kind` argument) because channel adapters are the only scaffold kind in MVP. If more kinds are added later, the CLI can be refactored into a group command at that point.

Adding future channels (Signal, WhatsApp, Matrix) becomes:

```bash
onex scaffold-channel-adapter --platform signal --library signalbot
```

### Template Compilation Requirement

All generated code MUST compile cleanly (`ruff check` + `mypy --strict`) even as a skeleton. Templates are designed with this constraint:
- All imports are valid (library import is behind a try/except with a clear error message)
- Type annotations are complete (no `Any` escape hatches in generated code)
- Handler stubs raise `NotImplementedError` with descriptive messages
- Test stubs use `pytest.mark.skip(reason="Scaffold stub -- implement handler first")`

### Files

- **New**: `omnibase_core/src/omnibase_core/cli/templates/channel_adapter/`
  - `contract.yaml.j2` (Jinja2 template)
  - `node.py.j2`
  - `handler_inbound.py.j2`
  - `handler_outbound.py.j2`
  - `test_handler_inbound.py.j2`
  - `__init__.py.j2`
- **New**: `omnibase_core/src/omnibase_core/cli/cli_scaffold_channel.py`
- **Edit**: `omnibase_core/src/omnibase_core/cli/cli_commands.py` (register subcommand)

### Steps (TDD)

1. **Test first**: Write `tests/unit/cli/test_cli_scaffold_channel.py`
   - Given `--platform signal --library signalbot`, scaffold generates:
     - `node_channel_signal_adapter/contract.yaml` with correct topics
     - `node_channel_signal_adapter/node.py` with thin shell
     - `node_channel_signal_adapter/handlers/handler_inbound.py` with `import signalbot` stub
     - `node_channel_signal_adapter/handlers/handler_outbound.py`
     - Test file
   - Assert topics follow naming: `onex.cmd.omniclaw.signal-outbound.v1`
   - Assert generated code passes `ruff check` and `mypy --strict`
   - Assert generated tests are valid pytest files (importable, discoverable)
2. **Implement templates** -- Jinja2 templates parameterized on `platform`, `library`, `Platform` (capitalized):
   - `contract.yaml.j2`: substitutes topic names and node name
   - `handler_inbound.py.j2`: imports the library, stubs the handler with TODO markers
   - `handler_outbound.py.j2`: stubs the outbound with library-specific send call
3. **Implement CLI** (`cli_scaffold_channel.py`, ~80 LOC):
   ```python
   @click.command("scaffold-channel-adapter")
   @click.option("--platform", required=True, help="Platform name (e.g., signal)")
   @click.option("--library", required=True, help="Python library to wrap (e.g., signalbot)")
   @click.option("--output-dir", type=click.Path(), default=".")
   def cli_scaffold_channel_adapter(platform: str, library: str, output_dir: str) -> None:
       # Load Jinja2 templates, render with platform/library, write to output_dir
       ...
   ```
4. **Verify**: `uv run pytest tests/unit/cli/test_cli_scaffold_channel.py -v`

### Commit

```
feat(cli): add channel adapter scaffold generator for OmniClaw [OMN-XXXX]
```

---

## Dependency Graph

```
Part 1 Tasks 1-6 (prerequisites -- must be complete)
  |
  +-- Task 12 (onex install CLI -- independent)
  |
  +-- Task 14 (Scaffold generator -- independent of Task 12)
```

Tasks 12 and 14 are independent and can be built in parallel.

---

routing: plan-to-tickets + epic-team
