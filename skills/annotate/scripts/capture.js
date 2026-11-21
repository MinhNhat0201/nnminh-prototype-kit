#!/usr/bin/env node
/* Capture prototype screens from a manifest, for the spec, the handoff package and the Figma wireflow (annotate skill).

   node capture.js <manifest.js|manifest.json> <out dir> [base URL] [--only S01,S02]

   base URL   where the prototype is served (default http://localhost:8791/). Serve over HTTP, not file://:
              multi-page apps share files and hand data over through sessionStorage/localStorage.
   --only     capture only these screens; earlier screens of the same flow still run (they set up the state).

   Manifest (format in references/manifest.md):
     { viewport, scale (device scale factor, default 2; use 3 for phone frames),
       frames: { F: "<iframe selector>", ... }   pin and step selectors "F|<sel>" act inside that frame,
       att: "<folder of sample files for 'files' steps>",
       screens: [ { id, name, flow, cont, viewport, scale, fullPage, steps, pins: [{ref, sel}], next: [{to, action, trigger, condition}] } ] }

   Writes <id>.png and screens.json (page, hash, steps, viewport, pins with computed style and matching DS token names,
   exits, console errors). screens.json is merged with the previous run, so --only keeps the other screens.
   Token names come from ds.json > tokens.prefix and tokens.roles (via scripts/kitconf.js). */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const kit = require(path.resolve(__dirname, '../../../scripts/kitconf.js'));

const die = m => { console.error('ERROR: ' + m); process.exit(1); };
const argv = process.argv.slice(2);
if (!argv.length || argv.includes('--help') || argv.includes('-h')) {
  console.log('Usage: node capture.js <manifest.js|manifest.json> <out dir> [base URL] [--only S01,S02]');
  process.exit(argv.length ? 0 : 1);
}
const oi = argv.indexOf('--only');
const only = oi >= 0 ? (argv[oi + 1] || '').split(',').filter(Boolean) : null;
const pos = argv.filter((a, i) => !(oi >= 0 && (i === oi || i === oi + 1)));
const [manifestFile, OUT] = pos;
const BASE = (pos[2] || 'http://localhost:8791/').replace(/\/?$/, '/');
if (!manifestFile || !OUT) die('manifest and out dir are required. Run with --help.');
const mPath = path.resolve(manifestFile);
if (!fs.existsSync(mPath)) die('manifest not found: ' + manifestFile);
const M = mPath.endsWith('.json') ? JSON.parse(fs.readFileSync(mPath, 'utf8')) : require(mPath);
if (!Array.isArray(M.screens)) die('manifest has no screens[]');

const cfg = kit.load(process.cwd(), false) || kit.load(path.dirname(mPath));
if (!cfg._ds) die(`DS profile not found (kit.config.json > ds = ${cfg.ds}).`);
const TOK = { prefix: cfg._ds.tokens.prefix, roles: cfg._ds.tokens.roles || {}, scale: cfg._ds.tokens.scale || {} };

// Runs in the page. Computed style of el plus the DS token names whose value is the same.
// For each property only tokens of the matching role are returned; without one, primitives (prefix, no role) are returned.
function tokenStyle(el, T) {
  const rs = getComputedStyle(document.documentElement);
  const probe = document.createElement('span');
  probe.style.cssText = 'position:absolute;visibility:hidden;display:block';
  document.body.appendChild(probe);
  const norm = (prop, v) => { probe.style[prop] = ''; probe.style[prop] = v; return getComputedStyle(probe)[prop]; };
  const names = new Set();
  for (const sh of document.styleSheets) {
    let rules; try { rules = sh.cssRules; } catch (e) { continue; }
    const walk = list => { for (const r of list) { if (r.style) for (const n of r.style) if (n.startsWith(T.prefix)) names.add(n); if (r.cssRules) walk(r.cssRules); } };
    walk(rules);
  }
  const color = {}, length = {}, shadow = {};
  for (const n of names) {
    const v = rs.getPropertyValue(n).trim(); if (!v) continue;
    let map, key;
    if (/^(#|rgb|hsl|oklch|oklab|lab|lch|color-mix|color\()/.test(v)) { map = color; key = norm('color', v); }
    else if (/^-?[\d.]+(px|rem|em)$/.test(v)) { map = length; key = norm('width', v); }
    else if (/(px|rem).*(#|rgb|hsl|oklch)|(#|rgb|hsl|oklch).*(px|rem)/.test(v)) { map = shadow; key = norm('boxShadow', v); }
    else continue;                                     // font names, motion and other values are not mapped
    if (!key || key === 'auto' || key === 'none') continue;
    (map[key] = map[key] || []).push(n);
  }
  probe.remove();
  const roleList = Object.values(T.roles).concat(Object.values(T.scale));
  const isPrimitive = n => !roleList.some(p => n.startsWith(p));
  const pick = (map, v, roles) => {
    const all = map[v] || [];
    const pre = roles.map(r => T.roles[r] || T.scale[r]).filter(Boolean);
    const sem = all.filter(n => pre.some(p => n.startsWith(p)));
    return (sem.length ? sem : all.filter(isPrimitive)).slice(0, 3);
  };
  const c = getComputedStyle(el), b = el.getBoundingClientRect();
  return {
    props: { color: c.color, backgroundColor: c.backgroundColor, borderColor: c.borderTopColor, borderWidth: c.borderTopWidth,
      borderRadius: c.borderTopLeftRadius, fontSize: c.fontSize, fontWeight: c.fontWeight, lineHeight: c.lineHeight,
      padding: c.padding, gap: c.gap, boxShadow: c.boxShadow, width: Math.round(b.width) + 'px', height: Math.round(b.height) + 'px' },
    tokens: { color: pick(color, c.color, ['text', 'icon']), backgroundColor: pick(color, c.backgroundColor, ['bg']),
      borderColor: c.borderTopWidth === '0px' ? [] : pick(color, c.borderTopColor, ['stroke']), borderRadius: pick(length, c.borderTopLeftRadius, ['radius']),
      fontSize: pick(length, c.fontSize, ['fontSize']), lineHeight: pick(length, c.lineHeight, ['lineHeight']),
      gap: pick(length, c.gap, ['spacing']), padding: pick(length, c.paddingTop, ['spacing']),
      boxShadow: c.boxShadow === 'none' ? [] : pick(shadow, c.boxShadow, ['shadow']) },
    cls: el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className,
    tag: el.tagName.toLowerCase(), text: (el.innerText || '').trim().slice(0, 120),
  };
}

const pct = (v, total) => +(v / total * 100).toFixed(1);

(async () => {
  const browser = await chromium.launch();
  fs.mkdirSync(OUT, { recursive: true });
  const prevFile = path.join(OUT, 'screens.json');
  const prev = fs.existsSync(prevFile) ? JSON.parse(fs.readFileSync(prevFile, 'utf8')) : [];
  const res = []; let cur = null; let failed = 0;
  const flowOf = id => (M.screens.find(x => x.id === id) || {}).flow;
  for (const s of M.screens) {
    if (only && !only.includes(s.id) && !(s.flow && only.some(o => flowOf(o) === s.flow))) continue;
    const vp = s.viewport || M.viewport || { width: 1280, height: 800 };
    const same = s.cont && cur && cur.flow && cur.flow === s.flow;
    if (!same) {
      if (cur) await cur.ctx.close();
      // 2x so text stays sharp when BA and developers zoom; phone frames use 3.
      const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: s.scale || M.scale || 2 });
      const page = await ctx.newPage(); const errors = [];
      page.on('pageerror', e => errors.push(String(e)));
      page.on('console', m => { if (m.type() === 'error' && !/font/i.test(m.text())) errors.push(m.text()); });
      cur = { ctx, page, errors, flow: s.flow };
    } else await cur.page.setViewportSize(vp);
    const page = cur.page;
    const FR = M.frames || {};
    const scope = key => {
      if (!key) return page;
      if (!FR[key]) throw new Error(`frame "${key}" is not declared in manifest.frames`);
      return page.frameLocator(FR[key]);
    };
    const locate = sel => {
      const m = /^([A-Za-z]\w*)\|(.*)$/.exec(sel);
      return m && FR[m[1]] ? scope(m[1]).locator(m[2]).first() : page.locator(sel).first();
    };
    try {
      for (const st of s.steps || []) {
        const T = st.timeout || 8000;
        const L = sel => (st.in ? scope(st.in).locator(sel).first() : locate(sel));
        if (st.goto) await page.goto(BASE + String(st.goto).replace(/^\//, ''));
        else if (st.reset) { await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); }); await page.reload(); await page.waitForTimeout(700); }
        else if (st.hover) await L(st.hover).hover({ timeout: T });
        else if (st.click) await L(st.click).click({ timeout: T });
        else if (st.fill) await L(st.fill[0]).fill(st.fill[1], { timeout: T });
        else if (st.type) { if (Array.isArray(st.type)) { await L(st.type[0]).click({ timeout: T }); await page.keyboard.type(st.type[1]); } else await page.keyboard.type(st.type); }
        else if (st.press) await page.keyboard.press(st.press);
        else if (st.eval) await page.evaluate(st.eval);
        else if (st.wait) await page.waitForTimeout(st.wait);
        else if (st.waitFor) await L(st.waitFor).waitFor({ timeout: T });
        else if (st.waitEval) await page.waitForFunction(st.waitEval, null, { timeout: T });
        else if (st.waitUrl) await page.waitForURL(new RegExp(st.waitUrl), { timeout: T });
        else if (st.files) {
          const [fc] = await Promise.all([page.waitForEvent('filechooser', { timeout: T }), L(st.files[0]).click({ timeout: T })]);
          await fc.setFiles(st.files[1].map(f => path.resolve(path.dirname(mPath), M.att || 'att', f)));
        } else throw new Error('unknown step ' + JSON.stringify(st));
      }
    } catch (e) {
      failed++;
      console.log(`${s.id} FAILED at steps: ${String(e.message || e).split('\n')[0]}`);
      continue;
    }
    await page.waitForTimeout(250);
    const sy = s.fullPage ? await page.evaluate(() => scrollY) : 0;
    const imgH = s.fullPage ? await page.evaluate(() => document.documentElement.scrollHeight) : vp.height;
    const where = async sel => {
      if (!sel) return null;
      const loc = locate(sel);
      const box = await loc.boundingBox({ timeout: 1500 }).catch(() => null); // short wait: fast transitions move on
      return box && box.width > 0 ? { box, loc } : null;
    };
    const pins = [];
    for (const p of s.pins || []) {
      const sel = p.sel || p.selector;
      const w = await where(sel);
      if (!w) { pins.push({ ref: p.ref, sel, found: false }); continue; }
      pins.push({ ref: p.ref, sel, found: true,
        leftPct: pct(w.box.x + Math.min(w.box.width / 2, w.box.width - 8), vp.width),
        topPct: pct(w.box.y + sy + w.box.height / 2, imgH),
        style: await w.loc.evaluate(tokenStyle, TOK).catch(() => null) });
    }
    const exits = [];
    for (const n of s.next || []) {
      const w = await where(n.trigger);
      exits.push({ to: n.to, action: n.action, condition: n.condition || '', found: !!w,
        leftPct: w ? pct(w.box.x + w.box.width / 2, vp.width) : null,
        topPct: w ? pct(w.box.y + sy + w.box.height / 2, imgH) : null });
    }
    if (!only || only.includes(s.id)) {
      await page.screenshot({ path: path.join(OUT, s.id + '.png'), fullPage: !!s.fullPage });
      const u = new URL(page.url());
      const basePath = new URL(BASE).pathname.replace(/^\//, '');
      res.push({ id: s.id, name: s.name, flow: s.flow || null, cont: !!s.cont,
        page: u.pathname.replace(/^\//, '').replace(basePath, ''), hash: u.hash, viewport: vp, scale: s.scale || M.scale || 2,
        steps: s.steps || [], pins, exits, errors: cur.errors.slice() });
      const missing = pins.filter(p => !p.found).map(p => p.sel);
      console.log(s.id, missing.length ? 'pins not found: ' + missing.join(' ; ') : 'ok', cur.errors.length ? 'CONSOLE ' + cur.errors.join(' | ') : '');
    }
  }
  if (cur) await cur.ctx.close();
  await browser.close();
  const merged = prev.filter(p => !res.find(r => r.id === p.id)).concat(res);
  const order = M.screens.map(s => s.id);
  merged.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
  // Cross-page edge: the target screen lives in another file than the source screen.
  const byId = Object.fromEntries(merged.map(r => [r.id, r]));
  for (const r of merged) for (const e of r.exits || []) e.xpage = !!(byId[e.to] && byId[e.to].page !== r.page);
  fs.writeFileSync(prevFile, JSON.stringify(merged, null, 1));
  console.log(`Wrote ${res.length} screen(s) to ${OUT} (screens.json has ${merged.length}).` + (failed ? ` ${failed} failed.` : ''));
  if (failed) process.exit(1);
})().catch(e => die(String(e && e.message || e)));
