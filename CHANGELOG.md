# Changelog

## 0.6.0 · 2026-11-21
- New skill `verify`: compares a developer build with the approved prototype after handoff. `verify.js` (Playwright) opens each screen pair at each viewport on both sides and collects masked full-page screenshots, the colours, font sizes and radii in use, DS component classes, visible labels and headings, console errors and, on the build, axe-core results; then runs each flow on both sides. Token values are resolved in the prototype, which embeds the DS.
- `verify.py`: `init` (pairs.json), `run` (report with Fail, Differences to review, Approved deviations and Skipped; side-by-side images prototype · build · differences; visual differences from 500 px or 1 %; values outside the DS tokens and not in the prototype; missing DS components; missing texts; flows that pass in the prototype but fail in the build), `accept` (a difference becomes an approved deviation only with an approved, implemented or verified decision; failures cannot be accepted), `close` (after a clean run, decisions in scope move from implemented to verified; refuses while failures remain or differences are unanswered), `report`. Findings have stable ids across runs.
- `brief` routes design-QA requests; `handoff` names `verify` as the next step; README, docs and the CLAUDE.md template list it. New config key `paths.verify` (default `docs/verify`). Locales `verify` (en, vi).

## 0.5.0 · 2026-11-21
- Machine-readable component catalogue: `catalog.json` next to `catalog.md` in the DS profile (`ds.json > catalog_json`). `document/scripts/catalog.py`: `build` (parses components, variants with their classes, states, source, structure, tokens and `components.map`; keeps the fields people maintain), `check` (classes and variant classes exist in the DS CSS, tokens are defined, deprecated components name an existing replacement, unique ids), `find` (look a role up by words), `show`, `set` (status active / experimental / deprecated with `replacedBy` and reason; Figma component, key and node; usage `use` / `avoid`; accessibility notes), `scan --app` (components used by an app, by class and by React/Vue name; exits 1 when a deprecated component is still in use). Works from a project or with `--ds <profile>`.
- `adopt` builds `catalog.json`; `kickoff` builds it for linked profiles; `document` rebuilds it, deprecates instead of deleting, and records Figma mapping and usage rules; `prototype` looks components up in it and never uses deprecated ones; `review` reports deprecated components still in use; `mockup` uses the Figma mapping first.

## 0.4.0 · 2026-11-21
- New skill `validate`: browser checks of a prototype written to one report that separates **Fail** (page or console errors, horizontal overflow, axe-core critical/serious, failing flow steps), **Needs a human** (touch targets under 44 px on phones, clipped text, no visible focus ring, axe moderate/minor, visual changes) and **Skipped** (with the reason). Runs every screen and listed state (`prepare` scripts) at 390, 768 and 1280 px in light and dark mode, then every flow (click, fill, select, press, goto, expect…).
- `validation.py`: `init` (plan.json with screens, states, flows), `run` (Playwright via `validate.js`, screenshot comparison with the accepted baseline using Pillow: changed when at least `--min-pixels` 100 or `--threshold` 0.5 % differ, highlighted diffs), `baseline` (accept a run after a human looked), `report`. Accessibility uses `axe-core` when the project has it; otherwise it is reported as skipped, never as passed.
- `prototype` runs `validate` as its test step; `handoff` needs a current report with Fail (0); `brief` routes QA requests.
- New config key `paths.validation` (default `docs/validation`). Locales `validate` (en, vi).

## 0.3.0 · 2026-11-21
- New skill `context`: product memory every skill reads, in `paths.context` (default `product-context`): product overview, personas, UX principles, business rules, constraints, in the project language (`context.py init`, `check`, `summary`).
- Decision log (`decisions.py add`, `set`, `list`, `show`, `index`, `check`): one Markdown file per decision with a status lifecycle observed → proposed → approved → implemented → verified, plus rejected and superseded. Moves outside the lifecycle are refused; approved and rejected need the name of who decided; observed needs a source; superseding is recorded on both decisions; `check` also validates the history lines against the status.
- `explore choose` records the user's choice as an approved decision when the project keeps a log. `define` reads the context and logs the business decisions it proposes; `prototype` reads principles, rules and approved decisions, and moves built decisions to implemented; `handoff` adds `spec/decisions.md` (approved, implemented, verified decisions in scope); `kickoff` offers to create the folder; `brief` routes memory requests.
- Locales `context` (en, vi).

## 0.2.0 · 2026-11-21
- New skill `explore`: two to four design directions for one design question, built with the DS as light HTML pages, before any prototype. `explore.py` creates the exploration (`init`), validates it (`check`: DS markers, version meta, no raw colours, every direction described with strengths, weaknesses, risks, DS fit and effort), writes `compare.html` (directions side by side or one at a time, phone/tablet/desktop frames) and records the human decision (`choose`: chosen, rejected and merged parts, reason, `decision.md`). The skill never chooses for the user.
- `define` marks waves with a real design question and suggests `explore`; `prototype` builds only from a chosen direction and stops when no decision is recorded; `brief` routes "show me options" requests.
- New config key `paths.explorations` (default `docs/explorations`). New helper `scripts/dshtml.py` (embed the DS CSS, theming defaults and version label in a standalone page).
- Locales `explore` (en, vi).

## 0.1.2 · 2026-11-21
- `apps[].stack` is honoured everywhere: `review` (`audit_app.py`, report header lists app overrides), `contribute` (`registry.py` scans `src/components/local/` for react/vue apps), `sync` (`sync_ds.py`), `kickoff` (`scaffold.py` picks the template from the app's stack; new `--stack` option; the suggested `apps[]` entry includes `stack` when it differs).

## 0.1.1 · 2026-11-21
- `review` (`audit_app.py`): a native control inside a DS wrapper is no longer reported as home-made. Wrapper classes are read from the DS CSS (`.acme-select > select` needs the parent, `.acme-x select` any ancestor), so `<span class="acme-select"><select>` passes, as in `library.html`.
- `review` (`audit_app.py`): reads DS CSS embedded as `<style id="<css.styleBlocks>…">` blocks, as a copy of the bundle inside the app, or through `<link href>` to it; theming attributes are read only from `<html>` and `documentElement` (the same attribute on other elements is app state); local blocks also match the registry `anchor`; non-object entries under `ds.json > theming` are skipped.
- `docs/config.md`: `css.styleBlocks`.

## 0.1.0 · 2026-11-21
- First release: 14 skills (`brief`, `kickoff`, `adopt`, `define`, `prototype`, `annotate`, `wireflow`, `mockup`, `handoff`, `share`, `review`, `sync`, `contribute`, `document`).
- Configuration through `kit.config.json` and `ds/<name>/ds.json`; helpers `scripts/kitconf.py` and `scripts/kitconf.js`.
- Stacks `html`, `react`, `vue`, with a per-app override; templates for each (`html`, `html-multi`, Vite + Tailwind v4 for React and Vue, single-file handoff build).
- Default preset `shadcn` (shadcn/ui 4.23.0, shadcn-vue 2.9.0 values) with Material 3 structure for mobile and tablet.
- English and Vietnamese locales for generated documents.
- Known gaps: Figma scripts tested against a mock of the Figma API only; the generated Flutter theme is not compiled; the Figma variables script may need two `use_figma` calls on large profiles.
