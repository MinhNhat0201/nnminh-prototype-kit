# Prototype Kit

A design workflow for Claude Code that works with **any design system**: 18 skills that take a design from requirement to developer handoff and back. Plan the work, explore directions, build HTML, React or Vue prototypes with the DS, check them in the browser, write the spec, put the flows on Figma, package everything for BA, QC and developers, then check the developers' build against what was approved.

**People decide, the kit does the work and checks it.** Every design choice goes through a gate where a named person decides, and the decision log remembers who decided what and why across sessions.

No design system yet? `adopt` builds a base one from a public preset (shadcn by default) with your brand colour, for web, mobile and tablet.

Website: [nnminh-prototype-kit.vercel.app](https://nnminh-prototype-kit.vercel.app) · Repository: `MinhNhat0201/nnminh-prototype-kit`

## Install

In Claude Code:

```
/plugin marketplace add MinhNhat0201/nnminh-prototype-kit
/plugin install kit@nnminh-prototype-kit
```

Skills are then available as `/kit:<skill>`, and Claude also picks them up from plain requests such as "build the settings screen" or "package feature 1234 for QC".

Requirements: Python 3.9+, Node 18+, Playwright with Chromium for screen capture and browser checks, Pillow for image optimisation and screenshot comparison. Optional: `axe-core` in the project (`npm i -D axe-core`) for the accessibility checks of `validate`. The Figma skills need the Figma connector; `share` needs a mail connector.

## Quick start

```
/kit:brief      I want to prototype a task manager for our team
```

`brief` asks one or two questions and sends you to the right skill. A new project usually goes:

1. `/kit:adopt`: only if you have no DS. Pick a brand colour, name and radius; get a DS profile in `ds/<name>/`.
2. `/kit:kickoff`: choose language, stack (`html`, `react`, `vue`) and the DS. Creates `kit.config.json`, the first app and a project `CLAUDE.md`.
3. `/kit:define`: turn PM/BA requirements into questions, waves and a traceability matrix.
4. `/kit:explore`: when a wave has a real design question, build 2–3 directions with the DS, compare them side by side and let the team choose one.
5. `/kit:prototype`: build screens with DS components only, from the chosen direction. It asks before creating new components or pages. `/kit:validate` checks it in the browser.
6. `/kit:annotate`, `/kit:wireflow`, `/kit:handoff`, `/kit:share`: spec, Figma flow board, zip package, email draft.
7. `/kit:verify`: once developers have built it, compare their build with the approved prototype and close the decisions as verified.

## Skills

### Skill map

```mermaid
flowchart LR
    brief(["brief<br/>entry point"])

    subgraph setup["1 · Set up"]
        adopt["adopt<br/>base DS from preset"]
        kickoff["kickoff<br/>config + first app"]
    end

    subgraph plan["2 · Plan"]
        context["context<br/>product memory + decisions"]
        define["define<br/>requirements → waves"]
    end

    subgraph build["3 · Explore, build & check"]
        explore["explore<br/>directions → choice"]
        prototype["prototype<br/>screens with DS"]
        validate["validate<br/>browser checks + report"]
    end

    subgraph spec["4 · Spec & Figma"]
        annotate["annotate<br/>Markdown spec"]
        wireflow["wireflow<br/>Figma flow board"]
        mockup["mockup<br/>Figma specs board"]
    end

    subgraph deliver["5 · Deliver"]
        handoff["handoff<br/>zip package"]
        share["share<br/>email draft"]
    end

    subgraph after["6 · After development"]
        verify["verify<br/>build vs approved design"]
    end

    subgraph ds["DS maintenance loop"]
        review["review<br/>read-only audit"]
        contribute["contribute<br/>local → DS"]
        document["document<br/>DS source + docs"]
        sync["sync<br/>new DS into apps"]
    end

    brief -.routes.-> kickoff & context & define & explore & prototype & validate & annotate & handoff & verify & review

    adopt -->|DS profile| kickoff
    kickoff -.no DS.-> adopt
    kickoff --> define
    define -->|waves| prototype
    define -.design question.-> explore
    context -.read by.-> define & explore & prototype
    explore -.approved decision.-> context
    explore -->|chosen direction| prototype
    prototype --> validate
    validate -->|Fail 0| annotate
    annotate -->|captures + flows| wireflow
    wireflow --> mockup
    annotate --> handoff
    wireflow -->|Figma links| handoff
    handoff --> mockup
    handoff --> share
    handoff -.developers build.-> verify
    verify -.verified decisions.-> context
    mockup -.Figma link.-> share

    prototype -->|local components| contribute
    review -->|undecided locals| contribute
    review -->|fix| sync
    contribute -->|approved proposal| document
    document -->|new version| sync
    sync -->|updated apps| prototype
```

Solid arrows are the usual order of work; dotted arrows are routing or optional links. The DS loop runs whenever the DS or the local components change, alongside the main flow.

| Skill | What it does |
|---|---|
| `brief` | Entry point: understands the request and routes to the right skill |
| `kickoff` | Sets up a project: config, DS link, stack, first app |
| `adopt` | Builds a base DS from a preset (shadcn) plus Material 3 structure for mobile and tablet |
| `define` | Requirement analysis, questions for PM/BA, delivery waves, traceability |
| `context` | Product memory every skill reads: overview, personas, UX principles, business rules, constraints, and a decision log with statuses (observed → proposed → approved → implemented → verified) |
| `explore` | Two to four design directions built with the DS, a comparison page and a recorded human decision before building |
| `prototype` | Builds screens and flows with the DS; component and new-page gates |
| `validate` | Browser checks of a prototype in one report: errors, overflow, accessibility (axe-core), keyboard focus, touch targets, states, flows, visual changes against a baseline; failures separated from items a human must judge |
| `annotate` | Markdown spec per unit with screen captures, pins, token-level style notes and flows |
| `wireflow` | Flow board on Figma from captures; updates in place so shared links keep working |
| `mockup` | Rebuilds screens on Figma with auto layout, DS components and variables, with an automatic audit |
| `handoff` | One zip for BA, QC and developers: spec, checklists, changelog, AGENTS.md, scoped prototype |
| `share` | Drafts the handoff email (never sends) |
| `verify` | After development: compares the build with the approved prototype (side-by-side screenshots, values outside DS tokens, missing components, changed texts, flows, accessibility); differences become defects or deviations covered by an approved decision |
| `review` | Read-only audit of an app against the DS, with remediation options |
| `sync` | Brings a new DS version into apps |
| `contribute` | Reviews local components and proposes them to the DS (two approval gates) |
| `document` | Writes and maintains DS documentation and tokens |

## People decide, the kit checks

| Gate (a person decides) | Where |
|---|---|
| Plan and waves approved before anything is built | `define` |
| One design direction chosen out of two to four, with the reason | `explore` |
| Every new component (compose, local block, or proposal to the DS) | `prototype` |
| Every new page (own file or route, or a screen inside the current one) | `prototype` |
| A local component proposed to the DS, then accepted into it | `contribute` (two gates) |
| A difference between the build and the design accepted as intended | `verify` (needs an approved decision) |
| Anything sent to people | `share` only drafts; nothing is sent, published or merged without you |

| Check (the kit proves it) | Where |
|---|---|
| Contrast of every colour pair, light and dark | `adopt`, `document` |
| Catalogue matches the DS CSS; deprecated components not used | `document` (`catalog.py check`), `review` |
| Prototype in the browser: errors, overflow, accessibility, focus, touch targets, states, flows, visual changes | `validate` |
| App code against the DS: hard-coded values, overrides, home-made controls | `review` |
| Developer build against the approved prototype | `verify` |

Decisions move through `observed → proposed → approved → implemented → verified` (or `rejected`, `superseded`). Skills read them before they plan or build, and update them when they build or verify.

## What the kit writes, and where

| Folder (default) | Holds | Written by |
|---|---|---|
| `kit.config.json` | Language, stack, apps, paths | `kickoff` |
| `ds/<name>/` | DS profile: tokens, CSS bundle, `catalog.md`, `catalog.json`, `rules.md` | `adopt`, `document` |
| `product-context/` | Overview, personas, UX principles, business rules, constraints, `decisions/` | `context`, `explore`, `define`, `prototype`, `verify` |
| `docs/plans/` | Requirement analysis, waves, traceability | `define` |
| `docs/explorations/<slug>/` | Directions, comparison page, decision | `explore` |
| `apps/<app>/` | Prototypes | `kickoff`, `prototype` |
| `docs/validation/<app>/` | Validation plan, runs, baseline screenshots | `validate` |
| `docs/handover/` | Handoff packages | `handoff` |
| `docs/verify/<name>/` | Build-vs-design runs and accepted deviations | `verify` |

Every folder is configurable in `kit.config.json > paths`.

## How it adapts to your project

Two files, no hard-coded design system:

- `kit.config.json` in the project: language of replies and documents, stack, apps, local-component prefix, handoff and email settings. See [docs/config.md](docs/config.md).
- `ds/<name>/ds.json` in the DS profile: token prefix and roles, CSS bundle, theming attributes, version label, Figma libraries. Made by `adopt`, or written by hand for an existing DS. Next to it, `catalog.md` (for people) and `catalog.json` (for agents: variants, states, tokens, code and Figma mapping, deprecated components and their replacement, usage rules).

Stacks are described in [docs/stacks.md](docs/stacks.md). Each app can override the project stack, so old HTML apps and new Vue apps can live side by side.

## Languages

The kit is written in English. Replies and generated documents follow `kit.config.json > language`; English and Vietnamese templates ship in `locales/`. To add a language, copy `locales/en/` to `locales/<code>/` and translate the values.

## Contributing

Read [docs/authoring.md](docs/authoring.md) before adding or changing a skill.

## Licence

MIT. The shadcn preset is derived from shadcn/ui and shadcn-vue (MIT); see `presets/shadcn/NOTICE`. Profiles made by `adopt` carry their own `NOTICE`.
