---
id: A11Y-905
title: Everything works with a keyboard
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

Every action that works with a pointer also works with the keyboard, in reading order, without a positive `tabindex` and without a keyboard trap. Dialogs, sheets and menus move focus inside when they open, keep it there, close with Esc and return focus to the control that opened them. Dragging has an alternative without dragging.

Why: keyboard and screen reader users cannot finish a task otherwise, and focus lost after a dialog closes is the most common break (WCAG 2.1.1, 2.1.2, 2.4.3, 2.5.7).
