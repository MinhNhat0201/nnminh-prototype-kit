// Mockup audit (READ ONLY). spec_audit.py render fills __CONFIG__ from ds.json > figma and the node ids,
// then the result is sent verbatim through use_figma.
// pass = true when the Specs board has every screen of the Wireflow board, every frame with children uses
// auto layout, every colour, text, spacing and radius is bound to a library variable or style, variables (colour,
// spacing, radius, font size) come from the configured libraries and collections, text styles come from a library,
// and instances come from a library.
const CFG = __CONFIG__;
// CFG: { pageId, specsId, wireflowId, libraries: [names], collections: [names], imageSuffix,
//        exemptPrefix, iconPrefixes: [..], issueMax }
const ISSUE_MAX = CFG.issueMax || 30;

const page = await figma.getNodeByIdAsync(CFG.pageId);
if (!page || page.type !== 'PAGE') throw new Error('Page not found: ' + CFG.pageId);
await figma.setCurrentPageAsync(page);
const specs = await figma.getNodeByIdAsync(CFG.specsId);
if (!specs) throw new Error('Specs board not found: ' + CFG.specsId);

// library name of each remote variable collection, when the team library API is available
const libOfCollection = {};
try {
  for (const c of await figma.teamLibrary.getAvailableLibraryVariableCollectionsAsync()) libOfCollection[c.key] = c.libraryName;
} catch (e) {}

const code = (s) => String(s).split(' · ')[0].trim();
// 1. Parity: every screen on the Wireflow board (frame "<id><imageSuffix>") needs a frame "<id> · …" on the Specs board
const parity = { wireflow: [], specs: specs.children.map(n => code(n.name)), missing: [], extra: [] };
if (CFG.wireflowId) {
  const wf = await figma.getNodeByIdAsync(CFG.wireflowId);
  if (!wf) throw new Error('Wireflow board not found: ' + CFG.wireflowId);
  const SFX = [].concat(CFG.imageSuffix), sfx = name => SFX.find(x => name.endsWith(x));   // one suffix or a list
  wf.findAll(n => n.type === 'FRAME' && sfx(n.name))
    .forEach(n => { const c = n.name.slice(0, -sfx(n.name).length).trim(); if (!parity.wireflow.includes(c)) parity.wireflow.push(c); });
  parity.missing = parity.wireflow.filter(c => !parity.specs.includes(c));
  parity.extra = parity.specs.filter(c => !parity.wireflow.includes(c));
}

const varCache = {}, colCache = {};
async function varInfo(id) {
  if (varCache[id]) return varCache[id];
  const v = await figma.variables.getVariableByIdAsync(id);
  let col = '', lib = '';
  if (v) {
    const c = colCache[v.variableCollectionId] || (colCache[v.variableCollectionId] = await figma.variables.getVariableCollectionByIdAsync(v.variableCollectionId));
    col = c ? c.name : ''; lib = c && c.key ? (libOfCollection[c.key] || '') : '';
  }
  return (varCache[id] = { name: v ? v.name : '?', remote: !!(v && v.remote), col, lib });
}
const T = { screens: 0, frames: 0, noAutoLayout: 0, absolute: 0, rawFill: 0, rawStroke: 0, rawText: 0, rawSpacing: 0, rawRadius: 0,
  localVar: 0, localStyle: 0, foreignVar: 0, instances: 0, instancesLib: 0, localInstances: 0, exempt: 0 };
const bound = (n, f) => n.boundVariables && n.boundVariables[f];
function under(n, stop, test) { let p = n.parent; while (p && p !== stop) { if (test(p)) return true; p = p.parent; } return false; }
function note(list, msg) { if (list.length < ISSUE_MAX) list.push(msg); }
async function checkVar(b, n, label, list) {
  const ids = Array.isArray(b) ? b.map(x => x.id) : [b.id];
  for (const id of ids) {
    const vi = await varInfo(id);
    if (!vi.remote) { T.localVar++; note(list, label + ' bound to local variable ' + vi.name + ': ' + n.name); continue; }
    const badLib = CFG.libraries.length && vi.lib && !CFG.libraries.includes(vi.lib);
    const badCol = CFG.collections.length && vi.col && !CFG.collections.includes(vi.col);
    if (badLib || badCol) { T.foreignVar++; note(list, label + ' bound to ' + vi.name + ' from ' + (vi.lib || '?') + ' / ' + vi.col + ' (not a configured DS library or collection): ' + n.name); }
  }
}
async function paints(n, key, label, list, iconCtx) {
  if (!(key in n) || n[key] === figma.mixed) return 0;
  let raw = 0;
  for (const p of n[key]) {
    if (p.visible === false || p.type !== 'SOLID') continue;
    const b = p.boundVariables && p.boundVariables.color;
    if (b) { await checkVar(b, n, label, list); continue; }
    if (iconCtx) continue;
    if (key === 'fills' && n.fillStyleId && n.fillStyleId !== figma.mixed) continue;     // library paint style
    if (key === 'strokes' && n.strokeStyleId) continue;
    raw++; note(list, label + ' raw colour: ' + n.name);
  }
  return raw;
}

const screens = [], exempt = [];
for (const scr of specs.children) {
  T.screens++;
  const issues = [];
  const S = { name: scr.name, id: scr.id, noAutoLayout: 0, raw: 0, instances: 0 };
  const nodes = [scr, ...('findAll' in scr ? scr.findAll(() => true) : [])];
  for (const n of nodes) {
    if (n !== scr && under(n, scr, p => p.type === 'INSTANCE')) continue;       // inside a library component
    if (n.name.startsWith(CFG.exemptPrefix)) { T.exempt++; exempt.push(scr.name + ' › ' + n.name); continue; }
    if (under(n, scr, p => p.name.startsWith(CFG.exemptPrefix))) continue;
    const iconCtx = ['VECTOR', 'BOOLEAN_OPERATION', 'ELLIPSE', 'STAR', 'POLYGON', 'LINE'].includes(n.type) && under(n, scr, p => CFG.iconPrefixes.some(k => p.name.startsWith(k)));
    if (n.type === 'INSTANCE') {
      T.instances++; S.instances++;
      const mc = await n.getMainComponentAsync();
      if (mc && mc.remote) T.instancesLib++;
      else { T.localInstances++; note(issues, 'Instance not from a DS library: ' + n.name); }
      continue;
    }
    if (n.type === 'FRAME' || n.type === 'COMPONENT') {
      T.frames++;
      const kids = n.children ? n.children.length : 0;
      const isIcon = CFG.iconPrefixes.some(k => n.name.startsWith(k));
      if (kids > 0 && n.layoutMode === 'NONE' && !isIcon) { T.noAutoLayout++; S.noAutoLayout++; note(issues, 'No auto layout: ' + n.name); }
      if (n.layoutMode !== 'NONE') {
        let rawSp = false;
        for (const f of ['paddingLeft', 'paddingRight', 'paddingTop', 'paddingBottom', 'itemSpacing', 'counterAxisSpacing']) {
          if (bound(n, f)) { await checkVar(bound(n, f), n, 'Spacing ' + f, issues); continue; }
          if (!rawSp && typeof n[f] === 'number' && n[f] > 0) { rawSp = true; T.rawSpacing++; S.raw++; note(issues, 'Spacing not bound to a variable ' + f + '=' + n[f] + ': ' + n.name); }
        }
      }
      const rad = typeof n.cornerRadius === 'number' ? n.cornerRadius : n.topLeftRadius;
      for (const f of ['topLeftRadius', 'cornerRadius']) if (bound(n, f)) { await checkVar(bound(n, f), n, 'Radius', issues); break; }
      if (rad > 0 && !bound(n, 'topLeftRadius') && !bound(n, 'cornerRadius') && !isIcon) { T.rawRadius++; S.raw++; note(issues, 'Radius not bound to a variable ' + rad + ': ' + n.name); }
    }
    if (n !== scr && 'layoutPositioning' in n && n.layoutPositioning === 'ABSOLUTE') T.absolute++;
    if (n.type === 'TEXT') {
      const style = n.textStyleId && n.textStyleId !== figma.mixed && n.textStyleId !== '';
      if (!style && !bound(n, 'fontSize')) { T.rawText++; S.raw++; note(issues, 'Text without a DS text style or font-size variable: ' + n.name); }
      if (!style && bound(n, 'fontSize')) await checkVar(bound(n, 'fontSize'), n, 'Font size', issues);
      if (style) {
        const ts = await figma.getStyleByIdAsync(n.textStyleId);
        if (ts && !ts.remote) { T.localStyle++; note(issues, 'Text style is local, not from a DS library (' + ts.name + '): ' + n.name); }
      }
    }
    const rf = await paints(n, 'fills', n.type === 'TEXT' ? 'Text colour' : 'Fill', issues, iconCtx);
    const rs = await paints(n, 'strokes', 'Stroke', issues, iconCtx);
    T.rawFill += rf; T.rawStroke += rs; S.raw += rf + rs;
  }
  S.issues = issues;
  screens.push(S);
}
const collections = {};
for (const k in varCache) { const c = varCache[k]; const key = (c.remote ? 'library: ' + (c.lib || '?') + ' / ' : 'local: ') + c.col; collections[key] = (collections[key] || 0) + 1; }
const pass = parity.missing.length === 0 && T.noAutoLayout === 0 && T.localVar === 0 && T.localStyle === 0 && T.foreignVar === 0 && T.localInstances === 0 &&
  T.rawFill + T.rawStroke + T.rawText + T.rawSpacing + T.rawRadius === 0;
return { pass, parity, totals: T, collections, libraryLookup: Object.keys(libOfCollection).length > 0,
  exempt: exempt.slice(0, 40), screens: screens.filter(s => s.issues.length).map(s => ({ name: s.name, id: s.id, issues: s.issues })) };
