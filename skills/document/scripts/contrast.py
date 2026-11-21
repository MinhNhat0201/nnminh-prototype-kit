#!/usr/bin/env python3
"""Contrast check of DS colour tokens (WCAG 2 ratio), resolved from the DS CSS bundle. Read-only.

Foreground and background are tokens, token prefixes (every token that starts with it) or hex values.
Tokens resolve on plain :root rules; --mode <value> also applies the rules of the mode attribute from
ds.json > theming.mode (for example :root[data-mode="dark"]) on top.

Usage:
  python3 contrast.py --fg --acme-text- --bg --acme-bg-white --bg --acme-bg-page
  python3 contrast.py --fg --acme-stroke-input --bg --acme-bg-white --min 3
  python3 contrast.py --fg --acme-text- --bg --acme-bg-white --mode dark
  python3 contrast.py --fg "#767676" --bg "#ffffff"
  python3 contrast.py ... --css other.css     read another CSS file instead of the bundle

Thresholds: body text 4.5, large text 3, control borders and icons 3 (pass --min).
Exit code 1 on error; a failing pair is reported, not an error.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from kitconf import load, ds_path  # noqa: E402

HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})")
RGB = re.compile(r"rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)(?:[\s,/]+([\d.]+%?))?\s*\)")
VAR = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^)]*))?\)")
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def fail(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def parse_color(v):
    v = (v or "").strip()
    m = HEX.fullmatch(v)
    if m:
        h = v[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)), (int(h[6:8], 16) / 255 if len(h) == 8 else 1.0)
    m = RGB.fullmatch(v)
    if m:
        a = m.group(4)
        alpha = 1.0 if not a else float(a.rstrip("%")) / (100 if a.endswith("%") else 1)
        return (int(m.group(1)), int(m.group(2)), int(m.group(3))), alpha
    return None


def lum(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = map(f, rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def blend(fg, alpha, bg):
    return tuple(round(f * alpha + b * (1 - alpha)) for f, b in zip(fg, bg))


def token_defs(css, mode_sel):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
    defs = {}
    for want in [":root"] + ([mode_sel] if mode_sel else []):
        for m in RULE.finditer(css):
            sels = [re.sub(r"\s+", " ", s.strip()) for s in m.group(1).split(",")]
            if want in sels:
                for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", m.group(2)):
                    defs[k] = v.strip()
    return defs


def resolve(defs, k, depth=0):
    v = defs.get(k)
    if v is None or depth > 12:
        return None
    m = VAR.fullmatch(v)
    if m:
        return resolve(defs, m.group(1), depth + 1) or (m.group(2) or "").strip() or None
    return v


def expand(items, defs):
    out = []
    for x in items:
        if x.startswith("--") and x not in defs:
            out += sorted(k for k in defs if k.startswith(x))
        else:
            out.append(x)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fg", action="append", required=True, help="foreground token, token prefix or hex (repeatable)")
    ap.add_argument("--bg", action="append", required=True, help="background token or hex (repeatable)")
    ap.add_argument("--min", type=float, default=4.5, help="minimum ratio (default 4.5)")
    ap.add_argument("--mode", help="mode value from ds.json > theming.mode, e.g. dark")
    ap.add_argument("--css", help="CSS file to read (default: ds.json > css.bundle)")
    argv, i = [], 0
    raw = sys.argv[1:]
    while i < len(raw):  # token names start with "--": glue them to their option so argparse keeps them as values
        if raw[i] in ("--fg", "--bg") and i + 1 < len(raw):
            argv.append("%s=%s" % (raw[i], raw[i + 1]))
            i += 2
        else:
            argv.append(raw[i])
            i += 1
    a = ap.parse_args(argv)
    mode_sel = None
    if a.css:
        css_file = a.css
    else:
        cfg = load()
        if not cfg["_ds"]:
            fail("no DS profile: kit.config.json > ds must point at a folder with ds.json.")
        css_file = ds_path(cfg, cfg["_ds"]["css"]["bundle"])
        if a.mode:
            attr = ((cfg["_ds"].get("theming") or {}).get("mode") or {}).get("attr")
            if not attr:
                fail("ds.json > theming.mode.attr is not set: cannot select a mode.")
            mode_sel = ':root[%s="%s"]' % (attr, a.mode)
    if a.mode and a.css:
        mode_sel = ':root[data-mode="%s"]' % a.mode
    if not css_file or "://" in css_file or not Path(css_file).is_file():
        fail("CSS not found or is a URL: %s" % css_file)
    defs = token_defs(Path(css_file).read_text(encoding="utf-8"), mode_sel)
    fgs, bgs = expand(a.fg, defs), expand(a.bg, defs)
    if not fgs:
        fail("no foreground token matches %s" % ", ".join(a.fg))
    print("| Foreground | Background | Ratio | Min | Result |\n|---|---|---|---|---|")
    bad = 0
    for b in bgs:
        bc = parse_color(resolve(defs, b) if b.startswith("--") else b)
        if not bc:
            print("| — | `%s` | — | — | unresolved |" % b)
            continue
        for f in fgs:
            fc = parse_color(resolve(defs, f) if f.startswith("--") else f)
            if not fc:
                print("| `%s` | `%s` | — | — | unresolved |" % (f, b))
                continue
            rgb = blend(fc[0], fc[1], bc[0]) if fc[1] < 1 else fc[0]
            r = ratio(rgb, bc[0])
            ok = r >= a.min
            bad += not ok
            print("| `%s` | `%s` | %.2f | %g | %s |" % (f, b, r, a.min, "pass" if ok else "FAIL"))
    print("\n%d pair(s) below %g%s." % (bad, a.min, " (mode %s)" % a.mode if a.mode else ""))


if __name__ == "__main__":
    main()
