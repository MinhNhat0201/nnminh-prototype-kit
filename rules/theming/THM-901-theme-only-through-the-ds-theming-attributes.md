---
id: THM-901
title: Theme only through the DS theming attributes
category: theming
layer: kit
applies_to: []
skills: [prototype, explore, review, validate]
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

Brand, mode and density are set only through the attributes in `ds.json > theming`, on `<html>`. Never invent an attribute or a class for theming. Dark mode stays off unless the user asks for it.

Why: every app, the validation run and the spec viewer switch themes the same way.
