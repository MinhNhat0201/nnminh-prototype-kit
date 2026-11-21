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
| `steps` | Actions to reach the screen (below). |
| `pins` | `{ ref, sel }`: rule code and element. `sel` may be `F|<selector>` for an element inside frame `F`. |
| `next` | Exits: `{ to, action, trigger, condition }`. `action` is the exact label on screen. |

## Steps

| Step | Does |
|---|---|
| `{ goto: 'path#/route' }` | Open a file relative to the base URL |
| `{ reset: 1 }` | Clear `localStorage` and `sessionStorage`, reload |
| `{ click }`, `{ hover }`, `{ waitFor }` | Act on or wait for a selector |
| `{ fill: [sel, text] }` | Fill an input |
| `{ type: text }` or `{ type: [sel, text] }` | Type with the keyboard (optionally click `sel` first) |
| `{ press: 'Escape' }` | Press a key |
| `{ files: [sel, ['a.xlsx']] }` | Click `sel` and choose files from `att` |
| `{ eval }`, `{ waitEval }` | Run a script / wait until an expression is true |
| `{ waitUrl: 'regex' }`, `{ wait: ms }` | Wait for a URL / a delay |

Any step may add `in: 'F'` (act inside frame `F`) and `timeout` (ms, default 8000).

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

Token matching: every custom property that starts with `ds.json > tokens.prefix` is resolved on `<html>`. For each property only names of the matching role are kept (`color` → `text`, `icon`; `backgroundColor` → `bg`; `borderColor` → `stroke`; `borderRadius` → `radius`; `fontSize`; `lineHeight`; `gap`, `padding` → `spacing`; `boxShadow` → `shadow`). With no role match, primitives (prefix but no role) are returned. `padding` tokens describe `padding-top` only.

`screens.json` merges with the previous run, so `--only` keeps the other screens. Exit code 1 when a screen's steps fail.
