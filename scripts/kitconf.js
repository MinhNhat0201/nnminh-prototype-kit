// Load kit.config.json and the DS profile it points to (Node version of kitconf.py).
//   const { load, t, versionLabel } = require('<kit>/scripts/kitconf.js');
//   const cfg = load();   // cfg._root, cfg._ds, cfg._dsDir
//   const mob = load(null, true, 'acme-mobile');   // the DS profile of that app (apps[].ds)
const fs = require('fs');
const path = require('path');

const KIT_ROOT = path.resolve(__dirname, '..');
const DEFAULTS = {
  language: 'en', stack: 'html', ds: null, apps: [],
  local: { prefix: 'x-', marker: 'LOCAL', registry: 'docs/local-components.json', command: { update: null, check: null }, fields: {},
    vueStyle: 'sfc', vueCss: 'src/styles/local.css' },
  handoff: { dir: 'docs/handover', zipName: 'Design - {pbi}', maxZipMB: 3, figmaRequired: true, itemLabel: '', grepLabels: [],
    dsLabel: 'auto', dsLabelCheck: 'warn', specFiles: { archive: 'archive.md', crossPage: 'cross-page.md', legacy: [] },
    csv: { feature: null, qc: null }, pre: null, post: null, specFields: {}, smokeWidths: [400, 768, 1280] },
  email: { subject: '[{app}] Design - {feature} - {version}', attachLimitMB: 3, demoLinks: true, maxItems: 12, template: null },
  deploy: { type: 'none', site: null },
  sync: { command: null, check: null, prepare: null, post: null },
  review: { extraChecks: [] },
  prototype: { post: null },
  figma: { imageSuffix: null },
  validate: { touchTarget: { default: 44, desktop: 24 }, axePath: null, setTheme: null },
  skills: {},
  rules: { categories: {} },
  paths: { changelog: 'CHANGELOG.md', plans: 'docs/plans', audits: 'docs/audits', explorations: 'docs/explorations', context: 'product-context', validation: 'docs/validation', verify: 'docs/verify', rules: 'rules' },
};
const DS_DEFAULTS = {
  label: null, version: '0.0.0', platforms: ['web'],
  tokens: { prefix: '--ds-', roles: {}, scale: {}, file: 'tokens.json', ignorePrefixes: [] },
  css: { bundle: null, sources: [], marker: { begin: '@ds:begin', end: '@ds:end' }, load: 'embed', linkPath: null },
  version_label: { text: '{label} {version}', meta: 'ds-version' },
  theming: {}, breakpoints: { compact: 0, medium: 600, expanded: 840 }, icons: {},
  catalog: 'catalog.md', catalog_json: 'catalog.json', rules: 'rules.md', changelog: null, review: { genericClasses: [] }, library: {},
  figma: { libraries: [], collections: {}, modes: {} }, preset: {}, patterns: [],
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

function readProfile(root, rel) {
  if (!rel) return [null, null];
  const dir = path.resolve(root, rel), f = path.join(dir, 'ds.json');
  if (!fs.existsSync(f)) return [null, null];
  const ds = merge(DS_DEFAULTS, JSON.parse(fs.readFileSync(f, 'utf8')));
  ds.label = ds.label || ds.name;
  return [ds, dir];
}

// The app's own DS profile (apps[].ds) replaces the top-level one; unknown app or no apps[].ds: unchanged.
function forApp(cfg, appId) {
  if (!cfg || !appId) return cfg;
  const a = (cfg.apps || []).find(x => x.id === appId);
  const out = { ...cfg, _app: appId };
  if (a && a.ds && a.ds !== cfg.ds) { out.ds = a.ds; [out._ds, out._dsDir] = readProfile(cfg._root, a.ds); }
  return out;
}

function load(start, require = true, app = null) {
  const root = findRoot(start);
  if (!root) {
    if (require) { console.error('ERROR: kit.config.json not found in this folder or any parent. Run the kickoff skill first.'); process.exit(1); }
    return null;
  }
  const cfg = merge(DEFAULTS, JSON.parse(fs.readFileSync(path.join(root, 'kit.config.json'), 'utf8')));
  cfg._root = root; cfg._app = null;
  [cfg._ds, cfg._dsDir] = readProfile(root, cfg.ds);
  return app ? forApp(cfg, app) : cfg;
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

// How an app loads the DS CSS (same as kitconf.py css_load): ds.json > css.load / linkPath, apps[].css overrides.
function cssLoad(cfg, appId) {
  const css = (cfg && cfg._ds && cfg._ds.css) || {};
  let load = css.load || 'embed', link = css.linkPath || null;
  const a = ((cfg && cfg.apps) || []).find(x => x.id === appId);
  if (a && a.css && typeof a.css === 'object') { load = a.css.load || load; link = a.css.linkPath || link; }
  if (load === 'link' && !link && css.bundle && !css.bundle.includes('://')) link = path.basename(css.bundle);
  return { load, linkPath: load === 'link' ? link : null };
}

// Lines of apps[].pageContract (same as kitconf.py page_contract): what every page must do for the app shell. Default [].
function pageContract(cfg, appId) {
  const a = ((cfg && cfg.apps) || []).find(x => x.id === appId);
  const v = (a && a.pageContract) || [];
  return typeof v === 'string' ? [v] : v.map(String);
}

module.exports = { load, forApp, findRoot, t, versionLabel, dsPath, cssLoad, pageContract, KIT_ROOT };
