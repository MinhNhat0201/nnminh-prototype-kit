---
name: verify
description: "Check a developer build against the approved prototype after handoff, screen by screen and flow by flow: side-by-side screenshots with highlighted differences, colours, font sizes and radii that match no DS token, DS components that went missing, texts that changed, flows that pass in the prototype but fail in the build, console errors and accessibility. Differences are either defects for developers or intended changes covered by an approved decision in the decision log; once nothing fails and every difference is answered, the decisions in scope move to verified. Use when the user says 'check the implementation', 'compare the build with the design', 'design QA', 'is the dev version faithful', 'visual regression against the prototype'. Do not use to test the prototype itself (`validate`) or to audit prototype code against the DS (`review`). Also use for the same request in any language."
---

# Verify: close the loop after handoff

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

Script: `Y=<kit>/skills/verify/scripts/verify.py` (`--help` lists every command); it runs `verify.js` (Playwright, installed Chromium; never `playwright install`). Folder: `<paths.verify>/<name>/` (default `docs/verify`).

Goal: the shipped product matches what was approved, and every difference has an owner.
Reason: design work does not end at handoff; without a check, small drifts pile up until nobody knows which version is right.

## Step 1. Pair the screens

- Load `kit.config.json`. The prototype must be the approved one (built for `react` / `vue`). Ask for the implementation URL (local, preview or staging). Never use a production site with real user data; never log in with real credentials.
- `python3 $Y init <name> --app <id> --implementation <base URL>` writes `pairs.json`. Fill it:
  - **screens**: one pair per approved screen (S-ids from the spec or the `handoff` package): prototype route and implementation path, a `prepare` script per side to reach the same state, `mask` selectors for content that changes on every load (dates, avatars, live data);
  - **flows**: the flows of the QC checklist, as steps per side (selectors may differ).
- Accessibility uses `axe-core` in the project (`npm i -D axe-core`); without it the report says skipped.

## Step 2. Run

`python3 $Y run <name>` (viewports from `pairs.json`, default 390 and 1280 px) writes `<run>/report.md`, `report.json`, `shots/` and `side/` (prototype · implementation · highlighted differences). Exit 1 when anything fails.

| Result | Meaning |
|---|---|
| **Fail** | The build does not open, throws errors, fails a flow the prototype passes, or has an axe critical or serious defect |
| **Differences to review** | Visual difference (500 px or more, or 1 %), a colour, font size or radius matching no DS token and not in the prototype, a DS component of the prototype missing in the build, a prototype text missing in the build, a flow broken in both |
| **Approved deviations** | Differences covered by an approved decision |
| **Skipped** | Not checked, and why |

## Step 3. Sort every difference with the user

Look at each `side/` image and each finding. For every difference, the user decides:
- **Defect** → list it for developers with the screen, the viewport, the finding id and the side-by-side image.
- **Intended change** → it needs an approved decision. Existing one: `python3 $Y accept <name> <finding id> --decision D-… --by "<name>"`. None yet: record the user's approval first (`context`: `decisions.py add --status approved --by "<name>"`), then accept.
- Never accept a difference on your own, and never accept a failure: failures are fixed.

## Step 4. Close

When the developers fixed the defects: `python3 $Y run <name>` again. With **Fail (0)** and every difference accepted, or confirmed by the user as reviewed: `python3 $Y close <name> --by "<name>" [--all-reviewed]`. It moves the decisions in scope from `implemented` to `verified`.

Report: run folder; counts; defects for developers (id, screen, viewport, image); deviations accepted and their decisions; skipped checks; decisions verified.

## Rules

- Never edit the implementation or the prototype here.
- Never treat the prototype as wrong because the build differs: ask; a changed design goes back through `explore` or `prototype` and the decision log.
- Never accept a deviation without an approved decision that names who decided.
- Never use real accounts, real personal data or production systems.
