---
id: A11Y-904
title: Motion respects reduced motion
category: a11y
layer: kit
applies_to: []
skills: [prototype, validate, review, verify]
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

Under `prefers-reduced-motion: reduce` (and the system setting on phones) there is no sliding, zooming, bouncing or parallax: use a short opacity change or switch instantly, and stop decorative loops. Animation takes its durations and easings from the DS motion tokens; local animation follows the same media query as the DS.

Why: large motion causes dizziness and nausea for people with vestibular disorders, and they have already asked their system for less (WCAG 2.3.3).
