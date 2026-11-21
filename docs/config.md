# Configuration

The kit reads two files. Skills and scripts never hard-code a design system (DS), a product name or a site URL: they read them from here.

| File | One per | Holds |
|---|---|---|
| `kit.config.json` | project (repository root) | language, stack, apps, local-component registry, handoff, deploy |
| `ds/<name>/ds.json` | design system profile | token prefix and roles, CSS bundle, theming attributes, version label, Figma libraries |

Scripts find `kit.config.json` by walking up from the current directory. `scripts/kitconf.py` and `scripts/kitconf.js` load both files and fill defaults; use them instead of parsing the files by hand.

## `kit.config.json`

```json
{
  "language": "en",
  "stack": "html",
  "ds": "ds/acme",
  "apps": [
    {
      "id": "acme-web",
      "name": "Acme Web",
      "path": "apps/acme-web",
      "entry": "index.html",
      "type": "single",
      "build": null,
      "check": null
    }
  ],
  "local": {
    "prefix": "x-",
    "marker": "LOCAL",
    "registry": "docs/local-components.json"
  },
  "handoff": {
    "dir": "docs/handover",
    "zipName": "Design - {pbi}",
    "maxZipMB": 3,
    "figmaRequired": true
  },
  "email": {
    "subject": "[{app}] Design - {feature} - {version}",
    "attachLimitMB": 3
  },
  "deploy": {
    "type": "none",
    "site": null
  },
  "paths": {
    "changelog": "CHANGELOG.md",
    "plans": "docs/plans",
    "audits": "docs/audits"
  }
}
```

| Key | Values | Default | Used by |
|---|---|---|---|
| `language` | BCP 47 code: `en`, `vi`, … | `en` | Every skill: the language of replies and of generated documents (spec, README, AGENTS, QC checklist, email). Template strings come from `locales/<language>/*.json` (one file per skill, keys `<skill>.<key>`); a missing key falls back to `en`. |
| `stack` | `html`, `react`, `vue` | `html` | `kickoff`, `prototype`, `review`, `contribute`, `handoff`, `sync`. See [stacks.md](stacks.md). |
| `ds` | path to a DS profile folder | required | Every skill |
| `apps[]` | one entry per prototype app | `[]` | `prototype`, `review`, `contribute`, `sync`, `handoff` |
| `apps[].stack` | `html`, `react`, `vue` | the top-level `stack` | Per-app override, so one repository can keep old `html` apps and add `vue` apps. Skills use the app's stack when they work on one app. |
| `apps[].type` | `single` (one HTML file), `multi` (one file per feature, shared shell), `spa` (React/Vue app with a router) | `single` | `prototype`, `handoff` |
| `apps[].build`, `apps[].check` | shell commands, or `null` | `null` | Run after editing a shared shell (`multi`) or before a handoff (`spa`) |
| `local.prefix` | CSS class prefix of local (not-yet-in-DS) components | `x-` | `prototype`, `contribute`, `review` |
| `local.marker` | Comment marker that opens a local block: `/* LOCAL: <name> */` | `LOCAL` | same |
| `local.registry` | JSON registry of local components | `docs/local-components.json` | same |
| `handoff.zipName` | zip and root folder name; `{pbi}` is the work-item code | `Design - {pbi}` | `handoff`, `share` |
| `handoff.figmaRequired` | the handoff stops when a screen has no Figma node | `true` | `handoff`, `wireflow` |
| `email.subject` | subject template | as above | `share` |
| `email.attachLimitMB` | largest zip attached to a draft; bigger zips get a link instead | `3` (what mail connectors usually accept per call) | `share` |
| `deploy.type` | `none`, `vercel`, `static` | `none` | demo links in `wireflow`, `share`, `handoff` |
| `deploy.site` | base URL of the deployed prototypes | `null` | same |

## `ds/<name>/ds.json`

```json
{
  "name": "acme",
  "label": "Acme DS",
  "version": "0.1.0",
  "platforms": ["web", "mobile", "tablet"],
  "tokens": {
    "prefix": "--acme-",
    "roles": {
      "text": "--acme-text-",
      "bg": "--acme-bg-",
      "stroke": "--acme-stroke-",
      "icon": "--acme-icon-",
      "radius": "--acme-radius-",
      "fontSize": "--acme-font-size-",
      "lineHeight": "--acme-line-height-",
      "spacing": "--acme-space-",
      "shadow": "--acme-shadow-"
    },
    "scale": {
      "spacing": "--acme-num-spacing-"
    },
    "file": "tokens.json"
  },
  "css": {
    "bundle": "dist/acme.css",
    "sources": ["tokens.css", "tokens-dark.css", "base.css", "components.css", "responsive.css"],
    "marker": { "begin": "@ds:begin", "end": "@ds:end" }
  },
  "version_label": {
    "text": "{label} {version}",
    "meta": "ds-version"
  },
  "theming": {
    "brand": { "attr": "data-brand", "values": ["default"] },
    "mode": { "attr": "data-mode", "values": ["light", "dark"], "default": "light" },
    "density": { "attr": "data-density", "values": ["auto", "comfortable", "standard", "compact"], "default": "auto" }
  },
  "breakpoints": { "compact": 0, "medium": 600, "expanded": 840 },
  "icons": { "set": "tabler", "file": "icons.json" },
  "catalog": "catalog.md",
  "rules": "rules.md",
  "library": { "page": "library.html" },
  "figma": {
    "libraries": [
      { "name": "Acme Components", "platform": "web", "fileKey": null }
    ],
    "collections": { "primitives": "Primitives", "semantic": "Semantic", "spacing": "Spacing" },
    "modes": { "light": "Light", "dark": "Dark" }
  },
  "preset": { "name": "shadcn", "version": null }
}
```

| Key | Meaning |
|---|---|
| `tokens.prefix` | Prefix of every custom property of the DS. Scripts treat `var(<prefix>…)` as "uses a token". |
| `tokens.roles` | Prefix per role. `annotate` groups computed styles by role; `review` maps hard-coded values to tokens of the matching role (`color` → `text`, `background` → `bg`, borders → `stroke`, `fill`/`stroke` → `icon`). |
| `tokens.scale.spacing` | Primitive spacing scale. Used to match hard-coded `margin`, `padding`, `gap`. |
| `css.bundle` | One CSS file with the whole DS. Prototypes in the `html` stack embed it; the spec viewer and the audit read it. Path is relative to the profile folder, or a URL. |
| `css.marker` | Comments that wrap the embedded DS CSS inside an app, so `sync` can replace it and `review` can tell DS CSS from app CSS. |
| `css.styleBlocks` | Optional id prefix (for example `lib`): every `<style id="<prefix>…">` block in an app is DS CSS. For DS that embed their library blocks by id instead of marker comments. A file in the app named like the bundle (for example `mds.css`) and a `<link href>` to it also count as DS CSS. |
| `version_label` | Footer text and `<meta>` name that state which DS version a prototype uses. |
| `theming` | Attributes the DS reads on `<html>`. Skills set them only through these keys; they never invent new attributes. |
| `catalog` | Component catalogue for agents: class, variants, states, tokens, and the `components.map` table (HTML class ↔ React ↔ Vue component). |
| `rules` | Hard rules of the DS (intentional deviations, accessibility fixes, "do not override"). Every skill reads it before it builds or reviews. |
| `figma` | Libraries, variable collections and modes for `mockup` and `adopt`. |
| `preset` | The public DS the profile was adopted from, if any (`adopt`). |

## The DS profile folder

```
ds/<name>/
  ds.json         this file
  tokens.json     tokens in W3C Design Tokens (DTCG) format
  tokens.css      primitives and semantic tokens (light)
  tokens-dark.css dark mode
  base.css        reset, font, focus ring
  components.css  components; semantic tokens only
  responsive.css  breakpoints, tab bar on compact screens
  dist/<name>.css bundle of the files above
  catalog.md      component catalogue + components.map
  rules.md        hard rules
  library.html    library page (optional)
  flutter/        Dart theme generated from tokens (optional)
  NOTICE          origin and licence of the preset (when adopted)
  CHANGELOG.md
```

A profile may live inside the project repository (recommended for a private DS) or in its own repository.
