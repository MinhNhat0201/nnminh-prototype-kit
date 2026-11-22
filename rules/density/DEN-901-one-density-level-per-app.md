---
id: DEN-901
title: One density level per app
category: density
layer: kit
applies_to: []
skills: []
severity: should
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

An app uses the DS default density unless the product needs one fixed level; then it sets that level once and uses it everywhere. Never redefine the values of a density level.

Why: mixed densities on one screen look broken, and redefined values drift from the DS.
