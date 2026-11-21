#!/usr/bin/env python3
"""Static DS compliance audit of the apps in kit.config.json (read-only: changes nothing).

Per app it measures: declared DS version against ds.json, embedded tokens against the DS bundle, hard-coded values
outside tokens, Tailwind arbitrary values and inline style objects (react, vue), CSS that overrides DS classes,
tokens used but never defined, DS component use, theming attributes and the local-component registry.
It does not run a browser: overflow, console errors, contrast and large text are checked by the review skill.

DS region  = text between the comments /* <css.marker.begin> */ and /* <css.marker.end> */ (ds.json), plus whole
             <style id="<css.styleBlocks>…"> blocks when ds.json sets css.styleBlocks (e.g. "lib").
App region = every other CSS (other <style> blocks, .css files outside the region, style="" attributes,
             style={{...}} objects, :style bindings, Tailwind arbitrary values).

Usage:
  python3 audit_app.py                      markdown report for every app
  python3 audit_app.py acme-web             one app
  python3 audit_app.py --json out.json      also write raw numbers
  python3 audit_app.py --roots roots.json   write the DS root classes for audit_components_browser.js
"""
import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, ds_path, t  # noqa: E402

SKIP_DIRS = {"node_modules", "dist", "build", ".vite", ".next", ".nuxt", "coverage", ".git"}
EXT_HTML = {".html", ".htm"}
EXT_CSS = {".css", ".scss"}
EXT_SCRIPT = {".js", ".mjs", ".ts", ".tsx", ".jsx"}
EXT_VUE = {".vue"}

STYLE = re.compile(r"<style([^>]*)>(.*?)</style>", re.S | re.I)
STYLE_ATTR = re.compile(r'(?<![:\w-])style="([^"]*)"')
COMMENT = re.compile(r"/\*.*?\*/", re.S)
URL = re.compile(r"url\([^)]*\)", re.I)
HEX = re.compile(r"(?<![&\w-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")
FUNC = re.compile(r"\b(?:rgba?|hsla?)\(\s*[0-9.]")
NAMED = re.compile(r"(?:^|[;{\s])(?:color|background(?:-color)?|border(?:-[a-z]+)?-color|fill|stroke|outline-color)\s*:\s*"
                   r"(white|black|red|blue|green|gray|grey|orange|yellow|purple|pink|navy|silver)\b", re.I)
PX_FONT = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px")
PX_RADIUS = re.compile(r"border-radius\s*:\s*([^;}]*\d+(?:\.\d+)?px[^;}]*)")
PX_SPACE = re.compile(r"(?:^|[;{\s])(?:margin|padding|gap|row-gap|column-gap)(?:-[a-z]+)?\s*:\s*([^;}]*\d+(?:\.\d+)?px[^;}]*)")
SHADOW = re.compile(r"box-shadow\s*:\s*(?!none)([^;}]+)")
FALLBACK = re.compile(r"var\([^()]*,\s*(?:#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))\s*\)")
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
CLASS = re.compile(r"\.([A-Za-z][\w-]*)")
GENERIC = {"active", "selected", "open", "disabled", "hidden", "show", "hide", "left", "right", "center", "grow", "thumb", "small", "large"}
VISUAL_PROPS = r"color|background[a-z-]*|border[a-z-]*|box-shadow|font[a-z-]*|line-height|height|min-height|padding[a-z-]*"

# Tailwind arbitrary values: bg-[#fff], p-[13px], rounded-[6px], text-[13px], hover:bg-[rgb(0_0_0)]
TW = re.compile(r"(?<![\w\[-])((?:[\w-]+:)*)-?(bg|text|border(?:-[trblxy])?|rounded(?:-[a-z]{1,2})?|p[trblxy]?|m[trblxy]?|gap(?:-[xy])?|"
                r"space-[xy]|leading|tracking|fill|stroke|ring|outline|shadow|decoration)-\[([^\]\s'\"`]+)\]")
TW_PALETTE = re.compile(r"(?<![\w-])(?:[\w-]+:)*(?:bg|text|border|fill|stroke|ring|outline|decoration)-"
                        r"(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|"
                        r"violet|purple|fuchsia|pink|rose)-(?:50|[1-9]00|950)\b")
TW_PROP = {"bg": "background-color", "rounded": "border-radius", "leading": "line-height", "tracking": "letter-spacing",
           "fill": "fill", "stroke": "stroke", "ring": "outline-color", "outline": "outline-color", "shadow": "box-shadow",
           "decoration": "text-decoration-color"}
COLORISH = re.compile(r"^(#|rgba?\(|hsla?\(|(white|black|red|blue|green|gray|grey|orange|yellow|purple|pink)$)", re.I)
STYLE_OBJ = re.compile(r"\bstyle=\{\{(.*?)\}\}", re.S)
VUE_STYLE = re.compile(r"(?:\s:|v-bind:)style=\"\{(.*?)\}\"", re.S)
UNITLESS = {"line-height", "opacity", "z-index", "font-weight", "flex", "flex-grow", "flex-shrink", "order", "zoom"}


def read(p):
    return Path(p).read_text(encoding="utf-8", errors="replace")


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


AT_STMT = re.compile(r"@(?:import|charset|use|forward|tailwind|namespace)\b[^;{]*;")


def strip(css):
    return AT_STMT.sub("", URL.sub("url()", COMMENT.sub("", css)))


def blank(m):
    """Replace a match with spaces, keeping newlines so line numbers stay right."""
    return re.sub(r"[^\n]", " ", m.group(0))


def norm(x):
    return re.sub(r"\s+", " ", x.strip())


def top_n(counter, n=None):
    """Like Counter.most_common, ties sorted by name so every run gives the same output."""
    return sorted(counter.items(), key=lambda x: (-x[1], str(x[0])))[:n]


def vkey(s):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", s or "")
    return tuple(map(int, m.groups())) if m else None


# ---------- configuration ----------

class Ctx:
    """Everything the audit needs from kit.config.json and ds.json."""

    def __init__(self, start=None):
        cfg = load(start)
        if cfg["_ds"] is None:
            die("no DS profile: kit.config.json > ds must point at a folder with ds.json.")
        self.cfg, self.ds, self.root = cfg, cfg["_ds"], Path(cfg["_root"])
        self.prefix = self.ds["tokens"]["prefix"]
        p = re.escape(self.prefix)
        self.DEF = re.compile(r"(%s[A-Za-z0-9_-]+)\s*:\s*([^;}]+)" % p)
        self.USE = re.compile(r"var\(\s*(%s[A-Za-z0-9_-]+)" % p)
        self.VISUAL = re.compile(r"(?:^|[;\s])(?:%s|%s[a-z0-9-]+)\s*:" % (VISUAL_PROPS, p))
        mk = self.ds["css"]["marker"]
        self.REGION = re.compile(r"/\*\s*%s[^*]*\*/(.*?)/\*\s*%s[^*]*\*/" % (re.escape(mk["begin"]), re.escape(mk["end"])), re.S)
        # Optional: whole <style id="<prefix>…"> blocks are DS CSS (DS that embed their library blocks by id)
        sb = self.ds["css"].get("styleBlocks")
        self.STYLE_ID = re.compile(r'\bid\s*=\s*["\']%s[^"\']*["\']' % re.escape(sb), re.I) if sb else None
        loc = cfg["local"]
        self.local_prefix = loc["prefix"]
        self.LOCAL = re.compile(r"/\*\s*%s:\s*([^*]*?)\s*\*/" % re.escape(loc["marker"]))
        bundle = self.ds["css"]["bundle"]
        if not bundle:
            die("ds.json > css.bundle is empty: the audit needs the DS CSS bundle.")
        self.bundle_path = ds_path(cfg, bundle)
        if "://" in self.bundle_path:
            die("ds.json > css.bundle is a URL (%s): download it into the profile folder and point css.bundle at the file." % bundle)
        if not Path(self.bundle_path).is_file():
            die("DS bundle not found: %s" % self.bundle_path)
        self.bundle_name = Path(self.bundle_path).name
        srcs = [ds_path(cfg, s) for s in self.ds["css"]["sources"] if "component" in s.lower()]
        self.components_css = [s for s in srcs if Path(s).is_file()] or [self.bundle_path]
        self.stack = cfg["stack"]

    def apps(self):
        return {a["id"]: a for a in self.cfg["apps"] if a.get("id")}

    def label(self):
        return "%s %s" % (self.ds["label"], self.ds["version"])

    def tr(self, key, **kw):
        return t(self.cfg, "review." + key, **kw)


def app_files(ctx, app):
    base = (ctx.root / app["path"]).resolve()
    if not base.exists():
        die("app '%s': path not found: %s" % (app["id"], app["path"]))
    if base.is_file():
        return [base]
    ds_dir = Path(ctx.cfg["_ds_dir"]).resolve()
    exts = EXT_HTML | EXT_CSS | EXT_SCRIPT | EXT_VUE
    out = []
    for f in sorted(base.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in exts:
            continue
        rel = f.relative_to(base).parts
        if any(p in SKIP_DIRS or p.startswith(".") for p in rel[:-1]):
            continue
        if ds_dir in f.resolve().parents:
            continue  # a DS profile copied inside the app is DS, not app
        if f.name.endswith((".min.js", ".min.css")):
            continue
        out.append(f)
    return out


# ---------- DS facts ----------

def ds_facts(ctx, min_rules=3):
    bundle = read(ctx.bundle_path)
    css = strip(bundle)
    defs = {(k, norm(v)) for k, v in ctx.DEF.findall(css)}
    cnt = collections.Counter()
    for m in RULE.finditer(css):
        for c in set(CLASS.findall(m.group(1))):
            cnt[c] += 1
    classes = {c for c, n in cnt.items() if n >= 3 and len(c) > 3 and c not in GENERIC}
    comp = strip("\n".join(read(f) for f in ctx.components_css))
    rootn, mods = collections.Counter(), collections.defaultdict(set)
    for m in RULE.finditer(comp):
        for sel in m.group(1).split(","):
            first = re.split(r"[\s>+~]", sel.strip())[:1]
            cs = CLASS.findall(first[0]) if first else []
            if cs:
                rootn[cs[0]] += 1
                mods[cs[0]] |= set(cs[1:])
    allm = set().union(*mods.values()) if mods else set()
    roots = {r for r, n in rootn.items() if n >= min_rules and len(r) > 2 and r not in allm
             and not r.startswith(("is-", ctx.local_prefix))}
    classes |= roots  # root classes count even when short (btn, tag)
    rules = {(norm(m.group(1)), norm(m.group(2))) for m in RULE.finditer(css)}
    return {"rules": rules, "sel": {k for k, _ in rules}, "roots": roots, "mods": {r: mods[r] for r in roots},
            "all_classes": set(rootn) | allm | set(cnt), "defs": defs, "names": {k for k, _ in defs},
            "classes": classes, "version": ctx.ds["version"]}


# ---------- extraction ----------

def split_top(text, sep=","):
    out, depth, quote, cur = [], 0, None, []
    for ch in text:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'`":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0 and not quote:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return [s.strip() for s in out if s.strip()]


def kebab(k):
    return re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), k.strip().strip("'\""))


def style_object(body):
    """'color: "#fff", padding: 13' -> 'color: #fff; padding: 13px'. Expressions and template strings are skipped."""
    decls = []
    for part in split_top(body):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        prop, v = kebab(k), v.strip()
        if re.fullmatch(r"(['\"])(.*)\1", v, re.S):
            v = v[1:-1]
        elif re.fullmatch(r"-?\d+(?:\.\d+)?", v):
            v = v if prop in UNITLESS or v == "0" else v + "px"
        else:
            continue
        decls.append("%s: %s" % (prop, v))
    return "; ".join(decls)


def tailwind_decl(base, value):
    value = re.sub(r"^(color|length|size|number|percentage|url|image|position|line-width|family|shadow):", "", value).replace("_", " ")
    if "var(" in value or value.startswith("--"):
        return None  # a token through an arbitrary value: not hard-coded
    color = bool(COLORISH.match(value))
    if base == "text":
        prop = "color" if color else "font-size"
    elif base.startswith("border"):
        if not color:
            return None
        side = {"t": "-top", "r": "-right", "b": "-bottom", "l": "-left"}.get(base[7:8], "")
        prop = "border%s-color" % side
    elif base.startswith("rounded"):
        prop = "border-radius"
    elif base[0] in "pm" and re.fullmatch(r"[pm][trblxy]?", base):
        prop = ("padding" if base[0] == "p" else "margin") + {"t": "-top", "r": "-right", "b": "-bottom", "l": "-left",
                                                               "x": "-inline", "y": "-block"}.get(base[1:2], "")
    elif base.startswith("gap"):
        prop = {"gap-x": "column-gap", "gap-y": "row-gap"}.get(base, "gap")
    elif base.startswith("space"):
        prop = "margin"
    elif base in ("fill", "stroke", "ring", "outline") and not color:
        return None  # widths, not colours
    else:
        prop = TW_PROP.get(base)
    return (prop, value) if prop else None


def inline_decls(ctx, path, text):
    """[(line, origin, 'prop: value; ...')] for style="", style={{}}, :style and Tailwind arbitrary values."""
    out = []
    suf = path.suffix.lower()
    line = lambda pos: text.count("\n", 0, pos) + 1
    if suf in EXT_HTML | EXT_VUE:
        no_style = STYLE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
        for m in STYLE_ATTR.finditer(no_style):
            out.append((line(m.start()), 'style=""', m.group(1)))
    if suf in {".tsx", ".jsx", ".js", ".ts"}:
        for m in STYLE_OBJ.finditer(text):
            d = style_object(m.group(1))
            if d:
                out.append((line(m.start()), "style={{}}", d))
    if suf in EXT_VUE:
        for m in VUE_STYLE.finditer(text):
            d = style_object(m.group(1))
            if d:
                out.append((line(m.start()), ":style", d))
    if ctx.stack in ("react", "vue") and suf in EXT_SCRIPT | EXT_VUE | EXT_HTML:
        for m in TW.finditer(text):
            d = tailwind_decl(m.group(2), m.group(3))
            if d:
                out.append((line(m.start()), "tw:" + m.group(0), "%s: %s" % d))
    return out


def tailwind_counts(ctx, text):
    if ctx.stack not in ("react", "vue"):
        return collections.Counter(), 0
    arb = collections.Counter(m.group(0) for m in TW.finditer(text) if tailwind_decl(m.group(2), m.group(3)))
    return arb, len(TW_PALETTE.findall(text))


def css_blocks(ctx, path, text):
    """[(start_line, ds_css, app_css)] for every CSS source in a file. Line numbers are 1-based."""
    suf = path.suffix.lower()
    mask = lambda m: re.sub(r"[^\n]", " ", m.group(0))
    if suf in EXT_CSS:
        if path.name == ctx.bundle_name:
            return [(1, text, re.sub(r"[^\n]", " ", text))]  # a copy of the DS bundle inside the app is DS CSS
        return [(1, "\n".join(ctx.REGION.findall(text)), ctx.REGION.sub(mask, text))]
    if suf in EXT_HTML | EXT_VUE:
        out = []
        for m in STYLE.finditer(text):
            line = text.count("\n", 0, m.start(2)) + 1
            if ctx.STYLE_ID and ctx.STYLE_ID.search(m.group(1)):
                out.append((line, m.group(2), re.sub(r"[^\n]", " ", m.group(2))))
            else:
                out.append((line, "\n".join(ctx.REGION.findall(m.group(2))), ctx.REGION.sub(mask, m.group(2))))
        return out
    return []


def imports_bundle(ctx, text):
    n = re.escape(ctx.bundle_name)
    return bool(re.search(r"""(?:@import|import)\s*(?:url\()?\s*['"][^'"]*%s['"]""" % n, text)
                or re.search(r"""<link\b[^>]*\bhref\s*=\s*['"][^'"]*%s['"]""" % n, text, re.I))


def declared_versions(ctx, files):
    ds = ctx.ds
    meta = re.compile(r'name="%s"\s+content="([^"]*)"' % re.escape(ds["version_label"]["meta"]))
    pat = re.escape(ds["version_label"]["text"]).replace(r"\{label\}", re.escape(ds["label"])) \
        .replace(r"\{name\}", re.escape(ds.get("name") or "")).replace(r"\{version\}", r"(\d+\.\d+\.\d+)")
    label = re.compile(pat)
    seen = collections.Counter()
    for f in files:
        txt = read(f)
        for m in meta.finditer(txt):
            seen["meta " + m.group(1)] += 1
        for m in label.finditer(txt):
            seen["label " + m.group(1)] += 1
    return seen


# ---------- audit ----------

def audit_app(ctx, app, lib):
    files = app_files(ctx, app)
    texts = {f: read(f) for f in files}
    ds_parts, app_parts, inline, inline_raw = [], [], [], []
    seen_blocks = set()
    imported = [str(f.relative_to(ctx.root)) for f, x in texts.items() if imports_bundle(ctx, x)]
    tw_arb, tw_pal = collections.Counter(), 0
    for f, txt in texts.items():
        for _, d, a in css_blocks(ctx, f, txt):
            h = hashlib.sha1(a.encode()).hexdigest()
            if h in seen_blocks:
                continue  # the same block copied into several files (multi apps with a shared shell) counts once
            seen_blocks.add(h)
            ds_parts.append(d)
            app_parts.append(a)
        for _, origin, d in inline_decls(ctx, f, txt):
            inline_raw.append((origin, d))
            inline.append(d)
        a_, p_ = tailwind_counts(ctx, txt)
        tw_arb += a_
        tw_pal += p_
    ds_css, app_css = strip("\n".join(ds_parts)), strip("\n".join(app_parts))
    inline = [strip(x) for x in inline]
    res = {"app": app["id"], "name": app.get("name", app["id"]), "files": len(files)}

    # 1. version
    seen = declared_versions(ctx, files)
    vs = sorted({vkey(k) for k in seen if vkey(k)})
    cur = vs[-1] if vs else None
    res["version"] = {"ds": lib["version"], "app": ".".join(map(str, cur)) if cur else None, "declared": dict(seen),
                      "behind": bool(cur and vkey(lib["version"]) and cur < vkey(lib["version"])),
                      "inconsistent": len(vs) > 1}

    # 2. embedded tokens against the bundle
    app_defs = {(k, norm(v)) for k, v in ctx.DEF.findall(ds_css)}
    app_names = {k for k, _ in app_defs}
    res["tokens"] = {"embedded": len(app_names), "imported": imported,
                     "missing": sorted(lib["names"] - app_names) if app_names else [],
                     "changed": sorted({k for k, _ in app_defs - lib["defs"]} & lib["names"]),
                     "extra": sorted(app_names - lib["names"])}

    # verbatim DS rules outside the region are DS CSS, not app CSS
    copied = [0]

    def drop_copy(m):
        if (norm(m.group(1)), norm(m.group(2))) in lib["rules"]:
            copied[0] += 1
            return ""
        return m.group(0)
    app_css = RULE.sub(drop_copy, app_css)
    res["copied_rules"] = copied[0]

    # 3. tokens redefined in the app region (a verbatim copy of a DS definition is allowed)
    app_side = {(k, norm(v)) for k, v in ctx.DEF.findall(app_css)}
    res["redefined"] = sorted({k for k, _ in app_side - lib["defs"] - app_defs})

    # 4. tokens used but defined nowhere
    used = set(ctx.USE.findall(app_css)) | set(ctx.USE.findall("\n".join(inline)))
    for f, txt in texts.items():
        if f.suffix.lower() in EXT_SCRIPT | EXT_VUE | EXT_HTML:
            used |= set(ctx.USE.findall(txt))
    defined = app_names | {k for k, _ in ctx.DEF.findall(app_css)}
    res["undefined_tokens"] = sorted(used - defined - lib["names"])

    # 5. hard-coded values (raw values inside token definitions are counted under "redefined")
    scan = ctx.DEF.sub("", app_css) + "\n" + "\n".join(inline)
    hexes = HEX.findall(scan)
    res["hard"] = {"hex": len(hexes), "rgb_hsl": len(FUNC.findall(scan)), "named": len(NAMED.findall(scan)),
                   "fallback_in_var": len(FALLBACK.findall(scan)),
                   "font_px": len(PX_FONT.findall(scan)), "radius_px": len(PX_RADIUS.findall(scan)),
                   "space_px": len([x for x in PX_SPACE.findall(scan) if re.search(r"[2-9]\d*(?:\.\d+)?px|1\d+px", x)]),
                   "shadow_literal": len([x for x in SHADOW.findall(scan) if "var(" not in x]),
                   "important": scan.count("!important"), "token_uses": len(ctx.USE.findall(scan)),
                   "top_hex": top_n(collections.Counter(h.lower() for h in hexes), 8),
                   "inline_by_origin": dict(collections.Counter(o.split(":")[0] if o.startswith("tw:") else o for o, _ in inline_raw))}
    res["tailwind"] = {"arbitrary": sum(tw_arb.values()),
                       "arbitrary_colour": sum(n for k, n in tw_arb.items() if re.search(r"\[(#|rgb|hsl)", k)),
                       "palette": tw_pal, "top": top_n(tw_arb, 8)}

    # 6. CSS overriding DS classes
    over = collections.Counter()
    for m in RULE.finditer(app_css):
        if not ctx.VISUAL.search(m.group(2)):
            continue
        for c in set(CLASS.findall(m.group(1))):
            if c in lib["classes"] and not c.startswith(ctx.local_prefix):
                over[c] += 1
    same = sorted({norm(m.group(1)) for m in RULE.finditer(app_css) if norm(m.group(1)) in lib["sel"]
                   and not m.group(1).strip().startswith((":root", "html", "body", "@")) and not re.match(r"^[\d.%,\s]+$", m.group(1).strip())})
    res["override"] = {"rules": sum(over.values()), "classes": top_n(over, 10), "same_selector": same}

    # 6b. component use: DS root classes in markup, unknown variants, native controls without a DS or local class
    markup = "\n".join(txt for f, txt in texts.items() if f.suffix.lower() in EXT_HTML | EXT_SCRIPT | EXT_VUE)
    app_defined = set(CLASS.findall(app_css))
    roots, mods, allc = lib["roots"], lib["mods"], lib["all_classes"]
    used_c, unknown = collections.Counter(), collections.Counter()
    for attr in re.findall(r"""class(?:Name)?\s*[=:]\s*\\?["'`]([^"'`<>{}$]+)""", markup):
        toks = [x.strip("\\") for x in attr.split()]
        for tk in toks:
            if tk in roots:
                used_c[tk] += 1
                for u in toks:
                    if u != tk and u not in mods[tk] and not u.startswith(ctx.local_prefix) and u not in allc and u not in app_defined \
                            and not re.match(r"^[\w-]+:|.*\[", u):
                        unknown[(tk, u)] += 1
    native = {}
    for tag, extra in (("button", ""), ("input", r"(?![^>]*type=[\"']?(?:checkbox|radio|hidden|file|range|color))"),
                       ("select", ""), ("textarea", ""), ("table", "")):
        n = {"ds": 0, "local": 0, "none": 0}
        for m in re.finditer(r"<%s\b%s([^>]*)>" % (tag, extra), markup):
            cl = re.search(r"""class(?:Name)?=\\?["'{]([^"'}]*)""", m.group(1))
            toks = [x.strip("\\") for x in cl.group(1).split()] if cl else []
            n["ds" if any(x in roots or x in allc for x in toks) else "local" if any(x.startswith(ctx.local_prefix) for x in toks) else "none"] += 1
        native[tag] = n
    res["components"] = {"used": top_n(used_c), "roots": len(roots),
                         "unknown_modifiers": [("%s.%s" % k, v) for k, v in top_n(unknown, 10)], "native": native}

    # 7. theming attributes from ds.json > theming
    blob = "\n".join(ctx.REGION.sub("", x) for x in texts.values())  # the DS region only reads the attributes
    th = {}
    for key, spec in (ctx.ds.get("theming") or {}).items():
        if not isinstance(spec, dict):
            continue  # notes or other non-attribute entries
        attr = spec.get("attr")
        if not attr:
            continue
        camel = re.sub(r"-([a-z])", lambda m: m.group(1).upper(), attr[5:]) if attr.startswith("data-") else None
        # only the root element carries theming attributes: <html …>, documentElement.setAttribute/dataset
        # (the same attribute name on other elements is app state, e.g. data-mode="edit" on a panel)
        vals = set()
        for tag in re.findall(r"<html\b[^>]*>", blob, re.I):
            vals |= set(re.findall(r'%s="([\w-]+)"' % re.escape(attr), tag))
        vals |= set(re.findall(r"""documentElement\.setAttribute\(\s*['"]%s['"]\s*,\s*['"]([\w-]+)['"]""" % re.escape(attr), blob))
        if camel:
            vals |= set(re.findall(r"""documentElement\.dataset\.%s\s*=\s*['"]([\w-]+)['"]""" % camel, blob))
        allowed = spec.get("values") or []
        th[key] = {"attr": attr, "values": sorted(vals), "unknown": sorted(v for v in vals if allowed and v not in allowed),
                   "default": spec.get("default")}
    res["theme"] = th

    # 8. local components
    reg_path = ctx.root / ctx.cfg["local"]["registry"]
    comps = []
    if reg_path.is_file():
        data = json.loads(read(reg_path))
        items = data.get("components", []) if isinstance(data, dict) else data
        comps = [c for c in items if isinstance(c, dict) and c.get("app") in (app["id"], app.get("name"))]
    blocks = sorted({m.strip() for txt in texts.values() for m in ctx.LOCAL.findall(txt)})
    known = {str(c.get(k)) for c in comps for k in ("block", "name", "title", "id") if c.get(k)}
    known |= {m.strip() for c in comps if c.get("anchor") for m in ctx.LOCAL.findall(str(c["anchor"]))}  # registry keeps the full comment
    res["local"] = {"registry": str(reg_path.relative_to(ctx.root)), "registry_found": reg_path.is_file(), "total": len(comps),
                    "by_status": dict(collections.Counter(c.get("status") for c in comps)),
                    "pending": [c.get("title") or c.get("name") or c.get("id") for c in comps if c.get("status") == "pending"],
                    "blocks": blocks, "unregistered": [b for b in blocks if b not in known]}
    res["css_lines"] = app_css.count("\n") + 1
    return res


# ---------- report ----------

def level(ctx, n, warn=None):
    return ctx.tr("level.pass") if n == 0 else ctx.tr("level.deviation") if warn is None or n > warn else ctx.tr("level.note")


def rows(ctx, r):
    tr, R = ctx.tr, []
    h, tk, v = r["hard"], r["tokens"], r["version"]
    R.append((tr("row.version"), tr("res.version", app=v["app"] or tr("unknown"), ds=v["ds"]),
              tr("level.deviation") if v["behind"] or not v["app"] else tr("level.note") if v["inconsistent"] else tr("level.pass")))
    if tk["embedded"]:
        R.append((tr("row.tokens"), tr("res.tokens", missing=len(tk["missing"]), changed=len(tk["changed"]), extra=len(tk["extra"])),
                  level(ctx, len(tk["missing"]) + len(tk["changed"]), 0)))
    elif tk["imported"]:
        R.append((tr("row.tokens"), tr("res.tokens_imported", file=", ".join(tk["imported"][:3])), tr("level.pass")))
    else:
        R.append((tr("row.tokens"), tr("res.tokens_none"), tr("level.deviation")))
    R.append((tr("row.redefined", prefix=ctx.prefix), str(len(r["redefined"])), level(ctx, len(r["redefined"]), 0)))
    R.append((tr("row.colors"), tr("res.colors", hex=h["hex"], func=h["rgb_hsl"], named=h["named"], fb=h["fallback_in_var"]),
              level(ctx, h["hex"] + h["rgb_hsl"] + h["named"], 0)))
    R.append((tr("row.metrics"), "%d, %d, %d, %d" % (h["font_px"], h["radius_px"], h["space_px"], h["shadow_literal"]),
              level(ctx, h["font_px"] + h["radius_px"] + h["shadow_literal"], 0)))
    if ctx.stack in ("react", "vue"):
        tw = r["tailwind"]
        R.append((tr("row.tailwind"), tr("res.tailwind", n=tw["arbitrary"], colors=tw["arbitrary_colour"], palette=tw["palette"]),
                  tr("level.deviation") if tw["arbitrary"] else tr("level.note") if tw["palette"] else tr("level.pass")))
    o = r["override"]
    R.append((tr("row.override"), tr("res.override", rules=o["rules"], same=len(o["same_selector"]), important=h["important"], copied=r["copied_rules"]),
              level(ctx, o["rules"], 0)))
    c = r["components"]
    tot = sum(sum(x.values()) for x in c["native"].values())
    non = sum(x["none"] for x in c["native"].values())
    R.append((tr("row.components"), tr("res.components", used=len(c["used"]), roots=c["roots"], unknown=len(c["unknown_modifiers"]), native=non, total=tot),
              level(ctx, len(c["unknown_modifiers"]) + non, 0)))
    R.append((tr("row.undefined"), str(len(r["undefined_tokens"])), level(ctx, len(r["undefined_tokens"]), 0)))
    parts, bad = [], 0
    for key, x in r["theme"].items():
        parts.append("`%s` %s" % (x["attr"], ", ".join(x["values"]) or tr("not_set")))
        bad += len(x["unknown"])
    R.append((tr("row.theming"), "; ".join(parts) or tr("res.theming_none"), tr("level.deviation") if bad else tr("level.pass")))
    lo = r["local"]
    st = ", ".join("%s %d" % (k, n) for k, n in sorted((str(k), n) for k, n in lo["by_status"].items())) or tr("empty")
    R.append((tr("row.local"), tr("res.local", total=lo["total"], status=st, pending=len(lo["pending"]), blocks=len(lo["blocks"]), unregistered=len(lo["unregistered"])),
              tr("level.note") if lo["pending"] or lo["unregistered"] else tr("level.pass")))
    return R


def codes(xs, fmt="`%s`", n=6):
    return ", ".join(fmt % (x if isinstance(x, tuple) else (x,)) for x in xs[:n])


def report(ctx, r):
    tr, L = ctx.tr, []
    h, tk, c, lo, o = r["hard"], r["tokens"], r["components"], r["local"], r["override"]
    L += ["## %s" % r["name"], "", tr("scanned", files=r["files"], lines=r["css_lines"]), "",
          "| %s | %s | %s |" % (tr("col.item"), tr("col.result"), tr("col.level")), "|---|---|---|"]
    L += ["| %s | %s | %s |" % x for x in rows(ctx, r)]
    L += ["", tr("legend"), ""]
    b = lambda key, items, fmt="`%s`": L.append("- " + tr(key, n=len(items), list=codes(items, fmt))) if items else None
    if r["version"]["inconsistent"]:
        L.append("- " + tr("b.versions", list=", ".join("`%s`" % k for k in sorted(r["version"]["declared"]))))
    b("b.missing", tk["missing"])
    b("b.changed", tk["changed"])
    b("b.redefined", r["redefined"])
    b("b.top_hex", h["top_hex"], "`%s` ×%d")
    if ctx.stack in ("react", "vue"):
        b("b.tailwind", r["tailwind"]["top"], "`%s` ×%d")
    b("b.same_selector", o["same_selector"])
    b("b.overridden", o["classes"], "`.%s` ×%d")
    b("b.unknown_mods", c["unknown_modifiers"], "`%s` ×%d")
    bad = ["%s %d/%d" % (k, x["none"], sum(x.values())) for k, x in c["native"].items() if x["none"]]
    if bad:
        L.append("- " + tr("b.native", list=", ".join(bad)))
    b("b.used", c["used"], "`.%s` ×%d")
    b("b.undefined", r["undefined_tokens"])
    for key, x in r["theme"].items():
        if x["unknown"]:
            L.append("- " + tr("b.theming_unknown", attr=x["attr"], list=", ".join(x["unknown"])))
    b("b.local_pending", lo["pending"], "%s")
    b("b.local_unregistered", lo["unregistered"], "%s")
    if not lo["registry_found"]:
        L.append("- " + tr("b.no_registry", path=lo["registry"]))
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Static DS compliance audit of the apps in kit.config.json (read-only).",
                                 epilog="Run from the project folder (or pass --project). Exit code 1 on error.")
    ap.add_argument("apps", nargs="*", help="app ids from kit.config.json > apps (default: all)")
    ap.add_argument("--json", help="also write raw numbers to this file")
    ap.add_argument("--roots", help="write the DS root classes (JSON list) for audit_components_browser.js")
    ap.add_argument("--min-rules", type=int, default=3, help="rules a class needs in the DS components CSS to count as a root class (default 3)")
    ap.add_argument("--project", help="project folder (default: the current folder)")
    a = ap.parse_args()
    ctx = Ctx(a.project)
    apps = ctx.apps()
    keys = a.apps or list(apps)
    for k in keys:
        if k not in apps:
            die("app '%s' is not declared in kit.config.json > apps (declared: %s)" % (k, ", ".join(apps) or "none"))
    lib = ds_facts(ctx, a.min_rules)
    out, js = ["# " + ctx.tr("title"), "", ctx.tr("intro", ds=ctx.label(), bundle=Path(ctx.bundle_path).relative_to(ctx.root) if ctx.root in Path(ctx.bundle_path).parents else ctx.bundle_path, stack=ctx.stack), ""], []
    for k in keys:
        r = audit_app(ctx, apps[k], lib)
        js.append(r)
        out.append(report(ctx, r))
    print("\n".join(out))
    if a.roots:
        Path(a.roots).write_text(json.dumps(sorted(lib["roots"])), encoding="utf-8")
    if a.json:
        Path(a.json).write_text(json.dumps(js, ensure_ascii=False, indent=1, default=list), encoding="utf-8")


if __name__ == "__main__":
    main()
