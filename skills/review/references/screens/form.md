# Form (create or edit)

Applies to: creating or editing a record, a request, a profile. Not for: several pages of steps (`wizard.md`), a one-question dialog (`dialog.md`).
Read with: `a11y-web.md` W-40–W-47, `states-and-edge-data.md` D-01–D-11.

| Code | Check | Level |
|---|---|---|
| FM-01 | The title says what is created or edited ("New task", "Edit task: Q3 report") | Must |
| FM-02 | Fields follow the order people think in; related fields are grouped with a heading | Should |
| FM-03 | Required and optional are marked one way across the app; the less common kind is the one marked | Must |
| FM-04 | Labels above or beside fields, never placeholder-only; help text under the field when the format is not obvious | Must |
| FM-05 | Sensible defaults filled in; nothing typed twice that the system already knows | Should |
| FM-06 | The control fits the data: a choice of up to about five is radios or a segmented control, longer lists a select or combobox, dates a date picker that also takes typing | Should |
| FM-07 | Checks run when a field is left or on submit, not on every key; the message says the fix | Must |
| FM-08 | Submit with errors moves focus to the first error and keeps everything typed | Must |
| FM-09 | Primary button names the result ("Create task"); Cancel is there and asks before discarding changes | Must |
| FM-10 | The submit button shows progress and cannot be pressed twice; success says where the record is | Must |
| FM-11 | Leaving with unsaved changes (Back, close tab, another menu) asks first | Should |
| FM-12 | Edit mode shows the current values and what changed; read-only fields look read-only, with the reason | Should |
| FM-13 | Field widths hint at the expected length (a postcode is short, a description is wide) | Nice |
| FM-14 | Long forms keep the actions in reach (sticky footer) or split into sections | Nice |
| FM-15 | A server error keeps the form and says whether anything was saved | Must |
