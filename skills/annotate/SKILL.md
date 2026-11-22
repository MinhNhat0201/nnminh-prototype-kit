---
name: annotate
description: "Write or update the design spec for BA, QC and developers from a prototype: split the BA spec into units (one Markdown file per unit), capture every screen and state, pin elements with their computed style mapped to DS token names, record style changes, map units to screens with a confidence level, and draw the business-flow wireflow (flows.json + flows.md with Mermaid). Markdown is the source of truth; an HTML viewer with pinned screenshots is generated only when someone needs it. Use when the user says 'write the spec', 'annotate the screens', 'map the spec to screens', 'design notes for dev', 'update the spec for the new version'. Use `wireflow` to put the flow board on Figma, `handoff` to package the spec into a zip, `define` to analyse requirements before any screen exists. Also use for the same request in any language."
---

# Annotate: Markdown spec mapped to prototype screens

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.annotate` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

Rules: run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rules.py list --app <app> --skill annotate` (no app: leave out `--app`) and follow what it prints: `must` rules are never broken, a `should` rule is broken only with the reason in the report, `EXCEPTION` and `OVERRIDDEN` lines say what does not apply to this app. It replaces reading long rule documents; read the DS `rules.md` only when the output says the profile keeps its rules there. `rules.py show <id>` explains one rule ([docs/rules.md](../../docs/rules.md)).

Goal: a reader opens the spec, sees the whole flow first, and every spec unit shows its own screens and design notes, not a design section collected at the end.

Hard rules:
- The business text belongs to the BA. Keep it verbatim. Never rewrite it or add rules.
- Screens and design notes come from the running prototype (capture, DOM, computed style), never from memory.
- When a unit and a screen do not match, say so. Never invent a screen, an edge or a match to fill a gap.
- No images inside the spec. Each screen links to its Figma node (the `wireflow` board); captures stay in the working folder.
- Token names come from `ds.json > tokens.prefix` and `tokens.roles`. Never write a hex or raw px value where a token exists.

Read first: `kit.config.json`, the DS profile of the app (`ds.json`, `catalog.md`; `apps[].ds` when set), the rules (above). Older frontmatter keys of `spec/index.md` are read through `handoff.specFields` (e.g. `{"ds": "<old key>"}`); write the kit keys in new specs. Headings and fixed labels of generated files come from `locales/<language>/annotate.json` (`annotate.h.*`, `annotate.col.*`, `annotate.label.*`); use them so `spec_md.py check` and every reader find the same words.

## 0. Inputs
Two things are needed: (1) the BA spec (Markdown, docx, pasted text, or an older spec to update), (2) the prototype (an app from `kit.config.json > apps`, a file, or a URL). If one is missing, ask one question and stop. Work on a copy when the prototype is not in the repository.

Serve the prototype over HTTP, not `file://`:

| `stack` | How to serve |
|---|---|
| `html` | `python3 -m http.server <port>` in the project root |
| `react`, `vue` | `npm run build` then `npx vite preview --port <port>` (or the dev server); hash routes |

Multi-page apps (`apps[].type: multi`, or `spa` with several entries): first read, from the code, the list of pages, the shared files, the route table, and how data moves between pages (`sessionStorage`, `localStorage` keys, URL parameters). Do not guess.

## 1. Split the spec into units
A unit is a piece of business text that can map to one or more screens: a functional requirement, rule, condition, state, error message.
- Keep the BA codes (FR-01, BR-03). Without codes, number in order (FR-01, FR-02…) and say the codes are temporary.
- Each unit: code, title, verbatim text, numbered sub-rules (FR-01.1, FR-01.2…).
- Cut along the BA's structure. Do not merge or split by your own judgement.

## 2. Inventory the screens
List every screen and state a user can see: main views, dialogs, drawers, empty, error, loading, important hover or disabled states. Look for routes, `data-screen`, `section[id]`, dialog classes, view-switch functions.
Table: `S01 | name | how to reach | state`. Screen codes are stable (S01, S02…; S03b for a second state) and name the image files.
Multi-page: add columns **page (file)** and **route**, plus a hand-over table (from, to, action, data key, behaviour on direct open). Verify by running, not only by reading code.

## 3. Capture
Write a manifest and run `scripts/capture.js` (format: [references/manifest.md](references/manifest.md)):

```
node skills/annotate/scripts/capture.js <manifest.js> <shots dir> http://localhost:<port>/ [--only S03,S04]
```

- Scale 2 (device scale factor) so text stays sharp when zoomed; phone frames (390 px wide) use `scale: 3`. Pin positions are in %, measurements in CSS px.
- Screens of one flow with `cont: 1` run in the same tab, so data handed between pages survives.
- Each pin stores `style.props` (computed style) and `style.tokens` (DS token names with the same value, grouped by role; several names when several match: list them, do not pick for the designer).
- `next` gives the exits (edges) of a screen; their positions become the rings on the wireflow.
- Chromium and Playwright must already be installed. Never run `playwright install`. If capture is impossible, stop and tell the user; never draw a substitute image.

## 4. Review every capture
Open each PNG with Read (on an update: only new or changed screens). Check: right screen, right state, not blank, layout not broken, pins on the right element. Wrong: fix the manifest and capture again. Keep the PNGs in the working folder for Figma (`wireflow`) and for the HTML viewer; do not put them in the spec.

## 5. Map units to screens
Match in this order: (1) the spec names the screen, (2) spec keywords equal real labels, titles, buttons, messages on the screen, (3) flow order, only when 1 and 2 are not enough.
- A unit may have several screens; a screen may serve several units (show it under the main unit, link from the others).
- Confidence per pair: High (named or same label), Medium (from flow order), Low (guess). Ask the user about Low pairs or put them under "Not matched".
- Always two lists: units without a screen, screens without a unit. Never force a match.
- Save `requirements/spec-map.json`: `[{unit, screens[], confidence, reason}]`.

## 6. Wireflow
The spec opens with the business flow: screens joined by arrows labelled with the action.
1. **Flows** from the spec (BA steps) and the prototype (handlers, routes). Each flow: name, start, steps, branches (condition, error, cancel), end. Main flow first. A flow that only the prototype has is listed with the label "prototype only".
2. **Edges**: source, action (exact label on screen), target, condition. Put them in the manifest `next`. An edge you cannot verify is still drawn, dashed, labelled "needs confirmation". Spec and prototype disagree: draw the prototype, record a "Deviation from spec". Unclear order: ask the user once with a proposed flow list.
3. **Nodes**: one per screen state, with code, name, unit code, and a ring at each exit.
4. **Cross-page edges** (`xpage` in screens.json) carry the label "Page change" and both files and routes. If a page behaves differently on direct open (no handed-over data), add a "Direct open" node and capture it.
5. Branches go on their own row headed "From Sxx, when <condition>". A return to a known screen is a "Back to Sxx" chip, not a duplicate node.
6. **Scope**: in a scoped handoff, edges that leave the feature end in an "Out of scope" box.
7. Screens in no flow are listed as "Off-flow screens" so nobody thinks they were missed.

Write `requirements/flows.json` (format in [references/spec-format.md](references/spec-format.md)) and the text version `spec/flows.md`: numbered `S01 → [Click "Create"] → S02` lines (multi-page: add file and route), then a ` ```mermaid ` `flowchart LR` block. Each flow starts with its demo link line when `flows[].url` is set (the `wireflow` skill fills it from `deploy.site`).

## 7. Design notes per unit
From the DOM and CSS in the captured state, one row per pin:
- DS component and variant (by class, or by component name in `react`/`vue` using `catalog.md > components.map`), control size.
- States on screen and when they appear or disappear.
- Real content: labels, placeholders, error text, exactly as shown.
- Token per property from `style.tokens`. No hex or px where a token exists.
- Style change against the previous version: `property: before → after`, or "New", "No style change", "No baseline to compare". Generate with `spec_md.py styles shots/screens.json --baseline <old screens.json>`.
- Spec says A, screen does B: a "Deviation from spec" line. Do not fix either side.
No vague notes ("friendly UI"). Every note must be checkable on the screen.

## 8. Write the Markdown spec (source of truth)
One file per unit, readable alone, grep-able by code. No CSS, no images. Layout and templates: [references/spec-format.md](references/spec-format.md).

```
spec/index.md        frontmatter (pbi, title, version, date, ds, prototype) + units, screens, Not matched, Out of scope, Deviations
spec/flows.md        text wireflow + Mermaid
spec/FR-01.md …      one file per unit; each screen is "### S01 · <name>" with route, how to reach, Figma link
spec/cross-page.md   multi-page prototypes only
screens/screens.json requirements/flows.json requirements/spec-map.json
```

`cross-page.md` and `archive.md` are the default names; a project may rename them in `kit.config.json > handoff.specFiles` (`crossPage`, `archive`; `legacy` lists older names still read as special files, never as units).

- `ds` in the frontmatter is the DS version label (`ds.json > version_label`) of the version you read.
- Pin code `S01-2` = screen and pin number in screens.json (same number as on the viewer image).
- Links between files are relative (`FR-02.md`, `flows.md#WF-01`), never private URLs.

**Cross-page contract** (multi-page): four tables in `spec/cross-page.md` (pages and routes; data handed between pages; direct open; shared state), all values from code and a real run. Unverified values: "Not verified". Mock data is marked as mock.

Check: `python3 -I skills/annotate/scripts/spec_md.py check <folder>` must show no `ERROR:`. Handle every `WARN:` (add the screen to a unit or to "Not matched"; note a DS version mismatch).

## 9. HTML viewer (only when someone asks)
Default: do not make it. When BA, QC or the user wants pinned screenshots and an image wireflow:

```
python3 -I skills/annotate/scripts/spec_md.py html <folder> --img <shots dir>
```

- Writes a self-contained `design-spec.html` next to `spec/`, no JavaScript (mail filters accept it). Images use paths relative to the HTML file: send the HTML with the shots folder. Without `--img`, screen cells show the route.
- The page chrome uses its own `--kit-*` variables (light and dark); the DS bundle is embedded in a low-priority layer.
- Never edit the HTML: fix the Markdown or JSON and generate again.
- Check in a browser at 1280 and 400 px: no broken image, no horizontal scroll, no console error, pin numbers match the pin tables.

## 10. Self-check before delivery
- `check` has no error; every warning handled.
- Every unit has a `### Sxx ·` section or "No screen for this item yet." and is listed under "Not matched"; every screen is used or listed there.
- Business text equals the original word for word.
- Pin codes match screens.json; pins not found at capture say "needs confirmation".
- No hex or raw values where a token exists; frontmatter states the DS version.
- Every flow has a start and an end; edge labels equal real labels; `flows.md` matches `flows.json`.
- Multi-page: every cross-page edge has `xpage` and both ends were captured in one run; `cross-page.md` matches the run.

## 11. Report (short)
Path of `spec/` (and `design-spec.html` if made), text size, flows and nodes/edges (unverified edges; multi-page: pages and cross-page edges), units and screens, pairs per confidence, the "Not matched" lists, deviations from spec, Low pairs the BA must confirm, and a DS version mismatch if the DS moved since the older spec.
