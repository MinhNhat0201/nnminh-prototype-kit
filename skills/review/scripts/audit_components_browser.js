#!/usr/bin/env node
/* Browser audit of DS components: compare the real computed style of each control in the app with THE SAME control
 * rebuilt in an iframe that holds only the DS CSS bundle (ds.json > css.bundle), with no app CSS.
 *
 * For each DS root class (list from `python3 audit_app.py --roots roots.json`) it takes a few visible elements,
 * copies their outerHTML into the DS-only iframe, copies the theming attributes of <html> (ds.json > theming),
 * and compares computed styles. A difference = app CSS overrides the component, or the app embeds an older DS.
 *
 * Usage (static server on port 8765, e.g. `python3 -m http.server 8765` from the project folder):
 *   node audit_components_browser.js roots.json out.json http://localhost:8765/apps/acme-web/#/ [url ...]
 * Options: --width N (viewport width, default 1280), --project DIR (folder with kit.config.json, default cwd).
 * Needs Playwright with Chromium already installed; never runs `playwright install`.
 * Height is compared only when the DS gives the class its own height: when the DS copy keeps the same height with its
 * content removed (and has a box: a DS value of 'auto' is never compared). A wrapper or box whose height follows its content (menus, chip rows, logo boxes) is not reported for
 * height (counted as contentHeight).
 * Limit: the control is cut from its parent, so rules like `.parent .child` and inherited colours can show false
 * differences. Trust a difference only when it repeats on several elements for the same property.
 */
const fs = require('fs');
const path = require('path');
const { load, dsPath } = require(path.resolve(__dirname, '../../../scripts/kitconf.js'));

function fail(msg) { console.log('ERROR: ' + msg); process.exit(1); }

const argv = process.argv.slice(2);
if (argv.includes('-h') || argv.includes('--help')) {
  console.log(fs.readFileSync(__filename, 'utf8').split('*/')[0].replace(/^#!.*\n\/\* ?/, '').replace(/^ \* ?/gm, ''));
  process.exit(0);
}
const opt = (name, dflt) => { const i = argv.indexOf(name); if (i < 0) return dflt; const v = argv[i + 1]; argv.splice(i, 2); return v; };
const width = parseInt(opt('--width', '1280'), 10);
const project = opt('--project', undefined);
const [rootsFile, outFile, ...urls] = argv;
if (!rootsFile || !outFile || !urls.length) fail('missing arguments: roots.json out.json url [url ...] (see --help)');

let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { fail('Playwright is not installed for Node (npm i playwright); do not run playwright install from here.'); }

const cfg = load(project);
if (!cfg._ds) fail('no DS profile: kit.config.json > ds must point at a folder with ds.json.');
const bundle = dsPath(cfg, cfg._ds.css.bundle);
if (!bundle || bundle.includes('://') || !fs.existsSync(bundle)) fail('DS bundle not found or is a URL: ' + cfg._ds.css.bundle);
const dsCss = fs.readFileSync(bundle, 'utf8');
const attrs = Object.values(cfg._ds.theming || {}).map(x => x && x.attr).filter(Boolean);
const roots = JSON.parse(fs.readFileSync(rootsFile, 'utf8'));
const PROPS = ['height', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left', 'border-top-left-radius',
  'font-size', 'font-weight', 'line-height', 'color', 'background-color', 'border-top-color', 'border-top-width', 'box-shadow', 'column-gap'];

(async () => {
  const browser = await chromium.launch();
  const out = [];
  for (const url of urls) {
    const page = await browser.newPage({ viewport: { width, height: 800 } });
    const errs = [];
    page.on('pageerror', e => errs.push(String(e)));
    try {
      await page.goto(url, { waitUntil: 'load' });
    } catch (e) {
      out.push({ url, pageerrors: [String(e)], components: { _error: 'page did not load' } });
      await page.close();
      continue;
    }
    await page.waitForTimeout(1200);
    const res = await page.evaluate(async ({ roots, PROPS, css, attrs }) => {
      const html = document.documentElement;
      const htmlAttrs = attrs.map(a => html.hasAttribute(a) ? `${a}="${html.getAttribute(a)}"` : '').join(' ');
      const fr = document.createElement('iframe');
      fr.style.cssText = `position:fixed;left:-9999px;top:0;width:${innerWidth}px;height:800px;border:0`;
      document.body.appendChild(fr);
      fr.srcdoc = `<!doctype html><html ${htmlAttrs}><head><style>${css.replace(/<\/style/gi, '<\\/style')}</style></head><body style="margin:0"></body></html>`;
      await new Promise(r => fr.addEventListener('load', r, { once: true }));
      const doc = fr.contentDocument, win = fr.contentWindow;
      const result = {};
      const seen = new Set();
      for (const root of roots) {
        const els = [...document.querySelectorAll('.' + CSS.escape(root))].filter(e => e.offsetParent && e.getBoundingClientRect().width > 0);
        const diffs = {}; let n = 0, bad = 0, auto = 0;
        for (const el of els) {
          const key = root + '|' + el.className;
          if (seen.has(key) || n >= 6) continue; seen.add(key); n++;
          doc.body.innerHTML = '';
          const holder = doc.createElement('div'); holder.style.cssText = 'padding:8px;width:640px';
          holder.innerHTML = el.outerHTML; doc.body.appendChild(holder);
          const ref = holder.firstElementChild, a = getComputedStyle(el), b = win.getComputedStyle(ref);
          let d = PROPS.filter(p => a.getPropertyValue(p) !== b.getPropertyValue(p));
          if (d.includes('height')) {   // height set by the content (a wrapper, a list, a logo box): not a DS value to compare
            const empty = ref.cloneNode(false); holder.appendChild(empty);
            const dsH = b.getPropertyValue('height');   // 'auto': the DS copy has no box (display: contents, or hidden there)
            const fixed = dsH !== 'auto' && win.getComputedStyle(empty).getPropertyValue('height') === dsH;
            empty.remove();
            if (!fixed) { d = d.filter(p => p !== 'height'); auto++; }
          }
          if (d.length) { bad++; d.forEach(p => { (diffs[p] = diffs[p] || []).push([a.getPropertyValue(p), b.getPropertyValue(p)]); }); }
        }
        if (n) result[root] = { checked: n, differ: bad, contentHeight: auto, props: Object.fromEntries(Object.entries(diffs).map(([k, v]) => [k, { count: v.length, example: v[0] }])) };
      }
      fr.remove();
      return result;
    }, { roots, PROPS, css: dsCss, attrs });
    out.push({ url, pageerrors: errs, components: res });
    await page.close();
  }
  await browser.close();
  fs.writeFileSync(outFile, JSON.stringify(out, null, 1));
  for (const o of out) {
    console.log('\n' + o.url + (o.pageerrors.length ? '  [pageerror: ' + o.pageerrors.length + ']' : ''));
    if (o.components._error) { console.log('  ' + o.components._error); continue; }
    const entries = Object.entries(o.components).sort((x, y) => y[1].differ - x[1].differ);
    if (!entries.length) console.log('  no visible element with a DS root class');
    for (const [r, v] of entries) {
      const ps = Object.entries(v.props).map(([p, q]) => `${p} x${q.count} (${q.example[0]} != ${q.example[1]})`).join('; ');
      console.log(`  .${r}: ${v.differ}/${v.checked} differ from the DS${ps ? ' - ' + ps : ''}`);
    }
  }
})().catch(e => fail(String(e && e.stack || e)));
