---
type: guide
status: current
date: "2026-08-26"
title: "OmniDash Development Guide"
topics: [omnidash, development, storybook, widgets, data-source, how-to]
refs: [architecture/omnidash-composable-frame.md, reference/omnidash-component-manifest.md, reference/omnidash-dashboard-definition.md]
---

# OmniDash Development Guide

**Owner:** `omnidash`
**Verification:** `npm run check && npm run test:run`

---

## Prerequisites

- Node.js (version managed by the project).
- `npm` (bundled with Node.js).
- No backend services required for dev mode.

---

## Install

```bash
npm install
```

---

## Data Source Modes

OmniDash runs in four modes selected by the `VITE_DATA_SOURCE` environment variable. Default values are generated from `contract.yaml` into `src/config/generated/data-source-defaults.ts` — run `npm run generate:config` after editing `contract.yaml`.

The contract default is `http`. `file` is the zero-infra dev mode you opt into explicitly.

### File mode (zero-infra dev)

```bash
VITE_DATA_SOURCE=file npm run dev
```

Reads data from `./fixtures/<topic>/` JSON files. Persists layouts to `./dashboard-layouts/` (gitignored). `./fixtures/` itself is committed via a `.gitignore` carve-out (`!fixtures/**`). Zero infrastructure required.

### HTTP mode (default)

```bash
VITE_DATA_SOURCE=http npm run dev
```

Reads via the projection backend. The base contract deliberately carries no backend URL — unconfigured `http` mode fails loudly. Set the URL via a `contract.local.yaml` overlay or the `OMNIDASH_BRIDGE_URL` environment variable. The local Express bridge (`npm run dev:server`) defaults to port 3002.

### SQLite and Postgres modes

```bash
VITE_DATA_SOURCE=sqlite npm run dev
VITE_DATA_SOURCE=postgres npm run dev
```

Both resolve through `HttpSnapshotSource` pointing at the projection backend. The distinction is server-side; the frontend uses the same HTTP read path as `http` mode.

**Hard rule:** Do NOT hardcode backend URLs or ports in source files. All data access goes through `src/data-source/` adapters. Do NOT read `VITE_DATA_SOURCE` directly in components — always call `resolveEffectiveDataSource()` from `src/data-source/data-source-override.ts`, which layers the runtime chrome override over env defaults.

### Runtime override

The `DataSourceControl` chrome component allows switching the active backend at runtime without restarting. It writes a persisted override via `src/data-source/data-source-override.ts`. This is the single seam — there is no per-widget or per-mode env read outside this module.

---

## Commands

| Command | Purpose |
|---------|---------|
| `npm run dev` | Vite dev server with HMR (contract-default mode: `http`) |
| `npm run dev:server` | Express bridge server (watch mode) |
| `npm run check` | TypeScript-only check (`tsc --noEmit`) — must pass before every PR |
| `npm run test:run` | Vitest single run — must pass before every PR |
| `npm run test` | Vitest watch mode |
| `npm run test:coverage` | Coverage report |
| `npm run lint` | ESLint with zero warnings — must pass before every PR |
| `npm run build` | Type-check then production build |
| `npm run generate:registry` | Rewrite `src/registry/component-registry.json` |
| `npm run generate:config` | Regenerate `src/config/generated/data-source-defaults.ts` from `contract.yaml` — run after editing `contract.yaml` |
| `npm run generate:fixtures` | Regenerate fixture snapshots |
| `npm run types:generate` | Regenerate types under `src/shared/types/generated/` |
| `npm run storybook` | Storybook on port 6006 |
| `npm run build-storybook` | Production Storybook build |

---

## Before Every PR

```bash
npm run lint       # must exit 0
npm run check      # must exit 0
npm run test:run   # must exit 0
npm run build      # must exit 0
```

---

## Adding a New Widget

### Track A: Local MVP widget

Use this track for all in-repo widgets.

1. Create `src/components/dashboard/<name>/<Name>.tsx`. Default-export a React component that accepts a `config` prop shaped per its manifest's `configSchema`.

2. Register the lazy import in `src/components/dashboard/index.ts`:

   ```ts
   '<name>/<Name>': lazy(() => import('./<name>/<Name>')),
   ```

3. Add a manifest entry to `MVP_COMPONENTS` in `scripts/generate-registry.ts`:

   ```ts
   '<name>/<Name>': {
     name: '<name>',
     displayName: 'Widget Display Name',
     // ...full ComponentManifest fields
   }
   ```

4. Run registry generation:

   ```bash
   npm run generate:registry
   ```

5. Add at minimum `Empty` and `Populated` Storybook stories as `<Name>.stories.tsx` alongside the component. The compliance test enforces this on every `npm test`.

6. Add unit tests as `<Name>.test.tsx` alongside the component.

### Track B: External package widget

External widgets come from `@omninode/*` npm packages.

1. The package must declare manifests in its `package.json`:

   ```json
   "dashboardComponents": "./path/to/manifests.json"
   ```

2. Install the package:

   ```bash
   npm install @omninode/<package-name>
   ```

3. Run registry generation to pick up the new manifests:

   ```bash
   npm run generate:registry
   ```

4. The widget appears in the palette with `status: 'not_implemented'` until its `implementationKey` is also registered in the local `componentImports` map in `src/components/dashboard/index.ts`.

---

## Registry Generation

`scripts/generate-registry.ts` is the single source of truth for what appears in the palette. It:

- Reads `MVP_COMPONENTS` for in-repo widgets.
- Auto-scans `node_modules/@omninode/*` for external package manifests.
- Writes `src/registry/component-registry.json`.

Run it after any manifest change:

```bash
npm run generate:registry
```

The output file is committed. Do not hand-edit it.

If the palette is empty after changes, the registry is likely stale — run `npm run generate:registry` and restart the dev server.

---

## Regenerating All Artifacts

If starting from a fresh clone or after major changes:

```bash
npm run types:generate
npm run generate:fixtures
npm run generate:registry
npm run dev
```

---

## Storybook

Storybook runs on port 6006:

```bash
npm run storybook
```

**Story conventions:**

- Stories live alongside components as `<Name>.stories.tsx`.
- Every widget must export at minimum `Empty` and `Populated` stories.
- Widgets that call `useProjectionQuery` must wrap stories with `makeDashboardDecorator(...)` from `@/storybook/decorators/withDashboardContext`.
- Fixtures live under `src/storybook/fixtures/`. Extend existing fixtures rather than duplicating.

The compliance test `src/storybook-coverage-compliance.test.ts` runs as part of `npm test` and fails if any registered widget is missing required stories.

---

## Backend Assumptions

OmniDash reads data from the platform runtime via:

- HTTP polling via `useProjectionQuery` against the projection backend. Live updates are poll-driven — there is no WebSocket connection. The `/ws` path was permanently removed: it was rejected with a 403 by the projection backend and never delivered events. Raw browser WebSocket construction is blocked by the `local/no-projection-websocket` ESLint rule.
- HTTP endpoints exposed by the projection backend (URL from `contract.local.yaml` / `OMNIDASH_BRIDGE_URL`; the local bridge defaults to port 3002) in http/sqlite/postgres modes.

These endpoints are provided by the platform runtime running on the runtime host (`<onex-host>`). In dev mode, fixture files replace live data entirely and no runtime connection is needed.

---

## Gotchas

- **Palette is empty:** `src/registry/component-registry.json` is stale. Run `npm run generate:registry`.
- **Widgets show "no data":** `./fixtures/<topic>/` is missing JSON files. Run `npm run generate:fixtures`. (No `fixtures/registry.json` is required — the `/_fixtures` Vite middleware auto-generates each topic's `index.json` by listing the directory; see `vite.config.ts`.)
- **Edit mode drag/resize not working:** Edit mode is toggled via the `editModeSlice` in Zustand. It must be active. Check `src/store/editModeSlice.ts`.
- **Layout changes not persisting:** Layout does not auto-save on drag. Use the explicit Save button. Layouts write to `./dashboard-layouts/` (gitignored).
- **Types under `src/shared/types/generated/` are wrong:** Run `npm run types:generate` to regenerate from the JSON schema sources.

---

## Key Source Locations

| Path | Purpose |
|------|---------|
| `src/components/dashboard/` | All widget implementations |
| `src/components/dashboard/index.ts` | Lazy-import map |
| `src/components/dashboard/DashboardGrid.tsx` | Grid layout behavior |
| `src/components/dashboard/ComponentPalette.tsx` | Widget palette |
| `src/data-source/` | Data source adapters; `data-source-override.ts` is the single runtime override seam |
| `src/services/` | Route seam for all `/api/` fetch/axios calls — do not place `/api/` literals outside this directory or `src/data-source/` (seam convention; the `local/no-api-literal` rule cited in old source comments does not exist at HEAD) |
| `src/store/` | Zustand state slices |
| `src/pages/DashboardView.tsx` | Main dashboard page (edit/view toggle, Save/Discard) |
| `src/layout/layout-persistence.ts` | Layout save/load |
| `scripts/generate-registry.ts` | Registry source of truth |
| `src/registry/component-registry.json` | Generated registry |
| `shared/types/dashboard.ts` | `DashboardDefinition` schema |
| `shared/types/component-manifest.ts` | `ComponentManifest` schema |
| `server/index.ts` | Express HTTP bridge |
| `src/storybook/fixtures/` | Shared Storybook fixture data |
