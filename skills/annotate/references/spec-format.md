# Spec folder format

Headings and fixed labels below are the English strings. Write them in the project language from
`locales/<language>/annotate.json` (keys in brackets).

## `spec/index.md`

```markdown
---
pbi: "PBI 1234"
title: "Scheduled tasks"
version: "1.0.0"
date: "2026-11-21"
ds: "Acme DS 0.1.0"
prototype: "prototype/index.html"
---
# Scheduled tasks

PBI 1234 · version 1.0.0 · Acme DS 0.1.0 · Prototype: `prototype/index.html` (how to open: README)

## Spec units                                  [annotate.h.units]
| Code | Title | Screens | Confidence | File |
|---|---|---|---|---|
| FR-01 | … | S01, S02 | High | [FR-01](FR-01.md) |

## Screens                                     [annotate.h.screens]
| Code | Name | Page · route | Figma | Spec |
|---|---|---|---|---|
| S01 | … | `index.html#/…` | [Figma](<node link>) | FR-01 |

## Not matched                                 [annotate.h.unmatched]
- Screens without a spec unit: …
- Spec units without a screen: …

## Out of scope                                [annotate.h.outOfScope]
## Deviations from spec                        [annotate.h.deviations]
```

`check` requires `pbi`, `title`, `version`, `ds`, and that every unit file is linked here.

## `spec/FR-01.md` (one unit)

```markdown
# FR-01 · <title>
Screens: S01, S02 · Match confidence: High · Flow: [WF-01](flows.md)      [annotate.line.unitMeta]

## Business rules (BA wording, verbatim)                                  [annotate.h.business]
<verbatim text>
1. **FR-01.1** <verbatim rule>

## Screens
### S01 · <screen name>
Page · route: `index.html#/…` · open in prototype: `prototype/index.html#/…`
How to reach: <action, exact labels>
Figma: [S01](<node link on the wireflow board>)

## Design notes                                                           [annotate.h.designNotes]
| Pin | Rule | Element | DS component | Token | States | Style change |
|---|---|---|---|---|---|---|
| S01-1 | FR-01.1 | <label on screen> | <component, variant, size> | <property `--acme-…`> | <states> | <`property: before → after` / New / No style change> |

## Deviations from spec
- …
```

A unit replaced or dropped in this version gets a status line under the title, `Status: Dropped in 1.5.0` (or
`Replaced in 1.5.0 by FR-12`; Vietnamese `Trạng thái: Bỏ ở 1.5.0`). The handoff archives it; wording in
`handoff`'s [package-layout.md](../../handoff/references/package-layout.md#replaced-or-dropped-units).

Write these labels as words so they can be grepped: "needs confirmation", "Deviation from spec", "Out of scope",
"intentional deviation", "No screen for this item yet." (`annotate.label.*`).

## `spec/flows.md`

```markdown
# Wireflow

## WF-01 · Create a task
Open demo: [Open demo of WF-01](https://prototypes.example.com/apps/acme-web/#/) · Start: S01

1. S01 → [Click "New task"] → S02
2. S02 → [Click "Save"] → S01
3. S02 → [Click "Save" with an empty name] → Out of scope (needs confirmation)

Off-flow screens: S09

```mermaid
flowchart LR
  S01 -->|Click "New task"| S02 -->|Click "Save"| S01
```
```

Multi-page: write file and route after the code, `S02 (library/#p1) → [Click "Open"] → S03 (editor/)`, and mark the page change.

## `requirements/flows.json`

```json
{ "flows": [
    { "id": "WF-01", "name": "Create a task", "url": "https://prototypes.example.com/apps/acme-web/#/", "start": "S01",
      "rows": [
        { "items": [["n", "S01"], ["e", "Click \"New task\""], ["n", "S02"], ["e", "Click \"Save\""], ["chip", "S01"]] },
        { "label": "From S02, when the name is empty",
          "items": [["e", "Click \"Save\"", "u"], ["out", "Out of scope"]] } ] } ],
  "units": { "S01": "FR-01", "S02": "FR-02" },
  "offflow": ["S09"] }
```

| Item | Meaning |
|---|---|
| `["n", "S01"]` | Screen node |
| `["e", "label"]` | Edge; third value `"u"` = unverified (dashed, "needs confirmation"), `"x"` = page change |
| `["chip", "S01"]` | "Back to S01" |
| `["out", "text"]` | Grey dashed box, e.g. "Out of scope" |

`units` links a node to its unit anchor. `url` must also appear in `spec/flows.md`.

## `spec/cross-page.md` (multi-page)

| Table [key] | Columns |
|---|---|
| Pages and routes [`annotate.h.pagesRoutes`] | page (file), route, screens, description, entry from |
| Data handed between pages [`annotate.h.handover`] | from → to, action, mechanism (sessionStorage / localStorage / URL parameter), key and content, who writes / reads, one-time or kept |
| Direct open [`annotate.h.directOpen`] | page, observed behaviour (back to home, empty state, error) |
| Shared state [`annotate.h.sharedState`] | `localStorage` key, content, scope, how to reset |

## `requirements/spec-map.json`

```json
[{ "unit": "FR-01", "screens": ["S01", "S02"], "confidence": "High", "reason": "Button label \"New task\" equals FR-01.1" }]
```
