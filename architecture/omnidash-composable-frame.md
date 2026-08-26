---
type: architecture
status: accepted
date: "2026-08-26"
title: "OmniDash Composable Frame Architecture"
topics: [omnidash, dashboard, widgets, component-registry, data-source, frontend]
refs: [reference/omnidash-dashboard-definition.md, reference/omnidash-component-manifest.md, guides/omnidash-development.md, architecture/omnidash-component-truth-boundary.md]
---

# OmniDash Composable Frame Architecture

**Owner:** `omnidash`
**Verification:** `npm run check && npm run test:run`

---

## Overview

OmniDash is a composable dashboard builder. It is a thin frame that discovers, mounts, and arranges self-contained widget components. The frame has no knowledge of specific domains or data pipelines — all domain knowledge lives in widget implementations.

---

## Three Layers

### Layer 1: Frame

The shell application. Responsibilities:

- Auth and navigation
- Theme switching (vanilla-extract CSS custom properties)
- Grid layout (drag, resize, snap)
- Dashboard CRUD (create, save, load, export, import)
- Edit mode / view mode toggle
- Global filter state (time range, shared Zustand context)

The frame does NOT own:

- Data fetching for any specific domain
- Component-to-component event semantics
- Widget business logic

### Layer 2: Component Registry

Discovers and resolves component manifests at startup. Sources:

1. **In-repo MVP manifests** — the `MVP_COMPONENTS` object in `scripts/generate-registry.ts`.
2. **External package manifests** — auto-scanned from any installed `@omninode/*` npm package that declares `"dashboardComponents": "./path/to/manifests.json"` in its `package.json`.

The registry generates `src/registry/component-registry.json`. This file is committed and must be regenerated via `npm run generate:registry` after any manifest change. Do not hand-edit it.

Registry resolution:

- If a manifest entry has a matching `implementationKey` in `src/components/dashboard/index.ts`, the component is loadable.
- If the manifest entry has no matching implementation, the palette shows the component with `status: 'not_implemented'`. The frame does not crash.
- If an implementation exists without a manifest entry, it is invisible to the registry and cannot be placed on dashboards.

### Layer 3: Widgets

Self-contained React components. Each widget:

- Lives under `src/components/dashboard/<widget-name>/`.
- Default-exports a React component that accepts a `config` prop matching its manifest's `configSchema`.
- Owns its own data fetching (via `useProjectionQuery` or direct fixture reads).
- Has at minimum `Empty` and `Populated` Storybook stories (enforced by the compliance test).
- Has unit tests alongside the component file.

Widget variants (2D, 3D) live in the same directory. A dispatcher component reads `config.dimension` and `config.style` and lazy-imports the matching variant. Consumers who pick 2D never load the three.js bundle.

---

## Data Flow

```
Node/contract repo (Python)         omnidash (TypeScript)
───────────────────────────         ─────────────────────
contract.yaml                       Component Registry
  → dashboard_components              → discovers manifests
    (declares what exists)            → matches implementationKey
                                      → mounts in grid cells

handlers/                           src/components/dashboard/
  → bus → DB projections              → React components
                                      → own data fetching
                                      → own event subscriptions
```

### Data Source Modes

The active data source is selected by `VITE_DATA_SOURCE`, but the canonical defaults are owned by `contract.yaml` and generated into `src/config/generated/data-source-defaults.ts` via `npm run generate:config` (env vars are optional overrides, not the source of truth). The contract default mode is `http` (`DATA_SOURCE_DEFAULT_MODE`) — the Express bridge must not hold a direct Postgres connection; reads route through the projection API instead. Local development typically sets `VITE_DATA_SOURCE=file` in `.env` to run without infrastructure.

Four modes are supported (`src/data-source/index.ts`):

| Mode | Adapter | Reads from |
|------|---------|-----------|
| `file` | `FileSnapshotSource` | `./fixtures/<topic>/` JSON snapshots — zero infra |
| `http` | `HttpSnapshotSource` | HTTP projection backend at the contract URL (a local Express bridge on port 3002 by default) |
| `sqlite` | `HttpSnapshotSource` | same HTTP read path as `http`; the sqlite distinction is server-side (`server/routes.ts` reads `delegation.sqlite`) |
| `postgres` | `HttpSnapshotSource` | same HTTP read path as `http`; the postgres distinction is server-side (Postgres projections) |

All three live modes (`http` / `sqlite` / `postgres`) read through the single `HttpSnapshotSource` HTTP projection path on the client; only `file` reads fixtures directly.

**Runtime override seam:** `src/data-source/data-source-override.ts` is the single seam that lets an operator switch the effective backend at runtime (persisted to `localStorage`, surfaced via the `DataSourceControl` chrome) without restarting. Resolution code consults `resolveEffectiveDataSource()` rather than reading `import.meta.env.VITE_DATA_SOURCE` directly, so there is exactly one place that decides the effective source.

---

## Application Pages

The composable dashboard builder is the default page, but the app shell (`src/App.tsx`) routes between several top-level pages by `activePage` in the Zustand frame store. Page arms verified in `src/App.tsx`:

- `default` → `DashboardView` (the composable builder)
- `feature-flags` → `FeatureFlagDashboard`
- `eval` → `InstructionEvalPage`
- `delegation-evidence` → `DelegationEvidencePage` (lazy)
- `event-bus` → `EventBusPage` (lazy)
- `experiments` → `ExperimentsPage` (lazy)
- `sea-control` → `SeaControlPage` (lazy)

Additional pages exist under `src/pages/` (e.g. `TraceExplorerPage`, `SessionReplayPage`, `SandboxMonitorPage`, `VoiceSessionPage`). The shell also mounts `AgentOrchestrator` (`src/agent/`), the conversational dashboard-builder agent, and a `CommandPalette`. All page data access flows through the same `src/data-source/` adapters and `src/services/` route seam.

---

## Component Contract Truth Boundary

The contract (declared in the owning node repository's `metadata.yaml`) is the coupling surface between backend and frontend.

**The contract declares:**

- The existence and data bindings of a dashboard component.
- What topics, tables, and API endpoints the component needs.
- What events the component emits and consumes.
- The component's `configSchema` (what settings it accepts).

**The contract does NOT deliver:**

- React source code. Frontend implementations live in omnidash under `src/components/dashboard/`.
- Runtime component instances. The frame's registry resolves contract declarations to local React implementations at startup.

**Consequences:**

- Redesigning a component (visual change only): edit TypeScript in omnidash. Backend untouched.
- Changing data shape: update the contract + handler in the owning node repository, update the component in omnidash.
- Adding a new component: declare it in the contract, implement it in omnidash. The registry picks it up on the next `npm run generate:registry`.

---

## Cross-Component Communication

Components communicate via three channels:

| Channel | Purpose | When to use |
|---------|---------|-------------|
| Zustand shared context (`src/store/`) | Frame-level UI state: time range, global filters, edit mode | Lightweight shared state that the frame manages |
| `mitt` event bus | Component-to-component coordination: selection, drill-down, highlight | Interactions that do not require backend round-trips |
| HTTP projection polling (`useProjectionQuery`) | Domain events with backend significance | Data updates, live metrics, workflow events — poll-driven, no WebSocket |

The frame does not mediate component-to-component communication. Components subscribe directly to the mitt bus and poll the projection backend via `useProjectionQuery`.

**WebSocket removed:** The `/ws` path was permanently deleted. The deployed projection backend never registered a `/ws` route; the browser's upgrade request was rejected with 403 and no events were delivered. Raw browser WebSocket construction is blocked by the `local/no-projection-websocket` ESLint rule.

**Route seam:** All `/api/` path literals in fetch and axios calls belong in `src/services/` or `src/data-source/`. This is a **convention, not an enforced ESLint rule** — there is no `local/no-api-literal` rule at HEAD, despite stale source comments that cite one. The rules actually registered in `eslint.config.js` are `local/no-typography-inline`, `local/no-projection-websocket`, and `local/no-untyped-empty-state`.

---

## Dashboard Definition Schema

A saved dashboard is a `DashboardDefinition` JSON document (see `shared/types/dashboard.ts`):

```
DashboardDefinition
  id                  UUID
  schemaVersion       "1.0"
  name                string
  layout              DashboardLayoutItem[]
    i                 UUID (grid item key)
    componentName     string (registry key)
    componentVersion  string (semver)
    x, y, w, h        number (grid coordinates)
    config            Record<string,unknown> (validated against configSchema)
  globalFilters       optional time range
  createdAt / updatedAt / author / shared
```

Dashboard definitions are serializable JSON — exportable, importable, versionable. Config validation against `configSchema` happens on load; invalid configs are rejected with a diagnostic.

---

## Ownership Summary

| Concern | Owner |
|---------|-------|
| Frame shell, grid, CRUD | `omnidash` |
| Component registry generation | `omnidash` (`scripts/generate-registry.ts`) |
| Widget React implementations | `omnidash` (`src/components/dashboard/`) |
| Dashboard definition schema | `omnidash` (`shared/types/dashboard.ts`) |
| Component manifest schema | `omnidash` (`shared/types/component-manifest.ts`) |
| Contract declarations (what components exist) | the owning node repository (`metadata.yaml`) |
| Business logic, event handlers, DB projections | the owning node repository |
| Infrastructure (broker, Postgres, cache) | the platform infrastructure repository |

---

## Related

- [`reference/omnidash-dashboard-definition.md`](../reference/omnidash-dashboard-definition.md)
- [`reference/omnidash-component-manifest.md`](../reference/omnidash-component-manifest.md)
- [`guides/omnidash-development.md`](../guides/omnidash-development.md)
- [`architecture/omnidash-component-truth-boundary.md`](omnidash-component-truth-boundary.md)
