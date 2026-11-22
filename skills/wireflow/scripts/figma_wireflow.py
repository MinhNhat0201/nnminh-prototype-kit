#!/usr/bin/env python3
"""Prepare data and images for the Figma wireflow board (skill `wireflow`), and map the board back into a package.

Commands:
  build     --spec <dir with screens.json + images> --flows <flows.json> --out <dir>
            [--pbi "PBI 1234" --feature "Scheduled tasks" --version 1.2.0] [--app <app id>] [--site <https URL>]
            [--title ...] [--meta ...] [--page ... | --page-id 123:456] [--png <dir>] [--scale 0.5] [--width 3200]
            -> <out>/code.js (send verbatim to use_figma), <out>/images/<Sxx>.png|jpg, <out>/plan.json
  upload    --out <dir> --urls <urls.json>
            urls.json: {"imageScreens": [...], "urls": [...]} in the order upload_assets returned them.
            POSTs each image to its URL (images never pass through the model context).
  mapjs     --root <board node id>          prints use_figma code: screen id -> card node, image frame node
  retitlejs --root <board node id> --title "..."   prints use_figma code: rename the board in place, copy image
            fills to repeated frames of the same screen (node ids stay, links already sent keep working)
  setmap    --config <pkg.json> --json <mapjs result> [--file <Figma file link>]
            writes figma_file, figma_board, figma_page, figma (screen id -> card node) into the package config

Never reads HTML: only screens.json (capture output of `annotate`) and flows.json.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
from demo_links import app_url, check_url, first_screen, load_screens, read_json, screen_url  # noqa: E402
from kitconf import load, t, version_label, app as app_entry  # noqa: E402

TEMPLATE = HERE.parent / 'assets' / 'wireflow-template.js'
IMG_SUFFIX = ' · image'  # fixed layer-name suffix of image frames; mapjs and the mockup audit match on it
LABELS = ('openPrototype', 'openFlow', 'demoNote', 'legend', 'toConfirm', 'pageChange', 'outOfScope', 'offflow')


def rgb(h):
    h = h.lstrip('#')
    if not re.fullmatch(r'[0-9a-fA-F]{6}', h):
        sys.exit(f'ERROR: colour must be #RRGGBB (found {h})')
    return {k: round(int(h[i:i + 2], 16) / 255, 3) for k, i in zip('rgb', (0, 2, 4))}


def colours(accent):
    # Board presentation colours (neutral greys + one accent), not product UI.
    return {'text': rgb('#262626'), 'sub': rgb('#666666'), 'line': rgb('#E0E0E0'), 'surface': rgb('#F6F6F6'),
            'white': rgb('#FFFFFF'), 'accent': rgb(accent), 'warn': rgb('#D97706')}


def page_label(page):
    """Short page label for a screen card: file name, with its folder when the file is index.html (no host, no local path)."""
    parts = [x for x in re.sub(r'^[a-z]+://[^/]*', '', (page or '').replace('\\', '/')).split('/') if x]
    if not parts:
        return ''
    return '/'.join(parts[-2:]) if parts[-1] == 'index.html' and len(parts) > 1 else parts[-1]


def fail(msg):
    print('ERROR: ' + msg)
    sys.exit(1)


def build(a):
    cfg = load(require=False, app=a.app or None) or {'language': 'en', 'deploy': {}, '_ds': None}  # apps[].ds: version label
    by = load_screens(os.path.join(a.spec, 'screens.json'))
    flows = read_json(a.flows)
    units = flows.get('units', {})
    used = []
    for f in flows['flows']:
        for r in f['rows']:
            for it in r['items']:
                if it[0] in ('n', 'chip') and it[1] not in by:
                    fail(f'{f["id"]} uses {it[1]} but screens.json has no such screen')
                if it[0] == 'n' and it[1] not in used:
                    used.append(it[1])
    used += [i for i in flows.get('offflow', []) if i not in used]
    missing = [i for i in by if i not in used]
    if missing:
        print('WARNING: screens in no flow and not in offflow:', ', '.join(missing))

    def compact(s):
        inside = lambda o: o.get('found') and 0 <= o['leftPct'] <= 100 and 0 <= o['topPct'] <= 100
        pins = [[p['leftPct'], p['topPct']] if inside(p) else 0 for p in s.get('pins', [])]  # keep pin numbering
        ex = [[e['leftPct'], e['topPct']] for e in s.get('exits', []) if inside(e)] or 0
        vp = s.get('viewport') or {'width': 1280, 'height': 800}
        return [s['name'], page_label(s.get('page')) + (s.get('hash') or ''), vp['width'], vp['height'],
                units.get(s['id'], ''), pins, ex]

    # demo links: flows.json first, else computed from site + app
    site = a.site or (cfg.get('deploy') or {}).get('site') or ''
    app_name, app_path = '', ''
    if a.app:
        if not cfg.get('_root'):
            fail('--app needs kit.config.json (run the kickoff skill first)')
        ae = app_entry(cfg, a.app)
        app_name, app_path = ae.get('name') or ae['id'], ae['path']
    if site and app_path:
        flows.setdefault('home', app_url(site, app_path))
        for f in flows['flows']:
            sid = first_screen(f)
            if not f.get('url') and sid in by:
                f['url'] = screen_url(site, app_path, by[sid].get('page'), by[sid].get('hash'))
    site = site or flows.get('home', '')
    for f in flows['flows']:
        if f.get('url') and site and not check_url(f['url'], site):
            fail(f'link of {f["id"]} ({f["url"]}) is not on site {site} (https required)')
    nolink = [f['id'] for f in flows['flows'] if not f.get('url')]
    if nolink and len(nolink) < len(flows['flows']):
        print('WARNING: flows without a demo link:', ', '.join(nolink))
    elif nolink:
        print('WARNING: no demo links (set deploy.site, pass --site/--app, or run demo_links.py fill); the board has no demo buttons')

    lang = cfg
    page = a.page or (t(lang, 'wireflow.page', pbi=a.pbi, feature=a.feature) if a.pbi and a.feature else 'Wireflow')
    title = a.title or (t(lang, 'wireflow.title', feature=a.feature, version=a.version) if a.feature and a.version
                        else ' · '.join(x for x in ('Wireflow', a.feature) if x))
    ds = version_label(cfg) if cfg.get('_ds') else ''
    meta = a.meta or ' · '.join(x for x in (a.pbi, a.feature, app_name, ds) if x)
    labels = {k: t(lang, 'wireflow.' + k) for k in LABELS}
    labels['start'] = t(lang, 'wireflow.start', start='{start}')

    data = {
        'page': page, 'pageId': a.page_id.replace('-', ':'), 'title': title, 'meta': meta, 'width': a.width,
        'scale': a.scale, 'imgSuffix': IMG_SUFFIX, 'L': labels, 'C': colours(a.accent),
        'screens': {i: compact(by[i]) for i in used},
        'flows': [[f['id'], f['name'], [[r.get('label', ''), r['items']] for r in f['rows']], f.get('url', ''), f.get('start', '')]
                  for f in flows['flows']],
        'home': flows.get('home', ''),
        'offflow': flows.get('offflow', []),
    }
    os.makedirs(os.path.join(a.out, 'images'), exist_ok=True)
    tpl = TEMPLATE.read_text(encoding='utf-8')
    body = '\n'.join(l for l in tpl.splitlines() if not l.startswith('//'))  # drop header comments: shortest code
    code = body.replace('__DATA__', json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    open(os.path.join(a.out, 'code.js'), 'w', encoding='utf-8').write(code)
    try:
        from PIL import Image
    except ImportError:
        Image = None
    # Sharp images: send the original PNGs of the capture step (--png, captured at deviceScaleFactor 2) unchanged;
    # without them, convert the --spec images to high-quality JPEG at the same pixel size.
    for i in used:
        png = os.path.join(a.png, i + '.png') if a.png else ''
        dst = os.path.join(a.out, 'images', i + '.jpg')
        if png and os.path.exists(png):
            open(dst[:-4] + '.png', 'wb').write(open(png, 'rb').read())
            continue
        src = os.path.join(a.spec, by[i].get('file', i + '.png'))
        if not os.path.exists(src):
            fail(f'image of {i} not found: {src}')
        if Image:
            Image.open(src).convert('RGB').save(dst, quality=94, optimize=True, subsampling=0)
        else:
            print(f'WARNING: Pillow not installed; copying {os.path.basename(src)} as is')
            dst = dst[:-4] + os.path.splitext(src)[1]
            open(dst, 'wb').write(open(src, 'rb').read())
    nedges = sum(1 for f in flows['flows'] for r in f['rows'] for it in r['items'] if it[0] == 'e')
    plan = {'screens': used, 'flows': len(flows['flows']), 'edges': nedges, 'codeBytes': len(code.encode('utf-8')),
            'page': page, 'title': title}
    json.dump(plan, open(os.path.join(a.out, 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'code.js {plan["codeBytes"]} bytes · {len(flows["flows"])} flows · {len(used)} screens · {nedges} edges · '
          f'images in {os.path.join(a.out, "images")}')


MAPJS = """const b = await figma.getNodeByIdAsync(%(root)s);
if (!b) throw new Error('Board not found: ' + %(root)s);
let p = b; while (p && p.type !== 'PAGE') p = p.parent;
await figma.setCurrentPageAsync(p);
const S = %(suffix)s, m = {}, imgs = {};
for (const n of b.findAll(x => x.type === 'FRAME' && x.name.endsWith(S))) { const id = n.name.slice(0, -S.length); if (!m[id]) { m[id] = n.parent.id; imgs[id] = n.id; } }
return { ...m, _imgs: imgs, _board: b.id, _title: b.name, _page: p.id, _pageName: p.name };"""

RETITLEJS = """const b = await figma.getNodeByIdAsync(%(root)s);
if (!b) throw new Error('Board not found: ' + %(root)s);
let p = b; while (p && p.type !== 'PAGE') p = p.parent;
await figma.setCurrentPageAsync(p);
const T = %(title)s, S = %(suffix)s;
b.name = T;
const h = b.findOne(x => x.type === 'TEXT' && x.name === 'Board title');
if (h) { await figma.loadFontAsync(h.fontName); h.characters = T; }
const first = {}, imgs = {}; let copied = 0;
for (const n of b.findAll(x => x.type === 'FRAME' && x.name.endsWith(S))) {
  const id = n.name.slice(0, -S.length);
  if (!first[id]) { first[id] = n; imgs[id] = n.id; continue; }
  if (n.fills !== figma.mixed && JSON.stringify(n.fills) !== JSON.stringify(first[id].fills)) { n.fills = first[id].fills; copied++; }
}
return { board: b.id, title: b.name, titleText: !!h, copiedFills: copied, _imgs: imgs };"""


def js_args(a, **extra):
    d = {'root': json.dumps(a.root.replace('-', ':')), 'suffix': json.dumps(IMG_SUFFIX)}
    d.update({k: json.dumps(v, ensure_ascii=False) for k, v in extra.items()})
    return d


def mapjs(a):
    print(MAPJS % js_args(a))


def retitlejs(a):
    print(RETITLEJS % js_args(a, title=a.title))


def setmap(a):
    r = read_json(a.json)
    if '_board' not in r:
        fail(f'{a.json} is not a mapjs result (no _board)')
    conf = json.load(open(a.config, encoding='utf-8')) if os.path.exists(a.config) else {}
    if a.file:
        conf['figma_file'] = re.sub(r'[?&]node-id=[^&]*', '', a.file).rstrip('?&')
    conf['figma_board'] = r.get('_board', '')
    conf['figma_page'] = r.get('_pageName', '')
    conf['figma'] = {k: v for k, v in r.items() if not k.startswith('_')}
    json.dump(conf, open(a.config, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"Wrote {len(conf['figma'])} screens, board {conf['figma_board']} ({r.get('_title', '')}) "
          f"on page \"{conf['figma_page']}\" to {a.config}")


def upload(a):
    m = read_json(a.urls)
    ids, urls = m['imageScreens'], m['urls']
    if len(ids) != len(urls):
        fail(f'{len(ids)} screens but {len(urls)} URLs')
    ok = 0
    for i, u in zip(ids, urls):
        base = os.path.join(a.out, 'images', i)
        p = next((base + e for e in ('.jpg', '.png', '.webp') if os.path.exists(base + e)), None)
        if not p:
            print(f'ERROR: no image for {i} in {os.path.dirname(base)}')
            continue
        ctype = {'.jpg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}[os.path.splitext(p)[1]]
        req = urllib.request.Request(u, data=open(p, 'rb').read(), method='POST', headers={'Content-Type': ctype})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                ok += 200 <= r.status < 300
        except Exception as e:  # noqa: BLE001
            print('ERROR: upload failed for', i, e)
    print(f'Uploaded {ok}/{len(ids)} images')
    if ok != len(ids):
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description='Wireflow board for Figma. Commands: build, upload, mapjs, retitlejs, setmap.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build', help='write code.js, images/ and plan.json for one use_figma call')
    b.add_argument('--spec', required=True, help='folder with screens.json and the screen images')
    b.add_argument('--flows', required=True, help='flows.json')
    b.add_argument('--out', required=True, help='output folder (use the scratchpad)')
    b.add_argument('--pbi', default='', help='work-item code, e.g. "PBI 1234" (page name, meta)')
    b.add_argument('--feature', default='', help='feature name (page name, title, meta)')
    b.add_argument('--version', default='', help='package version for the title, e.g. 1.2.0')
    b.add_argument('--title', default='', help='board title (default from --feature and --version)')
    b.add_argument('--meta', default='', help='line under the title (default: pbi · feature · app · DS version label)')
    b.add_argument('--page', default='', help='page name to create or reuse (default "[<pbi>] <feature>")')
    b.add_argument('--page-id', default='', help='existing page id (node-id of the page in the Figma link); overrides --page')
    b.add_argument('--app', default='', help='app id from kit.config.json > apps (demo links, meta)')
    b.add_argument('--site', default='', help='https base URL of the demo site (default: kit.config.json > deploy.site)')
    b.add_argument('--png', default='', help='folder of original capture PNGs (<Sxx>.png, deviceScaleFactor 2): sent unchanged')
    b.add_argument('--scale', type=float, default=0.5, help='image size on the board vs capture (web 1280px: 0.5; mobile 390px: 0.75)')
    b.add_argument('--width', type=int, default=3200, help='board width in px')
    b.add_argument('--accent', default='#2563EB', help='accent colour of buttons, pins and rings (#RRGGBB)')
    u = sub.add_parser('upload', help='POST images to the upload URLs from upload_assets')
    u.add_argument('--out', required=True); u.add_argument('--urls', required=True)
    m = sub.add_parser('mapjs', help='print use_figma code that reads screen card and image frame ids of a board')
    m.add_argument('--root', required=True, help='board node id (123:456 or 123-456)')
    rt = sub.add_parser('retitlejs', help='print use_figma code that renames a board in place and syncs repeated images')
    rt.add_argument('--root', required=True); rt.add_argument('--title', required=True)
    sm = sub.add_parser('setmap', help='write the mapjs result into the package config (pkg.json)')
    sm.add_argument('--config', required=True); sm.add_argument('--json', required=True)
    sm.add_argument('--file', default='', help='Figma file link')
    a = ap.parse_args()
    {'build': build, 'upload': upload, 'mapjs': mapjs, 'retitlejs': retitlejs, 'setmap': setmap}[a.cmd](a)


if __name__ == '__main__':
    main()
