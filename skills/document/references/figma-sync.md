# Sync the DS from Figma

Figma is the design source, but a sync **never silently overwrites** the places where the DS deviates on purpose. List every deviation for the user to decide.
`get_design_context` output is a reference only: rebuild with semantic tokens; never copy hex or hard-coded styles from it.

## Steps

1. **Scope.** From the user: Figma link (file key and node id; turn `-` into `:` in the node id; a branch link uses the branch key), what to sync (colour, spacing, text, radius, components, logos, icons), current DS version. Libraries and variable collections are listed in `ds.json > figma`.
2. **Open a Figma session** with the file key before any other Figma tool; reuse the session id. Load the Figma skills the connector requires before its tools.
3. **Read in batches** (below), never the whole file at once.
4. **Normalise names** to the DS prefix (`ds.json > tokens.prefix`), following the naming the profile already uses (for example `Text/Secondary` → `--acme-text-secondary`). A variable that does not map goes to the "unmatched" list; never invent a name.
5. **Diff by code.** Resolve the DS `var()` chain in light mode and compare with the Figma values. Classes: new; changed value; in the DS but not in Figma; identical.
   - **Protected deviations** (`rules.md`: accessibility fixes, density, overlays, modes not designed in Figma, brand extras): never apply Figma to them; list them under "Figma differs from the DS".
   - Every colour about to change: measure contrast (text 4.5:1, control borders and icons 3:1) on the main backgrounds with `scripts/contrast.py`; report before and after.
6. **Show the diff before applying** when the change touches widely used tokens (text, background, border, spacing, radius) or lowers contrast. Small, clear changes: apply and list them in the report. Nobody to ask: apply only the certain part; the rest goes to "Needs design confirmation".
7. **Apply to the source**: `tokens.css` (and `tokens-dark.css` for new dark values), `components.css`, icons, logos. New tokens go into the right group. Renaming or removing a token is breaking (`X.0.0`).
8. **Test**: resolve `var()` for light, each dark block and each brand; compare before/after only for the tokens meant to change; then the standard checks.
9. **Changelog**: tokens (name, old → new), impact, "Needs design confirmation" (contrast drops, Figma deviations, unmatched names), apps not synced. Update `tokens.json`, `catalog.md`, the version label.
10. **Report**: synced items, number of new and changed tokens, deviations kept, unmatched names, contrast risks, apps to sync next (`sync`).

## Large files: batches with a manifest on disk

Each batch is small and its result lives on disk, so an interrupted session or a compressed context can resume.

1. **Batch 0, map.** `get_metadata` at file or page level for the node tree (name, id, type, size), no detail yet. Write `<scratchpad>/figma-sync/manifest.json`:
   ```json
   {"file": "<fileKey>", "items": [
     {"group": "variables", "name": "Colors", "node": "1:2", "status": "pending", "tries": 0, "out": null}
   ]}
   ```
   `group`: variables, component, icon, logo. `status`: `pending`, `done`, `error`.
2. **Split** into batches of 5 to 10 nodes, one token group, or one component set. Order: variables → components from small to large (button, input, tag, then table, dialog) → icons and logos. Many pages → one page at a time.
3. **Write to disk after each batch**: `figma-sync/raw/<group>-<node>.json`; set the item to `done`. Never paste long results into the conversation.
4. **Resume from the manifest**: at the start of each batch and after context compression, read the manifest and do only `pending` items.
5. **Merge the diff at the end** with one script that reads all of `raw/`, normalises names to the prefix, resolves `var()` and writes `diff.json`. Comparison and contrast are done by code.
6. **Errors**: a node too large or a timeout → split into its children. At most 2 tries per item, then `error`; go on and list it in the report.
7. **Checkpoint**: after the variables batch, show the token diff to the user before reading components (when they are present).
8. **Parallel** only when the user allows subagents: one node group per subagent, each writes only to `raw/` and returns one line. Default: sequential.
