// Renames the layers of a board built by an older or another template to the kit's layer names, so readBoard can map
// it (figma_wireflow.py mapjs --adopt). Only names change; node ids stay, so links already sent keep working.
//   image frame: a FRAME filled with an IMAGE, or whose name ends with a known image suffix (SS); a frame inside
//                another image frame is not one. Renamed '<id>' + own suffix.
//   card:        the parent of the image frame (not the board, not a 'Row'). Renamed '<id>'.
//   screen id:   leading token of the image frame name (suffix removed), else of the card name: S01, S10b, FR-02.
//   board title: a TEXT already named 'Board title', else the first TEXT of the board header (the first child of the
//                board that holds text and no image frame), else the largest text. Renamed 'Board title'.
// Returns {renamed: [{id, from, to}], skipped: [image frame names without a screen id]}.
function adoptBoard(b, SS, own) {
  const ID = /^\s*([A-Za-z]+-?\d+[a-z]?)(?![\w])/;
  const sfx = name => SS.find(x => name.endsWith(x));
  const isImg = n => n.type === 'FRAME' && (!!sfx(n.name) || (Array.isArray(n.fills) && n.fills.some(f => f && f.type === 'IMAGE')));
  const inside = (n, top) => { for (let p = n.parent; p && p !== b; p = p.parent) if (top ? p === top : isImg(p)) return true; return false; };
  const imgs = b.findAll(isImg).filter(n => !inside(n));
  const renamed = [], skipped = [];
  const rename = (n, to) => { if (n.name !== to) { renamed.push({ id: n.id, from: n.name, to }); n.name = to; } };
  for (const n of imgs) {
    const card = n.parent && n.parent !== b && n.parent.type === 'FRAME' && n.parent.name !== 'Row' ? n.parent : null;
    const s = sfx(n.name);
    const m = (s ? n.name.slice(0, -s.length) : n.name).match(ID) || (card ? card.name.match(ID) : null);
    if (!m) { skipped.push(n.name); continue; }
    rename(n, m[1] + own);
    if (card) rename(card, m[1]);
  }
  if (!b.findOne(x => x.type === 'TEXT' && x.name === 'Board title')) {
    const head = b.children.find(x => x.type === 'TEXT' || ('children' in x && x.findOne(t => t.type === 'TEXT') && !imgs.some(i => inside(i, x))));
    const size = t => typeof t.fontSize === 'number' ? t.fontSize : 0;
    const t = head ? (head.type === 'TEXT' ? head : head.findOne(x => x.type === 'TEXT'))
      : b.findAll(x => x.type === 'TEXT').sort((p, q) => size(q) - size(p))[0];
    if (t) rename(t, 'Board title');
  }
  return { renamed, skipped };
}
