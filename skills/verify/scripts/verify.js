#!/usr/bin/env node
// Compare a developer build with the approved prototype, screen by screen. Called by verify.py run.
//
//   node verify.js --pairs pairs.json --tokens tokens.json --out <run dir> [--project <dir>]
//
// pairs.json: { "prototypeBase": "<url>", "implementationBase": "<url>", "viewports": [390, 1280],
//   "screens": [{ "id": "S01", "name": "...", "prototype": "#/", "implementation": "/tasks",
//                 "prepare": {"prototype": "<js>", "implementation": "<js>"}, "mask": ["[data-time]"] }],
//   "flows": [{ "name": "...", "viewport": 1280, "prototype": {"start": "#/", "steps": [...]},
//               "implementation": {"start": "/tasks", "steps": [...]} }] }
// tokens.json: { "prefix": "--acme-", "names": ["--acme-bg-canvas", ...] }
//
// For each screen and viewport, on both sides: screenshot (masked), the colours, font sizes and radii in use,
// DS component classes, visible texts, console errors; axe-core on the implementation when installed.
// Token values are resolved on the prototype page, which embeds the DS. Writes results.json and shots/.
'use strict';
const fs = require('fs');
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { console.log('ERROR: playwright is not available'); process.exit(1); }

const A = {}; { const v = process.argv.slice(2); for (let i = 0; i < v.length; i++) if (v[i].startsWith('--')) A[v[i].slice(2)] = v[i + 1] && !v[i + 1].startsWith('--') ? v[++i] : true; }
if (A.help || !A.pairs || !A.tokens || !A.out) { console.log('usage: node verify.js --pairs pairs.json --tokens tokens.json --out <dir> [--project <dir>]'); process.exit(A.help ? 0 : 1); }
const P = JSON.parse(fs.readFileSync(A.pairs, 'utf8'));
const TOK = JSON.parse(fs.readFileSync(A.tokens, 'utf8'));
const out = path.resolve(A.out);
fs.mkdirSync(path.join(out, 'shots'), { recursive: true });
const viewports = (P.viewports || [390, 1280]).map(Number);
const IGNORE = /fonts\.(googleapis|gstatic)\.com|Failed to load resource.*(font|woff)|ERR_NAME_NOT_RESOLVED|ERR_INTERNET_DISCONNECTED/i;
const slug = s => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'x';

let axePath = null;
for (const base of [A.project, path.resolve(__dirname, '../../..'), process.cwd()].filter(Boolean)) {
  try { axePath = require.resolve('axe-core/axe.min.js', { paths: [base] }); break; } catch (e) { /* next */ }
}

function url(base, route) {
  if (route === undefined || route === null) route = '';
  if (/^[a-z]+:/i.test(route)) return route;
  if (!base) throw new Error('no base URL for route ' + route);
  if (route.startsWith('#')) return base.split('#')[0] + route;
  return route ? new URL(route, base).href : base;
}

async function open(ctx, base, route, prepare, mask) {
  const errors = [];
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push('pageerror: ' + String(e.message || e).slice(0, 200)));
  page.on('console', m => { if (m.type() === 'error' && !IGNORE.test(m.text())) errors.push('console: ' + m.text().slice(0, 200)); });
  await page.goto(url(base, route), { waitUntil: 'load' });
  if (prepare) await page.evaluate(code => (0, eval)(code), prepare);
  await page.addStyleTag({ content: '*{animation:none!important;transition:none!important;caret-color:transparent!important}' + (mask || []).map(s => s + '{visibility:hidden!important}').join('') });
  await page.waitForTimeout(250);
  return { page, errors };
}

// Token values as computed in the prototype (the DS is embedded there).
async function tokenValues(page) {
  return page.evaluate(names => {
    // A wrapper with a sentinel colour: a token that is not a colour makes the probe inherit it, so it is skipped.
    const wrap = document.createElement('div');
    wrap.style.cssText = 'position:absolute;left:-9999px;top:0;color:rgb(1, 2, 3)';
    const probe = document.createElement('div');
    probe.style.cssText = 'position:absolute;border:0 solid;';
    wrap.appendChild(probe);
    document.body.appendChild(wrap);
    const out = { color: {}, length: {} };
    for (const n of names) {
      const raw = getComputedStyle(document.documentElement).getPropertyValue(n).trim();
      if (!raw) continue;
      probe.style.color = 'var(' + n + ')';
      const c = getComputedStyle(probe).color;
      if (c && c !== 'rgb(1, 2, 3)') (out.color[c] = out.color[c] || []).push(n);
      probe.style.width = 'var(' + n + ')';
      const w = getComputedStyle(probe).width;
      if (w.endsWith('px') && (w !== '0px' || /^0(px|rem|em)?$/.test(raw))) (out.length[w] = out.length[w] || []).push(n);
    }
    wrap.remove();
    return out;
  }, TOK.names || []);
}

async function inspect(page, prefix) {
  return page.evaluate(prefix => {
    const used = { color: {}, background: {}, border: {}, fontSize: {}, radius: {} };
    const sample = {};
    const comps = {};
    const texts = new Set();
    const cls = prefix.replace(/^--/, '');
    const name = el => el.tagName.toLowerCase() + ((el.getAttribute('class') || '').trim() ? '.' + el.getAttribute('class').trim().split(/\s+/)[0] : '');
    const add = (k, v, el) => { if (!v) return; used[k][v] = (used[k][v] || 0) + 1; if (!sample[k + v]) sample[k + v] = name(el); };
    document.querySelectorAll('body *').forEach(el => {
      const s = getComputedStyle(el), b = el.getBoundingClientRect();
      if (s.display === 'none' || s.visibility === 'hidden' || b.width === 0 || b.height === 0) return;
      const ownText = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
      if (ownText) { add('color', s.color, el); add('fontSize', s.fontSize, el); }
      if (s.backgroundColor && !/rgba\(0, 0, 0, 0\)|transparent/.test(s.backgroundColor)) add('background', s.backgroundColor, el);
      if (parseFloat(s.borderTopWidth) > 0 && s.borderTopStyle !== 'none') add('border', s.borderTopColor, el);
      if (parseFloat(s.borderTopLeftRadius) > 0) add('radius', s.borderTopLeftRadius, el);
      (el.getAttribute('class') || '').split(/\s+/).forEach(c => { if (c.startsWith(cls) && !c.includes('__') && !c.includes('--')) comps[c] = (comps[c] || 0) + 1; });
      const role = el.getAttribute('role') || '';
      const label = /^(H[1-6]|BUTTON|A|LABEL|TH|LEGEND|SUMMARY|OPTION|DT)$/.test(el.tagName) || /^(button|tab|heading|link|menuitem)$/.test(role)
        || parseInt(s.fontWeight, 10) >= 600 || /title|heading|label/i.test(el.getAttribute('class') || '');
      if (ownText && label) {
        const t = el.innerText.trim().replace(/\s+/g, ' ');
        if (t && t.length <= 80) texts.add(t);
      }
    });
    return { used, sample, comps, texts: [...texts] };
  }, prefix || '--ds-');
}

async function axe(page) {
  if (!axePath) return null;
  try {
    await page.addScriptTag({ path: axePath });
    return await page.evaluate(async () => (await window.axe.run(document, { resultTypes: ['violations'] })).violations
      .map(v => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length })));
  } catch (e) { return [{ id: 'axe-error', impact: 'minor', help: String(e.message || e).slice(0, 160), nodes: 0 }]; }
}

async function steps(page, list) {
  for (let i = 0; i < (list || []).length; i++) {
    const s = list[i];
    try {
      if (s.goto !== undefined) await page.goto(url(page.url(), s.goto));
      else if (s.click) await page.click(s.click, { timeout: 3000 });
      else if (s.fill) await page.fill(s.fill[0], s.fill[1], { timeout: 3000 });
      else if (s.select) await page.selectOption(s.select[0], s.select[1], { timeout: 3000 });
      else if (s.press) await page.keyboard.press(s.press);
      else if (s.wait) await page.waitForTimeout(Math.min(+s.wait, 5000));
      else if (s.expectVisible) await page.waitForSelector(s.expectVisible, { state: 'visible', timeout: 3000 });
      else if (s.expectHidden) await page.waitForSelector(s.expectHidden, { state: 'hidden', timeout: 3000 });
      else if (s.expectText) { const t = await page.textContent(s.expectText[0], { timeout: 3000 }); if (!t || !t.includes(s.expectText[1])) throw new Error('text of ' + s.expectText[0] + ' does not contain "' + s.expectText[1] + '"'); }
      else if (s.expectUrl) { if (!page.url().includes(s.expectUrl)) throw new Error('URL ' + page.url() + ' does not contain ' + s.expectUrl); }
      else throw new Error('unknown step ' + JSON.stringify(s));
    } catch (e) { return { ok: false, step: i + 1, error: String(e.message || e).split('\n')[0].slice(0, 200) }; }
  }
  return { ok: true };
}

(async () => {
  const browser = await chromium.launch();
  const res = { started: new Date().toISOString(), viewports, axe: !!axePath, prefix: TOK.prefix, tokens: null, screens: [], flows: [] };
  for (const sc of P.screens || []) {
    for (const vp of viewports) {
      const item = { screen: sc.id, name: sc.name || '', vp };
      for (const side of ['prototype', 'implementation']) {
        const ctx = await browser.newContext({ viewport: { width: vp, height: vp < 600 ? 844 : 900 } });
        try {
          const { page, errors } = await open(ctx, P[side + 'Base'], sc[side], (sc.prepare || {})[side], sc.mask);
          if (side === 'prototype' && !res.tokens) res.tokens = await tokenValues(page);
          const shot = [slug(sc.id), vp, side].join('__') + '.png';
          await page.screenshot({ path: path.join(out, 'shots', shot), fullPage: true });
          item[side] = Object.assign({ shot, errors, url: page.url() }, await inspect(page, TOK.prefix));
          if (side === 'implementation' && vp === viewports[viewports.length - 1]) item[side].axe = await axe(page);
        } catch (e) {
          item[side] = { fatal: String(e.message || e).split('\n')[0].slice(0, 240) };
        }
        await ctx.close();
      }
      res.screens.push(item);
    }
  }
  for (const f of P.flows || []) {
    const r = { name: f.name };
    for (const side of ['prototype', 'implementation']) {
      const ctx = await browser.newContext({ viewport: { width: f.viewport || 1280, height: 900 } });
      try {
        const def = f[side] || {};
        const { page, errors } = await open(ctx, P[side + 'Base'], def.start, def.prepare, []);
        r[side] = await steps(page, def.steps);
        r[side].errors = errors;
      } catch (e) { r[side] = { ok: false, error: String(e.message || e).split('\n')[0].slice(0, 200) }; }
      await ctx.close();
    }
    res.flows.push(r);
  }
  await browser.close();
  res.finished = new Date().toISOString();
  fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify(res, null, 2));
  console.log('Compared ' + res.screens.length + ' screen views and ' + res.flows.length + ' flows. axe-core: ' + (axePath ? 'yes' : 'not installed'));
})().catch(e => { console.log('ERROR: ' + (e.message || e)); process.exit(1); });
