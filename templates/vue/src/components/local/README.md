# Local components

A local component is UI that the DS does not have yet. It exists only after the component gate of the `prototype` skill (option B or C), never silently.

## Rules

- One component per file: `src/components/local/<Name>.vue`.
- The first line of the file is the header comment, with the marker from `kit.config.json > local.marker`:

  ```vue
  <!-- {{LOCAL_MARKER}}: Upload drop zone -->
  ```

  One name per file. The registry script finds the file by this header.
- Class names keep the local prefix `{{LOCAL_PREFIX}}` (`{{LOCAL_PREFIX}}drop-zone`), so audits and screen captures can tell local UI from DS UI.
- Build from DS components (`src/components/ui/`, `catalog.md > components.map`) and Tailwind classes mapped to DS tokens. No Tailwind arbitrary values (square-bracket colours or sizes), no `:style` binding for colour or spacing, no CSS that restyles a DS component.
- After adding, changing or removing a file here, run `python3 <kit>/skills/contribute/scripts/registry.py update`, fill the new entry in `{{LOCAL_REGISTRY}}` (title, kind, status, summary, where, vs_ds, decision with reason, decided_on), then `registry.py check`.
- Proposed to the DS (`status: "propose"`): keep the `proposal` block current and run `registry.py ack <id>` after each change.
