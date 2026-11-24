// Redraws the pins and click rings of screens whose image was replaced (figma_wireflow.py redrawjs, or `images --map`).
// Clears the marks inside every image frame of those screens on the board (repeated frames too) and draws them again
// from screens.json with drawMarks of wireflow-lib.js, the code the board template uses. Node ids stay.
//   D.root board node id, D.ids screen ids, D.sfx accepted image-frame suffixes, D.screens compact screen data
const D = __DATA__;
__LIB__

const b = await figma.getNodeByIdAsync(D.root);
if (!b) throw new Error('Board not found: ' + D.root);
let page = b; while (page && page.type !== 'PAGE') page = page.parent;
await figma.setCurrentPageAsync(page);
const sfx = name => D.sfx.find(x => name.endsWith(x));
const done = {}; let cleared = 0, drawn = 0;
for (const n of b.findAll(x => x.type === 'FRAME' && sfx(x.name))) {
  const id = n.name.slice(0, -sfx(n.name).length).trim();
  if (!D.ids.includes(id)) continue;
  cleared += clearMarks(n);
  drawn += drawMarks(n, D.screens[id], n.width, n.height);
  done[id] = (done[id] || 0) + 1;
}
return { board: b.id, frames: done, cleared, drawn, missing: D.ids.filter(i => !done[i]) };
