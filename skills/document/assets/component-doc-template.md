# <Component name> · `<technical name>`

**DS:** <label> <x.y.z> · Native <x.y.z or "not yet">
**Certainty:** In Figma and the DS | Only in the DS (proposal) | Unconfirmed
**Since version:** <x.y.z when added>

> One template for all four roles. A section that does not apply gets one line, "Not applicable: <reason>"; never delete the section. Delete the `<...>` guidance when you fill it in. Write the doc in the project language.

## Summary
- **What it is:** <one sentence, no unexplained jargon>
- **Use when:** <a concrete situation in the product>
- **Do not use when:** <situation> → use `<other component>` instead.
- **Example:** <one sentence, e.g. the Save button at the end of a form>

## Picture it
<Image or live example from the library page or a sample. None → "See <section> on the DS library page".>

## Variants
| Variant | Use when | Class / component |
|---|---|---|
| <name> | <situation> | `<.class>` / `<Component variant="…">` |

## States and expected result — [QC] [Dev]
| State | Looks like | Happens when | Main tokens |
|---|---|---|---|
| Default | | | |
| Hover | | | |
| Pressed | | | |
| Keyboard focus | | | |
| Disabled | | | |
| <error, loading, selected… if any> | | | |

## Behaviour, keyboard, accessibility — [QC] [BA]
- **Mouse and touch:** <action → result>
- **Keyboard:** <key → result>
- **Accessibility:** <required aria attributes, focus order, screen-reader label>

## Size and spacing — [Dev] [QC]
| Property | Value (px) | Token |
|---|---|---|
| Height | | |
| Horizontal padding | | |
| Gap between parts | | |
| Radius | | |

## Content — [BA] [QC]
- **Sample label:** <exact text>
- **Maximum length and overflow:** <truncate, wrap, ellipsis>
- **Sample messages:** <exact text, and when it shows>

## Rules of use — [Design] [BA]
**Do**
- <short rule, with a one-clause reason>

**Don't**
- <short rule> → <what to do instead>

## For Dev
**HTML (smallest working snippet):**
```html
<!-- shortest working snippet, taken from the library page or catalogue -->
```
**React / Vue:** <component name from `catalog.md > components.map`, or "not mapped">
**Native:** <widget name from the profile's native code, or "not in native yet">
**Forbidden and known issues:**
- <no raw colour values; no CSS overriding variants>
- <hard-coded values still in the CSS, from the "Hard-coded values to review" part of `component_facts.py`>

## For QC — test checklist
- [ ] Every variant × state in the table above renders as described
- [ ] <main sizes match the Size table>
- [ ] <keyboard: each key in the Behaviour section>
- [ ] <long text, empty text, text with diacritics>
- [ ] At least two brands; light and dark (dark is a proposal unless designed; say so when testing)
- [ ] Narrow screen 400 px: no horizontal scroll

## For BA — how to write it in the spec
- **Sentence to copy into the spec:** "<ready-made sentence using the exact component name>"
- **BA must decide:** <business choices the component leaves open>

## For Design
- **Against Figma:** same | differs in <point> because <reason>. Intentional deviations go into `rules.md`.
- **Contrast and density:** <pass/fail, control size>
- **Dark mode:** proposal, <note>
- **Related:** <components often used with it, components easily confused with it>

## History
| Version | Change |
|---|---|
| <x.y.z> | <one line> |
