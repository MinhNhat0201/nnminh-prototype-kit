---
name: mockup
description: "Figma handoff for one work item, built from a handoff package or from the prototype code: one page per work item with a Wireflow board (screenshots joined along the flows, via `wireflow`) and a Specs board where every screen is rebuilt as editable layers with auto layout, DS library components and DS variables. A mandatory automatic check must pass: same screens as the wireflow, no frame without auto layout, no raw colour, text, spacing or radius. Use when the user says 'rebuild the screens in Figma', 'Figma specs', 'Figma handoff', 'draw the prototype in Figma with our components'. Only the flow board: use `wireflow`. A zip package: use `handoff`. Also use for the same request in any language."
---

# Figma handoff: Wireflow + Specs

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.

The result is **one Figma page per work item** with two boards:

| Board | What | How |
|---|---|---|
| `Wireflow` | Prototype captures joined along the flows | `wireflow` skill; never rewrite it here |
| `Specs` | One frame per wireflow screen, rebuilt as editable layers at the capture viewport size | Step 3, checked in step 4 |

The handoff is done only when step 4 returns `pass: true`, or when every remaining item was accepted by the user and is listed in the report.

Scripts: `S=skills/mockup/scripts`. Every script has `--help`.

## Step 0. Inputs and scope
1. **Screen source**, one of:
   - Handoff package (`handoff`): unzip into its own scratchpad folder. Use `screens.json`, `requirements/flows.json`, the images and the spec units (style notes, tokens, components per screen).
   - Prototype code under the app path: run `annotate` up to the capture step for `screens.json` and DOM notes (classes, tokens). Write `flows.json` from the flow agreed with the user; never infer flows.
2. **DS libraries:** `python3 $S/spec_audit.py libs [--platform web|mobile|tablet]`. It prints `ds.json > figma` (libraries, collections, modes).
   - It fails when `ds.json > figma.libraries` is empty: **stop**. Suggest `adopt` (it pushes the DS variables and styles to Figma) or publishing the DS library in Figma and adding it to `ds.json > figma.libraries`. Never build with raw values instead.
   - Pick the library by platform: web apps (responsive included) use the `web` library; native or mobile screens use the `mobile` library. A work item with both gets two boards (`Specs · Web`, `Specs · Mobile`, locale key `mockup.specsBoardPlatform`).
3. **Target Figma file:** link and page from the user (edit rights). `create_session` once and reuse the session id. Page name: `[<work-item code>] <feature>` (same as `wireflow`). A `node-id` that is a page: build there; a frame: ask. Never delete pages or nodes outside the two boards this skill made.
4. **Library check:** `get_libraries` for the target file. Every library from step 0.2 must be in `libraries_added_to_file`. Missing: **stop** and ask the user to add it (Assets › Libraries). Never substitute raw colours or numbers.
5. Read the DS version label of the prototype (footer, `<meta name="ds-version">`) for the board header. It differs from `ds.json > version`: remind the user and offer `sync`.

Before the first `use_figma` call: load `figma-use` (mandatory). Before the first write: also load `figma-generate-design`. Pass `skillNames: "figma-use,figma-generate-design"` on every write.

## Step 1. Screen list (agree before building)
Table: `screen id | name | flow | source (image, route) | DS components | local parts | outside DS`.
- **Id and name** exactly as in `screens.json` and the wireflow (`S18a · Paused`). Both boards use the same ids, or step 4 cannot compare them.
- **DS components:** from the spec style notes or DOM classes, matched to library components via `ds.json > catalog` (`components.map`) and step 3a. When `catalog.json` has a `figma` entry for the component (`component`, `key`, `node`), use it first; a code component without one is matched by name and reported so `document` can record the mapping.
- **Local parts** (`kit.config.json > local.prefix`): look them up in `local.registry` (description, tokens). In Figma build them as auto-layout frames with the same variables, named `<name> · <class>`. Never create components in the DS library.
- **Outside the DS on purpose:** simulated OS chrome (status bar, home screen), other apps' logos or icons, content images (photos, avatars). Name them with the prefix from locale key `mockup.exemptPrefix` so step 4 skips them, and list them in the report.
More than 5 new screens, or parts not in the DS: show the list to the user before building.

## Step 2. Wireflow
Run `wireflow` steps 1–4 with `--page-id` = the work-item page. Reuse the package's `flows.json` and images. Keep the board `rootId` as `WIREFLOW_ID`.

## Step 3. Specs board (rebuilt as layers)
Frame `Specs` to the right of the Wireflow board, 200px apart: horizontal auto layout, padding 64, gap 80, white fill. Each screen is a direct child, in wireflow order.

### 3a. Find library resources (once per work item)
- One `search_design_system` pass, limited (`includeLibraryKeys`) to the platform library. Collect the components (button, icon, app bar, toast, dialog, sheet, tag, input…) and variables: colour roles (bg, text, icon, stroke), spacing, radius, text styles.
- Map CSS tokens to Figma variables by role and name: `ds.json > tokens.roles` gives the CSS prefix per role; the variable sits in the collections of `ds.json > figma.collections` with the same path (for example `--acme-text-secondary` → `text/secondary` in the semantic collection). No matching variable: list it under "no token"; never type a number.
- Import once per `use_figma` call: `importComponentByKeyAsync` / `importComponentSetByKeyAsync`, `importVariableByKeyAsync`, `importStyleByKeyAsync`. Never copy and detach library components.

### 3b. Build rules (step 4 checks each)
1. **Auto layout everywhere:** every frame with children uses `figma.createAutoLayout()` or `layoutMode`. No x/y inside a screen.
   - Overlays (scrim, floating toast, popover, sticky bottom bar): `layoutPositioning = 'ABSOLUTE'` inside an auto-layout parent, with constraints.
   - Gaps: an auto-layout spacer set to `FILL`, never an empty positioned frame.
2. **Sizing:** screen `FIXED` at the viewport size. Body `FILL`. Multi-line text `textAutoResize = 'HEIGHT'` and width `FILL`. Buttons and tags `HUG`.
3. **Components:** where the DS has a component, use a **library instance** with the right variant and properties (variant, text, boolean, instance swap). Never redraw buttons, icons or toasts as frames. Icons: library icon instances named as in the prototype (`ds.json > icons.set`).
4. **Variables:** bind every fill, text colour and stroke (`setBoundVariableForPaint`); padding, gap, radius (`setBoundVariable`); text uses a library text style (`textStyleId`) or a font-size variable. A prototype value off the token scale (42px, 13px, 3px): use the nearest step and list it in the report; if it is an intentional deviation in `ds.json > rules`, ask the user. Never type numbers.
5. **Layer names:** screen `<id> · <name>`. Children by role, with the prototype class when there is one (`Header`, `Status message`, `x-panel`, `Done button`). Hand-drawn icons sit in a frame named `Icon …` or `Logo …`.
6. **Real content:** text, numbers and states as in the capture (no lorem). An overlay state (toast, popup) includes the screen behind it.
7. **Modes:** colour variables have the modes in `ds.json > figma.modes`. Build in the prototype's default mode (`ds.json > theming.mode.default`); never switch a collection's mode on your own.

### 3c. Calls
- One `use_figma` call builds 1–3 screens (one for a long screen) and returns the screen ids, instance count and bound-variable count. Set `placeholder = true` while building a screen, then turn it off.
- After each batch: one `get_screenshot` of the new screens, compared with the capture (layout, clipped text, overlaps). Fix the specific problem; never rebuild a whole screen.
- On a `use_figma` error: follow `safeToRetryWithoutCanvasRead` from `figma-use`.

## Step 4. Automatic check (mandatory)
1. `python3 $S/spec_audit.py render --page-id <page> --specs-id <Specs board> --wireflow-id <WIREFLOW_ID> [--platform web] --out <scratchpad>/audit.js`. It fills `assets/spec-audit.js` with a config object: node ids, library names and collection names from `ds.json > figma`, the exempt prefix in the project language. Send the file **verbatim** through `use_figma` (read only).
2. The result has:
   - `pass`;
   - `parity`: screens on the wireflow missing from Specs (`missing`), extra screens (`extra`);
   - `totals`: frames without auto layout, raw fills, strokes, text, spacing, radius, local variables, variables from other libraries or collections (`foreignVar`), instances not from a library;
   - `collections`: variable collections used, with library name; `libraryLookup: false` means library names could not be read, so only collection names were checked;
   - `screens[].issues`: issues per screen.
3. `pass: false`: fix exactly the listed issues and run again, until it passes or only user-accepted items remain (list each). `extra` screens: ask the user.
4. Finish with one `get_screenshot` of the whole page (both boards) as evidence.

## Step 5. Report
- Figma link with the `node-id` of the page, the Wireflow board and the Specs board.
- Flows and screens; step 4 result (`pass`, `totals`); library names and the DS version label of the prototype.
- Table: `id | DS components used | local parts | outside DS | differences from the prototype`.
- List separately: values rounded to the nearest token; parts not in the DS (suggest `contribute` when they repeat across work items); DS rules marked as intentional deviations or "to confirm" (keep them and repeat them).
- Add a line to `kit.config.json > paths.changelog` (link, work item, screens, check result) when the user wants a record.

## Rules
- The source of truth is the prototype and the DS profile. Captures are for layout comparison only; never take colours or numbers from them.
- Never put screenshots in place of UI on the Specs board; images belong on the Wireflow board only.
- Never edit the DS library in Figma, and never create local variables or components to fill a gap. Report it.
- Never edit the prototype from this skill. A wrong screen: fix it with `prototype`, then recapture.
- Audit change (criteria, exemptions): edit `assets/spec-audit.js` or `scripts/spec_audit.py` in the kit; it applies to every later work item. Library and collection names always come from `ds.json`, never from the template.
