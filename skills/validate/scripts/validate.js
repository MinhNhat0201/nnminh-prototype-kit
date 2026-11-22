#!/usr/bin/env node
// Browser checks for a prototype, driven by a validation plan. Called by validation.py run; usable alone.
//
//   node validate.js --url <file:// or http:// entry> --plan plan.json --out <run dir>
//                    [--viewports 390,768,1280] [--modes light,dark] [--mode-attr data-mode] [--touch-min 44]
//                    [--theming '{"brand":"data-brand"}'] [--set-theme '<JS body using key, value>'] [--axe <axe.min.js or folder>]
//                    [--waive '["#shell"]'] [--parity]
//   node validate.js --discover --url <served page> [--content-root 'main, #app, [role=main]']
//
// --discover: open the page, let its scripts run, and print one JSON line read from the rendered DOM (for validation.py
// init --url, so routes and ids that a JS bundle builds are found): title and heading, hash routes (a[href^="#/"],
// data-route / data-href / data-to attributes, and the hash a tab or nav button sets when clicked), and stable selectors
// (ids, data-testid, aria-label) of visible elements inside the content root: the first selector of the list that
// matches (plan / config contentRoot), never the shell around it.
// --parity: no axe or focus check; every view also records a snapshot (visible text lines, interactive elements by
// role and name, aria states) and every flow its URL after each step and localStorage at the end (validation.py parity).
//
// plan.prepare (a JS string, or {js, reload: true}) runs once after every page load of a screen and a flow, before its
// own steps and prepare (for example to dismiss a shell overlay); reload: true reloads the page after it.
// Before each screen and flow an http(s) URL is checked first: when the server does not answer, the run stops with one
// ERROR line and exit code 2 (results so far are written, with "aborted").
//
// Screens may carry steps (same vocabulary as flows and as the capture manifest: goto, reset, click, hover, fill,
// type, select, press, eval, reload, wait, waitFor, waitEval, waitUrl, files, expect*; "in": "F" or "F|sel" act inside the
// iframe plan.frames.F) and viewports (only these widths). A step without "timeout" waits plan.timeout, else 8000 ms
// (the capture.js default). Not reported: text for screen readers only, hidden file inputs, links inside a sentence.
// "reload" (or goto with reload: true) reloads the page and waits for load: a goto that only changes the hash does not.
//
// States: objects {name, prepare, theme: {<ds.json theming key>: value}, textScale: 2, axe: false} or named strings:
// "<theming key>=<value>" (e.g. "brand=ocean": sets ds.json > theming.brand.attr) and "text=200%" (root font size x2).
// plan.states are added to every screen. Theme values (and dark mode) are set with --set-theme when given (a JS body run
// in the page with key and value), else by setting the theming attribute on <html>. axe runs on every state of the plan
// (default, prepared, named), at the widest viewport; a state with "axe": false (or a screen with "axe": false) opts out;
// plan.axe / screen.axe {include: [sel], exclude: [sel]} limit it.
//
// For every screen x state x viewport x mode: page errors and console errors, horizontal overflow,
// accessibility (axe-core, when installed), keyboard focus visibility, touch targets on phones, clipped text,
// and a screenshot. Then every flow in the plan, step by step. Writes <out>/results.json and <out>/shots/*.png.
// Chromium is assumed installed; this script never runs `playwright install`. It never edits the app.
'use strict';
const fs = require('fs');
const path = require('path');

let chromium;
try { ({ chromium } = require('playwright')); } catch (e) {
  console.log('ERROR: playwright is not available (npm i -D playwright, Chromium installed separately)'); process.exit(1);
}

function args() {
  const a = {}, v = process.argv.slice(2);
  for (let i = 0; i < v.length; i++) if (v[i].startsWith('--')) a[v[i].slice(2)] = v[i + 1] && !v[i + 1].startsWith('--') ? v[++i] : true;
  return a;
}
const A = args();
if (A.help || !A.url || (!A.discover && (!A.plan || !A.out))) {
  console.log('usage: node validate.js --url <entry URL> --plan plan.json --out <dir> [--viewports 390,768,1280] [--modes light,dark] [--mode-attr data-mode] [--touch-min 44] [--project <dir>] [--theming <json>] [--set-theme <js>] [--axe <path>] [--waive <json>] [--parity]\n' +
    '       node validate.js --discover --url <served page> [--content-root <selector list>]');
  process.exit(A.help ? 0 : 1);
}
const plan = A.discover ? {} : JSON.parse(fs.readFileSync(A.plan, 'utf8'));
const PARITY = !!A.parity;
const PREP = typeof plan.prepare === 'string' ? { js: plan.prepare } : (plan.prepare || null);
const viewports = String(A.viewports || plan.viewports || '390,768,1280').split(',').map(Number).filter(Boolean);
const modes = String(A.modes || plan.modes || 'light').split(',').filter(Boolean);
const modeAttr = A['mode-attr'] || plan.modeAttr || 'data-mode';
const touchMin = Number(A['touch-min'] || plan.touchMin || 44);
const FRAMES = plan.frames || {};
const THEMING = Object.assign({ mode: modeAttr }, A.theming ? JSON.parse(A.theming) : {});
const SET_THEME = A['set-theme'] || plan.setTheme || null;
const WAIVE = A.waive ? JSON.parse(A.waive) : [];
const out = A.out ? path.resolve(A.out) : null;
if (out) fs.mkdirSync(path.join(out, 'shots'), { recursive: true });

// axe-core is optional: --axe (a file or a folder that holds it), else the project, the kit, and the current folder.
let axePath = null, axeVersion = null;
function axeVer(f) {
  try { const pj = JSON.parse(fs.readFileSync(path.join(path.dirname(f), 'package.json'), 'utf8')); if (pj.name === 'axe-core') return pj.version; } catch (e) { /* header */ }
  const m = /axe v?(\d+\.\d+\.\d+)/.exec(fs.readFileSync(f, 'utf8').slice(0, 400));
  return m ? m[1] : 'unknown';
}
if (A.discover || PARITY) { /* no axe: discovery and parity do not judge accessibility */ }
else if (A.axe) {
  const p = path.resolve(String(A.axe));
  const cands = fs.existsSync(p) && fs.statSync(p).isDirectory()
    ? [path.join(p, 'axe.min.js'), path.join(p, 'axe-core', 'axe.min.js'), path.join(p, 'node_modules', 'axe-core', 'axe.min.js')] : [p];
  axePath = cands.find(f => fs.existsSync(f) && fs.statSync(f).isFile()) || null;
  if (!axePath) { console.log('ERROR: axe-core not found at ' + p + ' (give axe.min.js or a folder with axe-core)'); process.exit(1); }
  axeVersion = axeVer(axePath);
} else {
  for (const base of [A.project, path.resolve(__dirname, '../../..'), process.cwd()].filter(Boolean)) {
    try { axePath = require.resolve('axe-core/axe.min.js', { paths: [base] }); axeVersion = axeVer(axePath); break; } catch (e) { /* next */ }
  }
}

const IGNORE_CONSOLE = /fonts\.(googleapis|gstatic)\.com|Failed to load resource.*(font|woff)|ERR_NAME_NOT_RESOLVED|ERR_INTERNET_DISCONNECTED/i;
const slug = s => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'x';

function urlFor(route) {
  if (!route) return A.url;
  if (/^[a-z]+:/.test(route)) return route;
  const base = A.url.split('#')[0];
  return route.startsWith('#') ? base + route : new URL(route, base).href;
}

async function pageChecks(page, vp) {
  return page.evaluate(({ vp, touchMin }) => {
    const r = { overflow: null, touch: [], clipped: [], hidden: false };
    // Never reported (WCAG 2.5.8 exceptions and content for screen readers only):
    // text for screen readers only (1x1 box, clip or clip-path), a file input hidden behind its button, a link inside a sentence.
    const srOnly = el => { for (let n = el, i = 0; n && n.nodeType === 1 && i < 3; n = n.parentElement, i++) {
      const s = getComputedStyle(n), b = n.getBoundingClientRect();
      if ((b.width <= 1 && b.height <= 1) || (s.clip && s.clip !== 'auto' && /rect\(\s*0/.test(s.clip)) || /inset\(50%|circle\(0/.test(s.clipPath)) return true;
    } return false; };
    const hiddenInput = el => el.matches('input[type=file]') && (parseFloat(getComputedStyle(el).opacity) === 0 || el.getBoundingClientRect().width <= 1);
    const inText = el => getComputedStyle(el).display === 'inline' && !!el.parentElement &&
      [...el.parentElement.childNodes].some(n => n !== el && n.nodeType === 3 && n.textContent.trim().length > 1);
    const vis = el => { const s = getComputedStyle(el), b = el.getBoundingClientRect(); return s.visibility !== 'hidden' && s.display !== 'none' && b.width > 0 && b.height > 0; };
    const name = el => { const id = el.id ? '#' + el.id : ''; const c = (el.getAttribute('class') || '').trim().split(/\s+/).slice(0, 2).filter(Boolean).map(x => '.' + x).join(''); const tx = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 40); return el.tagName.toLowerCase() + id + c + (tx ? ' "' + tx + '"' : ''); };
    const sw = document.documentElement.scrollWidth;
    if (sw > window.innerWidth + 1) {
      const wide = [];
      document.querySelectorAll('body *').forEach(el => {
        const b = el.getBoundingClientRect();
        if (b.right <= window.innerWidth + 1 || b.width === 0) return;
        for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if (o !== 'visible') return; }
        wide.push(name(el) + ' right=' + Math.round(b.right));
      });
      r.overflow = { scrollWidth: sw, width: window.innerWidth, elements: wide.slice(0, 5) };
    }
    if (vp < 600) {
      document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=link], [role=tab], [role=checkbox], [role=switch]').forEach(el => {
        if (!vis(el) || srOnly(el) || hiddenInput(el)) return;
        const b = el.getBoundingClientRect();
        if ((b.width < touchMin || b.height < touchMin) && !inText(el)) r.touch.push(name(el) + ' ' + Math.round(b.width) + 'x' + Math.round(b.height));
      });
      r.touch = r.touch.slice(0, 12);
    }
    document.querySelectorAll('body *').forEach(el => {
      if (r.clipped.length >= 10 || !vis(el) || !el.childNodes.length || srOnly(el)) return;
      const s = getComputedStyle(el);
      if (!/hidden|clip/.test(s.overflowX + s.overflow) || s.textOverflow === 'ellipsis') return;
      const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
      if (own && el.scrollWidth > el.clientWidth + 1) r.clipped.push(name(el));
    });
    return r;
  }, { vp, touchMin });
}

// One step of a screen or a flow. Selectors "F|sel" or "in": "F" act inside the iframe plan.frames.F.
async function runStep(page, s) {
  const T = s.timeout || plan.timeout || 8000;   // same default as capture.js: a screen it captures does not fail here
  const loc = sel => {
    const m = /^([A-Za-z]\w*)\|(.*)$/.exec(sel), key = s.in || (m && FRAMES[m[1]] ? m[1] : null);
    if (key && !FRAMES[key]) throw new Error('frame ' + key + ' is not declared in plan.frames');
    const inner = m && FRAMES[m[1]] ? m[2] : sel;
    return (key ? page.frameLocator(FRAMES[key]) : page).locator(inner).first();
  };
  if (s.goto !== undefined) {   // a goto that only changes the hash keeps the document: reload: true forces a fresh load
    await page.goto(urlFor(s.goto)); if (s.reload) await page.reload({ waitUntil: 'load' }); await page.waitForTimeout(150);
  }
  else if (s.reload) { await page.reload({ waitUntil: 'load' }); await page.waitForTimeout(150); }
  else if (s.reset) { await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); }); await page.reload(); await page.waitForTimeout(300); }
  else if (s.click) await loc(s.click).click({ timeout: T });
  else if (s.hover) await loc(s.hover).hover({ timeout: T });
  else if (s.fill) await loc(s.fill[0]).fill(s.fill[1], { timeout: T });
  else if (s.type) { if (Array.isArray(s.type)) { await loc(s.type[0]).click({ timeout: T }); await page.keyboard.type(s.type[1]); } else await page.keyboard.type(s.type); }
  else if (s.select) await loc(s.select[0]).selectOption(s.select[1], { timeout: T });
  else if (s.press) await page.keyboard.press(s.press);
  else if (s.eval) await page.evaluate(code => (0, eval)(code), s.eval);
  else if (s.wait) await page.waitForTimeout(Math.min(+s.wait, 5000));
  else if (s.waitFor) await loc(s.waitFor).waitFor({ timeout: T });
  else if (s.waitEval) await page.waitForFunction(s.waitEval, null, { timeout: T });
  else if (s.waitUrl) await page.waitForURL(new RegExp(s.waitUrl), { timeout: T });
  else if (s.files) {
    const [fc] = await Promise.all([page.waitForEvent('filechooser', { timeout: T }), loc(s.files[0]).click({ timeout: T })]);
    await fc.setFiles(s.files[1].map(f => path.resolve(plan.att || '.', f)));
  }
  else if (s.expectVisible) await loc(s.expectVisible).waitFor({ state: 'visible', timeout: T });
  else if (s.expectHidden) await loc(s.expectHidden).waitFor({ state: 'hidden', timeout: T });
  else if (s.expectText) {
    const txt = await loc(s.expectText[0]).textContent({ timeout: T });
    if (!txt || !txt.includes(s.expectText[1])) throw new Error('text of ' + s.expectText[0] + ' does not contain "' + s.expectText[1] + '"');
  } else if (s.expectUrl) { if (!page.url().includes(s.expectUrl)) throw new Error('URL ' + page.url() + ' does not contain ' + s.expectUrl); }
  else throw new Error('unknown step ' + JSON.stringify(s));
}

async function focusCheck(page) {
  const missing = [];
  await page.evaluate(() => { document.activeElement && document.activeElement.blur && document.activeElement.blur(); window.scrollTo(0, 0); });
  const seen = new Set();
  for (let i = 0; i < 25; i++) {
    await page.keyboard.press('Tab');
    const info = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      const s = getComputedStyle(el);
      const ring = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || (s.boxShadow && s.boxShadow !== 'none');
      const id = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + ((el.getAttribute('class') || '').trim() ? '.' + el.getAttribute('class').trim().split(/\s+/)[0] : '') +
        ((el.innerText || el.getAttribute('aria-label') || '').trim() ? ' "' + (el.innerText || el.getAttribute('aria-label')).trim().replace(/\s+/g, ' ').slice(0, 30) + '"' : '');
      return { id, ring };
    });
    if (!info) break;
    if (seen.has(info.id)) break;
    seen.add(info.id);
    if (!info.ring) missing.push(info.id);
  }
  return { tabStops: seen.size, missing: missing.slice(0, 10) };
}

// axe-core on the page. scope {include, exclude}: CSS selectors. Each node keeps its target, the waiver selectors it is
// inside (closest), and for color-contrast the colours and ratio axe measured.
async function axeCheck(page, scope) {
  if (!axePath) return null;
  try {
    if (!(await page.evaluate(() => !!window.axe))) await page.addScriptTag({ path: axePath });
    const res = await page.evaluate(async ({ scope, waive }) => {
      const inc = (scope && scope.include) || [], exc = (scope && scope.exclude) || [];
      const ctx = inc.length || exc.length ? Object.assign(inc.length ? { include: inc.map(s => [s]) } : {}, exc.length ? { exclude: exc.map(s => [s]) } : {}) : document;
      const r = await window.axe.run(ctx, { resultTypes: ['violations'] });
      const inside = t => { let el = null; try { el = t.length === 1 ? document.querySelector(t[0]) : null; } catch (e) { /* bad selector */ }
        return el ? waive.filter(s => { try { return !!el.closest(s); } catch (e) { return false; } }) : []; };
      const text = t => { let el = null; try { el = t.length === 1 ? document.querySelector(t[0]) : null; } catch (e) { /* bad selector */ }
        return el ? (el.getAttribute('aria-label') || el.innerText || el.value || el.getAttribute('title') || '').trim().replace(/\s+/g, ' ').slice(0, 60) : ''; };
      return r.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length, target: (v.nodes[0] && v.nodes[0].target || []).join(' '),
        list: v.nodes.slice(0, 20).map(n => { const d = ((n.any || []).concat(n.all || [], n.none || []).find(c => c.data && c.data.contrastRatio) || {}).data;
          const o = { target: (n.target || []).join(' '), inside: inside(n.target || []), text: text(n.target || []) };
          if (d) Object.assign(o, { ratio: d.contrastRatio, expected: d.expectedContrastRatio, fg: d.fgColor, bg: d.bgColor });
          return o; }) }));
    }, { scope: scope || null, waive: WAIVE });
    return res;
  } catch (e) { return [{ id: 'axe-error', impact: 'minor', help: String(e.message || e).slice(0, 160), nodes: 0, target: '' }]; }
}

// Theme values go through --set-theme (the app's own switch) when given, else the theming attribute on <html>.
async function setTheme(page, key, value) {
  if (SET_THEME) return page.evaluate(({ code, key, value }) => new Function('key', 'value', code)(key, value), { code: SET_THEME, key, value });
  if (!THEMING[key]) throw new Error('theming key "' + key + '" is not in ds.json > theming');
  return page.evaluate(({ a, v }) => document.documentElement.setAttribute(a, v), { a: THEMING[key], v: value });
}

// Named states: "brand=ocean" (any ds.json theming key) and "text=200%" (root font size); objects pass through.
function normState(st) {
  if (typeof st !== 'string') return st;
  const m = /^([\w-]+)\s*=\s*(.+)$/.exec(st);
  if (!m) return { name: st, error: 'unknown named state "' + st + '" (use <theming key>=<value> or text=200%)' };
  if (m[1] === 'text') { const v = m[2].trim(); return { name: st, textScale: parseFloat(v) / (v.endsWith('%') ? 100 : 1) }; }
  return { name: st, theme: { [m[1]]: m[2].trim() } };
}

async function openPage(ctx, route, mode, prepare, errors) {
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push('pageerror: ' + String(e.message || e).slice(0, 200)));
  page.on('console', m => { if (m.type() === 'error' && !IGNORE_CONSOLE.test(m.text())) errors.push('console: ' + m.text().slice(0, 200)); });
  await page.goto(urlFor(route), { waitUntil: 'load' });
  if (PREP && (PREP.js || PREP.script)) {   // plan.prepare: once per page load, before the screen's or flow's own steps
    await page.evaluate(code => (0, eval)(code), PREP.js || PREP.script);
    if (PREP.reload) await page.reload({ waitUntil: 'load' });
    await page.waitForTimeout(150);
  }
  await page.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; });
  if (mode) await setTheme(page, 'mode', mode);
  if (prepare) await page.evaluate(code => (0, eval)(code), prepare);
  await page.waitForTimeout(250);
  return page;
}

// Parity snapshot of a view: visible text lines, interactive elements counted by role and name, aria states.
async function snapshot(page) {
  return page.evaluate(root => {
    let R = null;   // the first selector of the list that matches (plan.contentRoot), else the whole body
    for (const r of String(root || '').split(',').map(x => x.trim()).filter(Boolean)) { try { R = document.querySelector(r); } catch (e) { /* bad selector */ } if (R) { root = r; break; } }
    R = R || document.body;
    const norm = x => String(x || '').replace(/\s+/g, ' ').trim();
    const vis = el => { const s = getComputedStyle(el), b = el.getBoundingClientRect(); return s.visibility !== 'hidden' && s.display !== 'none' && b.width > 0 && b.height > 0; };
    const implicit = el => { const t = el.tagName.toLowerCase(), ty = (el.getAttribute('type') || 'text').toLowerCase();
      if (t === 'a' && el.hasAttribute('href')) return 'link';
      if (t === 'button' || t === 'summary') return 'button';
      if (t === 'select') return el.multiple ? 'listbox' : 'combobox';
      if (t === 'textarea') return 'textbox';
      if (t === 'input') return { checkbox: 'checkbox', radio: 'radio', range: 'slider', number: 'spinbutton', search: 'searchbox',
        button: 'button', submit: 'button', reset: 'button', image: 'button', hidden: '' }[ty] ?? 'textbox';
      if (el.isContentEditable && el.getAttribute('contenteditable') !== null) return 'textbox';
      return ''; };
    const ROLES = /^(button|link|checkbox|radio|switch|tab|menuitem|menuitemcheckbox|menuitemradio|option|combobox|textbox|searchbox|listbox|slider|spinbutton|treeitem|menu|menubar|tablist|dialog|alertdialog)$/;
    const label = el => { const lb = el.getAttribute('aria-labelledby');
      const byId = lb ? lb.split(/\s+/).map(id => { const x = document.getElementById(id); return x ? x.textContent : ''; }).join(' ') : '';
      return norm(el.getAttribute('aria-label') || byId || (el.labels && el.labels[0] && el.labels[0].innerText) || el.innerText || el.value ||
        el.getAttribute('title') || el.getAttribute('placeholder') || el.getAttribute('alt')).slice(0, 60); };
    const roles = {}, aria = {};
    for (const el of R.querySelectorAll('*')) {
      const role = (el.getAttribute('role') || '').split(/\s+/)[0] || implicit(el);
      if (!ROLES.test(role) || !vis(el)) continue;
      const key = role + ' "' + label(el) + '"';
      roles[key] = (roles[key] || 0) + 1;
      const st = ['expanded', 'selected', 'checked', 'pressed', 'current', 'disabled', 'invalid'].map(k => {
        let v = el.getAttribute('aria-' + k);
        if (v === null && k === 'disabled' && el.disabled) v = 'true';
        if (v === null && k === 'checked' && (el.type === 'checkbox' || el.type === 'radio')) v = String(el.checked);
        return v === null ? '' : k + '=' + v; }).filter(Boolean).join(' ');
      if (st) { let k = key, n = 2; while (aria[k] !== undefined) k = key + ' #' + n++; aria[k] = st; }
    }
    const text = (R.innerText || '').split('\n').map(norm).filter(Boolean).slice(0, 400);
    return { root: root && R !== document.body ? root : 'body', text, roles, aria };
  }, plan.contentRoot || null);
}

// The page URL relative to the entry's folder (both builds of a parity run compare the same relative paths).
function relUrl(u) {
  const base = A.url.split('#')[0].replace(/[^/]*$/, '');
  return u.startsWith(base) ? u.slice(base.length) : u;
}

// Does the server answer? file: URLs always do; any HTTP status counts (a 404 is the screen's own failure).
async function answers(u) {
  if (!/^https?:/.test(u)) return null;
  return new Promise(done => {
    const req = require(u.startsWith('https:') ? 'https' : 'http').request(u.split('#')[0], { method: 'HEAD', timeout: 5000 }, res => { res.resume(); done(null); });
    req.on('timeout', () => { req.destroy(); done('no answer in 5 s'); });
    req.on('error', e => done(String(e.code || e.message || e)));
    req.end();
  });
}

async function runFlow(browser, flow) {
  const ctx = await browser.newContext({ viewport: { width: flow.viewport || 1280, height: 900 } });
  const errors = [];
  const res = { name: flow.name, ok: true, steps: (flow.steps || []).length, failedStep: null, error: null, errors, shot: null };
  if (PARITY) res.urls = [];
  let page;
  try {
    page = await openPage(ctx, flow.start || '', null, flow.prepare, errors);
    for (let i = 0; i < (flow.steps || []).length; i++) {
      const s = flow.steps[i];
      try {
        await runStep(page, s);
        if (PARITY) res.urls.push(relUrl(page.url()));
      } catch (e) {
        res.ok = false; res.failedStep = i + 1; res.error = String(e.message || e).split('\n')[0].slice(0, 240); break;
      }
    }
    if (errors.length) res.ok = false;
    if (PARITY) {
      await page.waitForTimeout(150);
      res.storage = await page.evaluate(() => { const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); o[k] = localStorage.getItem(k); } return o; });
      res.snap = await snapshot(page);
    }
    const shot = 'flow__' + slug(flow.name) + '.png';
    await page.screenshot({ path: path.join(out, 'shots', shot) });
    res.shot = shot;
  } catch (e) {
    res.ok = false; res.error = String(e.message || e).split('\n')[0].slice(0, 240);
  }
  await ctx.close();
  return res;
}

// --discover: routes, names and selectors read from the rendered page (validation.py init --url).
async function discover(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(A.url, { waitUntil: 'load' });
  await page.waitForTimeout(600);
  const roots = String(A['content-root'] || 'main, #app, [role=main]').split(',').map(x => x.trim()).filter(Boolean);
  const info = await page.evaluate(roots => {
    const norm = x => String(x || '').replace(/\s+/g, ' ').trim();
    const vis = el => { const s = getComputedStyle(el), b = el.getBoundingClientRect(); return s.visibility !== 'hidden' && s.display !== 'none' && b.width > 0 && b.height > 0; };
    let root = null, rootSel = null;
    for (const r of roots) { let el = null; try { el = document.querySelector(r); } catch (e) { /* bad selector */ } if (el && vis(el)) { root = el; rootSel = r; break; } }
    const R = root || document.body;
    const h = [...R.querySelectorAll('h1, h2, [role=heading]')].find(vis) || [...document.querySelectorAll('h1')].find(vis);
    const routes = [];
    const add = (r, name, via) => { if (r && r.startsWith('#/') && !routes.some(x => x.route === r)) routes.push(Object.assign({ route: r, name: norm(name).slice(0, 60) }, via ? { via } : {})); };
    document.querySelectorAll('a[href^="#/"]').forEach(a => add(a.getAttribute('href'), a.innerText || a.getAttribute('aria-label')));
    document.querySelectorAll('[data-route], [data-href], [data-to], [data-hash]').forEach(el => {
      const at = ['data-route', 'data-href', 'data-to', 'data-hash'].find(x => el.getAttribute(x)), raw = at ? el.getAttribute(at) : '';
      // a route ("#/x", "/x"), never a link to another page ("other/index.html", "https://…")
      const v = /^#\//.test(raw) ? raw : /^\/[\w\-/]*$/.test(raw) && at !== 'data-href' ? '#' + raw : '';
      add(v, el.innerText || el.getAttribute('aria-label'), at ? '[' + at + '="' + raw.replace(/["\\]/g, '\\$&') + '"]' : null);
    });
    const CTRL = 'button, a[href], input:not([type=hidden]), select, textarea, [role=button], [role=tab], [role=link], [role=menuitem], [role=checkbox], [role=switch], [role=combobox], [role=searchbox]';
    const esc = v => v.replace(/["\\]/g, '\\$&');
    const sels = [];
    const push = x => { if (x && !sels.includes(x)) sels.push(x); };
    const stable = el => {
      if (el.id && /^[A-Za-z][\w-]*$/.test(el.id)) return '#' + el.id;
      for (const a of ['data-testid', 'data-test', 'data-qa']) if (el.getAttribute(a)) return '[' + a + '="' + esc(el.getAttribute(a)) + '"]';
      const al = el.getAttribute('aria-label');
      if (al) return el.tagName.toLowerCase() + '[aria-label="' + esc(al) + '"]';
      return null; };
    R.querySelectorAll(CTRL).forEach(el => { if (vis(el)) push(stable(el)); });
    R.querySelectorAll('[id]').forEach(el => { if (vis(el) && el !== R) push(stable(el)); });
    const cssPath = el => {   // a stable selector, else nth-child steps from the closest ancestor that has one
      const steps = [];
      for (let n = el; n && n !== document.body; n = n.parentElement) {
        const st = stable(n);
        if (st) { steps.unshift(st); return steps.join(' > '); }
        steps.unshift(n.tagName.toLowerCase() + ':nth-child(' + ([...n.parentElement.children].indexOf(n) + 1) + ')');
      }
      return 'body > ' + steps.join(' > '); };
    const tabs = [...R.querySelectorAll('[role=tab], [role=tablist] button, nav button, nav [role=link]')].filter(vis).slice(0, 12).map(el => ({
      css: cssPath(el), role: el.getAttribute('role') || 'button', name: norm(el.getAttribute('aria-label') || el.innerText).slice(0, 60) }));
    return { title: norm(document.title), heading: h ? norm(h.innerText).slice(0, 80) : '', contentRoot: rootSel, routes, selectors: sels.slice(0, 40),
      tabs, hash: location.hash };
  }, roots);
  // Buttons that change the hash (a router built in JS): click each tab-like control once (a DOM click, so a shell
  // overlay does not block it) and read the hash it sets.
  for (const tb of info.tabs) {
    try {
      if (!(await page.evaluate(sel => { const el = document.querySelector(sel); if (el) el.click(); return !!el; }, tb.css))) continue;
      await page.waitForTimeout(200);
      const h = await page.evaluate(() => location.hash);
      // flows click it by role and name (survives a rebuild in another stack), else by its CSS path
      const via = tb.name ? 'role=' + tb.role + '[name="' + tb.name.replace(/"/g, '\\"') + '"]' : tb.css;
      if (h.startsWith('#/') && !info.routes.some(x => x.route === h)) info.routes.push({ route: h, name: tb.name, via });
    } catch (e) { /* not clickable: skip */ }
  }
  delete info.tabs;
  await ctx.close();
  return info;
}

(async () => {
  const browser = await chromium.launch();
  if (A.discover) {
    const why = await answers(A.url);
    if (why) { console.log('ERROR: ' + A.url.split('#')[0] + ' does not answer (' + why + ')'); await browser.close(); process.exit(2); }
    console.log(JSON.stringify(await discover(browser)));
    await browser.close();
    return;
  }
  const results = { url: A.url, started: new Date().toISOString(), viewports, modes, modeAttr, parity: PARITY,
    axe: { available: !!axePath, version: axeVersion, path: axePath, scope: plan.axe || null }, items: [], flows: [] };
  const save = () => { results.finished = new Date().toISOString(); fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify(results, null, 2)); };
  const stopIfDown = async (u, what) => {
    const why = await answers(u);
    if (!why) return;
    results.aborted = { before: what, url: u, error: why };
    save();
    await browser.close();
    console.log('ERROR: the server at ' + new URL(u).origin + ' does not answer (' + why + '): stopped before ' + what + ' after ' +
      results.items.length + ' screen views and ' + results.flows.length + ' flows. Start the server and run again.');
    process.exit(2);
  };
  const screens = plan.screens && plan.screens.length ? plan.screens : [{ id: 'S01', name: 'Entry', route: '' }];
  for (const sc of screens) {
    await stopIfDown(urlFor(sc.route), 'screen ' + sc.id);
    const states = [{ name: 'default', prepare: sc.prepare }].concat(sc.states || [], plan.states || []).map(normState);
    const vps = sc.viewports && sc.viewports.length ? sc.viewports.map(Number) : viewports;
    for (const st of states) {
      for (const vp of vps) {
        for (const mode of modes) {
          const ctx = await browser.newContext({ viewport: { width: vp, height: vp < 600 ? 844 : 900 } });
          const errors = [];
          const item = { screen: sc.id, screenName: sc.name || '', state: st.name, vp, mode, route: sc.route || '', errors, shot: null };
          try {
            const page = await openPage(ctx, sc.route, null, null, errors);
            for (let i = 0; i < (sc.steps || []).length; i++) {
              try { await runStep(page, sc.steps[i]); } catch (e) { throw new Error('step ' + (i + 1) + ': ' + String(e.message || e).split('\n')[0]); }
            }
            if (st.error) throw new Error(st.error);
            if (modes.length > 1 || mode !== 'light') await setTheme(page, 'mode', mode);
            for (const [k, v] of Object.entries(st.theme || {})) await setTheme(page, k, v);
            if (st.textScale) await page.evaluate(x => { const h = document.documentElement; h.style.fontSize = (parseFloat(getComputedStyle(h).fontSize) * x) + 'px'; }, st.textScale);
            if (st.prepare) await page.evaluate(code => (0, eval)(code), st.prepare);
            await page.waitForTimeout(150);
            Object.assign(item, await pageChecks(page, vp));
            if (PARITY) item.snap = await snapshot(page);
            else {
              if (st.name === 'default' && mode === modes[0]) item.focus = await focusCheck(page);
              // axe on every state of the plan at the widest width; "axe": false on the state or the screen opts out
              if (st.axe !== false && sc.axe !== false && vp === vps[vps.length - 1]) item.axe = await axeCheck(page, sc.axe || plan.axe);
            }
            const shot = [slug(sc.id), slug(st.name), vp, mode].join('__') + '.png';
            await page.evaluate(() => window.scrollTo(0, 0));
            await page.screenshot({ path: path.join(out, 'shots', shot), fullPage: true });
            item.shot = shot;
          } catch (e) {
            item.fatal = String(e.message || e).split('\n')[0].slice(0, 240);
          }
          results.items.push(item);
          await ctx.close();
        }
      }
    }
  }
  for (const f of plan.flows || []) {
    await stopIfDown(urlFor(f.start || ''), 'flow "' + f.name + '"');
    results.flows.push(await runFlow(browser, f));
  }
  await browser.close();
  save();
  console.log('Checked ' + results.items.length + ' screen views and ' + results.flows.length + ' flows. axe-core: ' + (axePath ? axeVersion : 'not installed'));
})().catch(e => { console.log('ERROR: ' + (e.message || e)); process.exit(1); });
