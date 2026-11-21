# Changelog

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
