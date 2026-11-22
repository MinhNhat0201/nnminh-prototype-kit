---
id: STY-902
title: Never override DS component CSS
category: styling
layer: kit
applies_to: []
skills: [prototype, explore, review, sync, contribute]
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

Never write CSS that changes the look of a DS component (its classes, variants or the elements they style), and never edit the embedded DS CSS or the copied bundle. A missing variant goes through the component gate of `prototype`.

Why: an override hides a gap the DS should close, and the next `sync` silently breaks or keeps the override.
