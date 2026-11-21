---
name: contribute
description: "Keep the local-component registry in step with the apps, score local (not-yet-in-DS) components, and move the good ones into the DS through two approval gates: the user picks items to propose (a `proposal` block is written), then approves each proposal before `document` adds it to the DS and `sync` updates the apps. Use when the user says 'review local components', 'which local components can go into the DS', 'propose this to the design system', 'update the local registry', 'check the registry', or after adding, changing or removing a local block. Use `sync` to bring a new DS version into apps, `review` for a full DS compliance audit, `document` to edit the DS directly. Also use for the same request in any language."
---

# Contribute local components to the DS

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.contribute` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

A local component is UI the DS does not have yet. Its code is marked, and the registry records what it is and what was decided. This skill keeps both in step and runs the path from local to DS with two approval gates.

Script: `python3 <kit>/skills/contribute/scripts/registry.py` (`scan`, `update`, `check`, `ack <id>`, `list`, `report`; `--help` lists options). Demo images: `node <kit>/skills/contribute/scripts/capture_demos.js` (header of the file explains the `demo` field).

## How local code is marked

| Stack | Mark |
|---|---|
| `html` | A CSS block that opens with `/* <local.marker>: <name> */` (default `/* LOCAL: <name> */`); classes start with `local.prefix` (default `x-`). One unique name per block. |
| `react` | A file `src/components/local/<Name>.tsx` whose first comment is `/* LOCAL: <name> */`; classes keep the prefix. CSS blocks in `.css` files are marked as in `html`. |
| `vue` | A file `src/components/local/<Name>.vue` with the same header (`/* … */` or `<!-- LOCAL: <name> -->`). |

Local code uses tokens only. `check` fails on prefixed classes outside any block and on unmarked files in `src/components/local/`. Prefixed classes found on the first scan are recorded once as existing debt; that list only shrinks.

## The registry (`kit.config.json > local.registry`)

One entry per block. The script writes `file`, `line`, `size`, `classes`, `uses`, `fp` (fingerprint) and `history`. You write the judgement fields:

| Field | Content |
|---|---|
| `title`, `kind` | Short name; `component`, `override`, `pattern`, `layout` or `data` |
| `status` | `pending` (new, not decided), `keep` (stays local), `propose` (proposed to the DS), `replaced` (replaced by the DS), `removed` (set by the script when the block is gone) |
| `summary`, `where` | What it is; screens that use it |
| `vs_ds` | Closest DS component and the difference |
| `decision`, `decided_on` | Decision with its reason; ISO date |
| `demo` | Optional: how to capture it (see `capture_demos.js`) |
| `proposal` | Required when `status` is `propose` (gate 1) |

Projects may name fields differently: `kit.config.json > local.fields` maps kit fields to the project's (`{"vs_ds": "compare"}`); the script reads and writes those names, and keeps every field it does not know (`demo`, notes) as it is. A project that owns its registry (it also builds pages from it) sets `local.command.update` / `local.command.check`: `update` and `check` run those commands and report their output; `--builtin` runs the kit's own.

Write only what you can show from the code, the registry history or the DS. Not verified: leave it empty, or in a proposal write "Unconfirmed: …". `replaced` and `removed` entries stay for traceability; reviews skip them.

**Every time a local block is added, changed or removed** (also from `prototype` or `sync`): `update`, fill in the judgement fields of new or changed entries, `ack <id>` for changed proposals, then `check` must print "Registry matches the apps". Entries still `pending` are allowed; list them in the report.

## Gates (required)
- **Gate 1: pick items to propose.** Without the user's choice, change no status and write no proposal.
- **Gate 2: approve a proposal into the DS.** Without approval of that proposal, do not edit the DS, bump its version or change apps. Gate 1 approval is not gate 2 approval.
- Nobody answers (scheduled or headless run): do steps 1 to 3 only, report the candidates, stop.

## Step 1. Current state
1. `registry.py check`. Code and registry differ: `update` first (this records facts, not decisions) and point out new `pending` entries.
2. Read the entries with `status` `keep`, `pending`, `propose` (skip `kind: data`). `registry.py list` gives the overview.
3. Compare each with the current DS (`catalog`, `rules`, `CHANGELOG.md`). Never from memory.

## Step 2. Score each entry
Four criteria. Each is **Met / Not met / Unknown**, with evidence from the registry or code (screens, classes, tokens):
1. **Used on 2+ screens or in 2+ apps** (`where`, `uses`, same or equivalent classes across apps).
2. **Clear states and variants** (hover, focus, selected, error, disabled… seen in the block or on screen).
3. **No app-specific business logic** (not tied to data or flows only one app has).
4. **Buildable with DS tokens only** (no hard-coded values; name the missing tokens).

Verdict:

| Verdict | When |
|---|---|
| A. Propose to the DS | All four met, or 1 and 4 met with a clear reason for the rest |
| B. Keep local | App-specific, one use, or not stable yet; give the reason |
| C. Replace with the DS | The DS already has an equivalent: no proposal, hand over to `sync` |
| D. Needs information | Any criterion "Unknown": say exactly what is missing and who can answer |

Never guess: a criterion you cannot verify is "Unknown", not "Met".

## Step 3. Present and wait (gate 1)
Table: `entry | app | verdict | 4 criteria | evidence | proposal type (component, variant, pattern) | suggested bump | cost (apps to change)`. Order A, D, B, C. Ask (at most 4 questions per turn) which entries to propose and which verdicts to change. Stop until the user answers.

## Step 4. Write the proposal (after gate 1)
For each chosen entry:
1. Set `status: "propose"` and fill `proposal`:
   - **Required:** `name`; `type` (`component`, `variant` or `pattern`); `purpose` (role, where it appears); `anatomy` (parts and how they relate); `rules` (use when, do not use when); `tokens` (tokens used; tokens missing); `bump` (`minor` for a new component, `patch` for a small change, `major` for a breaking token change).
   - **Should have:** `variants`; `states` (seen, or "Unconfirmed: …"); `reuse` (DS components it can reuse); `missing` (what the DS really lacks).
   - Only what you can verify. Otherwise "Unconfirmed: …"; never empty, never guessed.
2. No demo image: add a `demo` field and run `capture_demos.js <id>`.
3. `ack <id>`, then `check` must pass. `registry.py report --status propose --out <file>` gives a Markdown summary to share; it states that a proposal is not yet part of the DS.
4. Record the change in `paths.changelog`. Branch and pull request only when the user asks.

After that, every change to the block needs a review of `proposal` and a new `ack`; `check` fails until then.

## Step 5. Approve into the DS (gate 2)
For each proposal, show: the rule text that will be written (from `proposal`), the DS area (platform), the version bump, the apps that will switch from the local block to the DS component, and the risks. Ask: approve, change, or not yet. Only on **approve**:
1. Run `document`: add the component and its rules to the DS, bump the version, test, record in the DS changelog. Set the entry to `status: "replaced"`, `decision` "in DS <version>", the date; `update`, `check`.
2. Run `sync` for every app that uses the local block, so it switches to the DS component. Report visible behaviour changes.
3. One DS release per approval round. Branch and pull request only when the user asks.

Not approved: the proposal stays `propose`.

## Report (short)
Entries reviewed per verdict; entries chosen at gate 1; proposals written; proposals approved at gate 2 and the new DS version; apps synced; "Unknown" criteria and who must answer; `pending` entries; missing tokens and other warnings.

## Rules
- No status change and no proposal before gate 1; no DS change, version bump or app change before gate 2.
- Evidence comes from the registry, the code or real screens. Never invent use counts, variants or tokens.
- A proposal is only a proposal: never write it into the DS rules before approval.
- DS components and tokens change only through `document`.
