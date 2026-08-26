---
type: reference
status: current
date: "2026-08-26"
title: "OmniDash Typography Primitives — Text and Heading"
topics: [omnidash, typography, component-api, design-system]
refs: [adrs/ADR-0039-omnidash-typography-system.md, guides/omnidash-development.md]
---

# OmniDash Typography Primitives — `<Text>` and `<Heading>`

**Owner:** `omnidash` (`src/components/ui/typography/`)

The `<Text>` and `<Heading>` components are the single source of truth for rendered text in the app. They centralize size, color, weight, and family tokens so raw utility classes are not scattered across widgets. See [ADR-0039](../adrs/ADR-0039-omnidash-typography-system.md) for the rationale and the compliance gate.

## When to use which

- **`<Heading>`** — section titles and page titles (`h1`..`h4`). Carries semantic heading level.
- **`<Text>`** — everything else: body copy, labels, table cells, status strings, timestamps. Renders a `<span>` by default; use `as="p"` / `as="div"` when block semantics matter.

## Examples

Body text:

```tsx
<Text>plain text</Text>
```

Data row cell (monospace, muted, aligned numerals):

```tsx
<Text size="md" family="mono" color="tertiary" tabularNums>{timestamp}</Text>
```

Uppercase column header (note: `.text-tracked` preserves the spaced-caps look):

```tsx
<Text size="xs" weight="semibold" transform="uppercase" color="secondary" className="text-tracked">{label}</Text>
```

Truncated label (always pair `truncate` with `title` for hover disclosure):

```tsx
<Text truncate title={long}>{long}</Text>
```

Status cell:

```tsx
<Text color={ok ? 'ok' : 'bad'} weight="medium">{ok ? 'OK' : 'FAIL'}</Text>
```

## `TextProps`

| Prop | Description |
| --- | --- |
| `size` | `xs` \| `sm` \| `md` \| `lg` \| `xl` — token-backed font-size. |
| `color` | `primary` \| `secondary` \| `tertiary` \| `ok` \| `warn` \| `bad` \| `accent`. |
| `weight` | `regular` \| `medium` \| `semibold` \| `bold`. |
| `leading` | `tight` \| `normal` \| `relaxed` — line-height token. |
| `family` | `sans` (default) \| `mono`. |
| `transform` | `none` \| `uppercase` \| `lowercase` \| `capitalize`. |
| `align` | `left` \| `center` \| `right`. |
| `tabularNums` | `boolean` — enables `font-variant-numeric: tabular-nums`. |
| `truncate` | `boolean` — single-line ellipsis; pair with `title`. |
| `as` | Element override — `span` (default), `p`, `div`, `label`, etc. |
| `style` | Inline style escape hatch; wins over computed style. |
| `className` | Additional classes merged after computed ones. |
| `id`, `title`, `aria-*`, `role` | Standard a11y attributes forwarded to the DOM. |

## `HeadingProps`

| Prop | Description |
| --- | --- |
| `level` | `1` \| `2` \| `3` \| `4` → renders `h1`..`h4`. Default size maps from level. |
| `size` | Override the level's default size token. |
| `color` | Same palette as `TextProps.color`. |
| `weight` | Same scale as `TextProps.weight`. Default `semibold`. |
| `leading` | Line-height token override. |
| `transform` | Text transform override. |
| `align` | Text alignment. |
| `style`, `className`, a11y attrs | Same behavior as `TextProps`. |

## Escape hatch

The `style` prop always wins over computed style. Use it for one-off visual overrides that do not fit the prop API — but prefer extending the token set or adding a prop if the override recurs.

## Related utility classes

- `.text-tracked` — letter-spacing for small-caps uppercase labels.
- `.text-input-md` / `.text-input-sm` — font-size for native `<input>` and `<textarea>` elements (which cannot be rendered via `<Text>`).

## Storybook

Showcase: `npm run storybook` → Typography pages (`Heading.stories.tsx`, `Typography.stories.tsx` in `src/components/ui/typography/`).

## See also

- [ADR-0039 — Dashboard Typography System](../adrs/ADR-0039-omnidash-typography-system.md)
- `src/typography-compliance.test.ts` — the compliance gate.

## Evidence

Verified against the live omnidash tree at migration time: every documented `TextProps` field (`size`, `color`, `weight`, `leading`, `family`, `transform`, `align`, `tabularNums`, `truncate`) matches the `TextProps` interface in `Text.tsx` exactly.
