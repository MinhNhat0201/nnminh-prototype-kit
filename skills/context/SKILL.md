---
name: context
description: "Set up and maintain the product context the other skills read before they plan, explore or build: product overview, personas, UX principles, business rules, constraints, and a decision log where every design or product decision has a status (observed, proposed, approved, implemented, verified, rejected, superseded) and names who decided. Use when the user says 'set up product context', 'remember this decision', 'why did we decide X', 'what did we agree', 'record that the team approved…', when a project has no product-context folder yet, or when another skill needs product facts it cannot find. Do not use to analyse a PRD into waves (`define`), to compare design directions (`explore`) or to document the DS (`document`). Also use for the same request in any language."
---

# Context: product memory and decisions

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.context` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

`<kit>` below means the kit root: two folders above this skill's base directory (`${CLAUDE_PLUGIN_ROOT}` when the kit is installed as a plugin).

Scripts: `C=<kit>/skills/context/scripts/context.py`, `D=<kit>/skills/context/scripts/decisions.py` (`--help` lists every command). Folder: `<paths.context>/` (default `product-context`).

Goal: the kit knows the product across sessions, and every decision says who made it and why.
Reason: without memory every session relearns the product; without a status, a suggestion slowly turns into "what we agreed".

## The folder

| File | Holds |
|---|---|
| `product-overview.md` | What the product is, for whom, main jobs, what success looks like, sources |
| `personas.md` | People the team has evidence for |
| `ux-principles.md` | Agreed principles: short, testable, with a reason |
| `business-rules.md` | Rules the design must not break, quoted from their source |
| `constraints.md` | Technical, legal, brand and out-of-scope limits |
| `decisions/D-001-<slug>.md` | One decision each; `decisions/index.md` lists them |

## Decision status

| Status | Means | Who sets it |
|---|---|---|
| `observed` | Seen in the product or an existing app; nobody decided it here | Agent, with `--source` |
| `proposed` | Suggested, waiting for a human | Agent or designer |
| `approved` | A named person said yes | Human (`--by` required) |
| `implemented` | Built in a prototype | Agent, after `prototype` |
| `verified` | Checked in the developer build | Agent, after `verify` |
| `rejected` | A named person said no | Human (`--by` required) |
| `superseded` | Replaced by a newer decision | `add --supersedes <id>` |

The script refuses moves the lifecycle does not allow (for example proposed → implemented).

## Set up

1. Load `kit.config.json`. Missing → `kickoff`.
2. `python3 $C init`. It never overwrites existing files.
3. Fill the files from, in this order: what the user tells you; documents they give (PRD, research, analytics summaries); the existing apps and plans in the project. Ask at most 4 questions in one AskUserQuestion round, for the gaps that matter most (users, main jobs, business rules).
4. Anything you inferred and nobody confirmed: write it as inferred, with its source (`(observed: apps/acme-web, Settings)`), and record product or design choices you found as `observed` decisions. Never present an inference as agreed.
5. Remove each `<!-- fill: … -->` prompt once its part is written. `python3 $C check`: no missing file, no invalid decision; remaining prompts are warnings.

## Record and update decisions

- New decision: `python3 $D add --title "..." --status proposed --scope <S-ids, R-ids, app> --context "..." --decision "..." --alternatives "..." [--source "..."]`.
- The user approves or rejects: `python3 $D set <id> approved|rejected --by "<name>" --note "<their reason>"`. Use the person's name as they gave it; never put "team" or your own name.
- A decision changes: add the new one with `--supersedes <old id>`. Never edit an approved decision's meaning in place.
- `python3 $D list --status approved`, `python3 $D show <id>`, `python3 $D check`.

## How other skills use it

| Skill | Reads | Writes |
|---|---|---|
| `define` | All files before analysis; business rules win over guesses | Business decisions it proposes, as `proposed` |
| `explore` | Overview, personas, principles, constraints | The user's choice, as `approved` (automatic in `choose`) |
| `prototype` | Principles, rules, constraints; `approved` decisions in scope | After building: approved decisions in scope → `implemented` |
| `handoff` | Decisions in scope | Lists them in the package so developers see the why |
| `verify` | Decisions in scope | Checked decisions → `verified`; approved deviations are not errors |

Start of any of these skills: `python3 $C summary` gives the short digest. No folder → the skill works without it and suggests `context` once.

## Rules

- Never invent users, quotes, numbers, rules or decisions. Unknown → a question or an `observed` note with its source.
- Never mark a decision `approved` or `rejected` without a named person who said so in this conversation or in a document you can cite.
- Never delete a decision; supersede or reject it.
- Keep business rules verbatim; your reading of a rule goes into a decision's context, not into the rule.
- No personal data about real users in these files; personas describe roles, not people.
