---
id: PAG-902
title: Keep the business rules when a page is rebuilt
category: pages
layer: kit
applies_to: []
skills: [prototype, define, verify, review]
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

When an existing page is rebuilt in another stack or structure, every business rule stays as it was: flow, conditions, limits, input checks, visible text, messages, data shared with other pages and routes. Only the way it is built changes. Compare each spec unit of the page; what the new version cannot do yet is reported before, never dropped or changed silently.

Why: BA and QC test the rules, not the code; a silent change becomes a defect in the developer build.
