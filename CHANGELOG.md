# Changelog

## 0.11.1 · 2026-11-22
Fixes
- `catalog.py`: ids of components and page patterns fold diacritics (`Trang danh sách` -> `trang-danh-sach`) instead of dropping letters, as rule file names already do (K-R2). Found when a project profile listed page patterns with Vietnamese names.

## 0.11.0 · 2026-11-22
Fixes from a full trial run (one feature from requirement to handoff email, then one BA feedback round) and a side-by-side comparison with a project's own skills (K-F1…K-F20, K-B1…K-B10). Every new key has a default that keeps the 0.10 behaviour.

Validate
- `validate init --page <file> [--routes …] [--url <served URL>]`: plan for one page or a built bundle; parameter routes listed under `_paramRoutes`, named states under `_stateHints` (K-F5).
- Named states `"<theming key>=<value>"` and `"text=200%"` (root font size; px sizes and mobile system text scaling are not covered), `plan.states` for every screen; dark mode and theme states can go through the app's own switch (`validate.setTheme`) (K-F6, K-F19).
- axe scope (`plan.axe {include, exclude}`) and `waivers.json` (check or id + selector + required reason): known or out-of-scope findings go to "Known / waived" and never fail the run; every row is marked new or carried over against the previous run (`--compare`) (K-F7, K-B7).
- Contrast findings show the ratio, the required ratio and both colours; axe-core from `--axe`, `KIT_AXE_PATH` or `validate.axePath`, never installed into a project without `package.json` (K-F8, K-F9).
- `reload` step, and `goto` with `reload: true`, for hash-only routes after seeding storage (K-F10).

Annotate
- `capture.js`: `reload` step and `goto` with `reload: true` (K-F10); `noWait` on goto/reload and screen key `at: <ms>` capture short states such as a skeleton (K-F11).
- `capture.js`: before each screenshot the pointer leaves the page and a focused button or link is blurred, so `--baseline` pixel diffs no longer flag hover leftovers (K-B1); `neutral: false` turns it off.
- `spec_md.py notes`: writes and refreshes the screen sections and the Design notes table of `spec/<unit>.md` from screens.json and spec-map.json between `<!-- kit:…:begin/end -->` markers; rows keyed by screen, rule and selector, so a new pin renumbers codes without losing hand cells; `--check` reports out-of-date files (K-F12, K-B6).
- `spec_md.py check`: a folder without `screens/` skips screen, pin and image checks with one NOTE instead of false errors; `--screens <json>` runs them there (K-F13).

Handoff
- `pkg.json > status` (`final` / `awaiting-figma`) and `pkg.py relink`: a draft packaged with `--allow-missing-figma` gets its Figma links and a new zip without repackaging; order is handoff → wireflow → relink → share (K-B5).
- `finalize` refreshes the "Figma:" lines of `spec/*.md` and the Figma column of `spec/index.md` (K-B4).
- `pkg.py smoke <zip|folder>` runs the unpacked package in Chromium at `handoff.smokeWidths`: page and console errors, 4xx, broken images, horizontal scroll, blocked files (K-B9). Routes in `screens.json` no longer get a double `prototype/` prefix.
- Lock `nav_functions` take `{name, base: "page"|"app"}` (and `lock.nav_base`) (K-F15). `pkg.py proto` only counts bare file names in scripts (`--verbose` lists them) and lists pages reached only through a script registry (K-F16).

Wireflow and share
- `demo_links.py fill` also writes the demo links into `spec/flows.md` (`--md`, `--no-md`) (K-F14).
- The board build returns `map` (cards, image frames, flows, rows, edges with node ids): save it as `map.json`, no `mapjs` call needed after a first build. `figma_wireflow.py images` prepares `images/` and `pending.json` for an in-place update (K-B2).
- `figma_wireflow.py update --map --flows`: adds new screen cards in their row, relabels changed edges, adds rows and flows, prints `DIFF` lines; removed items are reported and kept unless `--prune` (K-B3). Template split into `wireflow-lib.js`, `wireflow-read.js`, `wireflow-update.js`; `--selftest` runs generated code against `figma_mock.js` (not yet run in real Figma).
- `wireflow` asks for an existing Figma file link before `create_new_file` (K-F20).
- `draft_email.py`: group names from `spec/index.md` instead of codes; changelog lines grouped Added / Changed / Fixed / Removed and an Added line is never folded into "UI refinements"; a first release says "Key features" (K-F17, K-B10). A package with status `awaiting-figma` is an ERROR unless `--allow-draft`.

Define and prototype
- `define`: the requirement source can be an existing running page; `extract_rules.py` drafts a parity checklist (visible text, messages, input constraints, limits, routes, storage keys, with `file:line`); porting ends with a parity check in `prototype` step 6 (K-F1).
- `docs/stacks.md`, `prototype`: pattern "Vue page inside a multi-page html app" (K-F2); the DS Vue layer folder needs `npm ci` first, `kickoff` prints a note (K-F3).
- New keys `apps[].pageContract` (printed by `kitconf.py contract --app <id>`, rule PAG-903) (K-F4) and `local.vueStyle` (`sfc` | `css-file`) with `local.vueCss` for projects that forbid CSS in `.vue` (K-F18).
- `catalog.py patterns`: page patterns from a `## Patterns` section of catalog.md or `ds.json > patterns`, searched by `find`; `define` step 5 checks patterns before writing "Missing" (K-B8).
- `prototype` step 6 runs `validate` instead of hand-written Playwright (K-B9).

Review checklists
- References: `validate/references/a11y-web.md` (W-codes, WCAG 2.2, how to write findings), `a11y-mobile.md` (M-codes, HIG and Material 3), `prototype/references/states-and-edge-data.md` (S- and D-codes), `review/references/motion.md` (C-codes) and `heuristics-rubric.md` (H1–H10 scored 0–4, also for `explore`). Credits kept: platform-design-skills (MIT), impeccable (Apache-2.0), emilkowalski/skills (MIT).
- New kit rules: A11Y-902 touch targets, A11Y-903 contrast in every mode, A11Y-904 reduced motion, A11Y-905 keyboard, CNT-902 empty/loading/error states (must), CNT-903 messages name the problem and the fix (should). A11Y-901 now covers names, labels and focus only.

## 0.10.0 · 2026-11-22
Fixes and extension points from three trial runs on a real project (handoff, rules and prototype, review and sync). Every new key has a default that keeps the 0.9 behaviour; behaviour changes only where 0.9 was wrong (listed under Fixes).

Fixes
- K-S1 `review`: the DS version label counts only as visible page text (comments, `<script>` and `<style>` are ignored: "since x.y.z" notes no longer make "several versions"); the `<meta>` version wins when a page has one.
- K-S2 `review`: identical CSS rules count once across files (a shared shell and its generated copy with other wrappers); see `apps[].generated` below.
- K-S3 `review`: LOCAL headers that span lines (`*` continuation) or hold a `*` (`.x-*`) are read whole; names compared with whitespace collapsed, so they match the registry.
- K-S4 `review`: "CSS lines" counts non-empty lines after the DS region is masked (a linked or embedded bundle no longer adds its lines).
- K-S5 `audit_map_tokens.py`: linear time (0.9 rescanned long blank runs and sliced the text per declaration: minutes on large apps; now under a second), a selector never starts with whitespace in the shared rule regex, each app mapped against its own DS profile (`apps[].ds`), `--selftest` with a time bound.
- K-S8 `catalog.py scan`: copies of the DS bundle (same file name, the app's `css.linkPath`) and embedded DS regions (`css.marker`, `css.styleBlocks`) are not counted as component use.
- K-S10 `review.extraChecks`: `{platform}` (`apps[].platform`) and `{stack}` placeholders; with `parse`, a row is Pass only at exit 0 when no matched line counts something (a number other than 0).
- K-S12 `review`: the report header names the DS per app when `apps[].ds` differ.
- K-R1 `rules.py import-md`: titles end at `.`, `!` or `?` (never at `:`), code spans keep their text (`/* LOCAL`, `FLAG_NAME`), emphasis is dropped only around words; severity `must` when the bullet uses a must word (English always, plus the project language: locale `rules.import.mustWords`), else `should`.
- K-R2 rule file names fold diacritics (NFKD, `d` for the stroked d) instead of dropping letters.
- K-R4 `rules.py check`: results are pass, fail or **skipped** with the reason: the command names an `http(s)://` URL that does not answer, `{path}` does not exist, or the command exits 77 or prints `SKIP: <reason>` (or the project-language word of locale `rules.check.skipWords`) on its first or last line. Skipped checks never pass silently; `review` shows them as Skipped, `validate` lists them under Skipped. `coverage` counts the checks that need a server. JSON results gain `status`, `reason`, `perApp` (`ok` is false only for a failure).
- K-R9 `validation.py run --rules-scope app` (default): only rule checks of the validated app (`{app}`, `{path}`, `{platform}`, `{stack}`) can fail the run; failing project-wide checks go to the new section "Outside the scope". `--rules-scope all` restores the 0.9 behaviour; a comma list of rule ids limits the blocking checks to those.
- K-R10 `prototype`: fill notes for every new **and changed** local registry entry.
- K-12 `spec_md.py styles`: properties a capture did not record are skipped (no "None → …"); token names are printed as names, not `var(--…)`. New `--selftest`.
- K-13 `capture.js`: values `0`, `none`, `normal`, `auto`, `transparent` get no token; `ds.json > tokens.ignorePrefixes` keeps primitive scales out of style notes.
- K-14 Wireflow image frames: `mapjs`, `retitlejs` and the `mockup` audit accept the English suffix, the locale suffix (`wireflow.imageSuffix`) and `kit.config.json > figma.imageSuffix` (also the suffix new boards get; default `" · image"` as before).
- K-16 `capture.js` records `search` (the query of the page or of the last `goto`); `pkg.py finalize` keeps it in each route (`index.html?demo=1#/x`), also for older captures (read from the steps).
- K-17 AGENTS.md grep labels add the locale labels for intentional deviations and "no screen for this item".
- K-21 `share`: in a `.md`/`.txt` email template the HTML body links Figma and demo URLs with the locale labels (`share.openFigma`, `share.openDemo`); `draft_email.py` and the SKILL warn that some mail connectors refuse an attachment on a draft without recipients.

Handoff
- K-15 `pkg.py capture --baseline <screens.json | image folder of the previous package>`: new and changed screens against the delivered version (route, pin styles, pixels; images at another scale are resized and softened first); `changed.json` says why.
- K-18 `pkg.json > csv` (`{feature, qc}`, the shape of `handoff.csv`) overrides the project headers for one package.
- K-20 `pkg.py proto --pages … --into <package>/prototype (--app | --root)`: copies the pages and only the files they load (href, src, srcset, `url()`, `@import`, file paths named in scripts and JSON, followed transitively), keeps relative paths, leaves other pages out and lists them, lists references it could not resolve.

Validate
- K-19 every `validation.py` command takes `--dir <folder>` (plan, runs, baseline outside `paths.validation`).
- K-R8 `validation.py init` reads the app: one screen per page and hash route (`href="#/…"`, `"#/…"` in route tables, router paths), one flow per hash link, control ids as `_selectors` hints. `--blank` writes the 0.9 template.

Extension points (all off by default)
- K-S2 `apps[].generated` (globs: build output of the app's own sources, skipped by `review`) and `apps[].sources` (globs: sources outside the app folder, scanned with it).
- K-S6 `ds.json > changelog` (`path`, `format` `md` | `json`, `versionKey`, `match`, `fields`): `sync_ds.py changes` reads the DS changelog where the project keeps it; a missing file is an ERROR that names the key.
- K-S7 `sync.prepare` (before the sync, e.g. rebuild the DS library from source) and `sync.post` (after it); after every `apply` the script lists the files that changed per app and the LOCAL blocks added, removed or changed; `status` says it checks the built DS, not DS sources. The SKILL follows the project's own branch and PR rules; scripts still never commit, push or publish.
- K-S9 `ds.json > rules` may be `{"file": "rules.md", "from": "<other profile>"}`: a profile inherits another profile's DS-layer rules, read once and applied to the apps of both (no duplicate ids in `conflicts`).
- K-S11 `ds.json > review.genericClasses`: utility classes never counted as overrides and never measured by the browser step.
- K-R3 `rules.py import-md --layer ds [--app A]` drafts straight into the profile's `rules/` folder.
- K-R5 rule `skills` may name activity groups (`scripts`, `pr`, `commit`, `deploy`, `release`) and `"*"` (every skill, like `[]`): a rule that names only activities stays out of `list --skill prototype`.
- `prototype.post`: optional project step after a build, run with `kitconf.py hook prototype.post --app <id>` (the generic runner for optional project commands: `{app}`, `{path}`, `{root}`).

Generalised
- K-R6 `ds.json > css.load` (`embed` default | `link`) with `css.linkPath`, per app `apps[].css`: `kickoff` writes one DS file and links it from every page, `sync` (built-in) rewrites that file, `review` treats it as DS CSS, `catalog.py scan` skips it, `pkg.py proto` copies it with the pages; `prototype`, `kickoff` and [docs/stacks.md](docs/stacks.md) no longer say every html page embeds the DS.
- K-R7 `prototype`: step 0 (which DS profile and design source apply: `apps[].ds`, optional `apps[].designSource` note, `css.load`), a build ladder (reuse a DS component, compose, local block, propose), edge states and edge data in the tests, PRs through the project's own rules; no artifact or publish step in the kit (optional `prototype.post`).

New keys (defaults keep 0.9): `apps[].generated`, `apps[].sources`, `apps[].designSource`, `apps[].css` (`null`), `sync.prepare`, `sync.post`, `prototype.post` (`null`), `figma.imageSuffix` (`null`), `ds.json > css.load` (`embed`), `css.linkPath` (`null`), `tokens.ignorePrefixes` (`[]`), `changelog` (`null` = `CHANGELOG.md`), `review.genericClasses` (`[]`), `rules` object form, `pkg.json > csv`. `kitconf.py check` validates `css.load`, `apps[].css`, `apps[].generated`/`sources`, `changelog.format`, `rules.from`, `ignorePrefixes`, `genericClasses`.

Tests: `tests/e2e.py` 107 checks (89 in 0.9): skipped rule checks and their reasons, activity groups, `rules.from`, `import-md --layer ds`, `css.load link` through kickoff, sync and review, `sync.prepare`/`post` with the change report, review dedupe and `apps[].generated`, `validate init` from the app with `--dir`, `prototype.post` through `kitconf.py hook`, `pkg.py proto`; new `--selftest` of `audit_map_tokens.py` (time bound), `spec_md.py` and `catalog.py`, more cases in every changed script.

## 0.9.0 · 2026-11-22
The rules registry, eleven fixes from a second real-package pilot, a DS profile per app and a project email layout. Every new key has a default that keeps the 0.7 behaviour; behaviour changes only where 0.7 was wrong (listed under Fixes).

Rules registry (new, `scripts/rules.py`, [docs/rules.md](docs/rules.md))
- One Markdown file per rule with a small front matter read by the standard library: `id` (category prefix + number), `title`, `category`, `layer` (`kit`, `ds`, `project`, `app`), `applies_to`, `skills`, `severity` (`must`, `should`, `note`), `status` (`proposed`, `active`, `deprecated`, `superseded`), `since`, `decision` (decision log id; required for active project and app rules when the project keeps a log), `check` (command, `{app}`, `{path}`, `{root}`), `overrides` + `reason`, `exceptions` (`app`, `note`, `decision`), `superseded_by`, `supersedes`, `history`. Body = rule, then why, in the project language.
- Layers and folders: kit `rules/` (14 generic rules: tokens only, no CSS over DS components, theming attributes, one density, ask before a new component, ask before a new page, keep business rules when a page is rebuilt, reference images give layout only, mock data, no loose `.js` in packages, drafts only, no secrets, names/labels/focus, version label), DS `<profile>/rules/`, project and app `paths.rules` (default `rules/`). Precedence kit < ds < project < app with explicit `overrides`; id ranges per layer (kit 900–999, DS 500–899, project and app 001–499) keep ids unique across upgrades. Recommended categories with prefixes; `rules.categories` adds more.
- Commands: `list` (filters `--app --skill --category --severity --status --layer`; layers, overrides and exceptions resolved; `--json`), `show`/`explain` (text, where it applies, state for an app, decision with who decided, exceptions, history; locale en/vi), `add` (next id, validation, decision link: a decision not approved keeps the rule proposed), `except`, `deprecate`, `supersede --by --decision`, `check` (exit 1 on a failing must rule; `--json`), `coverage`, `conflicts`, `export` (`md`, `html` "Project rules" page, `claude` block between `<!-- kit:rules:begin/end -->`, `--into` replaces it in place), `import-md` (drafts from an existing rules document: one rule per top-level bullet, status proposed, `since`/`decision` `Unconfirmed`, `_import-review.md`). `--selftest`.
- Skills: every skill that builds, reviews or packages starts with `rules.py list --app <app> --skill <name>` instead of reading long rule documents (the DS `rules.md` only when `list` says the profile keeps its rules there). `review` (`audit_app.py`) adds one row per rule check and app (must = Deviation, else Note; `--no-rules`); `validate` (`validation.py run`) puts failing checks in the report (must = Fail, else Needs a human; `--no-rules`). `context` owns the registry (add, except, supersede, explain, import); `decisions.py` offers `rules.py add --decision` when a decision is approved; `kickoff` (`scaffold.py`) creates the rules folder; `brief` routes rule requests; `templates/CLAUDE.md` has the generated block.

Fixes from the pilot (K-1…K-11)
- K-1 `lock.seed` / `hide.seed` run in their own `<script id="x-handover-seed">` at the top of `<head>` (after `<meta charset>`), before every app script; app code that reads the key while it loads sees it. `references/scope-layers.md` states the order.
- K-2 `finalize` replaces only the sentence that points at screen images, keeps the rest of the line, and adds no locale sentence when the line already points at Figma.
- K-3 `handoff.specFiles.legacy` may be `{"archive": [...], "crossPage": [...]}`: AGENTS (Dev path, archive line) and the archive step use the older file when the package has it or README/AGENTS/changelog point at it. The list form still works as before.
- K-4 `lock.open_block`: regex tested first on `window.open` and link URLs (written and resolved); blocks even a page of the package (same page with another feature's hash). `init` writes it empty.
- K-5 `review`: root classes from the profile's `catalog.json` when it exists; files other apps build into an app (`apps[].usedBy`) skipped; DS version read only from pages (HTML meta and footer, Vue/JSX/TSX label text), never from scripts; `review.extraChecks` take `{path}`; `parse` that matches nothing prints the last line (as documented), not "—".
- K-6 `apps[].type: "page"` with `usedBy` (required) and `output`: one page built in another stack and copied into other apps. `kitconf.py check` accepts it.
- K-7 `handoff.specFields` (`{"ds": "<old key>"}`): older frontmatter keys of `spec/index.md` are read by `spec_md.py` and `pkg.py`; a bare version becomes the profile's version label. No more sed in packaging.
- K-8 / Part 4 `email.template`: a project `.md`/`.txt`/`.html` layout with placeholders (`{greeting}`, `{figma}`, `{sections}`, `{package}`…, `{language}` in the path); default = the 0.7 layout. `draft_email.py --template`, `--selftest`.
- K-9 Behaviour note: `capture.js` records the border colour and its stroke token only when the border is wider than 0 (since 0.6). Style notes of elements without a border have no stroke line; documented in `references/manifest.md`.
- K-10 One step timeout for capture and validate: steps without `timeout` wait `manifest.timeout` / `plan.timeout`, default 8000 ms in both (`validate.js` waited 3 s). `validation.py init --from-manifest` writes `timeout` into the plan.
- K-11 `validate` no longer reports text for screen readers only (1×1 box, `clip`, `clip-path`) as clipped, a hidden file input as a small target, or a link inside a sentence (WCAG 2.5.8 inline exception).

DS profile per app (Part 3)
- `apps[].ds` overrides the top-level `ds` for that app (for example a mobile profile with its own version numbering). `kitconf.load(app=…)`, `for_app`, `profiles` (Python) and `load(…, app)`, `forApp` (Node); every script that works on one app uses its profile: `capture.js` (`--app`, `manifest.app`), `pkg.py` (`pkg.json > app`; `capture --app`), `spec_md.py` (`app:` in the frontmatter), `validation.py`, `validate`, `audit_app.py` (one DS fact set per profile), `sync_ds.py` (status/apply per app), `draft_email.py`, `scaffold.py`, `catalog.py scan`, `verify.py`, `explore.py`, `figma_wireflow.py`, `rules.py` (DS rules apply to the apps of their profile). `kitconf.py check` validates each app profile (ds.json, prefix, bundle); `kitconf.py --app <id>` prints the merged configuration.

New keys (defaults keep 0.7): `apps[].ds` (top-level `ds`), `apps[].usedBy`, `apps[].output`, `apps[].type: page`, `handoff.specFields` (`{}`), `handoff.specFiles.legacy` as object, `email.template` (`null`), `paths.rules` (`rules`), `rules.categories` (`{}`), `pkg.json > lock.open_block` (`""`), `manifest.timeout` / `plan.timeout` (8000), `manifest.app`.

Tests: `tests/e2e.py` 89 checks (49 in 0.7): every `rules.py` command, rule rows in review and validate, apps[].ds through kickoff, sync, review and kitconf, type page + usedBy, specFields, legacy object, seed order in Chromium, open_block, sentence replacement, K-11 filters, email.template (.md and .html); new `--selftest` of `rules.py` and `draft_email.py`.

## 0.8.0 · 2026-11-21
- New preset `atelier` for `adopt` (`--preset atelier`): dark-first, warm neutral surfaces that lighten step by step, the brand colour kept for the main action and the selected state (text, stroke and tint plus a check mark), inset sheen on dark surfaces and soft drop shadows in light mode, a brand glow on the primary button, Manrope for headings and labels on Geist body text, Geist Mono for metadata, dashed list separators. Light mode included. Same class names and shadcn alias layer as the shadcn preset, so prototypes, stack templates and audits work unchanged. Taken from the author's own design system under MIT; no code, images or personal content.
- `adopt`: radius, font and the new display font (`--font-display`) default to the preset's values; `preset.json > defaults.mode` sets the default mode in `ds.json` and the library page (atelier: dark); shadows may name semantic tokens (`{bg-brand}`); a preset may replace a contrast pair with another check (`contrast_skip`, recorded in `ds.json > contrast.skip` and `rules.md`); the bundle header names the preset's licence. Every profile now defines `font-family-display` (the sans family unless the preset sets one). shadcn profiles are otherwise unchanged.

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
