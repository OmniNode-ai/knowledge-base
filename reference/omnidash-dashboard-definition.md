---
type: reference
status: current
date: "2026-08-26"
title: "OmniDash DashboardDefinition Schema"
topics: [omnidash, dashboard-definition, schema, layout, widgets]
refs: [reference/omnidash-component-manifest.md, architecture/omnidash-composable-frame.md]
---

# OmniDash DashboardDefinition Schema

**Owner:** `omnidash`
**Verification:** `npm run check`
**Source of truth:** `shared/types/dashboard.ts`

---

## Overview

A saved dashboard is represented as a `DashboardDefinition` JSON document. Dashboard definitions are:

- Serializable — exportable and importable as JSON files.
- Versioned — the `schemaVersion` field tracks the definition schema version.
- Validated on load — `config` values for each layout item are validated against the widget's `configSchema`.

---

## DashboardDefinition

```typescript
interface DashboardDefinition {
  id: string;                    // UUID — unique dashboard identifier
  schemaVersion: '1.0';          // definition schema version
  name: string;                  // human-readable name (required, non-empty)
  description?: string;          // optional description
  theme?: string;                // optional theme name
  layout: DashboardLayoutItem[]; // array of placed widgets
  globalFilters?: {
    timeRange?: { start: string; end: string };
  };
  createdAt: string;             // ISO 8601 timestamp
  updatedAt: string;             // ISO 8601 timestamp
  author: string;                // author identifier
  shared: boolean;               // whether the dashboard is shared
}
```

### Validation Rules

`validateDashboardDefinition` (exported from `shared/types/dashboard.ts`) checks:

- `name` is present and non-empty.
- `id` is present.
- `schemaVersion` is exactly `'1.0'`.
- Every layout item has a non-empty `componentName`.
- Every layout item has `w > 0` and `h > 0`.

Invalid definitions return `{ valid: false, errors: string[] }` rather than throwing.

---

## DashboardLayoutItem

```typescript
interface DashboardLayoutItem {
  i: string;                // UUID — grid item key (unique within the dashboard)
  componentName: string;    // registry key — must match a ComponentManifest name
  componentVersion: string; // semver — matched against manifest version
  x: number;                // grid column (0-indexed)
  y: number;                // grid row (0-indexed)
  w: number;                // width in grid units (> 0)
  h: number;                // height in grid units (> 0)
  config: Record<string, unknown>; // validated against the widget's configSchema
}
```

The `config` field is validated against the matching `ComponentManifest.configSchema` on load. Invalid configs are rejected with a diagnostic — not silently accepted. A layout item with a missing or wrong config key fails to load with an explicit error.

---

## Schema Versioning

The `schemaVersion` field is `'1.0'` for all current dashboards. When the schema evolves (new required fields, changed semantics), the version increments. The registry reads this version to determine how to parse and migrate the definition.

Saved dashboard files in `./dashboard-layouts/` use `schemaVersion: '1.0'`. The directory is gitignored and local-only.

---

## Example

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "schemaVersion": "1.0",
  "name": "Platform Health Overview",
  "description": "Real-time health and cost monitoring",
  "layout": [
    {
      "i": "item-1",
      "componentName": "health-monitor",
      "componentVersion": "1.0.0",
      "x": 0,
      "y": 0,
      "w": 6,
      "h": 4,
      "config": {}
    },
    {
      "i": "item-2",
      "componentName": "cost-trend",
      "componentVersion": "1.0.0",
      "x": 6,
      "y": 0,
      "w": 6,
      "h": 4,
      "config": {
        "dimension": "2d",
        "style": "area"
      }
    }
  ],
  "createdAt": "2026-04-29T00:00:00Z",
  "updatedAt": "2026-04-29T00:00:00Z",
  "author": "dashboard-author",
  "shared": false
}
```

---

## Related

- [`reference/omnidash-component-manifest.md`](omnidash-component-manifest.md) — `ComponentManifest` schema (defines `configSchema` per widget)
- [`architecture/omnidash-composable-frame.md`](../architecture/omnidash-composable-frame.md) — how dashboard definitions flow through the frame
- Source: `shared/types/dashboard.ts`
