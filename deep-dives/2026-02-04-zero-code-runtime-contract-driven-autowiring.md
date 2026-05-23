---
type: deep-dive
status: public-curated
date: 2026-02-04
title: "Zero-Code Runtime: Contract-Driven Handler Discovery and Dependency Injection"
period: "2026-01-28 to 2026-02-05"
topics:
  - runtime
  - contracts
  - dependency-injection
  - plugin-architecture
  - auto-wiring
refs:
  - adr/ADR-004-contract-first-definitions.md
  - doctrine/11-ingestion-interpretation-boundary.md
---

# 2026-02-04: Zero-Code Runtime — Contract-Driven Handler Discovery and Dependency Injection

## Summary

The ONEX runtime crossed a foundational threshold: handlers could be discovered, loaded, and wired into the event bus without any changes to the runtime kernel code. A node package published to a package registry with a correctly structured contract YAML and an entry point declaration became available to the runtime automatically on next startup. This was not just an operational convenience — it changed the architectural model from a centrally-managed registry of known handlers to a contract-governed plugin surface where the runtime kernel and individual node packages are developed and deployed independently.

## Core Work

The zero-code runtime milestone built on two components that landed within days of each other:

**Runtime dependency injection for zero-code nodes.** The `RuntimeHostProcess` startup sequence was extended to integrate a `ContractDependencyResolver` that reads contract YAML files from installed packages, extracts their declared dependencies (subscribed topics, published topics, required services), and constructs a dependency graph. The resolver then invokes the dependency injection container to satisfy each handler's declared requirements before registering it with the event bus.

**Contract-driven auto-discovery via entry points.** The Python package entry point mechanism (`onex.nodes` entry point group) was adopted as the discovery surface. An installed package declares its handlers in `pyproject.toml` under `[project.entry-points."onex.nodes"]`. The runtime kernel iterates this entry point group at startup and loads each declared handler without any prior knowledge of the package's existence.

The resulting capability: `pip install onex-weather` (a hypothetical node package declaring a weather forecast handler) registers that handler with the event bus, subscribes it to the configured topics, and injects its declared dependencies — all without any change to the runtime kernel.

## Architectural Pressure

Prior to this milestone, adding a new handler required modifying the runtime kernel directly — editing a list of known handlers, updating wiring configuration, or changing startup code. As the number of nodes in the platform grew, this created several pressures:

**The kernel became a coordination bottleneck.** Every new capability required a PR to the runtime kernel repository. Kernel changes required full integration testing. The deployment cycle for a new handler was gated on kernel deployment.

**Hardcoded handler lists accumulated drift.** Lists of known handlers in the kernel fell out of sync with actually installed packages. Some handlers were listed but not installed; others were installed but not listed. The mismatch produced silent failures — missing handlers generated no error, just an absence of expected behavior.

**Cross-team coordination friction.** Teams working on specialized node packages could not deploy independently. Every node addition required coordination with whoever owned the kernel deployment.

The contract-driven auto-wiring model eliminated all three pressures by making the contract YAML the single source of truth for what a node is, what it consumes, and what it produces.

## Discoveries

**Entry points as a discovery boundary.** Python's entry point mechanism provided exactly the right level of indirection: it is installation-scoped (only installed packages are discovered), structured (the entry point group name creates a namespace), and does not require the kernel to know about packages in advance. This discovery model was already established by the Python ecosystem and required no custom infrastructure.

**Contract YAML as the kernel's only interface to node packages.** The kernel reads contract YAML; it does not import handler code directly at discovery time. Handler code is only loaded when the kernel resolves the entry point and instantiates the handler. This late binding means contract validation can happen before any handler code runs, and malformed contracts fail at startup rather than at runtime.

**Namespace package discovery has a subtle failure mode.** During rollout, packages structured as `pkgutil`-style namespace packages were silently skipped by the contract auto-discovery because the entry point resolver expected regular packages. No error was emitted — the handlers simply did not load. This failure mode (silent absence rather than explicit error) was particularly difficult to diagnose. The fix required adding a boot-time gate that asserted each discovered entry point had a corresponding subscribed topic with at least one registered handler.

**The dependency injection model required explicit handler declaration.** Early iterations assumed the DI container could infer handler dependencies from type annotations alone. This worked for simple cases but broke for handlers that required multiple services of the same type (e.g., two different database tables). Explicit dependency declaration in contract YAML — listing each required service by name — resolved the ambiguity and made the wiring auditable.

## Decisions Made

**Contract YAML is the kernel's complete interface to node behavior.** The kernel does not read handler source code or import handler modules to determine topics, dependencies, or capabilities. Everything the kernel needs to wire a handler is in the contract YAML. This boundary is enforced by a lint rule that rejects any kernel code that imports handler modules at discovery time.

**Entry point group `onex.nodes` is the discovery surface.** Any installed package that declares entries under this group participates in auto-discovery. Packages that do not declare entry points are invisible to the runtime. There is no secondary registration mechanism.

**Boot-time invariant: every subscribed topic must have a handler.** The startup sequence fails hard if a handler declares a subscribed topic in its contract but no handler is registered for that topic after the full discovery cycle. This converts the silent-absence failure mode into a loud boot failure.

**Contract-declared capabilities replace hardcoded node lists.** The list of known capabilities in the runtime is derived from installed package contracts at startup, not maintained as a static list. This list changes when packages are installed or removed.

## Candidate ADRs

- Contract YAML as the exclusive interface between the runtime kernel and node packages
- Entry point groups as the discovery surface for runtime-loadable components
- Boot-time invariant enforcement: all declared topic subscriptions must resolve to registered handlers

## Candidate Pivots

This milestone represents a foundational platform pivot: from a kernel-centric model where the kernel owns all handler registrations, to a plugin model where the kernel provides infrastructure and handlers are independently developed, packaged, and deployed. The kernel shrinks; the contract surface expands.

## Related Doctrine

- **Section 4 (Contract-First Definitions):** This milestone is the runtime expression of contract-first doctrine. The contract YAML is not documentation of what a node does — it is the specification that the runtime uses to wire the node. Documentation and wiring use the same artifact.
- **Section 11 (Ingestion vs. Interpretation Boundary):** The kernel is pure ingestion infrastructure: discover, load, wire, route. It does not interpret what handlers do. Interpretation belongs in the handlers themselves. The contract-driven model enforces this boundary structurally.

## Related Evidence

- Integration tests for event ledger runtime wiring verify that the full discovery-to-dispatch path works end-to-end
- Namespace package discovery fix confirmed by registering handlers from previously-invisible packages

## Open Questions

- What is the correct behavior when a handler's contract declares a dependency that the DI container cannot satisfy? Fail at startup (hard) or skip the handler (soft)? The current implementation fails hard, which protects against silent partial wiring but may be too strict for optional capabilities.
- Should contract YAML validation happen before or after entry point loading? Current: after. Earlier validation would catch malformed contracts before any handler code is touched.

## Follow-up Work

- Extend the boot-time invariant to cover published topics: if a contract declares a published topic, verify that some downstream handler subscribes to it
- Add a dry-run mode to the discovery sequence that reports what would be loaded without starting the event bus
- Document the entry point group naming convention for third-party node package authors
