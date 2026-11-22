---
name: validate
description: "Check a prototype in the browser and write one validation report that separates real failures from items a human must judge: page and console errors, horizontal overflow, accessibility (axe-core), keyboard focus visibility, touch targets on phones, clipped text, every listed state (empty, loading, error, success) and user flow, at phone, tablet and desktop widths in light and dark mode, plus visual changes against an accepted baseline. Use when the user says 'test the prototype', 'validate', 'QA this', 'is it ready for review or handoff', 'check accessibility', 'did anything change visually', after `prototype` finishes a wave, and before `handoff`. Do not use to audit DS compliance of the code (`review`) or to compare a developer build with the design (`verify`). Also use for the same request in any language."
---

# Validate: prove the prototype works

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.validate` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

Rules: run `python3 <kit>/scripts/rules.py list --app <app> --skill validate` (no app: leave out `--app`) and follow what it prints: `must` rules are never broken, a `should` rule is broken only with the reason in the report, `EXCEPTION` and `OVERRIDDEN` lines say what does not apply to this app. It replaces reading long rule documents; read the DS `rules.md` only when the output says the profile keeps its rules there. `rules.py show <id>` explains one rule ([docs/rules.md](../../docs/rules.md)).

Script: `V=<kit>/skills/validate/scripts/validation.py` (`--help` lists every command); it runs `validate.js` (Playwright, installed Chromium; never `playwright install`). Folder: `<paths.validation>/<app>/` (default `docs/validation`); every command takes `--dir <folder>` to keep plan, runs and baseline elsewhere (for example the scratchpad during a trial).

Goal: a prototype that was checked, not only generated.
Reason: a screen that looks right in one screenshot can still break at another width, in dark mode, with a keyboard, or in its empty state.

## Step 1. Plan what to check

- Load `kit.config.json`. Pick the app. `react` / `vue`: run the app's `build` first (the check opens `dist/index.html`). `html`: the entry file opens directly.
- First time: `python3 $V init --app <id>` writes a starter `plan.json` read from the app: one screen per page and hash route it finds (`href="#/…"`, `"#/…"` in route tables, router paths), one flow per hash link, and the ids of the main controls as selector hints (`_selectors`). `--blank` writes the example template instead. One page only: `--page <file>` (relative to the app folder or the project; a built bundle such as `dist/index.html` works, so routes that exist only in the build are found), `--routes '#/,#/n/1'` to set the routes yourself, `--url <URL the page is served at>` for an app served over HTTP (routes are then hash-only, and the page is opened in Chromium so routes and ids that its scripts build are found: hash links, `data-route` attributes, the hash a tab button sets, selectors of visible controls inside the content root `--content-root`, else `kit.config.json > validate.contentRoot`, default `main, #app, [role=main]`, never the shell; screens are named from the title and heading; other buttons of the content root are each clicked once in a fresh page, never one named like delete or reset, and a hash they set becomes a screen; with no route in the files the URL as given is the first screen; `--no-browser` reads the files only). Serve the page before `init --url`. When `init` still writes the sample plan it prints a NOTE: pass `--routes` with concrete routes. Routes with a parameter (`#/n/:id`) are listed under `_paramRoutes`: fill in a real id. Check every route, then complete it:
  - **screens**: one per screen (S-ids from the `define` plan or the `annotate` spec), with its `route` (`""` for the entry, `#/settings` for hash routes);
  - **states** per screen: every state the screen has (empty, loading, error, success, long content), each with a `prepare` script run in the page (clear or seed `localStorage`, click a control, set a mock flag). A state you cannot reach without code changes → list it in the report as not checked; never fake it;
  - **named states** need no code: `"brand=<value>"` (any `ds.json > theming` key) and `"text=200%"` (root font size doubled: scales rem/em text like the browser font setting; px sizes stay, and it is not mobile system text scaling, which needs a real device or the platform setting). `plan.states` adds them to every screen; `init` lists the ones the DS offers under `_stateHints`;
  - **axe** runs on every state of the plan at the widest width (default, prepared, named). `"axe": false` on a state or a screen opts out: only with the reason in the report;
  - **plan.prepare**: JS run after every page load of every screen and flow, before their own steps and `prepare`, e.g. to dismiss a shell overlay or a first-visit notice: `"prepare": {"js": "localStorage.setItem('acme:tour', '1')", "reload": true}` (`reload` loads the page again after it). Never copy it into each flow;
  - **flows**: the user flows of the wave, as steps (`click`, `fill`, `select`, `press`, `goto`, `reload`, `wait`, `expectVisible`, `expectHidden`, `expectText`, `expectUrl`), each with the acceptance criterion it proves. A `goto` that only changes the hash keeps the page: after seeding `localStorage` use `{"reload": true}` or `{"goto": "#/", "reload": true}`.
- The app already has a capture manifest (`annotate`, `handoff`): `python3 $V init --app <id> --from-manifest <manifest.js> --base <URL the manifest is served at>` turns its screens into plan screens, each with the steps that reach it (screens it continues from are inlined; `F|…` and `in` frames kept). Screens recorded with clicks run at the manifest width only. Run with the prototype served at the same base URL (the plan keeps it as `url`). Steps without `timeout` wait the plan's `timeout` (copied from the manifest, default 8000 ms, the capture default), so a screen that captures does not fail here on a slow wait. Add states and flows by hand.
- Touch targets: the minimum on phone widths depends on the app's platform (`apps[].platform`, sizes in `kit.config.json > validate.touchTarget`: 44 px by default, 24 px for `desktop`, the WCAG 2.2 minimum). A desktop web app checked at 390 px is not held to the phone size.
- Accessibility needs axe-core: `--axe <axe.min.js or folder>`, env `KIT_AXE_PATH` or `kit.config.json > validate.axePath`, else `node_modules` of the project or the kit. The project has no `package.json` → never install into it; use a copy elsewhere (for example the scratchpad) through one of those. Not found → ask once; without it the report lists accessibility as skipped, never as passed.
- Scope and known findings: `plan.axe` (or `screen.axe`) `{"include": [sel], "exclude": [sel]}` limits axe to the part of the page the work owns. Findings that are known or belong to other work (a shared frame, an intentional DS deviation) go into `<dir>/waivers.json` (or `--waivers <file>`): `[{"check": "a11y", "id": "color-contrast", "selector": "#shell", "screen": "S01", "reason": "…"}]`; `reason` and `check` or `id` are required; `selector` matches an axe node inside it (or the text of a touch, clipped or focus element). Add a waiver only with the user's agreement.
- Dark mode and theme states set `ds.json > theming.<key>.attr` on `<html>` by default. An app that must switch through its own code: `kit.config.json > validate.setTheme` (or `plan.setTheme`), a JS body with `key` and `value`, e.g. `"window.AcmeAppearance.set({[key]: value})"`.

## Step 2. Run

`python3 $V run --app <id>` (defaults: 390, 768 and 1280 px; light and dark when `ds.json > theming.mode` has both). It writes `<run>/report.md`, `report.json`, `shots/` and `diffs/`, and exits 1 when anything fails. A served entry is checked before each screen and flow: when the server does not answer, the run stops with one `ERROR:` line; start the server and run again (never report those views as failures).

| Result | Meaning | Examples |
|---|---|---|
| **Fail** | A real defect | page or console error, horizontal overflow, axe critical or serious, a flow step that fails, a page that does not open, a `must` rule of the rules registry whose check fails |
| **Needs a human** | The script cannot decide | touch target under the platform minimum on phones, clipped text, no visible focus ring, axe moderate or minor, a visual change against the baseline, a `should` or `note` rule whose check fails |
| **Outside the scope** | A rule check of the whole project failed; not about these screens, never blocks | a project-wide `check` command (no `{app}` or `{path}`); `--rules-scope all` makes them count, `--rules-scope STY-001,A11Y-002` limits the blocking checks to those rules |
| **Skipped** | Not checked, and why | axe-core not installed, no baseline yet, a rule check whose server is down or that does not apply to the app |
| **Known / waived** | Matched a waiver; never fails | shared-frame contrast, an accepted deviation, with its reason |

Never reported: text for screen readers only (1×1 box, `clip`, `clip-path`), a file input hidden behind its button, a link inside a sentence (the inline exception of WCAG 2.5.8). Rules: `run` also runs the `check` of every active rule for `validate` (`rules.py check --app <id>`); `--no-rules` skips them.

Contrast findings show the ratio, the required ratio and both colours. Each Fail and Needs-a-human row is marked **new** or **carried over** against the previous run (`--compare <run|report.json>` for another one, `--compare none` to turn off); the report also counts the ones no longer found. axe rows match on rule id, screen view and the text of the failing elements, so a changed selector is not a new finding.

### Parity: two builds of one page

A page rebuilt in another stack (an HTML page and its Vue port) or refactored: `python3 $V parity --a <URL of build A> --b <URL of build B> --plan <plan.json> --dir <folder> [--app <id>]` runs the same plan (screens, states, flows, `plan.prepare`) on both, at 1280 px in the first mode (`--viewports`, `--modes`), and writes `parity.md` and `parity.json`: per screen and state, visible text, controls by role and name, aria states, console errors and screenshot pixels (Pillow); per flow, its result, the URL after each step and `localStorage` at the end. Each row is **Match** or **Differs** with both values; exit 1 when anything differs. `plan.contentRoot` limits text, controls and aria states to the page's own content. For every Differs row: a regression to fix, or an intended change the user confirms (list it in the report with the decision). URLs are compared relative to each side's entry folder, path only (scheme, host and port ignored), so the two builds may run on two servers and a flow that leaves for another page of the same app still matches (`../chat/#/c/1`). Parts that change on every run (clocks, timestamps): list their selectors in `plan.mask` (masked in screenshots, text replaced before text compare); `plan.normalize: ["time"]` also replaces clock times and relative times ("5 min ago") in the compared text.

## Step 3. Read the report like a reviewer

- Open `report.md` and look at the screenshots of every failing or flagged view (Read the PNG). Confirm each failure is real before you fix it.
- Fix failures in the app with `prototype` rules (DS only, gates for anything new), rebuild, run again. Repeat until **Fail (0)**.
- Look first at rows marked **new**: they came with this change. For each "Needs a human" item: fix it, or ask the user and record why it is acceptable (a decision in the log, see `context`, or a line in the report under the item). Never mark it fine on your own.
- Judging accessibility and states by hand: read `references/a11y-web.md` (W-codes), plus `references/a11y-mobile.md` (M-codes) when `apps[].platform` is a phone platform; for the states to list in step 1, `<kit>/skills/prototype/references/states-and-edge-data.md`. Cite the codes in the report.
- Visual changes: show the diff images (`diffs/`) and the user decides whether the change is intended. Only then accept the new screenshots: `python3 $V baseline --app <id>` (first run: accept after the user has looked at the screenshots).

## Step 4. Report

Short: run folder; counts (fail / needs a human / skipped); failures fixed and how; items the user accepted and why; states or flows not checked and why; baseline updated or not. A prototype goes to `handoff` only with **Fail (0)** and every "Needs a human" item answered.

## Rules

- Never edit the plan to make a failing check disappear; fix the app or record the user's decision.
- Never accept a baseline without a human looking at the screenshots.
- Never report a skipped check as passed.
- Never change DS components or tokens to make a check pass; DS problems go to `document`.
