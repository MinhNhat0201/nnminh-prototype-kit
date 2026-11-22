---
id: CNT-902
title: Every data region has empty, loading and error states
category: content
layer: kit
applies_to: []
skills: [define, prototype, validate, review, verify]
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
  - 2026-11-22 · active · kit 0.11.0
---

Every list, table and result area of a main flow has a first-use empty state (what will be here, why, how to start, one primary action), a loading state for waits over about one second, and an error state that says what happened and how to continue; built with the DS empty, alert, skeleton and spinner components. A state that the requirement does not describe is asked about, not invented; a state not built is listed in the report.

Why: prototypes that show only filled data hide the screens real users meet first, and developers then invent them.
