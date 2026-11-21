#!/usr/bin/env python3
"""Optimise a handoff package folder before zipping: small (target: kit.config.json > handoff.maxZipMB, default 3 MB)
and safe to send by mail (mail filters block executable extensions, also inside a zip).

  python3 -I optimize_package.py "<package folder>" [--target-mb 3] [--max-px 1600] [--quality 78]
                                 [--inline-max-kb 8] [--zip "<output zip>"] [--dry-run]

Steps, in order; each prints its numbers:
1. Inline JS into HTML: every <script src="file.js"> that points into the package becomes a <script> block with the
   file content (load order kept, type kept, defer/async dropped because the code is now in place). A .js file that no
   page loads any more is deleted. A JS file shared by several pages is copied into each page: the size cost is printed.
   An ES module that imports other modules cannot be inlined: build it first (react/vue: vite build, single file).
2. Base64 images (data:image/png|jpeg|gif|bmp|webp): converted to WebP, long side down to --max-px, --quality.
   - Images over --inline-max-kb move to assets/img-<hash>.webp (one file per image, shared by every page), referenced
     by a path relative to the page; small images stay base64 as WebP. Also applies inside <script>.
   - Kept base64 (only converted to WebP) when the image is in a .json file, or in a <script> block that reads pixels
     or compares data: strings (getImageData, toDataURL, toBlob, startsWith('data:')). When such code is in another block
     and images were still moved out, a NOTE is printed: canvas cannot read file:// images, so open over HTTP and have
     QC re-test export features.
   SVG, animated GIF and images where WebP is not at least 10% smaller are skipped.
3. Loose PNG/JPEG/GIF/BMP (except attachments/): converted to WebP when smaller; every mention in HTML/CSS/JSON/MD fixed.
4. Remove files blocked by mail filters: executable or script extensions (.js .mjs .cjs .py .sh .bat .cmd .ps1 .vbs
   .exe .jar .msi .dll .scr .hta .lnk ...), nested archives, source maps, OS junk. A .js file still loaded by a page
   that could not be inlined is kept and reported as ERROR.
5. Report: total before -> after, 10 largest files, estimated zip size against the target.
Only storage of images and location of code change; content, look and behaviour of the prototype do not.
Exit code: 0 target met, 1 over target, 2 .js files still loaded (fix by hand and run again).
"""
import argparse, base64, hashlib, io, os, re, sys, zipfile

BLOCKED = {'.js', '.mjs', '.cjs', '.jse', '.py', '.pyc', '.pyw', '.sh', '.bash', '.zsh', '.bat', '.cmd', '.com', '.ps1',
           '.psm1', '.vb', '.vbs', '.vbe', '.wsf', '.wsh', '.wsc', '.exe', '.msi', '.msp', '.msc', '.dll', '.sys', '.scr',
           '.cpl', '.pif', '.hta', '.jar', '.jnlp', '.lnk', '.reg', '.inf', '.scf', '.chm', '.gadget', '.app', '.dmg',
           '.pkg', '.deb', '.rpm', '.apk', '.iso', '.img', '.vhd', '.vhdx', '.xll', '.appx', '.msix', '.php', '.pl',
           '.rb', '.ts', '.map'}
NESTED = {'.zip', '.rar', '.7z', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.cab'}
JUNK = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}
TEXT = {'.html', '.htm', '.css', '.json', '.md', '.svg', '.txt', '.csv'}
RASTER = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
PIXEL_READ = ('getImageData', 'toDataURL', 'toBlob', "startsWith('data:", 'startsWith("data:', "indexOf('data:")
DATA_RX = re.compile(r'data:image/(png|jpe?g|gif|bmp|webp);base64,([A-Za-z0-9+/=]{200,})')
SCRIPT_SRC_RX = re.compile(r'<script\b([^>]*?)\bsrc\s*=\s*["\']([^"\']+)["\']([^>]*)>\s*</script>', re.I)


def config_target():
    """handoff.maxZipMB from kit.config.json when one is found (cwd or parents), else 3."""
    try:
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
        from kitconf import load
        cfg = load(require=False)
        return float(cfg['handoff'].get('maxZipMB', 3)) if cfg else 3.0
    except Exception:
        return 3.0


def human(n):
    return f'{n / 1e6:.2f} MB' if n >= 1e5 else f'{n / 1e3:.0f} KB'


def size_of(root):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(root) for f in fs)


def files(root):
    for r, _, fs in os.walk(root):
        for f in fs:
            yield os.path.join(r, f)


_CACHE = {}


def to_webp(raw, a):
    """WebP bytes when at least 10% smaller, else None (cached by hash: an image repeated on many pages is encoded once)."""
    k = hashlib.sha1(raw).digest()
    if k not in _CACHE:
        _CACHE[k] = _to_webp(raw, a)
    return _CACHE[k]


def _to_webp(raw, a):
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(raw))
        if getattr(im, 'is_animated', False) and im.n_frames > 1:
            return None
        im.load()
    except Exception:
        return None
    if max(im.size) > a.max_px:
        im = im.copy(); im.thumbnail((a.max_px, a.max_px), Image.LANCZOS)
    alpha = im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info)
    im = im.convert('RGBA' if alpha else 'RGB')
    b = io.BytesIO(); im.save(b, 'WEBP', quality=a.quality, method=4)
    out = b.getvalue()
    return out if len(out) < 0.9 * len(raw) else None


def inline_scripts(root, a, log):
    pages = [p for p in files(root) if p.lower().endswith(('.html', '.htm'))]
    used, dup = {}, 0
    for p in pages:
        s = open(p, encoding='utf-8').read()
        def rep(m):
            nonlocal dup
            src = m.group(2)
            if re.match(r'^(https?:)?//', src) or src.startswith('data:'):
                return m.group(0)
            path = os.path.normpath(os.path.join(os.path.dirname(p), src.split('?')[0].split('#')[0]))
            if not os.path.isfile(path):
                return m.group(0)
            code = open(path, encoding='utf-8').read()
            if re.search(r'type\s*=\s*["\']module', m.group(1) + m.group(3)) and re.search(r'^\s*(import\s|export\s)|\bimport\s*\(', code, re.M):
                return m.group(0)   # module that imports modules: cannot inline, strip_blocked reports an ERROR
            code = code.replace('</script', '<\\/script')
            used.setdefault(path, 0); used[path] += 1
            if used[path] > 1: dup += os.path.getsize(path)
            attrs = re.sub(r'\s+(defer|async)\b', '', m.group(1) + m.group(3)).strip()
            rel = os.path.relpath(path, root).replace(os.sep, '/')
            return '<script%s data-inlined-from="%s">\n%s\n</script>' % ((' ' + attrs) if attrs else '', rel, code)
        t = SCRIPT_SRC_RX.sub(rep, s)
        if t != s and not a.dry_run:
            open(p, 'w', encoding='utf-8').write(t)
    log.append(f'Inline JS into HTML: {len(used)} JS file(s), {sum(used.values())} load(s)' + (f'; copies on several pages add {human(dup)}' if dup else ''))
    return used


def convert_data_uris(root, a, log):
    assets = os.path.join(root, 'assets')
    n_in = n_out = 0; saved = 0; warn = set()
    for p in files(root):
        ext = os.path.splitext(p)[1].lower()
        if ext not in ('.html', '.htm', '.css', '.json') or os.sep + 'attachments' + os.sep in p:
            continue
        s = open(p, encoding='utf-8').read()
        if 'base64,' not in s:
            continue
        # <script> spans (may keep base64) and the rest (images move to files)
        spans = [(m.start(), m.end()) for m in re.finditer(r'<script\b.*?</script>', s, re.S | re.I)] if ext in ('.html', '.htm') else []
        # Images inside <script> also move to files unless that block reads pixels or compares data: strings (canvas fails on file:// images)
        risky_spans = [(x, y) for x, y in spans if any(k in s[x:y] for k in PIXEL_READ)]
        in_script = lambda i: ext == '.json' or any(x <= i < y for x, y in risky_spans)
        page_reads_pixels = bool(risky_spans)
        out, last = [], 0
        for m in DATA_RX.finditer(s):
            raw = base64.b64decode(m.group(2))
            w = to_webp(raw, a)
            data = w or raw
            mime = 'webp' if w else m.group(1)
            if not in_script(m.start()) and len(data) > a.inline_max_kb * 1024 and ext != '.json':
                name = 'img-' + hashlib.sha1(data).hexdigest()[:12] + ('.webp' if w else '.' + m.group(1).replace('jpeg', 'jpg'))
                if not a.dry_run:
                    os.makedirs(assets, exist_ok=True)
                    q = os.path.join(assets, name)
                    if not os.path.exists(q): open(q, 'wb').write(data)
                newtxt = os.path.relpath(os.path.join(assets, name), os.path.dirname(p)).replace(os.sep, '/')
                n_out += 1
                if page_reads_pixels and any(x <= m.start() < y for x, y in spans):
                    warn.add(os.path.relpath(p, root))
            elif w:
                newtxt = 'data:image/webp;base64,' + base64.b64encode(w).decode(); n_in += 1
            else:
                continue
            saved += len(m.group(0)) - len(newtxt)
            out.append(s[last:m.start()]); out.append(newtxt); last = m.end()
        if out:
            out.append(s[last:])
            if not a.dry_run:
                open(p, 'w', encoding='utf-8').write(''.join(out))
    log.append(f'Base64 images: {n_out} moved to assets/*.webp, {n_in} kept base64 as WebP; about {human(max(saved, 0))} saved')
    if warn:
        log.append('NOTE: pages draw images on a canvas (PDF/image export) and their images moved to files; export may fail over file://. '
                   'README must say to open over HTTP, and QC must re-test that feature: ' + ', '.join(sorted(warn)))


def convert_loose_images(root, a, log):
    renames = {}
    for p in files(root):
        ext = os.path.splitext(p)[1].lower()
        if ext not in RASTER or os.sep + 'attachments' + os.sep in p:
            continue
        raw = open(p, 'rb').read()
        w = to_webp(raw, a)
        if not w:
            continue
        q = p[:-len(ext)] + '.webp'
        if os.path.exists(q):
            continue
        renames[p] = q
        if not a.dry_run:
            open(q, 'wb').write(w); os.remove(p)
    if renames:
        for t in files(root):
            if os.path.splitext(t)[1].lower() not in TEXT or a.dry_run:
                continue
            s = open(t, encoding='utf-8', errors='ignore').read(); u = s
            for old, new in renames.items():
                ob, nb = os.path.basename(old), os.path.basename(new)
                u = re.sub(r'(?<![\w.-])' + re.escape(ob) + r'(?![\w-])', nb, u)
            if u != s:
                open(t, 'w', encoding='utf-8').write(u)
    log.append(f'Loose PNG/JPEG converted to WebP: {len(renames)} file(s)')


def strip_blocked(root, a, used, log):
    still = set()
    for p in files(root):
        if p.lower().endswith(('.html', '.htm')):
            for m in SCRIPT_SRC_RX.finditer(open(p, encoding='utf-8').read()):
                still.add(os.path.normpath(os.path.join(os.path.dirname(p), m.group(2).split('?')[0])))
    removed, errors = [], []
    for p in list(files(root)):
        base = os.path.basename(p); ext = os.path.splitext(p)[1].lower()
        if base in JUNK or ext in BLOCKED or ext in NESTED or '__pycache__' in p:
            if ext in ('.js', '.mjs', '.cjs') and os.path.normpath(p) in still:
                errors.append(os.path.relpath(p, root)); continue
            removed.append(os.path.relpath(p, root))
            if not a.dry_run: os.remove(p)
    for r, ds, fs in os.walk(root, topdown=False):
        if not ds and not fs and r != root and not a.dry_run:
            os.rmdir(r)
    log.append(f'Files blocked by mail filters: removed {len(removed)}' + (': ' + ', '.join(removed[:12]) + (' ...' if len(removed) > 12 else '') if removed else ''))
    if errors:
        log.append('ERROR: pages still load these JS files, which could not be inlined (kept; fix by hand): ' + ', '.join(errors))
    return errors


def zip_size(root):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files(root):
            z.write(p, os.path.relpath(p, os.path.dirname(root)))
    return b.tell(), b


def main():
    ap = argparse.ArgumentParser(description='Optimise a handoff package folder before zipping (see the module docstring).',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('root', help='package folder'); ap.add_argument('--target-mb', type=float, default=None,
                    help='zip size target in MB (default kit.config.json > handoff.maxZipMB, else 3)')
    ap.add_argument('--max-px', type=int, default=1600); ap.add_argument('--quality', type=int, default=78)
    ap.add_argument('--inline-max-kb', type=int, default=8); ap.add_argument('--zip', help='write the zip here'); ap.add_argument('--dry-run', action='store_true', help='measure on a copy, change nothing')
    a = ap.parse_args()
    if a.target_mb is None:
        a.target_mb = config_target()
    root = os.path.abspath(a.root.rstrip('/'))
    if not os.path.isdir(root):
        print('ERROR: package folder not found: ' + a.root); sys.exit(1)
    s0 = size_of(root); log = []
    tmp = None
    if a.dry_run:   # run on a copy so the numbers are right and the package folder stays as it is
        import shutil, tempfile
        tmp = tempfile.mkdtemp(); root = os.path.join(tmp, os.path.basename(root))
        shutil.copytree(a.root.rstrip('/'), root); a.dry_run = False; dry = True
    else:
        dry = False
    used = inline_scripts(root, a, log)
    convert_data_uris(root, a, log)
    convert_loose_images(root, a, log)
    errors = strip_blocked(root, a, used, log)
    s1 = size_of(root); zs, buf = zip_size(root)
    print('\n'.join(log))
    print(f'Package folder: {human(s0)} -> {human(s1)}' + (' (dry run on a copy, package folder unchanged)' if dry else ''))
    big = sorted(((os.path.getsize(p), os.path.relpath(p, root)) for p in files(root)), reverse=True)[:10]
    print('Largest files: ' + '; '.join(f'{n} {human(s)}' for s, n in big))
    ok = zs <= a.target_mb * 1e6
    print(f'Estimated zip: {human(zs)} / target {a.target_mb:g} MB -> ' + ('MET' if ok else 'OVER: follow the size-reduction steps of the handoff skill'))
    if a.zip and not dry:
        open(a.zip, 'wb').write(buf.getvalue()); print('Wrote', a.zip)
    if tmp:
        import shutil; shutil.rmtree(tmp)
    sys.exit(2 if errors else (0 if ok else 1))


if __name__ == '__main__':
    main()
