# {{APP_NAME}} (react, no Tailwind)

Vite + React + TypeScript, themed by the DS profile `{{DS_LABEL}}`. No Tailwind and no shadcn/ui: styles come from the DS bundle; screens use {{COMPONENT_SOURCE}}.

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
| `src/index.css` | Imports the DS bundle once; skeleton classes `app-*` that use DS alias variables only. |
| `src/App.tsx` | Hash router. One route per page. |
| `src/pages/<Name>.tsx` | Pages. |
| `src/components/local/` | Local components, see the README there. |
| `src/lib/theming.ts` | Theming attributes on `<html>` from `ds.json > theming`. |
| `src/lib/mock.ts` | Mock data. |
| `index.html` | `<meta name="{{VERSION_META}}">` with the DS version and the footer label. |
{{DS_VUE_README}}
