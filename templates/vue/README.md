# {{APP_NAME}} (vue)

Vite + Vue 3 + TypeScript + Tailwind CSS v4 + shadcn-vue-compatible components, themed by the DS profile `{{DS_LABEL}}`.

| Command | Result |
|---|---|
| `npm install` | Install the pinned dependencies |
| `npm run dev` | Local server with hot reload |
| `npm run build` | Type check, then `dist/index.html`: one self-contained file (CSS and JS inlined, hash routing), opens from any folder or by double-click |
| `npm run build:handoff` | `build`, then `scripts/assert-single-file.mjs` checks that `dist/` holds HTML only and no separate `.js` (run before a handoff) |

## Where things are

| Path | What |
|---|---|
| `src/ds/{{DS_BUNDLE_FILE}}` | Copy of the DS bundle (`ds.json > css.bundle`), between the DS markers. Never edit; `sync` replaces it. |
| `src/index.css` | Imports Tailwind and the DS bundle once; maps Tailwind colours and radius to the DS alias variables. |
| `src/router.ts` | Hash router. One route per page. |
| `src/pages/<Name>.vue` | Pages. |
| `src/components/ui/` | DS or shadcn-vue components (Button and Card are included as source). |
| `src/components/local/` | Local components, see the README there. |
| `src/lib/theming.ts` | Theming attributes on `<html>` from `ds.json > theming`. |
| `src/lib/mock.ts` | Mock data. |
| `index.html` | `<meta name="{{VERSION_META}}">` with the DS version and the footer label. |

## Adding shadcn-vue components

`components.json` is ready for `npx shadcn-vue@latest add <component>`. The CLI may offer to write colour variables into `src/index.css`: decline, or remove them afterwards. The DS bundle already defines every alias variable for light and dark. Use the component only if `catalog.md > components.map` lists it, or after the component gate.
