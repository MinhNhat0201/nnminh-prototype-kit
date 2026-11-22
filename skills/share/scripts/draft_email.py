#!/usr/bin/env python3
"""Compose the design handoff email for BA, QC and developers from a handoff package (share skill).

  python3 -I draft_email.py "<package zip | package folder>" --app <app id or name> --feature "<work-item name>" \
      --figma <Figma link> [--demo <demo link>] [--version x.y.z] [--greeting "..."] [--signature "<name>"] \
      [--with-features] [--max-items 12] [--business <json>] [--attach-limit-mb 25] [--package-link <url>] --out <folder>

Writes <out>/email.json: subject, body (plain text), htmlBody, attachment (zip path, sha256, size) or null, sections,
warnings, errors; plus subject.txt, body.txt, body.html for review and source.json (material for the business rewrite).
The script reads only README.md, requirements/changelog.md, requirements/checklist-feature.csv, requirements/flows.json
and spec/index.md from the zip. It does not unzip the whole package, call the network or send mail.

- Subject: kit.config.json > email.subject with {app}, {feature}, {version}, {pbi}.
- Version: --version, else read from README.md, requirements/changelog.md or spec/index.md of the package.
- Demo link: --demo, else kit.config.json > deploy.site + the app path; flows with "url" in flows.json add one link per flow.
  kit.config.json > email.demoLinks = false (or --no-demo): no demo, prototype or flow link in the email at all.
- Long lists keep the first email.maxItems items (default 12; --max-items overrides).
- Feature columns: kit.config.json > handoff.csv.feature when set (roles), else the locale headers.
- Section 3 (key features or changelog) is written for business readers: pass --business <json> (SKILL.md step 2).
  Without it, a draft is built from checklist-feature.csv (out-of-scope rows dropped, grouped by the group column; group
  codes get their name from spec/index.md) and the version's changelog section (grouped by change type Added, Changed,
  Fixed, Removed; technical lines folded into one line, never an Added line), with a NOTE to rewrite it. First release
  (first-release text, or no earlier version in the changelog): "Key features", not "changes".
- pkg.json > status "awaiting-figma" (pkg.json next to the package, or --config) -> ERROR; --allow-draft composes anyway.
- Layout: kit.config.json > email.template (or --template) = a project file with placeholders replaces the default
  layout: .md / .txt -> the plain body (the HTML body is built from it), .html -> the HTML body (the plain body is its
  text). "{language}" in the path is the project language. Placeholders: {greeting} {intro} {figma} {demo} {sections}
  {package} {how_to_open} {feedback} {thanks} {signature} {feature} {version} {app} {pbi} {subject} {attachment}.
  Unknown placeholders stay as written (NOTE). Without a template the default layout is used.
- Checks: Figma link on figma.com; demo link https; no file in the zip that mail filters block (.js ...);
  zip over --attach-limit-mb (mail provider limit, default 25 MB) -> no attachment, the body points to --package-link;
  zip over kit.config.json > handoff.maxZipMB -> NOTE.
Exit code 1 on ERROR. --selftest checks the template helpers (no package needed).
"""
import argparse, csv, hashlib, html, io, json, re, shutil, sys, tempfile, zipfile
from pathlib import Path
from urllib.parse import urlparse

KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, t, csv_header, CSV_ROLES, for_app  # noqa: E402

BLOCKED = ('.js', '.mjs', '.cjs', '.exe', '.bat', '.cmd', '.com', '.msi', '.ps1', '.sh', '.vbs', '.jar', '.scr', '.dll',
           '.apk', '.py', '.hta', '.lnk', '.reg')
VER = re.compile(r'\b(\d+\.\d+\.\d+)\b')
READ = re.compile(r'(README\.md|requirements/(changelog\.md|checklist-feature\.csv|flows\.json)|spec/index\.md)$')


class Safe(dict):
    def __missing__(self, k):
        return '{' + k + '}'


def both(cfg, key):
    """The string in every locale, project language first (to match package content written in any of them)."""
    langs = [cfg.get('language', 'en'), 'en'] + sorted(d.name for d in (KIT / 'locales').iterdir() if d.is_dir())
    return [x for x in dict.fromkeys(t(lg, key) for lg in langs) if x and x != key]


def pkg_status(src, config=''):
    """(status, screens awaiting Figma, pkg.json path) from the package config of `handoff` (pkg.json > status):
    --config, else pkg.json next to the package or one folder up (zip in <item>/out/, pkg.json in <item>/)."""
    p = Path(src).resolve()
    cands = [Path(config)] if config else [d / 'pkg.json' for d in (p.parent, p.parent.parent)]
    for c in cands:
        if c.is_file():
            try:
                pc = json.loads(c.read_text(encoding='utf-8'))
            except ValueError:
                return '', [], c
            return pc.get('status', ''), pc.get('awaiting_figma') or [], c
    return '', [], None


def read_pkg(src):
    """(package root, zip path or None, file names, temp folder or None)."""
    p = Path(src)
    if p.is_file() and p.suffix.lower() == '.zip':
        tmp = Path(tempfile.mkdtemp(prefix='handoff-'))
        with zipfile.ZipFile(p) as z:
            names = z.namelist()
            for n in names:  # only the text files we read; never the whole package
                if READ.search(n) and '..' not in n and not n.startswith('/'):
                    z.extract(n, tmp)
        roots = [d for d in tmp.iterdir() if d.is_dir()]
        return (roots[0] if len(roots) == 1 else tmp), p, names, tmp
    if p.is_dir():
        return p, None, [str(f.relative_to(p)) for f in p.rglob('*') if f.is_file()], None
    print(f'ERROR: package not found: {src}')
    sys.exit(1)


def text(path):
    return path.read_text(encoding='utf-8-sig') if path.exists() else ''


def find_version(root, given):
    if given:
        return given
    for f in (root / 'README.md', root / 'requirements' / 'changelog.md', root / 'spec' / 'index.md'):
        m = VER.search(text(f))
        if m:
            return m.group(1)
    return ''


KINDS = ('added', 'changed', 'fixed', 'removed')  # order of the groups in the email


def kind_words(cfg):
    """[(word, kind)] longest first, from share.words<Kind> in every locale ("sửa lỗi" before "sửa")."""
    ws = [(w.strip().lower(), k) for k in KINDS for x in both(cfg, 'share.words' + k.title()) for w in x.split('|') if w.strip()]
    return sorted(dict.fromkeys(ws), key=lambda x: -len(x[0]))


def change_kind(words, s):
    """(kind or None, text without a leading "Added:" label). Kind from the first word(s) of a line or a heading."""
    s0 = re.sub(r'^\*\*([^*]+)\*\*', r'\1', s.strip()).strip()
    low = s0.lower()
    for w, k in words:
        if low.startswith(w) and (len(low) == len(w) or not low[len(w)].isalnum()):
            rest = s0[len(w):]
            m = re.match(r'\s*\**\s*[:：–—-]\s*(.*)', rest)
            return k, ((m.group(1)[:1].upper() + m.group(1)[1:]) if m and m.group(1) else s0)
    return None, s0


def changelog_items(cfg, root, version):
    """([{'text', 'kind'}], first release?). Kind comes from a sub-heading (### Added) or the line's first words.
    First release: the locale first-release text is in the section, or the changelog has no earlier version."""
    s = text(root / 'requirements' / 'changelog.md')
    if not s:
        return [], False
    older = [w.lower().lstrip('# ').strip() for w in both(cfg, 'handoff.changelog.older')]
    head = lambda x: x.split('\n', 1)[0].lower().lstrip('# ').strip()
    # sections start at a version heading or the "earlier versions" heading; "### Added" stays inside its version
    secs = [x for x in re.split(r'\n(?=#{2,3}\s)', '\n' + s) if re.match(r'#{2,3}\s', x)]
    merged = []
    for x in secs:
        if merged and not VER.search(x.split('\n', 1)[0]) and head(x) not in older:
            merged[-1] += '\n' + x
        else:
            merged.append(x)
    secs = merged
    vsecs = [x for x in secs if VER.search(x.split('\n', 1)[0])]
    sec = next((x for x in vsecs if version and version in x.split('\n', 1)[0]), None) or (vsecs[0] if vsecs else secs[0] if secs else s)
    earlier = [x for x in vsecs if x is not sec] + [x for x in secs if head(x) in older]
    firsts = [w.lower() for w in both(cfg, 'handoff.changelog.first')]
    first = any(w in sec.lower() for w in firsts) or (bool(vsecs) and not earlier)
    words, items, cur = kind_words(cfg), [], None
    for line in sec.splitlines()[1:]:
        m = re.match(r'\s*[-*]\s+(.*)', line)
        if m and m.group(1).strip():
            k, txt = change_kind(words, m.group(1))
            txt = re.sub(r'\*\*([^*]+)\*\*', r'\1', txt)
            if not any(txt.lower().strip(' .') == w for w in firsts):  # the first-release line itself is not an item
                items.append({'text': txt, 'kind': k or cur})
        elif line.strip():  # sub-heading, bold line or "Added:" line sets the kind of the lines below it
            cur = change_kind(words, re.sub(r'^#+\s*', '', line.strip()).rstrip(':： '))[0]
    return items, first


def change_groups(changes, tech, T, first=False):
    """Changelog lines grouped by change type (Added, Changed, Fixed, Removed, then lines with no type). Technical
    lines fold into one "UI refinements" line at the end, never an Added line (a new feature must stay visible).
    First release: one list without type names."""
    by, n_tech = {}, 0
    for c in changes:
        if tech.search(c['text']) and c['kind'] != 'added':
            n_tech += 1
            continue
        by.setdefault(None if first else c['kind'], []).append(c['text'])
    groups = [{'name': T('kind' + k.title()) if k else '', 'items': by[k]} for k in KINDS + (None,) if by.get(k)]
    if n_tech:
        if groups and not groups[-1]['name']:
            groups[-1]['items'].append(T('uiTuning', n=n_tech))
        else:
            groups.append({'name': '', 'items': [T('uiTuning', n=n_tech)]})
    return groups


def spec_names(root, rows=()):
    """Code -> name, from spec/index.md (table rows "| GC-01 | Notes |" and headings "## GC-01 · Notes") and from
    checklist rows whose code is used as a group code elsewhere. Turns group codes into the names BA uses."""
    names = {}
    code = r'[A-Za-z]{1,6}[-_]?\d+[A-Za-z]?'
    for line in text(root / 'spec' / 'index.md').splitlines():
        m = re.match(r'\s*\|\s*\[?(%s)\]?(?:\([^)]*\))?\s*\|\s*([^|]+?)\s*\|' % code, line) or \
            re.match(r'#{1,4}\s+(%s)\s*[·:—–-]\s*(.+?)\s*$' % code, line)
        if m and not re.fullmatch(r'-+', m.group(2)):
            names.setdefault(m.group(1), m.group(2))
    for c, n in rows:
        if c and n:
            names.setdefault(c, n)
    return names


def feature_items(cfg, root):
    """Rows of checklist-feature.csv except out-of-scope ones: code, name, group, screen, status.
    Columns are matched by the headers in locales/<lang>/handoff.json > handoff.csv.feature (project language + English)."""
    s = text(root / 'requirements' / 'checklist-feature.csv')
    rows = list(csv.reader(io.StringIO(s))) if s else []
    if not rows:
        return []
    head = [h.strip().lower() for h in rows[0]]
    std = [[c.strip().lower() for c in h.split(',')] for h in both(cfg, 'handoff.csv.feature')]
    hdr, roles = csv_header(cfg, 'feature')   # kit.config.json > handoff.csv.feature (names and roles), or the locale
    declared = {r: n.strip().lower() for r, n in zip(roles, hdr.split(',')) if r}

    def col(i):  # i = position in the standard header list
        role = CSV_ROLES['feature'][i]
        names = {h[i] for h in std if i < len(h)} | ({declared[role]} if role in declared else set())
        return next((j for j, h in enumerate(head) if h in names), None)
    ci, cn, cg, cm, cs = col(0), col(1), col(2), col(3), col(7)
    if cn is None:
        cn = 1 if len(head) > 1 else 0
    out_words = [w.lower() for w in both(cfg, 'share.outOfScope')]
    full_words = [w.lower() for w in both(cfg, 'share.statusFull')]
    g = lambda r, i: r[i].strip() if i is not None and i < len(r) else ''
    groups = {g(r, cg) for r in rows[1:]}
    names = spec_names(root, [(g(r, ci), g(r, cn)) for r in rows[1:] if g(r, ci) in groups])
    out = []
    for r in rows[1:]:
        if not g(r, cn) or any(w in ' '.join(r).lower() for w in out_words):
            continue
        st = g(r, cs)
        gr = g(r, cg)
        out.append({'code': g(r, ci), 'name': g(r, cn), 'group': names.get(gr, gr), 'groupCode': gr if gr in names else '',
                    'screen': g(r, cm), 'status': '' if st.lower() in full_words else st})
    return out


def tech_rx(cfg):
    """Technical lines (tokens, CSS, files, DS version...) that business readers do not need."""
    ds = cfg.get('_ds') or {}
    words = [re.escape(ds.get('tokens', {}).get('prefix', '--ds-'))]
    for k in ('label', 'name'):
        if ds.get(k):
            words.append(r'\b' + re.escape(ds[k]) + r'\b')
    words += [r'\btoken\b', r'\bcss\b', r'\bclass\b', '`', r'\.js\b', r'\.html\b', r'\bpx\b', r'#[0-9a-f]{3,6}\b',
              'refactor', r'\bcomponent', r'\bvariant', 'radius', 'spacing', 'font size', r'\bstyle\b', 'intentional deviation']
    for w in both(cfg, 'share.techWords'):
        words += [x for x in w.split('|') if x]
    return re.compile('(' + '|'.join(words) + ')', re.I)


def flow_links(root):
    s = text(root / 'requirements' / 'flows.json')
    if not s:
        return [], ''
    try:
        d = json.loads(s)
    except ValueError:
        return [], ''
    fl = d.get('flows', []) if isinstance(d, dict) else d
    home = d.get('home', '') if isinstance(d, dict) else ''
    return [(f.get('id', ''), f.get('name', ''), f['url'], f.get('start', '')) for f in fl if f.get('url')], home


def fill(tpl, vals, missing):
    """Replace {name} placeholders (only word names, so CSS braces and other text stay); unknown names stay as written."""
    def rep(m):
        if m.group(1) in vals:
            return str(vals[m.group(1)])
        missing.append(m.group(1))
        return m.group(0)
    return re.sub(r'\{([a-z_]+)\}', rep, tpl)


def sections_text(secs, T):
    L = []
    for sec, (groups, more) in secs:
        L += ([''] if L else []) + [sec['title'] + ':']
        for g in groups:
            if g['name']:
                L.append('  ' + g['name'])
            L += [('    - ' if g['name'] else '  - ') + x for x in g['items']]
        if more:
            L.append('  - ' + T('more', n=more) + (' (' + T('seeFile', file=sec['more']) + ')' if sec['more'] else ''))
    return '\n'.join(L)


def sections_html(secs, T):
    E = lambda s: html.escape(s, quote=True)
    out = []
    for sec, (groups, more) in secs:
        h = f'<p><b>{E(sec["title"])}:</b></p>'
        for g in groups:
            h += (f'<p style="margin:8px 0 0"><b>{E(g["name"])}</b></p>' if g['name'] else '')
            h += '<ul>' + ''.join(f'<li>{E(x)}</li>' for x in g['items']) + '</ul>'
        if more:
            h += '<p>' + E(T('more', n=more)) + (' (' + E(T('seeFile', file=sec['more'])) + ')' if sec['more'] else '') + '</p>'
        out.append(h)
    return '\n'.join(out)


def text_to_html(text, labels=None):
    """Plain body -> simple mail HTML: paragraphs, "- " lists, **bold**, links for http(s) URLs. labels = {url: link
    text} (the Figma and demo links read "Open Figma" in the project language instead of the raw URL)."""
    lab = {html.escape(k, quote=True): v for k, v in (labels or {}).items() if k and v}

    def inline(s):
        s = html.escape(s, quote=True)
        s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
        return re.sub(r'(https?://[^\s<]+)', lambda m: '<a href="%s">%s</a>' % (m.group(1), html.escape(lab[m.group(1)]) if m.group(1) in lab
                                                                              else m.group(1)), s)
    out, para, items = [], [], []
    def flush():
        if para:
            out.append('<p>' + '<br>'.join(inline(x) for x in para) + '</p>')
            para.clear()
        if items:
            out.append('<ul>' + ''.join(f'<li>{inline(x)}</li>' for x in items) + '</ul>')
            items.clear()
    for ln in text.splitlines():
        m = re.match(r'\s*[-*]\s+(.*)', ln)
        if not ln.strip():
            flush()
        elif m:
            if para:
                out.append('<p>' + '<br>'.join(inline(x) for x in para) + '</p>')
                para.clear()
            items.append(m.group(1))
        else:
            if items:
                flush()
            para.append(ln.strip())
    flush()
    return '\n'.join(out)


def html_to_text(h):
    s = re.sub(r'(?i)<br\s*/?>|</p>|</li>|</h\d>|</tr>', '\n', h)
    s = re.sub(r'(?i)<li[^>]*>', '- ', s)
    s = re.sub(r'(?i)<a\s[^>]*href="([^"]*)"[^>]*>(.*?)</a>', lambda m: m.group(2) + (' (' + m.group(1) + ')' if m.group(1) != m.group(2) else ''), s)
    s = html.unescape(re.sub(r'<[^>]+>', '', s))
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(x.rstrip() for x in s.splitlines())).strip() + '\n'


def from_template(cfg, tpl_path, warn, err, vals, secs, T):
    """(plain body, HTML body) from the project's email template (email.template)."""
    p = Path(cfg['_root']) / tpl_path.replace('{language}', cfg.get('language', 'en'))
    if not p.is_file():
        err.append(f'email template not found: {p}')
        return '', ''
    tpl = p.read_text(encoding='utf-8')
    if p.suffix.lower() in ('.html', '.htm'):
        E = lambda s: html.escape(str(s), quote=True)
        hv = {k: E(v) for k, v in vals.items()}
        for k in ('figma', 'demo'):
            if vals[k].startswith('http'):
                hv[k] = f'<a href="{E(vals[k])}">{E(vals[k])}</a>'
        hv['sections'] = sections_html(secs, T)
        missing = []
        htmlbody = fill(tpl, hv, missing)
        body = html_to_text(htmlbody)
    else:
        missing = []
        body = fill(tpl, dict(vals, sections=sections_text(secs, T)), missing).strip() + '\n'
        htmlbody = text_to_html(body, {vals['figma']: T('openFigma'), vals['demo']: T('openDemo')})
    if missing:
        warn.append('email template has unknown placeholders, left as written: ' + ', '.join('{%s}' % m for m in dict.fromkeys(missing)))
    return body, htmlbody


def selftest():
    miss = []
    assert fill('Hi {greeting} <style>p{margin:0}</style> {nope}', {'greeting': 'team'}, miss) == \
        'Hi team <style>p{margin:0}</style> {nope}' and miss == ['nope'], miss
    h = text_to_html('Hello,\n\nFigma: https://www.figma.com/x\n- one\n- **two**\nBye')
    assert '<a href="https://www.figma.com/x">' in h and '<li><b>two</b></li>' in h and h.endswith('<p>Bye</p>'), h
    h = text_to_html('Figma: https://www.figma.com/x?a=1&b=2', {'https://www.figma.com/x?a=1&b=2': 'Open Figma'})
    assert '<a href="https://www.figma.com/x?a=1&amp;b=2">Open Figma</a>' in h, h
    assert html_to_text('<p>Hi</p><ul><li>a</li></ul><p><a href="https://x.y/">open</a></p>') == 'Hi\n- a\nopen (https://x.y/)\n'
    T = lambda k, **kw: k + (str(kw.get('n', '')) if kw else '')
    sec = {'title': 'Changes', 'groups': [{'name': '', 'items': ['a']}], 'more': 'requirements/changelog.md'}
    assert sections_text([(sec, (sec['groups'], 2))], T) == 'Changes:\n  - a\n  - more2 (seeFile)', sections_text([(sec, (sec['groups'], 2))], T)
    # K-F17 / K-B10: change types, first release, group names
    cfg = {'language': 'vi'}
    W = kind_words(cfg)
    assert change_kind(W, 'Added: two-pane layout on wide screens') == ('added', 'Two-pane layout on wide screens')
    assert change_kind(W, 'Sửa lỗi: lưu ghi chú trống')[0] == 'fixed' and change_kind(W, 'Sửa nhãn nút')[0] == 'fixed'
    assert change_kind(W, 'Đổi tên nút Lưu')[0] == 'changed' and change_kind(W, 'Newsletter link')[0] is None
    tmp = Path(tempfile.mkdtemp(prefix='share-'))
    try:
        (tmp / 'requirements').mkdir()
        (tmp / 'spec').mkdir()
        cl = tmp / 'requirements' / 'changelog.md'
        cl.write_text('# Changelog\n\n## 1.0.0 · 2026-11-21\n- Notes list and editor\n', encoding='utf-8')
        items, first = changelog_items(cfg, tmp, '1.0.0')
        assert first and items == [{'text': 'Notes list and editor', 'kind': None}], (first, items)  # no earlier version
        cl.write_text('# Changelog\n\n## 1.1.0 · 2026-11-22\n### Added\n- Two panes at `notes/index.html#/` (S03d)\n'
                      '- Changed: close button says "Close note"\n### UI style changes\n- `--acme-space-2` gap on cards\n\n'
                      '## 1.0.0 · 2026-11-21\n- Phát hành đầu\n', encoding='utf-8')
        items, first = changelog_items(cfg, tmp, '1.1.0')
        assert not first and [c['kind'] for c in items] == ['added', 'changed', None], items
        Tn = lambda k, **kw: {'kindAdded': 'Added', 'kindChanged': 'Changed'}.get(k, k) + (str(kw['n']) if 'n' in kw else '')
        gs = change_groups(items, tech_rx({'language': 'en', '_ds': {'tokens': {'prefix': '--acme-'}}}), Tn)
        assert gs == [{'name': 'Added', 'items': ['Two panes at `notes/index.html#/` (S03d)']},
                      {'name': 'Changed', 'items': ['Close button says "Close note"']}, {'name': '', 'items': ['uiTuning1']}], gs
        (tmp / 'spec' / 'index.md').write_text('| Unit | Name | Status |\n|---|---|---|\n| [GC-01](GC-01.md) | Notes | Active |\n'
                                               '## GC-02 · Reminders\n', encoding='utf-8')
        # K-B5: a package awaiting Figma is found through pkg.json next to the zip folder
        (tmp / 'out').mkdir()
        (tmp / 'pkg.json').write_text(json.dumps({'status': 'awaiting-figma', 'awaiting_figma': ['S03d']}))
        st = pkg_status(tmp / 'out' / 'Design - 1234.zip')
        assert st[:2] == ('awaiting-figma', ['S03d']) and pkg_status(tmp / 'none.zip', str(tmp / 'nope.json'))[0] == '', st
        assert spec_names(tmp, [('GC-03', 'Sharing')]) == {'GC-01': 'Notes', 'GC-02': 'Reminders', 'GC-03': 'Sharing'}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('draft_email.py selftest OK')


def main():
    if '--selftest' in sys.argv:
        selftest()
        return
    ap = argparse.ArgumentParser(description='Compose the handoff email (draft material only; never sends).',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('src', help='package zip or folder')
    ap.add_argument('--app', required=True, help='app id from kit.config.json > apps, or the app name')
    ap.add_argument('--feature', required=True, help='work-item name as the user says it, e.g. "[1234] Scheduled tasks"')
    ap.add_argument('--pbi', default='', help='work-item code (for {pbi} in email.subject)')
    ap.add_argument('--figma', default='', help='Figma handoff page or board link')
    ap.add_argument('--demo', default='', help='demo link (default: deploy.site + app path, or flows.json > home)')
    ap.add_argument('--version', default='')
    ap.add_argument('--greeting', default='')
    ap.add_argument('--signature', default='')
    ap.add_argument('--with-features', action='store_true', help='list key features as well as the changelog')
    ap.add_argument('--max-items', type=int, default=None, help='items kept per section (default: email.maxItems, else 12)')
    ap.add_argument('--no-demo', action='store_true', help='no demo or flow links (as email.demoLinks = false)')
    ap.add_argument('--business', default='', help='JSON of section 3 rewritten for business readers (SKILL.md step 2)')
    ap.add_argument('--attach-limit-mb', type=float, default=None, help='attachment limit in MB (default: kit.config.json > email.attachLimitMB, else 3)')
    ap.add_argument('--package-link', default='', help='download link used when the zip is too big to attach')
    ap.add_argument('--demo-needs-login', action='store_true', help='add a line that the demo site needs an account')
    ap.add_argument('--template', default='', help='email layout file (default: kit.config.json > email.template)')
    ap.add_argument('--config', default='', help="handoff package config (pkg.json; default: found next to the package)")
    ap.add_argument('--allow-draft', action='store_true', help='compose from a package still awaiting Figma (never send it)')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    cfg = load()
    aid = next((x['id'] for x in cfg['apps'] if a.app in (x.get('id'), x.get('name'))), None)
    cfg = for_app(cfg, aid)  # the app's own DS profile (apps[].ds): technical words of its DS
    if a.attach_limit_mb is None:
        a.attach_limit_mb = float((cfg.get('email') or {}).get('attachLimitMB') or 3)
    if a.max_items is None:
        a.max_items = int((cfg.get('email') or {}).get('maxItems') or 12)
    demo_links = not a.no_demo and (cfg.get('email') or {}).get('demoLinks', True) is not False
    T = lambda k, **kw: t(cfg, 'share.' + k, **kw)
    app_name, app_path = a.app, ''
    for x in cfg['apps']:
        if x.get('id') == a.app or x.get('name') == a.app:
            app_name, app_path = x.get('name') or x['id'], x.get('path', '')
    root, zpath, names, tmp = read_pkg(a.src)
    warn, err = [], []
    status, waiting, pcfg = pkg_status(a.src, a.config)
    if status == 'awaiting-figma':
        msg = (f'the package is a draft awaiting Figma ({pcfg}: status awaiting-figma'
               + (f'; screens {", ".join(waiting[:12])}' if waiting else '') + '). Run wireflow (update the board, setmap), '
               'then `pkg.py relink --pkg <package> --config pkg.json --zip`, and compose the email from the new zip.')
        (warn if a.allow_draft else err).append(msg + (' --allow-draft: composed anyway; do not send it.' if a.allow_draft else ''))
    version = find_version(root, a.version)
    flows, home = flow_links(root)
    demo = a.demo or home or ((cfg['deploy'].get('site') or '').rstrip('/') + '/' + app_path.strip('/') + '/'
                              if cfg['deploy'].get('site') and app_path else '')
    if not demo_links:
        flows, demo = [], ''
    if not version:
        err.append('no version found in the package: pass --version x.y.z')
    if a.figma and urlparse(a.figma).netloc not in ('figma.com', 'www.figma.com'):
        err.append(f'Figma link is not on figma.com: {a.figma}')
    if demo and urlparse(demo).scheme != 'https':
        err.append(f'demo link must be https: {demo}')
    if not a.figma:
        warn.append('no Figma link: the email says "not available yet"; ask the user before creating the draft.')
    if not demo_links:
        if a.demo:
            warn.append('email.demoLinks is false (or --no-demo): --demo is ignored, the email has no demo link')
    elif not demo:
        warn.append('no demo link: the email says "not available yet"; ask the user before creating the draft.')
    elif not a.demo:
        warn.append(f'no --demo given; using {demo} (from flows.json > home or deploy.site): confirm with the user')
    blocked = [n for n in names if n.lower().endswith(BLOCKED)]
    if blocked:
        err.append('the package still has files that mail filters block: ' + ', '.join(blocked[:5])
                   + ' (run the size and blocked-file step of the handoff skill)')
    att, dropped = None, False
    if zpath:
        size = zpath.stat().st_size
        mb = size / 1048576
        if mb > a.attach_limit_mb:
            dropped = True
            warn.append(f'zip is {mb:.1f} MB, over the {a.attach_limit_mb:g} MB attachment limit: the draft has no attachment. '
                        'Tell the user; share the zip by link (--package-link) instead. Never split or rename it.')
            if not a.package_link:
                warn.append('no --package-link: the email says the link will follow; ask the user for a download link.')
        else:
            if mb > float(cfg['handoff'].get('maxZipMB', 3)):
                warn.append(f'zip is {mb:.1f} MB, over handoff.maxZipMB ({cfg["handoff"].get("maxZipMB", 3)} MB).')
            att = {'path': str(zpath.resolve()), 'filename': zpath.name, 'bytes': size,
                   'sha256': hashlib.sha256(zpath.read_bytes()).hexdigest(), 'mimeType': 'application/zip'}
            warn.append('some mail connectors refuse an attachment on a draft without recipients: add To before creating the '
                        'draft, or tell the user to attach the zip by hand (never base64 it yourself).')
    else:
        warn.append('source is a folder, there is no zip to attach: zip it with the handoff skill and run again.')

    changes, first = changelog_items(cfg, root, version)
    feats = feature_items(cfg, root)
    tech = tech_rx(cfg)
    subject = cfg['email']['subject'].format_map(Safe(app=app_name, feature=a.feature, version=version, pbi=a.pbi))

    # sections: [{"title": ..., "groups": [{"name": group or "", "items": [sentences]}], "more": file in the package}]
    sections, auto = [], not a.business
    if a.business:
        try:
            nv = json.load(open(a.business, encoding='utf-8'))
        except (OSError, ValueError) as e:
            print(f'ERROR: cannot read --business: {e}')
            sys.exit(1)
        for sec in (nv if isinstance(nv, list) else [nv]):
            if first and sec.get('title') in both(cfg, 'share.changelog'):
                warn.append(f'version {version} is the first release: title "{sec["title"]}" speaks of changes; use "{T("keyFeatures")}"')
            sections.append({'title': sec.get('title') or (T('keyFeatures') if first else T('changelog')),
                             'groups': [{'name': g.get('name', ''), 'items': [m for m in g.get('items', []) if m]}
                                        for g in sec.get('groups', [])],
                             'more': sec.get('more', '')})
        for sec in sections:
            for g in sec['groups']:
                for m in g['items']:
                    if tech.search(m):
                        warn.append(f'item still has technical terms, rewrite it for business readers: "{m}"')
    else:
        if (first or a.with_features or not changes) and feats:
            groups = {}
            for f in feats:
                groups.setdefault(f['group'], []).append(f['name'] + (f' ({f["status"]})' if f['status'] else ''))
            sections.append({'title': T('keyFeatures'), 'groups': [{'name': k, 'items': v} for k, v in groups.items()],
                             'more': 'requirements/checklist-feature.csv'})
            coded = sorted({f['group'] for f in feats if re.fullmatch(r'[A-Za-z]{1,6}[-_]?\d+[A-Za-z]?', f['group'] or '')})
            if coded:
                warn.append('feature groups are codes without a name in spec/index.md: ' + ', '.join(coded)
                            + ' (name them in the --business rewrite)')
        if changes and (not first or not feats):  # first release without a feature list: its lines are the key features
            sections.append({'title': T('keyFeatures') if first else T('changelog'),
                             'groups': change_groups(changes, tech, T, first), 'more': 'requirements/changelog.md'})
        if sections:
            warn.append('section 3 is copied from the package: rewrite it for business readers into a JSON file and run again '
                        'with --business (SKILL.md step 2). Material is in source.json.')
    if not feats and not changes and not sections:
        warn.append('the package has no checklist-feature.csv or changelog.md: no feature section; ask the user.')

    def cut(sec):
        """Keep at most --max-items items for the whole section; the rest points to the file in the package."""
        left, out_g, more = a.max_items, [], 0
        for g in sec['groups']:
            keep = g['items'][:max(0, left)]
            more += len(g['items']) - len(keep)
            left -= len(keep)
            if keep:
                out_g.append({'name': g['name'], 'items': keep})
        return out_g, more

    na = T('notYet')
    greeting = a.greeting or T('greeting')
    if att:
        pkg_line, pkg_html = T('attached', file=att['filename']), T('attached', file=html.escape(att['filename']))
    elif dropped:
        link = a.package_link or T('linkFollows')
        pkg_line = T('byLink', file=zpath.name, link=link)
        pkg_html = T('byLink', file=html.escape(zpath.name), link=(f'<a href="{html.escape(a.package_link)}">{html.escape(a.package_link)}</a>'
                                                                   if a.package_link else html.escape(link)))
    else:
        pkg_line = pkg_html = T('noZip')

    # plain text
    L = [greeting, '', T('intro', feature=a.feature, version=version, app=app_name), '']
    L += ['1. ' + T('figma') + ': ' + (a.figma or na)]
    if demo_links:
        L.append('2. ' + T('demo') + ': ' + (demo or na))
    for fid, fname, url, start in flows:
        L.append(f'   - {fid} {fname}: {url}' + (' (' + T('start', start=start) + ')' if start else ''))
    n = 3 if demo_links else 2
    for sec in sections:
        groups, more = cut(sec)
        L += ['', f'{n}. {sec["title"]}:']
        for g in groups:
            if g['name']:
                L.append(f'   {g["name"]}')
            L += [('     - ' if g['name'] else '   - ') + x for x in g['items']]
        if more:
            L.append('   - ' + T('more', n=more) + (' (' + T('seeFile', file=sec['more']) + ')' if sec['more'] else ''))
        n += 1
    L += ['', f'{n}. {T("package")}: {pkg_line}', '   ' + T('howToOpen')]
    if a.demo_needs_login and demo_links:
        L += ['', T('demoLogin')]
    L += ['', T('feedback'), '', T('thanks')] + ([a.signature] if a.signature else [])
    body = '\n'.join(L)

    # HTML (simple, safe for mail readers)
    E = lambda s: html.escape(s, quote=True)
    A = lambda u, label=None: f'<a href="{E(u)}">{E(label or u)}</a>'
    H = [f'<p>{E(greeting)}</p>', '<p>' + E(T('intro', feature=a.feature, version=version, app=app_name)) + '</p>', '<ol>']
    H.append(f'<li><b>{E(T("figma"))}:</b> ' + (A(a.figma, T('openFigma')) if a.figma else E(na)) + '</li>')
    if demo_links:
        d = f'<li><b>{E(T("demo"))}:</b> ' + (A(demo, T('openDemo')) if demo else E(na))
        if flows:
            d += '<ul>' + ''.join(f'<li>{E(fid)} {E(fname)}: {A(url, T("openFlow"))}'
                                  + (' (' + E(T('start', start=start)) + ')' if start else '') + '</li>'
                                  for fid, fname, url, start in flows) + '</ul>'
        H.append(d + '</li>')
    for sec in sections:
        groups, more = cut(sec)
        li = f'<li><b>{E(sec["title"])}:</b>'
        for g in groups:
            li += (f'<p style="margin:8px 0 0"><b>{E(g["name"])}</b></p>' if g['name'] else '')
            li += '<ul>' + ''.join(f'<li>{E(x)}</li>' for x in g['items']) + '</ul>'
        if more:
            li += '<p style="margin:4px 0 0">' + E(T('more', n=more)) + (' (' + E(T('seeFile', file=sec['more'])) + ')' if sec['more'] else '') + '</p>'
        H.append(li + '</li>')
    H.append(f'<li><b>{E(T("package"))}:</b> {pkg_html}<br>{E(T("howToOpen"))}</li></ol>')
    if a.demo_needs_login and demo_links:
        H.append(f'<p>{E(T("demoLogin"))}</p>')
    H.append(f'<p>{E(T("feedback"))}</p>')
    H.append(f'<p>{E(T("thanks"))}' + (f'<br>{E(a.signature)}' if a.signature else '') + '</p>')
    htmlbody = '\n'.join(H)
    tpl_path = a.template or (cfg.get('email') or {}).get('template') or ''
    if tpl_path:
        body, htmlbody = from_template(cfg, tpl_path, warn, err, {
            'greeting': greeting, 'intro': T('intro', feature=a.feature, version=version, app=app_name), 'figma': a.figma or na,
            'demo': (demo or na) if demo_links else '', 'package': pkg_line, 'how_to_open': T('howToOpen'), 'feedback': T('feedback'),
            'thanks': T('thanks'), 'signature': a.signature, 'feature': a.feature, 'version': version, 'app': app_name,
            'pbi': a.pbi, 'subject': subject, 'attachment': att['filename'] if att else ''},
            [(sec, cut(sec)) for sec in sections], T)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = {'subject': subject, 'body': body, 'htmlBody': htmlbody, 'attachment': att, 'attachmentDropped': dropped,
           'version': version, 'demo': demo, 'sections': sections, 'businessRewritten': not auto, 'firstRelease': first,
           'flowLinks': len(flows), 'demoLinks': demo_links, 'template': tpl_path or None, 'warnings': warn, 'errors': err}
    (out / 'email.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'subject.txt').write_text(subject, encoding='utf-8')
    (out / 'body.txt').write_text(body, encoding='utf-8')
    (out / 'body.html').write_text(htmlbody, encoding='utf-8')
    (out / 'source.json').write_text(json.dumps({'firstRelease': first, 'version': version, 'features': feats, 'changes': changes,
                                                 'flows': [{'id': i, 'name': nm} for i, nm, _, _ in flows]},
                                                ensure_ascii=False, indent=1), encoding='utf-8')
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    print('Subject: ' + subject)
    print(f'Features: {len(feats)} · changes: {len(changes)} · section 3: {"business rewrite" if not auto else "copied from package"}'
          f' · flow links: {len(flows)} · attachment: '
          + (f'{att["filename"]} ({att["bytes"] / 1048576:.2f} MB)' if att else ('dropped (too big)' if dropped else 'none')))
    for w in warn:
        print('NOTE ' + w)
    for e in err:
        print('ERROR: ' + e)
    print(f'Wrote {out / "email.json"}')
    sys.exit(1 if err else 0)


if __name__ == '__main__':
    main()
