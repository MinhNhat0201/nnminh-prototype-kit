---
id: A11Y-902
title: Touch targets meet the platform minimum
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

Every tap or click target is at least 24×24 CSS px or spaced so that 24 px circles around targets do not overlap; on phones it meets the platform size in `kit.config.json > validate.touchTarget` (44 px by default; 44 pt iOS, 48 dp Android). Enlarge the hit area with padding, never the icon. When the DS documents another target size (per density or platform), follow the DS and note it in the report. Links inside a sentence are exempt.

Why: small targets cause mis-taps for everyone and block people with limited motor control (WCAG 2.2 2.5.8).
