---
name: share
description: "Draft the design handoff email for BA, QC and developers from a handoff package: subject from the project template, Figma link, demo links (app and each flow), key features or the version changelog written for business readers, and the package zip attached. Creates a DRAFT only for the user to review and send; never sends. Use when the user says 'write the handoff email', 'email BA/QC/Dev', 'send the design package by mail', 'handover email'. Use `handoff` to build the zip and `wireflow` or `mockup` for the Figma board. Also use for the same request in any language."
---

# Handoff email

Reply in the project language (`kit.config.json > language`). Generated documents use the same language.
Model and effort: `kit.config.json > skills.share` (`model`, `effort`) when set. Work handed to a sub-agent starts with them; when this session runs another model, say so once.

Rules: run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rules.py list --app <app> --skill share` (no app: leave out `--app`) and follow what it prints: `must` rules are never broken, a `should` rule is broken only with the reason in the report, `EXCEPTION` and `OVERRIDDEN` lines say what does not apply to this app. It replaces reading long rule documents; read the DS `rules.md` only when the output says the profile keeps its rules there. `rules.py show <id>` explains one rule ([docs/rules.md](../../docs/rules.md)).

Result: **one email draft** in the user's mail connector (or plain text to paste when there is none).

| Part | Content | Source |
|---|---|---|
| Subject | `kit.config.json > email.subject` (`{app}`, `{feature}`, `{version}`, `{pbi}`) | user, package `README.md` |
| 1. Figma link | the work-item page (wireflow, Figma specs) | report of `wireflow` / `mockup`, `pkg.json > figma_file`, or the user |
| 2. Demo link | the app on `deploy.site`, plus one link per flow; left out when `email.demoLinks` is `false` | `requirements/flows.json` (`home`, `url`), `deploy.site` + `apps[].path`, or the user |
| 3. Key features / changelog | **written for business readers**, grouped by feature or flow. First release: key features. Later: the version changelog (features too when the user wants) | `requirements/checklist-feature.csv`, `requirements/changelog.md` |
| 4. Package | the zip attached, how to open | `<handoff.zipName>.zip` from `handoff` |

## Step 0. Inputs
Ask everything missing in one round (at most 4 questions):
1. **The zip.** None yet: build it with `handoff` first (size and blocked-file step done: no `.js`, under `handoff.maxZipMB`).
2. **App** (id or name from `kit.config.json > apps`), **work-item name** as the user says it (may include the code, e.g. `[1234] Scheduled tasks`), **version** (default: read from the package).
3. **Figma link:** from the Figma step of this session, else ask. **Demo link:** `home` in `flows.json`, else `deploy.site` + app path; confirm with the user. Never invent a link.
4. **Recipients** (To, Cc) and signature: ask every time. Never write email addresses into the repository, a PR or a shared report.

## Step 1. Compose
```
python3 -I skills/share/scripts/draft_email.py "<package>.zip" --app <app id> --feature "<work-item name>" \
  --figma <Figma link> [--demo <demo link>] [--version x.y.z] [--signature "<name>"] [--greeting "..."] \
  [--with-features] [--package-link <url>] [--demo-needs-login] --out <scratch folder>/email
```
- Writes `email.json` (subject, body, htmlBody, attachment: path, sha256, size, or `null`), `subject.txt`, `body.txt`, `body.html`, and `source.json` (material for step 2). Reads only README, changelog, feature list, flows.json and `spec/index.md` from the zip; no network.
- ERROR (exit 1): no version found; Figma link not on figma.com; demo link not https; the zip still has files that mail filters block.
- **Attachment size:** mail providers cap attachments (often 20–25 MB) and mail connectors often accept much less per call (about 3 MB is common). The limit comes from `kit.config.json > email.attachLimitMB` (default 3); `--attach-limit-mb` overrides it. Over the cap, the script drops the attachment and the body points to `--package-link`. Tell the user, and offer a draft without the attachment plus a download link (drive, site). Never split, rename or password-protect the zip.
- NOTE: missing links, zip over `handoff.maxZipMB`, no feature list or changelog, demo link derived from config.
- Long lists keep the first `email.maxItems` items (default 12; `--max-items` overrides) and point to the file in the package for the rest. "Out of scope" rows are not key features.
- The project keeps its own short layout: `kit.config.json > email.template` (or `--template`) is a `.md`/`.txt` or `.html` file with placeholders (`{greeting}`, `{intro}`, `{figma}`, `{demo}`, `{sections}`, `{package}`, `{how_to_open}`, `{feedback}`, `{thanks}`, `{signature}`, `{feature}`, `{version}`, `{app}`, `{pbi}`, `{subject}`, `{attachment}`; `{language}` in the path). The table above is then only the material: the template decides what appears and in which order. A NOTE lists placeholders it does not know. Without a template the kit layout is used.
- `email.demoLinks: false` (or `--no-demo`): the project sends no prototype or demo links by mail. The email has no demo item and no flow links (numbering shifts up); a `--demo` value is ignored with a NOTE. Do not ask for a demo link then.

## Step 2. Rewrite section 3 for business readers (required)
The first run copies section 3 from the package (technical lines folded into one "UI refinements" line) and prints a NOTE. Read `source.json` (features with group, screen, status; changelog lines; flow names), and `spec/index.md` if needed, then write a JSON file:
```json
{"title": "Changelog (changes since the previous version)", "more": "requirements/changelog.md",
 "groups": [{"name": "Create a scheduled task", "items": ["Users can pause and resume a task without losing its history"]},
            {"name": "Offline", "items": ["When the connection drops, the task is saved and synced when it returns"]}]}
```
First release: title "Key features", `more` `requirements/checklist-feature.csv`. Both: a JSON array of two sections. Write the titles in the project language. Run step 1 again with `--business <file>`.
- **Group** by the feature or flow names BA uses (flow ids, feature groups in the checklist), not by screen or file.
- **One business sentence per item:** who can do what, how the system responds, new rules or conditions (limits, permissions, states). For a change, say before and after from the user's view.
- **No technical detail:** tokens (`ds.json > tokens.prefix`), colours, type sizes, radius, classes, files, DS version. Pure UI changes fold into one line "UI refinements to match the design system (details in changelog.md)". The script flags items that still contain technical terms.
- Mock or demo-only features say "(demo)". Add nothing the package does not have; ask when unsure.

## Step 3. Review with the user
Show subject, body (plain text), recipients, attachment name and size (or the link when dropped). Apply feedback (edit the business JSON or arguments, run again). Do not create the draft while there is an ERROR, or while `businessRewritten` is false and the user has not agreed to keep the copied text.

## Step 4. Create the draft
- Use the create-draft tool of the user's mail connector: subject, plain body, HTML body, To, Cc, the provider's signature when supported, and the zip from `email.json > attachment` (path, file name, `application/zip`). When the connector takes a file reference (for example `sha256:<sha256>:<absolute path>`), use it; never base64 the file by hand.
- **Draft only, never send.** The user opens the draft and presses Send. Send on their behalf only when they ask for it explicitly in that turn.
- No mail connector: give subject and body to paste, and hand the zip to the user as a file.

## Step 5. Report (short)
Draft link, subject, recipients, attachment and size (or "sent by link" and why), number of features or changelog items, NOTEs left (missing links, size). Remind: the demo link may need a site account; the zip opens on any computer.

## Rules
- Content comes only from the package and the user. Never invent features, changes or links.
- Section 3 is for business readers; technical detail stays in the package.
- The subject follows `email.subject`; the version matches the package `README.md` and changelog.
- Never attach a package that has not passed the size and blocked-file step of `handoff`.
- Never store recipients, the email text or the draft link in the repository.
