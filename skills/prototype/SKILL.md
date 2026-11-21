---
name: prototype
description: "Build new screens, flows or a whole prototype with the project's DS from a written request, a plan wave, reference images or screenshots of another app: map every element to the DS catalogue, reuse DS components first, and stop to ask before any new component or new page. Use whenever the user asks to build, mock up or prototype a screen or flow, 'make it like this image', pastes a screenshot of another app as reference, or wants a screen added to an existing app, even without naming the skill. Do not use to bring an app to a new DS version (`sync`), to change the DS itself (`document`) or to plan from a PRD (`define`). Also use for the same request in any language."
---

# Prototype: build screens with the DS

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

Goal: screens that look like the user's product, reuse DS components as much as possible, and never grow a new component silently.
Reason: the DS is the single source of truth; every home-made component is maintenance debt for every app.


## Step 1. Read configuration and input

- Load `kit.config.json` (`python3 <kit>/scripts/kitconf.py`). Missing → `kickoff`. No DS profile → `adopt`. Note `stack`, the target app in `apps[]` and its `type`.
- Read the DS profile: `ds.json`, `rules.md`, `catalog.md`. `rules.md` overrides everything else here.
- Product context (`paths.context`, see `context`): `python3 <kit>/skills/context/scripts/context.py summary`; read UX principles, business rules, constraints and the `approved` decisions in scope. Building against an approved decision → stop and ask; never silently override it.
- Input: the written request, or the wave handed over by `define` (R-ids, S-ids, assumptions, page and component decisions; reuse them, do not ask again).
- Exploration from `explore`: build from the **chosen** direction only (`<paths.explorations>/<slug>/<id>/index.html`, `decision.md`); apply the parts listed as merged. No recorded decision (`explore.py list` shows `exploring`) → stop and send the user back to the decision gate in `explore`. The exploration page is a layout and behaviour reference; still run the gates below for anything not in the DS (`dsFit.missing`). Open reference images with Read. Existing app: read the screens you change, one at a time.
- **Reference images give layout, order, behaviour and ideas only.** Never copy colours, fonts, radii, shadows or icons from them.
- Write an image breakdown: every region and element you see (nav, card, table, form, dialog, empty state…), and the anatomy of unfamiliar patterns (parts, arrangement, relations).
- An image shows one moment. List what it does **not** show: hover, focus, error, empty, loading, scroll, small-screen behaviour. Mark them "not in the image", use the DS component defaults, and never invent behaviour.
- App-specific settings (brand, density, special rules): read them from the existing app or ask. Never change them and never infer them from another app.

## Step 2. Load the DS sources

- Component classes, variants, states and `components.map` from `catalog.md`; tokens from the CSS bundle (`ds.json > css.bundle`) or `tokens.file`. Token values win over prose when they disagree.
- Icons from `ds.json > icons`.
- Never write a token, class, component name or version from memory. Source unreadable → stop and say so; never invent styles.

## Step 3. Map every element to the catalogue

Table: `element | DS component (class / React / Vue name, variant) | match level`.

| Match level | Action |
|---|---|
| Available | Use it as is |
| Close | Use the nearest variant or compose existing components; record the remaining difference |
| Tokens only | Tokens exist, no component → gate (step 4) |
| Missing | Nothing in the DS → gate (step 4) |

For anything not Available, classify it:
- (a) **Missing component:** a new role (stepper, timeline, kanban card).
- (b) **Missing variant or state** of an existing component (tag with close button, input with prefix).
- (c) **Layout or interaction pattern** built only from existing components (list-detail split, command bar, drop zone).

Try composing before you call something missing. Type (c) is almost always buildable from DS components plus spacing, radius and surface tokens. Only (a) and (b) really need the DS to grow.

## Step 4. Component gate (mandatory)

For every Tokens only / Missing element, and every significant Close one: **stop before building that part** and ask with AskUserQuestion (at most 4 questions per round).
Each question states: proposed name, role, where it sits in the image or flow, why the DS component is not enough, and the nearest DS alternative.

| Option | What you do |
|---|---|
| **A. Compose existing** (first; mark "Recommended" when the gap is small or the element is type (c)) | Use the nearest DS component or compose DS components. Nothing new. |
| **B. Local block** | Class prefix `local.prefix`, tokens only, inside a `/* <local.marker>: <name> */` block (one name per block; file location per stack below). Register it: `python3 <kit>/skills/contribute/scripts/registry.py update`, then fill the new entry in `local.registry` (title, kind, status, summary, where, vs_ds, decision with reason, decided_on). |
| **C. Local + proposal to the DS** | Build as B, set `status: "propose"` and fill the `proposal` block `contribute` requires (name, type, purpose, anatomy, usage rules, tokens used and missing, version bump; variants, states, reused DS components, what is really missing). Then `registry.py ack <id>`. Each later change to the block: review the proposal and `ack` again. Unverified facts → "Unconfirmed: …", never empty, never guessed. |

- The user wants to keep a distinctive look from the image (large radius, dense layout): say it is a deviation from DS tokens and let them decide here. Never copy it on your own.
- Accepting a proposal into the DS is not this skill's job: `contribute` reviews it, `document` adds it to the DS, `sync` replaces the local block in apps.
- Unattended: use A where possible, B only for what the prototype needs to run, keep building, and put every question at the top of the report.
- Never change DS components or tokens from inside an app.

## Step 4b. New-page gate (mandatory)

A **new page** is a destination with its own entry point (nav item, tab, chip, button elsewhere), its own flow and states, and an address the user may want to open or send.
**Not** a new page: dialog, drawer, popover; a tab or step inside an existing page; empty or error states; layout changes. In doubt → treat it as a new page and ask.

When the request leads to a new page: STOP, announce it and ask. Create files, folders or routes only after the user chooses. A decision already recorded in the `define` plan counts; do not ask twice.

Read the app's shape first:

| Stack / app type | Option A means | Cost |
|---|---|---|
| `html`, `single` | New file `apps/<app>/<slug>/index.html`. The shared shell (header, nav, CSS, scripts) must be extracted first, or copied (drifts). | High; propose as its own plan |
| `html`, `multi` | One more page file in the existing shell, its entry in the app's route table, then the app's `build` and `check` commands | Low |
| `react`, `vue` (`spa`) | One route in the router plus one page component under `src/pages/` | Low |

Announcement (AskUserQuestion, complete enough to decide without follow-up):

> **New page:** <name>
> - Purpose and entry point: <what it does; where the user clicks to get there>
> - Proposal: <file or route>, address <path>; sub-routes: `#/` (main), `#/<sub>` (list); unknown hash → app home
> - Shared with the app: shell and DS CSS of the same version; brand, mode, density; long-lived data in `localStorage` with prefix `<app>:`; hand-over data from other pages via `sessionStorage`
> - Cost: <app shape; extra size; follow-up work: build, route table, registry, cross-page tests>
> - Options: (A) own file or route · (B) screen inside the current file or page · (C) inside the current file now, split later
> - Recommended: <A/B/C> because <reason>

Default recommendation: A when the page has 3+ screens or its own flow, needs its own link, or the app is already `multi` or `spa`. B or C when the page is small (1–2 screens) and the app is `single`.

When the user chooses A:
- Slug: lowercase, hyphens, no diacritics.
- Hash routing (`#/…`) for every stack, so the static build opens from a folder. Route table at the top of the page script (`html`) or in the router (`react`, `vue`). `#/` is the default; parameters like `#/c/<id>`; unknown hash → app home; Back and Forward work without reload.
- Links between pages go through the app's route table with relative paths; never hard-code a site URL.
- The page opens directly from its link. Missing hand-over data → a valid empty state, no error.
- Add the entry point (nav item, chip) through the route table.
- Each `html` page file embeds the DS CSS and the version label.
- Extra tests: open the link directly, reload keeps the screen, Back/Forward, unknown hash, moving between pages.

Unattended: create no new file or route; build as B and put the "New page" announcement with the A proposal at the top of the report.

## Step 5. Build

Rules for every stack:
- Only DS tokens (`ds.json > tokens.prefix`) and DS components from `catalog.md`. No hex, `rgb()`, raw gradients or loose px for colour, spacing, radius or font size when a token exists.
- Never write CSS that overrides a DS component. A missing variant goes through the gate.
- Brand, mode and density only through the attributes in `ds.json > theming`, on `<html>`. Never invent attributes. Dark mode stays off unless asked (`theming.mode.default`).
- Density: use `theming.density.default` (usually `auto`). A product that needs one fixed level sets it once and keeps it everywhere. Never redefine density values.
- Line height and reading text: use the DS text tokens; never set your own px line heights.
- Content cut off by a frame: fade the cut edge only if `catalog.md` lists such a utility; never on images, avatars, fixed-ratio frames, ellipsis text or inputs.
- Version label: render `ds.json > version_label.text` in the footer and `<meta name="<version_label.meta>">`, from the version you read. Editing an existing app whose label differs from the profile → report it and suggest `sync`.
- Breakpoints from `ds.json > breakpoints`; follow the DS's compact-screen pattern (for example a tab bar) if `catalog.md` has one.
- Mock data is marked as mock. No real personal data. No real API, auth or persistence beyond `localStorage`.
- Adding to an existing app: leave the rest of the app untouched.

Per stack (see `<kit>/docs/stacks.md`):

| | `html` | `react` | `vue` |
|---|---|---|---|
| Where | `apps/<app>/index.html` (or the page file chosen in 4b) | `apps/<app>/src/pages/<Page>.tsx` + route | `apps/<app>/src/pages/<Page>.vue` + route |
| DS CSS | Embedded bundle between `/* @ds:begin */` and `/* @ds:end */` (`css.marker`); never edit inside it | Imported once in `src/index.css`; do not re-import | Same as React |
| Components | DS classes from `catalog.md` | React column of `components.map` | Vue column of `components.map` |
| Styling | Tokens via `var(...)` in the app's CSS | Tailwind classes mapped to tokens; no arbitrary values (`bg-[#fff]`, `p-[13px]`), no inline `style={{…}}` for colour or spacing | Same as React; no `:style` for colour or spacing |
| Local blocks | `/* LOCAL: <name> */` block in the app CSS | `src/components/local/<Name>.tsx` with the header comment; classes keep `x-` | `src/components/local/<Name>.vue`, same |
| After editing | `multi`: run the app's `build` then `check` | `npm run build` (or `apps[].build`) must pass | Same as React |

## Step 6. Test

Playwright with the installed Chromium; never run `playwright install`.
- No `pageerror`; no console errors (blocked web fonts in a sandbox are acceptable).
- No horizontal scroll at 400, 768 and 1280 px.
- Light and dark mode; at least two brands if `theming.brand.values` has several.
- Mobile or responsive screens: system text size 200% (at 390 px, root font size 200%). Everything still visible: no clipped text, no overlap, no lost buttons or inputs; text wraps and frames grow.
- No hard-coded values left (grep the changed code for hex, `rgb(`, px colour/spacing, and per-stack patterns above).
- Local blocks added or changed: `python3 <kit>/skills/contribute/scripts/registry.py check` passes.
- Capture the new screen next to the reference image and compare layout, order and behaviour (not style).
- Open every main state in the flow (empty, error, loading).

## Step 7. Save and report

- Save the files. Add an entry to `paths.changelog` (date, app, screens, DS version, tests). Open a PR only if the user asks; never merge.
- Decision log (if the project has one): each `approved` decision you built → `decisions.py set <id> implemented --note "<app, screens>"`. Design choices you made that nobody approved → `decisions.py add --status proposed`, and list them in the report.
- Short report:
  - element mapping table (element | DS component | match level), with differences from the reference image and why;
  - component decisions (A / B / C) and registry entries written;
  - new pages decided (own file or route, or inside the current file);
  - what the image did not show and how you handled it;
  - mock parts; open questions; deviations from the DS and intentional deviations kept from `rules.md`;
  - warnings (version label mismatch, unattended defaults).

## Rules

- Never create a new component before step 4, even if it "is just a bit of CSS".
- Never create a page file, folder or route before step 4b. Always announce and wait.
- Never copy the style of the app in a reference image; take layout and behaviour only.
- Never invent classes, tokens, component names or version numbers.
- Keep items `rules.md` marks as intentional deviations, "needs design confirmation" or "proposal" as they are, and mention them in the report.
- New DS version for an existing app → `sync`. New component in the DS → `document`.
