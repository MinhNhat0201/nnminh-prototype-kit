#!/usr/bin/env node
/* Capture prototype screens from a manifest, for the spec, the handoff package and the Figma wireflow (annotate skill).

   node capture.js <manifest.js|manifest.json> <out dir> [base URL] [--only S01,S02] [--app <app id>]

   base URL   where the prototype is served (default http://localhost:8791/). Serve over HTTP, not file://:
              multi-page apps share files and hand data over through sessionStorage/localStorage.
   --only     capture only these screens; the earlier screens they continue from (same flow, cont) still run to set up
              the state, but nothing else runs and no other image is written.
   --app      the app whose DS profile names the tokens (apps[].ds); default manifest.app, else the top-level ds.
   --selftest run the checks of the manifest helpers (no browser).

   Manifest (format in references/manifest.md):
     { app, viewport, scale (device scale factor, default 2; use 3 for phone frames), timeout (ms a step waits, default 8000),
       frames: { F: "<iframe selector>", ... }   pin and step selectors "F|<sel>" act inside that frame,
       att: "<folder of sample files for 'files' steps>",
       neutral: true | false | { pointer, blur }   before each screenshot move the pointer off the page and blur a focused
                  button or link (default on; a screen with a hover step keeps its pointer; editable fields and open
                  menus, listboxes and dialogs keep their focus). A screen may set its own neutral.
       screens: [ { id, name, flow, cont, viewport, scale, fullPage, at, neutral, steps, pins: [{ref, sel}], next: [{to, action, trigger, condition}] } ] }
   Steps: goto (reload: true also reloads, for a hash-only change; noWait: true returns at the start of navigation),
          reload (reload the page, noWait as goto), reset, click, hover, fill, type, press, eval, wait, waitFor, waitEval,
          waitUrl, files.
   at: <ms>   screenshot that many ms after the last step, before the usual settle and before pins are measured,
              for short states (a skeleton shown for 500 ms). Combine with noWait on the goto or reload.

   Writes <id>.png and screens.json (page, search = query of the page or of the last goto, hash, steps, viewport, pins with computed style and matching DS token names,
   exits, console errors). screens.json is merged with the previous run, so --only keeps the other screens.
   Token names come from ds.json > tokens.prefix and tokens.roles (via scripts/kitconf.js).
   Style notes: border colour and its token are recorded only when the border is wider than 0 (no stroke token for an
   element without a border). */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const kit = require(path.resolve(__dirname, '../../../scripts/kitconf.js'));

const die = m => { console.error('ERROR: ' + m); process.exit(1); };
const argv = process.argv.slice(2);
if (!argv.length || argv.includes('--help') || argv.includes('-h')) {
  console.log('Usage: node capture.js <manifest.js|manifest.json> <out dir> [base URL] [--only S01,S02] [--app <app id>]\n' +
    '       node capture.js --selftest');
  process.exit(argv.length ? 0 : 1);
}

// Legacy step aliases: "<frame letter in lower case><step>" acts inside that frame, e.g. {fclick: sel} = {click: sel, in: 'F'}.
// "<x>wait" with a selector = {waitFor: sel, in: 'X'}. Kept so older manifests run unchanged.
const ALIAS_STEPS = ['click', 'hover', 'fill', 'type', 'waitFor', 'wait', 'files'];
function normStep(st) {
  if (!st || typeof st !== 'object') return st;
  for (const k of Object.keys(st)) {
    const m = /^([a-z])([a-z][A-Za-z]*)$/.exec(k);
    if (!m || !ALIAS_STEPS.includes(m[2]) || ['click', 'hover', 'fill', 'type', 'files', 'wait'].includes(k)) continue;
    const rest = Object.fromEntries(Object.entries(st).filter(([x]) => x !== k));
    const step = m[2] === 'wait' && typeof st[k] === 'string' ? 'waitFor' : m[2];
    return { ...rest, [step]: st[k], in: m[1].toUpperCase() };
  }
  return st;
}
// Pointer and focus reset before a screenshot (K-B1): {pointer, blur}. Screen value over manifest value; a screen that
// hovers on purpose keeps its pointer.
function neutralOpts(M, s) {
  const v = s.neutral !== undefined ? s.neutral : M.neutral;
  const o = v === false ? { pointer: false, blur: false } : { pointer: true, blur: true, ...(typeof v === 'object' && v ? v : {}) };
  if ((s.steps || []).map(normStep).some(st => st && st.hover)) o.pointer = false;
  return o;
}
// Runs in the page: blur a focused button or link, never an editable field or an element inside an open popup.
function blurSafe() {
  const el = document.activeElement;
  if (!el || el === document.body || !el.blur) return false;
  if (el.isContentEditable || /^(input|textarea|select)$/i.test(el.tagName)) return false;
  if (el.closest('[role=menu],[role=listbox],[role=dialog],[role=combobox],dialog[open],[popover]')) return false;
  if (!el.closest('a,button,[role=button],[role=tab],summary')) return false;
  el.blur();
  return true;
}
// Every frame a selector ("F|sel") or a step ("in": "F") names must be declared in manifest.frames.
function undeclaredFrames(M) {
  const FR = M.frames || {}, bad = [];
  const sel = (where, v) => {
    for (const x of [].concat(v || [])) {
      const m = typeof x === 'string' && /^([A-Za-z]\w*)\|/.exec(x);
      if (m && !FR[m[1]]) bad.push(`${where}: "${x}" uses frame ${m[1]}`);
    }
  };
  for (const s of M.screens || []) {
    (s.steps || []).forEach((st0, i) => {
      const st = normStep(st0);
      if (st && st.in && !FR[st.in]) bad.push(`${s.id} step ${i + 1}: in "${st.in}"`);
      for (const k of ['click', 'hover', 'waitFor']) if (st && typeof st[k] === 'string') sel(`${s.id} step ${i + 1}`, st[k]);
      for (const k of ['fill', 'type', 'files']) if (st && Array.isArray(st[k])) sel(`${s.id} step ${i + 1}`, st[k][0]);
    });
    (s.pins || []).forEach(p => sel(`${s.id} pin ${p.ref || ''}`, p.sel || p.selector));
    (s.next || []).forEach(n => sel(`${s.id} exit to ${n.to}`, n.trigger));
  }
  return bad;
}
// Screens to run for --only: each asked screen plus the screens it continues from (same flow, cont: 1).
function runSet(M, only) {
  if (!only) return null;
  const S = M.screens, need = new Set();
  for (const id of only) {
    let i = S.findIndex(x => x.id === id);
    if (i < 0) continue;
    need.add(S[i].id);
    while (S[i].cont && S[i].flow) {
      let j = i - 1;
      while (j >= 0 && S[j].flow !== S[i].flow) j--;
      if (j < 0) break;
      need.add(S[j].id); i = j;
    }
  }
  return need;
}
if (argv.includes('--selftest')) {
  const assert = require('assert');
  assert.deepStrictEqual(normStep({ fclick: '#a', timeout: 9 }), { timeout: 9, click: '#a', in: 'F' });
  assert.deepStrictEqual(normStep({ ewait: '.card' }), { waitFor: '.card', in: 'E' });
  assert.deepStrictEqual(normStep({ wait: 300 }), { wait: 300 });
  assert.deepStrictEqual(normStep({ click: '#b' }), { click: '#b' });
  const M = { frames: { F: 'iframe' }, screens: [
    { id: 'S01', flow: 'f1', steps: [{ fclick: '#x' }], pins: [{ ref: 'R1', sel: 'F|.ok' }] },
    { id: 'S02', flow: 'f2', steps: [{ eclick: '#y' }] },
    { id: 'S03', flow: 'f1', cont: 1, steps: [], pins: [{ ref: 'R2', sel: 'G|.no' }] },
    { id: 'S04', flow: 'f1', cont: 1, steps: [] }] };
  const bad = undeclaredFrames(M);
  assert.strictEqual(bad.length, 2, bad.join('; '));
  assert.deepStrictEqual([...runSet(M, ['S03'])].sort(), ['S01', 'S03']);
  assert.deepStrictEqual([...runSet(M, ['S02'])], ['S02']);
  assert.deepStrictEqual(neutralOpts({}, { steps: [{ click: '#a' }] }), { pointer: true, blur: true });
  assert.deepStrictEqual(neutralOpts({}, { steps: [{ ehover: '#a' }] }), { pointer: false, blur: true });
  assert.deepStrictEqual(neutralOpts({ neutral: false }, { steps: [] }), { pointer: false, blur: false });
  assert.deepStrictEqual(neutralOpts({ neutral: false }, { neutral: { blur: false }, steps: [] }), { pointer: true, blur: false });
  console.log('capture.js selftest OK');
  process.exit(0);
}
const oi = argv.indexOf('--only');
const only = oi >= 0 ? (argv[oi + 1] || '').split(',').filter(Boolean) : null;
const ai0 = argv.indexOf('--app');
const pos = argv.filter((a, i) => !(oi >= 0 && (i === oi || i === oi + 1)) && !(ai0 >= 0 && (i === ai0 || i === ai0 + 1)));
const [manifestFile, OUT] = pos;
const BASE = (pos[2] || 'http://localhost:8791/').replace(/\/?$/, '/');
if (!manifestFile || !OUT) die('manifest and out dir are required. Run with --help.');
const mPath = path.resolve(manifestFile);
if (!fs.existsSync(mPath)) die('manifest not found: ' + manifestFile);
const M = mPath.endsWith('.json') ? JSON.parse(fs.readFileSync(mPath, 'utf8')) : require(mPath);
if (!Array.isArray(M.screens)) die('manifest has no screens[]');
const badFrames = undeclaredFrames(M);
if (badFrames.length) die('frame not declared in manifest.frames (add frames: { X: "<iframe selector>" }):\n  ' + badFrames.join('\n  '));
const RUN = runSet(M, only);
if (only && only.some(id => !M.screens.find(s => s.id === id))) die('--only names screens not in the manifest: ' + only.filter(id => !M.screens.find(s => s.id === id)).join(', '));

// The app's own DS profile (apps[].ds) when the manifest names its app (manifest.app) or --app is given.
const ai = argv.indexOf('--app'), APP = (ai >= 0 && argv[ai + 1]) || M.app || null;
const cfg = kit.forApp(kit.load(process.cwd(), false) || kit.load(path.dirname(mPath)), APP);
if (!cfg._ds) die(`DS profile not found (kit.config.json > ds = ${cfg.ds}).`);
const TOK = { prefix: cfg._ds.tokens.prefix, roles: cfg._ds.tokens.roles || {}, scale: cfg._ds.tokens.scale || {},
  ignore: cfg._ds.tokens.ignorePrefixes || [] };

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
  for (const n of [...names]) if ((T.ignore || []).some(p => n.startsWith(p))) names.delete(n);   // ds.json > tokens.ignorePrefixes
  const color = {}, length = {}, shadow = {};
  for (const n of names) {
    const v = rs.getPropertyValue(n).trim(); if (!v) continue;
    if (/^(0(px|rem|em)?|none|normal|auto|transparent)$/.test(v)) continue;
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
  // 0, none, normal, auto, transparent: no token describes "nothing" (a primitive that happens to be 0 is noise)
  const EMPTY = /^(0(px|rem|em)?|none|normal|auto|transparent|rgba\(0, 0, 0, 0\))$/;
  const pick = (map, v, roles) => {
    if (v == null || EMPTY.test(String(v).trim())) return [];
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
  for (const s of M.screens) {
    if (RUN && !RUN.has(s.id)) continue;
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
    let lastQuery = (same && cur.lastQuery) || '';   // a screen that continues its flow keeps the query of the earlier goto
    try {
      for (const st of (s.steps || []).map(normStep)) {
        if (st.goto) { const q = /\?[^#]*/.exec(String(st.goto)); lastQuery = cur.lastQuery = q ? q[0] : ''; }
        const T = st.timeout || M.timeout || 8000;   // validate.js uses the same default (plan.timeout)
        const L = sel => (st.in ? scope(st.in).locator(sel).first() : locate(sel));
        // noWait: return when navigation starts (K-F11); reload: a hash-only goto keeps the document, so reload it (K-F10)
        const nav = { waitUntil: st.noWait ? 'commit' : 'load' };
        if (st.goto) { await page.goto(BASE + String(st.goto).replace(/^\//, ''), nav); if (st.reload) await page.reload(nav); }
        else if (st.reload) await page.reload(nav);
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
    const nt = neutralOpts(M, s);
    if (nt.pointer) await page.mouse.move(-1, -1);   // off the page: no element keeps a hover style (K-B1)
    if (nt.blur) {
      await page.evaluate(blurSafe).catch(() => false);
      for (const k of Object.keys(FR)) await page.frameLocator(FR[k]).locator(':root').evaluate(blurSafe, null, { timeout: 500 }).catch(() => false);
    }
    const shoot = !only || only.includes(s.id);
    const shotFile = path.join(OUT, s.id + '.png');
    if (s.at != null) { await page.waitForTimeout(+s.at || 0); if (shoot) await page.screenshot({ path: shotFile, fullPage: !!s.fullPage }); }
    else await page.waitForTimeout(250);
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
    if (shoot) {
      if (s.at == null) await page.screenshot({ path: shotFile, fullPage: !!s.fullPage });
      const u = new URL(page.url());
      const basePath = new URL(BASE).pathname.replace(/^\//, '');
      res.push({ id: s.id, name: s.name, flow: s.flow || null, cont: !!s.cont, ...(s.at != null ? { at: +s.at } : {}),
        page: u.pathname.replace(/^\//, '').replace(basePath, ''), search: u.search || lastQuery, hash: u.hash, viewport: vp, scale: s.scale || M.scale || 2,
        steps: (s.steps || []).map(normStep), pins, exits, errors: cur.errors.slice() });
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
