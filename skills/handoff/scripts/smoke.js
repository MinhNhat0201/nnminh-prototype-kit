#!/usr/bin/env node
// Smoke run of an unpacked handoff package, called by `pkg.py smoke` (which unzips and serves the package over HTTP).
//
//   node smoke.js <base URL of the served package> <routes.json> [--widths 400,768,1280]
//
// routes.json: [{"id": "S01", "route": "prototype/index.html#/"}, ...] (relative to the package folder).
// For every route x width: page errors, console errors (blocked web fonts ignored), same-origin responses >= 400 and
// failed requests, broken images, horizontal scroll. Prints one JSON line: [{id, route, width, issues: [...]}].
// Chromium is assumed installed; this script never runs `playwright install`. It never edits the package.
'use strict';
const fs = require('fs');

let chromium;
try { ({ chromium } = require('playwright')); } catch (e) {
  console.log('ERROR: playwright is not available (npm i -D playwright, Chromium installed separately)'); process.exit(1);
}
const argv = process.argv.slice(2);
if (argv.includes('--help') || argv.length < 2) {
  console.log('usage: node smoke.js <base URL> <routes.json> [--widths 400,768,1280]');
  process.exit(argv.includes('--help') ? 0 : 1);
}
const [base, routesFile] = argv;
const wi = argv.indexOf('--widths');
const widths = String(wi >= 0 ? argv[wi + 1] : '400,768,1280').split(',').map(Number).filter(Boolean);
const routes = JSON.parse(fs.readFileSync(routesFile, 'utf8'));
const origin = new URL(base).origin;
// Same-origin failures are reported from the network events; "Failed to load resource" console lines would repeat them.
const IGNORE_CONSOLE = /fonts\.(googleapis|gstatic)\.com|Failed to load resource|ERR_NAME_NOT_RESOLVED|ERR_INTERNET_DISCONNECTED/i;

(async () => {
  const b = await chromium.launch(), out = [];
  for (const w of widths) {
    const ctx = await b.newContext({ viewport: { width: w, height: 800 } });
    for (const r of routes) {
      const page = await ctx.newPage(), issues = [];
      const rel = u => u.startsWith(origin) ? u.slice(origin.length) : u;
      page.on('pageerror', e => issues.push('pageerror: ' + String(e.message || e).split('\n')[0].slice(0, 200)));
      page.on('console', m => { if (m.type() === 'error' && !IGNORE_CONSOLE.test(m.text())) issues.push('console: ' + m.text().slice(0, 200)); });
      page.on('response', res => { if (res.status() >= 400 && res.url().startsWith(origin)) issues.push(res.status() + ': ' + rel(res.url())); });
      page.on('requestfailed', rq => { if (rq.url().startsWith(origin)) issues.push('request failed: ' + rel(rq.url())); });
      try {
        await page.goto(new URL(r.route, base).href, { waitUntil: 'load', timeout: 15000 });
        await page.waitForTimeout(400);
        const m = await page.evaluate(() => ({
          sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
          broken: Array.from(document.images).filter(i => i.complete && i.getAttribute('src') && i.naturalWidth === 0)
            .map(i => i.getAttribute('src').slice(0, 120)).slice(0, 5),
        }));
        if (m.sw > m.cw + 1) issues.push('horizontal scroll: content ' + m.sw + ' px wide in ' + m.cw + ' px');
        m.broken.forEach(s => issues.push('broken image: ' + s));
      } catch (e) { issues.push('load: ' + String(e.message || e).split('\n')[0]); }
      out.push({ id: r.id, route: r.route, width: w, issues: Array.from(new Set(issues)) });
      await page.close();
    }
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify(out));
})().catch(e => { console.log('ERROR: ' + (e.message || e)); process.exit(1); });
