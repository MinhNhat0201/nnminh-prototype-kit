---
id: BLD-901
title: The version label states the DS version you read
category: build
layer: kit
applies_to: []
skills: [prototype, sync, review, handoff]
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
  - 2026-11-22 · active · kit 0.8.0
---

The footer label (`ds.json > version_label.text`) and the `<meta name="<version_label.meta>">` of every page state the DS version the app was built or synced with. An app whose label differs from the profile is reported, and `sync` is suggested.

Why: developers and the handoff check read the label to know which DS a screen follows.
