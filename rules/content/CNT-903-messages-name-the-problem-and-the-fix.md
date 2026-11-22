---
id: CNT-903
title: Messages name the problem and the fix
category: content
layer: kit
applies_to: []
skills: [prototype, review, verify]
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
  - 2026-11-22 · active · kit 0.11.0
---

Error messages say what went wrong and how to fix it in plain words, next to the field or part that failed, keep what the user typed and never show a bare error code. Buttons name the action with a verb and an object, and a confirmation repeats that action on its button. One word per concept across the app.

Why: vague messages ("Something went wrong", "OK") leave people stuck and turn into support requests (WCAG 3.3.1, 3.3.3, 2.4.6).
