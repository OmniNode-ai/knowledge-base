---
type: adr
status: accepted
date: "2026-04-24"
title: "ADR-0039: Dashboard Typography System — Tokens Plus Typed Primitives"
adr_id: ADR-0039
topics: [omnidash, typography, design-system, eslint, storybook]
refs: [adrs/ADR-0040-omnidash-storybook-widget-coverage.md, reference/omnidash-typography-primitives.md]
supersedes: []
superseded_by: []
---

# ADR-0039: Dashboard Typography System — Tokens Plus Typed Primitives

**Status**: Accepted
**Date**: 2026-04-24
**Source**: omnidash `docs/adr/001-typography-system.md` (filed in-repo as "ADR 001"; renumbered on migration into the platform-wide decision ledger)

---

## Context

During a UX polish pass, two dashboard widgets — `EventStream` and `RoutingDecisionTable` — were observed to diverge visually despite being designed to read as a matched pair of "data feed" surfaces. The symptoms were subtle but systematic:

- Data rows: EventStream rendered at `0.75rem` (12 px); RoutingDecisionTable rendered at `0.8125rem` (13 px).
- Column headers: EventStream at `10 px`; RoutingDecisionTable at `11 px`.
- Status/pagination rows: EventStream at `11 px`; RoutingDecisionTable at `12 px`.
- Timestamp cell color: EventStream dimmed (`--ink-3`); RoutingDecisionTable used the full ink (`--ink`).

Root cause: every widget hand-authors inline `fontSize`, `fontFamily`, `fontWeight`, and `color` values. There is no typography scale, no semantic text-role token, and no shared React primitive for rendering text. Widgets that "should look the same" must remember to pick the same numbers — and they did not.

A prior refactor introduced `--font-sans` and `--font-mono` CSS custom properties. That solved the family drift (widget mono text was rendering in the wrong mono face because of a stale vanilla-extract override). The family tokens are a good start but cover only one axis of typography. Size, weight, leading, and text-color drift remain open.

Across the codebase, at the time of this decision:

- 8 widget files reference inline `fontSize` values (10, 11, 12, 13, 14, `0.75rem`, `0.8125rem`, …).
- 10+ widget files inline `fontFamily: 'var(--font-mono)'` — these should read as a primitive, not repeat everywhere.
- No Storybook setup exists to visually audit typography variants.
- No lint rule prevents a new widget from repeating the drift.

## Decision

Adopt a **CSS custom-property tokens + typed React component primitives** typography system:

1. **Token layer (CSS).** Declare type-scale, leading, weight, and text-color-role tokens in `src/styles/globals.css :root`. Every typographic value a widget can use traces to one of these tokens. Themes override via `[data-theme="X"]` scope.

2. **Component layer (React).** Introduce `<Text>` and `<Heading>` in `src/components/ui/typography/`. Both accept prop variants (`size`, `color`, `weight`, `leading`, `family`, `transform`, `tabularNums`, `truncate`, `as`, …) that resolve internally to the CSS custom properties. Widgets consume the components, never the raw tokens inline.

3. **Enforcement layer.** A custom ESLint rule `local/no-typography-inline` fails CI when any of `fontSize`, `fontFamily`, `fontWeight`, `fontVariantNumeric`, `letterSpacing`, `textTransform`, `lineHeight` appears in a JSX `style` prop outside `src/components/ui/typography/`. This prevents regression.

4. **Showcase layer.** Storybook with a theme decorator. Typography and Heading stories document every variant in both light and dark modes; the stories are also the visual contract a reviewer can check.

5. **Compliance-testing layer.** `src/typography-compliance.test.ts` encodes every acceptance criterion as a Vitest assertion. The count of failing tests is the refactor's progress indicator; it is excluded from the default test run during the refactor and promoted to a permanent regression gate at the end.

**Constraint on new work.** No CSS-in-JS for typography. The existing vanilla-extract theme contract in `src/theme/tokens.css.ts` is retained for colors and radius, but its font entries have been removed. New components must not reference `vars.font.*` — use the CSS custom property directly (`fontFamily: 'var(--font-mono)'`) until tokens are consumed through `<Text>` / `<Heading>`.

## Consequences

| Consequence | Pro | Con | Mitigation |
|---|---|---|---|
| Single-source typography tokens | Drift between widgets impossible by construction | Widget authors must learn the token vocabulary | Storybook showcase + typography reference document every variant |
| `<Text>` / `<Heading>` primitives | Widgets express intent, not implementation | One-off overrides need an escape hatch | `style` prop on Text merges OVER computed style; documented as the escape hatch |
| ESLint rule blocks inline typography | Regression mechanically impossible | Inputs / textareas cannot style natively via `<Text>` | Exempt `src/components/ui/typography/` from the rule; for native inputs, use a small CSS utility class (e.g. `.text-input-md`) rather than inline style |
| Two parallel theme systems during migration | Non-breaking — legacy components keep working | vanilla-extract + globals.css cohabit — confusing to new readers | Comment in `tokens.css.ts` flags the system as legacy for colors only; consolidation deferred |
| Compliance file excluded from default run | Refactor does not red the CI while in progress | Easy to forget to re-enable | The promotion step's acceptance explicitly checks the `exclude` list and gates promotion |
| Multi-ticket epic | Broken into waves; multi-agent workflow can parallelize the widget migrations | Each ticket adds tracker noise | Work tracked under a single typography epic umbrella without a sprawling sibling-epic set |
| Theme-able foundation (for a future alternate visual mode) | Rebranding is a token-override exercise, not a widget sweep | None at current scale | — |

## Alternatives Considered

1. **Tailwind utility classes (`text-sm text-muted-foreground font-mono`).**
   Rejected. Tailwind is a heavy runtime dependency for this scope and would shadow the existing CSS-custom-property conventions. Migrating to Tailwind would be a multi-week effort that dwarfs the typography fix. If the team adopts Tailwind later, the token names (`--text-xs` etc.) can be mapped into `tailwind.config.ts` without touching widgets.

2. **vanilla-extract everywhere (unify on CSS-in-JS).**
   Rejected. One legacy component uses vanilla-extract, but the rest of the app uses plain CSS + CSS variables. Migrating `globals.css` into vanilla-extract is a large refactor with no functional improvement. Keep the two systems; new typography work uses CSS custom properties directly.

3. **A full third-party component library.**
   Rejected. The app already has its own visual language. Adopting a component library would force a total visual rewrite. Typography is narrower — solve typography, do not overhaul the chrome.

4. **Styled-components / emotion.**
   Rejected. Same reason as vanilla-extract — CSS custom properties are already the primary pattern; adding a second CSS-in-JS layer increases complexity without benefit.

5. **Inline improvements (keep ad-hoc typography, just be more careful).**
   Rejected. The observed drift happened *despite* author attention. Without a structural fix, drift is inevitable.

## Evidence

Verified against the live omnidash tree at migration time:

- `local/no-typography-inline` is registered at `'error'` severity in `eslint.config.js`.
- `<Text>` / `<Heading>` primitives and their `tokens.ts` live under `src/components/ui/typography/`.
- `src/typography-compliance.test.ts` exists and runs as a regression gate.
