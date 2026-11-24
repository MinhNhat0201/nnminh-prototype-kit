#!/usr/bin/env python3
"""Prepare data and images for the Figma wireflow board (skill `wireflow`), and map the board back into a package.

Commands:
  build     --spec <dir with screens.json + images> --flows <flows.json> --out <dir>
            [--pbi "PBI 1234" --feature "Scheduled tasks" --version 1.2.0] [--app <app id>] [--site <https URL>]
            [--title ...] [--meta ...] [--page ... | --page-id 123:456] [--png <dir>] [--scale 0.5] [--width 3200]
            -> <out>/code.js (send verbatim to use_figma), <out>/images/<Sxx>.png|jpg, <out>/plan.json
            The use_figma return value has `map` (same shape as the mapjs result): save the return as <out>/map.json.
  images    --spec <dir> --out <dir> [--png <dir>] [--screens S01,S02 | --changed <changed.json>] [--map <map.json>]
            writes <out>/images/<Sxx> for an in-place update without building the board again; with --map also
            <out>/pending.json (imageScreens + nodeIds of their image frames, for upload_assets and upload)
  update    --map <map.json> --spec <dir> --flows <flows.json> --out <dir> [--png <dir>] [--prune] [--app ...]
            compares the board (map.json: mapjs result or an earlier build/update return) with flows.json: new
            screens, new or relabelled edges, new rows and flows, row labels, flow names. Rows pair by label, then by
            their screen ids, never by position (a row inserted in the middle is drawn there). Prints the diff (DIFF lines)
            and writes <out>/update.js (send verbatim to use_figma), images of the new screens, <out>/plan.json.
            Removed edges, chips, rows and flows are reported and kept, unless --prune. Cards are never deleted:
            with --prune, cards of screens in no flow move to the off-flow section, so links already sent keep working.
  upload    --out <dir> --urls <urls.json>
            urls.json: {"imageScreens": [...], "urls": [...]} in the order upload_assets returned them; without
            imageScreens, <out>/pending.json (from `images --map`) gives the order.
            POSTs each image to its URL (images never pass through the model context).
  mapjs     --root <board node id>          prints use_figma code: screen id -> card node, image frame node, flows
  retitlejs --root <board node id> --title "..."   prints use_figma code: rename the board in place, copy image
            fills to repeated frames of the same screen (node ids stay, links already sent keep working)
  redrawjs  --map <map.json> --screens <screens.json> (--ids S01,S02 | --changed <changed.json>) [--accent #RRGGBB]
            prints use_figma code that clears the pins and click rings of those screens' image frames and draws them
            again from screens.json with the board template's drawing code (after a new image: step 3b). Node ids stay.
            `images --map` writes the same code to <out>/redraw.js.
  setmap    --config <pkg.json> --json <mapjs result | build/update return> [--file <Figma file link>]
            writes figma_file, figma_board, figma_page, figma (screen id -> card node) into the package config
  --selftest  diff checks, and the generated code run against a small Figma stand-in (figma_mock.js; needs node)

Never reads HTML: only screens.json (capture output of `annotate`) and flows.json.
"""
import argparse
import contextlib
import difflib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
from demo_links import app_url, check_url, first_screen, load_screens, read_json, screen_url  # noqa: E402
from kitconf import load, t, version_label, app as app_entry  # noqa: E402

ASSETS = HERE.parent / 'assets'
IMG_SUFFIX = ' · image'  # default layer-name suffix of image frames (kit.config.json > figma.imageSuffix changes it)


def suffixes(cfg):
    """[suffix the board is built with, other suffixes mapjs/retitlejs accept]: figma.imageSuffix, else the English one,
    plus the locale's (wireflow.imageSuffix) and the English one, so boards built by other tools or in another
    language still map."""
    cfg = cfg or {}
    own = ((cfg.get('figma') or {}).get('imageSuffix')) or IMG_SUFFIX
    loc = t(cfg if cfg.get('language') else 'en', 'wireflow.imageSuffix')
    return list(dict.fromkeys([own, loc if loc != 'wireflow.imageSuffix' else IMG_SUFFIX, IMG_SUFFIX]))


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


def js(name):
    """An asset without its comment-only lines (shortest code)."""
    return '\n'.join(l for l in (ASSETS / name).read_text(encoding='utf-8').splitlines() if not l.lstrip().startswith('//'))


def assemble(template, data):
    """Template + drawing helpers + board reader + data: the code sent verbatim to use_figma."""
    code = js(template).replace('__LIB__', js('wireflow-lib.js')).replace('__READ__', js('wireflow-read.js'))
    return code.replace('__DATA__', json.dumps(data, ensure_ascii=False, separators=(',', ':')))


def compact(s, units):
    inside = lambda o: o.get('found') and 0 <= o['leftPct'] <= 100 and 0 <= o['topPct'] <= 100
    pins = [[p['leftPct'], p['topPct']] if inside(p) else 0 for p in s.get('pins', [])]  # keep pin numbering
    ex = [[e['leftPct'], e['topPct']] for e in s.get('exits', []) if inside(e)] or 0
    vp = s.get('viewport') or {'width': 1280, 'height': 800}
    return [s['name'], page_label(s.get('page')) + (s.get('hash') or ''), vp['width'], vp['height'],
            units.get(s['id'], ''), pins, ex]


def check_flows(flows, by):
    """Screens used as `n` in flow order, then offflow; ERROR for a screen missing from screens.json."""
    used = []
    for f in flows['flows']:
        for r in f['rows']:
            for it in r['items']:
                if it[0] in ('n', 'chip') and it[1] not in by:
                    fail(f'{f["id"]} uses {it[1]} but screens.json has no such screen')
                if it[0] == 'n' and it[1] not in used:
                    used.append(it[1])
    for i in flows.get('offflow', []):
        if i not in by:
            fail(f'offflow lists {i} but screens.json has no such screen')
    return used + [i for i in flows.get('offflow', []) if i not in used]


def fill_links(cfg, a, flows, by):
    """Fill flow `url` and `home` from site + app (values in flows.json win); ERROR for links off the site. Returns the app name."""
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
    return app_name


def flow_data(f):
    return [f['id'], f.get('name', ''), [[r.get('label', ''), r['items']] for r in f['rows']], f.get('url', ''), f.get('start', '')]


def base_data(cfg, a, by, ids, units):
    L = {k: t(cfg, 'wireflow.' + k) for k in LABELS}
    L['start'] = t(cfg, 'wireflow.start', start='{start}')
    return {'imgSuffix': suffixes(cfg)[0], 'sfx': suffixes(cfg), 'L': L, 'C': colours(a.accent), 'width': a.width,
            'scale': a.scale, 'screens': {i: compact(by[i], units) for i in ids}}


def write_images(spec, by, ids, png, out):
    """<out>/images/<id>.png (original capture PNG from --png, unchanged) or .jpg (converted from the --spec image)."""
    os.makedirs(os.path.join(out, 'images'), exist_ok=True)
    try:
        from PIL import Image
    except ImportError:
        Image = None
    # Sharp images: send the original PNGs of the capture step (--png, captured at deviceScaleFactor 2) unchanged;
    # without them, convert the --spec images to high-quality JPEG at the same pixel size.
    for i in ids:
        src_png = os.path.join(png, i + '.png') if png else ''
        dst = os.path.join(out, 'images', i + '.jpg')
        for old in (dst, dst[:-4] + '.png', dst[:-4] + '.webp'):  # an older image of another type would win in upload
            if os.path.exists(old):
                os.remove(old)
        if src_png and os.path.exists(src_png):
            shutil.copyfile(src_png, dst[:-4] + '.png')
            continue
        src = os.path.join(spec, by[i].get('file', i + '.png'))
        if not os.path.exists(src):
            fail(f'image of {i} not found: {src}')
        if Image:
            Image.open(src).convert('RGB').save(dst, quality=94, optimize=True, subsampling=0)
        else:
            print(f'WARNING: Pillow not installed; copying {os.path.basename(src)} as is')
            shutil.copyfile(src, dst[:-4] + os.path.splitext(src)[1])


def build(a):
    cfg = load(require=False, app=a.app or None) or {'language': 'en', 'deploy': {}, '_ds': None}  # apps[].ds: version label
    by = load_screens(os.path.join(a.spec, 'screens.json'))
    flows = read_json(a.flows)
    used = check_flows(flows, by)
    missing = [i for i in by if i not in used]
    if missing:
        print('WARNING: screens in no flow and not in offflow:', ', '.join(missing))
    app_name = fill_links(cfg, a, flows, by)
    nolink = [f['id'] for f in flows['flows'] if not f.get('url')]
    if nolink and len(nolink) < len(flows['flows']):
        print('WARNING: flows without a demo link:', ', '.join(nolink))
    elif nolink:
        print('WARNING: no demo links (set deploy.site, pass --site/--app, or run demo_links.py fill); the board has no demo buttons')

    page = a.page or (t(cfg, 'wireflow.page', pbi=a.pbi, feature=a.feature) if a.pbi and a.feature else 'Wireflow')
    title = a.title or (t(cfg, 'wireflow.title', feature=a.feature, version=a.version) if a.feature and a.version
                        else ' · '.join(x for x in ('Wireflow', a.feature) if x))
    ds = version_label(cfg) if cfg.get('_ds') else ''
    meta = a.meta or ' · '.join(x for x in (a.pbi, a.feature, app_name, ds) if x)
    data = dict(base_data(cfg, a, by, used, flows.get('units', {})), page=page, pageId=a.page_id.replace('-', ':'),
                title=title, meta=meta, flows=[flow_data(f) for f in flows['flows']], home=flows.get('home', ''),
                offflow=flows.get('offflow', []))
    os.makedirs(a.out, exist_ok=True)
    code = assemble('wireflow-template.js', data)
    open(os.path.join(a.out, 'code.js'), 'w', encoding='utf-8').write(code)
    write_images(a.spec, by, used, a.png, a.out)
    nedges = sum(1 for f in flows['flows'] for r in f['rows'] for it in r['items'] if it[0] == 'e')
    plan = {'screens': used, 'flows': len(flows['flows']), 'edges': nedges, 'codeBytes': len(code.encode('utf-8')),
            'page': page, 'title': title}
    json.dump(plan, open(os.path.join(a.out, 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'code.js {plan["codeBytes"]} bytes · {len(flows["flows"])} flows · {len(used)} screens · {nedges} edges · '
          f'images in {os.path.join(a.out, "images")}')
    print(f'Save the use_figma return value as {os.path.join(a.out, "map.json")} (its "map": setmap, update, images --map).')


def read_map(p):
    """A board map: the mapjs result, or the `map` of a build/update return value."""
    r = read_json(p)
    r = r.get('map', r) if isinstance(r, dict) else r
    if not isinstance(r, dict) or '_board' not in r:
        fail(f'{p} is not a board map (no _board): use the mapjs result or the build/update return value')
    return r


# ---------- in-place update: diff of the board (map) with flows.json ----------

def key(it, out_default):
    """Comparable key of a row item, from flows.json (['e', label, flag]) or from the board (with a trailing node id)."""
    k = it[0]
    if k == 'e':
        return 'e:%s|%s' % (it[1], it[2] if len(it) > 2 and it[2] in ('x', 'u') else '')
    if k == 'out':
        return 'out:' + (it[1] or out_default)
    if k == '?':
        return '?:' + it[-1]
    return '%s:%s' % (k, it[1])


def describe(it):
    if it[0] == 'e':
        return '"%s"' % it[1] + (' [%s]' % it[2] if len(it) > 2 and it[2] in ('x', 'u') else '')
    return {'chip': '↩ ' + it[1], 'out': '[%s]' % it[1]}.get(it[0], it[1])


def kind(it):
    return {'e': 'edge', 'out': 'out-of-scope box', 'chip': 'back chip', 'n': 'screen'}.get(it[0], 'layer')


def row_screens(items):
    return {it[1] for it in items if it[0] in ('n', 'chip')}


def pair_rows(old_rows, new_rows):
    """For each row of flows.json, the index of its row on the board (None = a new row). Never by position: first the
    same non-empty row label, then the same set of screen ids (screens and back chips), then the board row sharing the
    most screen ids. Board rows left unpaired are rows flows.json no longer has."""
    res, used = [None] * len(new_rows), set()
    for i, r in enumerate(new_rows):
        lab = r.get('label', '')
        j = next((j for j, o in enumerate(old_rows) if lab and j not in used and o.get('label', '') == lab), None)
        if j is not None:
            res[i] = j
            used.add(j)
    for i, r in enumerate(new_rows):
        s = row_screens(r['items'])
        j = next((j for j, o in enumerate(old_rows) if s and res[i] is None and j not in used and row_screens(o['items']) == s), None)
        if j is not None:
            res[i] = j
            used.add(j)
    cand = sorted((-len(row_screens(r['items']) & row_screens(o['items'])), i, j) for i, r in enumerate(new_rows)
                  for j, o in enumerate(old_rows) if res[i] is None and j not in used)
    for score, i, j in cand:
        if score < 0 and res[i] is None and j not in used:
            res[i] = j
            used.add(j)
    return res


def plan_update(bm, flows, out_default, prune=False):
    """(data for wireflow-update.js, diff lines, new cards to draw). Pure: works on the map and flows.json only.

    Rows of a flow pair by row label, then by their screen ids (pair_rows), never by position: a row inserted in the
    middle is drawn at its place and the rows after it keep their nodes. Items inside a row match by sequence (difflib). Card nodes are reused, and moved
    when a screen changed place, so their ids and the links to them stay. An edge whose label or flag changed between
    the same neighbours is replaced in place (relabel). Removed items stay on the board unless prune."""
    old_flows = bm.get('_flows') or {}
    off = bm.get('_off') or None
    where, cards = {}, {}  # card node id -> 'WF-01 row 2'; screen id -> its card node ids in board order
    for fid, of in old_flows.items():
        for ri, r in enumerate(of['rows']):
            for it in r['items']:
                if it[0] == 'n':
                    cards.setdefault(it[1], []).append(it[-1])
                    where[it[-1]] = f'{fid} row {ri + 1}'
    for it in (off or {}).get('items', []):
        if it[0] == 'n':
            cards.setdefault(it[1], []).append(it[-1])
            where[it[-1]] = 'off-flow'
    K = lambda it: key(it, out_default)
    claimed, diff, makes, remove, to_off = set(), [], [], [], []

    # pass 1: rows to compare (flows by id, rows by label and screens: pair_rows); equal items keep their nodes
    jobs, row_paired = [], {}
    for f in flows['flows']:
        of = old_flows.get(f['id'])
        pairs = pair_rows(of['rows'], f['rows']) if of else [None] * len(f['rows'])
        row_paired[f["id"]] = {j for j in pairs if j is not None}
        for ri, r in enumerate(f['rows']):
            orow = of['rows'][pairs[ri]] if pairs[ri] is not None else None
            nxt = next((of['rows'][j] for j in pairs[ri + 1:] if j is not None), None) if of and not orow else None
            jobs.append({'here': f'{f["id"]} row {ri + 1}', 'old': orow, 'olds': orow['items'] if orow else [],
                         'new': r['items'], 'label': r.get('label', ''), 'flow': {'id': of['id']} if of else {'new': f['id']},
                         'existing_flow': bool(of), 'before': (nxt.get('labelId') or nxt['id']) if nxt else ''})
    jobs.append({'here': 'off-flow', 'old': off, 'olds': (off or {}).get('items', []), 'off': True,
                 'new': [['n', i] for i in flows.get('offflow', [])]})
    for j in jobs:
        j['ops'] = difflib.SequenceMatcher(None, [K(x) for x in j['olds']], [K(x) for x in j['new']], autojunk=False).get_opcodes()
        for tag, i1, i2, _, _ in j['ops']:
            if tag == 'equal':
                claimed.update(x[-1] for x in j['olds'][i1:i2])

    # pass 2: new items in order; a new screen takes a free card of the same screen (same row first) or is drawn
    def place(n, here, prefer):
        if n[0] == 'n':
            for nid in [x for x in prefer if x in cards.get(n[1], [])] + cards.get(n[1], []):
                if nid not in claimed:
                    claimed.add(nid)
                    if where.get(nid) != here:
                        diff.append(f'moved screen {n[1]}: {where.get(nid)} -> {here}')
                    return ['id', nid]
            makes.append(n[1])
            diff.append(f'added screen {n[1]} in {here}')
            return ['make', n]
        diff.append(f'added {kind(n)} {describe(n)} in {here}')
        return ['make', n]

    for j in jobs:
        final, here, olds, news = [], j['here'], j['olds'], j['new']
        for tag, i1, i2, j1, j2 in j['ops']:
            if tag == 'equal':
                final += [['id', x[-1]] for x in olds[i1:i2]]
                continue
            os_, ns = olds[i1:i2], news[j1:j2]
            pairs = dict(zip([id(n) for n in ns if n[0] == 'e'], [o for o in os_ if o[0] == 'e'])) if tag == 'replace' else {}
            prefer = [o[-1] for o in os_ if o[0] == 'n']
            for n in ns:
                o = pairs.get(id(n))
                if o:
                    diff.append(f'edge label in {here}: {describe(o[:3])} -> {describe(n)}')
                    remove.append(o[-1])
                    final.append(['make', n])
                else:
                    final.append(place(n, here, prefer))
            paired = {id(o) for o in pairs.values()}
            final += [['left', o] for o in os_ if id(o) not in paired]
        j['final'] = final

    # pass 3: old items with no match: kept (stale) or, with prune, removed; cards are never removed
    def leftover(o, j, out):
        here = j['here']
        if o[0] == 'n':
            if o[-1] in claimed:
                return  # the card moved to its new place
            claimed.add(o[-1])
            if prune and not j.get('off'):
                diff.append(f'screen {o[1]} is in no flow: card moved to the off-flow section (was {here})')
                to_off.append(['id', o[-1]])
                return
            diff.append(f'screen {o[1]} is no longer listed in {here}: card kept' + ('' if j.get('off') else ' (--prune moves it to off-flow)'))
        elif o[0] != '?':
            if prune:
                diff.append(f'removed {kind(o)} {describe(o)} in {here}')
                remove.append(o[-1])
                return
            diff.append(f'removed {kind(o)} {describe(o)} in {here}: kept on the board, stale (--prune removes it)')
        out.append(['id', o[-1]])

    rows = []
    for j in jobs:
        final = []
        for x in j['final']:
            if x[0] == 'left':
                leftover(x[1], j, final)
            else:
                final.append(x)
        j['final'] = final

    # rows and flows that flows.json no longer has
    new_ids = {f['id']: f for f in flows['flows']}
    for fid, of in old_flows.items():
        nf = new_ids.get(fid)
        gone = [(ri, r) for ri, r in enumerate(of['rows']) if not nf or ri not in row_paired.get(fid, ())]
        if not gone:
            continue
        name = lambda ri, r: f'{fid} row {ri + 1}' + (f' "{r["label"]}"' if r.get('label') else '')
        if not prune:
            diff.append((f'flow {fid}' if not nf else ('row ' if len(gone) == 1 else 'rows ') + ', '.join(name(ri, r) for ri, r in gone))
                        + ' not in flows.json: kept on the board (--prune removes it)')
            continue
        keep_flow = False
        for ri, r in gone:
            here = name(ri, r)
            if any(o[0] == '?' for o in r['items']):
                diff.append(f'{here} has layers the kit did not make: kept')
                keep_flow = True
                continue
            for o in r['items']:
                if o[0] == 'n' and o[-1] not in claimed:
                    claimed.add(o[-1])
                    diff.append(f'screen {o[1]} is in no flow: card moved to the off-flow section (was {here})')
                    to_off.append(['id', o[-1]])
            remove += [r['id']] + ([r['labelId']] if r.get('labelId') else [])
            diff.append(f'removed row {here}')
        if not nf and not keep_flow:
            remove.append(of['id'])
            diff.append(f'removed flow {fid}')

    new_flows, titles, prev = [], [], None
    for f in flows['flows']:
        of = old_flows.get(f['id'])
        name = f'{f["id"]} · {f.get("name", "")}'
        if not of:
            new_flows.append([flow_data(dict(f, rows=[])), prev])
            diff.append(f'new flow {f["id"]} ({len(f["rows"])} rows)')
        elif of.get('titleId') and of.get('title') != name:
            titles.append([of['titleId'], name])
            diff.append(f'flow name {f["id"]}: "{of.get("title")}" -> "{name}"')
        prev = {'id': of['id']} if of else {'new': f['id']}
    for j in jobs:
        if j.get('off'):
            final = j['final'] + to_off
            if final and [x[1] for x in final] != [x[-1] for x in j['olds']]:
                rows.append({'off': True, 'row': (off or {}).get('row', ''), 'items': final})
            continue
        op = {'flow': j['flow'], 'row': j['old']['id'] if j['old'] else '', 'items': j['final']}
        if not j['old']:
            op['label'] = ['', j['label']]
            if j['before']:
                op['before'] = j['before']  # drawn above the next row the board already has, not at the end
            if j['existing_flow']:
                diff.append(f'new row {j["here"]}' + (f' "{j["label"]}"' if j['label'] else ''))
        elif j['old'].get('label', '') != j['label']:
            op['label'] = [j['old'].get('labelId', ''), j['label']]
            diff.append(f'row label {j["here"]}: "{j["old"].get("label", "")}" -> "{j["label"]}"')
        if 'label' in op or [x[1] for x in j['final']] != [x[-1] for x in j['olds']]:
            rows.append(op)
    data = {'root': bm['_board'], 'newFlows': new_flows, 'rows': rows, 'remove': remove, 'titles': titles}
    return data, diff, makes


def update(a):
    cfg = load(require=False, app=a.app or None) or {'language': 'en', 'deploy': {}, '_ds': None}
    bm = read_map(a.map)
    if '_flows' not in bm:
        fail(f'{a.map} has no _flows (read by an older kit): run the mapjs code of this kit version and save its result')
    by = load_screens(os.path.join(a.spec, 'screens.json'))
    flows = read_json(a.flows)
    used = check_flows(flows, by)
    fill_links(cfg, a, flows, by)
    data, diff, makes = plan_update(bm, flows, t(cfg, 'wireflow.outOfScope'), a.prune)
    chips = [it[1] for f in flows['flows'] for r in f['rows'] for it in r['items'] if it[0] == 'chip']
    data.update(base_data(cfg, a, by, list(dict.fromkeys(used + chips)), flows.get('units', {})))
    os.makedirs(a.out, exist_ok=True)
    code = assemble('wireflow-update.js', data)
    open(os.path.join(a.out, 'update.js'), 'w', encoding='utf-8').write(code)
    write_images(a.spec, by, list(dict.fromkeys(makes)), a.png, a.out)
    plan = {'board': bm['_board'], 'diff': diff, 'newScreens': makes, 'rowsChanged': len(data['rows']),
            'removed': len(data['remove']), 'codeBytes': len(code.encode('utf-8'))}
    json.dump(plan, open(os.path.join(a.out, 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for line in diff:
        print('DIFF ' + line)
    if not diff:
        print('No change: the board matches flows.json. Nothing to send.')
        return
    print(f'update.js {plan["codeBytes"]} bytes · {len(makes)} new screens · {len(data["rows"])} rows changed · '
          f'{len(data["remove"])} nodes removed. Send update.js verbatim; save its return value as the new map.json.')


def images(a):
    by = load_screens(os.path.join(a.spec, 'screens.json'))
    if a.changed:
        ch = read_json(a.changed)
        ids = list(dict.fromkeys((ch.get('changed') or []) + (ch.get('new') or [])))
    elif a.screens:
        ids = [x.strip() for x in a.screens.split(',') if x.strip()]
    else:
        ids = list(by)
    bad = [i for i in ids if i not in by]
    if bad:
        fail('not in screens.json: ' + ', '.join(bad))
    write_images(a.spec, by, ids, a.png, a.out)
    print(f'{len(ids)} images in {os.path.join(a.out, "images")}: {", ".join(ids) or "(none)"}')
    if a.map:
        imgs = read_map(a.map).get('_imgs') or {}
        on, off = [i for i in ids if i in imgs], [i for i in ids if i not in imgs]
        if off:
            print('WARNING: not on the board yet (add them with `update` first; its return lists their image frames):', ', '.join(off))
        pend = {'imageScreens': on, 'nodeIds': [imgs[i] for i in on]}
        json.dump(pend, open(os.path.join(a.out, 'pending.json'), 'w', encoding='utf-8'), indent=1)
        print(f'upload_assets: count {len(on)}, nodeIds {json.dumps(pend["nodeIds"])} (in {os.path.join(a.out, "pending.json")})')
        if on:
            code = redraw_code(a, read_map(a.map), by, on)
            open(os.path.join(a.out, 'redraw.js'), 'w', encoding='utf-8').write(code)
            print(f'After the upload send {os.path.join(a.out, "redraw.js")} verbatim (use_figma): it redraws pins and click rings.')


def redraw_code(a, bm, by, ids):
    """use_figma code that clears and redraws the pins and click rings of these screens (wireflow-redraw.js)."""
    cfg = load(require=False, app=getattr(a, 'app', '') or None) or {'language': 'en'}
    look = argparse.Namespace(accent=getattr(a, 'accent', '') or '#2563EB', width=3200, scale=0.5)
    return assemble('wireflow-redraw.js', dict(base_data(cfg, look, by, ids, {}), root=bm['_board'], ids=ids))


def redrawjs(a):
    by = load_screens(a.screens)
    bm = read_map(a.map)
    if a.changed:
        ch = read_json(a.changed)
        ids = list(dict.fromkeys((ch.get('changed') or []) + (ch.get('new') or [])))
    else:
        ids = [x.strip() for x in a.ids.split(',') if x.strip()]
    if not ids:
        fail('no screens: pass --ids S01,S02 or --changed <changed.json>')
    bad = [i for i in ids if i not in by]
    if bad:
        fail('not in screens.json: ' + ', '.join(bad))
    off = [i for i in ids if i not in (bm.get('_imgs') or {})]
    if off:
        print('// WARNING: not on the board (add them with `update` first): ' + ', '.join(off))
    print(redraw_code(a, bm, by, [i for i in ids if i not in off]))


MAPJS = """const b = await figma.getNodeByIdAsync(%(root)s);
if (!b) throw new Error('Board not found: ' + %(root)s);
let p = b; while (p && p.type !== 'PAGE') p = p.parent;
await figma.setCurrentPageAsync(p);
%(read)s
return readBoard(b, p, %(suffix)s);"""

RETITLEJS = """const b = await figma.getNodeByIdAsync(%(root)s);
if (!b) throw new Error('Board not found: ' + %(root)s);
let p = b; while (p && p.type !== 'PAGE') p = p.parent;
await figma.setCurrentPageAsync(p);
const T = %(title)s, SS = %(suffix)s;
const sfx = name => SS.find(x => name.endsWith(x));
b.name = T;
const h = b.findOne(x => x.type === 'TEXT' && x.name === 'Board title');
if (h) { await figma.loadFontAsync(h.fontName); h.characters = T; }
const first = {}, imgs = {}; let copied = 0;
for (const n of b.findAll(x => x.type === 'FRAME' && sfx(x.name))) {
  const id = n.name.slice(0, -sfx(n.name).length).trim();
  if (!first[id]) { first[id] = n; imgs[id] = n.id; continue; }
  if (n.fills !== figma.mixed && JSON.stringify(n.fills) !== JSON.stringify(first[id].fills)) { n.fills = first[id].fills; copied++; }
}
return { board: b.id, title: b.name, titleText: !!h, copiedFills: copied, _imgs: imgs };"""


def js_args(a, **extra):
    cfg = load(require=False) or {'language': 'en'}
    d = {'root': json.dumps(a.root.replace('-', ':')), 'suffix': json.dumps(suffixes(cfg), ensure_ascii=False)}
    d.update({k: json.dumps(v, ensure_ascii=False) for k, v in extra.items()})
    return d


def mapjs_code(a):
    return MAPJS % dict(js_args(a), read=js('wireflow-read.js'))


def mapjs(a):
    print(mapjs_code(a))


def retitlejs(a):
    print(RETITLEJS % js_args(a, title=a.title))


def setmap(a):
    r = read_map(a.json)
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
    ids, urls = m.get('imageScreens'), m['urls']
    if ids is None:
        pend = os.path.join(a.out, 'pending.json')
        if not os.path.exists(pend):
            fail(f'{a.urls} has no imageScreens and {pend} does not exist (run `images --map`, or add imageScreens)')
        ids = read_json(pend)['imageScreens']
    if len(ids) != len(urls):
        fail(f'{len(ids)} screens but {len(urls)} URLs')
    ok = 0
    for i, u in zip(ids, urls):
        base = os.path.join(a.out, 'images', i)
        p = next((base + e for e in ('.jpg', '.png', '.webp') if os.path.exists(base + e)), None)
        if not p:
            print(f'ERROR: no image for {i} in {os.path.dirname(base)} (for an update run `images` first)')
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


# ---------- selftest ----------

def selftest():
    OUT = 'Out of scope'
    n = lambda s, nid: ['n', s, nid]
    e = lambda l, f, nid: ['e', l, f, nid]
    bm = {'S01': '1:10', 'S02': '1:20', 'S03': '1:30', '_board': '1:1', '_imgs': {}, '_off': None, '_flows': {
        'WF-01': {'id': '1:2', 'title': 'WF-01 · Create', 'titleId': '1:3', 'rows': [
            {'id': '1:4', 'label': '', 'labelId': '', 'items': [n('S01', '1:10'), e('Back to list', '', '1:11'), n('S02', '1:20')]},
            {'id': '1:5', 'label': 'From S02', 'labelId': '1:6', 'items': [e('Save', 'u', '1:21'), n('S03', '1:30')]}]}}}
    # K-B3: relabel, new edge and screen after the last card of the row, removed edge reported and kept
    flows = {'flows': [{'id': 'WF-01', 'name': 'Create', 'rows': [
        {'items': [['n', 'S01'], ['e', 'Close note', ''], ['n', 'S02'], ['e', 'Narrow screen', 'x'], ['n', 'S03d']]},
        {'label': 'From S02', 'items': [['n', 'S03']]}]}]}
    d, diff, makes = plan_update(bm, flows, OUT)
    txt = '\n'.join(diff)
    assert makes == ['S03d'], makes
    assert 'edge label in WF-01 row 1: "Back to list" -> "Close note"' in txt, txt
    assert 'added edge "Narrow screen" [x] in WF-01 row 1' in txt and 'added screen S03d in WF-01 row 1' in txt, txt
    assert 'removed edge "Save" [u] in WF-01 row 2: kept on the board, stale' in txt, txt
    assert len(d['rows']) == 1 and d['rows'][0]['row'] == '1:4', d['rows']  # row 2 keeps its nodes: no change sent
    assert [x[0] for x in d['rows'][0]['items']] == ['id', 'make', 'id', 'make', 'make'], d['rows'][0]
    assert d['remove'] == ['1:11'], d['remove']  # only the relabelled edge
    # --prune: stale edge removed; a flow no longer listed removed, its card moved to off-flow (never deleted)
    bm['_flows']['WF-09'] = {'id': '1:90', 'title': 'WF-09 · Old', 'titleId': '1:91', 'rows': [
        {'id': '1:92', 'label': '', 'labelId': '', 'items': [n('S09', '1:93'), e('Go', '', '1:94'), ['chip', 'S01', '1:95']]}]}
    d, diff, makes = plan_update(bm, flows, OUT, prune=True)
    txt = '\n'.join(diff)
    assert '1:21' in d['remove'] and '1:90' in d['remove'] and '1:93' not in d['remove'], d['remove']
    assert d['rows'][-1] == {'off': True, 'row': '', 'items': [['id', '1:93']]}, d['rows'][-1]
    assert 'removed flow WF-09' in txt and 'S09 is in no flow: card moved' in txt, txt
    d, diff, _ = plan_update(bm, flows, OUT)
    assert 'flow WF-09 not in flows.json: kept' in '\n'.join(diff) and '1:90' not in d['remove'], diff
    # a screen that changed place moves (same node); flow name and row label changes; a new row
    flows2 = {'flows': [{'id': 'WF-01', 'name': 'Create a note', 'rows': [
        {'items': [['n', 'S01'], ['e', 'Back to list', ''], ['n', 'S02']]},
        {'label': 'From S02, saved', 'items': [['e', 'Save', 'u'], ['n', 'S03']]},
        {'label': 'Old', 'items': [['n', 'S09'], ['e', 'Go', ''], ['out', '']]}]}]}
    del bm['_flows']['WF-09']
    bm['_off'] = {'id': '1:70', 'row': '1:71', 'items': [n('S09', '1:93')]}
    d, diff, makes = plan_update(bm, flows2, OUT)
    txt = '\n'.join(diff)
    assert not makes and 'moved screen S09: off-flow -> WF-01 row 3' in txt and 'no longer listed' not in txt, txt
    assert d['titles'] == [['1:3', 'WF-01 · Create a note']] and 'row label WF-01 row 2' in txt, (d['titles'], txt)
    new_row = next(r for r in d['rows'] if r['row'] == '')
    assert new_row['items'][0] == ['id', '1:93'] and new_row['label'] == ['', 'Old'] and 'new row WF-01 row 3 "Old"' in txt, new_row
    assert key(['out', ''], OUT) == key(['out', OUT, '1:5'], OUT) and key(['e', 'A', 'u'], OUT) == key(['e', 'A', 'u', '9:9'], OUT)
    # unchanged board: nothing to send
    same = {'flows': [{'id': 'WF-01', 'name': 'Create', 'rows': [
        {'items': [['n', 'S01'], ['e', 'Back to list', ''], ['n', 'S02']]}, {'label': 'From S02', 'items': [['e', 'Save', 'u'], ['n', 'S03']]}]}],
        'offflow': ['S09']}
    d, diff, makes = plan_update(bm, same, OUT)
    assert not diff and not d['rows'] and not d['remove'], (diff, d)
    # issue 30: rows pair by label, then by screens, never by position; a row inserted in the middle shifts nothing
    bm3 = {'_board': '2:1', '_imgs': {}, '_off': None, '_flows': {'WF-01': {'id': '2:2', 'title': 'WF-01 · A', 'titleId': '2:3', 'rows': [
        {'id': '2:10', 'label': '', 'labelId': '', 'items': [n('S01', '2:11'), e('Open', '', '2:12'), n('S02', '2:13')]},
        {'id': '2:20', 'label': 'From S02', 'labelId': '2:21', 'items': [e('Save', '', '2:22'), n('S03', '2:23')]},
        {'id': '2:30', 'label': 'From S03', 'labelId': '2:31', 'items': [e('Back', '', '2:32'), ['chip', 'S01', '2:33']]}]}}}
    rows = lambda *rs: {'flows': [{'id': 'WF-01', 'name': 'A', 'rows': list(rs)}]}
    r1 = {'items': [['n', 'S01'], ['e', 'Open', ''], ['n', 'S02']]}
    r2 = {'label': 'From S02', 'items': [['e', 'Save', ''], ['n', 'S03']]}
    r3 = {'label': 'From S03', 'items': [['e', 'Back', ''], ['chip', 'S01']]}
    mid = {'label': 'From S02, error', 'items': [['e', 'Save', 'u'], ['n', 'S04']]}
    d, diff, makes = plan_update(bm3, rows(r1, mid, r2, r3), OUT)
    assert diff == ['added edge "Save" [u] in WF-01 row 2', 'added screen S04 in WF-01 row 2', 'new row WF-01 row 2 "From S02, error"'] and makes == ['S04'], diff
    assert len(d['rows']) == 1 and d['rows'][0]['row'] == '' and d['rows'][0]['before'] == '2:21' and not d['remove'], d
    assert pair_rows(bm3['_flows']['WF-01']['rows'], [r3, r1, dict(r2, label='From S02, saved')]) == [2, 0, 1]
    assert pair_rows(bm3['_flows']['WF-01']['rows'], [dict(r2, label=''), dict(r1, items=r1['items'] + [['e', 'x', ''], ['n', 'S09']])]) == [1, 0]
    # a row that disappeared is reported (kept, or removed with --prune), never matched to the row that took its place
    d, diff, _ = plan_update(bm3, rows(r1, r3), OUT)
    assert diff == ['row WF-01 row 2 "From S02" not in flows.json: kept on the board (--prune removes it)'] and not d['rows'], diff
    d, diff, _ = plan_update(bm3, rows(r1, r3), OUT, prune=True)
    assert '2:20' in d['remove'] and '2:21' in d['remove'] and 'removed row WF-01 row 2 "From S02"' in diff, (d, diff)
    assert 'screen S03 is in no flow: card moved to the off-flow section (was WF-01 row 2 "From S02")' in diff, diff
    selftest_codegen()
    print('figma_wireflow.py selftest OK')


def selftest_codegen():
    """Generated code: placeholders filled; with node, build -> images -> update -> mapjs run against figma_mock.js."""
    tmp = Path(tempfile.mkdtemp(prefix='wireflow-'))
    try:
        spec, png = tmp / 'spec', tmp / 'png'
        spec.mkdir()
        png.mkdir()
        scr = [{'id': i, 'name': 'Screen ' + i, 'page': 'tasks/index.html', 'hash': '#/', 'viewport': {'width': 1280, 'height': 800},
                'pins': [{'found': True, 'leftPct': 10, 'topPct': 10}]} for i in ('S01', 'S02', 'S03', 'S04')]
        (spec / 'screens.json').write_text(json.dumps(scr))
        for s in scr:
            (png / (s['id'] + '.png')).write_bytes(b'\x89PNG-' + s['id'].encode())
        fl = {'flows': [{'id': 'WF-01', 'name': 'Create', 'rows': [{'items': [['n', 'S01'], ['e', 'Back', ''], ['n', 'S02']]}]}]}
        (tmp / 'flows.json').write_text(json.dumps(fl))
        A = lambda **k: argparse.Namespace(**dict(dict(
            spec=str(spec), flows=str(tmp / 'flows.json'), out=str(tmp / 'out'), pbi='', feature='Tasks', version='1.0.0', title='',
            meta='', page='', page_id='', app='', site='', png=str(png), scale=0.5, width=3200, accent='#2563EB', prune=False,
            map='', screens='', changed=''), **k))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            build(A())
        code = (tmp / 'out' / 'code.js').read_text()
        assert '__' + 'DATA__' not in code and '__LIB__' not in code and '__READ__' not in code and 'function readBoard' in code
        assert (tmp / 'out' / 'images' / 'S01.png').read_bytes() == b'\x89PNG-S01'
        node = shutil.which('node')
        if not node:
            print('SKIP: node not found, generated code not run')
            return
        state = tmp / 'state.json'

        def run(f):
            r = subprocess.run([node, str(HERE / 'figma_mock.js'), str(f), str(state)], capture_output=True, text=True)
            assert r.returncode == 0, r.stderr
            return json.loads(r.stdout)
        r = run(tmp / 'out' / 'code.js')
        m = r['map']
        assert r['imageScreens'] == ['S01', 'S02'] and m['_imgs']['S01'] == r['imageNodeIds'][0], r  # K-B2: map at first build
        assert [x[0] for x in m['_flows']['WF-01']['rows'][0]['items']] == ['n', 'e', 'n'], m
        (tmp / 'map.json').write_text(json.dumps(r))
        # K-B2: images for an in-place update, image frame ids for upload_assets from the map
        with contextlib.redirect_stdout(io.StringIO()):
            images(A(out=str(tmp / 'upd'), map=str(tmp / 'map.json'), screens='S02,S04'))
        pend = json.loads((tmp / 'upd' / 'pending.json').read_text())
        assert pend == {'imageScreens': ['S02'], 'nodeIds': [m['_imgs']['S02']]}, pend
        # issue 31: a new capture of S02 moved its pin and added one, plus a click ring: redraw.js redraws them in place
        scr[1]['pins'] = [{'found': True, 'leftPct': 50, 'topPct': 50}, {'found': True, 'leftPct': 80, 'topPct': 20}]
        scr[1]['exits'] = [{'found': True, 'leftPct': 90, 'topPct': 90}]
        (spec / 'screens.json').write_text(json.dumps(scr))
        with contextlib.redirect_stdout(io.StringIO()):
            images(A(out=str(tmp / 'upd'), map=str(tmp / 'map.json'), screens='S02'))
        red = run(tmp / 'upd' / 'redraw.js')
        assert red == {'board': m['_board'], 'frames': {'S02': 1}, 'cleared': 2, 'drawn': 3, 'missing': []}, red
        doc = json.loads(state.read_text())
        def find(nd, i):
            return nd if nd['id'] == i else next((x for c in nd.get('children') or [] for x in [find(c, i)] if x), None)
        kids = [c['name'] for c in find(doc['root'], m['_imgs']['S02'])['children']]
        assert kids == ['Pin 1', 'Pin number 1', 'Pin 2', 'Pin number 2', 'Click ring'], kids
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            redrawjs(argparse.Namespace(map=str(tmp / 'map.json'), screens=str(spec / 'screens.json'), ids='S02,S04', changed='', app='', accent='#2563EB'))
        assert 'not on the board' in buf.getvalue() and '"ids":["S02"]' in buf.getvalue() and 'function drawMarks' in buf.getvalue()
        # K-B3: relabel, new screen after the last card of its row, new row with a chip, new off-flow screen
        fl2 = {'flows': [{'id': 'WF-01', 'name': 'Create', 'rows': [
            {'items': [['n', 'S01'], ['e', 'Close', ''], ['n', 'S02'], ['e', 'Narrow', 'x'], ['n', 'S03']]},
            {'label': 'From S03', 'items': [['e', 'Cancel', 'u'], ['chip', 'S01']]}]}], 'offflow': ['S04']}
        (tmp / 'flows.json').write_text(json.dumps(fl2))
        with contextlib.redirect_stdout(io.StringIO()):
            update(A(out=str(tmp / 'upd'), map=str(tmp / 'map.json')))
        assert (tmp / 'upd' / 'images' / 'S03.png').exists()
        u = run(tmp / 'upd' / 'update.js')
        m2 = u['map']
        assert u['imageScreens'] == ['S03', 'S04'] and m2['S01'] == m['S01'] and m2['_imgs']['S02'] == m['_imgs']['S02'], u
        rows = m2['_flows']['WF-01']['rows']
        assert [x[:2] for x in rows[0]['items']] == [['n', 'S01'], ['e', 'Close'], ['n', 'S02'], ['e', 'Narrow'], ['n', 'S03']], rows
        assert rows[0]['items'][3][2] == 'x' and rows[1]['label'] == 'From S03' and rows[1]['items'][0][2] == 'u', rows
        assert [x[1] for x in m2['_off']['items']] == ['S04'], m2['_off']
        (tmp / 'map.json').write_text(json.dumps(u))
        # issue 30: a row inserted between two rows is drawn there; the rows around it keep their nodes
        fl3 = dict(fl2, flows=[dict(fl2['flows'][0], rows=[fl2['flows'][0]['rows'][0],
                                                           {'label': 'From S02', 'items': [['e', 'Help', ''], ['chip', 'S02']]},
                                                           fl2['flows'][0]['rows'][1]])])
        (tmp / 'flows.json').write_text(json.dumps(fl3))
        with contextlib.redirect_stdout(io.StringIO()):
            update(A(out=str(tmp / 'upd3'), map=str(tmp / 'map.json')))
        u3 = run(tmp / 'upd3' / 'update.js')
        r3 = u3['map']['_flows']['WF-01']['rows']
        assert [r['label'] for r in r3] == ['', 'From S02', 'From S03'] and r3[0]['id'] == rows[0]['id'] and r3[2]['id'] == rows[1]['id'], r3
        (tmp / 'map.json').write_text(json.dumps(u3))
        (tmp / 'flows.json').write_text(json.dumps(fl2))
        with contextlib.redirect_stdout(io.StringIO()):
            update(A(out=str(tmp / 'upd4'), map=str(tmp / 'map.json'), prune=True))
        u = run(tmp / 'upd4' / 'update.js')
        assert [r['label'] for r in u['map']['_flows']['WF-01']['rows']] == ['', 'From S03'], u['map']['_flows']
        (tmp / 'map.json').write_text(json.dumps(u))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            update(A(out=str(tmp / 'upd2'), map=str(tmp / 'map.json')))
        assert 'No change' in buf.getvalue(), buf.getvalue()
        (tmp / 'mapjs.js').write_text(mapjs_code(argparse.Namespace(root=m['_board'])))
        assert run(tmp / 'mapjs.js') == m2, 'mapjs reads the same map as the update return'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    if '--selftest' in sys.argv:
        selftest()
        return
    ap = argparse.ArgumentParser(description='Wireflow board for Figma. Commands: build, images, update, upload, mapjs, retitlejs, redrawjs, setmap.',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p):
        p.add_argument('--spec', required=True, help='folder with screens.json and the screen images')
        p.add_argument('--out', required=True, help='output folder (use the scratchpad)')
        p.add_argument('--png', default='', help='folder of original capture PNGs (<Sxx>.png, deviceScaleFactor 2): sent unchanged')

    def look(p):
        p.add_argument('--app', default='', help='app id from kit.config.json > apps (demo links, meta)')
        p.add_argument('--site', default='', help='https base URL of the demo site (default: kit.config.json > deploy.site)')
        p.add_argument('--scale', type=float, default=0.5, help='image size on the board vs capture (web 1280px: 0.5; mobile 390px: 0.75)')
        p.add_argument('--width', type=int, default=3200, help='board width in px')
        p.add_argument('--accent', default='#2563EB', help='accent colour of buttons, pins and rings (#RRGGBB)')

    b = sub.add_parser('build', help='write code.js, images/ and plan.json for one use_figma call')
    common(b)
    b.add_argument('--flows', required=True, help='flows.json')
    b.add_argument('--pbi', default='', help='work-item code, e.g. "PBI 1234" (page name, meta)')
    b.add_argument('--feature', default='', help='feature name (page name, title, meta)')
    b.add_argument('--version', default='', help='package version for the title, e.g. 1.2.0')
    b.add_argument('--title', default='', help='board title (default from --feature and --version)')
    b.add_argument('--meta', default='', help='line under the title (default: pbi · feature · app · DS version label)')
    b.add_argument('--page', default='', help='page name to create or reuse (default "[<pbi>] <feature>")')
    b.add_argument('--page-id', default='', help='existing page id (node-id of the page in the Figma link); overrides --page')
    look(b)
    im = sub.add_parser('images', help='write images/ (and pending.json with --map) for an in-place update')
    common(im)
    im.add_argument('--screens', default='', help='comma-separated screen ids (default: every screen)')
    im.add_argument('--changed', default='', help="changed.json of handoff's pkg.py capture: its changed and new screens")
    im.add_argument('--map', default='', help='map.json: also write pending.json (image frame ids for upload_assets) and redraw.js')
    im.add_argument('--accent', default='#2563EB', help='accent colour of pins and rings in redraw.js (#RRGGBB), as at the build')
    up = sub.add_parser('update', help='diff the board with flows.json and write update.js (new screens, edges, labels)')
    common(up)
    up.add_argument('--map', required=True, help='map.json (mapjs result, or a build/update return value)')
    up.add_argument('--flows', required=True, help='flows.json of the new version')
    up.add_argument('--prune', action='store_true', help='remove edges, chips, rows and flows no longer in flows.json '
                                                       '(cards of screens in no flow move to the off-flow section)')
    look(up)
    u = sub.add_parser('upload', help='POST images to the upload URLs from upload_assets')
    u.add_argument('--out', required=True)
    u.add_argument('--urls', required=True)
    m = sub.add_parser('mapjs', help='print use_figma code that reads screen cards, image frames and flows of a board')
    m.add_argument('--root', required=True, help='board node id (123:456 or 123-456)')
    rt = sub.add_parser('retitlejs', help='print use_figma code that renames a board in place and syncs repeated images')
    rt.add_argument('--root', required=True)
    rt.add_argument('--title', required=True)
    rd = sub.add_parser('redrawjs', help='print use_figma code that redraws pins and click rings of replaced screen images')
    rd.add_argument('--map', required=True, help='map.json (mapjs result, or a build/update return value)')
    rd.add_argument('--screens', required=True, help='screens.json of the new capture (pins, exits)')
    rd.add_argument('--ids', default='', help='comma-separated screen ids')
    rd.add_argument('--changed', default='', help="changed.json of handoff's pkg.py capture: its changed and new screens")
    rd.add_argument('--app', default='', help='app id from kit.config.json > apps')
    rd.add_argument('--accent', default='#2563EB', help='accent colour of pins and rings (#RRGGBB), as at the build')
    sm = sub.add_parser('setmap', help='write the board map into the package config (pkg.json)')
    sm.add_argument('--config', required=True)
    sm.add_argument('--json', required=True, help='mapjs result or build/update return value')
    sm.add_argument('--file', default='', help='Figma file link')
    a = ap.parse_args()
    {'build': build, 'images': images, 'update': update, 'upload': upload, 'mapjs': mapjs, 'retitlejs': retitlejs,
     'setmap': setmap, 'redrawjs': redrawjs}[a.cmd](a)


if __name__ == '__main__':
    main()
