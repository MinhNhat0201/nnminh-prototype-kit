# Configuration

The kit reads two files. Skills and scripts never hard-code a design system (DS), a product name or a site URL: they read them from here.

| File | One per | Holds |
|---|---|---|
| `kit.config.json` | project (repository root) | language, stack, apps, local-component registry, handoff, email, deploy, project commands, skill hints, rules registry |
| `ds/<name>/ds.json` | design system profile | token prefix and roles, CSS bundle, theming attributes, version label, Figma libraries |

Scripts find `kit.config.json` by walking up from the current directory. `scripts/kitconf.py` and `scripts/kitconf.js` load both files and fill defaults; use them instead of parsing the files by hand.

## `kit.config.json`

```json
{
  "language": "en",
  "stack": "html",
  "ds": "ds/acme",
  "apps": [
    {
      "id": "acme-web",
      "name": "Acme Web",
      "path": "apps/acme-web",
      "entry": "index.html",
      "type": "single",
      "build": null,
      "check": null,
      "platform": null,
      "ds": null
    }
  ],
  "local": {
    "prefix": "x-",
    "marker": "LOCAL",
    "registry": "docs/local-components.json",
    "command": { "update": null, "check": null },
    "fields": {},
    "vueStyle": "sfc",
    "vueCss": "src/styles/local.css"
  },
  "handoff": {
    "dir": "docs/handover",
    "zipName": "Design - {pbi}",
    "maxZipMB": 3,
    "figmaRequired": true,
    "itemLabel": "",
    "grepLabels": [],
    "dsLabel": "auto",
    "dsLabelCheck": "warn",
    "specFiles": { "archive": "archive.md", "crossPage": "cross-page.md", "legacy": [] },
    "csv": { "feature": null, "qc": null },
    "pre": null,
    "post": null,
    "specFields": {}
  },
  "email": {
    "subject": "[{app}] Design - {feature} - {version}",
    "attachLimitMB": 3,
    "demoLinks": true,
    "maxItems": 12,
    "template": null
  },
  "deploy": {
    "type": "none",
    "site": null
  },
  "sync": { "command": null, "check": null, "prepare": null, "post": null },
  "review": { "extraChecks": [] },
  "prototype": { "post": null },
  "define": { "messageCalls": ["toast", "showToast", "alert", "confirm", "prompt", "notify", "snackbar", "showError", "showMessage", "setCustomValidity"], "storageCalls": [], "storagePrefix": null },
  "figma": { "imageSuffix": null },
  "validate": { "touchTarget": { "default": 44, "desktop": 24 } },
  "skills": {},
  "rules": { "categories": {} },
  "paths": {
    "changelog": "CHANGELOG.md",
    "plans": "docs/plans",
    "audits": "docs/audits",
    "explorations": "docs/explorations",
    "context": "product-context",
    "validation": "docs/validation",
    "verify": "docs/verify",
    "rules": "rules"
  }
}
```

| Key | Values | Default | Used by |
|---|---|---|---|
| `language` | BCP 47 code: `en`, `vi`, … | `en` | Every skill: the language of replies and of generated documents (spec, README, AGENTS, QC checklist, email). Template strings come from `locales/<language>/*.json` (one file per skill, keys `<skill>.<key>`); a missing key falls back to `en`. |
| `stack` | `html`, `react`, `vue` | `html` | `kickoff`, `prototype`, `review`, `contribute`, `handoff`, `sync`. See [stacks.md](stacks.md). |
| `ds` | path to a DS profile folder | required | Every skill |
| `apps[]` | one entry per prototype app | `[]` | `prototype`, `review`, `contribute`, `sync`, `handoff` |
| `apps[].stack` | `html`, `react`, `vue` | the top-level `stack` | Per-app override, so one repository can keep old `html` apps and add `vue` apps. Skills use the app's stack when they work on one app. |
| `apps[].type` | `single` (one HTML file), `multi` (one file per feature, shared shell), `spa` (React/Vue app with a router), `page` (one page built in its own stack whose output is copied into other apps, see `usedBy`) | `single` | `prototype`, `handoff`, `review` |
| `apps[].usedBy`, `apps[].output` | `page` apps: files of other apps that the build output becomes (paths from the project root, required for `page`), and the build output itself: one path, or a list when one page is built into several host apps (one build per host, for example `["pages/dist/v2/tasks.js", "pages/dist/v1/tasks.js"]`) | `null` | `review` skips the `usedBy` files when it audits the apps that hold them (they are audited with the page app); the page app's DS version and DS CSS come from those host apps (the app whose path holds a `usedBy` file), and `{page}` in check commands is the host page; `kitconf.py add-page` renames every output; `kitconf.py check` (`output`: a path or a non-empty list of paths) |
| `apps[].ds` | path to a DS profile folder for this app | the top-level `ds` | Every script that reads the DS for one app (capture, validate, review, sync, handoff, share, kickoff, catalogue scan, verify, explore, wireflow, rules): a project can keep a web profile and a mobile profile, each with its own version numbers. `kitconf.py check` validates the profile (ds.json, prefix, bundle); `kitconf.py --app <id>` prints the merged configuration for that app. |
| `apps[].build`, `apps[].check` | shell commands, or `null` | `null` | Run after editing a shared shell (`multi`) or before a handoff (`spa`) |
| `apps[].platform` | free word, e.g. `desktop`, `web`, `mobile`, `tablet` | `null` | `validate`: picks the touch-target size from `validate.touchTarget`; `{platform}` in `review.extraChecks` and rule checks |
| `apps[].generated`, `apps[].sources` | glob patterns from the project root (`**` allowed): files built from the app's own sources (skipped by `review`, so a shell and its generated copy count once), and source files outside the app folder (scanned with the app) | `null` | `review` (`audit_app.py`, `audit_map_tokens.py`); `kitconf.py check` |
| `apps[].designSource` | free text: where layouts and components come from when it is not the DS catalogue alone (for example a named Figma library) | `null` | `prototype` step 0 |
| `apps[].css` | `{"load": "embed" \| "link", "linkPath": "<file relative to the app folder>"}`: overrides `ds.json > css.load` / `css.linkPath` for this app | `null` (the profile's) | `kickoff`, `prototype`, `review`, `sync`, `handoff`; `kitconf.py check` |
| `apps[].pageContract` | list of lines (or one string): what every page of the app must do for its shell, e.g. `"Call Shell.ready() after the first render, else the nav icons are not drawn"`, `"Load shared/shell.js before the page script"` | `[]` | `prototype` prints it (`kitconf.py contract --app <id>`; for a `page` app the contract of each host app follows, the host being the app whose `path` holds a `usedBy` file) and follows every line on each page it builds or edits; a project rule can point to it; `kitconf.py check` |
| `apps[].pageHook` | host apps: a project command that wires a new page app into the host (adds it to the host build, the copy step, the page file, the route), run by `kitconf.py add-page --host <id>` with `{id}`, `{path}`, `{host}`, `{like}`, `{output}` (every output, space-separated), `{usedBy}` (first file), `{root}` | `null` (add-page prints the host-side steps instead) | `prototype`; `kitconf.py check` |
| `local.prefix` | CSS class prefix of local (not-yet-in-DS) components | `x-` | `prototype`, `contribute`, `review` |
| `local.marker` | Comment marker that opens a local block: `/* LOCAL: <name> */` | `LOCAL` | same |
| `local.registry` | JSON registry of local components | `docs/local-components.json` | same |
| `local.vueStyle`, `local.vueCss` | `vue` apps: where the CSS of a local block lives. `sfc` = the `<style>` of `src/components/local/<Name>.vue`; `css-file` = a `/* <marker>: <name> */` block in the CSS file `vueCss` (relative to the app folder), imported once in `src/main.ts`; the markup stays in the page or in a `.vue` file outside `src/components/local/` with no `<style>` (for projects that forbid CSS in `.vue`; the registry reads the CSS block, so the block name is the entry). Only for `spa` apps: a `page` app puts its local blocks in the host app's CSS (`apps[].pageContract` of the host), and `kitconf.py check` warns when `vueCss` is set to another value than the default, `vueStyle` is `sfc` and every `vue` app is a `page` | `sfc`, `src/styles/local.css` | `prototype`; `kitconf.py check` |
| `define.messageCalls` | calls whose string arguments are messages in the parity draft (`extract_rules.py`); the last part of a call matches too (`toast` matches `Shell.toast`) | `["toast", "showToast", "alert", "confirm", "prompt", "notify", "snackbar", "showError", "showMessage", "setCustomValidity"]` | `define` (other strings of the scripts are listed as "text in script"); `kitconf.py check` |
| `define.storageCalls`, `define.storagePrefix` | the project's storage wrapper: calls whose first string argument is a storage key (`["Shell.store.get", "Shell.store.put"]`), and the prefix the wrapper adds to every key (`"acme."`) | `[]`, `null` | `define`: rows "storage" with the stored key name; without them, any `.get/.put/.set/.remove` call with a string key is listed as "storage through a wrapper? check the code"; `kitconf.py check` |
| `define.skipRegions` | regular expressions of regions that `extract_rules.py --skip-shell` leaves out of the parity draft, each matching a whole region (the shared shell inside a page) | `[]` (= `<!-- SHELL:x --> … <!-- /SHELL:x -->` in HTML and `/* SHELL:x */ … /* /SHELL:x */` in scripts) | `define`; `kitconf.py check` |
| `handoff.zipName` | zip and root folder name; `{pbi}` is the work-item code | `Design - {pbi}` | `handoff`, `share` |
| `handoff.figmaRequired` | the handoff stops when a screen has no Figma node | `true` | `handoff`, `wireflow` |
| `handoff.itemLabel` | text before the work-item code in AGENTS.md, the lock toast and the `x-handover` meta, e.g. `"PBI "` | `""` | `handoff` |
| `handoff.grepLabels` | extra labels listed in AGENTS.md "Find with grep" (the project's own status words) | `[]` | `handoff` |
| `handoff.dsLabel` | where the DS label of the package comes from: `auto` (`pkg.json > ds_label`, then `ds` in the frontmatter of `spec/index.md`, then `ds.json`), `pkg`, `spec`, `ds`, `prototype` (version in the `<meta>` of the package pages) | `auto` | `handoff` |
| `handoff.dsLabelCheck` | label differs from the pages' `<meta name="<version_label.meta>">` or from `spec/index.md`: `warn`, `error` (finalize stops), `off` | `warn` | `handoff` |
| `handoff.specFiles` | names of the special spec files: `archive`, `crossPage`; `legacy` lists older names still read as special files (not counted as units). `legacy` may also be `{"archive": [...], "crossPage": [...]}`: then AGENTS.md (Dev reading path, archive line) and the archive step use the older file when the package has it (or README, AGENTS or the changelog already point at it) | `archive.md`, `cross-page.md`, `[]` | `handoff`, `annotate` |
| `handoff.specFields` | older frontmatter keys of `spec/index.md`: `{kit key: old key or list}`, e.g. `{"ds": "acmeVersion"}`. Kit keys: `pbi`, `title`, `version`, `date`, `ds`, `prototype`. A DS alias that holds only a version (`2.4.1`) becomes the version label of the profile. The kit key wins when both are set | `{}` | `annotate` (`spec_md.py`), `handoff` |
| `handoff.csv.feature`, `handoff.csv.qc` | CSV headers: `null` (locale), a comma string or list in the standard column order, or an object `{role: header}` (roles: feature `code, feature, group, screen, behaviour, inputs, expected, status, dependencies`; qc `id, unit, preconditions, steps, expected, result, notes`). `init` writes them; `finalize` warns when the package header differs. `pkg.json > csv` (same shape) overrides them for one package (headers kept from its earlier versions) | `null` | `handoff`, `share` |
| `handoff.pre`, `handoff.post` | project commands run before and after `pkg.py finalize` (after the zip). `{pkg}`, `{config}`, `{zip}`, `{root}` are replaced (shell-quoted); also in the environment as `KIT_PKG`, `KIT_CONFIG`, `KIT_ZIP`. A failing command stops finalize | `null` | `handoff` |
| `handoff.smokeWidths` | viewport widths in px for `pkg.py smoke` (the unpacked package opened in Chromium) | `[400, 768, 1280]` | `handoff` |
| `email.subject` | subject template | as above | `share` |
| `email.attachLimitMB` | largest zip attached to a draft; bigger zips get a link instead | `3` (what mail connectors usually accept per call) | `share` |
| `email.demoLinks` | `false`: the email has no demo, prototype or flow link at all | `true` | `share` |
| `email.maxItems` | items kept in the feature or changelog section; the rest points to the file in the package | `12` | `share` |
| `email.template` | path (project root) of the project's email layout: `.md` / `.txt` (plain body; the HTML body is built from it) or `.html` (HTML body; the plain body is its text). `{language}` in the path is the project language. Placeholders: `{greeting}`, `{intro}`, `{figma}`, `{demo}`, `{sections}`, `{package}`, `{how_to_open}`, `{feedback}`, `{thanks}`, `{signature}`, `{feature}`, `{version}`, `{app}`, `{pbi}`, `{subject}`, `{attachment}`; unknown ones stay as written (NOTE) | `null` (the kit layout) | `share` |
| `figma.imageSuffix` | layer-name suffix of the screen image frames on the wireflow board, e.g. `" · image"` | `null` (`" · image"`; `mapjs`, `retitlejs` and the `mockup` audit also accept the locale suffix `wireflow.imageSuffix` and the English one) | `wireflow`, `mockup` |
| `deploy.type` | `none`, `vercel`, `static` | `none` | demo links in `wireflow`, `share`, `handoff` |
| `deploy.site` | base URL of the deployed prototypes | `null` | same |
| `paths.context` | product context files and the decision log (`decisions/`) | `product-context` | `context`, `define`, `explore`, `prototype`, `handoff` |
| `paths.validation` | validation plans, runs (report, screenshots, diffs) and the accepted baseline, one sub-folder per app | `docs/validation` | `validate`, `handoff` |
| `paths.verify` | implementation checks: pairs, runs (report, screenshots, side-by-side images) and accepted deviations | `docs/verify` | `verify` |
| `paths.rules` | project and app layer of the rules registry, one file per rule (`<category>/<ID>-<slug>.md`). See [rules.md](rules.md) | `rules` | every skill (`scripts/rules.py`), `kickoff` creates it |
| `rules.categories` | extra rule categories with their id prefix, `{"motion": "MOT"}` (2–6 capital letters or digits) | `{}` (the recommended categories only) | `scripts/rules.py` |
| `paths.explorations` | folder of design explorations, one sub-folder per question | `docs/explorations` | `explore`, `prototype` |
| `validate.touchTarget` | smallest touch target in px on phone widths, per `apps[].platform`; `default` for apps without a platform (or with one not listed). `ds.json > touchTarget` may add platforms | `{"default": 44, "desktop": 24}` (24 px = WCAG 2.2 target size minimum) | `validate` |
| `validate.axePath` | path to `axe.min.js` (or a folder that holds axe-core), relative to the project root or absolute, for projects that do not install axe-core (no `package.json`); `--axe` and env `KIT_AXE_PATH` win | `null` (look in `node_modules` of the project and the kit) | `validate` |
| `validate.setTheme` | JS function body run in the page to set a theme value, with `key` (a `ds.json > theming` key: `mode`, `brand`, `density`) and `value`, e.g. `"window.AcmeAppearance.set({[key]: value})"`: dark mode and theme states then go through the app's own switch | `null` (set `ds.json > theming.<key>.attr` on `<html>`) | `validate` |
| `validate.contentRoot` | CSS selector list of the page's own content, inside the shell: `validate init --url` reads routes and selector hints of visible elements inside the first selector that matches; `plan.contentRoot` (written by `init`) also limits the text, controls and aria states `validate parity` compares, and is the default `plan.axe.include` of `validate run` (first selector that matches) | `"main, #app, [role=main]"` | `validate` |
| `validate.minPixels`, `validate.threshold` | a screenshot counts as changed from this many changed pixels, or this percent of the screenshot: `run` and `report` against the baseline, `parity` between the two builds (raise `minPixels` when anti-aliasing noise of a few hundred pixels shows up between two builds); `--min-pixels`, `--threshold` and `plan.minPixels`, `plan.threshold` win | `100`, `0.5` | `validate`; `kitconf.py check` |
| `skills.<skill>.model`, `skills.<skill>.effort` | model and effort hints per skill, e.g. `{"handoff": {"model": "sonnet", "effort": "medium"}}`; `effort` is `low`, `medium`, `high`, `xhigh` or `max`. Skills read their own entry; `brief` passes it on when it hands work to a skill or a sub-agent. `python3 scripts/kitconf.py skills` lists them | `{}` (no hint: the session's model and effort) | every skill |

## Project commands (extension points)

A project that already has its own scripts for a step keeps them; the kit runs them and reports their output and exit code instead of doing the step itself. Every key is off by default, so the kit's own behaviour stays.

| Key | Replaces | Notes |
|---|---|---|
| `sync.command` | `sync_ds.py apply` | Runs in the project root. `{app}` becomes the `--app` value. `apply --dry-run` prints the command and runs `sync.check` instead. May also be set in `ds.json > sync` (the kit config wins). |
| `sync.check` | `sync_ds.py status` | Exit code other than 0 = apps are behind or out of step. `status` checks the DS as built in the profile, not its sources (it says so). |
| `sync.prepare` | runs before `sync_ds.py apply` (project or built-in sync) | For example a project that must rebuild its DS library from source before syncing apps. A failing command stops the sync. `{app}`, `{root}`. |
| `sync.post` | runs after `apply` and its change report | For example the project's own docs or publish check. Output and exit code printed, never parsed; exit other than 0 makes `apply` exit 1. After every `apply` the script also lists the files that changed per app and the LOCAL blocks added, removed or changed. |
| `prototype.post` | optional step after a `prototype` build | `python3 <kit>/scripts/kitconf.py hook prototype.post --app <id>` runs it (`{app}`, `{path}`, `{root}`); for example the project's own preview or publish script. The kit never publishes by itself. |
| `local.command.update`, `local.command.check` | `registry.py update`, `registry.py check` | The project owns the registry (for example it also builds pages from it). `--builtin` runs the kit's own command. |
| `local.fields` | field names of the registry | `{kit field: project field}`, e.g. `{"vs_ds": "compare", "removed_on": "dropped"}`. The kit reads and writes the project's names. Fields the kit does not know (demo, notes…) are always kept as they are. |
| `review.extraChecks` | adds rows to the `review` report | `[{"name": "Flag ledger", "command": "python3 scripts/flags.py", "parse": "^flags:", "level": "deviation"}]`. Runs after `audit_app.py` in the project root; `{app}` (app id), `{path}` (app folder), `{platform}` (`apps[].platform`), `{stack}` or `{page}` (the page to open, from the project root: the app folder, or for a `page` app each host page, one run per page) = one run and one row per audited app, else one row in "Project checks". Result: exit code + the lines matching `parse` (the last line when none matches, or without `parse`). Pass = exit 0 and no matched line counts something (a number other than 0); else `level` (`deviation` by default, or `note`). A `page` app skips a command whose URL holds `{app}` (no such folder on the site; use `{page}`). `--no-extra` skips them. A rule with a `check` in the rules registry is the other way to add a row. |
| `handoff.pre`, `handoff.post` | runs around `pkg.py finalize` | See the table above. |

## `ds/<name>/ds.json`

```json
{
  "name": "acme",
  "label": "Acme DS",
  "version": "0.1.0",
  "platforms": ["web", "mobile", "tablet"],
  "tokens": {
    "prefix": "--acme-",
    "roles": {
      "text": "--acme-text-",
      "bg": "--acme-bg-",
      "stroke": "--acme-stroke-",
      "icon": "--acme-icon-",
      "radius": "--acme-radius-",
      "fontSize": "--acme-font-size-",
      "lineHeight": "--acme-line-height-",
      "spacing": "--acme-space-",
      "shadow": "--acme-shadow-"
    },
    "scale": {
      "spacing": "--acme-num-spacing-"
    },
    "file": "tokens.json",
    "ignorePrefixes": []
  },
  "css": {
    "bundle": "dist/acme.css",
    "sources": ["tokens.css", "tokens-dark.css", "base.css", "components.css", "responsive.css"],
    "marker": { "begin": "@ds:begin", "end": "@ds:end" },
    "load": "embed",
    "linkPath": null
  },
  "version_label": {
    "text": "{label} {version}",
    "meta": "ds-version"
  },
  "theming": {
    "brand": { "attr": "data-brand", "values": ["default"] },
    "mode": { "attr": "data-mode", "values": ["light", "dark"], "default": "light" },
    "density": { "attr": "data-density", "values": ["auto", "comfortable", "standard", "compact"], "default": "auto" }
  },
  "breakpoints": { "compact": 0, "medium": 600, "expanded": 840 },
  "icons": { "set": "tabler", "file": "icons.json" },
  "catalog": "catalog.md",
  "rules": "rules.md",
  "changelog": null,
  "review": { "genericClasses": [] },
  "library": { "page": "library.html" },
  "figma": {
    "libraries": [
      { "name": "Acme Components", "platform": "web", "fileKey": null }
    ],
    "collections": { "primitives": "Primitives", "semantic": "Semantic", "spacing": "Spacing" },
    "modes": { "light": "Light", "dark": "Dark" }
  },
  "preset": { "name": "shadcn", "version": null }
}
```

| Key | Meaning |
|---|---|
| `tokens.prefix` | Prefix of every custom property of the DS. Scripts treat `var(<prefix>…)` as "uses a token". |
| `tokens.roles` | Prefix per role. `annotate` groups computed styles by role; `review` maps hard-coded values to tokens of the matching role (`color` → `text`, `background` → `bg`, borders → `stroke`, `fill`/`stroke` → `icon`). |
| `tokens.scale.spacing` | Primitive spacing scale. Used to match hard-coded `margin`, `padding`, `gap`. |
| `css.bundle` | One CSS file with the whole DS. Prototypes in the `html` stack embed it; the spec viewer and the audit read it. Path is relative to the profile folder, or a URL. |
| `tokens.ignorePrefixes` | Token prefixes never used to name a captured style (`annotate`, `capture.js`), e.g. primitive scales such as `--acme-num-`. Values `0`, `none`, `normal`, `auto` and `transparent` never get a token. Default `[]`. |
| `css.marker` | Comments that wrap the embedded DS CSS inside an app, so `sync` can replace it and `review` can tell DS CSS from app CSS. |
| `css.load`, `css.linkPath` | How `html` pages load the DS CSS: `embed` (default: the bundle between the markers of each page) or `link` (one file per app, `linkPath` relative to the app folder, default the bundle's file name; pages `<link>` it). `apps[].css` overrides both per app. `kickoff` writes it, `sync` (built-in) rewrites the whole file, `review` treats it as DS CSS, `handoff` (`pkg.py proto`) copies it with the pages. See [stacks.md](stacks.md). |
| `changelog` | Where the DS changelog is: a path, or `{"path", "format": "md" \| "json", "versionKey", "match"}`; the path is relative to the profile folder, else the project root. `md` = `## <version>` sections; `json` = a list of entries (or `{"entries": [...]}`) with a version key (`versionKey`, default `version` or `v`), `match` `{key: value}` keeps only matching entries, `fields` lists the keys to print (default: every text field but the version and match keys). Default: `CHANGELOG.md` (md) in the profile folder. Read by `sync_ds.py changes`; missing → an ERROR that names this key. |
| `review.genericClasses` | Class names of the DS that are utilities rather than components (icons, scroll fades): never counted as overrides by `review` and never measured by its browser step. Default `[]`. |
| `css.styleBlocks` | Optional id prefix (for example `lib`): every `<style id="<prefix>…">` block in an app is DS CSS. For DS that embed their library blocks by id instead of marker comments. A file in the app named like the bundle (for example `acme.css`) and a `<link href>` to it also count as DS CSS. |
| `version_label` | Footer text and `<meta>` name that state which DS version a prototype uses. `handoff` compares the `<meta>` of the package pages with the package's DS label. |
| `toast` | Optional: the DS toast pattern for the handoff lock layer: `container`, `class`, `close_class`, `icon` (HTML of the icon), `close_html` (inner HTML of the close button). `pkg.json > lock.toast` overrides each key. |
| `touchTarget` | Optional: `{platform: px}` touch-target sizes of the DS, used by `validate` when `kit.config.json > validate.touchTarget` has no entry for the app's platform. |
| `tailwind` | Optional, `react` and `vue` stacks: `false` = the DS is used without Tailwind; `kickoff` uses the plain templates (`templates/<stack>-plain`: no Tailwind, no shadcn) and `review` drops the Tailwind row. Default: Tailwind (absent or `true`). |
| `components.vue` | Optional: the DS's own Vue component layer, `{"package": "<folder in the project, or npm name@version>", "propsMap": "<CSV, first column = component name>", "version": "<npm version when package has none>"}`. `map` is read as `propsMap`; the path is relative to the project root, else to the profile folder. Without `package` the layer is off. Vue apps then use these components instead of shadcn-vue: `kickoff` uses the plain Vue template with the alias `@ds-vue` (folder) or the npm dependency, `prototype` builds only with them (props per the props map), `review` reports local `.vue` files named like a DS component and shadcn-vue imports. |
| `patterns` | Optional list of page patterns and templates, `[{"name": "Master detail", "classes": ["acme-split", "acme-side"], "use": "list left, detail right; one pane on compact screens"}]`, for profiles built by a script. Same as a `## Patterns` section of `catalog.md` (that one wins on the same name). Default `[]`. Read by `catalog.py patterns` and `find`, `define` step 5 and `prototype`. |
| `sync` | Optional: `{"command", "check"}` project commands for `sync` (see "Project commands"); `kit.config.json > sync` wins. |
| `theming` | Attributes the DS reads on `<html>`. Skills set them only through these keys; they never invent new attributes. |
| `catalog` | Component catalogue for agents: class, variants, states, tokens, and the `components.map` table (HTML class ↔ React ↔ Vue component). |
| `catalog_json` | Machine-readable catalogue (default `catalog.json`), built from `catalog` by `document/scripts/catalog.py build`. Adds fields people maintain: `figma` (component, key, node), `status` (`active`, `experimental`, `deprecated` with `replacedBy` and `reason`), `usage` (`use`, `avoid`) and `a11y`. Rebuilding keeps them. Read by `prototype`, `review`, `mockup`. |
| `rules` | Hard rules of the DS (intentional deviations, accessibility fixes, "do not override") as one document. A profile can split them into rule files in `rules/` (DS layer of the [rules registry](rules.md); `rules.py import-md --layer ds` drafts them); until then `rules.py list` reminds skills to read this file. Also an object `{"file": "rules.md", "from": "../acme"}`: `from` (relative to this profile folder) inherits the DS-layer rules of another profile, for example a mobile profile that shares the web profile's rules. |
| `figma` | Libraries, variable collections and modes for `mockup` and `adopt`. |
| `preset` | The preset the profile was adopted from, if any (`adopt`: `shadcn` or `atelier`). |
| `contrast` | Optional. `skip`: contrast pairs the preset replaces with another check, each with the reason (`adopt`). |

## The DS profile folder

```
ds/<name>/
  ds.json         this file
  tokens.json     tokens in W3C Design Tokens (DTCG) format
  tokens.css      primitives and semantic tokens (light)
  tokens-dark.css dark mode
  base.css        reset, font, focus ring
  components.css  components; semantic tokens only
  responsive.css  breakpoints, tab bar on compact screens
  dist/<name>.css bundle of the files above
  catalog.md      component catalogue + components.map
  rules.md        hard rules (one document)
  rules/          DS layer of the rules registry: <category>/<ID>-<slug>.md (optional)
  library.html    library page (optional)
  flutter/        Dart theme generated from tokens (optional)
  NOTICE          origin and licence of the preset (when adopted)
  CHANGELOG.md
```

A profile may live inside the project repository (recommended for a private DS) or in its own repository.

## What the kit writes, and where

| Folder (default) | Holds | Written by | Key |
|---|---|---|---|
| `kit.config.json` | Language, stack, apps, paths | `kickoff` | |
| `ds/<name>/` | DS profile: tokens, CSS bundle, `catalog.md`, `catalog.json`, `rules.md`, `rules/` (DS layer of the rules registry) | `adopt`, `document` | top-level `ds`, `apps[].ds` |
| `rules/` | Project and app rules, one file per rule (`<category>/<ID>-<slug>.md`) | `kickoff`, `rules.py add`, `context` | `paths.rules` |
| `product-context/` | Overview, personas, UX principles, business rules, constraints, `decisions/` | `context`, `explore`, `define`, `prototype`, `verify` | `paths.context` |
| `docs/plans/` | Requirement analysis, waves, traceability | `define` | `paths.plans` |
| `docs/explorations/<slug>/` | Directions, comparison page, decision | `explore` | `paths.explorations` |
| `apps/<app>/` | Prototypes | `kickoff`, `prototype` | `apps[].path` |
| `docs/validation/<app>/` | Validation plan, runs, baseline screenshots | `validate` | `paths.validation` |
| `docs/handover/` | Handoff packages | `handoff` | `handoff.dir` |
| `docs/verify/<name>/` | Build-vs-design runs and accepted deviations | `verify` | `paths.verify` |

## Languages

The kit is written in English. Replies and generated documents follow `language`; English and Vietnamese templates ship in `locales/`. To add a language, copy `locales/en/` to `locales/<code>/` and translate the values. A missing key falls back to English.
