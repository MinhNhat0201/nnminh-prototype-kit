# Remediation options (step 7 of `review`)

Read this after the report is written. Three principles set the order of preference. An option that breaks one of them never goes into the recommended list.

## 1. Map hard-coded values to existing tokens first

```
python3 <kit>/skills/review/scripts/audit_map_tokens.py [app ...] --csv <scratchpad>/map.csv
```

The script matches hex and rgb colours, font sizes, radii, line heights and spacing in the app region (CSS, `style=""`, `style={{…}}`, `:style`, Tailwind arbitrary values) with the resolved value of each token in the default configuration of the DS bundle (plain `:root`, light).
The role comes from the property and `ds.json > tokens.roles`:

| Property | Role prefix |
|---|---|
| `color` | `roles.text`, then `roles.icon` |
| `background`, `background-color` | `roles.bg` |
| `border*`, `outline*` | `roles.stroke` |
| `fill`, `stroke` | `roles.icon`, then `roles.bg` |
| `font-size` | `roles.fontSize` |
| `line-height` | `roles.lineHeight` |
| `border-radius` | `roles.radius` |
| `margin`, `padding`, `gap` | `tokens.scale.spacing` first (the shared scale), then `roles.spacing` |

| Confidence | Meaning | Action |
|---|---|---|
| Exact | same value as exactly one token of the role | replace now; nothing visible changes |
| By role | several semantic tokens share the value | pick by the meaning of the place; the user approves each group |
| Near | only a close token (colour deltaE ≤ 4, size ≤ 1 px) | a visible change: check Figma, then decide |
| None | no token | check Figma (section 3); never invent a token |

- Map to semantic tokens only. Never use a primitive token to get around a missing semantic one.
- Translucent colours, fully rounded radii and composite shadows: never decide alone; go to section 3.
- Font size and line height marked "check the text role": the value matches, but the text style (body, caption, title) must match too.
- React / Vue: replace `bg-[#fff]` with the Tailwind theme class that maps to the token, or `bg-[var(<token>)]` when no class exists; replace `style={{ color: '#fff' }}` with `var(<token>)`. Never move styles between files or components.

## 2. Never change DOM or behaviour

Options change **CSS values** only (including values in style attributes, style objects and Tailwind classes).
Never change: DOM structure, class names that scripts use, text, sample data, flow, routes, behaviour, events.
An option that needs one of these is listed apart as "needs a product decision" and never goes into an automatic batch.

Prove that nothing else moved:
- Capture the same screen in the same state before and after.
- The "Exact" batch shows zero pixel difference beyond rendering noise.
- Other batches differ only where the proposal says.
- The local registry check and the app's `check` command (`kit.config.json > apps[].check`) still pass.

## 3. Prefer Figma; never force DS controls

Figma is the design source. The DS is its normalised copy. When the app differs from the DS, ask Figma before asking "is it the DS".
Read Figma with the libraries in `ds.json > figma`; it cannot be read → say so; never guess.

For every "Near", "None", home-made control and override:

| Case | Action |
|---|---|
| Matches Figma, the DS has a token with the Figma value | map to the token (safe batch) |
| Matches Figma, the DS lacks the token or control | keep the look; use tokens where they exist, keep the other values local with a note naming the Figma source; group a home-made control into a local `x-` block and propose it through `contribute`. **Never force a DS control** when that changes look or behaviour against Figma. |
| Differs from Figma | an app bug: propose the Figma fix as a visible change, in its own batch |
| Figma differs from the DS | a DS deviation: report it to `document`; never change the app to follow the wrong copy |

Icons, logos, images: take them from Figma or the DS (logos as the original SVG); never redraw.

## 4. Present the options

One row per group, at least two options (never just one):

| Group | Places | Options | Visible change | Product risk | Needs Figma |
|---|---|---|---|---|---|
| e.g. `#fff` as background | 11 | A keep and record; **B map to `--acme-bg-white` (recommended)** | no | no | no |

Order of recommendation: map to a token with no visible change → keep as in Figma with a record → fix to match Figma → propose to the DS.

Batches, one PR each so each can be undone:
1. **Batch 1, "Exact":** same-value mapping, nothing visible changes.
2. **Batch 2, "By role":** after the user approves each group.
3. **Batch 3, "Near" and "None":** after the Figma check; with the list of visible changes.
4. **Batch 4, home-made controls and overrides:** keep as in Figma, group into local `x-` blocks, propose to the DS when worth it; never replace in bulk.
5. **Batch 5, version debt:** `sync` (may come before batch 1, because tokens change with the version).

Every batch needs the user's approval before anyone starts. The audit never carries one out.
