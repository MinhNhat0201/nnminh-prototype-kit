---
name: sync
description: "Bring the latest DS version into one or more prototype apps: read the DS changelog since the app's version, replace the embedded DS CSS (html) or bump the DS package and re-import tokens (react, vue), sort every control into groups A/B/C/D, ask before touching local components, replace hard-coded values that map to exactly one token, update the version label, test and record the change. Use when the user says 'update the app to the new DS', 'sync with the latest DS', 'bump the design system', 'the DS has a new version', or when an app's version label is behind the DS profile. Use `document` to change the DS itself, `review` for a read-only audit, `contribute` to move local components into the DS. Also use for the same request in any language."
---

# Sync apps with the latest DS

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.sync` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

Goal: every app in scope runs the latest DS version, keeps its own content, data and logic, and no local component changes without the user's decision. Local components may be intentional exceptions or old debt; only the user knows which.

Read first: `kit.config.json`, `ds.json`, the DS `rules` file, the DS `catalog`, the DS `CHANGELOG.md`. Never fill a token value, class name or version from memory. If a source cannot be read, stop and say so.

Script: `python3 <kit>/skills/sync/scripts/sync_ds.py` (`status`, `changes`, `apply`, `note`; `--help` lists options).

**Project sync commands.** Some projects already sync their apps with their own script (several DS blocks per app, shared shells rebuilt, versions per platform). When `kit.config.json > sync.command` (or `ds.json > sync.command`) is set, `apply` runs that command instead of replacing blocks, and `status` runs `sync.check` instead of reading versions; `apply --dry-run` runs `sync.check` and prints the command. Report their output and exit code as they are, never rewrite blocks by hand around them. Every other step of this workflow (changelog, control inventory, local components, hard-coded values, tests, record) still applies. `--builtin` forces the kit's own status/apply; use it only when the user asks.

## Scope
- Default: every app in `kit.config.json > apps`. The user names apps: only those.
- Several apps: finish the whole workflow for one app before the next. Ask about the local components of each app separately.
- An app that is not declared in `apps[]`: ask for its path; do not invent one.

## Workflow
1. **Latest version.** `ds.json > version` is the target. Run `sync_ds.py status`: it prints the version each app states (`<meta name="<version_label.meta>">` or the version label text) and the files that hold the embedded DS block. Version not found: write "unknown" and treat every control as "to check".
2. **Read the app.** Find every place that renders UI (HTML, CSS, JSX/TSX, Vue templates). `multi` apps: the shared shell is the source; edit it, never the generated copies.
3. **Changelog.** `sync_ds.py changes --from <app version>`. List what affects the app: new or changed tokens, new or renamed classes or components, new variants and states. Items the DS marks "needs design confirmation" or "intentional deviation": keep them as they are and repeat them in the report.
4. **Replace the DS layer.**

   | Stack | Do |
   |---|---|
   | `html` | `sync_ds.py apply --app <id> --dry-run`, then `apply`. It replaces only the CSS between the `ds.json > css.marker` comments and the version label. App CSS outside the markers stays. No markers: stop and ask whether to add them around the current DS CSS. |
   | `react`, `vue` | Bump the DS package to the target version (or copy the new bundle where `src/index.css` imports it). Re-map the Tailwind theme only if the DS changelog renames tokens. Run `apps[].build`. |

   `apps[].build` is set (`multi`, `spa`): run it after the change, then `apps[].check` if set.
5. **Control inventory.** For each control type in the DS `catalog`, put every use in exactly one group:

   | Group | How to recognise it | Action |
   |---|---|---|
   | A. Current DS | DS class or component, no override | Keep |
   | B. Old DS | Old class, renamed selector, missing a new variant | Update |
   | C. Local component | Signs below | **Ask**, do not edit yet |
   | D. Not in the DS | A role with no DS component | List and suggest, do not edit |

   Signs of a local component: the `local.prefix` class or a `/* <local.marker>: … */` block; a file under `src/components/local/` (react, vue); a custom name for a DS role (`.my-btn`, `CustomSelect`); a redefinition of a DS class; CSS outside the DS markers that overrides a DS class; a wrapper around a DS control with its own style; colours or spacing not from `var(<tokens.prefix>…)`; two definitions of one control.

   For each local component record: name, file:line, number of uses, closest DS control, visible differences (size, colour, behaviour), and states or variants that only one side has.
6. **Ask about local components.** Required when group C is not empty, and before any local component is edited. Replacing an intentional exception breaks the UI; keeping old debt keeps the app off the DS.
   - Open with one sentence: controls scanned, A/B updates planned, local components to decide.
   - Group local components of one kind into one question ("Local button: 3 variants, 41 uses"). At most 4 questions per turn; most-used groups first.
   - Options: (1) **Replace with the DS** (first; mark "Recommended" when the match is clear); (2) **Keep local** (intentional exception; ask for the reason to note in code); (3) **Propose to the DS** (keep for now, status `propose`, fill the `proposal` block: see `contribute`).
   - If the local component has a state or behaviour the DS lacks, say that replacing it loses that.
   - Nobody answers (scheduled run, headless, user away): do not block. Default **keep local**, finish group B and the other steps, put every question in the report.
7. **Update controls and hard-coded values.**
   - Group B and locals approved for "Replace": switch to the new DS class or component. Remove the override; do not stack another one. Keep content, data, logic, events.
   - Hard-coded values (hex, `rgb()`, gradients, odd px for colour, spacing, radius; in `react`/`vue` also Tailwind arbitrary values and inline styles): replace only where the value clearly maps to one token of the matching role (`ds.json > tokens.roles`). Not sure: keep it and list it. A mapping table the user approved after `review`: apply exactly that batch, CSS values only, no DOM or logic change.
   - Never touch hard-coded values inside a local component without a decision.
   - Kept locals: leave them. If the user wants, add `/* DS exception: <reason> */` at the definition.
8. **Version label.** `apply` updates the `<meta>` and the label text from `ds.json > version_label`. In `react`/`vue`, check `index.html` and the app footer.
9. **Test.** Browser test (Playwright, Chromium already installed; never run `playwright install`): no page errors; no console errors except blocked web fonts; no horizontal scroll at 320, 400, 768, 1280 px; light and dark through `ds.json > theming.mode`; at least two brand values when `theming.brand` has them; each changed control in hover, focus, disabled and error (where the DS has them); before/after captures of screens with changed controls. An unexpected difference: stop and report; never fix it silently.
10. **Record.**
    - Changelog: `sync_ds.py note --app <id> --from <old> --to <new> --summary "<what changed>"` appends to `paths.changelog`.
    - Local registry: run `contribute`'s `registry.py update`, fill in the decision of each new or changed entry (status, reason, date), `ack <id>` for changed proposals, then `check` must pass.
    - Branch, commit and pull request: only when the user asks. Never merge, never force-push.
11. **Report** (short): apps and versions (from → to); visible changes; control table (name | group | action); local components replaced, kept (with reason), proposed, still waiting for an answer; hard-coded values replaced and kept; items that need design confirmation; test results; branch or PR link if any.

## Rules
- No edit to a local component before the user answers, even when it looks like a copy of a DS control.
- No change to app content, data or flows beyond what the DS needs.
- Never change DS token values or DS CSS inside an app. If the app needs something different, report it (and suggest `document`).
- Never invent a version, class, token value or date.
- Theme, mode and density only through `ds.json > theming` attributes.
- Internal design-team notes (checklists, open discussion) stay out of the app and the DS docs; put them in the report.
