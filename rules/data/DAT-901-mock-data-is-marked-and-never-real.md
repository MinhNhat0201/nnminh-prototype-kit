---
id: DAT-901
title: Mock data is marked and never real
category: data
layer: kit
applies_to: []
skills: [prototype, explore, handoff]
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

Mock data is marked as mock in the code and, where a reader could take it for real, in the UI. No real personal data, no real API, no authentication, no persistence beyond `localStorage`.

Why: prototypes are shared widely; real data in them is a privacy incident.
