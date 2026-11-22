# Rules registry

A project's rules (tokens only, ask before a new page, mock data marked…) used to live in long documents that every skill had to read in full. The registry keeps **one Markdown file per rule** instead. Each rule says how strict it is, where it applies, which skills must load it, which decision made it, which apps are exempt, and how a script can check it. Skills load only the rules for the app and the step at hand.

Script: `python3 <kit>/scripts/rules.py` (`--help` lists every command). Configuration: `kit.config.json > paths.rules` and `rules.categories` (see [config.md](config.md)).

## Layers

| Layer | Folder | Holds | Ids |
|---|---|---|---|
| `kit` | `<kit>/rules/` | Generic rules every project inherits (DS tokens only, no CSS over DS components, ask before a new page, keep business rules when a page is rebuilt, mock data marked, no loose `.js` in packages…). Read-only for projects. | `XXX-900`–`999` |
| `ds` | `<DS profile>/rules/` | Rules of one DS profile. They apply to the apps that use that profile (`apps[].ds`, else the top-level `ds`). | `XXX-500`–`899` |
| `project` | `<paths.rules>/` (default `rules/`) | Rules of this project. | `XXX-001`–`499` |
| `app` | same folder, `layer: app` | Rules of some apps only; `applies_to` is required. | `XXX-001`–`499` |

Precedence: kit < ds < project < app. A rule of a later layer replaces an earlier one only with `overrides: <id>` and a `reason`; it replaces it for the apps in its own `applies_to` (empty = every app). Number ranges keep ids unique when the kit or a DS ships new rules later.

A rule that does not hold for one app keeps its text and gets an **exception** for that app (`exceptions: [{app, note, decision}]`). Kit rules cannot be edited: an app that needs something else gets an app rule with `overrides`.

## Rule file

`<layer folder>/<category>/<ID>-<slug>.md`, for example `rules/styling/STY-001-no-raw-colours-in-app-css.md`:

```markdown
---
id: STY-001
title: No raw colours in app CSS
category: styling
layer: project
applies_to: []
skills: [prototype, review, validate]
severity: must
status: active
since: 2026-11-22
decision: D-003
check: python3 scripts/raw_colours.py {app}
overrides:
reason:
superseded_by:
supersedes:
exceptions:
  - app: acme-legacy
    note: Keeps raw colours until the rebuild in Q3
    decision: D-004
history:
  - 2026-11-22 · active · D-003
  - 2026-11-22 · exception acme-legacy · D-004
---

Only DS tokens in app CSS: no hex, rgb() or named colours.

Why: raw colours do not follow brand, mode or the next DS version.
```

The body is in the project language: the first paragraph is the rule, then the reason. `rules.py list` prints the first paragraph; `show` prints everything.

Front matter format (read with the Python standard library, no YAML package):

- `key: value` on one line; quotes are optional and removed.
- `[a, b]` is a list.
- A key with nothing after the colon takes the indented `- item` lines below it: strings, or maps that start with `- key: value` and continue with more `key: value` lines indented further.
- Lines that start with `#` are comments. Files named `README.md` or starting with `_` are not rules.

| Field | Required | Values |
|---|---|---|
| `id` | yes | category prefix, hyphen, number: `STY-001` (number range per layer, see above) |
| `title` | yes | short name |
| `category` | yes | one of the categories below, or one declared in `kit.config.json > rules.categories` |
| `layer` | yes | `kit`, `ds`, `project`, `app` (must match the folder) |
| `applies_to` | `app` layer | app ids from `kit.config.json > apps`; empty = every app |
| `skills` | no | skills that must load the rule; empty = every skill |
| `severity` | yes | `must` (a failure blocks), `should` (a person judges), `note` |
| `status` | yes | `proposed`, `active`, `deprecated`, `superseded` |
| `since` | yes | date `YYYY-MM-DD`; `Unconfirmed` only while `proposed` |
| `decision` | active project and app rules, when the project keeps a decision log | decision id (`D-003`) of `context`; must be approved, implemented or verified for an active rule; `Unconfirmed` only while proposed |
| `check` | no | shell command run in the project root; exit 0 = followed. `{app}`, `{path}` (app folder), `{root}` are replaced; with `{app}` or `{path}` it runs once per app in scope |
| `overrides`, `reason` | together | id of an earlier-layer rule this one replaces, and why |
| `superseded_by`, `supersedes` | set by `supersede` | successor and predecessor |
| `exceptions` | no | `- app:` / `note:` / `decision:` (optional) |
| `history` | set by the script | one line per change: date · what · decision |

### Categories

| Category | Prefix | Category | Prefix |
|---|---|---|---|
| `styling` | `STY` | `data` | `DAT` |
| `theming` | `THM` | `handoff` | `HND` |
| `density` | `DEN` | `figma` | `FIG` |
| `layout` | `LAY` | `email` | `EML` |
| `content` | `CNT` | `security` | `SEC` |
| `a11y` | `A11Y` | `process` | `PRC` |
| `pages` | `PAG` | `assets` | `AST` |
| `flags` | `FLG` | `build` | `BLD` |

A project adds its own in `kit.config.json > rules.categories`, for example `{"motion": "MOT"}`.

### Status

| Status | Means | In force |
|---|---|---|
| `proposed` | written, not decided (an imported draft, or a rule whose decision is still proposed) | no |
| `active` | in force | yes |
| `deprecated` | retired, no successor (`deprecate --reason`) | no |
| `superseded` | replaced by another rule (`supersede --by`) | no |

## Commands

| Command | Does |
|---|---|
| `list [--app A] [--skill S] [--category C] [--severity must] [--status active\|all] [--layer L] [--brief\|--full] [--json]` | Rules in force with layers, overrides and exceptions resolved. Lines `EXCEPTION` and `OVERRIDDEN` say what does not apply to the app and why. |
| `show <id> [--app A]` (alias `explain`) | Plain explanation in the project language: severity, category, layer, status and date, where it applies, the state for one app, the decision (title, status, who decided), overrides, successor, automated check, text, exceptions, history. |
| `add --title … --category … --severity … [--layer project\|app\|ds] [--applies-to a,b] [--skills …] [--decision D-003] [--status proposed\|active] [--check "cmd"] [--overrides ID --reason …] [--exception "app=note=D-004"]… [--body …\|--body-file f]` | Writes the next id in the layer's range, validates every field (unknown app, skill, category, decision; a decision not approved keeps the rule proposed) and records the first history line. |
| `except <id> --app A --note … [--decision D-004]` | Adds an app exception to a project or DS rule. |
| `deprecate <id> --reason … [--decision …]` | Retires a rule. |
| `supersede <old> --by <new> [--decision …]` | Marks the old rule superseded and links both. Reminds you to move exceptions that still hold. |
| `check [--app A] [--skill S] [--category C] [--id ID] [--json <file>\|-]` | Runs the `check` commands of the active rules in scope; exit 1 when a `must` rule fails. |
| `coverage [--json]` | Must and should rules with and without an automated check, per category and per app. |
| `conflicts` | Format errors; two overrides of one rule for the same app; overrides from the same or an earlier layer; exceptions on deprecated or superseded rules; superseded rules without a valid successor; unknown apps, skills, categories or decisions. Exit 1 on error. |
| `export [--format md\|html\|claude] [--app A] [--out f] [--into CLAUDE.md]` | A "Project rules" page grouped by category (Markdown or self-contained HTML), or the compact block for `CLAUDE.md` between `<!-- kit:rules:begin -->` and `<!-- kit:rules:end -->` (replaced in place on every run). |
| `import-md <file> [--layer project\|app] [--category process] [--map "heading words=category"]… [--dry-run]` | Splits an existing rules document into draft rule files: one per top-level bullet or numbered item, category from the heading (a category name in it, or `--map`), status `proposed`, severity `should`, `since` and `decision` `Unconfirmed`, the source section quoted in the body. Writes `<rules>/_import-review.md` listing what to confirm for each draft. It never guesses decisions or dates. |

## How skills use it

| Skill | Reads | Writes |
|---|---|---|
| Every skill that builds, reviews or packages (`define`, `explore`, `prototype`, `annotate`, `mockup`, `wireflow`, `handoff`, `share`, `verify`, `review`, `validate`, `sync`, `contribute`, `document`) | `rules.py list --app <app> --skill <name>` at the start; follows the result. Long rule documents (`rules.md` of a DS profile not split into files yet) are read only when `list` says so. | — |
| `review` | `audit_app.py` runs the checks of the rules for `review`: one row per rule and app (a failing `must` rule = Deviation, others = Note). `--no-rules` skips them. | — |
| `validate` | `validation.py run` runs the checks of the rules for `validate` and puts failures in the report: `must` = Fail, others = Needs a human. `--no-rules` skips them. | — |
| `context` | Decisions | An approved decision that states a rule: offers `rules.py add --decision <id>`. |
| `kickoff` | — | Creates the project rules folder (`paths.rules`) with a README. |
| `brief` | — | Routes "add a rule", "why is this a rule", "which rules apply" requests to `context` (rules registry). |

## Use cases

### Add a new rule with an app exception

The team agreed that status chips use the DS tag, but the legacy app keeps its own chips until it is rebuilt.

```
python3 <kit>/skills/context/scripts/decisions.py add --title "Status chips use the DS tag" --status approved --by "<name>"
python3 <kit>/scripts/rules.py add --title "Status chips use the DS tag" --category content --severity must \
  --decision D-007 --skills prototype,review --check "python3 scripts/chips.py {app}" \
  --exception "acme-legacy=Own chips until the rebuild=D-007" --body "Status chips are DS tags (catalogue: tag).

Why: one pattern for status across apps."
python3 <kit>/scripts/rules.py conflicts
```

`review` and `validate` now run `scripts/chips.py` for every app except `acme-legacy`; `rules.py list --app acme-legacy` prints `EXCEPTION CNT-003 … Own chips until the rebuild [D-007]`.

### Build a screen: load only the relevant rules

`prototype` starts with `rules.py list --app acme-web --skill prototype`. It gets the rules in force for that app and step (for example 12 lines with the rule text), not the rules of `share` or `handoff`, not rules excepted or overridden for this app, and a `NOTE` when the DS profile still keeps its rules in one `rules.md`.

### Supersede a rule

The density rule changes: compact everywhere on phones.

```
python3 <kit>/scripts/rules.py add --title "Phones use compact density" --category density --severity must --decision D-012 --body "…"
python3 <kit>/scripts/rules.py supersede DEN-002 --by DEN-004 --decision D-012
```

`DEN-002` stays in the registry as `superseded` (with the successor in its history), so "why did this change" has an answer. `conflicts` reports exceptions left on the old rule.

### Explain a rule to a BA

`python3 <kit>/scripts/rules.py show STY-001 --app acme-legacy` prints, in the project language, what the rule says and why, how strict it is, where it applies, that it does not apply to `acme-legacy` (with the note), the decision behind it and who approved it, and its history. `export --format html --out docs/rules.html` gives the whole set as one page to share.

### A new project inherits the kit and DS rules

`kickoff` creates `rules/` (empty except a README). From the first session `rules.py list` already returns the kit rules and the rules of the DS profile in `ds/<name>/rules/`. The project adds only its own rules; where it needs something else for one app it adds an app rule with `overrides` and a reason, which `conflicts` validates. `export --format claude --into CLAUDE.md` keeps a short summary in the project's `CLAUDE.md`.

## Migrating an existing rules document

1. `python3 <kit>/scripts/rules.py import-md docs/rules.md --map "colour=styling" --map "handoff=handoff" --dry-run`, then without `--dry-run`.
2. Go through `rules/_import-review.md` with the user: severity, category, date, decision. Merge or delete drafts that are not rules.
3. Set each confirmed rule to `status: active` with `since` and `decision`; `rules.py conflicts` must pass.
4. Keep the old document until every rule is in the registry; then point it at `rules.py export`.

## Compatibility

Projects without a `rules/` folder keep working: `list` returns the kit rules (and DS rules when the profile has a `rules/` folder), the checks run only when a rule has a `check`, and every new key has a default (see [config.md](config.md)).
