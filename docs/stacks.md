# Stacks

`kit.config.json > stack` tells every skill how prototypes are built. It is a setting, not a skill: `kickoff` asks for it once; change it later by editing the file or running `kickoff` again. An app can override it with `apps[].stack` (for example, keep existing `html` apps and build new ones in `vue`); skills always use the stack of the app they work on.

| | `html` (default) | `react` | `vue` |
|---|---|---|---|
| App skeleton (`kickoff`) | `apps/<app>/index.html` with the DS bundle embedded between `/* @ds:begin */` and `/* @ds:end */`, or linked from one file (`css.load: "link"`, below) | Vite + React + TypeScript + Tailwind, components from shadcn/ui; without Tailwind see below | Vite + Vue 3 + TypeScript + Tailwind, components from shadcn-vue; DS Vue layer or no Tailwind: see below |
| Tokens | Custom properties from `ds.json > css.bundle` | Same custom properties, imported once in `src/index.css`; Tailwind theme maps to them | Same as React |
| Components (`prototype`) | DS classes from `catalog.md` | Components named in `catalog.md > components.map` (React column) | Components named in `components.map` (Vue column) |
| Routing | Hash router per page (`#/…`); `multi` apps have one file per feature | Framework router with hash history (the static build works from a folder); pages in `src/pages/<Name>.tsx` | Same; pages in `src/pages/<Name>.vue` |
| Local components | Class prefix `x-` in a `/* LOCAL: <name> */` block in the app's CSS | Files under `src/components/local/<Name>.tsx` with a `/* LOCAL: <name> */` header comment; classes keep the `x-` prefix | `local.vueStyle: "sfc"` (default): files under `src/components/local/<Name>.vue` with the same header comment. `"css-file"`: a `/* LOCAL: <name> */` block in `local.vueCss` (default `src/styles/local.css`), no `<style>` in `.vue` files |
| Hard-coded values (`review`) | Hex, `rgb()`, px for colour, spacing, radius, font size in CSS and `style=""` | Same in CSS, plus Tailwind arbitrary values (`bg-[#fff]`, `p-[13px]`, `rounded-[6px]`) and inline `style={{…}}` | Same in CSS, plus Tailwind arbitrary values and `:style` bindings |
| Version label | Footer text + `<meta name="ds-version">` | Same, in `index.html` and the app footer | Same |
| Handoff build (`handoff`) | Copy the files | `vite build` with a single-file plugin: one self-contained HTML per entry, no separate `.js` file | Same as React |
| Screen capture, specs, wireflow, Figma | Rendered DOM, so the same for every stack | same | same |

## Without Tailwind, and DS Vue component layers

Two keys of `ds.json` change the `react` and `vue` stacks. Both are off by default.

| `ds.json` | `kickoff` template | `prototype` | `review` |
|---|---|---|---|
| `"tailwind": false` | `templates/<stack>-plain`: Vite + framework + TypeScript, the DS bundle imported once, neutral `app-*` skeleton CSS with DS alias variables; no Tailwind, no shadcn | DS classes and tokens in the app CSS; no utility classes | no Tailwind row; Tailwind is never asked for |
| `"components": {"vue": {"package": "…", "propsMap": "…"}}` (vue only) | `templates/vue-plain` with the alias `@ds-vue` to the package folder (or the npm package `name@version` in `package.json`); README names the props map | only the DS Vue components, props named as in the props map; never rebuilt in the app, never shadcn-vue; a missing one goes through the component gate | row "DS Vue components": local `.vue` files named like a DS component, shadcn-vue imports |

A DS Vue layer is source the developers copy, so the prototype uses it as is; when it lacks CSS for a case, report it for the DS instead of styling it in the app.

A layer kept as a folder in the project usually has its own `package.json`, and its `tsconfig.json` extends packages installed there (for example `@vue/tsconfig`). Run `npm ci` in that folder once before the first app build; without it `vite build` or `vue-tsc` stops with a tsconfig error (`TSCONFIG_ERROR`, "cannot find base config"). `kickoff` prints this when it scaffolds a Vue app against such a folder.

## A Vue page inside a multi-page html app

An `html` app of type `multi` can get one page built in Vue (for example to try the DS Vue layer on one feature) without moving the whole app. The page is its own app entry. When the project already has one page app, start the next one with `python3 <kit>/scripts/kitconf.py add-page --like <page app> --id <new id> --host <host app> [--name "…"] [--dry-run]`: it copies the folder skeleton (package files, Vite and TypeScript config, `src/main.ts`, `env.d.ts`, `.gitignore`; not the components), renames it, adds this entry (`output`, `usedBy` and `pageContract` built like the other page's), and prints the host-side steps (host build, copy, host page, route). It runs the host's `apps[].pageHook` when the project has one; else those steps stay manual. Entry:

```json
{"id": "acme-tasks", "name": "Tasks page", "path": "pages/tasks", "stack": "vue", "type": "page",
 "build": "npm --prefix pages/tasks run build", "check": "npm --prefix pages/tasks run typecheck",
 "output": "pages/tasks/dist/tasks.js", "usedBy": ["apps/acme-web/tasks/tasks.js"]}
```

| Part | How |
|---|---|
| Build | Vite library mode, one file: `build.lib = {entry: "src/main.ts", formats: ["iife"], name: "AcmeTasks", fileName: () => "tasks.js"}`, Vue bundled in, `define` sets `process.env.NODE_ENV` to `"production"`. No CSS in the output. |
| Copy | The host app's `build` runs the page build first, then copies `output` to every `usedBy` file (`"build": "npm --prefix pages/tasks run build && python3 apps/acme-web/_shell/build.py build"`). `review` audits the copies with the page app, not with the host. |
| Host page | Keeps the shell (header, nav, DS CSS, shared scripts) and an empty mount element (`<section id="page-root">`). It sets the page config as one global (`window.__TASKS__ = {…}`), loads the shell scripts, then `<script src="tasks.js">`. |
| Hand-over | `main.ts` reads the config, mounts into the mount element only (`createApp(App).mount("#page-root")`), and calls the shell through one adapter file (`src/lib/shell.ts`: toast, router, storage, icons). It never writes the shell's markup. |
| Contract | Every line of the host app's `apps[].pageContract` applies to the page (for example "call `Shell.ready()` after the first render"); put the call in `main.ts`, after mount. |
| CSS | DS CSS from the host page; local blocks go into the host app CSS (`/* LOCAL: <name> */` blocks), never into a `<style>` of a `.vue` file. |
| Routes | Hash routes of the page stay the page's own (`#/`, `#/t/<id>`); links to other pages go through the host app's route table. |
| Tests | `validate` on the host page (its entry), not on `dist/`; the page app's `check` must pass. |

## How html pages load the DS CSS

`ds.json > css.load` (per app: `apps[].css.load`), off by default:

| `css.load` | Pages | `sync` (built-in) | `review` | `handoff` |
|---|---|---|---|---|
| `embed` (default) | the bundle between the `css.marker` comments in each page | replaces the marked block | the marked region is DS CSS | pages carry their CSS |
| `link` | one `<link rel="stylesheet">` to `css.linkPath` (relative to the app folder, default the bundle's file name); pages in sub-folders use `../` | rewrites the whole linked file | the linked file is DS CSS | `pkg.py proto` copies the linked file with the pages |

A project whose own build writes the linked file keeps it: set `sync.command` and the kit runs that instead.

## Rules that hold for every stack

- Prototypes use only DS tokens and DS components. No raw colour or spacing values when a token exists.
- The prototype is a design artefact, not production code: data is mocked and marked as mock; there is no real API, auth or persistence beyond `localStorage`.
- The handoff package never contains loose `.js` files (mail filters block them). The `html` stack inlines scripts at package time; `react` and `vue` build to single-file HTML.
- Theme, mode and density are set only through the attributes in `ds.json > theming`.

## Choosing

- `html`: designers work alone, need light handoff packages and artifacts that open anywhere. Developers rebuild in their own stack, guided by `components.map`.
- `react` / `vue`: the team already has a coded DS in that framework, or developers want to reuse prototype code. Costs more agent time (install, build).
