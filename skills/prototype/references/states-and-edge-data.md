# States and edge data: checklist for building and checking screens

Drawn from the `harden` and `onboard` parts of the impeccable skill (Apache-2.0) and from `break-ui` of emilkowalski/skills (MIT), rewritten for prototypes built with a DS.
Read it in `prototype` (step 6), in the "Missing" check of `define` (step 3), in `validate` (step 1, when listing the states of each screen) and when reviewing a screen.
Prototypes tend to show only "nice" data; this checklist makes you try what real users will meet.
Every state takes its style from the DS (empty state, alert, toast, skeleton, spinner, illustrations in the catalogue); never draw your own.

## 1. Every data region has all its states
| Code | State | Must have | Often missing in |
|---|---|---|---|
| S-01 | Empty, first use | Three parts: **what will be here**, **why it is worth using**, **how to start** (one primary action) | A new list, a chat history, a template library opened for the first time |
| S-02 | Empty after a filter or search | Says which conditions found nothing, with a button to clear the filters; different from first use | A search box, a filtered table |
| S-03 | Loading | A skeleton shaped like the content (or a spinner for a short action); shown only after about one second | Opening a record, switching to a tab with data |
| S-04 | Long processing | Progress or the current step; the user may leave the screen when it runs in the background; Stop or Cancel | Generating a document, an export, an AI task |
| S-05 | Partial error | The failed part says so in place, with Retry; the rest still works | Some items of a batch failed, one attachment failed |
| S-06 | Full error | What happened, whether data was lost, how to continue (Retry, contact) | Offline in the middle of a session, an expired session |
| S-07 | No permission or quota reached | The reason and a way forward (request access, top up, upgrade) | Out of credits, a feature not enabled for the organisation |
| S-08 | Success | A short confirmation (toast) and the next step when there is one; never a blocking dialog | Save, share, export |
| S-09 | Disabled | A disabled control says why (tooltip or text nearby) | A Create button while a required part is empty |

## 2. Edge data set (try on every screen)
Use values in the project language, with its diacritics, number and date formats. Examples below are in English.

| Code | Data | Sample | Check |
|---|---|---|---|
| D-01 | Very long name | `Digital transformation plan for the back office and the regional branches in the central region for 2027` | Cut with … and a way to read it in full (tooltip, detail view); the row does not break, buttons are not pushed out |
| D-02 | Long personal name, with diacritics | `María-José Nguyễn-Österberg van der Berg` | Initials avatar, labels and chips do not overflow |
| D-03 | One word with no break point | `https://drive.example.com/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz` | `overflow-wrap:anywhere` in text blocks; no horizontal page scroll |
| D-04 | Large numbers in the locale format | `19,606,990.1`, `1,250,000,000` with a currency | No line break inside a number; right-aligned in tables; tabular figures in columns when the DS has them |
| D-05 | Zero, one, very many | 0, 1 and 1,000 items | Correct plural ("1 file", "12 files"); long lists scroll or page; counters show "99+" |
| D-06 | Edge dates and times | Today, yesterday, 31 Dec, another year, another time zone | Correct relative labels; the project's date format |
| D-07 | Pasted content | 5,000 characters of text, a table from a spreadsheet, a large image | A limit and a message when it is exceeded; the page does not hang |
| D-08 | Special characters | `<b>`, `&`, emoji, quotes | Shown as text, never injected as HTML (escaped) |
| D-09 | Fast or repeated actions | Send pressed twice, Esc halfway, browser Back | No duplicates, nothing typed is lost |
| D-10 | Text size and narrow frames | 200 %, 320–400 px | As in the standard tests: nothing clipped, nothing overlapping |
| D-11 | Optional fields missing | No description, no cover image, no owner | No odd gaps, no "undefined" or "null", no orphan "·" or "–" separators |
| D-12 | No avatar | The user never set one, the image fails to load | Falls back to an initials avatar or a DS illustration at the same frame size |
| D-13 | Exactly one | 1 item, 1 collaborator, 1 notification | Correct sentence and separators ("1 file", never "1 files" or "1 file(s)"); a group of one still makes sense |
| D-14 | Very short | A two-letter name, a one-word label, a two-character title | The layout does not shift, buttons do not shrink below the touch target, alignment holds |
| D-15 | Real-looking data, not noise | From the domain (company names, file names, emails like `first.last@company.example`) | Never `aaaaaaaa` or 5,000 random characters: failures like that convince nobody |

Mock data stays marked as mock and never holds real personal data (see the data rules in `rules.py list`).

## 3. How to use it
- **Building:** the mock data of each screen has at least one D-01, one D-04 and D-05 (zero and many); every main data region has S-01, S-03 and S-06, plus S-04 when a task runs long. States you did not build go into the final report ("skipped").
- **Planning (`define`):** a state the requirement does not mention becomes a question for PM/BA (NON-BLOCKING, with a temporary assumption).
- **Validating:** each built state is a plan state with a `prepare` script; a state that cannot be reached without code changes is listed as not checked.
- **Reviewing:** S-01 or S-06 missing in a main flow is **Must fix**; S-02, S-07 or S-09 missing, or a break with D-01 to D-05, is **Should fix**. Write findings as in `validate` [a11y-web.md](../../validate/references/a11y-web.md).
