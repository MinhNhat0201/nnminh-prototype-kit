# Screen review rubric (heuristics and cognitive load)

Drawn from `critique-rubric` of the impeccable skill (Apache-2.0), based on Nielsen's ten usability heuristics, rewritten for prototypes built with a DS.
Read it when the user asks to "review this screen" or "give feedback on this flow", and in `explore` when comparing directions; use it with `validate` [a11y-web.md](../../validate/references/a11y-web.md) (and [a11y-mobile.md](../../validate/references/a11y-mobile.md), `prototype` [states-and-edge-data.md](../../prototype/references/states-and-edge-data.md)).
This rubric scores **experience**, not style: colour, font, radius and spacing follow the DS and Figma; a difference there is written "deviates from the DS" or "deviates from Figma".

## 1. Ten heuristics, each scored 0–4
Scale: **4** no problem · **3** minor, does not get in the way · **2** slows down or confuses, can be worked around · **1** many people will get stuck · **0** blocks the task or loses data.
Score along the main flow of the screen (name the flow). Every score under 4 has at least one finding with a concrete situation.

| # | Heuristic | Ask | Common signs in prototypes |
|---|---|---|---|
| H1 | Visibility of system status | Do people know what is happening, whether it is done, how long it takes? | A long AI task with no progress; a save with no feedback |
| H2 | Match with the real world | Do words and order follow how users speak and work, not how the system stores data? | Technical words (prompt, token, payload) in front of business users |
| H3 | User control and freedom | Is there Undo, Cancel, Back; does leaving halfway lose data? | A dialog with no Cancel; no edit after create; delete with no undo |
| H4 | Consistency and standards | Same task, same name, same place, same DS component on every screen? | Two buttons for one task with different names across versions; a ⋮ menu in a different order |
| H5 | Error prevention | Does the design prevent mistakes before it has to report them? | Create allowed while data is missing; a number field that accepts letters |
| H6 | Recognition rather than recall | Are choices, context and earlier values visible? | Users must remember a template name or an id; filters lost on Back |
| H7 | Flexibility and efficiency | Do experienced users have shortcuts (keys, bulk actions) without confusing new users? | No Enter to send; no multi-select to delete |
| H8 | Minimal, focused design | Does everything on the screen serve the main task? | Many buttons of equal weight; secondary information inside the main flow |
| H9 | Help users recognise and recover from errors | Do errors say the problem in plain words, show the fix, keep what was typed? | "Something went wrong" with no way forward; an error that clears the form |
| H10 | Help and documentation | Do hard places have a hint in place, at the right moment? | A new feature with no explaining empty state; a tooltip that repeats the label |

The total of 40 is only for comparing two reviews of the **same screen**; never compare screens, never use it instead of the findings.
When comparing directions in `explore`, score each direction along the same flow and put the scores and the main findings into each direction's `pros`, `cons` and `risks`; the decision stays with the user.

## 2. Cognitive load
- **Choices at once:** ≤ 4 is easy; 5–7 should be grouped or revealed step by step; 8+ is overload (people skip or mis-tap).
- **Eight common problems:** (1) a wall of equal-weight choices; (2) information to remember from an earlier screen; (3) hidden navigation (shown only on hover); (4) internal jargon; (5) visual noise (many labels, borders and accent colours at once); (6) two interaction styles for one task; (7) several tasks at once on one screen; (8) context switching (leave the screen to fetch information, then come back).
- Tie each problem you record to its heuristic (usually H6, H8, H4).

## 3. Review report
1. Scope: screens, flow, viewport widths seen, light or dark.
2. Score table H1–H10 (one line of reason for each score under 4).
3. Findings as **Must fix / Should fix / Nice to have**, numbered in one sequence, each in four parts (What it is · Problem · Fix with DS components · If ignored) with its code (H#, W-, M-, S-, D-, C-).
4. What works well (one or two lines, so nobody removes it by mistake).
5. Not seen: flows, states, widths not tried.
