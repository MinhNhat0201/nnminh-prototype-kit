# Experience and accessibility checklist: mobile screens (iOS, Android)

Condensed from the Apple Human Interface Guidelines and Material Design 3 (through the `ios` and `android` skills of platform-design-skills, MIT) and WCAG 2.2, for phone apps, phone-frame mockups of native screens and HTML built with a mobile DS profile.
Read it for apps whose `apps[].platform` is a phone platform (`mobile`, `ios`, `android`), together with [a11y-web.md](a11y-web.md): its W-codes on names, contrast, labels and messages still apply.

**Order of precedence:** the rules in force (`rules.py list`) and the DS > this checklist. Where the DS differs from HIG or Material (control size, text, colour), write "platform deviation, needs design confirmation"; do not change the app on your own. Never copy iOS or Material style into the app: use the checklist only to ask "can a phone user tap, read and go back?".

Column **How**: `A` = measured by `validate` at phone width; `P` = a `validate` named state (`text=200%`, 390 px, `mode=dark`); `M` = look or operate by hand (a real device or the platform setting where the browser cannot simulate it).

## 1. Touch targets and gestures (critical)
| Code | Check | Source | How |
|---|---|---|---|
| M-01 | Targets ≥ 44×44 pt (iOS) / 48×48 dp (Android); a smaller icon gets a larger hit area through padding, never a larger icon. A DS that documents another size wins: follow it and note it | HIG, M3 | A (`validate.touchTarget`) |
| M-02 | Two adjacent targets are at least 8 px apart | M3 | M |
| M-03 | Every gesture (swipe to delete, swipe between tabs, long press) has a button or menu alternative | HIG, WCAG 2.5.1 | M |
| M-04 | System gestures are not blocked: edge swipe back (iOS), back gesture or Back button (Android) | HIG, M3 | M |
| M-05 | The main action sits where the thumb reaches (lower half of the screen) | HIG | M |

## 2. Safe areas and keyboard (critical)
| Code | Check | Source | How |
|---|---|---|---|
| M-10 | Content and buttons stay clear of the notch, camera cut-out, status bar and home indicator (safe areas) | HIG, M3 | M |
| M-11 | With the keyboard open, the field being typed in and the send button stay visible (the frame moves up, nothing is covered) | HIG, M3 | M |
| M-12 | The keyboard type matches the content (number, email, URL); the Return key says what it does (Send, Next, Done) | HIG | M |

## 3. Text and system text size (critical)
| Code | Check | Source | How |
|---|---|---|---|
| M-20 | System text size up to 200 % (Dynamic Type, font scale): text wraps, frames grow, nothing clipped or overlapping | HIG, M3, WCAG 1.4.4 | P |
| M-21 | Tab bar labels and buttons are not cut with … at large sizes; change the layout when needed (icon above text, a vertical list) | HIG | P |
| M-22 | Body text ≥ 16 px at the default size (the DS mobile body style) | HIG, M3 | M |

## 4. Navigation (high)
| Code | Check | Source | How |
|---|---|---|---|
| M-30 | Tab bar with 3–5 items, always with text labels; the current item is clear without relying on colour | HIG, M3 | M |
| M-31 | A child screen has a back button at the top left; the title sits centred (iOS) or left (Android), as the DS mobile header does | HIG, M3 | M |
| M-32 | Bottom sheet: a drag handle or close button, swipe down closes, tapping the scrim closes (except a mandatory sheet) | HIG, M3 | M |
| M-33 | Confirmation dialog: cancel and action are clearly different; a destructive action uses the DS danger style and the platform's side | HIG, M3 | M |
| M-34 | Leaving a half-filled flow asks to save a draft or discard | HIG | M |

## 5. Feedback and states (high)
| Code | Check | Source | How |
|---|---|---|---|
| M-40 | Every tap shows visible feedback (pressed state) within about 100 ms | HIG, M3 | M |
| M-41 | Long waits show progress; pull to refresh shows an indicator | HIG, M3 | M |
| M-42 | Offline or a failed send: a clear message, Retry, and nothing typed is lost | HIG | M |
| M-43 | Toasts and snackbars do not cover the main action and stay long enough to read (≥ 4 s; a close button when they hold an action) | M3 | M |

## 6. Permissions and privacy (high)
| Code | Check | Source | How |
|---|---|---|---|
| M-50 | Ask for a permission (microphone, camera, notifications, photos) only when it is needed, with an explaining screen before the system dialog | HIG, M3 | M |
| M-51 | When the user refuses, the feature still has a way forward (how to open Settings, an alternative) | HIG, M3 | M |

## 7. Dark mode and motion (medium)
| Code | Check | Source | How |
|---|---|---|---|
| M-60 | Dark mode (when the app offers it) keeps contrast on every screen; illustrations do not turn into white blocks | HIG, M3 | A (`mode=dark`) + M |
| M-61 | System reduced motion: slides and zooms become fades or no motion (see `review` [motion.md](../../review/references/motion.md)) | HIG, M3 | M |

Write findings as in "Writing findings" of [a11y-web.md](a11y-web.md) (Must fix / Should fix / Nice to have, four parts, rule code). Item statuses (Pass, Partly, Missing, N/A, Can't tell) as in "Item status" there.
