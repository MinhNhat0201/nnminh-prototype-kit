# Prototype delivery plan: <short name>

<!-- Write this plan in the project language (kit.config.json > language). Translate headings and labels. -->

| | |
|---|---|
| Target app | apps/<app> (DS in app: <label> x.y.z; current DS profile: x.y.z) |
| Plan version | v1 |
| Date | yyyy-mm-dd |
| Requirement source | <document, section, person, date> |
| Author | <name> |
| Prototype goal | <demo for whom, what it must prove> |

## Changes from the previous version
<From v2 only: table of added / changed / removed units, old and new verbatim, impact.>

## 1. Summary
<5 lines: main requirements, number of waves, first wave, biggest BLOCKING question, decisions needed from the user.>

## 2. Requirement units
| Code | Verbatim | Source | Type | Read as (interpretation, marked) |
|---|---|---|---|---|

## 3. Questions for PM/BA
| ID | Linked unit | Question | To | Level | Temporary assumption | If the assumption is wrong |
|---|---|---|---|---|---|---|

## 4. Impact on the prototype
### Screens
| Screen | Name | New / Change / Keep / Remove | Related units | Notes |
|---|---|---|---|---|
### Flows
| Flow | Start | Main steps | Error / cancel branches | End |
|---|---|---|---|---|
### New pages (proposal: own file or route)
| Page | Entry point | Proposal (file or route, address) | Current app shape (single / multi / spa) | Cost | Recommendation (A/B/C) | User's decision |
|---|---|---|---|---|---|---|
<Proposal only; nothing created yet. No new page → write "None".>

### Mock data and side effects
<List; mark clearly what is only simulated.>

## 5. DS catalogue mapping
| Element needed | Expected DS component | Match level (Available / Close / Tokens only / Missing) |
|---|---|---|
### Decide before building
<"Tokens only" and "Missing" elements: options A/B/C and recommendation.>

## 6. Waves
### Wave 0: preparation (if needed)
### Wave 1: <name>
- Goal:
- Units / screens:
- Dependencies:
- Tasks by skill:
- Acceptance criteria:
- Tests:
- Risks:
- Size: S / M / L

## 6b. Parity checklist (porting an existing page only)
<From `extract_rules.py`, completed. Old page: <file>; new page: <file or route>. Delete this section when the source is not a running page.>
| ID | Kind | Text or value (verbatim) | Source (file:line) | Rule | Unit | Old page | New page |
|---|---|---|---|---|---|---|---|

## 7. Traceability matrix
| R-id | Summary | Type | Screens | Wave | Status | Questions |
|---|---|---|---|---|---|---|

## 8. Outside the prototype
| R-id | Reason | Handling (mock / skip) |
|---|---|---|

## 9. Shared assumptions and risks
