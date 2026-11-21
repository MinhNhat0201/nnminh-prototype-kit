# Landing page content: nnminh-prototype-kit

Draft for review. Every claim below comes from the repository (README, skills, docs) or from a real test run of the kit. Nothing here is a made-up statistic, star count, logo or testimonial.

Page language: English (same as the kit). Tone, as on ui-skills.com: short, plain, imperative, written for designers and design engineers.

Notes in *[brackets and italics]* are layout notes, not page text.

---

## 0. Header

- Logo/wordmark: **nnminh-prototype-kit**
- Links: Skills · How it works · Install · Docs (→ GitHub `docs/`)
- Button: **GitHub** (→ repo)

---

## 1. Hero

**Headline**
From idea to developer handoff, with your design system.

**Subhead**
14 Claude Code skills that plan the work, build HTML, React or Vue prototypes with your design system, write the spec, put the flows on Figma and package everything for BA, QC and developers.

**Install card** *[code block with a Copy button]*
```
/plugin marketplace add MinhNhat0201/nnminh-prototype-kit
/plugin install kit@nnminh-prototype-kit
```

**Buttons**: Get started (→ #install) · View on GitHub

**Small line under the buttons**
MIT licence · Works with any design system · No design system yet? Start from shadcn.

---

## 2. Start with one sentence

**Heading**
Say what you want. The kit picks the skill.

**Body**
Start with `brief` and describe the job in plain words. It asks one or two questions, then routes the job to the right skill with a one-line plan.

*[code block]*
```
/kit:brief  I want to prototype a task manager for our team
```

You can also call a skill by name (`/kit:prototype`), or just ask: "build the settings screen", "package feature 1234 for QC".

---

## 3. How it works

**Heading**
One path from requirement to handoff.

*[horizontal stepper on desktop, vertical on mobile; 5 steps]*

1. **Set up**: `adopt` builds a base design system if you have none. `kickoff` picks the language, stack and design system and creates the first app.
2. **Define**: `define` turns PM and BA requirements into open questions, delivery waves and a traceability matrix.
3. **Prototype**: `prototype` builds screens with design-system components only. It asks before it creates a new component or page.
4. **Specify**: `annotate` writes the spec with screen captures, pins and token-level style notes. `wireflow` and `mockup` put the flows and screens on Figma.
5. **Hand off**: `handoff` packs one zip for BA, QC and developers. `share` drafts the email. It never sends it.

---

## 4. Skills

**Heading**
14 skills, one job each.

*[card grid grouped by phase; each card: skill name in mono, one sentence, link to its SKILL.md on GitHub]*

### Start
- **brief**: Understands a plain-language request and routes it to the right skill.
- **kickoff**: Sets up a project: config, design-system link, stack, first app and a smoke test.
- **adopt**: Builds a base design system from the shadcn preset and your brand colour, with Material 3 structure for mobile and tablet.

### Plan and build
- **define**: Splits requirements into units, writes questions for PM/BA, plans delivery waves with acceptance criteria.
- **prototype**: Builds screens and flows from a request, a plan wave or a screenshot, using design-system components first.

### Specify
- **annotate**: Writes a Markdown spec per unit, with screen captures, pinned elements and styles mapped to token names.
- **wireflow**: Builds a flow board on Figma from screen captures and updates it in place, so shared links keep working.
- **mockup**: Rebuilds screens on Figma with auto layout, library components and variables, then checks the result automatically.

### Deliver
- **handoff**: One zip for BA, QC and developers: spec, QC checklist, changelog, AGENTS.md and a scoped prototype.
- **share**: Drafts the handoff email with Figma and demo links. Draft only; you send it.

### Keep the design system in step
- **review**: Read-only audit of an app against the design system, with options to fix what it finds.
- **sync**: Brings a new design-system version into your apps.
- **contribute**: Reviews local components and proposes the good ones to the design system, with two approval gates.
- **document**: Writes and maintains design-system docs and tokens.

---

## 5. Any design system

**Heading**
No design system is hard-coded.

**Body**
The kit reads two files, so the same skills work for any team.

*[two side-by-side cards with a small code excerpt each]*

- **`kit.config.json`** in your project: language, stack, apps, local-component prefix, handoff and email settings.
- **`ds/<name>/ds.json`** in a design-system profile: token prefix and roles, CSS bundle, theming attributes, version label, Figma libraries.

**Footnote line**
Made by `adopt`, or written by hand for the design system you already have.

---

## 6. No design system yet

**Heading**
Start from shadcn. Make it yours.

**Body**
`adopt` asks for a brand colour, a name, a radius and a font. It takes the look from shadcn and the structure from Material Design 3, so one profile covers web, mobile and tablet.

*[bullet list with small icons]*
- Light and dark mode, with every colour pair checked for contrast (4.5:1 for text, 3:1 for icons and borders)
- A layout that switches from a side rail on tablet and desktop to a bottom tab bar on phones, and 48 px touch targets
- About 30 components, a `library.html` demo page, and tokens in CSS and in the W3C design-token format (DTCG)
- Variables that work with shadcn/ui and shadcn-vue components
- Optional: variables and text styles pushed to Figma, plus a Flutter theme

**Rule line** *[small, muted]*
You pick the brand colour and the prefix. The kit never picks them for you, and never lowers the contrast thresholds.

---

## 7. Your stack

**Heading**
HTML, React or Vue.

*[3 columns]*

- **html** (default): One file that opens anywhere. Light handoff packages.
- **react**: Vite, TypeScript, Tailwind and shadcn/ui, themed by your design system.
- **vue**: Vite, TypeScript, Tailwind and shadcn-vue, themed by your design system.

**Body**
Each app can use its own stack, so older HTML apps and new Vue apps can live in one repository. React and Vue builds come out as a single HTML file that opens from any folder.

---

## 8. What reaches your team

**Heading**
One package. Every role knows where to read.

*[list or 2×2 grid]*
- **BA**: Feature list and a Markdown spec per unit
- **QC**: A checklist per feature
- **Developers**: `AGENTS.md` with reading paths per role, styles mapped to token names, and the prototype itself
- **Everyone**: A Figma flow board, the changelog and a drafted email

**Small line**
No loose `.js` files in the zip, so mail filters let it through.

---

## 9. A real run

**Heading**
What `adopt` and `kickoff` produced in a test run.

*[terminal-style block, real output trimmed]*
```
Contrast: 148 pairs · 137 pass · 11 pass after tone adjustment · 0 fail
Profile OK
Created apps/nnminh-web (react, spa) from templates/react: 23 file(s).
dist/index.html  423.97 kB │ gzip: 123.30 kB
kit.config.json OK
```

*[optional: 2 screenshots from the same run, desktop with side rail and phone with tab bar]*

---

## 10. Languages

**Heading**
Your team's language.

**Body**
Replies and generated documents follow `kit.config.json > language`. English and Vietnamese ship with the kit. To add a language, copy `locales/en/` and translate the values.

---

## 11. Install

**Heading**
Install

*[code block with a Copy button]*
```
/plugin marketplace add MinhNhat0201/nnminh-prototype-kit
/plugin install kit@nnminh-prototype-kit
```

**Requirements**
- Claude Code
- Python 3.9+ and Node 18+
- Playwright with Chromium, for screen capture and browser checks
- Pillow, for image optimisation
- The Figma connector for `wireflow`, `mockup` and the Figma step of `adopt`
- A mail connector for `share`

**Then**
```
/kit:brief  I want to prototype a task manager for our team
```

---

## 12. Footer

- Tagline: Claude Code skills for prototypes and design handoff, with any design system.
- Links: GitHub · Docs (config, stacks, authoring) · Changelog · Licence (MIT)
- Credit line: The shadcn preset is derived from shadcn/ui and shadcn-vue (MIT).
- Version: v0.1.1
