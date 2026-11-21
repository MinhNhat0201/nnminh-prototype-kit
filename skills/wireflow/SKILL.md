---
name: wireflow
description: "Put a prototype flow board on Figma: one screenshot per screen, joined by arrows along the business flows, with pins, click rings, page-change edges, dashed 'to confirm' edges, out-of-scope boxes and demo-site buttons. Cheap on tokens: never reads the HTML, reuses captured images and screens.json, sends one use_figma call built from a fixed template, uploads images directly. Updates an existing board in place so links already sent keep working. Use when the user says 'put the flow on Figma', 'export the wireflow to Figma', 'HTML to Figma', 'make a flow board in Figma'. To rebuild screens as editable layers with DS components use `mockup`; to package a zip use `handoff`. Also use for the same request in any language."
---

# Wireflow board on Figma

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.wireflow` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

The result is a **flow reference board** in a Figma Design file, not an editable design. Each screen is a real prototype capture; arrows carry the user action, as in the flows section of the spec.

Why it is cheap: the model never reads the HTML and never writes Figma code per element. Images and pin positions come from the capture step of `annotate`. The code sent to Figma is a **fixed template** (`assets/wireflow-template.js`) plus compact data. Images go up by HTTP, not through the context.

Other levels (only when the user chooses; ask first):
- **Editable frames:** try one screen with a Figma HTML import tool, report the cost, then continue.
- **Rebuilt with DS components (Specs board):** use `mockup` (it calls this skill for the Wireflow board).

Figma guidance forbids screenshots in place of UI when *rebuilding a screen*. This board does not rebuild screens, so images are allowed. Say so in the report; never call this board "the Figma design".

Scripts: `S=skills/wireflow/scripts` (inside the kit). Every script has `--help`.

## Step 0. Inputs
1. **Images and `screens.json`:** the capture output of `annotate`. Reuse an existing capture (for example from a handoff package); do not capture again. No capture yet: run `annotate` up to the capture review first. The feature is not in the prototype (search screen names, labels, routes under the app path and recent branches): stop and ask for the source, or offer `prototype`. Never build a board from guessed screens.
2. **`flows.json`:** the flows of the board (format below). A handoff package has it at `requirements/flows.json`. None: write it from the flow agreed with the user. Never infer flows.
3. **Target Figma file (required for a handoff):** the designer gives a link to a Design file they can edit.
   - Link with `node-id`: call `get_metadata` on it (cheap). A page (`canvas`): build on it with `--page-id` (`-` becomes `:`). A frame or section: ask whether to use its page or a new page.
   - No file: create one with `create_new_file` following `figma-create-new-file` (ask which team when there are several).
   - Page name: `[<work-item code>] <feature>` (locale key `wireflow.page`). Board title: `Wireflow · <feature> v<version>`.
4. **Before the first `use_figma` call:** load the `figma-use` skill (mandatory) and pass `skillNames: "figma-use"`. Call `create_session` with the file key once and reuse the session id.

### flows.json
```json
{
  "flows": [
    {"id": "WF-01", "name": "Main flow: create a task", "url": "", "start": "", "rows": [
      {"label": "", "items": [["n","S01"], ["e","Click \"New\"",""], ["n","S02"], ["e","Click \"Open settings\"","x"], ["n","S03"]]},
      {"label": "From S02, nothing selected", "items": [["e","Click \"Save\"","u"], ["n","S02b"]]},
      {"label": "From S01, out of scope", "items": [["e","Click",""], ["out","Reports"]]},
      {"label": "From S02, cancel", "items": [["e","Click \"Close\"",""], ["chip","S01"]]}
    ]}
  ],
  "offflow": ["S41"],
  "units": {"S01": "FR-01"}
}
```
| Item | Meaning |
|---|---|
| `["n", id]` | Screen. Each screen appears once as `n`; repeat it with `chip` ("back to"). |
| `["e", label, flag]` | Edge. Flag `""` verified, `"x"` page change (another file), `"u"` to confirm (dashed). Label is the exact on-screen text. |
| `["out", label]` | Out-of-scope box. Empty label uses the locale default. |
| `["chip", id]` | Back-to-screen chip. |
| `offflow` | Screens outside every flow (own section). |
| `units` | Spec unit code shown under the screen name. |
| `home`, flow `url`, flow `start` | Demo links (step 0b). `start`: short exact on-screen action when the first screen needs clicks to reach. |

## Step 0b. Demo links per flow
Every board has demo buttons by default: "Open prototype" in the header and "Open flow demo" next to each flow. Reuse `url` already in `flows.json`. Otherwise:
```
python3 -I $S/demo_links.py fill --screens <screens.json> --flows <flows.json> --app <app id> [--site <https URL>] [--manifest <capture manifest>] [--page-root prototype]
```
- Page paths keep their folder (`tasks/index.html` → `<site>/<app path>/tasks/`). Captures of a package copy served from the package folder: `--page-root prototype`.
- `--site` defaults to `kit.config.json > deploy.site`. No site at all: skip; the board has no buttons, and say so in the report.
- Link = site + page path + hash route of the first screen. A flow with a hand-set `url` keeps it. Links must be https on the site, else ERROR.
- With `--manifest`: a REMINDER lists flows whose first screen needs steps and has no `start`. Fill `start` with the exact on-screen label; never guess.
- Links open the page and route only; they do not replay the steps. A site behind sign-in needs an account for that app. The site is the live build and can be newer than the captures.
- A scope-locked handoff build is not on the site: links open the full app. Say so in the report.

## Step 1. Build the data
```
python3 $S/figma_wireflow.py build --spec <folder with screens.json> --flows <flows.json> --out <scratchpad folder> \
  --pbi "<code>" --feature "<feature>" --version <x.y.z> --app <app id> (--page-id <id> | --page "<name>") \
  --png <folder of original capture PNGs> [--scale 0.75 for 390px mobile; default 0.5 for 1280px web] [--width 3200]
```
- Writes `code.js` (send verbatim), `images/<Sxx>.png|jpg`, `plan.json` (counts). Title, page name, meta line and board labels come from the project language; the meta line ends with the DS version label.
- ERROR when a flow uses a screen missing from `screens.json` or a link is off the site. WARNING for screens in no flow.
- **Sharp images:** always pass `--png` with the original capture PNGs (`deviceScaleFactor: 2`); they go up unchanged. Without them the script converts the `--spec` images to JPEG quality 94 at full size (WebP from a package is already compressed). Never use 1x captures: the board shows them at half size, so they blur when zoomed.

## Step 2. Build the board (one call)
- One `use_figma` call with `code` = the content of `code.js` **verbatim** (read the file and paste it; never rewrite or shorten it).
- The template uses the page from `--page-id`, or creates/reuses the page named `--page`. It removes an older board with the same title and places the new one to the right of existing content.
- It returns `rootId`, `imageNodeIds`, `imageScreens` (same order), `edges`. Keep the two arrays for step 3; no canvas read needed.

## Step 3. Attach the images
- `upload_assets` with `count` = number of screens (at most 60 per call; split in order) and `nodeIds` = `imageNodeIds`, `scaleMode: "FILL"`.
- Write `{"imageScreens": [...], "urls": [...]}` to `<out>/urls.json` in the returned order, then:
  `python3 $S/figma_wireflow.py upload --out <out> --urls <out>/urls.json`
- URLs are single-use: on a failed upload, request new URLs for the failed screens only.

## Step 3b. Update an existing board (next package version)
Never rebuild a board that was already sent: new nodes break the links.
1. Get the ids: `python3 $S/figma_wireflow.py mapjs --root <board id>` prints code for `use_figma`. It returns `{"S01": "<card node>", …, "_imgs": {"S01": "<image frame>"}, "_board", "_page", …}`. Save it as JSON.
2. Replace only changed screens (`<shots>/changed.json`, written by `handoff`'s `pkg.py capture`; none: ask): `upload_assets` with `nodeIds` = their `_imgs` frames, then `upload` as in step 3.
3. Rename the board and sync repeated images: `python3 $S/figma_wireflow.py retitlejs --root <board id> --title "Wireflow · <feature> v<new version>"`, send the printed code through `use_figma`.
4. New screens: add a card to the right flow by hand, or rebuild the board only when the user agrees.
5. Map screens to Figma in the package config, so each screen in the package links to Figma instead of an image:
   `python3 $S/figma_wireflow.py setmap --config <package>/pkg.json --json <mapjs result> --file <Figma file link>`
   It writes `figma_file`, `figma_board`, `figma_page` and `figma` (screen id → card node). Run it after a first build too.

## Step 4. Check (cheap)
- One `get_screenshot` of `rootId` (default 1024px): all flows, images shown, nothing overlaps. Do not capture each screen.
- Compare screen and edge counts with `plan.json` from the step 2 return value; call `get_metadata` only when something is missing.
- The header shows "Open prototype" and every flow with `url` shows "Open flow demo".
- Wrong: fix `flows.json` or the template and rerun from step 1 (only for a board not yet sent; otherwise step 3b).

## Step 5. Report (short)
Figma link with the board `node-id`; number of flows, screens, edges (page change, to confirm); demo links per flow (which have `start`, which have none) and the sign-in note; `code.js` size and number of Figma calls; what was not done (editable frames, `mockup`). Remind that the board is a reference built from captures, state the DS version label of the prototype, and point to the package spec for details.

## Rules
- Never read HTML into the context. Never embed base64 images in code. Never write per-package Figma code; change data only.
- Template change (layout, symbols): edit `assets/wireflow-template.js` in the kit; it applies to every later board. Layer names (`<id> · image`, `Board title`) are matched by scripts: keep them.
- Never edit the prototype or the images. A wrong screen: recapture with `annotate`.
- The Figma file belongs to the user: never delete pages or nodes outside the board this skill made (the board is found by its title).
