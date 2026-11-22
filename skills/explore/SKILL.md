---
name: explore
description: "Explore two to four meaningfully different design directions for one design question before building, all with the project's DS: a light HTML page per direction, a comparison page (side by side, phone/tablet/desktop), strengths, weaknesses, risks and DS fit for each, then a human decision that names the canonical direction and the reason. The chosen page becomes the input of `prototype`. Use when the user says 'show me options', 'explore directions', 'what are the ways to design this', 'compare layouts', when a plan wave has an open design question, or when a request could reasonably be designed in very different ways. Do not use to build the final screens (`prototype`), to plan from a PRD (`define`) or for visual styling outside the DS. Also use for the same request in any language."
---

# Explore: directions before decisions

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.explore` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

Rules: run `python3 <kit>/scripts/rules.py list --app <app> --skill explore` (no app: leave out `--app`) and follow what it prints: `must` rules are never broken, a `should` rule is broken only with the reason in the report, `EXCEPTION` and `OVERRIDDEN` lines say what does not apply to this app. It replaces reading long rule documents; read the DS `rules.md` only when the output says the profile keeps its rules there. `rules.py show <id>` explains one rule ([docs/rules.md](../../docs/rules.md)).

Script: `E=<kit>/skills/explore/scripts/explore.py` (`--help` lists every command). Folder: `<paths.explorations>/<slug>/` (default `docs/explorations`).

Goal: the user chooses how the product should work before anyone builds it.
Reason: an agent that builds the first idea turns a guess into a design decision. The human decides; the kit shows the options and records the choice.

## When to explore

| Situation | Do |
|---|---|
| A wave or request has a real design question (structure, navigation, main interaction, information order) | Explore |
| The request copies a reference closely, or adds a screen to an established pattern | Skip; go to `prototype` |
| The user asks for options | Explore |
| Unsure | Ask once: "explore 2–3 directions first, or build straight away?" |

## Step 1. Frame the question

- Load `kit.config.json` (`python3 <kit>/scripts/kitconf.py`). Missing → `kickoff`. No DS profile → `adopt`.
- Read the DS profile (`ds.json`, `catalog.md`), the rules (above) and the input: the `define` plan wave (R-ids, S-ids, assumptions) or the written request. Product context (`paths.context`, see `context`): `python3 <kit>/skills/context/scripts/context.py summary`, then read the overview, personas, UX principles, business rules and constraints. Every direction must respect the business rules and approved decisions; a direction that would change an approved decision says so in `risks`.
- Write the design question in one sentence ("How should a team see and triage today's tasks?").
- `python3 $E init <slug> --title "..." --question "..." --directions 3 --app <app>`. Slug: lowercase, hyphens.
- Fill `brief.md`: what must stay true (requirements, business rules, DS rules), what may vary, how the user will judge, what is out of scope.

## Step 2. Pick directions that really differ

- Two to four directions (default three). They differ in **structure, navigation, main interaction or information order**, never only in colour, spacing or copy.
- Each direction answers the same question with the same requirements. A direction that drops a requirement is not a direction; say so instead.
- Prefer one direction that composes existing DS components only, so there is always a cheap option.
- Name each direction by its idea ("Grouped list", "Board", "Focus mode"), not "Option 1".

## Step 3. Build each direction page

Each `a/index.html`, `b/index.html`… already embeds the DS CSS, theming defaults and version label. Build inside `<main>`:
- DS classes and tokens only (`catalog.md`, `rules.md`). No raw colours, no CSS over DS components, no new components. A direction that needs something the DS lacks lists it under `dsFit.missing`; it is decided later in the `prototype` gate.
- Enough to judge the idea: the main screen and the one interaction that defines the direction. Mock data marked as mock. No routing, no full flows, no polish.
- These are always plain HTML, whatever the app stack: they are for deciding, not for shipping.

Fill `directions.json` for every direction: `name`, `summary` (one sentence), `bestFor`, `pros`, `cons`, `risks` (open questions included), `dsFit.available` / `dsFit.missing` (component names from `catalog.md`), `effort` (`S` / `M` / `L`, relative). Be honest: every direction has weaknesses.

## Step 4. Check and compare

- `python3 $E check <slug>` must print `Exploration OK`. It checks pages, DS markers, version meta, raw colours and the description fields.
- `python3 $E compare <slug>` writes `compare.html`: directions side by side or one at a time, in a phone, tablet or desktop frame, with the description under each.
- Open `compare.html` with Playwright (installed Chromium; never `playwright install`): no `pageerror`, every frame loads. Look at one screenshot per viewport.

- Comparing directions on experience: score each one along the same flow with `<kit>/skills/review/references/heuristics-rubric.md` and put the result into its `pros`, `cons` and `risks`.

## Step 5. Decision gate (mandatory)

Present the directions and ask the user to choose (AskUserQuestion, one round): one option per direction with its one-line summary and main trade-off, plus "combine" and "none of these". Give your recommendation and why, marked as a recommendation.

- **Never choose for the user.** Unattended: stop here, report the comparison and the recommendation, and do not start `prototype`.
- Combine: record the base direction and each part kept from another as `--merge "<id>: <part>"`.
- None fits: ask what is missing; write new directions in the same exploration (keep the rejected ones and their reasons).

Record the answer: `python3 $E choose <slug> <id> --reason "<the user's reason, in their words>" --by "<name>" [--merge ...]`. It sets statuses, writes `decision.md` and refreshes `compare.html`. When the project keeps a decision log, it also records the choice as an `approved` decision (rejected directions under alternatives); `--by` is then required.

## Step 6. Hand over to `prototype`

Pass `prototype`: the chosen page (`<slug>/<id>/index.html`), `decision.md` (reason and merged parts), `brief.md` and the plan wave. The chosen direction is the layout and behaviour reference; `prototype` still runs its component and new-page gates.

Report: exploration path, the question, directions with one line each, the decision and reason, parts merged, DS gaps found (`dsFit.missing`), next step.

## Rules

- Never build the final screens here, and never edit an app or the DS profile.
- Never start `prototype` from an exploration without a recorded decision.
- Never present a direction as chosen, approved or "recommended by the team" unless the user said so.
- Never delete rejected directions; their reasons are part of the record.
- Never copy visual style from reference images; directions differ in structure and behaviour, not style.
