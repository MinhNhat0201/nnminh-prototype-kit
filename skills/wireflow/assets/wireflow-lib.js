// Drawing helpers shared by the board template and the update code (`figma_wireflow.py build` / `update` put this file
// in place of __LIB__). Needs D (data): D.L labels, D.C colours, D.imgSuffix, D.scale, D.width, D.screens.
// Layer names stay fixed ('<id> · image', 'Edge · <label>', 'Back · <id>', 'Out of scope', 'Row', 'Flow header',
// 'Off-flow screens'): wireflow-read.js finds the board structure by them.
const L = D.L, C = D.C, IMG = D.imgSuffix;
const S = D.scale || 0.5; // image size on the board relative to the capture viewport
await Promise.all([{ family: 'Inter', style: 'Regular' }, { family: 'Inter', style: 'Semi Bold' }].map(f => figma.loadFontAsync(f)));
const solid = c => [{ type: 'SOLID', color: c }];
const hex = c => '#' + [c.r, c.g, c.b].map(v => Math.round(v * 255).toString(16).padStart(2, '0')).join('');
function txt(s, size, bold, color, width, center) {
  const t = figma.createText();
  t.fontName = { family: 'Inter', style: bold ? 'Semi Bold' : 'Regular' };
  t.characters = s; t.fontSize = size; t.fills = solid(color || C.text);
  if (center) t.textAlignHorizontal = 'CENTER';
  if (width) { t.textAutoResize = 'HEIGHT'; t.resize(width, t.height); }
  return t;
}
function box(dir, props) { return figma.createAutoLayout(dir, props); }
function add(parent, child, fill) { parent.appendChild(child); if (fill) child.layoutSizingHorizontal = 'FILL'; return child; }
function put(parent, child, index, fill) { // insert at index (-1 = last)
  if (index < 0 || index >= parent.children.length) parent.appendChild(child); else parent.insertChild(index, child);
  if (fill) child.layoutSizingHorizontal = 'FILL'; return child;
}
// demo button: text hyperlink (works when viewing the file, Dev Mode) + Open URL reaction (works in presentation)
async function linkButton(label, url, name, big) {
  const b = box('HORIZONTAL', { name, itemSpacing: 12 });
  b.counterAxisAlignItems = 'CENTER';
  b.set({ paddingLeft: big ? 40 : 32, paddingRight: big ? 40 : 32, paddingTop: big ? 22 : 18, paddingBottom: big ? 22 : 18,
    cornerRadius: 999, fills: solid(C.accent), strokes: solid(C.white), strokeWeight: 3,
    effects: [{ type: 'DROP_SHADOW', color: { r: 0, g: 0, b: 0, a: .25 }, offset: { x: 0, y: 6 }, radius: 16, spread: 0, visible: true, blendMode: 'NORMAL' }] });
  add(b, txt('▶', big ? 26 : 22, true, C.white));
  const t = add(b, txt(label + '  ↗', big ? 28 : 24, true, C.white));
  t.hyperlink = { type: 'URL', value: url };
  try { await b.setReactionsAsync([{ trigger: { type: 'ON_CLICK' }, actions: [{ type: 'URL', url, openInNewTab: true }] }]); } catch (e) {}
  return b;
}

const imageNodeIds = [], imageScreens = [], made = {};
let edges = 0;
// pins (numbered dots) and click rings of one screen inside its image frame; also used by the redraw code
// (figma_wireflow.py redrawjs) after an image is replaced, so both draw the same marks. Returns the number of marks.
function clearMarks(img) { let k = 0;
  for (const c of [...img.children]) if (c.type === 'ELLIPSE' || c.type === 'TEXT' || /^(Pin|Click ring)/.test(c.name)) { c.remove(); k++; }
  return k; }
function drawMarks(img, s, w, h) {
  let k = 0;
  (s[5] || []).forEach((p, i) => { if (!p) return; // keep pin numbers; 0 = pin not found or outside the capture
    const dot = figma.createEllipse(); dot.name = 'Pin ' + (i + 1); dot.resize(22, 22); dot.fills = solid(C.accent); dot.strokes = solid(C.white); dot.strokeWeight = 2;
    dot.x = w * p[0] / 100 - 11; dot.y = h * p[1] / 100 - 11; img.appendChild(dot);
    const n = txt(String(i + 1), 11, true, C.white); n.name = 'Pin number ' + (i + 1); n.x = dot.x + 11 - n.width / 2; n.y = dot.y + 11 - n.height / 2; img.appendChild(n);
    k++;
  });
  const exits = !s[6] ? [] : Array.isArray(s[6][0]) ? s[6] : [s[6]];
  for (const q of exits) { const r = figma.createEllipse(); r.name = 'Click ring'; r.resize(28, 28); r.fills = []; r.strokes = solid(C.accent); r.strokeWeight = 3;
    r.x = w * q[0] / 100 - 14; r.y = h * q[1] / 100 - 14; img.appendChild(r); k++; }
  return k;
}
function screenNode(id) {
  const s = D.screens[id]; // [name, file#route, width, height, unit, pins[[left%,top%] | 0], exits [[left%,top%]…] | 0]
  const w = Math.round(s[2] * S), h = Math.round(s[3] * S);
  const card = box('VERTICAL', { name: id, itemSpacing: 8 });
  const img = figma.createFrame();
  img.name = id + IMG; img.resize(w, h); img.clipsContent = true; img.cornerRadius = 8;
  img.fills = solid(C.surface); img.strokes = solid(C.line); img.strokeWeight = 1;
  if (!made[id]) { imageNodeIds.push(img.id); imageScreens.push(id); made[id] = img.id; }
  drawMarks(img, s, w, h);
  card.appendChild(img);
  add(card, txt(id + ' · ' + s[0], 14, true, C.text, w));
  add(card, txt([s[4], s[1]].filter(Boolean).join(' · '), 12, false, C.sub, w));
  return card;
}
function edge(label, flag) {
  edges++;
  const e = box('VERTICAL', { name: 'Edge · ' + label, itemSpacing: 6 }); e.counterAxisAlignItems = 'CENTER';
  const col = flag === 'u' ? C.warn : C.sub;
  add(e, txt(label + (flag === 'u' ? ' · ' + L.toConfirm : ''), 12, false, col, 150, true));
  const dash = flag === 'u' ? ' stroke-dasharray="6 4"' : '';
  const a = figma.createNodeFromSvg('<svg width="140" height="16" viewBox="0 0 140 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2 8H134"' + dash + ' stroke="' + hex(col) + '" stroke-width="2"/><path d="M126 2L136 8L126 14" stroke="' + hex(col) + '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>');
  a.name = 'Arrow'; e.appendChild(a);
  if (flag === 'x') { const tag = add(e, box('HORIZONTAL', { name: 'Page change' }));
    tag.set({ paddingLeft: 8, paddingRight: 8, paddingTop: 2, paddingBottom: 2, cornerRadius: 999, strokes: solid(C.sub), dashPattern: [4, 3], strokeWeight: 1 });
    add(tag, txt(L.pageChange, 11, false, C.sub)); }
  return e;
}
function chip(id) {
  const c = box('HORIZONTAL', { name: 'Back · ' + id });
  c.set({ paddingLeft: 12, paddingRight: 12, paddingTop: 6, paddingBottom: 6, cornerRadius: 999, strokes: solid(C.line), strokeWeight: 1, fills: solid(C.white) });
  add(c, txt('↩ ' + id + (D.screens[id] ? ' · ' + D.screens[id][0] : ''), 12, false, C.text)); return c;
}
function out(label) {
  const o = box('VERTICAL', { name: 'Out of scope', itemSpacing: 4 });
  o.set({ paddingLeft: 16, paddingRight: 16, paddingTop: 16, paddingBottom: 16, cornerRadius: 8, fills: solid(C.surface), strokes: solid(C.sub), dashPattern: [6, 4], strokeWeight: 1 });
  add(o, txt(label || L.outOfScope, 12, false, C.sub, 200, true)); return o;
}
const makeItem = it => it[0] === 'n' ? screenNode(it[1]) : it[0] === 'e' ? edge(it[1], it[2]) : it[0] === 'chip' ? chip(it[1]) : out(it[1]);
// flow frame with its header, no rows yet. f = [id, name, rows, demo url, start hint]
async function flowFrame(parent, index, f) {
  const fl = put(parent, box('VERTICAL', { name: f[0], itemSpacing: 16 }), index, true);
  fl.set({ paddingTop: 24, paddingBottom: 24, paddingLeft: 24, paddingRight: 24, cornerRadius: 12, strokes: solid(C.line), strokeWeight: 1 });
  const fh = add(fl, box('HORIZONTAL', { name: 'Flow header', itemSpacing: 24 }), true);
  fh.counterAxisAlignItems = 'CENTER';
  add(fh, txt(f[0] + ' · ' + f[1], 22, true));
  if (f[3]) { fh.appendChild(await linkButton(L.openFlow, f[3], 'Button · Open demo ' + f[0]));
    if (f[4]) add(fh, txt(L.start.replace('{start}', f[4]), 18, true, C.sub)); }
  return fl;
}
function rowLabel(label) { return txt(label, 14, true, C.sub, D.width - 160); }
function addRow(fl, label, before) { // optional label line, then a wrapping row; before = node to insert above (else last)
  let at = before ? fl.children.indexOf(before) : -1;
  if (label) { put(fl, rowLabel(label), at); if (at >= 0) at++; }
  const row = put(fl, box('HORIZONTAL', { name: 'Row', itemSpacing: 24 }), at, true);
  row.layoutWrap = 'WRAP'; row.counterAxisSpacing = 32; row.counterAxisAlignItems = 'CENTER';
  return row;
}
function offSection(parent) {
  const off = add(parent, box('VERTICAL', { name: 'Off-flow screens', itemSpacing: 16 }), true);
  add(off, txt(L.offflow, 22, true));
  const row = add(off, box('HORIZONTAL', { name: 'Row', itemSpacing: 24 }), true); row.layoutWrap = 'WRAP';
  return row;
}
