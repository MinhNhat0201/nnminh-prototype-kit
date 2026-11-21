---
name: brief
description: "Entry point of the kit: the designer says in plain words what they want, and this skill finds out which job it is and hands it to the right skill with a one-line plan. Use when the request is open or unclear ('help me with this feature', 'where do I start', 'I have a PRD and some screenshots', 'what can this kit do'), or when the user calls the kit without naming a skill. Do not use when the request clearly matches one skill: go straight to that skill. Also use for the same request in any language."
---

# Brief: find the job, route to a skill

Reply in the project language (`kit.config.json > language`; no config yet → the user's language). Generated documents use the same language.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

## Steps

1. **Check setup.** Look for `kit.config.json` (walk up from the current folder, or `python3 <kit>/scripts/kitconf.py check`; `<kit>` is the plugin root).
   - Not found → route to `kickoff`.
   - Found, but `ds` missing or `ds.json` not found → route to `adopt` (or `kickoff` if the user has a DS profile somewhere to link).
2. **Read the request** and any files the user attached. Match it to the table below.
3. **Ask only if needed:** at most 1–2 questions in one AskUserQuestion round, only when two skills fit equally or a required input is missing (target app, source document). Never ask what the config already says.
4. **State a one-line plan**, for example: "`define` on the PRD for `acme-web`, then `prototype` for wave 1." Then invoke the first skill and pass it what you learned (app, files, goal).

## Routing

| Skill | Job | Typical phrases |
|---|---|---|
| `kickoff` | Set up the project: config, DS link, stack, first app | "start a new project", "set up the kit" |
| `adopt` | No DS yet: base DS profile from a public preset | "we have no design system", "start from shadcn" |
| `define` | Requirements → questions, plan, waves, traceability | "here is the PRD", "plan this feature", "impact of this change" |
| `explore` | 2–4 design directions with the DS, compare, human chooses | "show me options", "explore directions", "what are the ways to design this" |
| `prototype` | Build screens and flows with the DS | "build this screen", "make it like this image", "add a page" |
| `annotate` | Markdown spec per unit with screenshots, pins, tokens, flows | "write the spec", "annotate the screens" |
| `wireflow` | Flow board of screen images on Figma | "put the flow on Figma", "wireflow" |
| `mockup` | Rebuild screens on Figma with auto layout and DS components | "rebuild in Figma", "Figma specs" |
| `handoff` | One zip for BA, QC, developers | "package it", "handoff for PBI 1234" |
| `share` | Draft the handoff email (never sends) | "write the handoff email" |
| `review` | Read-only audit of an app against the DS | "audit", "how far are we from the DS" |
| `sync` | Bring a new DS version into apps | "update to the new DS version" |
| `contribute` | Review local components, propose them to the DS | "which local components can go into the DS" |
| `document` | Write and maintain DS docs and tokens | "document this component", "change a token" |
| `brief` | This skill | "where do I start" |

## Common chains

| Situation | Chain |
|---|---|
| New feature from a PRD | `define` → `explore` (waves with a design question) → `prototype` (per wave) → `annotate` → `wireflow` / `mockup` → `handoff` → `share` |
| Quick mock from a screenshot | `prototype` |
| Open design question ("how should this work?") | `explore` → `prototype` |
| DS released a new version | `review` → `sync` |
| Many local components | `contribute` → `document` → `sync` |

## Rules

- Route; do not do the work here.
- Never skip setup: no config → `kickoff` first.
- Never guess the target app or source document; ask.
