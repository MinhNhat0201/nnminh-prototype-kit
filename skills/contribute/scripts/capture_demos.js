// Capture a demo image of each local component from the running app.
//
//   python3 -m http.server 8765 &            # from the project root (html stack), or run the app dev server
//   node <kit>/skills/contribute/scripts/capture_demos.js [--out DIR] [id ...]
//
// Env: APP_BASE (default http://localhost:8765), PLAYWRIGHT_PATH (module path, default "playwright").
// Output: <DIR>/<id>.png, default <folder of kit.config.json > local.registry>/local-demos/.
//
// Each registry entry may have a "demo" field:
//   { "url": "/apps/acme-web/index.html#/settings"  (optional; default /<app path>/<app entry>, or <path> under it),
//     "path": "settings/index.html",                (optional, file inside the app)
//     "steps": [ ... ], "selector": "css", "clip": [x, y, w, h], "pad": 16, "max": [1200, 640],
//     "viewport": [1440, 900], "mode": "light", "load": 1800 }
// Steps, run in order on the opened page:
//   { "css": ".x-pill", "text": "All", "i": 0 }     click the i-th element matching css (filtered by text)
//   { "click": [x, y] }  { "type": "css", "value": "..." }  { "hover": "css" }  { "press": "Escape" }  { "wait": 500 }
// Without "selector" or "clip": the largest visible outermost element that carries one of the entry's classes.
// Entries without "demo", and entries in status replaced or removed, are skipped.
const fs = require('fs');
const path = require('path');
const { load } = require(path.resolve(__dirname, '../../../scripts/kitconf.js'));

const cfg = load();
const args = process.argv.slice(2);
if (args.includes('--help') || args.includes('-h')) {
  console.log(fs.readFileSync(__filename, 'utf8').split('\n').filter(l => l.startsWith('//')).map(l => l.slice(3)).join('\n'));
  process.exit(0);
}
const oi = args.indexOf('--out');
const regPath = path.join(cfg._root, cfg.local.registry);
const OUT = oi >= 0 ? path.resolve(args[oi + 1]) : path.join(path.dirname(regPath), 'local-demos');
const ONLY = args.filter((x, i) => oi < 0 || (i !== oi && i !== oi + 1));
const BASE = (process.env.APP_BASE || 'http://localhost:8765').replace(/\/$/, '');
let chromium;
try { ({ chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright')); }
catch (e) { console.error('ERROR: Playwright not found. Set PLAYWRIGHT_PATH to the playwright module.'); process.exit(1); }
if (!fs.existsSync(regPath)) { console.error('ERROR: registry not found: ' + cfg.local.registry); process.exit(1); }
const reg = JSON.parse(fs.readFileSync(regPath, 'utf8'));
const apps = Object.fromEntries(cfg.apps.map(a => [a.id, a]));

function urlOf(e) {
  if (e.demo.url) return /^https?:/.test(e.demo.url) ? e.demo.url : BASE + e.demo.url;
  const a = apps[e.app];
  if (!a) throw new Error('app not declared in kit.config.json: ' + e.app);
  return BASE + '/' + a.path.replace(/^\/|\/$/g, '') + '/' + (e.demo.path || a.entry || 'index.html');
}

async function run(pg, steps) {
  for (const st of steps || []) {
    if (st.press) { await pg.keyboard.press(st.press); await pg.waitForTimeout(st.wait || 300); }
    else if (st.click) { await pg.mouse.click(st.click[0], st.click[1]); await pg.waitForTimeout(st.wait || 700); }
    else if (st.hover) {
      // move in small steps so mousemove / mouseover listeners run as for a real user
      const bb = await pg.locator(st.hover).first().boundingBox();
      if (!bb) throw new Error('nothing to hover: ' + st.hover);
      const cx = bb.x + bb.width / 2, cy = bb.y + bb.height / 2;
      await pg.mouse.move(cx - 8, cy - 8);
      await pg.mouse.move(cx, cy, { steps: 6 });
      await pg.waitForTimeout(st.wait || 900);
    }
    else if (st.type) { await pg.locator(st.type).first().fill(st.value || ''); await pg.waitForTimeout(st.wait || 300); }
    else if (st.css) {
      let loc = pg.locator(st.css);
      if (st.text) loc = loc.filter({ hasText: st.text });
      const n = await loc.count();
      if (!n) throw new Error('no element for step ' + JSON.stringify(st));
      await loc.nth(Math.min(st.i || 0, n - 1)).click({ timeout: 3000 });
      await pg.waitForTimeout(st.wait || 450);
    }
    else if (st.wait) await pg.waitForTimeout(st.wait);
  }
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch();
  let ok = 0; const fail = [];
  for (const e of reg.components || []) {
    if (!e.demo || ['replaced', 'removed'].includes(e.status) || (ONLY.length && !ONLY.includes(e.id))) continue;
    // one context per entry so mode, theme or storage of one entry never leaks into the next
    const vp = e.demo.viewport || [1440, 900];
    const ctx = await b.newContext({ viewport: { width: vp[0], height: vp[1] }, deviceScaleFactor: 2, colorScheme: e.demo.mode || 'light' });
    const pg = await ctx.newPage();
    const errs = [];
    pg.on('pageerror', x => errs.push(String(x)));
    try {
      await pg.goto(urlOf(e));
      await pg.waitForTimeout(e.demo.load || 1800);
      await run(pg, e.demo.steps);
      let clip = null;
      if (e.demo.clip) clip = { x: e.demo.clip[0], y: e.demo.clip[1], width: e.demo.clip[2], height: e.demo.clip[3] };
      else clip = await pg.evaluate(({ classes, selector, pad, max }) => {
        const vis = x => { const r = x.getBoundingClientRect(), cs = getComputedStyle(x); return r.width > 6 && r.height > 6 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
        let el = null;
        if (selector) el = [...document.querySelectorAll(selector)].find(vis) || null;
        else if (classes.length) {
          const sel = classes.map(c => '.' + CSS.escape(c)).join(',');
          const all = [...document.querySelectorAll(sel)].filter(vis);
          const top = all.filter(x => !x.parentElement || !x.parentElement.closest(sel));
          let best = 0;
          (top.length ? top : all).forEach(x => { const r = x.getBoundingClientRect(); const s = Math.min(r.width, 900) * Math.min(r.height, 600); if (s > best) { best = s; el = x; } });
        }
        if (!el) return null;
        el.scrollIntoView({ block: 'nearest' });
        const r = el.getBoundingClientRect(), p = pad == null ? 16 : pad;
        const x0 = Math.max(0, r.left - p), y0 = Math.max(0, r.top - p);
        return { x: x0, y: y0, width: Math.min(r.width + 2 * p, innerWidth - x0, max[0]), height: Math.min(r.height + 2 * p, innerHeight - y0, max[1]) };
      }, { classes: e.classes || [], selector: e.demo.selector || null, pad: e.demo.pad, max: e.demo.max || [1200, 640] });
      if (!clip) throw new Error('no visible element to capture');
      await pg.screenshot({ path: path.join(OUT, e.id + '.png'), clip });
      ok++;
      if (errs.length) console.log('  NOTE: pageerror on', e.id + ':', errs[0].slice(0, 100));
    } catch (err) {
      fail.push(e.id + ': ' + String(err.message).split('\n')[0].slice(0, 140));
    }
    await ctx.close();
  }
  await b.close();
  console.log('Captured ' + ok + ' image(s) in ' + path.relative(cfg._root, OUT) + '; ' + fail.length + ' failed');
  fail.forEach(f => console.log('ERROR: ' + f));
  process.exit(fail.length ? 1 : 0);
})();
