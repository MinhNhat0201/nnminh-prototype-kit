---
id: SEC-901
title: No secrets or personal data in the repository
category: security
layer: kit
applies_to: []
skills: []
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

Never write passwords, tokens, keys, real site credentials or personal data into the repository, a config file, a PR, a package or a report.

Why: repositories and packages are copied and shared; a leaked secret cannot be taken back.
