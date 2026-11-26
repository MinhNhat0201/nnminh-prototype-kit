# Screen checklists: index

Checklists per screen type, written for this kit. Read this index in the critique mode of `review` ([critique.md](../critique.md)), in `prototype` before building a screen of a listed type, and in `explore` when comparing directions for one.
A screen can match two types (a settings page made of a form: `settings` and `form`). Use every type that matches; say which in the scope line.

**Order of precedence:** the rules in force (`rules.py list`), the DS and the approved Figma > these checklists. An item the DS or a recorded decision handles differently is "platform deviation, needs design confirmation", never a finding to fix on your own. The checklists set **no** style: they ask whether the screen has what people need to finish the task.

| Type | File | Signs | Codes |
|---|---|---|---|
| Sign-in | [sign-in.md](sign-in.md) | Email or user name and password, SSO buttons, "Forgot password" | SI- |
| Sign-up | [sign-up.md](sign-up.md) | Create an account, invite acceptance | SU- |
| Password reset | [password-reset.md](password-reset.md) | Request a link or code, set a new password | PW- |
| Form | [form.md](form.md) | Create or edit a record, a request, a profile | FM- |
| Multi-step flow | [wizard.md](wizard.md) | Steps with Next and Back, a stepper, setup | WZ- |
| Table or list | [table.md](table.md) | Rows of records, sort, filter, bulk actions, pages | TB- |
| Search and filters | [search.md](search.md) | A search box, results, facets, saved filters | SR- |
| Detail page | [detail.md](detail.md) | One record: header, fields, activity, actions | DT- |
| Dashboard | [dashboard.md](dashboard.md) | Numbers, charts, recent items, shortcuts | DB- |
| Settings | [settings.md](settings.md) | Preferences, account, organisation, integrations | ST- |
| Dialog and confirmation | [dialog.md](dialog.md) | Modal, sheet, confirm, delete | DG- |
| File upload | [upload.md](upload.md) | Choose or drop files, progress, attachments | UP- |
| Notifications | [notifications.md](notifications.md) | Bell, inbox, toasts, notification preferences | NT- |
| First run and empty | [first-run.md](first-run.md) | Onboarding, a new workspace, an empty product area | FR- |
| Long or AI task | [long-task.md](long-task.md) | Generate, import, export, analyse; anything that runs for seconds or minutes | LT- |

## How to use

- Each item has a level: **Must** (missing blocks or misleads people: a Must fix), **Should** (missing slows people or causes errors: a Should fix), **Nice** (polish).
- Give every item a status (Pass, Partly, Missing, N/A, Can't tell) as "Item status" in `<kit>/skills/validate/references/a11y-web.md` says.
- These lists do not repeat the general checklists. Read them with `a11y-web.md` (and `a11y-mobile.md` on phones), `<kit>/skills/prototype/references/states-and-edge-data.md` and [heuristics-rubric.md](../heuristics-rubric.md).
- Building (`prototype`): every Must item of the screen's type is built, or listed in the final report as left out with the reason.
- A type that is missing here: use the heuristics and the general checklists, and say so. A project can keep its own checklists in the same format; the user names them.
