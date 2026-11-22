# Scope layers: lock (b) and hide (c)

Both are layers added to the package copy of the prototype. App code, DS components, tokens and data stay unchanged. `pkg.py layer` renders them from `pkg.json` and injects them into each page (idempotent: running again replaces the old layer).

```
python3 skills/handoff/scripts/pkg.py layer --config pkg.json --kind lock --into "prototype/index.html" "prototype/tasks/index.html"
python3 skills/handoff/scripts/pkg.py layer --config pkg.json --kind hide --out layer.html   # inspect only
```

What gets injected:

| Kind | `<head>` | before `</body>` |
|---|---|---|
| lock | `<script id="x-handover-seed">` first (only with `seed`), then `<meta name="x-handover" content="lock <item label><code> · <title> v<version>">` (text from the locale key `handoff.layer.lock`) | `<script id="x-handover-lock">` from `assets/scope-lock.js` |
| hide | the same seed script, same meta from `handoff.layer.hide`, plus `<style id="x-handover-hide">` with `display:none !important` | `<script id="x-handover-hide-js">` from `assets/scope-hide.js` |

Order in `<head>`: the seed script is the first element after `<head>` (after `<meta charset>` when that opens the head), before every script of the page, so app code that reads a key while it loads already sees the value. The layer script itself runs last, at the end of `<body>`.

The layer script is inlined into the page, so the package still has no loose `.js` file.

## `pkg.json > lock`

```json
"lock": {
  "pages": ["index.html", "tasks/index.html"],
  "page_keys": {"home": "index.html", "tasks": "tasks/index.html", "notes": "notes/index.html"},
  "allow": ["[data-area=\"tasks\"]", "[role=dialog]", ".acme-menu", ".acme-toast-stack", "#modeBtn"],
  "allow_when": [{"sel": "#taskMore", "hash": "^#/tasks/"}],
  "block": ["[data-action=\"export\"]"],
  "nav_functions": ["appNav.go"],
  "shortcuts": ["F1"],
  "open_allow": "",
  "open_block": "#branch",
  "seed": {"localStorage": {"acme-web:whats-new": "seen"}},
  "toast": {"function": "", "args": [], "container": ".acme-toast-stack", "class": "acme-toast acme-toast--warning",
            "close_class": "acme-toast__close", "icon": "", "close_html": "", "ms": 5000}
}
```

| Key | Meaning |
|---|---|
| `pages` | Page files in the package, as paths relative to the package prototype folder. Links, `window.open` and wrapped navigation to any other page are blocked. Targets are compared after the URL is resolved against the current page, on the whole path (`notes/index.html` never matches `index.html`). Empty = no page check. |
| `page_keys` | Page keys the app's navigation functions take, mapped to files: `{"home": "index.html"}`. A key whose file is not in `pages` is blocked; an unknown key is blocked. (Keys listed in `pages`, as before, still pass.) |
| `allow` | Selectors of the feature, plus the menus, dialogs, popovers and toasts it uses, and shared controls you keep (theme switch). Required. |
| `allow_when` | Per-route rules: `[{"sel": "<selector>", "hash": "<regex>", "path": "<regex>"}]`. An element inside `sel` is allowed only while `location.hash` (and `location.pathname`, when given) match; this overrides `allow`. For a control that is in scope on one route and out of scope on another. |
| `block` | Selectors inside allowed areas that belong to another feature. Checked first. |
| `nav_functions` | Global navigation functions of the app (dotted path). Called with a page key (see `page_keys`) or a URL that is not in `pages`: toast, no navigation. |
| `shortcuts` | Key combos of out-of-scope features (`Ctrl+`, `Meta+`, `Alt+`, `Shift+` then `KeyboardEvent.key`). Toast, no action. |
| `open_allow` | Regex of more URLs `window.open` may open, tested on the URL as written and as resolved. A page in `pages` always opens (relative or absolute). With `pages` empty, only `open_allow` decides. |
| `open_block` | Regex tested first on the URL `window.open` (and a link) gets, as written and as resolved: a match is blocked **even for a page of the package**, for example the same page opened in a new tab with the hash of another feature (`#branch`). Empty = off. |
| `seed` | `{"localStorage": {key: value}, "sessionStorage": {…}}` set on load when the key is absent: state the package needs (for example a notice of another work item already dismissed). Runs in its own script at the top of `<head>`, before the app's scripts. |
| `toast.function` | Name (dotted path) of the app's own toast function, called with the message, then `toast.args` (for example the level `"warning"`). Preferred: the app already uses the DS toast. |
| `toast.container`, `class`, `close_class`, `icon`, `close_html` | Else the layer builds the toast from the DS toast pattern (`catalog.md`, or `ds.json > toast` as defaults): `icon` is the HTML of the DS icon before the text; the close button has `aria-label` and `close_html` (default: an outline × icon, never a bare character). One of `function` or `class` is required. |

The toast text comes from the locale key `handoff.lock.toast` ("outside the scope of the handoff <code> · <title> v<version>").

How it blocks: listeners on `window` in the capture phase, so they run before app handlers on `document`. Click and Enter/Space on interactive elements outside `allow` (or inside `block`) call `preventDefault`, `stopPropagation`, `stopImmediatePropagation`, then show one toast (no stacking). Fields outside scope: pointer-down and focus show the toast and the field loses focus; drop and paste are stopped; dragover and dragenter are stopped silently, so no out-of-scope drop zone lights up. Inside an iframe the toast is shown by the parent page when it has the layer.

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
| `seed` | As for lock: storage keys set on load when absent, from the seed script at the top of `<head>`. |

CSS does the hiding, so late-rendered elements and the compact-screen tab bar are covered without a MutationObserver. Use JS only when there is no stable selector; visible text is the last resort.

## Multi-page apps

- Inject the layer into **every page** of the package. Pages built from a shared shell (`apps[].type` = `multi`): add the injection to the shell build, rebuild, run `apps[].check`.
- Scan every page for static `<a href>`, `window.open` and shortcuts that reach dropped pages; they go into `allow`/`block` (lock) or `selectors` (hide).
- Test from each page: every way out of scope shows the toast (lock) or is gone (hide); every kept link opens; no link points to a file outside the package.
