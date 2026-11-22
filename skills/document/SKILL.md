---
name: document
description: "Maintain the DS profile and its documentation: change tokens and components at the source, rebuild the bundle, bump the version, write the changelog, sync tokens and components from Figma (large files in batches with a manifest on disk), protect intentional deviations, check contrast, and write clear DS docs for developers, QC, BA and designers (one component, a foundation, a release, or the whole DS) with facts taken from the CSS. Use when the user changes a DS token, component or style, shares a Figma link or file of the design system to update the DS, or asks to write, fix, review or explain DS docs ('doc for dev and QC', 'write the component spec', 'explain the DS to the team'). Do not use to bring an app to a new DS version (`sync`), to audit an app (`review`) or to write feature specs with screen captures (`annotate`). Also use for the same request in any language."
---

# Document: maintain the DS and its docs

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.document` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

Rules: run `python3 <kit>/scripts/rules.py list --app <app> --skill document` (no app: leave out `--app`) and follow what it prints: `must` rules are never broken, a `should` rule is broken only with the reason in the report, `EXCEPTION` and `OVERRIDDEN` lines say what does not apply to this app. It replaces reading long rule documents; read the DS `rules.md` only when the output says the profile keeps its rules there. `rules.py show <id>` explains one rule ([docs/rules.md](../../docs/rules.md)).

The skill owns the **DS profile** (`kit.config.json > ds`): its source files, version, changelog, Figma sync and docs.
Bringing a new DS version into apps is `sync`. `<kit>` below is the plugin root.

## Principles

- The DS profile is the **single source of truth**. Change the source files, then rebuild. Never hand-edit a built file (`css.bundle`, a built library page) and never fix the DS inside an app.
- Components use **semantic tokens only** (`ds.json > tokens.roles`). Semantic tokens point to primitives with `var()`. Raw values only where the primitive scale has no step (overlays, tints for dark mode).
- A new variant goes into the DS first; apps never override components.
- Never write a token value, class or version from memory. Source unreadable → stop and say so.
- `rules.md` lists the **protected intentional deviations** (accessibility fixes, density, overlays, dark mode, brand extras). A Figma sync never overwrites them; list them for the user.
- Dark mode and other modes not designed in Figma are **proposals**: say so, keep them optional through `ds.json > theming`, never on by default.
- A profile may have its own library build (`ds.json > library`, for example a library page or site generated from the sources). Use its build command or script as documented in the profile; this skill does not build a library website.
- Keep design-team internal notes out of shared docs.

## Profile layout

Read `ds.json` first; paths below are its defaults (see `docs/config.md` of the kit).

| File | Holds |
|---|---|
| `tokens.css`, `tokens-dark.css` | primitives and semantic tokens; dark mode |
| `base.css`, `components.css`, `responsive.css` | reset, components (semantic tokens only), breakpoints |
| `css.bundle` (`dist/<name>.css`) | the files above joined in `css.sources` order |
| `tokens.json` | tokens in DTCG format |
| `catalog.md` | components, variants, states, tokens, `components.map` (HTML class ↔ React ↔ Vue); page patterns and templates (master-detail, split panes, list pages) under `## Patterns` as `### <Name>` with `- Class:` and `- Use:` (a profile built by a script may list them in `ds.json > patterns` instead) |
| `catalog.json` | machine-readable catalogue built from `catalog.md` (`components`, `patterns`; `catalog.py patterns` lists the patterns), plus maintained fields: Figma mapping, status (active, experimental, deprecated + `replacedBy`), usage rules (`use`, `avoid`), accessibility notes |
| `rules.md` | hard rules and protected intentional deviations |
| `CHANGELOG.md` | one entry per version |

## Workflow for every change

1. **Understand the request**: component, token, mode, responsive behaviour. Read the affected source files.
2. **Edit the source** files only.
3. **Bump the version** in `ds.json > version` (semver):

   | Change | Bump |
   |---|---|
   | fix a value, a doc-visible bug, a state | `x.y.Z` |
   | add a token, component, variant or pattern | `x.Y.0` |
   | rename or remove a token or class, change a token's meaning (breaking) | `X.0.0` |
   | docs only, no token or CSS change | no bump; add a "Docs" line to `CHANGELOG.md` |

4. **Changelog**: one entry per version: what changed, tokens (name, old → new value), impact on apps, "Needs design confirmation" (every contrast drop, Figma deviation, unmatched name), apps not synced yet.
5. **Rebuild**: join `css.sources` into `css.bundle` in order, regenerate `tokens.json` and `catalog.md` entries that changed, then `python3 <kit>/skills/document/scripts/catalog.py build` (keeps the maintained fields) and `… check`, then the profile's own library build if it has one.
   - Retiring a component: never delete it in the same version. `catalog.py set <id> --status deprecated --replaced-by <id> --reason "..."`, note it in the changelog, run `review` (its scan lists apps still using it), remove it in a later major version.
   - Figma mapping and usage rules: `catalog.py set <id> --figma-component "..." --figma-key <key> --figma-node <id> --use "..." --avoid "..."`, only from facts you read in Figma or that the user stated.
6. **Update the shared docs in the same change** (same branch, same PR): `catalog.md` for components and variants, `rules.md` for rules and deviations, foundation docs for tokens, the "What's new" page for the version. Do not wait to be asked.
7. **Test** (below), including the contrast table.
8. **Report**: what changed, docs updated, version, apps still on the old version; propose `sync` for the apps.

Never commit, push or publish from a script. Work on a branch and open a PR only when the user asks; never merge.

## Tests

- Resolve `var()` for light, every dark block and every brand; compare before/after only for the tokens meant to change.
- Contrast for every colour that changes (text 4.5:1, control borders and icons 3:1) on the main backgrounds:
  ```
  python3 <kit>/skills/document/scripts/contrast.py --fg <roles.text> --bg <bg token> [--bg …] [--mode dark] [--min 3]
  ```
  Report before and after.
- Standard page checks with Playwright on the library page or a sample (Chromium is assumed installed; never run `playwright install`): no `pageerror`, no horizontal scroll at 400 px, light and dark, two brands, text size 200 % for mobile.
- Every token and class named in a doc exists in the source (see `references/doc-writing.md`).

## Sync from Figma

Use when the user shares a Figma link or file key of the design system. Read `references/figma-sync.md` and follow it: batches with a manifest on disk, normalise names to `ds.json > tokens.prefix`, diff by code, protect the deviations in `rules.md`, show the diff before applying wide changes.
Cannot read Figma (no access, no connector) → say so and stop at the part you can compare; never fill from memory.

## Write DS docs

Use when the user asks to write, fix, review or simplify DS docs for developers, QC, BA and designers. Read `references/doc-writing.md` first and fill `assets/component-doc-template.md`.

- One shared doc: a summary for everyone, then sections labelled [Dev] [QC] [BA] [Design].
- Facts from the source:
  ```
  python3 <kit>/skills/document/scripts/component_facts.py --list
  python3 <kit>/skills/document/scripts/component_facts.py <class> [<class> ...] [--key-only] [--json]
  ```
  Default CSS: the `css.sources` entries named `*component*`, else `css.bundle` (`--css` to override). It gives variants, states, declarations, tokens and hard-coded values.
- Never write a size or token from memory; unverified → "Unconfirmed".
- Read the draft four times, once per role, and check by machine that every token and class in it exists.
- Docs only → "Docs" line in `CHANGELOG.md`, no version bump.

## Promote an approved local proposal

When the user approved a proposal from `contribute`: use its proposal fields (purpose, anatomy, rules of use, tokens, variants, states) as the first draft, write the component into `components.css` and `catalog.md` like any other, bump `x.Y.0`, then tell `contribute` the entry is now in the DS (version and date). A proposal not yet approved never goes into the normative docs.

## Packaging the DS for readers

| Reader | Gets |
|---|---|
| BA | catalogue: component, class, variants, states, tokens, rules of use, gaps against Figma |
| QC | component docs with "States and expected result" and the test checklist |
| Developers | `css.bundle`, `tokens.json`, icons, and a short guide: tokens, base, components, theming attributes |
| Designers | `tokens.json` to compare with Figma variables |

Zip as `<ds.name>-<version>.zip` only when asked; scripts never send it.

## Rules

- Change the source, rebuild, bump the version, write the changelog, update the docs in the same change.
- Never overwrite a protected deviation from `rules.md` silently; list it.
- Never invent a token name; unmatched names go to "Needs design confirmation".
- Facts in docs come from the source or are marked "Unconfirmed".
