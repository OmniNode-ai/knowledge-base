---
type: doctrine
status: accepted
date: "2026-05-23"
title: "Runtime Complexity Must Be Isolated"
topics: [runtime-isolation]
refs: [doctrine/evidence-is-first-class-output.md, doctrine/truth-must-be-proven.md, doctrine/ingestion-and-interpretation-separate.md]
---

# Runtime Complexity Must Be Isolated

Complexity belongs in controlled layers:

- event ingestion
- runtime orchestration
- projection services
- contract validation
- evidence generation

Complexity must not leak into:

- clients
- duplicated service logic
- uncontracted scripts
- dashboard-only state

Mocks and simulations:

- are valid for unit validation
- do not prove system truth

Truth requires the applicable proof mode:

- replay validation
- contract validation
- static validation
- runtime evidence where the claim is runtime-dependent
