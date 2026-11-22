---
id: STY-901
title: Use DS tokens only
category: styling
layer: kit
applies_to: []
skills: [prototype, explore, mockup, review, contribute, validate]
severity: must
status: active
since: 2026-11-22
decision:
check:
overrides:
reason:
superseded_by:
supersedes:
exceptions:
history:
  - 2026-11-22 · active · kit 0.9.0
---

Colours, spacing, radius, font size, line height and shadows come from DS tokens (`ds.json > tokens.prefix`) or the alias variables the DS bundle defines. No hex, `rgb()`, named colours, raw gradients or loose px when a token exists; in React and Vue also no Tailwind arbitrary values and no inline style objects for these values.

Why: the DS is the single source of truth. A hard-coded value does not follow theme, mode, density or the next DS version, and developers copy it into production.
