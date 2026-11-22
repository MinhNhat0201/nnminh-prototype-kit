// Reads a wireflow board back from Figma: screen id -> card node and image frame, plus every flow, row and row item
// with its node id. Used by the board template (its return value), the update code and `figma_wireflow.py mapjs`.
// Works on boards built by earlier kit versions too: it only uses the fixed layer names of the template.
function readBoard(b, p, SS) {
  const sfx = name => SS.find(x => name.endsWith(x));
  const kids = n => ('children' in n ? n.children : []);
  const sid = n => n.name.slice(0, -sfx(n.name).length).trim();
  const m = {}, imgs = {}, flows = {};
  for (const n of b.findAll(x => x.type === 'FRAME' && sfx(x.name))) { const id = sid(n); if (!m[id]) { m[id] = n.parent.id; imgs[id] = n.id; } }
  const text0 = n => { const t = n.type === 'TEXT' ? n : n.findOne(x => x.type === 'TEXT'); return t ? t.characters : ''; };
  const item = c => { // [kind, value, (flag,) node id]
    const im = kids(c).find(x => x.type === 'FRAME' && sfx(x.name));
    if (im) return ['n', sid(im), c.id];
    if (c.name.startsWith('Edge · ')) { const l = c.name.slice(7);
      return ['e', l, kids(c).some(x => x.name === 'Page change') ? 'x' : text0(c) !== l ? 'u' : '', c.id]; }
    if (c.name.startsWith('Back · ')) return ['chip', c.name.slice(7), c.id];
    if (c.name === 'Out of scope') return ['out', text0(c), c.id];
    return ['?', c.name, c.id];
  };
  const rows = f => { const out = []; let lab = null;
    for (const c of kids(f)) {
      if (c.type === 'TEXT') lab = c;
      else if (c.name === 'Row') { out.push({ id: c.id, label: lab ? lab.characters : '', labelId: lab ? lab.id : '', items: kids(c).map(item) }); lab = null; }
    }
    return out; };
  let off = null;
  for (const f of kids(b)) {
    if (f.name === 'Off-flow screens') { const r = rows(f); off = { id: f.id, row: r[0] ? r[0].id : '', items: r[0] ? r[0].items : [] }; }
    else if (kids(f)[0] && kids(f)[0].name === 'Flow header') {
      const h = kids(kids(f)[0]).find(x => x.type === 'TEXT');
      flows[f.name] = { id: f.id, title: h ? h.characters : '', titleId: h ? h.id : '', rows: rows(f) };
    }
  }
  return { ...m, _imgs: imgs, _board: b.id, _title: b.name, _page: p.id, _pageName: p.name, _flows: flows, _off: off };
}
