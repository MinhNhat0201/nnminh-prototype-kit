#!/usr/bin/env node
// Browser checks for a prototype, driven by a validation plan. Called by validation.py run; usable alone.
//
//   node validate.js --url <file:// or http:// entry> --plan plan.json --out <run dir>
//                    [--viewports 390,768,1280] [--modes light,dark] [--mode-attr data-mode]
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
if (A.help || !A.url || !A.plan || !A.out) {
  console.log('usage: node validate.js --url <entry URL> --plan plan.json --out <dir> [--viewports 390,768,1280] [--modes light,dark] [--mode-attr data-mode] [--project <dir>]');
  process.exit(A.help ? 0 : 1);
}
const plan = JSON.parse(fs.readFileSync(A.plan, 'utf8'));
const viewports = String(A.viewports || plan.viewports || '390,768,1280').split(',').map(Number).filter(Boolean);
const modes = String(A.modes || plan.modes || 'light').split(',').filter(Boolean);
const modeAttr = A['mode-attr'] || plan.modeAttr || 'data-mode';
const out = path.resolve(A.out);
fs.mkdirSync(path.join(out, 'shots'), { recursive: true });

// axe-core is optional: look in the project, the kit, and the current folder.
let axePath = null, axeVersion = null;
for (const base of [A.project, path.resolve(__dirname, '../../..'), process.cwd()].filter(Boolean)) {
  try { axePath = require.resolve('axe-core/axe.min.js', { paths: [base] }); axeVersion = require(require.resolve('axe-core/package.json', { paths: [base] })).version; break; } catch (e) { /* next */ }
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
  return page.evaluate(({ vp }) => {
    const r = { overflow: null, touch: [], clipped: [], hidden: false };
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
        if (!vis(el)) return;
        const b = el.getBoundingClientRect();
        if (b.width < 44 || b.height < 44) {
          const inline = getComputedStyle(el).display === 'inline' && el.closest('p, li, td, dd');
          if (!inline) r.touch.push(name(el) + ' ' + Math.round(b.width) + 'x' + Math.round(b.height));
        }
      });
      r.touch = r.touch.slice(0, 12);
    }
    document.querySelectorAll('body *').forEach(el => {
      if (r.clipped.length >= 10 || !vis(el) || !el.childNodes.length) return;
      const s = getComputedStyle(el);
      if (!/hidden|clip/.test(s.overflowX + s.overflow) || s.textOverflow === 'ellipsis') return;
      const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
      if (own && el.scrollWidth > el.clientWidth + 1) r.clipped.push(name(el));
    });
    return r;
  }, { vp });
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

async function axeCheck(page) {
  if (!axePath) return null;
  try {
    await page.addScriptTag({ path: axePath });
    const res = await page.evaluate(async () => {
      const r = await window.axe.run(document, { resultTypes: ['violations'] });
      return r.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length, target: (v.nodes[0] && v.nodes[0].target || []).join(' ') }));
    });
    return res;
  } catch (e) { return [{ id: 'axe-error', impact: 'minor', help: String(e.message || e).slice(0, 160), nodes: 0, target: '' }]; }
}

async function openPage(ctx, route, mode, prepare, errors) {
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push('pageerror: ' + String(e.message || e).slice(0, 200)));
  page.on('console', m => { if (m.type() === 'error' && !IGNORE_CONSOLE.test(m.text())) errors.push('console: ' + m.text().slice(0, 200)); });
  await page.goto(urlFor(route), { waitUntil: 'load' });
  await page.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; });
  if (mode) await page.evaluate(({ a, m }) => document.documentElement.setAttribute(a, m), { a: modeAttr, m: mode });
  if (prepare) await page.evaluate(code => (0, eval)(code), prepare);
  await page.waitForTimeout(250);
  return page;
}

async function runFlow(browser, flow) {
  const ctx = await browser.newContext({ viewport: { width: flow.viewport || 1280, height: 900 } });
  const errors = [];
  const res = { name: flow.name, ok: true, steps: (flow.steps || []).length, failedStep: null, error: null, errors, shot: null };
  let page;
  try {
    page = await openPage(ctx, flow.start || '', null, flow.prepare, errors);
    for (let i = 0; i < (flow.steps || []).length; i++) {
      const s = flow.steps[i];
      try {
        if (s.goto !== undefined) { await page.goto(urlFor(s.goto)); await page.waitForTimeout(150); }
        else if (s.click) await page.click(s.click, { timeout: 3000 });
        else if (s.fill) await page.fill(s.fill[0], s.fill[1], { timeout: 3000 });
        else if (s.select) await page.selectOption(s.select[0], s.select[1], { timeout: 3000 });
        else if (s.press) await page.keyboard.press(s.press);
        else if (s.wait) await page.waitForTimeout(Math.min(+s.wait, 5000));
        else if (s.expectVisible) await page.waitForSelector(s.expectVisible, { state: 'visible', timeout: 3000 });
        else if (s.expectHidden) await page.waitForSelector(s.expectHidden, { state: 'hidden', timeout: 3000 });
        else if (s.expectText) {
          const txt = await page.textContent(s.expectText[0], { timeout: 3000 });
          if (!txt || !txt.includes(s.expectText[1])) throw new Error('text of ' + s.expectText[0] + ' does not contain "' + s.expectText[1] + '"');
        } else if (s.expectUrl) { if (!page.url().includes(s.expectUrl)) throw new Error('URL ' + page.url() + ' does not contain ' + s.expectUrl); }
        else throw new Error('unknown step ' + JSON.stringify(s));
      } catch (e) {
        res.ok = false; res.failedStep = i + 1; res.error = String(e.message || e).split('\n')[0].slice(0, 240); break;
      }
    }
    if (errors.length) res.ok = false;
    const shot = 'flow__' + slug(flow.name) + '.png';
    await page.screenshot({ path: path.join(out, 'shots', shot) });
    res.shot = shot;
  } catch (e) {
    res.ok = false; res.error = String(e.message || e).split('\n')[0].slice(0, 240);
  }
  await ctx.close();
  return res;
}

(async () => {
  const browser = await chromium.launch();
  const results = { url: A.url, started: new Date().toISOString(), viewports, modes, modeAttr,
    axe: { available: !!axePath, version: axeVersion }, items: [], flows: [] };
  const screens = plan.screens && plan.screens.length ? plan.screens : [{ id: 'S01', name: 'Entry', route: '' }];
  for (const sc of screens) {
    const states = [{ name: 'default', prepare: sc.prepare }].concat(sc.states || []);
    for (const st of states) {
      for (const vp of viewports) {
        for (const mode of modes) {
          const ctx = await browser.newContext({ viewport: { width: vp, height: vp < 600 ? 844 : 900 } });
          const errors = [];
          const item = { screen: sc.id, screenName: sc.name || '', state: st.name, vp, mode, route: sc.route || '', errors, shot: null };
          try {
            const page = await openPage(ctx, sc.route, modes.length > 1 || mode !== 'light' ? mode : null, st.prepare, errors);
            Object.assign(item, await pageChecks(page, vp));
            if (st.name === 'default' && mode === modes[0]) item.focus = await focusCheck(page);
            if (st.name === 'default' && vp === viewports[viewports.length - 1]) item.axe = await axeCheck(page);
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
  for (const f of plan.flows || []) results.flows.push(await runFlow(browser, f));
  await browser.close();
  results.finished = new Date().toISOString();
  fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify(results, null, 2));
  console.log('Checked ' + results.items.length + ' screen views and ' + results.flows.length + ' flows. axe-core: ' + (axePath ? axeVersion : 'not installed'));
})().catch(e => { console.log('ERROR: ' + (e.message || e)); process.exit(1); });
