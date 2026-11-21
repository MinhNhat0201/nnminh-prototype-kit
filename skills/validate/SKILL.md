---
name: validate
description: "Check a prototype in the browser and write one validation report that separates real failures from items a human must judge: page and console errors, horizontal overflow, accessibility (axe-core), keyboard focus visibility, touch targets on phones, clipped text, every listed state (empty, loading, error, success) and user flow, at phone, tablet and desktop widths in light and dark mode, plus visual changes against an accepted baseline. Use when the user says 'test the prototype', 'validate', 'QA this', 'is it ready for review or handoff', 'check accessibility', 'did anything change visually', after `prototype` finishes a wave, and before `handoff`. Do not use to audit DS compliance of the code (`review`) or to compare a developer build with the design (`verify`). Also use for the same request in any language."
---

# Validate: prove the prototype works

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

Script: `V=<kit>/skills/validate/scripts/validation.py` (`--help` lists every command); it runs `validate.js` (Playwright, installed Chromium; never `playwright install`). Folder: `<paths.validation>/<app>/` (default `docs/validation`).

Goal: a prototype that was checked, not only generated.
Reason: a screen that looks right in one screenshot can still break at another width, in dark mode, with a keyboard, or in its empty state.

## Step 1. Plan what to check

- Load `kit.config.json`. Pick the app. `react` / `vue`: run the app's `build` first (the check opens `dist/index.html`). `html`: the entry file opens directly.
- First time: `python3 $V init --app <id>` writes `plan.json`. Replace the example with the app's own:
  - **screens**: one per screen (S-ids from the `define` plan or the `annotate` spec), with its `route` (`""` for the entry, `#/settings` for hash routes);
  - **states** per screen: every state the screen has (empty, loading, error, success, long content), each with a `prepare` script run in the page (clear or seed `localStorage`, click a control, set a mock flag). A state you cannot reach without code changes → list it in the report as not checked; never fake it;
  - **flows**: the user flows of the wave, as steps (`click`, `fill`, `select`, `press`, `goto`, `wait`, `expectVisible`, `expectHidden`, `expectText`, `expectUrl`), each with the acceptance criterion it proves.
- Accessibility needs axe-core in the project: `npm i -D axe-core`. Not installed → ask once whether to install; without it the report lists accessibility as skipped, never as passed.

## Step 2. Run

`python3 $V run --app <id>` (defaults: 390, 768 and 1280 px; light and dark when `ds.json > theming.mode` has both). It writes `<run>/report.md`, `report.json`, `shots/` and `diffs/`, and exits 1 when anything fails.

| Result | Meaning | Examples |
|---|---|---|
| **Fail** | A real defect | page or console error, horizontal overflow, axe critical or serious, a flow step that fails, a page that does not open |
| **Needs a human** | The script cannot decide | touch target under 44 px on phones, clipped text, no visible focus ring, axe moderate or minor, a visual change against the baseline |
| **Skipped** | Not checked, and why | axe-core not installed, no baseline yet |

## Step 3. Read the report like a reviewer

- Open `report.md` and look at the screenshots of every failing or flagged view (Read the PNG). Confirm each failure is real before you fix it.
- Fix failures in the app with `prototype` rules (DS only, gates for anything new), rebuild, run again. Repeat until **Fail (0)**.
- For each "Needs a human" item: fix it, or ask the user and record why it is acceptable (a decision in the log, see `context`, or a line in the report under the item). Never mark it fine on your own.
- Visual changes: show the diff images (`diffs/`) and the user decides whether the change is intended. Only then accept the new screenshots: `python3 $V baseline --app <id>` (first run: accept after the user has looked at the screenshots).

## Step 4. Report

Short: run folder; counts (fail / needs a human / skipped); failures fixed and how; items the user accepted and why; states or flows not checked and why; baseline updated or not. A prototype goes to `handoff` only with **Fail (0)** and every "Needs a human" item answered.

## Rules

- Never edit the plan to make a failing check disappear; fix the app or record the user's decision.
- Never accept a baseline without a human looking at the screenshots.
- Never report a skipped check as passed.
- Never change DS components or tokens to make a check pass; DS problems go to `document`.
