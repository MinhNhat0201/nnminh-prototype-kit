#!/usr/bin/env python3
"""DS Figma libraries and the mockup audit for the `mockup` skill.

Commands:
  libs   [--platform web]
         Print the Figma libraries, collections and modes from ds.json > figma (for the given platform).
         Exit 1 when ds.json > figma.libraries is empty: run `adopt` or link a library first.
  render --page-id <id> --specs-id <id> [--wireflow-id <id>] [--platform web] [--out audit.js]
         Fill assets/spec-audit.js with a config object (node ids, library and collection names from ds.json,
         exempt prefix in the project language) and write or print the code to send verbatim to use_figma.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
from kitconf import load, t  # noqa: E402

TEMPLATE = HERE.parent / 'assets' / 'spec-audit.js'
IMG_SUFFIX = ' · image'  # default; the wireflow suffixes (figma.imageSuffix, locale, English) are all accepted
ICON_PREFIXES = ['Icon', 'Logo']


def fail(msg):
    print('ERROR: ' + msg)
    sys.exit(1)


def figma_conf(cfg, platform):
    ds = cfg.get('_ds')
    if not ds:
        fail(f'ds.json not found for kit.config.json > ds ({cfg.get("ds")}). Run the kickoff skill.')
    fg = ds.get('figma') or {}
    libs = fg.get('libraries') or []
    if not libs:
        fail('ds.json > figma.libraries is empty. The mockup needs DS components and variables in Figma: '
             'run the adopt skill (it pushes variables and styles to Figma), or publish the DS library in Figma '
             'and add it to ds.json > figma.libraries.')
    if platform:
        match = [l for l in libs if (l.get('platform') or 'web') == platform]
        if not match:
            fail(f'no library for platform "{platform}" in ds.json > figma.libraries '
                 f'(found: {", ".join(sorted({l.get("platform") or "web" for l in libs}))})')
        libs = match
    return libs, fg.get('collections') or {}, fg.get('modes') or {}


def collection_names(libs, cols):
    """Allowed collection names: a library's own `collections` (mobile and web libraries often name them
    differently) win over ds.json > figma.collections. Empty list = collection names are not checked."""
    names = []
    for lib in libs:
        own = lib.get('collections')
        src = own if own is not None else cols
        vals = src.values() if isinstance(src, dict) else src
        names += [v for v in vals if v and v not in names]
    return names


def selftest():
    web = {'name': 'W', 'platform': 'web', 'collections': {'semantic': 'Themes', 'spacing': 'Space'}}
    mob = {'name': 'M', 'platform': 'mobile', 'collections': ['Color Mode']}
    plain = {'name': 'P'}
    top = {'semantic': 'Semantic', 'spacing': ''}
    assert collection_names([web], top) == ['Themes', 'Space']
    assert collection_names([mob], top) == ['Color Mode']
    assert collection_names([plain], top) == ['Semantic']
    assert collection_names([web, plain], top) == ['Themes', 'Space', 'Semantic']
    assert collection_names([plain], {}) == []
    print('selftest OK')


def cmd_libs(a):
    cfg = load()
    libs, cols, modes = figma_conf(cfg, a.platform)
    print(json.dumps({'libraries': libs, 'collections': cols, 'modes': modes}, ensure_ascii=False, indent=1))


def cmd_render(a):
    cfg = load()
    libs, cols, _ = figma_conf(cfg, a.platform)
    conf = {
        'pageId': a.page_id.replace('-', ':'), 'specsId': a.specs_id.replace('-', ':'),
        'wireflowId': (a.wireflow_id or '').replace('-', ':'),
        'libraries': [l['name'] for l in libs if l.get('name')],
        'collections': collection_names(libs, cols),
        'imageSuffix': list(dict.fromkeys([((cfg.get('figma') or {}).get('imageSuffix')) or IMG_SUFFIX,
                                           t(cfg, 'wireflow.imageSuffix'), IMG_SUFFIX])),
        'exemptPrefix': t(cfg, 'mockup.exemptPrefix'),
        'iconPrefixes': ICON_PREFIXES,
        'issueMax': 30,
    }
    tpl = TEMPLATE.read_text(encoding='utf-8')
    body = '\n'.join(l for l in tpl.splitlines() if not l.startswith('//'))
    code = body.replace('__CONFIG__', json.dumps(conf, ensure_ascii=False))
    if a.out:
        Path(a.out).write_text(code, encoding='utf-8')
        print(f'Wrote {a.out} ({len(code.encode("utf-8"))} bytes) · libraries: {", ".join(conf["libraries"])} · '
              f'exempt prefix: {conf["exemptPrefix"]}')
    else:
        print(code)


def main():
    ap = argparse.ArgumentParser(description='DS Figma libraries and mockup audit. Commands: libs, render.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    lb = sub.add_parser('libs', help='print libraries, collections and modes from ds.json > figma')
    lb.add_argument('--platform', default='', help='web, mobile, tablet (default: all)')
    r = sub.add_parser('render', help='write the audit code for use_figma')
    r.add_argument('--page-id', required=True, help='page id of the work item')
    r.add_argument('--specs-id', required=True, help='node id of the Specs board')
    r.add_argument('--wireflow-id', default='', help='node id of the Wireflow board (parity check)')
    r.add_argument('--platform', default='', help='only the libraries of this platform')
    r.add_argument('--out', default='', help='file to write (default: print)')
    if sys.argv[1:] == ['--selftest']:
        return selftest()
    a = ap.parse_args()
    {'libs': cmd_libs, 'render': cmd_render}[a.cmd](a)


if __name__ == '__main__':
    main()
