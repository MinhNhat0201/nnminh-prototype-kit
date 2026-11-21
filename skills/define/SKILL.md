---
name: define
description: "Analyse stakeholder requirements (PM, BA) and plan how to build them in the prototype: split them into units, find what is vague, missing or contradictory and write questions for PM/BA, map units to screens, flows and the DS catalogue, flag new pages and missing components, then split the work into delivery waves with acceptance criteria and a traceability matrix. Use when the user shares a PRD, user story, ticket, meeting notes or change request, or says 'analyse the requirements', 'plan the prototype', 'impact analysis', 'split into waves', even without naming the skill. Do not build screens (use `prototype`), bring in a new DS version (`sync`) or write a spec with screenshots (`annotate`). Also use for the same request in any language."
---

# Define: requirements to a delivery plan

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.define` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

This skill comes before building. It turns PM/BA input into a plan that the user and stakeholders can approve, then hands each wave to the build skills.
It only plans. It never builds screens and never edits apps or the DS.
Reason: vague requirements, impact on existing screens and missing components are cheap to find here and expensive to find while building.

Read first: `kit.config.json` (load with `python3 <kit>/scripts/kitconf.py`; `<kit>` is the plugin root), the DS profile's `rules.md` and `catalog.md` (`ds.json > rules`, `ds.json > catalog`). No `kit.config.json` → run `kickoff`. No DS profile → run `adopt`.

## Step 0. Clarify the input (one AskUserQuestion round, at most 4 questions)

Ask only for what is missing, all in one round:

1. **Target app:** an entry of `kit.config.json > apps`, or a new app.
2. **Source and owner:** PM or BA; where the document, ticket or notes are; version or date. Several sources → which one wins on conflict.
3. **Goal of the prototype:** who sees the demo, what it must prove (flow, idea, developer handoff). This sets the level of detail.
4. **Constraints:** deadline, waves that must come first, parts that must not change.

Do not proceed without 1 and 2. Running unattended: write assumptions into the plan and put them at the top of the report.

## Step 1. Read input and current state

- Read every requirement document. Open images and attachments with Read. A link you cannot read → say so; never guess its content.
- Existing app: read its screens one at a time (never a large file in one go), `paths.changelog`, `local.registry`, and the DS version label in the app compared with `ds.json > version`.
- Change to an existing plan: read the old plan in `paths.plans` and follow "Update a plan" below.
- Product context (`paths.context`, see `context`): run `python3 <kit>/skills/context/scripts/context.py summary`, then read the overview, personas, business rules and constraints, and the approved decisions in scope. A business rule there wins over your reading of the PRD; a conflict between the PRD and a rule is a BLOCKING question. No context folder → work without it and suggest `context` once.
- Business decisions you propose (a reading of a vague rule, a default) go into the plan and into the decision log as `proposed` (`decisions.py add --status proposed`), never as agreed.

## Step 2. Split into units

- One unit = one idea that can be checked. Keep the PM/BA's codes (US-12, FR-03). None → number R01, R02… in order of appearance and say they are temporary.
- Each unit: code, text **verbatim**, source (document, section, person), type.
- Types: **functional**, **business rule**, **UI/UX**, **data**, **non-functional** (performance, security, real permissions), **outside the prototype** (backend, real integrations, real auth, real data; mock or skip).
- Never merge, split or reword units. Your reading goes in a separate column "Read as", never inside the verbatim text.

## Step 3. Quality check and questions for PM/BA

Check every unit for:

| Problem | Signs |
|---|---|
| Vague | Words you cannot measure ("fast", "friendly", "like screen X"); unclear actor or condition |
| Missing | No empty / error / loading state, role permissions, data limits, cancel behaviour, messages; a flow with a start and no end |
| Contradiction | Between two units, unit vs existing prototype, unit vs DS (asks for a style no token gives), two sources |
| Hidden assumption | Something you would have to guess to build it |

Question table: `ID | linked unit | question (specific, answerable in one sentence) | to (PM/BA) | level | temporary assumption | fallback if the assumption is wrong`.

| Level | Meaning |
|---|---|
| BLOCKING | Without an answer that part cannot be built correctly; its wave cannot start |
| NON-BLOCKING | A safe temporary assumption exists; build on it and record it so it is easy to change |

Business decisions belong to PM/BA. Never pick one reading and treat it as agreed. Propose, and mark it "proposal, awaiting confirmation".

## Step 4. Map to the prototype

No app yet: propose screens and flows from scratch. Existing app: for each unit, record:

- **Screens:** new / change / keep / remove. Codes S01…; reuse the app's codes if it has them.
- **Flows:** main flow, side flows, error and cancel branches, with start and end points. This feeds the wireflow later (`annotate`, `wireflow`). Draw nothing now.
- **New page?** For each new screen decide whether it is a **new page** or part of an existing one.
  - New page: a destination with its own entry point (nav item, tab, button elsewhere), its own flow and states, and possibly its own address.
  - Not a new page: dialog, drawer, popover; a tab or step inside an existing page; an empty or error state; a layout change.
  - In doubt → treat it as a new page.
  - List each new page under "New pages" in the plan: name, entry point, proposed file or route (see the stack table below), current app shape, cost, recommendation (A own file or route / B inside the current file / C inside the current file now, split later). Propose only. Never create files or routes.
- **Side effects:** existing screens or components affected, mock data to add or change, navigation to change.
- **Mock:** what is only simulated. Say so clearly so BA and QC do not mistake it for real behaviour.

| Stack (`kit.config.json > stack`) | New page means |
|---|---|
| `html`, app `single` | A new file `apps/<app>/<slug>/index.html` needs the shared shell extracted first (header, nav, CSS, scripts) or copied (drifts). Large cost; propose it as its own plan. |
| `html`, app `multi` | One more page file in the existing shell, plus its entry in the app's route table and the app's `build` command. Low cost. |
| `react`, `vue` (`spa`) | One route plus one page component. Low cost. |

## Step 5. Map to the DS catalogue

Table: `element needed | expected DS component (from catalog.md) | match level`. The source is `catalog.md` and the DS CSS, never memory.

| Match level | Meaning |
|---|---|
| Available | The DS has it; use it as is |
| Close | Compose it from existing components and variants |
| Tokens only | The DS has tokens for it but no component or CSS |
| Missing | Nothing in the DS |

- **Tokens only** and **Missing:** add them to "Decide before building" with the options below and a recommendation. Do not decide and do not build. The formal gate is in `prototype`; this step only warns early so the user knows the workload.

| Option | Meaning |
|---|---|
| A | Compose from existing DS components (no new component) |
| B | Local component for this app only: class prefix `local.prefix`, tokens only, in a `/* <local.marker>: <name> */` block, registered with `contribute` |
| C | B, plus a proposal to add it to the DS |

- App on an older DS version than the profile → first task of wave 0 is `sync`.
- Component the user chose to add to the DS (option C accepted into the DS) → `document` is a prerequisite of the wave that needs it.

## Step 6. Delivery waves

Split into small waves. Each wave ships a working prototype (a vertical slice through one flow). Never "wave 1 all frames, wave 2 all content".

- **Wave 0 (if needed):** preparation: `sync` for an outdated app, `document` for components accepted into the DS, extracting the shared shell of a `single` app (only if the user chose A for a new page), cleaning mock data.
- **Each wave:** name and goal; units (R-ids) and screens (S-ids); dependencies (earlier waves, BLOCKING questions that must be answered); tasks by skill in order (table below); **acceptance criteria** that can be checked (for example "go from S01 to S04 by doing X; message Y shows when Z is empty"); tests (the standard tests of `prototype` plus wave-specific cases); risks; size S / M / L (rough, relative between waves; never hours without evidence).
- **Order:** PM/BA priority if given (Must / Should / Could). Otherwise propose by value and dependency and say it is a proposal. Main flow before error branches. Waves with unanswered BLOCKING questions go last or are marked "waiting".

| Task | Skill |
|---|---|
| Bring the app to the current DS version | `sync` |
| Add or change a DS component or token | `document` |
| Build screens and flows, add screens to an app | `prototype` |
| Spec with screenshots, flows | `annotate` |
| Flow board on Figma | `wireflow` |
| Handoff package for BA, QC, developers | `handoff` |

- End each wave with a stakeholder review (demo) before the next one, unless the user says to run straight on.

## Step 7. Traceability matrix

Table: `R-id | summary | type | screens (S-id) | wave | status (not started / waiting for answer / built / outside prototype) | related questions`.
- Every unit appears exactly once.
- "Outside the prototype" units have a reason and a handling (mock or skip).
- Screens linked to no unit are listed separately. Never hide them.

## Step 8. Write the plan

- One Markdown file: `<paths.plans>/<app>-<short-name>-<yyyy-mm-dd>.md`, from `assets/plan-template.md`. Write headings and labels in the project language.
- The plan is for PM/BA to review: ask the user whether they want a shareable version. Never publish or send without consent. Keep internal design-team notes out of anything sent to stakeholders.
- Save the file and record it in `paths.changelog` if the project logs plans. Open a PR only if the user asks.

## Step 9. Confirm before building

Present, in this order: BLOCKING questions; **new pages** (A/B/C needed before building); component decisions; the wave you propose to start with. Ask the user to approve or adjust.
Mark each wave that has a real design question (structure, navigation, main interaction, information order) and suggest `explore` for it before `prototype`.
Move on only when the user says to start a specific wave: to `explore` for a marked wave if the user agrees, otherwise to `prototype`. Pass the wave's R-ids, S-ids, assumptions, page decisions and component decisions.

## Update a plan (requirements changed)

- Read the old plan and the new source. Diff table: units **added / changed / removed**, matched by code, old and new verbatim side by side.
- Impact: waves affected, built screens to change, tests to rerun, answers that no longer hold.
- Bump the plan version (v1 → v2) and add "Changes from the previous version" at the top. Never delete old units; mark them "removed" with reason and source.

## Final report (short)

Plan path; units by type; questions (BLOCKING / NON-BLOCKING); elements per match level and pending component decisions; new pages awaiting A/B/C; number of waves and the one to start; assumptions used; parts outside the prototype; warnings (outdated DS version, conflicting sources).

## Rules

- Never build UI and never edit apps or the DS profile. Build only after the plan is approved.
- Keep PM/BA text verbatim; your interpretation is separate and marked.
- Never invent requirements, business rules, numbers, effort estimates or stakeholder feedback. Unsure → a question, never a hidden assumption.
- Never decide for PM/BA. Propose and say it is a proposal.
- Never decide new components; leave that to the gate in `prototype`.
- Never create page files, folders or routes. Announce proposed pages; record the user's choice in the plan for the gate in `prototype`.
