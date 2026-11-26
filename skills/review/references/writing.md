# Writing review findings (audit and critique)

Read it before you write a `review` report, in both modes.

## Voice

- Plain designer voice. Short sentences, one idea each.
- Name the element, not an idea: "the Save button in the dialog footer", not "the primary action affordance".
- Say what happens to a person: "a user who presses Esc loses the text they typed".
- No praise padding, no chains of hedges, no emoji, no exclamation marks.
- Write in the project language (`kit.config.json > language`).

### Words to drop

They sound like a generated report and say nothing. Replace them with the concrete fact.

| Language | Drop |
|---|---|
| English | leverage, robust, seamless, streamlined, intuitive (without a test), elevate, enhance, empower, holistic, comprehensive, cutting-edge, best-in-class, user-friendly, delve, utilize, effectively, overall, it's worth noting, in today's world |
| Vietnamese | một cách (hiệu quả, rõ ràng…), của việc, để có thể, liền mạch, trực quan (không kèm bằng chứng), tối ưu hóa trải nghiệm, nâng tầm, toàn diện, mạnh mẽ, thân thiện với người dùng, đáng chú ý là, nhìn chung, nhằm mục đích |

## Accuracy

- Raise a point only when you can name the visible element, the screen, or the `file:line`. Not sure → **Can't tell** in a checklist, "Unconfirmed: …" in a finding.
- A standard pattern is not a finding: a ⋮ menu, a hamburger on phones, Cancel beside the primary button, a sticky header. Name a pattern only when it hurts the task in this screen.
- Work in progress is not a defect. Placeholder text, a state marked TODO or a page the plan builds later goes under "Not seen" or "not built yet", unless the user asks to judge it as final.
- Stay in scope. Critique: experience, content and how the screen uses the DS. Audit: DS compliance. A business rule or a wording decision is a question for PM or BA, not a finding.
- The DS and the rules in force win over every checklist. Where they differ: "platform deviation, needs design confirmation"; never propose a style change on your own.
- Every number comes from a script or a measure just run; state the command.

## Strengths

- A critique names at least two things that work, each tied to a visible element, so nobody removes them in the next round.
- An audit summary names the apps or areas that are in sync.
- A strength is specific ("the empty list explains what goes here and has one Create button"), never "clean design".

## Tables that paste well

- Plain Markdown tables. No HTML, no colour, no emoji or icons for status.
- Status words from "Item status" in `<kit>/skills/validate/references/a11y-web.md`: Pass, Partly, Missing, N/A, Can't tell.
- One line per row; the detail goes in the finding the row points to.
