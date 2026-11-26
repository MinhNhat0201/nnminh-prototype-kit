# Dialog and confirmation

Applies to: modal dialogs, side sheets, bottom sheets, confirmation of a destructive action. Read with: `a11y-web.md` W-13, W-44, W-46.

| Code | Check | Level |
|---|---|---|
| DG-01 | A dialog is used only when the task needs focus; a short message is a toast or an inline note instead | Should |
| DG-02 | The title states the question or the task ("Delete 3 files?") | Must |
| DG-03 | The body says the consequence: what is lost, whether it can be undone, who is affected | Must |
| DG-04 | The primary button repeats the action ("Delete files"), never "OK" or "Yes"; a destructive one uses the DS danger variant | Must |
| DG-05 | Cancel, Esc and the close button all close without side effects; focus returns to the opener | Must |
| DG-06 | Focus starts on the first field, or on Cancel for a destructive confirmation | Should |
| DG-07 | Clicking outside does not close a dialog with typed content | Must |
| DG-08 | A dialog opens no other dialog on top; a longer task moves to a page | Should |
| DG-09 | Content scrolls inside the dialog; the title and buttons stay visible | Should |
| DG-10 | An undo after the action can replace the confirmation when the action is reversible | Nice |
| DG-11 | On phones the dialog becomes a full-screen view or a bottom sheet with reachable buttons | Should |
