---
name: review
description: "Audit how well one or more prototype apps follow the DS: DS version and embedded tokens, hard-coded values outside tokens (CSS, style attributes, Tailwind arbitrary values, inline style objects), component use (root classes, variants, home-made native controls, real computed styles against the DS), CSS overriding DS components, undecided local components, theming attributes, browser checks; then classify each deviation, rate its risk, record intentional deviations and propose remediation options (map hard-coded values to tokens, never change behaviour, prefer Figma, never force DS controls). Read-only: it measures and proposes, it never edits the app. Use when the user says 'audit', 'compliance check', 'how far is the app from the DS', 'is this app in sync with the design system', 'what breaks when we upgrade the DS'. Do not use to fix (`sync`), to build screens (`prototype`) or to promote local components (`contribute`). Also use for the same request in any language."
---

# Review: audit an app against the DS

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.review` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

Goal: tell the user **how far each app is in sync with the DS, where it deviates, whether that matters, and what it risks**.
The skill only measures, analyses and proposes. It never edits the app, the local registry or the DS, and never opens a fix PR.

Scripts run from the project folder (or take `--project`).

## Step 1. Read configuration and scope

- Load `kit.config.json` (`python3 <kit>/scripts/kitconf.py check`). Missing → `kickoff`. No DS profile → `adopt`.
- Read the DS profile: `ds.json`, `rules.md`, `catalog.md`. Intentional deviations and "do not override" rules in `rules.md` are never findings.
- The DS source of truth is the bundle at `ds.json > css.bundle` and the profile files. Never say from memory that a token or class "exists in the DS": check with a script or read the source.
- Ask if unclear: which apps (default: every app in `apps[]`), static scan only or with browser checks, compare with an earlier audit (in `paths.audits`, if any).

## Step 2. Static scan

```
python3 <kit>/skills/review/scripts/audit_app.py [app ...] --json <scratchpad>/audit.json
```

Project checks: `kit.config.json > review.extraChecks` (the project's own scripts, for example a feature-flag ledger or an accessibility script) run after the scan; each adds a row (exit code and summary lines) to the app's table, or to "Project checks" when it is not per app. Treat a failing one like any other Deviation: read its output before concluding. `--no-extra` skips them.

DS with its own Vue component layer (`ds.json > components.vue`): vue apps get a "DS Vue components" row: local `.vue` files named like a DS component (rebuilt instead of used) and shadcn-vue imports are hard-rule violations. With `ds.json > tailwind: false` there is no Tailwind row and Tailwind is never asked for.

When the profile has `catalog.json`: `python3 <kit>/skills/document/scripts/catalog.py scan --app <id>` for each app. Components it lists as deprecated and still in use are findings (level: hard-rule violation), with the replacement it names as the remediation.

DS region = text between `/* <css.marker.begin> */` and `/* <css.marker.end> */`. App region = every other CSS, `style=""`, and per stack:

| Stack | Also scanned |
|---|---|
| `html` | `<style>` blocks, `.css`, `style=""`, `.js` for markup and `var()` use |
| `react` | `.tsx` / `.jsx` / `.ts` / `.css`; `style={{…}}` objects; Tailwind arbitrary values (`bg-[#fff]`, `p-[13px]`, `rounded-[6px]`, `text-[13px]`); default-palette classes (`bg-blue-500`) |
| `vue` | `.vue` templates and `<style>` blocks, `:style` bindings, Tailwind as for React |

For `react` / `vue` the DS CSS is normally imported, not embedded: the script reports the import instead of comparing embedded tokens.

| Item | Meaning | "Deviation" when |
|---|---|---|
| DS version | version the app declares (`<meta name="<version_label.meta>">`, footer label) vs `ds.json > version` | older, unknown, or several versions declared (Note) |
| Embedded tokens | DS tokens the app lacks or holds with another value | missing or changed |
| Redefined tokens | `<prefix>*` defined again outside the DS region (a verbatim copy of a DS definition is allowed) | any |
| Hard-coded colours | hex, rgb/hsl, colour names outside token definitions | any |
| Font size, radius, shadow | raw px or literal values | any |
| Tailwind arbitrary values | arbitrary values that bypass tokens; `bg-[var(<prefix>…)]` is a token use and is not counted | any (palette classes = Note: depends on the Tailwind theme) |
| Component use | DS root classes used; variants (`btn.xxx`) found neither in the DS nor in the app; native `<button>`, `<input>`, `<select>`, `<textarea>`, `<table>` with no DS or local class (a control inside a DS wrapper that the DS CSS styles, such as `.acme-select > select`, counts as DS) | unknown variant or home-made control |
| CSS over DS classes | app rules that touch visual properties (colour, background, border, text, height, padding) of DS classes; selectors equal to DS selectors with other content; verbatim DS rules outside the region are excluded | any |
| Undefined tokens | `var(<prefix>…)` used but defined nowhere | any |
| Theming | values of the attributes in `ds.json > theming` | a value the DS does not declare |
| Local components | registry entries by status, `/* <local.marker>: … */` blocks without an entry | undecided = Note |

Spacing in px (`margin`, `padding`, `gap`) is counted for scale only and does **not** set the level: many places have a token, many are valid. Check clusters before concluding.

Limits of the static scan (state them in the report): native controls are judged by classes in the source (their own, or a DS wrapper class on the parent or an ancestor as the DS selector requires), so controls built by plain JS without a class count as home-made; styles set by JS at run time, colours inside JS strings, inline SVG and CSS-in-JS libraries are not seen; numbers count declarations, not visible places; a class name shared by the DS and the app can be counted as an override. Identical style blocks copied into several files (`multi` apps) count once.

## Step 3. Browser checks (when the user wants a full measure)

Standard checks with Playwright (Chromium is assumed installed; never run `playwright install`), main screens of each app: no `pageerror`, no console error except blocked web fonts; no horizontal scroll at 400, 768, 1280 px; light and dark (`ds.json > theming.mode`), at least two brands when the DS has several; text size 200 % for mobile or responsive apps.

**Component compliance by real measures** (tells a harmless override from one that changes values). Serve the project folder (`python3 -m http.server 8765`), then:

```
python3 <kit>/skills/review/scripts/audit_app.py --roots <scratchpad>/roots.json
node <kit>/skills/review/scripts/audit_components_browser.js <scratchpad>/roots.json <scratchpad>/comp.json http://localhost:8765/<app path>/[#/<route>] [url ...]
```

For `react` / `vue`, serve the dev server or the built output and pass its URLs.
One URL per screen; open dialogs or tabs too when a control only shows there.
The script takes a few elements per DS root class, rebuilds the same element in an iframe that holds only the DS bundle, copies the theming attributes of `<html>`, and compares computed styles (height, padding, radius, text, colour, background, border, shadow, gap).
Trust a difference only when it repeats on several elements for the same property.
Rule out two false positives by reading the code: a control cut from its parent loses `.parent .child` rules and inherited colours; an app on an older DS shows version debt, not an override.
Record numbers; do not capture the whole app.

## Step 4. Classify every deviation

Never stop at the numbers. Put each group in one class:

| Class | Signs | Meaning |
|---|---|---|
| Hard-rule violation | hard-coded colour, CSS over a component, home-made control where a DS component exists, unknown variant, theming value not in `ds.json` | must be fixed (a home-made control the DS lacks goes through the `prototype` gate: compose, local `x-`, or propose) |
| Recorded deviation | inside a local block with a registry entry (kept or proposed), or listed as intentional in `rules.md` | keep; restate it |
| Undecided | registry entry still pending, or a local block without an entry | the user decides (`contribute`) |
| Version debt | old DS version, missing or changed tokens | `sync` |
| Unconfirmed | no evidence found | write "Unconfirmed: …"; never guess |

For each large group (by count and by spread): typical places (`file:line`), a few real examples, the cause with evidence (code, project changelog, registry). No speculation.

## Step 5. Risks

Tie each deviation to a concrete consequence, rated High, Medium or Low with a reason. Usual risks:

- **A DS upgrade breaks the UI:** overrides, redefined tokens and hard-coded values do not follow the new version; differences appear silently.
- **Brands and dark mode break:** hard-coded colours ignore the brand and mode attributes; contrast cannot be checked.
- **Accessibility:** px font sizes do not scale with system text size; horizontal overflow; missing states.
- **Handoff:** developers rebuild from hard-coded values; BA and QC see something different from the DS.
- **Maintenance:** undecided local components pile up; shared parts of `multi` apps drift (run the app's `check` command from `kit.config.json`).

## Step 6. Report

Return the report in the conversation. Save `<paths.audits>/<date>-<scope>.md` only when the user wants it kept. Structure:

1. **Summary**, three to five lines: which apps are fine, which deviate most, what to do first.
2. **App comparison table** (item × app, level Pass / Note / Deviation, numbers).
3. **Deviations by group** (class, `file:line` examples, cause, risk High / Medium / Low).
4. **Recorded deviations**: restate verbatim every intentional deviation, "needs design confirmation" and "proposal" item of `rules.md` or the catalogue that applies.
5. **Limits of this audit** (what the static scan cannot see, screens not tried).
6. **Remediation options and batches** (step 7). Do not carry them out.

Never give one overall score. To compare with an earlier audit, compare each item by raw numbers.

## Step 7. Remediation options

Read `references/remediation.md` and follow it. In short:

1. **Map hard-coded values to existing tokens first:**
   ```
   python3 <kit>/skills/review/scripts/audit_map_tokens.py [app ...] --csv <scratchpad>/map.csv
   ```
   Confidence: **Exact** (replace, nothing visible changes), **By role** (user picks by meaning), **Near** (visible change: check Figma first), **None** (check Figma; never invent a token). Semantic tokens only (`ds.json > tokens.roles`); never a primitive to get around it.
2. **Never change DOM or behaviour.** Options change CSS values only (and values in style attributes, style objects, Tailwind classes swapped for token-based ones). Anything that needs DOM, class names used by scripts, text, data, flow, routes or events is a separate "needs a product decision" item.
3. **Prefer Figma; never force DS controls.** Figma is the design source; the DS is its normalised copy. A home-made control that matches Figma stays; it becomes a local block and may be proposed through `contribute`.
4. **At least two options per group**, one recommended, split into batches the user approves one by one.

## Step 8. Next steps (proposals only; the user chooses)

- Approved batches, version debt, hard-coded values to tokens → `sync` (with the approved mapping table).
- Undecided locals, home-made controls worth sharing → `contribute`.
- Tokens or components missing in the DS, DS differs from Figma → `document`.
- Screens that need rebuilding → `prototype`.

## Rules

- Read and propose only. Never edit the app, the registry or the DS in this skill; never open a fix PR.
- Options change CSS values only; never DOM, classes used by scripts, text, flow or behaviour.
- Never force a DS control when the home-made UI matches Figma; never invent a token for a value the DS lacks.
- Every number in the report comes from a script or a measure just run; state the command. Never write numbers from memory.
- Unverified → "Unconfirmed: …".
- An intentional deviation in `rules.md` is not an error; restate it in the report.
- Scripts count, the reader concludes: look at a few places of every "Deviation" group before calling it a violation.
