#!/usr/bin/env node
// Selftest for assets/spec-audit.js: runs the audit against a small fake Figma document and checks
// that spacing, radius and font-size variables are checked against the configured libraries and
// collections, and that local text styles are reported. Usage: node audit_selftest.js
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const tpl = fs.readFileSync(path.join(__dirname, '..', 'assets', 'spec-audit.js'), 'utf8')
  .split('\n').filter(l => !l.startsWith('//')).join('\n');
const CFG = { pageId: 'P', specsId: 'SP', wireflowId: 'WF', libraries: ['DS'], collections: ['Theme', 'Space'],
  imageSuffix: [' · image'], exemptPrefix: '[outside DS]', iconPrefixes: ['Icon', 'Logo'], issueMax: 30 };
const code = tpl.replace('__CONFIG__', JSON.stringify(CFG));

const VARS = {
  vColor: { name: 'bg/page', remote: true, variableCollectionId: 'cTheme' },
  vSpace: { name: 'space/16', remote: true, variableCollectionId: 'cSpace' },
  vOther: { name: 'gap/16', remote: true, variableCollectionId: 'cOther' },     // other library
  vLocal: { name: 'radius/4', remote: false, variableCollectionId: 'cLocal' },
  vFont: { name: 'font/body', remote: true, variableCollectionId: 'cTheme' },
};
const COLS = { cTheme: { name: 'Theme', key: 'kT' }, cSpace: { name: 'Space', key: 'kS' },
  cOther: { name: 'Number', key: 'kO' }, cLocal: { name: 'Local', key: '' } };
const STYLES = { sLib: { name: 'Body', remote: true }, sLoc: { name: 'My body', remote: false } };

function node(o) {
  const n = Object.assign({ children: [], boundVariables: {}, fills: [], strokes: [], layoutMode: 'NONE' }, o);
  n.children.forEach(c => { c.parent = n; });
  n.findAll = f => n.children.flatMap(c => [c, ...c.findAll(() => true)]).filter(f);
  return n;
}
const ref = id => ({ type: 'VARIABLE_ALIAS', id });
const solid = id => ({ type: 'SOLID', visible: true, boundVariables: { color: ref(id) } });
const al = (name, kids, bv, extra) => node(Object.assign({ type: 'FRAME', name, layoutMode: 'VERTICAL', children: kids,
  paddingLeft: 16, itemSpacing: 16, boundVariables: bv }, extra || {}));
const text = (name, extra) => node(Object.assign({ type: 'TEXT', name, fills: [solid('vColor')] }, extra));

const ok = al('Body', [text('Title', { textStyleId: 'sLib' }), text('Hint', { textStyleId: '', boundVariables: { fontSize: ref('vFont') } })],
  { paddingLeft: ref('vSpace'), itemSpacing: ref('vSpace') });
const screen1 = al('S01 · Good', [ok], { paddingLeft: ref('vSpace'), itemSpacing: ref('vSpace') }, { fills: [solid('vColor')] });
const bad = al('Grid', [text('Label', { textStyleId: 'sLoc' }), text('Note', { textStyleId: '', boundVariables: { fontSize: ref('vOther') } })],
  { paddingLeft: ref('vOther'), itemSpacing: ref('vSpace') }, { cornerRadius: 4, boundVariables: { paddingLeft: ref('vOther'), itemSpacing: ref('vSpace'), topLeftRadius: ref('vLocal') } });
const screen2 = al('S02 · Bad', [bad], { paddingLeft: ref('vSpace'), itemSpacing: ref('vSpace') });
const specs = node({ type: 'FRAME', name: 'Specs', children: [screen1, screen2] });
const wf = node({ type: 'FRAME', name: 'Wireflow', children: [
  node({ type: 'FRAME', name: 'S01 · image' }), node({ type: 'FRAME', name: 'S02 · image' })] });
const page = node({ type: 'PAGE', name: 'Page', children: [wf, specs] });
const IDS = { P: page, SP: specs, WF: wf };

global.figma = {
  mixed: Symbol('mixed'),
  getNodeByIdAsync: async id => IDS[id] || null,
  setCurrentPageAsync: async () => {},
  getStyleByIdAsync: async id => STYLES[id] || null,
  teamLibrary: { getAvailableLibraryVariableCollectionsAsync: async () =>
    [{ key: 'kT', libraryName: 'DS' }, { key: 'kS', libraryName: 'DS' }, { key: 'kO', libraryName: 'Other' }] },
  variables: {
    getVariableByIdAsync: async id => VARS[id] || null,
    getVariableCollectionByIdAsync: async id => COLS[id] || null,
  },
};

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
new AsyncFunction(code)().then(r => {
  assert.deepStrictEqual(r.parity.missing, [], 'parity');
  const issues = (r.screens.find(s => s.name === 'S02 · Bad') || { issues: [] }).issues.join('\n');
  assert.ok(!r.screens.some(s => s.name === 'S01 · Good'), 'good screen has no issues: ' + JSON.stringify(r.screens));
  assert.ok(/Spacing paddingLeft bound to gap\/16 from Other/.test(issues), 'spacing variable from another library');
  assert.ok(/Radius bound to local variable radius\/4/.test(issues), 'radius bound to a local variable');
  assert.ok(/Font size bound to gap\/16 from Other/.test(issues), 'font size from another library');
  assert.ok(/Text style is local/.test(issues), 'local text style');
  assert.strictEqual(r.totals.foreignVar, 2, 'foreignVar count');
  assert.strictEqual(r.totals.localVar, 1, 'localVar count');
  assert.strictEqual(r.totals.localStyle, 1, 'localStyle count');
  assert.strictEqual(r.pass, false);
  console.log('selftest OK');
}).catch(e => { console.error(e); process.exit(1); });
