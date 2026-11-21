---
name: kickoff
description: "Set up a project for the kit: ask for language, stack, DS and the first app, write `kit.config.json`, link and validate the DS profile, create the first app from the stack template, write the project CLAUDE.md, the empty local-component registry and CHANGELOG.md, then run a smoke test. Use when there is no `kit.config.json`, or the user says 'set up the kit', 'start a new project', 'new prototype repo', 'change the stack', 'add another app'. Do not use to build a DS from a preset (`adopt`) or to build screens (`prototype`). Also use for the same request in any language."
---

# Kickoff: set up a project

Reply in the project language (`kit.config.json > language`; before it exists, the user's language). Generated documents use the same language.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

The project root is the current repository root.

## Step 1. Look at what exists

- `kit.config.json` exists → read it. Offer only the change the user asked for (new app, new stack, new DS link). Never rewrite it wholesale.
- List existing `ds/*/ds.json`, `apps/*`, `CLAUDE.md`, `CHANGELOG.md`, `docs/local-components.json`, `package.json`. Use them as defaults in step 2.

## Step 2. Ask (one AskUserQuestion round, at most 4 questions)

Skip any question the files already answer.

| # | Question | Options |
|---|---|---|
| 1 | Language for replies and generated documents | `en`, `vi`, other BCP 47 code |
| 2 | Stack | `html` (default: light, opens anywhere) · `react` · `vue` (team has a coded DS in that framework or developers reuse code). See `<kit>/docs/stacks.md`. |
| 3 | DS | Existing profile folder (path to `ds/<name>`) · existing coded DS package (npm name) · none → run `adopt` first |
| 4 | First app | id (`acme-web`), display name, type: `single` / `multi` (`html`) or `spa` (`react`, `vue`) |

DS answer "none": stop here, run `adopt`, then come back to step 3 with the profile it created.
DS answer "coded package": the profile still needs `ds.json`, `catalog.md` (with `components.map`) and `rules.md`. If none exist, run `adopt` with that package as the source, or ask the user for the profile.

## Step 3. Write `kit.config.json`

- Start from the example in `<kit>/docs/config.md`. Set `language`, `stack`, `ds`, and one `apps[]` entry (`id`, `name`, `path: apps/<id>`, `entry`, `type`, `build`, `check`). For `react`/`vue`: `build: "npm run build"` in the app folder.
- Keep the other keys at their defaults unless the user gave a value. Leave `deploy.site` `null`.
- File exists → show the diff and ask before writing.

## Step 4. Link and validate the DS profile

- Run `python3 <kit>/scripts/kitconf.py check`. Fix what it reports (wrong path, missing `ds.json`, missing `css.bundle`, bad prefix) or ask the user.
- Confirm `catalog.md` and `rules.md` exist in the profile. Missing → say which skills will be limited and suggest `adopt` or `document`.
- No `catalog.json` → build it: `python3 <kit>/skills/document/scripts/catalog.py build`, then `check`. A catalogue that does not parse (custom format) → say so; skills fall back to `catalog.md`.
- Never edit the DS profile here.

## Step 5. Create the first app

Run `python3 <kit>/skills/kickoff/scripts/scaffold.py --app <id> --name "<name>" --type <single|multi|spa>` (add `--dry-run` first to see the files). It copies the stack template, fills placeholders from config and `ds.json`, never overwrites files, and prints the `apps[]` entry to add if the app is not declared yet.

| Stack | Template | Then |
|---|---|---|
| `html` | `<kit>/templates/html/` | Embed `ds.json > css.bundle` between `/* @ds:begin */` and `/* @ds:end */`; set theming attributes on `<html>` from `ds.json > theming` defaults; version label in footer and `<meta>` |
| `html`, type `multi` | `<kit>/templates/html-multi/` | One file per feature; shared shell in `_shell/` (`shell.json` lists pages); after editing the shell run `python3 _shell/build.py build`, and `check` before a handoff. Set `apps[].build`/`check` to those commands |
| `react` | `<kit>/templates/react/` | `npm install`; import the DS CSS once in `src/index.css`; map Tailwind theme to DS tokens; version label in `index.html` and footer |
| `vue` | `<kit>/templates/vue/` | Same as React |

- `apps/<id>` exists and is not empty → ask before writing anything into it.
- Follow the template's own README if it has one.

## Step 6. Project files

Create each file only if it does not exist; otherwise ask (merge, skip or overwrite).

| File | Content |
|---|---|
| `CLAUDE.md` | From `<kit>/templates/CLAUDE.md`, placeholders filled from config and `ds.json` |
| `local.registry` (default `docs/local-components.json`) | Created by `python3 <kit>/skills/contribute/scripts/registry.py update` (empty `components` list) |
| `paths.changelog` (default `CHANGELOG.md`) | Title, then a first entry: date, "Project set up", stack, DS label and version, first app |
| `paths.plans`, `paths.audits` | Empty folders (add `.gitkeep`) |
| `paths.context` (default `product-context`) | Offer it; if the user agrees, `python3 <kit>/skills/context/scripts/context.py init`, then `context` fills it |

## Step 6b. Dress the skeleton with the DS
The templates are DS-agnostic: their shell uses neutral `app-*` classes styled only with the shadcn alias variables. Before handing over, swap the shell parts for DS components from `catalog.md` (top bar, navigation rail / bottom tab bar, icon button, list, card), keeping the router and IDs. In `react`/`vue`, use the components named in `components.map`. Then run `review`'s `audit_app.py`: no native control without a DS class, no hard-coded value.

## Step 7. Smoke test

| Stack | Test |
|---|---|
| `html` | Playwright (installed Chromium; never `playwright install`): open the entry file, no `pageerror`, no console errors except blocked web fonts, version label present, no horizontal scroll at 400 px |
| `react`, `vue` | `npm run build` passes; open the built entry with Playwright, same checks |

Rerun `python3 <kit>/scripts/kitconf.py check`; it must print `kit.config.json OK`.

## Step 8. Report

Files created and files skipped; stack, DS label and version, first app path; smoke test result; next step (usually `define` for a PRD, or `prototype` for a first screen).
Save only; no commit or PR unless the user asks.

## Rules

- Never overwrite an existing file without asking.
- Never invent a DS: no profile → `adopt`.
- Never hard-code DS values in the app skeleton; they come from `ds.json`.
- Never write secrets, real site URLs or personal data into config or `CLAUDE.md`.
