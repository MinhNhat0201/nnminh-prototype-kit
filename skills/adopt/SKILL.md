---
name: adopt
description: "Build a base DS profile for a project that has no design system: aesthetic layer (tokens, component recipes) from a public preset (default and only preset now: shadcn, which also serves shadcn-vue) and structure layer from Material Design 3 (window size classes, 48 px touch targets, bottom sheet, tab bar, navigation rail, FAB, density). Asks for brand seed colour, name and prefix, radius, font, dark mode; generates ds.json, tokens (DTCG and CSS), components, bundle, catalog, rules, library page, Flutter theme; checks contrast; optionally pushes variables and text styles to Figma. Use when the user says 'we have no design system', 'start from shadcn', 'create a base DS', 'make a DS from our brand colour', or when `kickoff`/`brief` finds no DS. Do not use to link an existing profile (`kickoff`), to change tokens of an existing DS (`document`), or to bring a new DS version into apps (`sync`). Also use for the same request in any language."
---

# Adopt: base DS profile from a preset

Reply in the project language (`kit.config.json > language`; no config yet → the user's language). Generated documents use the same language.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

Script: `S=<kit>/skills/adopt/scripts/adopt.py` (`--help` lists every command).

## The two layers

| Layer | Source | Gives |
|---|---|---|
| Aesthetic | Preset (`<kit>/presets/<preset>/`) | Neutral palette, semantic roles light and dark, radius scale, type scale, shadows, component recipes |
| Structure | Material Design 3 guidelines | Window size classes compact < 600, medium 600–839, expanded ≥ 840 px; 48 px touch target; bottom sheet, bottom tab bar, navigation rail, FAB, top bar; density levels |
| Brand | The designer | Seed colour → tonal brand palette; name, prefix, radius, font |

Where the layers clash, the component uses Material structure with preset tokens and is listed as **composed** in `catalog.md` and `rules.md`.

The result must not look like a copy of the preset: the seed colour and the prefix are always the designer's choice. Never pick them silently.

## Step 1. Check the ground

- Run `python3 <kit>/scripts/kitconf.py check` if `kit.config.json` exists. A linked DS already exists → stop and ask: replace it, build a second profile, or use `document` instead.
- The user named a coded DS package (from `kickoff`): this skill does not import packages in this version. Say so and offer a preset-based profile, or ask for the package's `ds.json`, `catalog.md` and `rules.md`.
- Target folder: `ds/<name>` in the project (default). It exists and is not empty → ask before `--force`.

## Step 2. Ask (one AskUserQuestion round, at most 4 questions)

| # | Question | Options |
|---|---|---|
| 1 | Preset | `shadcn` (default; shadcn/ui, same variables for shadcn-vue). Show other presets as "later", not selectable. |
| 2 | Brand seed colour | Hex the user types (`#2563eb` is only an example). Offer 3 starter hues if they have none; never choose for them. |
| 3 | Name and token prefix | Name (`acme`), label ("Acme DS"), prefix (default `--<name>-`). Classes use the prefix without the dashes (`acme-btn`). |
| 4 | Radius, font, dark mode | Radius in px (preset default 10; 0 square, 6 tight, 8, 10, 12 soft); font (default Inter, OFL; never a font owned by a platform vendor); dark mode yes (default) / no |

Platforms default to `web,mobile,tablet`; change only if the user says so. Icons: Tabler (MIT). Density default: `auto`.

## Step 3. Generate

```bash
python3 $S --name acme --label "Acme DS" --prefix --acme- --seed "#2563eb" \
  --radius 8 --font Inter --out ds/acme [--no-dark] [--lang vi]
```

- The script prints every contrast pair (light and dark): text 4.5:1; icons, strokes, component boundaries 3:1. A failing role is moved one half tone at a time (darker in light mode, lighter in dark) until it passes; the move is reported as ADJUSTED and written to `rules.md`.
- A pair that still fails → the script stops with `ERROR:` and writes nothing. Tell the user which pair and ask for another seed (usually darker or more saturated). Never lower the thresholds.

Profile written (layout per `<kit>/docs/config.md`):

| File | Content |
|---|---|
| `ds.json` | Profile config; `preset` names the preset and its upstream version |
| `tokens.json` | W3C DTCG: primitives, semantic (all modes in `$extensions.kit.modes`), density, typography |
| `tokens.css`, `tokens-dark.css` | Primitives, semantic tokens, density (`data-density`), mode (`data-mode`, also `.dark`), shadcn alias layer |
| `base.css`, `components.css`, `responsive.css` | Reset and text styles; ~30 components with semantic tokens only; app shell rail ↔ tab bar |
| `dist/<name>.css` | Bundle wrapped in `/* @ds:begin */ … /* @ds:end */` |
| `catalog.md`, `rules.md` | Classes, variants, states, tokens, `components.map` (HTML ↔ shadcn/ui ↔ shadcn-vue); hard rules, deviations, contrast table |
| `library.html` | Self-contained demo of every component; mode toggle, density switch |
| `figma-variables.json`, `icons.json` | Data for Figma level 1; Tabler starter icons |
| `flutter/<name>_theme.dart` | Theme generated from tokens. **Not compiled**: say so; developers run `flutter analyze` |
| `NOTICE`, `CHANGELOG.md` | Origin and licences; 0.1.0 entry |

Alias contract: the bundle defines `--background`, `--foreground`, `--card*`, `--popover*`, `--primary*`, `--secondary*`, `--muted*`, `--accent*`, `--destructive`, `--border`, `--input`, `--ring`, `--radius`, `--chart-1..5`, `--sidebar*`, all pointing at DS semantic tokens, so shadcn/ui and shadcn-vue components render with the DS.

| Stack | How the profile is used |
|---|---|
| `html` | Embed `dist/<name>.css`; build with the classes in `catalog.md` |
| `react` | Import the bundle once; shadcn/ui components read the alias layer; names from `components.map` (React column) |
| `vue` | Same with shadcn-vue (Vue column) |

## Step 4. Check

```bash
python3 $S check --out ds/acme
```

Must print `Profile OK`. It checks files, bundle markers, no hex/`rgb()`/px/primitive tokens in component CSS, every used token defined, the alias layer, and contrast. Fix the generator input, never the generated CSS by hand.

Then open `library.html` with Playwright (installed Chromium; never `playwright install`): no `pageerror`, no console errors, no horizontal scroll at 400, 768 and 1280 px, light and dark. Take one screenshot per mode and look at it.

## Step 5. Show the library page

Give the user the path of `library.html` and a short summary: seed position in the brand scale, adjusted tones, composed components. Offer to publish it as a page if the host supports it; never publish without asking.

## Step 6. Figma (optional; ask first)

| Level | What | Status |
|---|---|---|
| 1 | Variables (collections Primitives; Semantic with Light/Dark; Spacing with Comfortable/Standard/Compact) and text styles | This version |
| 2 | Duplicate a community shadcn Figma kit, then remap its variables to the DS | Guided step, user does the duplicate |
| 3 | Full component library built from the DS | Later |

Level 1:
1. Ask for a Figma Design file the user can edit (or create one with `figma-create-new-file`).
2. Load the `figma-use` skill (mandatory before any `use_figma` call). Call `create_session` with the file key.
3. `python3 $S figma-script --out ds/acme --js <scratch>/figma-push.js`, then send that file's content as the code of one `use_figma` call. It is idempotent: rerun to update.
4. Read the returned report: variable counts per collection, text styles, warnings (missing font, mode limit of the Figma plan). Report warnings as they are; never claim a mode or style that was not created.
5. Store the file key in `ds.json > figma.libraries` only if the user agrees.

Level 2: tell the user to duplicate a shadcn community kit they choose (check its licence), then map its variables to the DS collections by name with `figma-use`. Do not copy a kit's styles into the DS.

## Step 7. Hand over to `kickoff`

Return to `kickoff` (step 3 onwards) with `ds: "ds/<name>"`, or run it now. Report: profile path, label and version, preset and upstream version, seed, prefix, adjusted tones, composed components, contrast summary, Figma level done, open points.

## Rules

- Never pick the seed colour or the prefix for the user.
- Never edit generated files by hand; change inputs and rerun with `--force`.
- Never use a vendor-owned font, logo or icon set; Tabler (MIT) is the icon set.
- Never lower contrast thresholds; a failing seed goes back to the user.
- Keep `NOTICE` in the profile (MIT attribution of the preset).
- Save only; no commit, push or publish unless the user asks.
