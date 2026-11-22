---
id: A11Y-901
title: Names, labels and a visible focus
category: a11y
layer: kit
applies_to: []
skills: [prototype, validate, review, verify]
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

Every control has an accessible name, every field a label, every interactive element a visible focus indicator, and text meets the DS contrast pairs. Touch targets on phones follow `validate.touchTarget`.

Why: these fail first in audits and are cheap to get right while building.
