// Builds a wireflow board in a Figma Design file: one image frame per screen, joined by arrows along the flows.
// Fixed template of the `wireflow` skill. Never edit it per package: figma_wireflow.py puts the data in place of
// __DATA__, the drawing helpers (wireflow-lib.js) in place of __LIB__ and the board reader (wireflow-read.js) in place
// of __READ__; the result is sent verbatim through use_figma. Screenshots are attached afterwards with upload_assets
// (nodeIds = imageNodeIds returned below). Colours are board presentation colours (D.C), not product UI.
// Visible text comes from D.L (project language). Layer names stay fixed so scripts can find them again.
// The return value has `map` (same shape as the mapjs result): save it as <out>/map.json for setmap and later updates.
const D = __DATA__;
__LIB__
__READ__

// target page: by id (a Figma link whose node-id is a page), else by name, else create it
let page = D.pageId ? await figma.getNodeByIdAsync(D.pageId) : figma.root.children.find(p => p.name === D.page);
if (D.pageId && (!page || page.type !== 'PAGE')) throw new Error('pageId is not a page: ' + D.pageId);
if (!page) { page = figma.createPage(); page.name = D.page; }
await figma.setCurrentPageAsync(page);
for (const n of page.children.filter(n => n.name === D.title)) n.remove();

const root = box('VERTICAL', { name: D.title, itemSpacing: 48 });
root.set({ paddingTop: 48, paddingBottom: 48, paddingLeft: 48, paddingRight: 48, fills: solid(C.white) });
root.resize(D.width, 100); root.primaryAxisSizingMode = 'AUTO'; root.counterAxisSizingMode = 'FIXED';
const maxX = Math.max(0, ...page.children.filter(n => n !== root).map(n => n.x + n.width));
root.x = maxX ? maxX + 400 : 0; root.y = 0;

// board header: title, meta line, demo button, legend
const head = add(root, box('VERTICAL', { name: 'Board header', itemSpacing: 8 }), true);
add(head, txt(D.title, 32, true)).name = 'Board title';
add(head, txt(D.meta, 16, false, C.sub, D.width - 96));
if (D.home) {
  const demo = add(head, box('HORIZONTAL', { name: 'Demo', itemSpacing: 16 }));
  demo.counterAxisAlignItems = 'CENTER';
  demo.appendChild(await linkButton(L.openPrototype, D.home, 'Button · Open prototype', true));
  add(demo, txt(L.demoNote, 16, false, C.sub, 900));
}
const legend = add(head, box('HORIZONTAL', { name: 'Legend', itemSpacing: 24 }));
legend.counterAxisAlignItems = 'CENTER';
add(legend, txt(L.legend, 14, false, C.sub));

for (const f of D.flows) { // [id, name, [[row label, [[kind, …]]]], demo url, start hint]
  const fl = await flowFrame(root, -1, f);
  for (const r of f[2]) { const row = addRow(fl, r[0]); for (const it of r[1]) row.appendChild(makeItem(it)); }
}
if (D.offflow && D.offflow.length) { const row = offSection(root); for (const id of D.offflow) row.appendChild(screenNode(id)); }
return { pageId: page.id, rootId: root.id, imageScreens, imageNodeIds, count: imageNodeIds.length, edges,
  size: [Math.round(root.width), Math.round(root.height)], map: readBoard(root, page, D.sfx) };
