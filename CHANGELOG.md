# Changelog

## 0.7.0 · 2026-11-21
Fixes from a real handoff run, and extension points so a project can keep its own scripts. Every new key has a default that keeps the 0.6 behaviour; the fixes change behaviour only where 0.6 was wrong.

Handoff (`pkg.py`, `scope-lock.js`, `scope-hide.js`)
- One DS label per package, from one source: `handoff.dsLabel` (`auto` = `pkg.json > ds_label`, then `ds` in the frontmatter of `spec/index.md`, then `ds.json`; or `pkg`, `spec`, `ds`, `prototype`). `finalize` compares it with the `<meta name="<version_label.meta>">` of the package pages and with `spec/index.md`; `handoff.dsLabelCheck` = `warn` (default), `error` or `off`. `init` writes `ds_label`.
- `finalize` prints every WARN and ERROR line of the spec check, not only the last line.
- `finalize` checks file references (`spec/…`, `screens/…`, `requirements/…`, `prototype/…`, `assets/…`, `attachments/…`) in README, AGENTS and `spec/*.md` (ERROR) and in the changelog (WARN). Sentences that point at screen images (`screens/<id>.webp`) become the locale sentence `handoff.spec.imagesOnBoard`; table cells with `screens/Sxx.webp` become the Figma link in every spec file.
- Names of the special spec files are configurable: `handoff.specFiles` (`archive`, `crossPage`, `legacy` names still read as special files); `annotate`'s `spec_md.py` no longer counts them as units.
- `handoff.itemLabel` (text before the work-item code in AGENTS, the lock toast and the meta), `handoff.grepLabels` (extra grep labels in AGENTS). The `x-handover` meta text comes from the locale (`handoff.layer.lock`, `handoff.layer.hide`).
- Lock layer: pages compared on resolved paths relative to the package root, whole path (a relative `window.open` of a page in the package opens; `notes/index.html` no longer matches `index.html`); `open_allow` tested on the written and the resolved URL; `allow_when` (per-route allow rules: selector + hash/path regex); `page_keys` (navigation keys mapped to files); `toast.args` (extra arguments of the app's toast function, dotted names allowed), `toast.icon`, `toast.close_html` (default close button: `aria-label` + outline icon, no bare "×"), defaults from `ds.json > toast`; `dragover`/`dragenter` stopped; `seed` (storage keys set on load when absent; also for the hide layer).
- `pkg.py capture --only` really passes `--only` to `capture.js`; changed images are compared only for those screens.
- `handoff.pre` / `handoff.post`: project commands around `finalize` (`{pkg}`, `{config}`, `{zip}`, `{root}`).
- CSV headers configurable: `handoff.csv.feature|qc` (comma string, list, or `{role: header}`); `init` writes them, `finalize` warns when the package header differs; `share` finds the feature columns by role.
- `references/package-layout.md`: serve the package folder (images are in `assets/` next to `prototype/`), not `prototype/`.

Capture and validate
- `capture.js`: `--only` runs only the asked screens and the screens they continue from; an iframe named by a selector (`F|…`) or `in` that is not in `manifest.frames` is an ERROR before the browser starts; frame-prefixed legacy steps (`fclick`, `ehover`, `ffill`, `ewait: sel`…) are read as `click` + `in`, and `screens.json` records the current form. `--selftest`.
- `validation.py init --from-manifest <manifest> --base <URL>`: plan screens from a capture manifest (steps inlined, frames kept, plan `url`). Screens can carry `steps` and `viewports`; `validate.js` runs the manifest step vocabulary (hover, type, eval, waitFor, waitEval, waitUrl, files, reset, `in` frames) for screens and flows.
- Touch targets per platform: `apps[].platform` + `validate.touchTarget` (`{"default": 44, "desktop": 24}`), `ds.json > touchTarget`, `--touch-min`.

Wireflow
- `demo_links.py`: a relative page path keeps its page folder; `--page-root` drops the served copy's root folder. `--selftest`.

Extension points (docs/config.md "Project commands")
- `sync.command` / `sync.check` (also `ds.json > sync`): `sync_ds.py apply`/`status` run the project's commands and report their output; `--builtin` forces the kit's own. `--selftest`.
- `local.command.update|check` and `local.fields` ({kit field: project field}); the registry keeps unknown fields, also under `apps`. `--builtin`. `--selftest`.
- `review.extraChecks` ([{name, command, parse?, level?}]): rows in the audit report, per app with `{app}`; `--no-extra`. `--selftest`.
- `email.demoLinks` (default `true`; `false` = no demo, prototype or flow link; also `--no-demo`) and `email.maxItems` (default 12).
- `ds.json > components.vue` ({package, propsMap}): vue apps use the DS's own Vue component layer: `kickoff` picks the plain Vue template with the `@ds-vue` alias (or the npm dependency), `prototype` builds only with those components, `review` reports local `.vue` files named like a DS component and shadcn-vue imports. `ds.json > tailwind: false`: plain templates for react and vue (`templates/react-plain`, `templates/vue-plain`, overlays on the stack templates), no Tailwind row in `review`. `scaffold.py --selftest`.
- `skills.<name>.model|effort` hints in `kit.config.json`; every skill reads its own, `brief` passes them on; `kitconf.py skills` lists them; `kitconf.py check` validates them. `kitconf.py --selftest`.

Tests
- `tests/e2e.py`: runs every `--selftest`, then a throw-away project (adopt, kickoff html multi + plain vue, registry, review, sync, validate from a manifest, capture, lock layer in Chromium, finalize, zip, email, demo links). 49 checks.

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
