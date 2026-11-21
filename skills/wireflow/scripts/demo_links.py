#!/usr/bin/env python3
"""Demo-site links per wireflow flow (shared by the flows text of a spec and by the Figma wireflow board).

  python3 -I demo_links.py fill --screens <screens.json> --flows <flows.json> --app <app id>
                                [--site <https base URL>] [--manifest <manifest.json>] [--page-root <folder>] [--dry-run]
  python3 -I demo_links.py --selftest

- Flow link = site + page path + hash route of the first screen of the flow (first `n` item), from screens.json
  (the capture output). A flow that already has `url` keeps it (hand-edited).
- Writes `url` into each flow and `home` (the app root) into flows.json, and prints flow id · screen · link · start.
- With --manifest: when the first screen needs clicks to reach (`steps`) and the flow has no `start`, prints a
  REMINDER so the agent fills `start` with the exact on-screen label (for example: Click "New").
- Page path of a screen: when it contains the app path (`apps[].path`), the part after it is kept; when it is a
  relative path inside the app (captured from a copy of the app, for example a package prototype served from its own
  folder), it is kept as it is, with its page folder. --page-root <folder> removes that leading folder first (for
  example `prototype` when the package folder was served). Absolute paths outside the app keep only the file name.
- --site defaults to kit.config.json > deploy.site. --app is an app id from kit.config.json > apps (its `path` is used).
The script makes no network call.
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))


def app_url(site, app_path):
    return site.rstrip('/') + '/' + app_path.strip('/') + '/'


def screen_url(site, app_path, page, hash_, page_root=''):
    """Turn the page path at capture time (local server, file:// or a copy in a package) into a path on the site."""
    base = app_url(site, app_path)
    p = (page or '').replace('\\', '/')
    absolute = '://' in p or p.startswith('/')
    p = urlparse(p).path if '://' in p else p
    p = p.lstrip('/')
    app_path, root = app_path.strip('/'), page_root.strip('/')
    if app_path and (app_path + '/') in (p + '/'):
        rel = (p + '/').split(app_path + '/', 1)[1].rstrip('/')   # part after the app folder
    elif root and ('/' + root + '/') in ('/' + p):
        rel = ('/' + p).split('/' + root + '/', 1)[1]              # part after the served copy's root folder
    elif not absolute:
        rel = p                                                    # relative path inside the app: keep the page folder
    else:
        rel = p.rsplit('/', 1)[-1] if p.endswith('.html') else ''  # copy outside the repo: keep the file name only
    if rel.endswith('index.html'):
        rel = rel[:-len('index.html')]
    h = (hash_ or '').strip()
    if h and not h.startswith('#'):
        h = '#' + h
    return base + rel + h


def first_screen(flow):
    for r in flow.get('rows', []):
        for it in r.get('items', []):
            if it[0] == 'n':
                return it[1]
    return None


def check_url(u, site):
    s, p = urlparse(site), urlparse(u)
    return p.scheme == 'https' and p.netloc == s.netloc


def resolve_site_app(site, app_id):
    """Return (site, app path) from the arguments, falling back to kit.config.json."""
    from kitconf import load, app
    cfg = load(require=False)
    if not site and cfg:
        site = (cfg.get('deploy') or {}).get('site') or ''
    path = ''
    if app_id:
        if cfg is None:
            sys.exit('ERROR: --app needs kit.config.json (run the kickoff skill first).')
        path = app(cfg, app_id)['path']
    return site, path


def read_json(p):
    try:
        return json.load(open(p, encoding='utf-8'))
    except FileNotFoundError:
        sys.exit(f'ERROR: file not found: {p}')
    except json.JSONDecodeError as e:
        sys.exit(f'ERROR: {p} is not valid JSON: {e}')


def load_screens(p):
    s = read_json(p)
    return {x['id']: x for x in (s if isinstance(s, list) else s.get('screens', []))}


def fill(a):
    site, app_path = resolve_site_app(a.site, a.app)
    if not site:
        sys.exit('ERROR: no demo site. Pass --site or set kit.config.json > deploy.site.')
    if urlparse(site).scheme != 'https':
        sys.exit('ERROR: the demo site must be an https URL.')
    by = load_screens(a.screens)
    flows = read_json(a.flows)
    steps = {}
    if a.manifest:
        man = read_json(a.manifest)
        steps = {s['id']: s.get('steps') or [] for s in man.get('screens', [])}
    flows['home'] = app_url(site, app_path)
    rows, warn, err = [], [], []
    for f in flows.get('flows', []):
        sid = first_screen(f)
        if not f.get('url'):
            if not sid or sid not in by:
                err.append(f'{f.get("id")}: first screen of the flow is not in screens.json')
                continue
            f['url'] = screen_url(site, app_path, by[sid].get('page'), by[sid].get('hash'), a.page_root)
        if not check_url(f['url'], site):
            err.append(f'{f.get("id")}: link {f["url"]} is not on site {site}')
        if sid and steps.get(sid) and not f.get('start'):
            warn.append(f'{f.get("id")}: first screen {sid} needs {len(steps[sid])} step(s) to reach; add "start" to the flow')
        rows.append((f.get('id'), sid, f['url'], f.get('start', '')))
    for r in rows:
        print(' · '.join(x for x in (r[0], r[1] or '', r[2], ('start: ' + r[3]) if r[3] else '') if x))
    for w in warn:
        print('REMINDER: ' + w)
    for e in err:
        print('ERROR: ' + e)
    if err:
        sys.exit(1)
    if not a.dry_run:
        json.dump(flows, open(a.flows, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'Wrote url for {len(rows)} flow(s) and home to {a.flows}')


def selftest():
    S, A = 'https://demo.example.com', 'apps/acme-web'
    cases = [
        (('apps/acme-web/tasks/index.html', '#/list'), '', S + '/apps/acme-web/tasks/#/list'),
        (('tasks/index.html', '#/list'), '', S + '/apps/acme-web/tasks/#/list'),
        (('index.html', '#/'), '', S + '/apps/acme-web/#/'),
        (('prototype/tasks/index.html', '/x'), 'prototype', S + '/apps/acme-web/tasks/#/x'),
        (('file:///home/u/pkg/prototype/tasks/index.html', ''), 'prototype', S + '/apps/acme-web/tasks/'),
        (('file:///tmp/copy/page.html', ''), '', S + '/apps/acme-web/page.html'),
    ]
    for (page, h), root, want in cases:
        got = screen_url(S, A, page, h, root)
        assert got == want, (page, root, got, want)
    print('demo_links.py selftest OK')


def main():
    if '--selftest' in sys.argv:
        selftest()
        return
    ap = argparse.ArgumentParser(description='Demo-site links per wireflow flow. Commands: fill.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('fill', help='write url per flow and home into flows.json')
    f.add_argument('--screens', required=True, help='screens.json from the capture step')
    f.add_argument('--flows', required=True, help='flows.json to update in place')
    f.add_argument('--app', required=True, help='app id from kit.config.json > apps')
    f.add_argument('--site', default='', help='https base URL of the demo site (default: kit.config.json > deploy.site)')
    f.add_argument('--manifest', help='capture manifest with per-screen steps')
    f.add_argument('--page-root', default='', help='leading folder of the captured page paths to drop (e.g. prototype)')
    f.add_argument('--dry-run', action='store_true', help='print, do not write')
    a = ap.parse_args()
    fill(a)


if __name__ == '__main__':
    main()
