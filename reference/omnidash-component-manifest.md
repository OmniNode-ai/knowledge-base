---
type: reference
status: current
date: "2026-08-26"
title: "OmniDash ComponentManifest Schema"
topics: [omnidash, component-manifest, registry, json-schema, widgets]
refs: [reference/omnidash-dashboard-definition.md, architecture/omnidash-composable-frame.md, guides/omnidash-development.md]
---

# OmniDash ComponentManifest Schema

**Owner:** `omnidash`
**Verification:** `npm run generate:registry`; `npm run test:run -- shared/types/component-manifest.test.ts src/integration.part3.test.tsx`
**Source of truth:** `shared/types/component-manifest.ts`

---

## Overview

A `ComponentManifest` describes a single dashboard widget to the component registry. Manifests declare:

- Identity: name, display name, description, category, version.
- Sizing constraints: default, minimum, and maximum grid sizes.
- Data sources: what topics or projection endpoints the widget reads.
- Authority labels: whether the panel is projection-backed, runtime-observed, degraded, or hidden.
- Input and output contracts: the projection row schema the widget binds to, and the rendered-output contract it guarantees.
- Events: what the widget emits and consumes on the mitt bus.
- Config schema: a JSON Schema that governs what per-instance configuration the widget accepts.

The registry discovers manifests from two sources:

1. **In-repo MVP manifests** — `MVP_COMPONENTS` in `scripts/generate-registry.ts`.
2. **External package manifests** — declared in `@omninode/*` npm packages via the `"dashboardComponents"` field in their `package.json`.

---

## ComponentManifest Fields

```typescript
interface ComponentManifest {
  name: string;          // registry key — immutable, URL-safe slug
  displayName: string;   // human-facing label (can change across versions)
  description: string;   // one-sentence description
  category: ComponentCategory; // 'cost' | 'activity' | 'quality' | 'health'
  version: string;       // semver
  implementationKey: string; // path within componentImports map in index.ts
  paletteVisibility?: 'visible' | 'hidden';
  authorityLabel: 'projection-backed' | 'runtime-observed' | 'degraded' | 'hidden';

  configSchema?: JSONSchema7; // JSON Schema for per-instance config (optional)
                              // omit if the widget has nothing to configure

  projectionSchema?: JSONSchema7 | string; // input contract: shape of each upstream row
  displayContract?: JSONSchema7 | string;  // output contract: what the render guarantees

  dataSources: DataSourceDeclaration[]; // what data the widget reads
  events: {
    emits: ComponentEvent[];    // events the widget fires on the mitt bus
    consumes: ComponentEvent[]; // events the widget listens to on the mitt bus
  };

  defaultSize: GridSize; // { w: number; h: number } in grid units
  minSize: GridSize;     // minimum resize bounds
  maxSize: GridSize;     // maximum resize bounds

  emptyState: {
    message: string;  // shown when no data is available
    hint?: string;    // optional guidance for the user
    reasons?: Partial<Record<EmptyStateReason, { message: string; cta?: string }>>;
                      // per-reason messages; preferred over `message` when present
  };

  capabilities: {
    supports_compare: boolean;
    supports_export: boolean;
    supports_fullscreen: boolean;
    supports_time_range?: boolean;
  };
}
```

### Authority Labels

`authorityLabel` is required. Missing labels fail `validateComponentManifest`, and registry generation fails when an in-repo MVP component has no `PALETTE_CLASSIFICATION` entry.

Accepted labels:

- `projection-backed`: rows are served by the standard `/projection/{topic}` backend and can be used as proof only when the packet also carries fresh, correlation-linked projection data and browser network evidence.
- `runtime-observed`: data is observed from runtime health/topology surfaces. It is useful context, not projection proof by itself.
- `degraded`: the panel is intentionally visible with an honest empty/stale/unavailable state. It cannot be cited as projection-backed proof.
- `hidden`: the panel is not demo-visible from the palette because the backing projection path is absent, broken, or shape-incompatible.

Hidden panels must use `paletteVisibility: 'hidden'` and `authorityLabel: 'hidden'`. Visible panels must not use `authorityLabel: 'hidden'`.

Proof packets must record the authority label beside the screenshot and browser network trace. Nonblank UI is not proof; fresh projection-backed, correlation-linked data is proof.

### ComponentCategory

```typescript
const COMPONENT_CATEGORIES = ['cost', 'activity', 'quality', 'health'] as const;
type ComponentCategory = typeof COMPONENT_CATEGORIES[number];
```

Categories group widgets by domain (what the widget shows), not by chart shape (what it looks like). This keeps 2D and 3D variants of the same data together in the palette.

### GridSize

```typescript
interface GridSize {
  w: number; // grid columns
  h: number; // grid rows
}
```

### DataSourceDeclaration

```typescript
interface DataSourceDeclaration {
  type: 'websocket' | 'projection'; // how the data arrives
  topic?: string;                   // topic name (for websocket type)
  required: boolean;                // whether the widget fails without this source
  purpose: 'live_updates' | 'initial_fetch'; // how the widget uses this data
  auth_required?: boolean;          // whether the endpoint requires auth
}
```

### ComponentEvent

```typescript
interface ComponentEvent {
  name: string;                        // event name on the mitt bus
  schema?: Record<string, unknown>;    // optional JSON Schema for the payload
}
```

### configSchema

`configSchema` is a `JSONSchema7` definition. It is the source of truth for:

- What config keys a widget accepts.
- Types, defaults, and constraints for each key.
- Validation of `DashboardLayoutItem.config` on dashboard load.
- Config panel UI generation in edit mode (the frame generates form controls from the schema).
- Generated dashboard configs (an automated builder reads the schema to know what is valid).

Omit `configSchema` if the widget has no configurable settings. When present, it must have `type: 'object'` at the top level.

### projectionSchema — the input contract

`projectionSchema` is the JSON Schema (or a `$ref` string pointing to one) describing the shape of each row emitted by the upstream projection topic. Adapters receive data pre-validated against this schema. Omit it for widgets that do not bind to a projection source.

When row order matters for the widget's output, declare an `ordering` property inside this schema using `ProjectionOrderingAuthority`:

```typescript
interface ProjectionOrderingAuthority {
  authority: 'ingest_sequence' | 'bucket_time' | 'aggregation_key' | 'monotonic_field';
  fieldName?: string;
  direction?: 'asc' | 'desc';
  clockSemantics?: string; // required when authority is 'bucket_time'
}
```

Adapters must not rely on incidental array order unless this contract is declared.

### displayContract — the output contract

`displayContract` is the JSON Schema (or a `$ref` string) describing what the rendered widget guarantees to display. It is the basis for browser-driven render assertions. Omit it for widgets with no verifiable rendered-output contract.

### emptyState.reasons — per-reason empty states

`emptyState.message` is the fallback. `emptyState.reasons` supplies distinguished messages keyed by the canonical `EmptyStateReason` vocabulary (`no-data` | `missing-field` | `upstream-blocked` | `schema-invalid`); when a matching reason is present, the adapter renders it in preference to the top-level `message`. Each entry carries a `message` and an optional `cta`.

Notably, `upstream-blocked` MUST be declared for any widget whose `projectionSchema` has upstream-blocked columns. Omit `reasons` entirely for widgets that do not need distinguished states.

---

## implementationKey Convention

The `implementationKey` matches an entry in the `componentImports` lazy-import map in `src/components/dashboard/index.ts`:

```ts
// index.ts
export const componentImports: Record<string, () => Promise<{ default: ComponentType<WidgetProps> }>> = {
  'cost-trend/CostTrend': lazy(() => import('./cost-trend/CostTrend')),
  // ...
};
```

Convention: `'<widget-dir>/<ComponentName>'`

If a manifest's `implementationKey` has no matching entry in `componentImports`, the widget appears in the palette with `status: 'not_implemented'` and cannot be placed on a dashboard. The registry does not crash.

---

## Example

```typescript
const costTrendManifest: ComponentManifest = {
  name: 'cost-trend',
  displayName: 'Cost Trend',
  description: 'Stacked cost chart across cost categories over time.',
  category: 'cost',
  version: '1.0.0',
  implementationKey: 'cost-trend/CostTrend',
  paletteVisibility: 'visible',
  authorityLabel: 'projection-backed',
  configSchema: {
    type: 'object',
    properties: {
      dimension: {
        type: 'string',
        enum: ['2d', '3d'],
        default: '2d',
        description: 'Chart dimension variant',
      },
      style: {
        type: 'string',
        enum: ['area', 'bar'],
        default: 'area',
        description: 'Chart style (only meaningful in 3D mode)',
      },
    },
    additionalProperties: false,
  },
  dataSources: [
    {
      type: 'projection',
      topic: 'onex.evt.<domain>.cost-ledger.v1',
      required: true,
      purpose: 'initial_fetch',
    },
  ],
  events: {
    emits: [],
    consumes: [{ name: 'time_range_changed' }],
  },
  defaultSize: { w: 6, h: 4 },
  minSize: { w: 3, h: 3 },
  maxSize: { w: 12, h: 8 },
  emptyState: {
    message: 'No cost data available',
    hint: 'Start a workflow to generate cost events.',
    reasons: {
      'upstream-blocked': {
        message: 'Cost projection is degraded upstream',
        cta: 'Check the projection backend health',
      },
    },
  },
};
```

---

## Registry Generation

Manifests are registered in `scripts/generate-registry.ts` under `MVP_COMPONENTS`:

```ts
export const MVP_COMPONENTS: Record<string, ComponentManifest> = {
  'cost-trend/CostTrend': costTrendManifest,
  // ...
};
```

After editing `MVP_COMPONENTS`, run:

```bash
npm run generate:registry
```

This rewrites `src/registry/component-registry.json`. Do not hand-edit that file.

---

## Related

- [`reference/omnidash-dashboard-definition.md`](omnidash-dashboard-definition.md) — `DashboardDefinition` schema (uses manifests for `config` validation)
- [`architecture/omnidash-composable-frame.md`](../architecture/omnidash-composable-frame.md) — how the registry discovers and resolves manifests
- [`guides/omnidash-development.md`](../guides/omnidash-development.md) — step-by-step widget addition guide
- Source: `shared/types/component-manifest.ts`
