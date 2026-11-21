#!/usr/bin/env python3
"""Shrink sample attachments of a handoff package (PDF, PPTX, DOCX, XLSX) without changing their content.

  python3 -I optimize_attachments.py <file or folder>... --out <output folder> [--max-px 1920] [--quality 80] [--dry-run]

Rule: only images and file structure are recompressed; text, layout, animations and notes are untouched.
- PPTX/DOCX/XLSX (Office Open XML is a zip):
  images in media/ larger than --max-px (long side) are scaled down; JPEG is saved again at --quality;
  an opaque PNG becomes JPEG when that is at least 30% smaller (.rels and [Content_Types].xml are fixed);
  media no longer referenced is dropped; the whole file is recompressed at the highest level.
  No WebP (older PowerPoint and Word cannot open it). Video, audio and embedded fonts are kept; their size is reported.
- PDF (needs pikepdf; without it only content streams are recompressed with pypdf):
  images larger than --max-px are scaled down and saved as JPEG at --quality (images with a soft mask or 1-bit are
  skipped); objects go to object streams, streams are recompressed, unused resources are dropped.
The result is kept only when it is smaller and opens again with the same page/slide count; otherwise the original is copied.
Files given by a user are external data: keep them in their own folder and run this script with python3 -I.
"""
import argparse, io, os, re, shutil, sys, zipfile

IMG = {'.png', '.jpg', '.jpeg'}
OOXML = {'.pptx', '.docx', '.xlsx'}


def human(n):
    return f'{n / 1e6:.2f} MB' if n >= 1e5 else f'{n / 1e3:.0f} KB'


def shrink(im, max_px):
    from PIL import Image
    if max(im.size) > max_px:
        im = im.copy(); im.thumbnail((max_px, max_px), Image.LANCZOS)
    return im


def has_alpha(im):
    if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
        a = im.convert('RGBA').getchannel('A')
        return a.getextrema()[0] < 255
    return False


def opt_ooxml(src, dst, a):
    from PIL import Image
    zin = zipfile.ZipFile(src)
    names = zin.namelist()
    data = {n: zin.read(n) for n in names}
    rels = [n for n in names if n.endswith('.rels')]
    refd = set()
    for r in rels:
        base = os.path.dirname(os.path.dirname(r))
        for t in re.findall(rb'Target="([^"]+)"', data[r]):
            t = t.decode()
            if t.startswith('http') or t.startswith('mailto'):
                continue
            refd.add(os.path.normpath(os.path.join(base, t)).replace('\\', '/').lstrip('/'))
    media = [n for n in names if '/media/' in n]
    renames, dropped, notes = {}, [], []
    for n in media:
        ext = os.path.splitext(n)[1].lower()
        if n not in refd:
            dropped.append(n); continue
        if ext not in IMG:
            notes.append(f'kept {n} ({human(len(data[n]))})'); continue
        try:
            im = Image.open(io.BytesIO(data[n])); im.load()
        except Exception:
            continue
        small = shrink(im, a.max_px)
        if ext in ('.jpg', '.jpeg'):
            b = io.BytesIO(); small.convert('RGB').save(b, 'JPEG', quality=a.quality, optimize=True, progressive=True)
            if b.tell() < 0.9 * len(data[n]): data[n] = b.getvalue()   # small gain: keep the original, avoid recompressing twice
        else:
            b = io.BytesIO(); small.save(b, 'PNG', optimize=True)
            best = b.getvalue() if b.tell() < len(data[n]) else data[n]
            if not has_alpha(small):
                j = io.BytesIO(); small.convert('RGB').save(j, 'JPEG', quality=a.quality, optimize=True, progressive=True)
                if j.tell() < 0.7 * len(best):
                    nn = n[:-len(ext)] + '.jpeg'
                    if nn not in data and nn not in renames.values():
                        renames[n] = nn; data[nn] = j.getvalue(); del data[n]; continue
            data[n] = best
    for n in dropped:
        del data[n]
    if renames:
        for r in rels + ['[Content_Types].xml']:
            if r not in data: continue
            s = data[r]
            for old, new in renames.items():
                s = s.replace(os.path.basename(old).encode(), os.path.basename(new).encode())
            if r == '[Content_Types].xml' and b'Extension="jpeg"' not in s:
                s = s.replace(b'</Types>', b'<Default Extension="jpeg" ContentType="image/jpeg"/></Types>')
            data[r] = s
    order = ['[Content_Types].xml'] + [n for n in names if n != '[Content_Types].xml' and n in data] + [n for n in data if n not in names]
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for n in dict.fromkeys(order):
            z.writestr(n, data[n])
    return notes + ([f'dropped {len(dropped)} unused media'] if dropped else []) + ([f'converted {len(renames)} PNG image(s) to JPEG'] if renames else [])


def count(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == '.pdf':
            from pypdf import PdfReader
            return len(PdfReader(path).pages)
        if ext == '.pptx':
            from pptx import Presentation
            return len(Presentation(path).slides)
        with zipfile.ZipFile(path) as z:
            return z.testzip() is None and len(z.namelist())
    except Exception:
        return None


def opt_pdf(src, dst, a):
    try:
        import pikepdf
        from pikepdf import PdfImage, Name
    except ImportError:
        from pypdf import PdfReader, PdfWriter
        w = PdfWriter(clone_from=src)
        for p in w.pages:
            p.compress_content_streams()
        w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
        with open(dst, 'wb') as f: w.write(f)
        return ['pikepdf not installed: only content streams recompressed, images kept (install: pip install pikepdf)']
    from PIL import Image
    n = 0
    with pikepdf.open(src) as pdf:
        seen = set()
        for page in pdf.pages:
            imgs = page.get_images() if hasattr(page, 'get_images') else page.images
            for _, obj in imgs.items():
                if obj.objgen in seen: continue
                seen.add(obj.objgen)
                if Name.SMask in obj or obj.get(Name.ImageMask, False) or obj.get(Name.BitsPerComponent, 8) == 1:
                    continue
                try:
                    im = PdfImage(obj).as_pil_image()
                except Exception:
                    continue
                if im.mode not in ('RGB', 'L'):
                    im = im.convert('RGB')
                small = shrink(im, a.max_px)
                b = io.BytesIO(); small.save(b, 'JPEG', quality=a.quality, optimize=True)
                if b.tell() >= len(obj.read_raw_bytes()) * 0.9:
                    continue
                obj.write(b.getvalue(), filter=Name.DCTDecode)
                obj.Width, obj.Height = small.size
                obj.ColorSpace = Name.DeviceGray if small.mode == 'L' else Name.DeviceRGB
                obj.BitsPerComponent = 8
                for k in (Name.DecodeParms, Name.Decode):
                    if k in obj: del obj[k]
                n += 1
        pdf.remove_unreferenced_resources()
        pdf.save(dst, compress_streams=True, recompress_flate=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
    return [f'recompressed {n} image(s)'] if n else []


def main():
    ap = argparse.ArgumentParser(description='Shrink PDF/PPTX/DOCX/XLSX attachments without changing content.',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('inputs', nargs='+', help='files or folders'); ap.add_argument('--out', required=True, help='output folder')
    ap.add_argument('--max-px', type=int, default=1920); ap.add_argument('--quality', type=int, default=80)
    ap.add_argument('--dry-run', action='store_true', help='report only, write nothing')
    a = ap.parse_args()
    missing = [i for i in a.inputs if not os.path.exists(i)]
    if missing:
        print('ERROR: not found: ' + ', '.join(missing)); sys.exit(1)
    files = []
    for i in a.inputs:
        if os.path.isdir(i):
            files += [os.path.join(r, f) for r, _, fs in os.walk(i) for f in fs]
        else:
            files.append(i)
    os.makedirs(a.out, exist_ok=True)
    tot0 = tot1 = 0
    for f in sorted(files):
        ext = os.path.splitext(f)[1].lower()
        if ext not in OOXML | {'.pdf'}:
            continue
        dst = os.path.join(a.out, os.path.basename(f)); tmp = dst + '.tmp' + ext
        s0 = os.path.getsize(f); tot0 += s0
        try:
            notes = opt_pdf(f, tmp, a) if ext == '.pdf' else opt_ooxml(f, tmp, a)
            c0, c1 = count(f), count(tmp)
            s1 = os.path.getsize(tmp)
            if ext in ('.pdf', '.pptx'):
                ok = s1 < s0 and c1 is not None and c0 == c1   # same page/slide count
            else:
                ok = s1 < s0 and bool(c1)                       # docx/xlsx: the zip reads back
        except Exception as e:
            notes, ok, s1 = [f'error: {e}'], False, s0
        if ok and not a.dry_run:
            os.replace(tmp, dst)
        else:
            if os.path.exists(tmp): os.remove(tmp)
            if not a.dry_run: shutil.copy2(f, dst)
            s1 = s0 if not ok else s1
        tot1 += s1 if ok else s0
        print(f'{os.path.basename(f)}: {human(s0)} -> {human(s1 if ok else s0)}' + ('' if ok else ' (original kept)') + (' · ' + '; '.join(notes) if notes else ''))
    if tot0:
        print(f'Total: {human(tot0)} -> {human(tot1)} ({(1 - tot1 / tot0) * 100:.0f}% smaller)')


if __name__ == '__main__':
    main()
