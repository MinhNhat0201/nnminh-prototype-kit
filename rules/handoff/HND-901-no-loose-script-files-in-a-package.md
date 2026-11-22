---
id: HND-901
title: No loose script files in a package
category: handoff
layer: kit
applies_to: []
skills: [handoff, share]
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

A handoff package has no loose `.js` (or other executable) file: scripts are inlined into the pages, and `optimize_package.py` removes what remains. The zip stays under `handoff.maxZipMB`.

Why: mail filters block attachments with script files, and the package must open on the reader's computer.
