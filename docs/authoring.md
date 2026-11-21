# Authoring skills and scripts in this kit

Read this before you add or change a skill.

## Skill names and calls

| Skill | Job |
|---|---|
| `brief` | Entry point: find out what the designer wants and route to the right skill |
| `kickoff` | Set up a project: `kit.config.json`, DS profile link, stack, first app skeleton |
| `adopt` | No DS yet: build a base DS profile from a public preset (default shadcn) |
| `define` | Analyse PM/BA requirements, questions, delivery plan, traceability |
| `context` | Product context files and the decision log (status lifecycle, who decided) |
| `explore` | Two to four design directions with the DS, comparison page, human decision before building |
| `prototype` | Build screens and flows with the DS; gates before new components and new pages |
| `validate` | Browser checks of a prototype and one report: fail, needs a human, skipped |
| `annotate` | Markdown spec per unit: screen captures, pins, computed styles mapped to tokens, flows |
| `wireflow` | Put the flow board (screen images joined by arrows) on Figma |
| `mockup` | Rebuild screens on Figma with auto layout, DS components and variables |
| `handoff` | Package one feature or a whole app into one zip for BA, QC and developers |
| `share` | Draft the handoff email (never sends) |
| `verify` | Compare a developer build with the approved prototype; defects or approved deviations; verified decisions |
| `review` | Audit an app against the DS: read-only, findings and options |
| `sync` | Bring a new DS version into apps |
| `contribute` | Review local components and propose them to the DS (two approval gates) |
| `document` | Write and maintain DS documentation and tokens |

Refer to another skill by its bare name in backticks (`handoff`). Users call skills as `/kit:<name>`.

## SKILL.md

- English only. Write for an agent: imperative, short sentences, one idea per line. Prefer tables for decisions.
- Frontmatter: `name` equals the folder name; `description` says what the skill does, when to use it (English trigger phrases), and when to use another skill instead. End the description with: "Also use for the same request in any language."
- First lines of the body: "Reply in the project language (`kit.config.json > language`). Generated documents use the same language."
- Read configuration, never hard-code it: DS name, token prefix, CSS bundle, theming attributes, version label, app list, site URL, Figma libraries. Write "the DS" and "`ds.json > tokens.prefix`", not a real DS name.
- No proprietary content: no company, product, DS or person names, no internal URLs, Figma file keys, emails or secrets. Use the placeholder DS `acme` (prefix `--acme-`) and app `acme-web` in examples.
- Stack-aware: where the behaviour depends on `stack`, give a short table or bullets for `html`, `react`, `vue` (see [stacks.md](stacks.md)).
- Keep rules that came from real use (gates, "ask before", "never silently"), and keep the reason when it is short. Drop history and product-specific notes.
- Target length: as short as the workflow allows. Move long reference material to `references/*.md` inside the skill.

## Scripts

- Python 3.9+ standard library; Pillow only where images are processed. Node 18+ with Playwright for browser work (Chromium is assumed installed; never run `playwright install` from a script).
- Load configuration through `scripts/kitconf.py` / `scripts/kitconf.js`. From a skill script: `sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))` (skills/<name>/scripts/x.py → kit root).
- Every message (print, error, help) in English. Text that ends up in a generated document goes through `t(cfg, "<skill>.<key>", **kw)`, with the English string in `locales/en/<skill>.json` and the Vietnamese string in `locales/vi/<skill>.json`.
- File names, config keys, JSON keys: English, lowercase, no diacritics.
- `--help` works and lists every command. Exit code 1 on error, with a line that starts with `ERROR:`.
- Scripts never commit, push, publish or send anything.

## Placeholders

| Use | Example |
|---|---|
| DS profile | `ds/acme`, label "Acme DS", prefix `--acme-` |
| App | `acme-web`, "Acme Web" |
| Work item | `PBI 1234`, feature "Scheduled tasks" |
| Site | `https://prototypes.example.com` |
