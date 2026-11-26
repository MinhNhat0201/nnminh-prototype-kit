# Accessibility and experience checklist: web screens (responsive included)

Condensed from WCAG 2.2 (levels A and AA) and the `web` skill of platform-design-skills (MIT), rewritten for prototypes built with a DS.
Read it in `validate` (step 3, when judging "Needs a human" items), in `prototype` (step 6) and in the critique mode of `review`.
Apps with `apps[].platform` set to a phone platform (`mobile`, `ios`, `android`): read [a11y-mobile.md](a11y-mobile.md) as well; its M-codes add to these.

**Order of precedence:** the rules in force (`rules.py list`) and the DS > this checklist. Where the DS documents something else (text size, colour, radius, a touch target per density), do not change the app to fit the checklist: write "platform deviation, needs design confirmation" in the report and send it to `document`.
This checklist sets **no** style. It only asks whether people can read, reach and operate the screen.

Column **How**: `A` = measured by `validate` (axe-core, focus, touch targets, contrast); `P` = a `validate` width or named state (`text=200%`, 390 px, `mode=dark`); `M` = look or operate by hand.

## 1. Structure and names (critical)
| Code | Check | WCAG | How |
|---|---|---|---|
| W-01 | `<html lang="…">` on every page, matching the content language (screen readers pick the voice from it) | 3.1.1 | A |
| W-02 | Exactly one `<main>`; header, nav and aside use semantic elements | 1.3.1 | A |
| W-03 | Every button, link, tab and menu item has an accessible name (visible text, `aria-label` for icon-only buttons) | 4.1.2 | A |
| W-04 | The accessible name contains the visible label (a "Save" button is not `aria-label="Submit form"`) | 2.5.3 | M |
| W-05 | `button` for actions, `a[href]` for navigation; no `div onclick` | 4.1.2 | A |
| W-06 | Content images have a descriptive `alt`; decorative images `alt=""`; decorative SVG icons `aria-hidden="true"` | 1.1.1 | A |
| W-07 | Headings do not skip levels (h2 to h4); one h1 per page | 1.3.1 | A |
| W-08 | No text in images where HTML text works (logos and image slides with a description excepted) | 1.4.5 | M |

## 2. Keyboard and focus (critical)
| Code | Check | WCAG | How |
|---|---|---|---|
| W-10 | Everything the mouse does works with the keyboard (Tab, Enter, Space, arrow keys in menus, tabs and grids) | 2.1.1 | M |
| W-11 | Focus is visible on every element (the DS focus ring; never `outline:none` without a replacement) | 2.4.7 | A |
| W-12 | Tab order follows reading order; no positive `tabindex` | 2.4.3 | M |
| W-13 | Dialog, bottom sheet, menu: focus moves in on open, stays in while open, Esc closes, focus returns to the opener | 2.4.3 | M |
| W-14 | No keyboard trap (what you can enter, you can leave) | 2.1.2 | M |
| W-15 | The focused element is not hidden under a sticky header or a toast | 2.4.11 | M |
| W-16 | Dragging (move a block, reorder) has an alternative without dragging (buttons, a ⋮ menu) | 2.5.7 | M |

## 3. Colour and contrast (critical)
| Code | Check | WCAG | How |
|---|---|---|---|
| W-20 | Normal text ≥ 4.5:1, large text (≥ 24 px, or ≥ 18.66 px bold) ≥ 3:1, in light and dark | 1.4.3 | A (each mode) |
| W-21 | Field borders, meaningful icons and the focus ring ≥ 3:1 against their background | 1.4.11 | M |
| W-22 | Colour is never the only signal (errors have an icon or text; links inside text are underlined or styled otherwise) | 1.4.1 | M |
| W-23 | Text over images or gradients has an overlay with enough contrast (automated checks skip image backgrounds: look) | 1.4.3 | M |

## 4. Responsive and touch targets (critical)
| Code | Check | WCAG | How |
|---|---|---|---|
| W-30 | No horizontal page scroll at 320–400 px (tables and diagrams may scroll inside their own region, with the DS scroll fade when it has one) | 1.4.10 | P |
| W-31 | Text at 200 % still reads in full: nothing clipped, nothing overlapping | 1.4.4 | P (`text=200%`) |
| W-32 | Targets ≥ 24×24 px or spaced far enough apart; phones use the platform size (`kit.config.json > validate.touchTarget`). A DS that documents its own target per density wins: follow it and note it | 2.5.8 | A |
| W-33 | Larger line height and letter spacing set by the user (line-height 1.5, letter-spacing 0.12em) do not break the layout | 1.4.12 | M |
| W-34 | Orientation is not locked | 1.3.4 | M |

## 5. Forms and errors (high)
| Code | Check | WCAG | How |
|---|---|---|---|
| W-40 | Every field has a label (`label` or `aria-label`); a placeholder is not a label | 1.3.1, 3.3.2 | A |
| W-41 | Errors appear as text next to the field, say what is wrong and how to fix it; the field has `aria-invalid` and is linked to the message | 3.3.1, 3.3.3 | M |
| W-42 | Required fields are marked with text or an explained `*`, not by colour alone | 3.3.2 | M |
| W-43 | The right input type (`type=email`, `tel`, `number`, `inputmode`) and `autocomplete` for personal data | 1.3.5 | M |
| W-44 | Delete or send actions that cannot be undone ask for confirmation or offer undo | 3.3.4 | M |
| W-45 | Related choices (radio, checkbox) have a group name (`fieldset`/`legend` or `role=group`) | 1.3.1 | M |
| W-46 | Buttons and links name the action with a verb and an object ("Create report", "Delete file"), not "OK", "Yes", "Click here"; a confirmation dialog repeats the action on its button | 2.4.6, 2.4.4 | M |
| W-47 | Error messages state the **problem** and the **fix** in plain words ("The file is over 20 MB. Choose a smaller file or compress it."), never blame the user, never a bare error code | 3.3.3 | M |

## 6. Status, messages, motion (medium)
| Code | Check | WCAG | How |
|---|---|---|---|
| W-50 | Toasts, progress of a running task and send errors are announced (`aria-live`, `role=status`, `role=alert`) | 4.1.3 | A (region) + M (announced) |
| W-51 | A wait over about one second shows a loading state; every list and result area has empty and error states (details: `prototype` [states-and-edge-data.md](../../prototype/references/states-and-edge-data.md)) | — | M |
| W-52 | `prefers-reduced-motion` is respected (DS motion follows it; local animation must too; see `review` [motion.md](../../review/references/motion.md)) | 2.3.3 | M |
| W-53 | Nothing flashes more than three times per second | 2.3.1 | M |
| W-54 | Content that moves or scrolls by itself for more than five seconds has a pause control | 2.2.2 | M |
| W-55 | Content shown on hover also shows on focus, closes with Esc and stays while the pointer moves onto it | 1.4.13 | M |
| W-56 | An empty state says what will be here, why, and how to start; a loading state says what is happening ("Building the outline…"), not only "Loading" | — | M |
| W-57 | One word per concept across the app (not "report" here, "document" there) | 3.2.4 | M |

## 7. Navigation (medium)
| Code | Check | WCAG | How |
|---|---|---|---|
| W-60 | The current item in a side bar or tab list has `aria-current` or `aria-selected` | 4.1.2 | M |
| W-61 | `<title>` names the current screen; a hash router updates it on every screen change | 2.4.2 | M |
| W-62 | The browser Back button returns to the previous screen (hash router), it does not leave the app | — | M |
| W-63 | The same function has the same name and place on every page (shared header, shared side bar) | 3.2.3, 3.2.4 | M |

## Item status

Going through a checklist item by item (a critique table, the manual items of `validate`), give each item one status:

| Status | Means | Note needed |
|---|---|---|
| **Pass** | Present and works on what you saw | No |
| **Partly** | Present but incomplete: one width, one state, one field of several | What is missing |
| **Missing** | Should be there and is not | The finding it points to |
| **N/A** | Does not apply to this screen (no form, no motion, no dialog) | A few words why |
| **Can't tell** | Could not be judged from what you saw (a still image, a state not opened, a sign-in you lack) | What would show it |

Can't tell is never counted as Pass. N/A needs its reason, so a reader can tell "not needed" from "not checked". No percentage of items passed.

## Writing findings

Three groups: **Must fix** (critical, blocks people), **Should fix** (high), **Nice to have** (medium); number them in one sequence. Each finding:
**What it is** · **Problem** (a concrete situation: who does what and meets what) · **Fix** (with DS components and tokens; no home-made style) · **If ignored** · **Rule** (the code above and the WCAG criterion) · `file:line` or the screen.
No concrete situation, no finding.
A problem inside a DS component (it shows in every app) is written once and proposed to `document`; never patch it app by app.
The other checklists ([a11y-mobile.md](a11y-mobile.md), states S-/D-, motion C-, heuristics H-, the screen checklists of `review` [screens/](../../review/references/screens/index.md)) use this format and the item statuses above.
