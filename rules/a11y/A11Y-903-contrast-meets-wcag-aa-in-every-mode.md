---
id: A11Y-903
title: Contrast meets WCAG AA in every mode
category: a11y
layer: kit
applies_to: []
skills: [prototype, validate, review, verify, explore]
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

Text has a contrast of at least 4.5:1 with its background (3:1 for text of 24 px or more, or 18.66 px bold), and field borders, meaningful icons and focus indicators at least 3:1, in every mode and brand the app offers. Text over images or gradients gets an overlay that keeps these ratios. Colour is never the only signal of a state. When a DS token pair fails, report it to `document` instead of changing the colour in the app.

Why: low contrast is the most frequent audit failure and breaks first in dark mode and on other brands (WCAG 1.4.3, 1.4.11, 1.4.1).
