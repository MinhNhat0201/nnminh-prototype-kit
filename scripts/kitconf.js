// Load kit.config.json and the DS profile it points to (Node version of kitconf.py).
//   const { load, t, versionLabel } = require('<kit>/scripts/kitconf.js');
//   const cfg = load();   // cfg._root, cfg._ds, cfg._dsDir
const fs = require('fs');
const path = require('path');

const KIT_ROOT = path.resolve(__dirname, '..');
const DEFAULTS = {
  language: 'en', stack: 'html', ds: null, apps: [],
  local: { prefix: 'x-', marker: 'LOCAL', registry: 'docs/local-components.json' },
  handoff: { dir: 'docs/handover', zipName: 'Design - {pbi}', maxZipMB: 3, figmaRequired: true },
  email: { subject: '[{app}] Design - {feature} - {version}', attachLimitMB: 3 },
  deploy: { type: 'none', site: null },
  paths: { changelog: 'CHANGELOG.md', plans: 'docs/plans', audits: 'docs/audits', explorations: 'docs/explorations', context: 'product-context', validation: 'docs/validation', verify: 'docs/verify' },
};
const DS_DEFAULTS = {
  label: null, version: '0.0.0', platforms: ['web'],
  tokens: { prefix: '--ds-', roles: {}, scale: {}, file: 'tokens.json' },
  css: { bundle: null, sources: [], marker: { begin: '@ds:begin', end: '@ds:end' } },
  version_label: { text: '{label} {version}', meta: 'ds-version' },
  theming: {}, breakpoints: { compact: 0, medium: 600, expanded: 840 }, icons: {},
  catalog: 'catalog.md', catalog_json: 'catalog.json', rules: 'rules.md', library: {},
  figma: { libraries: [], collections: {}, modes: {} }, preset: {},
};

function merge(base, over) {
  const out = { ...base };
  for (const [k, v] of Object.entries(over || {})) {
    out[k] = v && typeof v === 'object' && !Array.isArray(v) && out[k] && typeof out[k] === 'object' && !Array.isArray(out[k])
      ? merge(out[k], v) : v;
  }
  return out;
}

function findRoot(start) {
  let d = path.resolve(start || process.cwd());
  for (;;) {
    if (fs.existsSync(path.join(d, 'kit.config.json'))) return d;
    const up = path.dirname(d);
    if (up === d) return null;
    d = up;
  }
}

function load(start, require = true) {
  const root = findRoot(start);
  if (!root) {
    if (require) { console.error('ERROR: kit.config.json not found in this folder or any parent. Run the kickoff skill first.'); process.exit(1); }
    return null;
  }
  const cfg = merge(DEFAULTS, JSON.parse(fs.readFileSync(path.join(root, 'kit.config.json'), 'utf8')));
  cfg._root = root; cfg._ds = null; cfg._dsDir = null;
  if (cfg.ds) {
    const dir = path.resolve(root, cfg.ds), f = path.join(dir, 'ds.json');
    if (fs.existsSync(f)) {
      const ds = merge(DS_DEFAULTS, JSON.parse(fs.readFileSync(f, 'utf8')));
      ds.label = ds.label || ds.name;
      cfg._ds = ds; cfg._dsDir = dir;
    }
  }
  return cfg;
}

const fmt = (s, kw) => s.replace(/\{(\w+)\}/g, (m, k) => (k in kw ? kw[k] : m));
const versionLabel = cfg => fmt(cfg._ds.version_label.text, { label: cfg._ds.label, version: cfg._ds.version, name: cfg._ds.name });
const dsPath = (cfg, rel) => (rel == null ? null : rel.includes('://') ? rel : path.join(cfg._dsDir, rel));

const cache = {};
function locale(lang) {
  if (!(lang in cache)) {
    const d = path.join(KIT_ROOT, 'locales', lang), merged = {};
    if (fs.existsSync(d)) for (const f of fs.readdirSync(d).filter(n => n.endsWith('.json')).sort())
      Object.assign(merged, JSON.parse(fs.readFileSync(path.join(d, f), 'utf8')));
    cache[lang] = merged;
  }
  return cache[lang];
}
function t(cfgOrLang, key, kw = {}) {
  const lang = typeof cfgOrLang === 'string' ? cfgOrLang : (cfgOrLang && cfgOrLang.language) || 'en';
  return fmt(locale(lang)[key] || locale('en')[key] || key, kw);
}

module.exports = { load, findRoot, t, versionLabel, dsPath, KIT_ROOT };
