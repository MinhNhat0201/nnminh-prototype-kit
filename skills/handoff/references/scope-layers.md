# Scope layers: lock (b) and hide (c)

Both are layers added to the package copy of the prototype. App code, DS components, tokens and data stay unchanged. `pkg.py layer` renders them from `pkg.json` and injects them into each page (idempotent: running again replaces the old layer).

```
python3 skills/handoff/scripts/pkg.py layer --config pkg.json --kind lock --into "prototype/index.html" "prototype/tasks/index.html"
python3 skills/handoff/scripts/pkg.py layer --config pkg.json --kind hide --out layer.html   # inspect only
```

What gets injected:

| Kind | `<head>` | before `</body>` |
|---|---|---|
| lock | `<meta name="x-handover" content="lock <code> · <title> v<version>">` | `<script id="x-handover-lock">` from `assets/scope-lock.js` |
| hide | same meta with `hide`, plus `<style id="x-handover-hide">` with `display:none !important` | `<script id="x-handover-hide-js">` from `assets/scope-hide.js` |

The layer script is inlined into the page, so the package still has no loose `.js` file.

## `pkg.json > lock`

```json
"lock": {
  "pages": ["index.html", "tasks/index.html"],
  "allow": ["[data-area=\"tasks\"]", "[role=dialog]", ".acme-menu", ".acme-toast-stack", "#modeBtn"],
  "block": ["[data-action=\"export\"]"],
  "nav_functions": ["appNav.go"],
  "shortcuts": ["F1"],
  "open_allow": "/tasks/index\\.html",
  "toast": {"function": "", "container": ".acme-toast-stack", "class": "acme-toast acme-toast--warning",
            "close_class": "acme-toast__close", "ms": 5000}
}
```

| Key | Meaning |
|---|---|
| `pages` | Page files in the package. Links, `window.open` and wrapped navigation to any other page are blocked. Empty = no page check. |
| `allow` | Selectors of the feature, plus the menus, dialogs, popovers and toasts it uses, and shared controls you keep (theme switch). Required. |
| `block` | Selectors inside allowed areas that belong to another feature. Checked first. |
| `nav_functions` | Global navigation functions of the app (dotted path). Called with a page key or URL that is not in `pages`: toast, no navigation. |
| `shortcuts` | Key combos of out-of-scope features (`Ctrl+`, `Meta+`, `Alt+`, `Shift+` then `KeyboardEvent.key`). Toast, no action. |
| `open_allow` | Regex of URLs `window.open` may open. Empty = only pages in `pages`. |
| `toast.function` | Name of the app's own global toast function, called with the message. Preferred: the app already uses the DS toast. |
| `toast.container`, `class`, `close_class` | Else the layer builds the toast from the DS toast classes in `catalog.md`. One of `function` or `class` is required. |

The toast text comes from the locale key `handoff.lock.toast` ("outside the scope of the handoff <code> · <title> v<version>").

How it blocks: listeners on `window` in the capture phase, so they run before app handlers on `document`. Click and Enter/Space on interactive elements outside `allow` (or inside `block`) call `preventDefault`, `stopPropagation`, `stopImmediatePropagation`, then show one toast (no stacking). Fields outside scope: pointer-down and focus show the toast and the field loses focus; drop and paste are stopped. Inside an iframe the toast is shown by the parent page when it has the layer.

Never: `disabled`, `aria-disabled`, opacity, cursor or colour changes. Out-of-scope UI must look normal.

Never edit the rendered copy by hand: change `pkg.json` and render again.

## `pkg.json > hide`

```json
"hide": {
  "selectors": ["[data-nav=\"admin\"]", "[data-action=\"import\"]", ".acme-tabs [data-tab=\"history\"]"],
  "shortcuts": ["Ctrl+k"],
  "dropped_hashes": ["^#/admin"],
  "entry": "index.html#/tasks",
  "defaults": [{"hidden": "[data-tab=\"history\"]", "fallback": "[data-tab=\"list\"]"}]
}
```

| Key | Meaning |
|---|---|
| `selectors` | Stable selectors from the confirmed hide list (`data-*`, `id`, `aria-label`). Include empty containers left behind (group titles, dividers). Required. |
| `shortcuts` | Key combos of hidden features (`Ctrl+`, `Meta+`, `Alt+`, `Shift+` then `KeyboardEvent.key`). Stopped silently. |
| `dropped_hashes` | Regexes of hashes that belong to dropped pages or hidden modules. Opening one redirects to `entry`. |
| `entry` | Entry of the package (page and route). |
| `defaults` | A default tab or item that is hidden: click the fallback on load. |

CSS does the hiding, so late-rendered elements and the compact-screen tab bar are covered without a MutationObserver. Use JS only when there is no stable selector; visible text is the last resort.

## Multi-page apps

- Inject the layer into **every page** of the package. Pages built from a shared shell (`apps[].type` = `multi`): add the injection to the shell build, rebuild, run `apps[].check`.
- Scan every page for static `<a href>`, `window.open` and shortcuts that reach dropped pages; they go into `allow`/`block` (lock) or `selectors` (hide).
- Test from each page: every way out of scope shows the toast (lock) or is gone (hide); every kept link opens; no link points to a file outside the package.
