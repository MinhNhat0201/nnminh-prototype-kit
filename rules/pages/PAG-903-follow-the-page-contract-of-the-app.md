---
id: PAG-903
title: Follow the page contract of the app
category: pages
layer: kit
applies_to: []
skills: [prototype]
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

Every page built or edited in an app does what `apps[].pageContract` lists (`kitconf.py contract --app <app>`): the calls, load order and mount elements its shell needs. A page built in another stack for that app (`type: "page"`) follows the contract of each host app. Each line gets a check in the validation plan.

Why: a missed contract call often fails without an error (icons or navigation disappear), so nobody sees it until review.
