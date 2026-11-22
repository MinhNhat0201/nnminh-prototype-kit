// Updates a wireflow board in place (figma_wireflow.py update). Card and image frame node ids stay, so links already
// sent keep working. Python computes every change; this code only applies it:
//   D.newFlows [[flow, after]]   new flow frames (after = {id} existing node or {new} flow id, null = after the header)
//   D.rows [{flow, row, off, label, items}]  final order of each changed row: ['id', node id] keeps or moves a node,
//                                ['make', item] draws a new one; row '' = new row (off = the off-flow section)
//   D.remove [node ids]          removed after the moves (--prune, replaced edges, relabelled rows)
//   D.titles [[text node id, text]]  flow header text changes
// Returns `map` (same shape as the mapjs result) and imageNodeIds / imageScreens of the new cards for upload_assets.
const D = __DATA__;
__LIB__
__READ__

const b = await figma.getNodeByIdAsync(D.root);
if (!b) throw new Error('Board not found: ' + D.root);
let page = b; while (page && page.type !== 'PAGE') page = page.parent;
await figma.setCurrentPageAsync(page);
const node = async id => { const n = await figma.getNodeByIdAsync(id); if (!n) throw new Error('Node not found: ' + id + ' (the board changed: run mapjs and update again)'); return n; };
const fl = {};
for (const [f, after] of D.newFlows) {
  const a = !after ? b.children.find(n => n.name === 'Board header') : after.new ? fl[after.new] : await node(after.id);
  fl[f[0]] = await flowFrame(b, a ? b.children.indexOf(a) + 1 : -1, f);
}
for (const r of D.rows) {
  const f = r.off ? null : r.flow.new ? fl[r.flow.new] : await node(r.flow.id);
  const row = r.row ? await node(r.row) : r.off ? offSection(b) : addRow(f, r.label ? r.label[1] : '');
  if (r.row && r.label) { const [lid, text] = r.label;
    if (lid) { const t = await node(lid); if (text) { await figma.loadFontAsync(t.fontName); t.characters = text; } else t.remove(); }
    else if (text) f.insertChild(f.children.indexOf(row), rowLabel(text)); }
  let i = 0;
  for (const it of r.items) row.insertChild(i++, it[0] === 'id' ? await node(it[1]) : makeItem(it[1]));
}
for (const id of D.remove) { const n = await figma.getNodeByIdAsync(id); if (n) n.remove(); }
for (const [id, s] of D.titles) { const t = await node(id); await figma.loadFontAsync(t.fontName); t.characters = s; }
return { rootId: b.id, imageScreens, imageNodeIds, count: imageNodeIds.length, edges, map: readBoard(b, page, D.sfx) };
