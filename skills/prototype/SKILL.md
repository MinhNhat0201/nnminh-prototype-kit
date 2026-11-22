---
name: prototype
description: "Build new screens, flows or a whole prototype with the project's DS from a written request, a plan wave, reference images or screenshots of another app: map every element to the DS catalogue, reuse DS components first, and stop to ask before any new component or new page. Use whenever the user asks to build, mock up or prototype a screen or flow, 'make it like this image', pastes a screenshot of another app as reference, or wants a screen added to an existing app, even without naming the skill. Do not use to bring an app to a new DS version (`sync`), to change the DS itself (`document`) or to plan from a PRD (`define`). Also use for the same request in any language."
---

# Prototype: build screens with the DS

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.prototype` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

Rules: run `python3 <kit>/scripts/rules.py list --app <app> --skill prototype` (no app: leave out `--app`) and follow what it prints: `must` rules are never broken, a `should` rule is broken only with the reason in the report, `EXCEPTION` and `OVERRIDDEN` lines say what does not apply to this app. It replaces reading long rule documents; read the DS `rules.md` only when the output says the profile keeps its rules there. `rules.py show <id>` explains one rule ([docs/rules.md](../../docs/rules.md)).

Goal: screens that look like the user's product, reuse DS components as much as possible, and never grow a new component silently.
Reason: the DS is the single source of truth; every home-made component is maintenance debt for every app.


## Step 0. Which DS and design source apply

Decide this before anything else, per app; never assume the project-wide one.

| Source | Read it from | Means |
|---|---|---|
| DS profile | `apps[].ds` of the target app, else the top-level `ds` (`python3 <kit>/scripts/kitconf.py --app <app>` prints the merged one) | the tokens, components, version label and rules of that profile; a web and a mobile app may use different profiles |
| Design source note | `apps[].designSource` (free text, optional), e.g. "screens follow the Figma library <name>; the DS covers tokens only" | where layouts and components come from when it is not the DS catalogue alone; follow it, and still use only tokens of the profile |
| How the DS CSS loads | `ds.json > css.load` / `apps[].css.load` (`embed` or `link`, see step 5) | where the DS CSS of a page lives |
| Page contract | `python3 <kit>/scripts/kitconf.py contract --app <app>` (`apps[].pageContract`; for a page app also the contract of each host app in `usedBy`) | what every page must do for the app shell (call a ready hook, load shared scripts first, keep a mount element). Follow every line on each page you build or edit; a missed line often fails silently (icons or nav missing, no console error), so step 6 checks it |

The note and the profile disagree, or neither covers the request: ask which one wins before building.

- Load `kit.config.json` (`python3 <kit>/scripts/kitconf.py`). Missing → `kickoff`. No DS profile → `adopt`. Note `stack`, the target app in `apps[]` and its `type`.
- Read the DS profile (`ds.json`, `catalog.md`) and the rules (`rules.py list`, above; the DS `rules.md` only when the output says so). The rules override everything else here. The user states a new rule while you build → record it through `context` (decision, then `rules.py add`), never only in the app.
- Product context (`paths.context`, see `context`): `python3 <kit>/skills/context/scripts/context.py summary`; read UX principles, business rules, constraints and the `approved` decisions in scope. Building against an approved decision → stop and ask; never silently override it.
- Input: the written request, or the wave handed over by `define` (R-ids, S-ids, assumptions, page and component decisions; reuse them, do not ask again).
- Porting an existing page (to another stack, or from one app to another): the parity checklist of the `define` plan is the requirement (no plan: `python3 <kit>/skills/define/scripts/extract_rules.py <page and its scripts>` and complete it first). Keep every business rule: flow, conditions, limits, input checks, visible text, messages, shared storage, routes. Only the way it is built changes. A rule the new build cannot keep → say so before building; never drop or change it silently.
- Exploration from `explore`: build from the **chosen** direction only (`<paths.explorations>/<slug>/<id>/index.html`, `decision.md`); apply the parts listed as merged. No recorded decision (`explore.py list` shows `exploring`) → stop and send the user back to the decision gate in `explore`. The exploration page is a layout and behaviour reference; still run the gates below for anything not in the DS (`dsFit.missing`). Open reference images with Read. Existing app: read the screens you change, one at a time.
- **Reference images give layout, order, behaviour and ideas only.** Never copy colours, fonts, radii, shadows or icons from them.
- Write an image breakdown: every region and element you see (nav, card, table, form, dialog, empty state…), and the anatomy of unfamiliar patterns (parts, arrangement, relations).
- An image shows one moment. List what it does **not** show: hover, focus, error, empty, loading, scroll, small-screen behaviour. Mark them "not in the image", use the DS component defaults, and never invent behaviour.
- App-specific settings (brand, density, special rules): read them from the existing app or ask. Never change them and never infer them from another app.

## Step 2. Load the DS sources

- Component classes, variants, states and `components.map` from `catalog.md`, or from `catalog.json` when the profile has it (`catalog.py find <words>` to look a role up, `catalog.py show <id>` for details, `catalog.py patterns` for page layouts such as master-detail or split panes). Never use a `deprecated` component: use its `replacedBy`. Say so in the report when you use an `experimental` one. Follow each component's `usage.use` / `usage.avoid` rules. Tokens from the CSS bundle (`ds.json > css.bundle`) or `tokens.file`. Token values win over prose when they disagree.
- Icons from `ds.json > icons`.
- Never write a token, class, component name or version from memory. Source unreadable → stop and say so; never invent styles.

## Step 3. Map every element to the catalogue

Build ladder, in this order; take the first step that works and say which one in the mapping table:
1. **Reuse** a DS component (or the app's existing screen part that already uses it).
2. **Compose** DS components and tokens (layout, spacing, surfaces), no new class.
3. **Local** block (gate B in step 4), tokens only.
4. **Propose** to the DS (gate C), still built as a local block.
Write the least code that does the job: no new helper, wrapper or option nobody asked for.

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
| **B. Local block** | Class prefix `local.prefix`, tokens only, inside a `/* <local.marker>: <name> */` block (one name per block; file location per stack below). Register it: `python3 <kit>/skills/contribute/scripts/registry.py update` (it runs `local.command.update` when the project sets one), then fill every **new and changed** entry in `local.registry` (title, kind, status, summary, where, vs_ds, decision with reason, decided_on; for a changed block also what changed and why). |
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
- Each `html` page file loads the DS CSS the way the app does (`css.load`, step 5) and carries the version label.
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

| | `html` | `react` | `vue` | `vue` page in an `html` app (`type: "page"`) |
|---|---|---|---|---|
| Where | `apps/<app>/index.html` (or the page file chosen in 4b) | `apps/<app>/src/pages/<Page>.tsx` + route | `apps/<app>/src/pages/<Page>.vue` + route | `<page app path>/src/` (`main.ts` mounts into the host page); built to one JS file (`apps[].output`) that becomes the files in `usedBy` |
| DS CSS | `css.load` `embed` (default): the bundle between the `ds.json > css.marker` comments of each page. `link`: one `<link rel="stylesheet">` to the app's DS file (`css.linkPath`, relative to the app folder; a page in a sub-folder uses `../`). Never edit inside either | Imported once in `src/index.css`; do not re-import | Same as React | None in the JS: the host page loads the DS CSS the way its app does |
| Components | DS classes from `catalog.md` | React column of `components.map` | Vue column of `components.map`; with `ds.json > components.vue`, only the DS Vue components (props from its props map) | Same as `vue` |
| Styling | Tokens via `var(...)` in the app's CSS | Tailwind classes mapped to tokens; no arbitrary values (`bg-[#fff]`, `p-[13px]`), no inline `style={{…}}` for colour or spacing | Same as React; no `:style` for colour or spacing | DS classes and tokens; no Tailwind unless the host app has it |
| Local blocks | `/* LOCAL: <name> */` block in the app CSS | `src/components/local/<Name>.tsx` with the header comment; classes keep `x-` | `local.vueStyle`: `sfc` (default) `src/components/local/<Name>.vue`, same header; `css-file` a `/* LOCAL: <name> */` block in `local.vueCss`, no `<style>` in `.vue` | In the host app CSS (`/* LOCAL: <name> */` block), so every host page gets it |
| After editing | `multi`: run the app's `build` then `check` | `npm run build` (or `apps[].build`) must pass | Same as React | The page app's `build` (and `check`), then each host app's `build` and `check` |

DS with its own Vue component layer (`ds.json > components.vue`): import the components from the alias `@ds-vue` (or the npm package `components.vue.package`), set props as the props map names them, never copy or rewrite a DS component into the app, never add shadcn-vue. A component the layer lacks goes through the component gate. The layer is a folder with its own `package.json` (its `tsconfig` extends packages such as `@vue/tsconfig`): run `npm ci` in that folder once before the first app build, or `vite build` / `vue-tsc` stop with a tsconfig error. No Tailwind (`ds.json > tailwind: false`): style only with DS classes and tokens in the app CSS.

Vue page in an `html` app: the host page keeps the shell (header, nav, DS CSS, shared scripts) and an empty mount element; it sets the page config (a global such as `window.__PAGE__`), loads the shell scripts, then the page JS. The page JS mounts only into that element, reads shell services (toast, router, storage) through one small adapter file, and never touches the shell's markup. The page contract lines of every host app apply. A new page app like an existing one: `python3 <kit>/scripts/kitconf.py add-page --like <page app> --id <new id> --host <host app> --dry-run`, show the plan, run it without `--dry-run`, then do the host-side steps it prints (it is a new page: the step 4b gate applies first). See `<kit>/docs/stacks.md`.

## Step 6. Test

Run `validate` for the screens, states and flows of this wave (`V=<kit>/skills/validate/scripts/validation.py`; `python3 $V run --app <id>`; add them to its `plan.json` first). It covers page and console errors, horizontal overflow, accessibility, focus, touch targets and visual changes at 390, 768 and 1280 px in each mode; the build is not done until its report shows **Fail (0)**. Never write your own Playwright script for these checks.
- Quick run while building (no plan yet, or a trial): `python3 $V init --app <id> --dir <scratch folder>` (`--page <file>` for one page), keep the screens of this wave, then `python3 $V run --app <id> --dir <scratch folder>`. Move the plan to `paths.validation` when the wave is done.
- Brands and text size 200%: list them as named plan states (`brand=<value>` for at least two brands if `theming.brand.values` has several; `text=200%` for mobile or responsive screens). Everything must stay visible: no clipped text, no overlap, no lost buttons or inputs.
- Page contract (`kitconf.py contract --app <app>`): each line has a check in the plan (a flow step `expectVisible` on what the contract makes appear, or a state), so a missed call fails instead of passing silently.
- Porting a page: run the parity check. Same steps on the old and the new page (a flow per row group of the parity checklist, run against both entries with `--url`); compare visible text, messages, states and stored data (`localStorage` keys and values). Every row of the checklist ends "same" or a difference the user accepted.
- No hard-coded values left: `python3 <kit>/skills/review/scripts/audit_app.py <app>` (hex, `rgb(`, px colour and spacing, per-stack patterns above) shows nothing new in the changed files.
- Local blocks added or changed: `python3 <kit>/skills/contribute/scripts/registry.py check` passes, and every new or changed entry has its notes filled.
- Capture the new screen next to the reference image and compare layout, order and behaviour (not style).
- Open every main state in the flow: empty, error, loading, and edge data (long names, many items, none, a missing image). The request rarely names them; build them with DS components (empty and error patterns from the catalogue) and list the ones you could not build. Which states and which edge data: `references/states-and-edge-data.md` (S- and D-codes). A screen that adds animation: `<kit>/skills/review/references/motion.md`.

## Step 7. Save and report

- Save the files. Add an entry to `paths.changelog` (date, app, screens, DS version, tests). Open a PR only if the user asks, following the project's own branch and PR rules (`rules.py list --skill pr`); never merge.
- Optional project step after a build (`kit.config.json > prototype.post`, off by default; for example the project's own preview or publish script): `python3 <kit>/scripts/kitconf.py hook prototype.post --app <app>` runs it in the project root and prints its output and exit code. Run it only when it is set and the user wants it this time; the kit itself never publishes.
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
