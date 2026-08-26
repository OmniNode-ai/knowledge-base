---
type: architecture
status: accepted
date: "2026-07-21"
title: "Untitled"
topics: [omnibase-infra, shared, enum, ownership]
refs: []
---

## Shared Enum Ownership Rule

**Rule: shared enums are defined once in `omnibase_core`. Downstream repos import or re-export; never redefine.**

### Background

Python's `isinstance()` checks class object identity, not semantic value equality. If two packages independently define `class EnumMessageCategory(Enum)` with identical members, Python treats them as different types. Cross-package `isinstance()` checks silently fail.

This caused a production incident: `Category must be EnumMessageCategory, got EnumMessageCategory.`

### Rule

- `omnibase_core` is the sole canonical owner of all shared messaging enums.
- Downstream repos (`omnibase_infra`, `omniclaude`, others) must import from `omnibase_core`:
  `from omnibase_core.enums import EnumMessageCategory`
- Re-exporting to preserve legacy import paths is allowed: `from omnibase_core.enums import EnumMessageCategory as EnumMessageCategory`
- Defining a second class with the same name is **forbidden**. CI will block it (`scripts/check_shared_enum_ownership.py`).

### Runtime Boundaries

Any code accepting a message category from an external caller must normalize first:

    category = coerce_message_category(raw_input)

Never rely on `isinstance(x, EnumMessageCategory)` at a package boundary where the calling package may have a different load context.

### Applies to All Future Shared Enums

Any new enum shared across packages: defined once in `omnibase_core`, imported downstream, coercion helper at runtime boundaries.
