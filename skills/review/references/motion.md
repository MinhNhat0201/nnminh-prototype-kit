# Motion checklist for prototype screens

Drawn from `emil-design-eng` and `review-animations` by Emil Kowalski (emilkowalski/skills, MIT), rewritten for prototypes built with a DS.
Read it in `review` (screen review, step 3) and in `prototype` (steps 5 and 6) when a screen adds or changes animation.
**Values always come from the DS motion tokens** (durations and easings: the token prefixes in `ds.json > tokens.roles.duration` and `tokens.roles.easing`, else motion tokens of the CSS bundle, and the DS enter, leave and view-change classes when the catalogue has them); never a curve or duration of your own.
Where the DS has no fitting token: write "platform deviation, needs design confirmation" and send it to `document`.

## 1. Should it move at all (by frequency)
| How often people meet it | Decision |
|---|---|
| Hundreds of times a day (shortcuts, opening search, switching tabs by key) | No motion |
| Tens of times a day (hover, moving through a list, changing page) | None, or very light (the shortest DS duration) |
| Now and then (dialog, drawer, toast, menu) | The DS standard motion |
| Rare or first time (onboarding, a first completion) | An accent is allowed |

Valid purposes: keep spatial orientation (where it opens from, where it goes), show state, explain a change, give feedback on an action, avoid an abrupt jump.
"It looks nice" is not a reason on an element people meet often. Keyboard actions do not animate.

## 2. Checklist
| Code | Check | How |
|---|---|---|
| C-01 | Follows the frequency table above; frequent elements have no long motion | M |
| C-02 | Entering uses the DS decelerate easing; leaving uses the DS accelerate easing and is **shorter** than entering; movement on screen uses the DS standard easing; steady progress uses `linear` | M |
| C-03 | UI motion ≤ about 300 ms (the DS medium duration); longer only for large scene changes (a full-screen panel, onboarding) | M |
| C-04 | Interruptible: a state change while it runs continues from where it is (`transition` for back-and-forth states, `@keyframes` only for loops or a one-time entrance) | M |
| C-05 | Popovers, menus and tooltips grow from their trigger (`transform-origin` at the anchor), not from the centre | M |
| C-06 | Never scale from `scale(0)`; enter from about `scale(.95)` together with `opacity` | M |
| C-07 | Tooltips: a delay the first time, then instant when moving to the next element (no second delay) | M |
| C-08 | Animate only `transform` and `opacity` (`clip-path` and `filter` when needed); never `width`, `height`, `top`, `left`, never `transition: all` | A (search the app CSS) |
| C-09 | `prefers-reduced-motion: reduce`: no slides, zooms or bounces; keep a short `opacity` change or switch instantly; decorative loops stop | A (emulate the media query) + M |
| C-10 | A pressed button responds at once (under 100 ms) and accepts input before any animation ends | M |
| C-11 | Staggered list entrances only on first load, a small delay per item (the shortest DS durations), about 300 ms in total; no stagger on scroll or re-filter | M |
| C-12 | Touch devices: hover effects do not stick after a tap (`@media (hover:hover)`) | M |
| C-13 | Decorative loops (an AI orb, a shimmer, a streaming effect) stop, or run only while work is in progress; never forever on a static screen | M |
| C-14 | Check in slow motion (browser animation panel at 10 %) or frame by frame: no jank, no layout jump, no content flash | M |

## 3. Writing findings
Use the four-part format of `validate` [a11y-web.md](../../validate/references/a11y-web.md), with the C-code.
A problem in the motion of a DS component (its enter classes, dialog, toast, menu) is written once and proposed to `document`.
Motion that causes dizziness or blocks input (C-09, C-10) is **Must fix**; C-01 to C-06 are usually **Should fix**; the rest **Nice to have**.
