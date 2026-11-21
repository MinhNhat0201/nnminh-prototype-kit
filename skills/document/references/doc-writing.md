# Writing DS docs for developers, QC, BA and designers

Read this when the user asks to write, fix, review or "make easier to read" the DS docs (one component, a foundation group, a release, or the whole DS).
The fill-in template is `assets/component-doc-template.md`; the script that takes facts from the CSS is `scripts/component_facts.py`.

## Goal

A reader in any of the four roles opens the doc and finds what they need in a few minutes, without messaging the DS maintainer.
A doc is neither a copy of the CSS nor an essay on design. A terse spec works for a BA who knows the DS; new developers, QC and designers miss examples, expected results and "do not use when".

## Four readers

| Role | Opens the doc to | Must be able to answer | Does not need |
|---|---|---|---|
| **Dev** | build the UI right | Which class (HTML) or component (React / Vue, from `components.map`)? Which tokens? Sizes? Smallest working code? What is forbidden (raw values, overrides)? | Long design rationale |
| **QC** | write test cases | Which variants and states exist? What does each look like, when does it happen? Sizes? Keys? Labels, maximum length, exact error text? | Token names |
| **BA** | write the feature spec | Which business situations is it for? Behaviour (show/hide, required, validation)? The right name? What must the BA decide? | Classes, tokens |
| **Design** | design new screens | This or that one? Do and don't? What colours mean? Same as Figma or not? Contrast, density, dark mode? | HTML |

The doc is one shared block: everyone reads the summary, then jumps to the sections labelled with their role.
Reason for one block instead of four: four copies drift apart after a few versions, and QC is usually the one who finds the drift.

## Writing principles

1. **Open for everyone.** Each component starts with a 3-line summary: what it is, when to use it, when not to (and what to use instead). The rest is split by role, with a **[Dev] [QC] [BA] [Design]** label at the start of each section so readers can scan.
2. **Facts from the source.** Sizes, tokens, variants and states come from `components.css`, `tokens.json`, the catalogue, the library page, or Figma once read. Never from memory. Anything unverified is marked "Unconfirmed", with who must confirm it.
3. **One fact, one place.** The full token table lives on the foundation page; a component page names only the tokens it uses and links back. Reason: when a value changes, only one place needs editing.
4. **Everyday words.** Short, active sentences in the project language. Explain a term (token, variant, state, local component) in one line the first time, or link to the glossary. Keep class, token and key names in `code`. One name per thing: once it is a "variant", never call it a "type" or "kind".
5. **Real example first, rule second.** "Save at the end of a form is primary; Cancel next to it is secondary" sticks better than "primary is for the main action". Use examples from real product screens when known, otherwise neutral ones.
6. **Tables for comparable things, sentences for reasons.** Variants, states and sizes go in tables of at most 5 columns, readable on a phone. Rules and reasons are sentences.
7. **State the certainty.** Each component carries one of three levels: *In Figma and the DS*, *Only in the DS (proposal)*, *Unconfirmed*. Modes not designed in Figma are always proposals. Intentional differences from Figma go under "Differs from Figma", never hidden.
8. **The doc reflects the DS; it never fixes it silently.** A bug or gap in the DS (hard-coded value, duplicate definition, missing state) goes under "Known issues" and to the user. Fixing the DS is the source workflow in `SKILL.md`.
9. **Never pad.** A section that does not apply gets one line, "Not applicable: <reason>", so QC knows it is not missing.

## Page types

| Type | Template |
|---|---|
| **"How to read these docs"** (first page) | Table of 4 roles → which sections to read first; DS version; the three certainty levels; how to report a wrong doc. Under one screen. |
| **Component** | `assets/component-doc-template.md`. |
| **Pattern** (form, data table, error page, comments, media) | Component template, plus "Built from which components" and "Behaviour flow" in the order the user acts. |
| **Foundation** (colour, type, spacing, radius, shadow, motion, brands, modes, responsive, icons) | What it is → When to use → Value table (token, value, used for) → Rules → [Dev] how to call `var()` → [Design] meaning and contrast. |
| **What's new per version** | Split by role: what Dev must change, what QC must retest, which behaviour changed for BA, what looks different for Design. One line each, linking to the component page. |
| **Glossary** | One word per line, with an example. Only words readers really meet. |
| **Mobile / native** | Same component template, plus two rows: the native widget name (from the profile's native code, e.g. `flutter/`; never invented) and "Differs from web". |

## Writing workflow

1. **Fix scope and readers.** One component, a group, a version, or the whole DS? Update an existing doc? Missing → ask exactly one question and stop.
2. **Collect facts.**
   - Read `ds.json` (version), `components.css`, `tokens.json`, `catalog.md`, `CHANGELOG.md`.
   - Inventory classes: `python3 <kit>/skills/document/scripts/component_facts.py --list`.
   - Fact sheet per component: `component_facts.py <class> [<class> ...]` (`--key-only` for a compact view, `--json` to process further). It gives variants, states, declarations, tokens used and hard-coded values.
   - A component with child classes (for example `tabs` and `tab`): pass both.
   - Read the DOM of the library page or a sample for the real HTML structure and sample labels; read its script for behaviour (keys, open/close).
   - Business behaviour the CSS cannot tell (when it shows, validation): take it from an earlier spec, the library page, or ask the user; never guess.
3. **Fill the template** top to bottom; write the summary last so it matches what you found. No source → "Unconfirmed" or "Not applicable".
4. **Read as each role.** Read the draft four times, one role each, and answer the questions below. A question the doc cannot answer → fix the doc, never explain it in chat.
5. **Check by machine** what a machine can check:
   - every token named in the doc exists in the source: `grep -o -- '<prefix>[a-z0-9-]*' doc.md | sort -u`, then compare with `tokens.css`;
   - every class named in the doc exists in `components.css`;
   - sizes in tables match the resolved token values.
   A mismatch → fix the doc to match the source, never the source to match the doc.
6. **Put it in the right place**, following the profile's structure (`catalog.md`, a docs folder, or the library page). A separate doc file → ask where first. Docs only → one "Docs" line in `CHANGELOG.md`, no version bump.

### When the doc lives in an HTML library page

- Use DS tokens and components; role labels use the DS tag or badge component.
- A "View by role" filter (All, Dev, QC, BA, Design) is optional: each role block has `data-role`, the switch is the DS segmented control, toggling `hidden`. Any extra frame is a local component (`x-doc-` prefix, inside a `/* LOCAL: … */` block). Tell the user before adding it, so they decide whether it joins the DS.
- Without the filter the page still reads top to bottom; JavaScript is only a convenience.

## Questions per role

| Role | The doc passes when the reader can answer, from the doc alone |
|---|---|
| Dev | What do I type to get this component (HTML or framework component)? Which class sets which variant? Which size comes from which token? Which hard-coded values must I avoid? How do web and native differ? |
| QC | Which cells make the variant × state matrix? What is expected in each? What does each key do? What happens with very long text? What exact error text shows? Which brands, modes and screen sizes to test? |
| BA | When is it used in the business flow? When not? What behaviour is required? Is there a sentence to copy into the spec? What must the BA decide? |
| Design | This one or the similar one? Do and don't? Same as Figma, and if not where and why? Does contrast pass? Which density? |

## Example (same content, two layouts)

Terse original, written for people who know the DS:

> **Class:** `.sbar` (track 16, thumb 6), `.t4` / `.t8` (thumb 4 / 8), `.md` (track 20), `.track` (track fill), `.sbar-pad` (content padding 20). **States:** default `stroke-scrollbar`; hover `icon-neutral`.

Rewritten for four roles. This only shows the layout: sizes and class names are from the original; the usage sentences are examples and must be checked against the source in a real doc.

> **Scroll bar** · `sbar` · In the DS
> **Summary.** A clearer scroll bar than the browser default, for scrolling regions such as tables, panels and long lists.
>
> **Variants**
> | Variant | Difference | Class |
> |---|---|---|
> | Default | track 16, thumb 6 | `.sbar` |
> | Thin / thick thumb | thumb 4 / 8 | `.sbar.t4` / `.sbar.t8` |
> | Wide track | track 20 | `.sbar.md` |
> | Filled track | fills the track | `.sbar.track` |
>
> **[QC] States.** Default: thumb in `--acme-stroke-scrollbar`. Hover: thumb turns `--acme-icon-neutral`.
> **[Dev]** Put `.sbar` on the scrolling element itself; add `.sbar-pad` (20) to keep content clear of the bar. Bar colours come from tokens; never write hex.

The difference: a summary, variants in a table, each state and instruction labelled with the role that needs it. No number beyond the source.
