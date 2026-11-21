#!/usr/bin/env python3
"""Propose a mapping from hard-coded values in an app to existing DS tokens (proposal only: changes nothing).

Reads the app region (same split as audit_app.py: CSS outside the DS markers, style="" attributes, style={{...}}
objects, :style bindings, Tailwind arbitrary values) and matches colours, font sizes, radii, line heights and spacing
against the resolved value of each token in the default configuration of the DS bundle (plain :root, light mode).
The token role comes from ds.json > tokens.roles, the spacing scale from ds.json > tokens.scale.spacing.

Confidence:
  Exact     one semantic token of the matching role has the same value: replacing changes nothing visible
  By role   several semantic tokens share the value: pick by the meaning of the place
  Near      only a close token (colour deltaE <= 4, size <= 1px): visible change, check Figma first
  None      no matching token: check Figma, never invent a token

Usage:
  python3 audit_map_tokens.py [app ...] [--csv out.csv] [--limit N]
Only CSS values are proposed; DOM, classes, text and behaviour never change.
"""
import argparse
import collections
import csv
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_app as A  # noqa: E402

HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")
RGBF = re.compile(r"rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)(?:[\s,/]+([\d.]+%?))?\s*\)")
PX = re.compile(r"(?<![\w.-])(-?\d+(?:\.\d+)?)px\b")
VAR = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^)]*))?\)")
CONF = ("exact", "role", "near", "none")


def roles(ctx):
    """Role prefixes from ds.json > tokens.roles; missing roles fall back to <prefix><role>-."""
    r = dict(ctx.ds["tokens"].get("roles") or {})
    p = ctx.prefix
    dflt = {"text": "text-", "bg": "bg-", "stroke": "stroke-", "icon": "icon-", "radius": "radius-", "fontSize": "font-size-",
            "lineHeight": "line-height-", "spacing": "space-"}
    for k, v in dflt.items():
        r.setdefault(k, p + v)
    return r


def prop_rules(ctx):
    R = roles(ctx)
    scale = (ctx.ds["tokens"].get("scale") or {}).get("spacing")
    color = [
        (re.compile(r"^(color|caret-color|text-decoration-color)$"), (R["text"], R["icon"])),
        (re.compile(r"^(background|background-color)$"), (R["bg"],)),
        (re.compile(r"^(border|border-[a-z-]*color|border-(top|right|bottom|left)|outline|outline-color|column-rule-color)$"), (R["stroke"],)),
        (re.compile(r"^(fill|stroke)$"), (R["icon"], R["bg"])),
    ]
    length = [
        (re.compile(r"^font-size$"), (R["fontSize"],), "font-size"),
        (re.compile(r"^border(-[a-z]+)*-radius$"), (R["radius"],), "radius"),
        (re.compile(r"^line-height$"), (R["lineHeight"],), "line-height"),
        (re.compile(r"^(margin|padding|gap|row-gap|column-gap)(-[a-z]+)?$"), tuple(x for x in (R["spacing"], scale) if x), "spacing"),
    ]
    return color, length, scale


def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), (int(h[6:8], 16) / 255 if len(h) == 8 else 1.0)


def lab(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = map(f, rgb[:3])
    x, y, z = (r * .4124 + g * .3576 + b * .1805) / .95047, r * .2126 + g * .7152 + b * .0722, (r * .0193 + g * .1192 + b * .9505) / 1.08883
    g_ = lambda v: v ** (1 / 3) if v > 0.008856 else 7.787 * v + 16 / 116
    return 116 * g_(y) - 16, 500 * (g_(x) - g_(y)), 200 * (g_(y) - g_(z))


def de(a, b):
    return math.dist(lab(a), lab(b))


def default_tokens(ctx):
    """Resolved value of every DS token in the default configuration (rules whose selector is exactly :root)."""
    css = A.strip(A.read(ctx.bundle_path))
    css = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)  # media blocks are not the default configuration
    defs = {}
    for m in A.RULE.finditer(css):
        if A.norm(m.group(1)) == ":root":
            for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", m.group(2)):
                defs[k] = v.strip()
    cache = {}

    def res(k, depth=0):
        if k in cache:
            return cache[k]
        v = defs.get(k)
        if v is None or depth > 12:
            return None
        m = VAR.fullmatch(v)
        out = res(m.group(1), depth + 1) if m else v
        cache[k] = out
        return out
    return {k: res(k) for k in defs if k.startswith(ctx.prefix)}


def build_index(tok):
    col, ln = collections.defaultdict(list), collections.defaultdict(list)
    for k, v in tok.items():
        if not v:
            continue
        if HEX.fullmatch(v):
            col[hex_rgb(v)[:3]].append(k)
        else:
            m = re.fullmatch(r"(-?\d+(?:\.\d+)?)px", v)
            if m:
                ln[float(m.group(1))].append(k)
    return col, ln


def occurrences(ctx, app, lib):
    """(file, line, selector or origin, property, value) for every declaration in the app region."""
    out, seen = [], set()
    for f in A.app_files(ctx, app):
        txt = A.read(f)
        rel = str(f.relative_to(ctx.root))
        for base, _, body in A.css_blocks(ctx, f, txt):
            if body in seen:
                continue  # shared block copied into several files: report it once, at its first location
            seen.add(body)
            body = A.AT_STMT.sub(A.blank, A.COMMENT.sub(A.blank, body))
            for r in A.RULE.finditer(body):
                if (A.norm(r.group(1)), A.norm(r.group(2))) in lib["rules"]:
                    continue
                for d in re.finditer(r"([\w-]+)\s*:\s*([^;]+)", r.group(2)):
                    line = base + body[:r.start(2) + d.start()].count("\n")
                    out.append((rel, line, A.norm(r.group(1))[:60], d.group(1).lower(), d.group(2).strip()))
        for line, origin, decls in A.inline_decls(ctx, f, txt):
            for d in re.finditer(r"([\w-]+)\s*:\s*([^;]+)", decls):
                out.append((rel, line, origin[:60], d.group(1).lower(), d.group(2).strip()))
    return out


def suggest(ctx, rules, prop, val, col, ln):
    """[(original value, confidence key, proposed token, note)]."""
    tr = ctx.tr
    color, length, scale = rules
    sem = {p for _, ps in color for p in ps}
    res = []
    if prop.startswith("--"):
        return res  # token definitions are reported by audit_app.py under "redefined"
    if "var(" in val and not re.search(r",\s*(#|rgb)", val):
        return res
    pre = next((p for pat, p in color if pat.match(prop)), None)
    if pre:
        for h in HEX.findall(val) + [m.group(0) for m in RGBF.finditer(val)]:
            mm = RGBF.fullmatch(h)
            rgba = (int(mm.group(1)), int(mm.group(2)), int(mm.group(3)), 1.0) if mm else hex_rgb(h)
            alpha = rgba[3]
            if mm and mm.group(4):
                a = mm.group(4)
                alpha = float(a.rstrip("%")) / (100 if a.endswith("%") else 1)
            if alpha < 0.999:
                res.append((h, "none", "", tr("map.note.alpha", a="%.2f" % alpha)))
                continue
            rgb = rgba[:3]
            cands = sorted(x for x in col.get(rgb, []) if x.startswith(pre))
            if len(cands) == 1:
                res.append((h, "exact", cands[0], ""))
            elif cands:
                res.append((h, "role", ", ".join(cands[:4]), tr("map.note.same", n=len(cands))))
            else:
                best = sorted((de(rgb, k), x) for k, xs in col.items() for x in xs if x.startswith(pre))[:1]
                if best and best[0][0] <= 4:
                    res.append((h, "near", best[0][1], tr("map.note.near_de", d="%.1f" % best[0][0])))
                else:
                    raw = sorted(col.get(rgb, []))
                    semantic = [x for x in raw if any(x.startswith(r) for r in sem)]
                    note = tr("map.note.other_role", token=semantic[0]) if semantic else tr("map.note.primitive", token=raw[0]) if raw else tr("map.note.no_token")
                    res.append((h, "none", "", note))
        return res
    for pat, pres, kind in length:
        if not pat.match(prop) or not pres:
            continue
        for m in PX.finditer(val):
            v = float(m.group(1))
            if v in (0, 1) and kind != "font-size":
                continue
            if kind == "radius" and v >= 999:
                res.append((m.group(0), "none", "", tr("map.note.pill")))
                continue
            cands = sorted(x for x in ln.get(v, []) if x.startswith(pres))
            if kind == "spacing" and scale:
                generic = [x for x in cands if x.startswith(scale)]
                if generic:
                    extra = len(cands) - len(generic)
                    res.append((m.group(0), "exact", generic[0], tr("map.note.scale_extra", n=extra) if extra else tr("map.note.scale")))
                    continue
            if len(cands) == 1:
                res.append((m.group(0), "exact", cands[0], tr("map.note.check_role") if kind in ("font-size", "line-height") else ""))
            elif cands:
                res.append((m.group(0), "role", ", ".join(cands[:4]), tr("map.note.same", n=len(cands))))
            else:
                near = sorted((abs(k - v), x) for k, xs in ln.items() for x in xs if x.startswith(pres))[:1]
                if near and near[0][0] <= 1:
                    res.append((m.group(0), "near", near[0][1], tr("map.note.near_px", d="%g" % near[0][0])))
                else:
                    res.append((m.group(0), "none", "", tr("map.note.no_token")))
    return res


def main():
    ap = argparse.ArgumentParser(description="Propose a mapping from hard-coded values to existing DS tokens (read-only).",
                                 epilog="Confidence levels: Exact, By role, Near, None. Exit code 1 on error.")
    ap.add_argument("apps", nargs="*", help="app ids from kit.config.json > apps (default: all)")
    ap.add_argument("--csv", help="write every proposal to this CSV file")
    ap.add_argument("--limit", type=int, default=12, help="value groups shown per confidence level (default 12)")
    ap.add_argument("--project", help="project folder (default: the current folder)")
    a = ap.parse_args()
    ctx = A.Ctx(a.project)
    tr = ctx.tr
    apps = ctx.apps()
    keys = a.apps or list(apps)
    for k in keys:
        if k not in apps:
            A.die("app '%s' is not declared in kit.config.json > apps (declared: %s)" % (k, ", ".join(apps) or "none"))
    lib = A.ds_facts(ctx)
    tok = default_tokens(ctx)
    if not tok:
        A.die("no token defined on a plain :root rule in %s: cannot resolve default values." % ctx.bundle_path)
    col, ln = build_index(tok)
    rules = prop_rules(ctx)
    label = {c: tr("map.conf." + c) for c in CONF}
    out_rows = []
    print("# %s\n" % tr("map.title"))
    print(tr("map.intro", ds=ctx.label()) + "\n")
    for k in keys:
        grp = collections.defaultdict(list)
        for f, line, sel, prop, val in occurrences(ctx, apps[k], lib):
            for orig, conf, token, note in suggest(ctx, rules, prop, val, col, ln):
                out_rows.append([k, f, line, sel, prop, orig, conf, token, note])
                g = prop if prop.startswith("--") else re.sub(r"-(top|right|bottom|left|inline|block)(-.*)?$", "", prop)
                grp[(conf, g, orig.lower(), token, note)].append("%s:%d" % (f, line))
        cnt = collections.Counter(c for (c, *_r), v in grp.items() for _ in v)
        print("## %s\n" % apps[k].get("name", k))
        print("| %s | %s | %s |\n|---|---|---|" % (tr("map.col.conf"), tr("map.col.count"), tr("map.col.distinct")))
        for c in CONF:
            print("| %s | %d | %d |" % (label[c], cnt[c], len([g for g in grp if g[0] == c])))
        print()
        for c in CONF:
            items = sorted(((g, v) for g, v in grp.items() if g[0] == c), key=lambda x: (-len(x[1]), x[0][2]))[:a.limit]
            if not items:
                continue
            print("**%s**\n" % label[c])
            print("| %s | %s | %s | %s | %s | %s |\n|---|---|---|---|---|---|" % tuple(
                tr("map.col." + x) for x in ("prop", "value", "token", "note", "places", "example")))
            for (conf, prop, orig, token, note), locs in items:
                tk = ("`%s`" % token.replace(", ", "`, `")) if token else "—"
                print("| `%s` | `%s` | %s | %s | %d | `%s` |" % (prop, orig, tk, note or "—", len(locs), locs[0]))
            print()
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["app", "file", "line", "selector", "property", "value", "confidence", "token", "note"])
            w.writerows(out_rows)


if __name__ == "__main__":
    main()
