---
id: PAG-901
title: Ask before a new page
category: pages
layer: kit
applies_to: []
skills: [define, prototype]
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
  - 2026-11-22 · active · kit 0.8.0
---

A new page (own entry point, flow and states; not a dialog, tab or step) is announced and the user chooses: an own file or route, or a screen inside the current file. No file, folder or route is created before the choice. Unattended run: build inside the current file and say so at the top of the report.

Why: a page changes navigation, handoff scope and the lock layer of packages.
