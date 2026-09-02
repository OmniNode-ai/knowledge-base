---
type: reference
status: current
date: "2026-08-26"
title: "OmniDash Implementation Status"
topics: [omnidash, widgets, data-sources, implementation-status]
refs: [reference/omnidash-component-manifest.md, reference/omnidash-dashboard-definition.md, architecture/omnidash-composable-frame.md]
---

<!-- Migrated from omnidash:docs/implementation-status.md on 2026-09-01 -->

# OmniDash — Implementation Status

**Owner:** `omnidash`
**Last verified:** 2026-08-26 (default-mode + dead DashboardBuilder.tsx reference corrected against live `contract.yaml`/`src/App.tsx`/`src/pages/`)
**Verification:** `npm run check && npm run test:run`

This document summarizes which parts of the OmniDash composable dashboard are implemented. A new developer should be able to start with this page and reach working code without opening the phased plan files.

---

## Summary

All four implementation parts are complete. The application runs, type-checks, and tests pass.

| Part | Description | Status |
|------|-------------|--------|
| 1 | Frame, theme system, Zustand store, query provider | Done |
| 2 | Component registry, dashboard builder, CRUD service | Done |
| 3 | MVP widget set, templates, proof of life | Done |
| 4 | Conversational dashboard builder | Done |

---

## Part 1: Frame, Theme System, Store, Query Provider

**What was built:**

- Vite + React 19 SPA with TypeScript, vanilla-extract, TailwindCSS.
- Four-mode data source system controlled by `VITE_DATA_SOURCE` env var (defaults generated from `contract.yaml` via `npm run generate:config`):
  - `http` (default, `contract.yaml`, flipped from `postgres`): reads via the projection backend at `localhost:3002`.
  - `file`: reads JSON snapshots from `./fixtures/`. Zero infra required — the override to use for local dev without a running backend.
  - `sqlite`: reads via the projection backend (resolves through `HttpSnapshotSource`).
  - `postgres`: reads via the projection backend (resolves through `HttpSnapshotSource`).
- Runtime data-source override: the `DataSourceControl` chrome component lets an operator switch the active backend at runtime without restarting. `src/data-source/data-source-override.ts` is the single seam — components must never read `VITE_DATA_SOURCE` directly.
- Zustand store with slices for edit mode, layout state, and global filters.
- TanStack Query provider for data fetching.
- Typography token system: all widget text goes through `<Text>` / `<Heading>` from `src/components/ui/typography`. ESLint rule `local/no-typography-inline` enforces this.
- Theme tokens in `src/styles/globals.css :root`.

**Key files:**

- `src/data-source/` — `FileSnapshotSource`, `HttpSnapshotSource`, `ProtocolSnapshotSource`
- `src/store/` — Zustand slices (edit mode, layout, filters)
- `src/components/ui/typography.tsx` — `<Text>`, `<Heading>` components
- `src/styles/globals.css` — CSS custom property tokens

---

## Part 2: Component Registry, Dashboard Builder, CRUD Service

**What was built:**

- Component registry that discovers manifests from two sources:
  1. `MVP_COMPONENTS` in `scripts/generate-registry.ts` (in-repo widgets).
  2. Auto-scanned `@omninode/*` npm packages that declare `"dashboardComponents"` in their `package.json`.
- `src/registry/component-registry.json` — generated output (committed, do not hand-edit).
- Dashboard builder UI: palette of available components, drag-and-drop grid, per-widget config panel.
- CRUD service: create, save, load, delete, export, import dashboards as `DashboardDefinition` JSON.
- Layout persistence to `./dashboard-layouts/` (gitignored, local only).

**Key files:**

- `scripts/generate-registry.ts` — registry source of truth
- `src/registry/component-registry.json` — generated registry
- `src/components/dashboard/ComponentPalette.tsx` — widget palette
- `src/components/dashboard/DashboardGrid.tsx` — grid layout
- `src/layout/layout-persistence.ts` — layout save/load
- `shared/types/dashboard.ts` — `DashboardDefinition`, `DashboardLayoutItem`
- `shared/types/component-manifest.ts` — `ComponentManifest`

---

## Part 3: Widget Set, Templates, Proof of Life

**What was built:**

- Approximately 30 widget directories under `src/components/dashboard/`, each following the per-widget directory layout. Current directories include (verified 2026-06-16):
  - `ab-compare/` — A/B comparison panel
  - `baselines/` — baselines ROI card (bespoke; see ADR-003)
  - `command-dispatch/` — command dispatch panel
  - `context-heatmap/` — context usage heatmap
  - `control-plane/` — control plane status
  - `cost-by-model/` — cost breakdown by model
  - `cost-by-repo/` — cost breakdown by repository
  - `cost-savings-overview/` — cost savings summary
  - `cost-summary/` — cost summary view
  - `cost-trend/` — 2D (ECharts) and 3D (three.js) stacked cost chart
  - `delegation/` — delegation metrics
  - `delegation-control-plane/` — delegation control plane
  - `dep-health/` — dependency health status
  - `event-dash/` — event dashboard views
  - `events/` — event list
  - `evidence-pipeline/` — evidence pipeline status
  - `instruction-eval/` — instruction evaluation
  - `intent-distribution/` — intent distribution chart
  - `live-events/` — live event feed
  - `mcp-tools/` — MCP tools panel
  - `projection-container/` — generic projection container
  - `quality/` — aggregated quality score display
  - `readiness/` — readiness indicators
  - `receipt-gate/` — receipt gate status
  - `routing/` — routing overview
  - `routing-decision/` — routing decision detail
  - `session-timeline/` — session timeline
  - `swarm-control-plane/` — swarm control plane
  - `token-usage/` — token usage breakdown
  - `trace-explorer/` — execution trace explorer

  Note: `activity-heatmap/`, `health-monitor/`, `execution-graph/`, and `node-registry/` are **no longer present** in `src/components/dashboard/`.

- Storybook stories for all widgets (at minimum `Empty` and `Populated` exports).
- Compliance test `src/storybook-coverage-compliance.test.ts` that enforces story coverage on every `npm test`.
- Dashboard templates for common observability layouts.

**Key files:**

- `src/components/dashboard/<widget-name>/` — all widget implementations
- `src/components/dashboard/index.ts` — lazy-import map
- `src/storybook/fixtures/` — shared Storybook fixture data
- `src/storybook-coverage-compliance.test.ts` — Storybook compliance enforcement

---

## Part 4: Conversational Dashboard Builder

**What was built:**

- Conversational builder interface for generating and modifying dashboards via natural language.
- `page-agent` integration for AI-driven dashboard composition.
- XYFlow-based canvas for visualizing proposed dashboard layouts before applying them.
- Config generation from natural language instructions validated against each widget's `configSchema`.

**Key files:**

- `src/pages/DashboardView.tsx` — the composable builder page (`activePage` default arm in `src/App.tsx`); there is no separate `DashboardBuilder.tsx`
- `src/agent/AgentOrchestrator.tsx`, `src/agent/usePageAgent.ts` — conversational agent orchestration, mounted from `src/App.tsx`
- `@xyflow/react` — canvas for layout visualization

---

## Known Gaps and Follow-On Work

| Gap | Notes |
|-----|-------|
| External package dynamic code loading | External `@omninode/*` widgets surface in palette with `status: 'not_implemented'` unless their `implementationKey` is also in the local `componentImports` map. Full dynamic loading is a future phase. |
| Auth integration | Auth stubs are present but the frame does not yet connect to the ONEX auth service. |
| Live data updates | Live updates are poll-driven via `useProjectionQuery`. The `/ws` WebSocket path was permanently removed after it was rejected with 403 by the projection backend and never delivered events. Raw browser WebSocket construction is blocked by the `local/no-projection-websocket` ESLint rule. |
