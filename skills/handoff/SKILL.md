---
name: handoff
description: "Package a prototype into ONE zip for BA, QC and developers: feature list, changelog, QC checklist, Markdown spec per unit (route, how to reach and Figma link per screen instead of images), AGENTS.md with reading paths per role. Two modes: one feature (scope filter, optional lock or hide of everything else) or the whole app by version; works for single-file and multi-page apps. The zip has no screen images (they live on the Figma wireflow board), no loose .js files, and stays under the size target. Use when the user says 'package', 'hand off', 'handover', 'send to BA/QC', 'build the x.y.z package'. Use `annotate` for the spec itself, `wireflow` for the Figma board, `share` for the email. Also use for the same request in any language."
---

# Handoff package

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.handoff` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

Rules: run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rules.py list --app <app> --skill handoff` (no app: leave out `--app`) and follow what it prints: `must` rules are never broken, a `should` rule is broken only with the reason in the report, `EXCEPTION` and `OVERRIDDEN` lines say what does not apply to this app. It replaces reading long rule documents; read the DS `rules.md` only when the output says the profile keeps its rules there. `rules.py show <id>` explains one rule ([docs/rules.md](../../docs/rules.md)).

One skill, two modes, one zip format:
- **Feature:** only what belongs to ONE feature. Scope filter, spec, optional lock or hide of the rest.
- **Whole app:** the app by version, no filter. Spec only when the user has one or asks.

Read first: `kit.config.json` (`handoff`, `stack`, `apps`, `deploy`), the DS profile `ds.json` of the app (`apps[].ds`, else `ds`: `version_label`, `tokens.prefix`), the rules (above).
Scripts: `skills/handoff/scripts/pkg.py` (pipeline), `optimize_package.py` (size, blocked files), `optimize_attachments.py` (sample files). Every script has `--help`.
Details: [references/scope-layers.md](references/scope-layers.md) (lock and hide), [references/package-layout.md](references/package-layout.md) (files, README tables, size steps).

## Step 0. Questions
Ask everything missing in one round (at most 4 questions), not one by one:
1. **Mode:** one feature or the whole app. "Package app X" = whole app; a feature name = feature.
2. **Source:** the app (`kit.config.json > apps[]`), an existing spec, a Figma source.
3. **Work-item code and version x.y.z.** The code is required: it names the folder and the zip (`handoff.zipName`). No version: next after the last one in the previous package changelog; else 1.0.0.
4. *(Feature)* **Scope:** screens, flows and parts in and out. Given only a name: propose the list from the prototype and ask to confirm. Include the flow list (main, alternate, error/cancel, start, end): it feeds the wireflow.
5. *(Feature)* **Prototype treatment**, ask every time:
   - (a) **keep**: full prototype; the spec lists how to reach each screen.
   - (b) **lock**: separate copy; out-of-scope UI stays visible and normal, a click shows a DS toast "outside the scope".
   - (c) **hide**: separate copy; features and modules not in scope are not shown. No toast (no way in). Readers lose product context; layout may shift where space closes.
   For multi-page apps say the cost: (a) pulls in the whole app; (b) and (c) keep only feature pages but need a layer.
   "Hide the unfinished parts" = (c); still confirm the hide list in step 3.
6. *(Feature that changes existing screens)* **Style baseline:** what "before" is (previous package, old build, screenshot, Figma). None: describe current style and write "no baseline".
7. **Figma link for the wireflow** (required when there is a spec and `handoff.figmaRequired` is true): the package has no screen images, so the board is the only place to see screens and the target of every screen's Figma link. Ask for the file or page for this work item. Later versions reuse `figma_file`/`figma_board` from `pkg.json`. No link: stop at step 8, do not deliver. Create a new Figma file only when the designer agrees and picks the team.

No answers available (unattended run): need items 1, and 4 + 5 for a feature. Choose (a) and say so at the top of the report.

## Step 1. Read the source
- Work on a copy. Note title, version, DS version label (`version_label`) of the prototype; compare with `ds.json > version`. Mismatch: warn and suggest `sync`; do not fix here.
- The package states ONE DS label, the one of the packaged prototype. When the profile has moved on (a later DS version than the prototype), write the prototype's label into `pkg.json > ds_label` (or set `handoff.dsLabel` to `prototype`). `finalize` compares the label with the pages' `<meta>` and with `spec/index.md` (`handoff.dsLabelCheck`).
- **Multi-page app** (`apps[].type` is `multi`, or one file per feature with its own router): take the whole app folder, not one file. Find pages, shared folders, the route table and how data passes between pages (`sessionStorage`, `localStorage`). Serve over HTTP (`python3 -m http.server`), never `file://`. Large sample data: tell the user the expected package size.
- Existing spec: read it all; keep what BA/designers wrote. Feature mode only filters it.

## Step 1b. Build by stack

| `stack` | Before packaging |
|---|---|
| `html` | Copy the files. `multi` apps: run `apps[].build`, then `apps[].check` when set. |
| `react`, `vue` | Run `apps[].build` (Vite with a single-file plugin, e.g. `vite-plugin-singlefile`, hash router): one self-contained HTML per entry, no separate `.js`. Package the built HTML, never `src/`. A build that still emits `.js` chunks: fix the build config, do not ship it. |

Layers in step 4 are injected into the built HTML (`pkg.py layer --into dist/*.html`), not into source.

## Step 2. Checks before packaging
- Latest `validate` report for the app is newer than the last change and shows **Fail (0)**, with every "Needs a human" item answered. Missing or failing → run `validate` first; never package around it.
- No hex, `rgb()` or hard-coded values where a DS token exists (`ds.json > tokens.prefix`).
- Footer version label matches the DS version.
- No console errors (blocked web fonts in a sandbox are fine).
- List every local component (`kit.config.json > local.prefix`) so BA knows.

## Step 3. Scope filter *(feature mode)*
- Pick the spec units and screens of the feature. Drop demo-only parts (decorative header, entry points already in production) unless the user keeps them.
- **Multi-page:** pick by **page**: pages with feature screens **plus** every page they link or hand data to. Linked but out of scope: (a) must include it (else links break) and mark "out of scope"; (b) leaves it out and locks every way in; (c) leaves it out and hides every way in. Copy only shared files the kept pages load: `pkg.py proto --pages <page> [<page> …] --into <package>/prototype --app <id>` copies the pages and the files they load (href, src, srcset, `url()`, `@import`, file names quoted in scripts, followed through CSS, JS and JSON), keeps relative paths, leaves other pages out and lists them (lock or hide every way in) and lists references it could not find (paths built at run time: check those screens in the browser). Bare file names quoted in scripts (no folder, often sample data) are only counted (`--verbose` lists them). Pages of the app folder that no static reference reaches (a page registry or router in a script) are listed too: decide for each one like a linked page. A linked DS file (`css.load: "link"`) comes with the pages.
- Make two lists: units without a screen, screens without a unit. Do not force matches.
- Everything dropped goes to "Out of scope", so BA knows it is on purpose.
- **(c) hide list**, two levels: module (top navigation item and its page) and feature (button, menu item, tab, filter, column, dialog inside a kept page). Each row: readable name, level, location, stable selector (`data-*`, `id`, `aria-label`; never visible text or position), reason. Confirm with the scope. Never hide what the feature flow passes through; in doubt, ask.

## Step 4. Prototype of the package
- **Whole app, or (a):** use it as read. Feature mode adds an "Entry points" table (clicks or route per screen) to the spec.
- **(b) lock** and **(c) hide:** a layer added on top. Never change DS components, tokens, app code or behaviour of kept parts. One package uses one treatment, never both.
  1. `pkg.py init --pbi <code> --title "<feature>" --version x.y.z --app <id> --treatment lock|hide` (once per work item), then fill `pkg.json > lock` or `> hide` (keys in [scope-layers.md](references/scope-layers.md)).
  2. `pkg.py layer --config pkg.json --kind lock|hide --into <every page in the package>`. Re-run after each change: it replaces the previous layer.
- **Lock rules:** never disable (`disabled`, `aria-disabled`, dimming, cursor, colour). Block with a capture-phase listener before app code runs (click, Enter/Space, focus and typing in fields, drop, dragover, paste), then show the DS toast (`lock.toast`: the app's toast function with its `args`, or the DS toast classes and icon from `catalog.md` / `ds.json > toast`). No stacked toasts. Wrap the app's navigation functions (`nav_functions`, keys mapped to files in `page_keys`) and `window.open` as a fallback; pages are compared on resolved paths. Read how each function resolves a path: relative to the app root (`X.nav('chat/index.html')` from `notes/`) needs `{"name": "X.nav", "base": "app"}` (or `nav_base: "app"`), else every valid page change is blocked. A control in scope on one route only: `allow_when`. State the package needs on load (a dismissed notice of another work item): `seed` (its own script at the top of `<head>`, before the app's scripts, so code that reads it while loading sees it). A page of the package that must not open from one control (the same page with another feature's hash in a new tab): `open_block` (regex). Scan pages for static `<a>`, `window.open`, shortcuts so the list is complete.
- **Hide rules:** `display:none !important` block on stable selectors (also hides late-rendered and mobile tab-bar items). Hide containers left empty (group titles, dividers, button groups, stat cards). Hidden default tab: switch to the first visible one through the layer. Shortcuts of hidden features: stopped silently. A route of a dropped page: redirect to the package entry.
- `pkg.py layer` writes `<meta name="x-handover">` with treatment and version; record the same in "Out of scope" of the spec.
- Test with Playwright at 400, 768, 1280 px (`pkg.py smoke <package folder>` opens every route of `screens.json` at `handoff.smokeWidths` and reports errors, 4xx, broken images, horizontal scroll; the checks below still need the flow): the feature flow works; (b) every out-of-scope entry shows the toast, URL and page state unchanged; (c) every hidden element has `offsetParent === null` and is not in Tab order, no visible way out of scope, layout not broken; no console errors.
- **Multi-page:** folder `prototype/` keeps relative paths (pages, shared files, images, fonts) and the entry address. The layer goes into **every page** of the package; when pages are built from a shared shell, add it at the shell and rebuild. No link may point to a file not in the package.

## Step 5. Feature list
Scan the UI and fill `requirements/checklist-feature.csv` (header written by `pkg.py init`): code (F01…), feature, group, screen/location, behaviour, inputs, expected result, status (full, demo, mock), dependencies. Mark mock data clearly. Add "Out of scope" rows (feature mode: also what step 3 dropped) and Figma deviations. Unsure: "needs confirmation", never guess.

## Step 6. Spec *(feature mode: required; whole app: only with a spec or on request)*
Run `annotate` on the package prototype. The spec is Markdown in `spec/`; `design-spec.html` only when someone needs a visual copy. Make sure that:
- `spec/index.md` starts with name, version, date, packager, relative prototype path (`prototype.html` or `prototype/<entry>`), DS version label.
- **Wireflow** (feature: required): `spec/flows.md` (text per flow, Mermaid) and `requirements/flows.json`. Flows confirmed in step 0. Each flow has a demo link (`url` in `flows.json`; `deploy.site` when deployed). (b): edges leaving the scope end at an "Out of scope" box. (c): no edges out. Unverified edges are dashed and listed as "needs confirmation".
- Sections "Prototype entry points" and "Out of scope" ((b): still visible, toast on click; (c): the hide list table).
- **Multi-page:** `spec/cross-page.md` under the wireflow: pages and routes, data hand-over, direct-open behaviour, shared state. Entry points name file and route (`prototype/<page>.html#/…`).
- **Style per pin** (required): computed style at the captured state, written as DS token names, never raw values when a token exists: element and component (class, variant, size); colours, radius, shadow, type, sizes, spacing, icons; states present (default, hover, focus, active, disabled, error, empty; "not captured" otherwise); with a baseline, "Style change" lines `property: before → after`, "New", or "No style change"; local components and untokenised values flagged.

## Step 7. Appendices
1. **Feature list:** step 5.
2. **Changelog** (`requirements/changelog.md`, one `## <version> · <date>` section per version): added, changed, removed since the last package; the first one says the first-release text of the locale. With style notes, a "UI style changes" part grouped by screen. Multi-page: name the files that changed. `pkg.py finalize` keeps the last `changelog_keep` (2) versions.
3. **QC checklist** (`requirements/checklist-qc.csv`): one happy-path case per feature; one end-to-end case per wireflow flow plus each branch; edge and error cases for forms; (b) a toast case; (c) hidden-element, Tab, direct-route and shortcut cases; style cases for each "Style change". Multi-page adds cross-page cases: full flow across pages, reload mid-flow, **open the target page directly**, Back/Forward, unknown hash, shared data (theme, samples) in sync, opening over HTTP as README says. Each case names the start page and route. Derive only from spec and UI; never invent.

4. **Decisions** (project with a decision log, see `context`): `decisions.py list` filtered to the feature scope (screens, R-ids, app). Copy the `approved`, `implemented` and `verified` ones into `spec/decisions.md` (id, title, status, who decided, why) so developers see the reason behind the design. Never include `proposed`, `rejected` or `observed` ones as decisions; list open `proposed` ones under open questions.

CSV files are UTF-8 with BOM (Excel).

## Step 8. Wireflow on Figma (required with a spec, before zipping)
1. `pkg.py capture --manifest manifest.js --shots shots --base <served package prototype>`: 2x captures, `shots/changed.json` lists new and changed screens. Look at only those. First kit run on a board built from an earlier package (no previous kit capture): add `--baseline <screens.json or image folder of that package>`, so the list compares with the delivered version (route, pin styles, pixels; images at another scale are resized) and `changed.json` says why. Routes in `screens.json` keep the query of the last `goto` (`?demo=1`). `--only S05,S07` re-captures just those screens. Every iframe a step or pin uses must be in `manifest.frames` (capture stops otherwise); older frame-prefixed steps (`fclick`) are read as `click` + `in`.
2. Run `wireflow` with the PNGs of `shots/` and `requirements/flows.json`. Page name contains `[<code>] <feature>`; board name `Wireflow · <feature> v<version>`. Later versions: **update in place, keep the board node**, replace only changed screens (sent links must not break). Never delete or move content the kit did not create.
3. Map screen → node into `pkg.json` (`figma_file`, `figma_board`, `figma`): run the `mapjs` code from `wireflow`'s `figma_wireflow.py` in `use_figma`, save the result, then `figma_wireflow.py setmap --config pkg.json --json <result> --file <fileKey>`. Fill the demo links with `wireflow`'s `demo_links.py fill` (captures of the package copy: add `--page-root prototype` when the package folder was served, so links keep the page folder). It writes `flows.json` and the "Open demo:" line under each flow heading of `spec/flows.md` (`--md` for another path); a flow without a heading is a WARN to fix by hand.
4. With `handoff.figmaRequired`, `pkg.py finalize` stops with an ERROR while `figma_file` is missing or a screen has no node. `--allow-missing-figma` only when the user accepts a draft: `pkg.json > status` becomes `awaiting-figma` (screens in `awaiting_figma`, spec lines "Figma: <not on the board yet>"). Never send a package in that state.
5. **Awaiting Figma** (a new screen in a patch version, board not updated yet). Order: `handoff` (finalize `--allow-missing-figma`, draft) → `wireflow` (add or replace the cards, `setmap`) → `pkg.py relink --pkg "<package>" --config pkg.json --zip` → `share`. `relink` only writes the Figma links (screens.json, spec "Figma:" lines and Figma columns, AGENTS board link), sets `status: "final"` and rebuilds the zip; it stops while a screen still has no node. Draft the email only after `relink` (the zip changes).

## Step 9. Zip
1. Name: `pkg.py name --config pkg.json` (from `handoff.zipName`); the folder inside has the same name. The version is in `README.md` and the changelog, not in the name. Layout and README tables: [package-layout.md](references/package-layout.md).
2. Sample attachments (PDF, PPTX, DOCX, XLSX): `python3 -I optimize_attachments.py <files> --out "<package>/attachments"`. Keep files meant to test size limits as they are and say so in README. Still over ~10 MB, or video: leave out, put a download link in README.
3. `pkg.py finalize --pkg "<package>" --shots shots --config pkg.json --zip`: slim `screens/screens.json`, remove screen images (also sentences that point at `screens/*.webp`), refresh the "Figma:" line of each screen and the Figma column of `spec/index.md` from `pkg.json > figma`, archive replaced units to the archive file (`handoff.specFiles`), trim changelog, write `AGENTS.md` (`handoff.itemLabel`, `handoff.grepLabels`), check the DS label, file references (README, AGENTS, spec: ERROR; changelog: WARN), CSV headers (`handoff.csv`; `pkg.json > csv` overrides it for a package that keeps the headers of its earlier versions), run the spec check of `annotate` and print every WARN and ERROR line, then `optimize_package.py` (inline JS, base64 → WebP in `assets/`, remove blocked files, zip at level 9). Read every WARN; fix or report each. Project steps around it: `handoff.pre` / `handoff.post`.
4. Over `handoff.maxZipMB`: follow the size steps in [package-layout.md](references/package-layout.md). Never rename `.js`, password-protect, split, nest zips or obfuscate code to pass mail filters.
5. `pkg.py smoke "<zip>"`: unzips to a temp folder, serves it over HTTP **from the package folder** (images are in `assets/` next to `prototype/`), opens every route of `screens.json` at `handoff.smokeWidths` in Chromium and reports page errors, console errors, 4xx, failed requests, broken images, horizontal scroll, and blocked files left in the zip. It must print `OK`. Then walk the feature flow once in the unzipped copy (`--keep` keeps it): routes alone do not run clicks.
6. Keep the work-item source (`pkg.json`, manifest, generators, baseline `screens.json`) in `<handoff.dir>/<code>/` for the next version. Captures stay out of the zip.

## Step 10. Final check
- Wireflow board on the work-item page, title has the version; every screen in `screens.json` has a working `figma` link.
- Spec check passes; every unit has a screen or is listed as unmatched; `screens/` holds only `screens.json`; `AGENTS.md` exists when there is a spec.
- Every pin has style notes; values match computed style; every `before → after` has both sides.
- (b): no disabled or dimmed out-of-scope UI, toast on click. (c): hidden items invisible and not focusable, no empty containers, layout fine at 400/768/1280 px, hide list in the spec.
- No real personal data; mock features marked. Nothing outside the feature without a stated reason.
- Zip under `handoff.maxZipMB`, or the user was told why and how to send it instead.

## Step 11. Report (short)

End the report with the next step after development: `verify` compares the developers' build with this prototype.

Name and version, zip name and size before → after, mode and treatment, number of units, screens, flows and edges (unverified edges), features, test cases, style changes and the baseline used, unmatched items, out of scope, files removed, warnings (DS version mismatch, mock data, local components, items BA must confirm). Multi-page: pages kept and dropped, cross-page edges, size per part, how to open.

## Rules
- Never change, republish or move the source app.
- Keep BA content word for word; add no rules.
- Never invent screens, features, test results or style values; write "needs confirmation".
- Never widen the scope on your own; ask.
- Wireflow edges only when verified on the prototype or stated in the spec; dashed otherwise.
- (b) never disables; (c) hides with a layer (`display:none`), never deletes app code; never mix (b) and (c).
- No executable or script file in the zip; code lives inside HTML.
- Screen images live on the Figma board, not in the zip.
