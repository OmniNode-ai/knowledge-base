---
type: architecture
status: accepted
date: "2026-09-01"
title: "omnibase_spi Dependency Direction"
topics:
  - omnibase_spi
  - architecture
  - import-graph
  - layering
refs: []
---

<!-- Migrated from omnibase_spi:docs/architecture/DEPENDENCY-DIRECTION.md on 2026-09-01 -->

# Dependency Direction

This page is the canonical public explanation of the `omnibase_spi` dependency
graph.

## Rule

```text
Application and product repos
        |
        v
omnibase_spi  ---- imports models/types ---->  omnibase_core
        ^                                      ^
        | implements protocols                 | uses models/types
        |
omnibase_infra and other implementation repos --+
```

`omnibase_spi` depends on `omnibase_core` because protocol signatures need
canonical platform models, enums, and JSON-compatible shared types. That is
intentional.

`omnibase_core` must not depend on `omnibase_spi`. Core is the model and
runtime-neutral type authority. If Core imported SPI, shared data definitions
would depend on the protocol layer that is supposed to describe consumers and
implementers.

## Why The Name Can Mislead

In many systems, an "SPI" package sits below model packages and defines every
interface without importing higher-level domain types. ONEX does not use that
shape.

In ONEX:

- Core owns canonical data shapes.
- SPI owns service and behavior boundaries.
- Infra owns concrete runtime behavior.
- Product repos consume Core data and SPI contracts.

The protocol layer is not lower than Core. It is adjacent to implementation
repos and points at Core for shared vocabulary.

## Allowed Imports

| Import | Status | Reason |
|--------|--------|--------|
| `omnibase_spi -> omnibase_core` | Allowed | Protocol signatures may reference canonical models and shared types. |
| `omnibase_infra -> omnibase_spi` | Allowed | Infra implements SPI contracts. |
| `omnibase_infra -> omnibase_core` | Allowed | Infra uses canonical models and enums. |
| Product repo -> `omnibase_spi` | Allowed | Product repos may type against protocol boundaries. |
| Product repo -> `omnibase_core` | Allowed | Product repos may use shared data shapes. |

## Forbidden Imports

| Import | Status | Reason |
|--------|--------|--------|
| `omnibase_core -> omnibase_spi` | Forbidden | Core must stay independent of protocol consumers. |
| `omnibase_spi -> omnibase_infra` | Forbidden | SPI must not depend on implementations. |
| `omnibase_spi -> product repo` | Forbidden | Protocol contracts must not depend on downstream products. |
| Protocol file -> concrete network/storage client | Forbidden | Implementations belong outside SPI. |

## Correct Protocol Addition

```python
from typing import Protocol, runtime_checkable

from omnibase_core.types import JsonType


@runtime_checkable
class ProtocolPayloadRenderer(Protocol):
    """Renders a canonical payload representation."""

    async def render(self, payload: JsonType) -> str:
        """Render the payload."""
        ...
```

This is valid because the protocol defines a boundary and uses a Core type for
the shared JSON-compatible payload shape.

## Incorrect Protocol Addition

```python
from typing import Protocol, runtime_checkable

from omnibase_infra.services.renderer import RendererService


@runtime_checkable
class ProtocolPayloadRenderer(Protocol):
    """Invalid: imports a concrete implementation."""

    async def render_with(self, renderer: RendererService) -> str:
        ...
```

This is invalid because SPI would now import from an implementation package.

## Data Model Boundary

General domain Pydantic models belong in `omnibase_core`.

The `src/omnibase_spi/contracts/` tree is reserved for narrow, data-only,
cross-boundary wire contracts. Those contracts must not import implementation
repos and should not become general application domain models.

## Validation

Use these checks before opening a PR:

```bash
python scripts/validation/validate_namespace_isolation.py
python scripts/validation/validate_spi_protocols.py
python scripts/validation/run_all_validations.py
uv run mypy src/ --strict
uv run pytest
```
