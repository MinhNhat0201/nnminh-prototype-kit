# CLAUDE.md: project rules

Reply in {{LANGUAGE_NAME}} (`kit.config.json > language` = `{{LANGUAGE}}`). Generated documents use the same language.
This file holds only rules that are always true. Workflows live in the kit skills (`/kit:<name>`); configuration lives in `kit.config.json` and the DS profile.

## 1. What is in this repository

| Area | What it is | Rules |
|---|---|---|
| `{{DS_PATH}}/` | DS profile {{DS_LABEL}}: `ds.json`, tokens, CSS bundle, `catalog.md`, `rules.md` | Change it only through `document`. It defines tokens and components. |
| `apps/<app>/` | Prototypes listed in `kit.config.json > apps` (stack `{{STACK}}`) | Use the DS only (sections 3 and 4). Never change the DS from here. |
| `docs/`, `{{CHANGELOG}}` | Records: plans, audits, local-component registry, handoffs | Records, not rules. |

Which skill does what:

| Task | Skill |
|---|---|
| Not sure where to start | `brief` |
| Set up the project, add an app, change the stack | `kickoff` |
| No DS yet: build a profile from a public preset | `adopt` |
| Analyse a PRD, user story or ticket; plan waves | `define` |
| Record product facts and decisions; answer "why did we decide X" | `context` |
| Compare 2–4 design directions and let the team choose before building | `explore` |
| Build screens, flows or a prototype | `prototype` |
| Check a prototype in the browser before review or handoff | `validate` |
| Markdown spec per unit with screen captures | `annotate` |
| Flow board of screen images on Figma | `wireflow` |
| Rebuild screens on Figma with DS components and variables | `mockup` |
| Package one feature or a whole app for BA, QC and developers | `handoff` |
| Draft the handoff email (never sends) | `share` |
| Audit an app against the DS (read-only) | `review` |
| Bring a new DS version into the apps | `sync` |
| Review local components and propose them to the DS (two approval gates) | `contribute` |
| Write DS documentation, change tokens or components | `document` |

## 2. Source of truth

- The DS profile `{{DS_PATH}}` is the only source: `ds.json`, `{{RULES}}`, `{{CATALOG}}`, and the bundle `{{DS_BUNDLE}}`. `rules.md` overrides everything else.
- Read the source before you build or review. Token values in the bundle win over prose when they disagree.
- Never write a token, class, component name or version from memory or from an older copy. Source unreadable → stop and say so; never invent styles.

## 3. Hard rules for `apps/`

- Only DS tokens (`{{TOKEN_PREFIX}}*` and the alias variables the bundle defines, such as `--background`, `--primary`, `--border`, `--radius`) and DS components, variants, page patterns, icons and logos listed in `catalog.md`.
- No hex, `rgb()`, named colours, raw gradients or loose px for colour, spacing, radius or font size when a token exists. React and Vue: no Tailwind arbitrary values (`bg-[#fff]`, `p-[13px]`) and no inline style objects or `:style` bindings for colour or spacing.
- Never write CSS that overrides a DS component. A missing variant goes through the component gate (section 4).
- Never edit the embedded DS CSS (between the `ds.json > css.marker` comments) or the copied bundle in `src/ds/`. `sync` replaces them.
- Brand, mode and density only through the attributes in `ds.json > theming`, set on `<html>`{{THEMING_ATTRS_NOTE}}. Never invent attributes. Dark mode stays off unless asked.
- Density: every app uses `{{DENSITY_DEFAULT}}` unless the product needs one fixed level; then set it once and use it everywhere. Never redefine density values.
- Line height and reading text: use the DS text tokens; never set your own px line heights.
- Mobile apps built with a native framework use the DS mobile tokens and never copy web CSS. An HTML mockup of a native screen: ask whether to build it with web components in a phone frame or with HTML that uses the mobile tokens.
- Version label: the footer shows `ds.json > version_label.text` and `<meta name="{{VERSION_META}}">` holds the version, both from the profile you read. Opening an app whose label differs from the profile → report it and suggest `sync`.
- Mock data is marked as mock. No real personal data, no real API, no auth, no persistence beyond `localStorage`.
- Items that `rules.md` marks as an intentional deviation, "needs design confirmation" or "proposal": keep them as they are and mention them in the report.

## 4. Components not in the DS

- Reference images give layout, flow and content only. Never copy colours, fonts, radii, shadows or icons from them; rebuild with DS tokens and components.
- Map every element to the catalogue: **Available** / **Close** (compose existing components) / **Tokens only** (tokens exist, no component) / **Missing**.
- Tokens only and Missing (and any significant Close): STOP and ask before building that part. Offer (A) compose existing components, (B) a local block, (C) a local block plus a proposal to the DS. The question format is in `prototype`.
- Option B or C: class prefix `{{LOCAL_PREFIX}}`, tokens only, one block per component opened by a `{{LOCAL_MARKER}}: <name>` comment (`html`: a CSS comment in the app CSS; `react`/`vue`: a header comment in `src/components/local/<Name>`), then register it (section 4a).
- Unattended run (nobody to answer): create no new component, build with (A) and put the warning at the top of the report.

## 4a. Local-component registry

- Every local block in an app is one entry of `{{LOCAL_REGISTRY}}`.
- **Each time you add, change or remove a local block**, or decide to replace, keep or propose one: run the registry `update` (skill `contribute`), fill the new or changed entry (status, summary, where, comparison with the DS, decision with reason and date), and commit it with the app change.
- An entry with `status: "propose"` needs a complete `proposal` block (name, type, purpose, anatomy, usage rules, tokens, version bump; variants, states, reused DS components, what is really missing). Each later change to its block: review the proposal and run `ack <id>`.
- Proposals reach the DS only through `contribute`: write a proposal only after the user picks the entry, and change the DS only after the user approves each proposal.
- Write only what has a basis (block name, earlier records, comparison with the DS). Not verified → "Unconfirmed: …", never a guess.
- Before a PR or handoff: the registry `check` passes. Entries still "pending" are allowed but must be listed in the report.

## 4b. New pages

- A **new page** is a destination with its own entry point, flow and states (not a dialog, tab, step or change to an existing page).
- When a request leads to a new page: **announce it and ask first.** Propose an own file or route (`html` `single`: `apps/<app>/<slug>/index.html` with its own hash router; `html` `multi`: one more page file in the shared shell; `react`/`vue`: one route and one page component), or a screen inside the current file. Create no file, folder or route before the user chooses.
- `define` puts the decision in the plan; `prototype` step 4b is the gate (announcement format, router and file conventions).
- Unattended run: create no new file; build inside the current file and put the announcement at the top of the report.
- `multi` apps: edit the shared shell in `apps/<app>/_shell/`, run the app's `build`, and its `check` must pass before a PR. Never edit inside the generated shell regions.

## 5. Records and handoff

- Every change to an app or the DS gets an entry in `{{CHANGELOG}}`: date, app, version, what changed, tests.
- DS changes bump the profile version: patch for small fixes, minor for a new component, major for breaking token changes; then `sync` brings it into the apps.
- Documentation that depends on the DS (catalogue, rules, component pages) changes in the same branch and PR as the DS change.
- Work on a branch. Open a PR only when asked. Never merge on your own.
- Never write secrets, passwords, tokens, real site URLs or personal data into the repository, a PR or a report.
- Prototypes are demos and references for developers, not production code.

## 6. Self-check before handoff

- Registry matches the apps: registry `check` passes (section 4a).
- New pages (if any) were announced and the user chose before any file or route was created (section 4b).
- No hex, raw colour or hard-coded value outside tokens in `apps/` (and no Tailwind arbitrary values for `react`/`vue`).
- Only DS components, page patterns, icons and logos; no CSS that overrides the DS.
- `react`/`vue`: `npm run build` passes; `npm run build:handoff` writes one self-contained HTML file with no separate `.js`.
- Browser test with Playwright and the installed Chromium (never `playwright install`): no `pageerror`, no console errors except blocked web fonts; no horizontal scroll at 400, 768 and 1280 px; light and dark mode; at least two brands when the DS has several. Mobile or responsive screens: system text size 200%, everything still visible, nothing clipped or overlapping.
- The version label matches the DS version you read.
- With a reference image: a table `element | DS component | match level`, and the differences from the image.
- List everything "not in the DS" and every deviation from the design files separately.

A request that conflicts with these rules: name the conflict and ask before you act.
