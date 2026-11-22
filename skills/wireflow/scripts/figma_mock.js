#!/usr/bin/env node
// Minimal stand-in for the Figma plugin API, only for `figma_wireflow.py --selftest` (no Figma connector needed).
// Runs generated use_figma code against an in-memory document and prints the return value as JSON.
//   node figma_mock.js <code.js> <state.json>   state.json keeps the document between runs (created when missing)
// It models only what the wireflow code uses: node tree, names, ids, characters, insert/append/remove, find*.
'use strict';
const fs = require('fs');
const [codeFile, stateFile] = process.argv.slice(2);
if (!codeFile || !stateFile) { console.error('ERROR: usage: node figma_mock.js <code.js> <state.json>'); process.exit(1); }

let seq = 1;
const byId = new Map();
class Node {
  constructor(type, props = {}) {
    this.id = props.id || `1:${seq++}`; this.type = type; this.name = props.name || type; this.parent = null;
    this.x = 0; this.y = 0; this.width = 100; this.height = 20; this.fontName = { family: 'Inter', style: 'Regular' };
    if (type !== 'TEXT' && type !== 'ELLIPSE' && type !== 'VECTOR') this.children = [];
    this.characters = props.characters || '';
    Object.assign(this, props); byId.set(this.id, this);
  }
  set(p) { Object.assign(this, p); }
  resize(w, h) { this.width = w; this.height = h; }
  appendChild(n) { this.insertChild(this.children.length, n); }
  insertChild(i, n) {
    if (n.parent) { const s = n.parent.children, k = s.indexOf(n); s.splice(k, 1); if (n.parent === this && k < i) i--; }
    this.children.splice(Math.min(i, this.children.length), 0, n); n.parent = this;
  }
  remove() { if (this.parent) this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null;
    const drop = n => { byId.delete(n.id); (n.children || []).forEach(drop); }; drop(this); }
  findAll(f) { const out = []; const walk = n => (n.children || []).forEach(c => { if (f(c)) out.push(c); walk(c); }); walk(this); return out; }
  findOne(f) { return this.findAll(f)[0] || null; }
  async setReactionsAsync() {}
}
const ser = n => ({ id: n.id, type: n.type, name: n.name, characters: n.characters || undefined, children: n.children && n.children.map(ser) });
function load(o, parent) { const n = new Node(o.type, { id: o.id, name: o.name, characters: o.characters || '' });
  if (o.children) for (const c of o.children) { const k = load(c, n); k.parent = n; n.children.push(k); } return n; }

const doc = fs.existsSync(stateFile) ? JSON.parse(fs.readFileSync(stateFile, 'utf8')) : null;
if (doc) seq = doc.seq;
const root = doc ? load(doc.root) : new Node('DOCUMENT', { id: '0:0' });
if (!doc) root.appendChild(new Node('PAGE', { id: '0:1', name: 'Page 1' }));
let current = root.children[0];
const make = (type, props) => { const n = new Node(type, props); current.appendChild(n); return n; }; // Figma adds new nodes to the current page
global.figma = {
  root, mixed: Symbol('mixed'),
  getNodeByIdAsync: async id => byId.get(id) || null,
  setCurrentPageAsync: async p => { current = p; }, loadFontAsync: async () => {},
  createPage: () => { const p = new Node('PAGE'); root.appendChild(p); return p; },
  createAutoLayout: (dir, props) => make('FRAME', Object.assign({ layoutMode: dir }, props)),
  createFrame: () => make('FRAME'), createText: () => make('TEXT'), createEllipse: () => make('ELLIPSE'),
  createNodeFromSvg: () => make('FRAME', { name: 'Svg' }),
};
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
new AsyncFunction(fs.readFileSync(codeFile, 'utf8'))().then(r => {
  fs.writeFileSync(stateFile, JSON.stringify({ seq, root: ser(root) }));
  console.log(JSON.stringify(r));
}).catch(e => { console.error('ERROR: ' + (e && e.stack || e)); process.exit(1); });
