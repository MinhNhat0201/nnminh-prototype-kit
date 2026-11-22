# Capture manifest (`capture.js`)

A CommonJS module (`manifest.js`) or a JSON file.

```js
module.exports = {
  viewport: { width: 1280, height: 900 },
  scale: 2,                         // device scale factor; 3 for phone frames
  frames: { F: '#detail iframe' },  // optional: named iframes
  att: 'att',                       // optional: folder of sample files for "files" steps, relative to the manifest
  screens: [
    { id: 'S01', name: 'Task list', flow: 'f1',
      steps: [{ goto: 'apps/acme-web/index.html#/' }, { reset: 1 }, { wait: 500 }],
      pins: [{ ref: 'FR-01.1', sel: '#new' }, { ref: 'FR-01.2', sel: 'F|.detail-title' }],
      next: [{ to: 'S02', action: 'Click "New task"', trigger: '#new', condition: '' }] },
    { id: 'S02', name: 'New task form', flow: 'f1', cont: 1,
      steps: [{ click: '#new' }, { fill: ['#name', 'Weekly report'] }],
      pins: [{ ref: 'FR-02.1', sel: '#save' }] },
  ],
};
```

## Screen keys

| Key | Meaning |
|---|---|
| `id`, `name` | Stable screen code (S01, S03b) and name. `id` names the PNG. |
| `flow`, `cont` | Screens with the same `flow` and `cont: 1` continue in the same tab (keeps handed-over data). |
| `viewport`, `scale` | Override the manifest values for this screen. `scale` applies when a new tab opens. |
| `fullPage` | Capture the whole page; pin positions use the page height. |
| `at` | Screenshot this many ms after the last step, before the usual 250 ms settle and before pins are measured: for short states (a skeleton shown for 500 ms). Pair it with `noWait` on the `goto` or `reload`. Recorded in `screens.json`. |
| `neutral` | Pointer and focus reset before the screenshot (below). `false` turns it off; `{ pointer: false }` or `{ blur: false }` turns off one part. Also a manifest key (default for every screen). |
| `steps` | Actions to reach the screen (below). |
| `pins` | `{ ref, sel }`: rule code and element. `sel` may be `F|<selector>` for an element inside frame `F`. |
| `next` | Exits: `{ to, action, trigger, condition }`. `action` is the exact label on screen. |

## Steps

| Step | Does |
|---|---|
| `{ goto: 'path#/route' }` | Open a file relative to the base URL. A goto that only changes the hash keeps the document (no reload). |
| `{ goto: 'path#/', reload: true }` | Open, then reload: use it after an `eval` that sets `localStorage`, so the app reads the new value |
| `{ reload: 1 }` | Reload the current page and wait for `load` (same name and meaning in `validate`) |
| `{ reset: 1 }` | Clear `localStorage` and `sessionStorage`, reload |
| `{ click }`, `{ hover }`, `{ waitFor }` | Act on or wait for a selector |
| `{ fill: [sel, text] }` | Fill an input |
| `{ type: text }` or `{ type: [sel, text] }` | Type with the keyboard (optionally click `sel` first) |
| `{ press: 'Escape' }` | Press a key |
| `{ files: [sel, ['a.xlsx']] }` | Click `sel` and choose files from `att` |
| `{ eval }`, `{ waitEval }` | Run a script / wait until an expression is true |
| `{ waitUrl: 'regex' }`, `{ wait: ms }` | Wait for a URL / a delay |

`goto` and `reload` take `noWait: true`: return when navigation starts instead of at `load`.

Short or timed states: prefer a hold flag the prototype reads (`goto: 'index.html?hold=loading#/'` keeps the skeleton until the flag is gone), so the capture does not depend on timing. Without one, use `noWait` plus the screen's `at`.

Pointer and focus reset (default on): before each screenshot the pointer moves off the page, so a click in the steps (or an earlier screen in the same tab) leaves no hover style, and a focused button, link or tab is blurred. A screen with a `hover` step keeps its pointer. Inputs, text areas, selects, editable text and anything inside an open menu, listbox, combobox, dialog or popover keep their focus. This keeps `--baseline` pixel diffs free of pointer noise.

Any step may add `in: 'F'` (act inside frame `F`) and `timeout` (ms). Without it a step waits the manifest's `timeout` (default 8000 ms); `validate` uses the same value (`validation.py init --from-manifest` copies it into the plan), so a screen that captures does not fail there. The manifest may name its `app`: token names then come from that app's DS profile (`apps[].ds`).

Every frame named by a selector (`F|…`) or by `in` must be declared in `frames`; otherwise `capture.js` stops with an ERROR that lists each place, before it opens a browser (a pin is never silently reported as "not found").

Older manifests may use frame-prefixed step names: `fclick: sel` is read as `{ click: sel, in: 'F' }`, `ehover`, `ffill`, `etype`, `ffiles` likewise, and `ewait: sel` (a selector) as `{ waitFor: sel, in: 'E' }`. The frame letter still needs a `frames` entry. `screens.json` records the steps in the current form.

`--only S05,S07` captures those screens only. Screens they continue from (`cont: 1` in the same flow) run first to set up the state, without a screenshot; no other screen runs.

## Output: `screens.json`

```json
[{ "id": "S01", "name": "Task list", "flow": "f1", "cont": false,
   "page": "apps/acme-web/index.html", "hash": "#/", "viewport": {"width": 1280, "height": 900}, "scale": 2,
   "steps": [], "errors": [],
   "pins": [{ "ref": "FR-01.1", "sel": "#new", "found": true, "leftPct": 50, "topPct": 21.6,
     "style": { "props": { "color": "rgb(255, 255, 255)", "backgroundColor": "rgb(37, 99, 235)", "...": "..." },
                "tokens": { "color": ["--acme-text-on-brand"], "backgroundColor": ["--acme-bg-brand"], "...": [] },
                "cls": "acme-btn", "tag": "button", "text": "New task" } }],
   "exits": [{ "to": "S02", "action": "Click \"New task\"", "condition": "", "found": true,
     "leftPct": 50, "topPct": 21.6, "xpage": false }] }]
```

Token matching: every custom property that starts with `ds.json > tokens.prefix` is resolved on `<html>`. For each property only names of the matching role are kept (`color` → `text`, `icon`; `backgroundColor` → `bg`; `borderColor` → `stroke`; `borderRadius` → `radius`; `fontSize`; `lineHeight`; `gap`, `padding` → `spacing`; `boxShadow` → `shadow`). With no role match, primitives (prefix but no role) are returned. `padding` tokens describe `padding-top` only. Values `0`, `none`, `normal`, `auto` and `transparent` get no token, and tokens that start with one of `ds.json > tokens.ignorePrefixes` are never named. `search` records the query of the page (or of the last `goto`), so `screens.json` routes in a package keep it (`?demo=1`).

`screens.json` merges with the previous run, so `--only` keeps the other screens. Exit code 1 when a screen's steps fail.

Border notes: `borderColor` and its stroke token are recorded only when the border is wider than 0. An element without a border gets no stroke token in its style notes (earlier versions listed the colour of a 0 px border).
