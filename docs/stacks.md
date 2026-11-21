# Stacks

`kit.config.json > stack` tells every skill how prototypes are built. It is a setting, not a skill: `kickoff` asks for it once; change it later by editing the file or running `kickoff` again. An app can override it with `apps[].stack` (for example, keep existing `html` apps and build new ones in `vue`); skills always use the stack of the app they work on.

| | `html` (default) | `react` | `vue` |
|---|---|---|---|
| App skeleton (`kickoff`) | `apps/<app>/index.html` with the DS bundle embedded between `/* @ds:begin */` and `/* @ds:end */` | Vite + React + TypeScript + Tailwind, components from shadcn/ui; without Tailwind see below | Vite + Vue 3 + TypeScript + Tailwind, components from shadcn-vue; DS Vue layer or no Tailwind: see below |
| Tokens | Custom properties from `ds.json > css.bundle` | Same custom properties, imported once in `src/index.css`; Tailwind theme maps to them | Same as React |
| Components (`prototype`) | DS classes from `catalog.md` | Components named in `catalog.md > components.map` (React column) | Components named in `components.map` (Vue column) |
| Routing | Hash router per page (`#/…`); `multi` apps have one file per feature | Framework router with hash history (the static build works from a folder); pages in `src/pages/<Name>.tsx` | Same; pages in `src/pages/<Name>.vue` |
| Local components | Class prefix `x-` in a `/* LOCAL: <name> */` block in the app's CSS | Files under `src/components/local/<Name>.tsx` with a `/* LOCAL: <name> */` header comment; classes keep the `x-` prefix | Files under `src/components/local/<Name>.vue` with the same header comment |
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

## Rules that hold for every stack

- Prototypes use only DS tokens and DS components. No raw colour or spacing values when a token exists.
- The prototype is a design artefact, not production code: data is mocked and marked as mock; there is no real API, auth or persistence beyond `localStorage`.
- The handoff package never contains loose `.js` files (mail filters block them). The `html` stack inlines scripts at package time; `react` and `vue` build to single-file HTML.
- Theme, mode and density are set only through the attributes in `ds.json > theming`.

## Choosing

- `html`: designers work alone, need light handoff packages and artifacts that open anywhere. Developers rebuild in their own stack, guided by `components.map`.
- `react` / `vue`: the team already has a coded DS in that framework, or developers want to reuse prototype code. Costs more agent time (install, build).
