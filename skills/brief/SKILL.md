---
name: brief
description: "Entry point of the kit: the designer says in plain words what they want, and this skill finds out which job it is and hands it to the right skill with a one-line plan. Use when the request is open or unclear ('help me with this feature', 'where do I start', 'I have a PRD and some screenshots', 'what can this kit do'), or when the user calls the kit without naming a skill. Do not use when the request clearly matches one skill: go straight to that skill. Also use for the same request in any language."
---

# Brief: find the job, route to a skill

Reply in the project language (`kit.config.json > language`; no config yet → the user's language). Generated documents use the same language.
Model and effort: `kit.config.json > skills.brief` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

## Steps

1. **Check setup.** Look for `kit.config.json` (walk up from the current folder, or `python3 <kit>/scripts/kitconf.py check`; `<kit>` is the plugin root).
   - Not found → route to `kickoff`.
   - Found, but `ds` missing or `ds.json` not found → route to `adopt` (or `kickoff` if the user has a DS profile somewhere to link).
2. **Read the request** and any files the user attached. Match it to the table below.
3. **Ask only if needed:** at most 1–2 questions in one AskUserQuestion round, only when two skills fit equally or a required input is missing (target app, source document). Never ask what the config already says.
4. **State a one-line plan**, for example: "`define` on the PRD for `acme-web`, then `prototype` for wave 1." Then invoke the first skill and pass it what you learned (app, files, goal). The skill has a model or effort hint (`python3 <kit>/scripts/kitconf.py skills`)? Name it in the plan, and start a sub-agent with that model and effort when you hand the work over.

## Routing

| Skill | Job | Typical phrases |
|---|---|---|
| `kickoff` | Set up the project: config, DS link, stack, first app | "start a new project", "set up the kit" |
| `adopt` | No DS yet: base DS profile from a public preset | "we have no design system", "start from shadcn", "use atelier" |
| `define` | Requirements → questions, plan, waves, traceability | "here is the PRD", "plan this feature", "impact of this change" |
| `context` | Product memory: overview, personas, principles, decision log, and the rules registry (`rules.py`: add, explain, supersede, except, export, import a rules document) | "remember this decision", "why did we decide X", "set up product context", "add a rule", "why is this a rule", "which rules apply to app X", "turn our rules doc into rule files" |
| `explore` | 2–4 design directions with the DS, compare, human chooses | "show me options", "explore directions", "what are the ways to design this" |
| `prototype` | Build screens and flows with the DS | "build this screen", "make it like this image", "add a page" |
| `validate` | Browser checks of a prototype: errors, overflow, accessibility, focus, states, flows, visual changes; one report | "test the prototype", "QA this", "is it ready for handoff" |
| `annotate` | Markdown spec per unit with screenshots, pins, tokens, flows | "write the spec", "annotate the screens" |
| `wireflow` | Flow board of screen images on Figma | "put the flow on Figma", "wireflow" |
| `mockup` | Rebuild screens on Figma with auto layout and DS components | "rebuild in Figma", "Figma specs" |
| `handoff` | One zip for BA, QC, developers | "package it", "handoff for PBI 1234" |
| `share` | Draft the handoff email (never sends) | "write the handoff email" |
| `verify` | Compare a developer build with the approved prototype; differences become defects or approved deviations | "check the implementation", "design QA", "compare the build with the design" |
| `review` | Read-only audit of an app against the DS, or a critique of one screen or flow | "audit", "how far are we from the DS", "review this screen", "does this look right" |
| `sync` | Bring a new DS version into apps | "update to the new DS version" |
| `contribute` | Review local components, propose them to the DS | "which local components can go into the DS" |
| `document` | Write and maintain DS docs and tokens | "document this component", "change a token" |
| `brief` | This skill | "where do I start" |

## Common chains

| Situation | Chain |
|---|---|
| New feature from a PRD | `define` → `explore` (waves with a design question) → `prototype` (per wave) → `validate` → `annotate` → `wireflow` / `mockup` → `handoff` → `share` → (after development) `verify` |
| Quick mock from a screenshot | `prototype` |
| Open design question ("how should this work?") | `explore` → `prototype` |
| DS released a new version | `review` → `sync` |
| Many local components | `contribute` → `document` → `sync` |
| A new rule the team agreed | `context`: decision (approved, named person) → `rules.py add --decision` → `rules.py conflicts` |

## Rules

- Route; do not do the work here.
- Never skip setup: no config → `kickoff` first.
- Never guess the target app or source document; ask.
