---
id: CNT-901
title: Reference images give layout only
category: content
layer: kit
applies_to: []
skills: [prototype, explore, mockup]
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

Reference images and screenshots of other apps give layout, order, behaviour and content only. Never copy their colours, fonts, radii, shadows or icons; rebuild with DS tokens and components, and list what the image does not show (hover, focus, error, empty, loading).

Why: copied styles bypass the DS and invented states become requirements nobody agreed.
