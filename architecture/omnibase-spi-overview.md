---
type: architecture
status: accepted
date: "2026-09-01"
title: "omnibase_spi Architecture Overview"
topics:
  - omnibase_spi
  - architecture
  - protocols
refs: []
---

<!-- Migrated from omnibase_spi:docs/architecture/README.md on 2026-09-01 -->

# Architecture

`omnibase_spi` is the ONEX service provider interface layer. It describes
behavioral contracts that implementation repos satisfy, while relying on
`omnibase_core` for shared data shapes.

## Principles

1. Protocols describe boundaries; they do not implement behavior.
2. Protocol signatures may use Core models and types.
3. Core must remain independent of SPI.
4. SPI must remain independent of implementation packages.
5. Public protocol files should be runtime-checkable and type-checkable.
6. Wire-format contracts in `src/omnibase_spi/contracts/` are narrow exceptions
   for cross-boundary payloads; they are not a license to move general domain
   models into SPI.

## Import Graph

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

The graph is intentionally different from the common expectation that an SPI
package must sit below every model package. In this workspace, Core is the
model/type authority and SPI is the protocol boundary authority.

See [Dependency Direction](omnibase-spi-dependency-direction.md) for allowed and forbidden
imports.

## Repo Contents

- `src/omnibase_spi/protocols/`: 232 `protocol_*.py` files across 39 protocol
  domains such as event bus, handlers, runtime, registry, storage, MCP, workflow
  orchestration, validation, and dashboard surfaces.
- `src/omnibase_spi/contracts/`: selected frozen wire contracts used across repo
  boundaries (subdomains: database, defaults, delegation, enrichment, events,
  measurement, pipeline, projections, services, shared, source_control,
  validation).
- `src/omnibase_spi/exceptions.py`: SPI exception hierarchy rooted at `SPIError`.
- `src/omnibase_spi/exceptions_skill_routing.py`: skill-routing SPI exceptions.
- `src/omnibase_spi/effects/`: effect-related public SPI helpers.
- `src/omnibase_spi/enums/`: SPI-local enums.
- `src/omnibase_spi/factories/`: factory helpers.
- `src/omnibase_spi/registry/`: lightweight registry utilities that remain free
  of implementation package dependencies.
- `scripts/validation/`: repo-local validation scripts for naming, namespace
  isolation, protocol shape, empty directories, and SPI typing patterns.

> Verified against code on this refresh: top-level package layout and the
> 232-file / 39-domain protocol count under `src/omnibase_spi/protocols/`.

## Protocol Shape

Public protocols should:

- inherit from `typing.Protocol`;
- include `@runtime_checkable`;
- use `...` for method and property bodies;
- keep one primary public protocol per `protocol_*.py` file when practical;
- use Core models/types only for canonical shared data shapes;
- avoid concrete service construction, I/O, persistence, or runtime state.

## Related Docs

- `Docs index` (in the omnibase_spi repository)
- `API Reference` (in the omnibase_spi repository)
- [Developer Guide](../guides/omnibase-spi-developer-guide.md)
- [Testing Guide](../guides/omnibase-spi-testing.md)
- [Glossary](../reference/omnibase-spi-glossary.md)
