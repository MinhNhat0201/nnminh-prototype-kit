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
  python3 audit_app.py --no-extra           skip kit.config.json > review.extraChecks
  python3 audit_app.py --no-rules           skip the check commands of the rules registry (scripts/rules.py)
  python3 audit_app.py --selftest           checks of the extra-check runner and the DS Vue layer check

Project checks (extension point): kit.config.json > review.extraChecks = [{"name", "command", "parse"?, "level"?}] run
after the scan in the project root. A command with {app} runs once per audited app and adds a row to that app's table;
otherwise it adds a row to the "Project checks" table. Result = exit code plus the summary lines: lines matching the
regex "parse", else (or when none matches) the last non-empty line. Exit 0 = Pass, else "level" (default Deviation;
"note" for Note). {app} is the app id, {path} its folder (apps[].path).

Rules registry: the check commands of the active rules for the review skill (scripts/rules.py check) add one row per
rule and app: a failing must rule = Deviation, should or note = Note.

Each app is audited against its own DS profile (apps[].ds, else ds). Root classes come from the profile's catalog.json
when it exists (the components it lists), else from the components CSS. Files other apps build into this app
(apps[].usedBy of a "page" app) are skipped, and the DS version is read from pages (HTML <meta> and footer label; Vue,
JSX and TSX label text), never from scripts.

DS Vue layer: when ds.json > components.vue is set, vue apps also get the row "DS Vue components": DS Vue components
used (imports from the package folder or an alias of it in vite.config.* / tsconfig.json, also through a local re-export
file, counted by template tags), local .vue files named like a DS Vue component (rebuilt instead of used; App.vue, main,
index and layout shells never count) and imports of shadcn-vue components (@/components/ui/).

Page apps (type "page", built into files of host apps, apps[].usedBy): the DS version and the DS CSS come from the host
apps (the app whose path holds a usedBy file) when the page declares none; the report names the host pages to open for
browser checks ({page} in extraChecks and rule checks). A check whose URL holds {app} is skipped for a page app.
"""
import argparse
import collections
import csv
import hashlib
import io
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, ds_path, t, ds_vue, app_ds, css_load, fill_command, page_hosts, app_pages, url_names_app  # noqa: E402
import rules as RULES  # noqa: E402  (scripts/rules.py)
import kitconf  # noqa: E402

SKIP_DIRS = {"node_modules", "dist", "build", ".vite", ".next", ".nuxt", "coverage", ".git"}
EXT_HTML = {".html", ".htm"}
EXT_CSS = {".css", ".scss"}
EXT_SCRIPT = {".js", ".mjs", ".ts", ".tsx", ".jsx"}
EXT_VUE = {".vue"}
PAGE_EXT = EXT_HTML | EXT_VUE | {".jsx", ".tsx"}

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
RULE = re.compile(r"([^{}\s][^{}]*)\{([^{}]*)\}")   # a selector never starts with whitespace: no quadratic scan of blank runs
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
JS_LOOKUP = re.compile(r"""(?:querySelector(?:All)?|closest|matches)\(\s*['"`]([^'"`]+)['"`]""")
JS_HAS = re.compile(r"""(?:getElementsByClassName|classList\.contains)\(\s*['"`]([\w-]+)['"`]""")
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


def rule_key(sel, body):
    """A CSS rule compared by content: whitespace around punctuation and a trailing semicolon do not count."""
    k = lambda x: re.sub(r"\s*([:;,>+~(){}])\s*", r"\1", norm(x)).rstrip(";")
    return k(sel), k(body)


def local_name(raw):
    """Name of a LOCAL block header: whitespace and comment continuation stars of a multi-line header collapsed."""
    return re.sub(r"\s+", " ", re.sub(r"\n\s*\*(?!/)", "\n", raw)).strip()


def top_n(counter, n=None):
    """Like Counter.most_common, ties sorted by name so every run gives the same output."""
    return sorted(counter.items(), key=lambda x: (-x[1], str(x[0])))[:n]


def vkey(s):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", s or "")
    return tuple(map(int, m.groups())) if m else None


# ---------- configuration ----------

class Ctx:
    """Everything the audit needs from kit.config.json and ds.json."""

    def __init__(self, start=None, app=None):
        cfg = load(start, app=app)
        if cfg["_ds"] is None:
            die("no DS profile: kit.config.json > ds (or apps[].ds of %s) must point at a folder with ds.json." % (app or "the app"))
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
        # a header may span lines (" * " continuation) and hold "*" (".m-*"): the name is read up to the closing */
        self.LOCAL = re.compile(r"/\*\s*%s:\s*(.*?)\*/" % re.escape(loc["marker"]), re.S)
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
        self.generic = set(GENERIC) | set(((self.ds.get("review") or {}).get("genericClasses")) or [])
        # css.load "link": the DS file each app links (css.linkPath, relative to the app folder) is DS CSS as a whole
        self.linked = set()
        for a in cfg.get("apps") or []:
            lp = css_load(cfg, a.get("id"))["linkPath"]
            if lp and a.get("path"):
                self.linked.add((self.root / a["path"] / lp).resolve())

    def apps(self):
        return {a["id"]: a for a in self.cfg["apps"] if a.get("id")}

    def label(self):
        return "%s %s" % (self.ds["label"], self.ds["version"])

    def tr(self, key, **kw):
        return t(self.cfg, "review." + key, **kw)


def globbed(root, patterns):
    """Resolved files matched by glob patterns relative to the project root (** allowed)."""
    out = set()
    for pat in patterns or []:
        out |= {f.resolve() for f in root.glob(pat) if f.is_file()}
    return out


def app_files(ctx, app):
    base = (ctx.root / app["path"]).resolve()
    if not base.exists():
        die("app '%s': path not found: %s" % (app["id"], app["path"]))
    if base.is_file():
        return [base]
    generated = globbed(ctx.root, app.get("generated"))  # build output of the app's own sources: counted once, at the source
    extra = sorted(f for f in globbed(ctx.root, app.get("sources")) if base not in f.parents)
    ds_dir = Path(ctx.cfg["_ds_dir"]).resolve()
    exts = EXT_HTML | EXT_CSS | EXT_SCRIPT | EXT_VUE
    built = build_outputs(ctx.cfg)
    out = []
    for f in sorted(base.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in exts:
            continue
        if f.resolve() in built:
            continue  # build output of another app (apps[].usedBy): audited with that app
        rel = f.relative_to(base).parts
        if any(p in SKIP_DIRS or p.startswith(".") for p in rel[:-1]):
            continue
        if ds_dir in f.resolve().parents:
            continue  # a DS profile copied inside the app is DS, not app
        if f.name.endswith((".min.js", ".min.css")):
            continue
        if f.resolve() in generated:
            continue
        out.append(f)
    exts = EXT_HTML | EXT_CSS | EXT_SCRIPT | EXT_VUE
    return out + [f for f in extra if f.suffix.lower() in exts and f not in generated]


# ---------- DS facts ----------

WRAP = re.compile(r"\.([\w-]+)(?![\w-])(?:[.:\[(][^\s>]*)?(?:\s*(>)\s*|\s+)(button|input|select|textarea|table)\b(?![\w-])")
TAG = re.compile(r"<(/?)([A-Za-z][\w.-]*)((?:[^>\"'{]|\"[^\"]*\"|'[^']*'|\{[^}]*\})*)>")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def build_outputs(cfg):
    """Resolved paths of files that other apps build into an app (apps[].usedBy)."""
    root = Path(cfg["_root"])
    return {(root / u).resolve() for a in cfg.get("apps") or [] for u in (a.get("usedBy") or []) if isinstance(u, str)}


def catalog_roots(ctx):
    """Root classes of the components listed in the profile's catalog.json, or None when it has none."""
    p = Path(ctx.cfg["_ds_dir"]) / (ctx.ds.get("catalog_json") or "catalog.json")
    if not p.is_file():
        return None
    try:
        comps = json.loads(p.read_text(encoding="utf-8")).get("components") or []
    except ValueError:
        return None
    roots = {c["class"] for c in comps if isinstance(c, dict) and c.get("class") and c.get("status") != "deprecated"}
    return roots or None


def class_tokens(attrs):
    cl = re.search(r"""class(?:Name)?=\\?["'{]([^"'}]*)""", attrs)
    return [x.strip("\\`") for x in cl.group(1).split()] if cl else []


def wrapped(txt, pos, wrap):
    """True when an open element around position `pos` carries a DS wrapper class for this control:
    the parent for a child rule (`.w > select`), any ancestor for a descendant rule (`.w select`)."""
    stack = []
    for m in TAG.finditer(txt, 0, pos):
        closing, name, attrs = m.group(1), m.group(2), m.group(3)
        if attrs.rstrip().endswith("/") or name.lower() in VOID:
            continue
        if closing:
            while stack and stack[-1][0] != name:
                stack.pop()
            if stack:
                stack.pop()
        else:
            stack.append((name, attrs))
    for depth, (_, attrs) in enumerate(reversed(stack)):
        for c in class_tokens(attrs):
            if c in wrap and (depth == 0 or not wrap[c]):
                return True
    return False

def ds_facts(ctx, min_rules=3):
    bundle = read(ctx.bundle_path)
    css = strip(bundle)
    defs = {(k, norm(v)) for k, v in ctx.DEF.findall(css)}
    cnt = collections.Counter()
    for m in RULE.finditer(css):
        for c in set(CLASS.findall(m.group(1))):
            cnt[c] += 1
    classes = {c for c, n in cnt.items() if n >= 3 and len(c) > 3 and c not in ctx.generic}
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
    cat = catalog_roots(ctx)
    if cat:  # the catalogue names the components: count those, not every class of the bundle
        roots = cat
    roots -= ctx.generic  # ds.json > review.genericClasses: utility classes, not components
    classes |= roots  # root classes count even when short (btn, tag)
    rules = {(norm(m.group(1)), norm(m.group(2))) for m in RULE.finditer(css)}
    # wrapper classes that style a native control inside them, e.g. `.acme-select > select` (child) or `.acme-x select` (descendant)
    wrappers = collections.defaultdict(dict)
    for m in RULE.finditer(css):
        for sel in m.group(1).split(","):
            for w in WRAP.finditer(sel):
                child = w.group(2) == ">"
                wrappers[w.group(3)][w.group(1)] = wrappers[w.group(3)].get(w.group(1), True) and child
    return {"rules": rules, "wrappers": {t: dict(v) for t, v in wrappers.items()}, "sel": {k for k, _ in rules}, "roots": roots, "mods": {r: mods.get(r, set()) for r in roots},
            "all_classes": set(rootn) | allm | set(cnt), "defs": defs, "names": {k for k, _ in defs},
            "classes": classes, "version": ctx.ds["version"], "roots_from": "catalog.json" if cat else "css"}


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
        if path.name == ctx.bundle_name or path.resolve() in ctx.linked:
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
    n = "(?:%s)" % "|".join(re.escape(x) for x in {ctx.bundle_name} | {Path(p).name for p in ctx.linked})
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
        if f.suffix.lower() not in PAGE_EXT:
            continue  # scripts and styles may name older DS versions (comments, changelogs, copied bundles)
        txt = read(f)
        for m in meta.finditer(txt):
            seen["meta " + m.group(1)] += 1
        # the label counts only as visible text: comments, <script> and <style> often say "since <DS> x.y.z"
        vis = re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", " ", txt, flags=re.S | re.I)
        vis = re.sub(r"<!--.*?-->|/\*.*?\*/|(?<![:\w])//[^\n]*", " ", vis, flags=re.S)
        for m in label.finditer(vis):
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
    # the same rule in a source and in its generated copy (multi apps, other wrappers): count it once
    seen_rules = set()

    def once(m):
        k = rule_key(m.group(1), m.group(2))
        if k in seen_rules:
            return ""
        seen_rules.add(k)
        return m.group(0)
    app_parts = [RULE.sub(once, strip(x)) for x in app_parts]
    ds_css, app_css = strip("\n".join(ds_parts)), "\n".join(app_parts)
    inline = [strip(x) for x in inline]
    res = {"app": app["id"], "name": app.get("name", app["id"]), "files": len(files)}

    # page app: the DS version and the DS CSS live in the host apps that load the built page
    hosts = page_hosts(ctx.cfg, app["id"])
    host_ids = sorted({h for h, _ in hosts if h and h in ctx.apps()})
    host_files = sorted({f for h in host_ids for f in app_files(ctx, ctx.apps()[h])}) if host_ids else []
    if hosts:
        res["host"] = {"apps": host_ids, "files": [u for _, u in hosts], "pages": app_pages(ctx.cfg, app["id"])}

    # 1. version: the <meta> wins when a page has one; labels count for consistency
    seen = declared_versions(ctx, files) or declared_versions(ctx, host_files)
    vs = sorted({vkey(k) for k in seen if vkey(k)})
    metas = sorted({vkey(k) for k in seen if k.startswith("meta ") and vkey(k)})
    cur = (metas or vs or [None])[-1]
    res["version"] = {"ds": lib["version"], "app": ".".join(map(str, cur)) if cur else None, "declared": dict(seen),
                      "behind": bool(cur and vkey(lib["version"]) and cur < vkey(lib["version"])),
                      "inconsistent": len(vs) > 1}

    # 2. embedded tokens against the bundle (a page app without DS CSS of its own: the host apps' DS CSS)
    if host_files and not ctx.DEF.search(ds_css) and not imported:
        htexts = {f: read(f) for f in host_files}
        imported = [str(f.relative_to(ctx.root)) for f, x in htexts.items() if imports_bundle(ctx, x)]
        ds_css = strip("\n".join(d for f, x in htexts.items() for _, d, _ in css_blocks(ctx, f, x)))
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
    # a name cut where a script joins the rest ('var(--acme-gap-' + n + ')') is no token: skipped when a token starts with it
    built = {u for u in used if u.endswith("-") and any(k.startswith(u) for k in defined | lib["names"])}
    res["undefined_tokens"] = sorted(used - defined - lib["names"] - built)

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
            if c in lib["classes"] and not c.startswith(ctx.local_prefix) and c not in ctx.generic:
                over[c] += 1
    same = sorted({norm(m.group(1)) for m in RULE.finditer(app_css) if norm(m.group(1)) in lib["sel"]
                   and not m.group(1).strip().startswith((":root", "html", "body", "@")) and not re.match(r"^[\d.%,\s]+$", m.group(1).strip())})
    res["override"] = {"rules": sum(over.values()), "classes": top_n(over, 10), "same_selector": same}

    # 6b. component use: DS root classes in markup, unknown variants, native controls without a DS or local class
    markup = "\n".join(txt for f, txt in texts.items() if f.suffix.lower() in EXT_HTML | EXT_SCRIPT | EXT_VUE)
    app_defined = set(CLASS.findall(app_css))
    roots, mods, allc = lib["roots"], lib["mods"], lib["all_classes"]
    used_c, unknown = collections.Counter(), collections.Counter()
    # classes scripts look up (querySelector('.x'), closest, matches, getElementsByClassName, classList.contains): hooks of
    # a script (the DS theming panel, a shell), not variants
    hooks = set()
    for f, txt in texts.items():
        if f.suffix.lower() in EXT_SCRIPT | EXT_HTML | EXT_VUE:
            for sel in JS_LOOKUP.findall(txt):
                hooks |= set(CLASS.findall(sel))
            hooks |= set(JS_HAS.findall(txt))
    for attr in re.findall(r"""class(?:Name)?\s*[=:]\s*\\?["'`]([^"'`<>{}$]+)""", markup):
        toks = [x.strip("\\") for x in attr.split()]
        for tk in toks:
            if tk in roots:
                used_c[tk] += 1
                for u in toks:
                    if u != tk and u not in mods[tk] and not u.startswith(ctx.local_prefix) and u not in allc and u not in app_defined \
                            and u not in hooks \
                            and not re.match(r"^[\w-]+:|.*\[", u):
                        unknown[(tk, u)] += 1
    native = {}
    files_markup = [txt for f, txt in texts.items() if f.suffix.lower() in EXT_HTML | EXT_SCRIPT | EXT_VUE]
    for tag, extra in (("button", ""), ("input", r"(?![^>]*type=[\"']?(?:checkbox|radio|hidden|file|range|color))"),
                       ("select", ""), ("textarea", ""), ("table", "")):
        n = {"ds": 0, "local": 0, "none": 0}
        wrap = lib["wrappers"].get(tag, {})
        for txt in files_markup:
            for m in re.finditer(r"<%s\b%s([^>]*)>" % (tag, extra), txt):
                toks = class_tokens(m.group(1))
                if any(x in roots or x in allc for x in toks) or (wrap and wrapped(txt, m.start(), wrap)):
                    n["ds"] += 1
                elif any(x.startswith(ctx.local_prefix) for x in toks):
                    n["local"] += 1
                else:
                    n["none"] += 1
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
    blocks = sorted({local_name(m) for txt in texts.values() for m in ctx.LOCAL.findall(txt)})
    known = {local_name(str(c.get(k))) for c in comps for k in ("block", "name", "title", "id") if c.get(k)}
    known |= {local_name(m) for c in comps if c.get("anchor") for m in ctx.LOCAL.findall(str(c["anchor"]))}  # registry keeps the full comment
    res["local"] = {"registry": str(reg_path.relative_to(ctx.root)), "registry_found": reg_path.is_file(), "total": len(comps),
                    "by_status": dict(collections.Counter(c.get("status") for c in comps)),
                    "pending": [c.get("title") or c.get("name") or c.get("id") for c in comps if c.get("status") == "pending"],
                    "blocks": blocks, "unregistered": [b for b in blocks if b not in known]}
    res["css_lines"] = sum(1 for x in app_css.splitlines() if x.strip())  # non-empty lines; the masked DS region is blank

    # 9. DS Vue component layer (ds.json > components.vue): components rebuilt locally, shadcn-vue used instead
    cv = ds_vue(ctx.cfg)
    if cv and (app.get("stack") or ctx.stack) == "vue":
        names = ds_vue_names(ctx, cv)
        pkg = (ctx.root / cv["package"]).resolve() if (ctx.root / cv.get("package", "")).exists() else None
        rebuilt = sorted(str(f.relative_to(ctx.root)) for f in files if f.suffix == ".vue" and squash(f.stem) in names
                         and squash(f.stem) not in SHELLS and not (pkg and pkg in f.resolve().parents))
        shadcn = sorted(str(f.relative_to(ctx.root)) for f, x in texts.items() if re.search(r"""from\s+['"]@/components/ui/""", x))
        used = ds_vue_usage(ctx, app, texts, pkg, names) if pkg else collections.Counter()
        res["dsvue"] = {"package": cv["package"], "components": len(names), "rebuilt": rebuilt, "shadcn": shadcn, "used": top_n(used)}
    return res


def squash(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


SHELLS = {"app", "main", "index", "root", "layout"}   # root shells of a Vue app, never a rebuilt DS component
NOT_COMPONENTS = {"node_modules", "demo", "demos", "docs", "example", "examples", "stories", "test", "tests", "__tests__", "playground"}
IMPORT = re.compile(r"""\b(import|export)\s+(?:type\s+)?([\w$*{}\s,]+?)\s+from\s+['"]([^'"]+)['"]""")
ALIAS_VITE = re.compile(r"""['"]?([@\w$~][\w$~./-]*)['"]?\s*:\s*(?:(?:new\s+)?[\w.]+\(\s*)*['"]([^'"]+)['"]""")
ALIAS_TS = re.compile(r'"([^"]+?)(?:/\*)?"\s*:\s*\[\s*"([^"]+?)(?:/\*)?"')


def ts_configs(f, seen=None):
    """A tsconfig file and the files it extends (relative "extends", string or list), nearest first."""
    seen = seen if seen is not None else set()
    if f in seen or not f.is_file():
        return []
    seen.add(f)
    out = [f]
    m = re.search(r'"extends"\s*:\s*(\[[^\]]*\]|"[^"]*")', read(f))
    for e in re.findall(r'"([^"]+)"', m.group(1)) if m else []:
        if e.startswith("."):
            p = (f.parent / e).resolve()
            out += ts_configs(p if p.suffix == ".json" else p.with_name(p.name + ".json"), seen)
    return out


def alias_table(base, root):
    """Import aliases an app sees: [(key, wildcard, target path)] from vite.config.* (resolve.alias: key and key/…) and
    tsconfig*.json (compilerOptions.paths, "key" exact or "key/*"), in the app folder and every folder above it up to the
    project root, following relative "extends"; nearest first. tsconfig targets resolve from the file's folder (or its
    baseUrl), vite targets from the config's folder."""
    out, seen, d = [], set(), base
    while True:
        for f in sorted(d.glob("vite.config.*")):
            for k, v in ALIAS_VITE.findall(read(f)):
                if not v.startswith(("http", "node:")):
                    out.append((k, None, (f.parent / v).resolve()))
        for top in sorted(d.glob("tsconfig*.json")):
            for f in ts_configs(top.resolve(), seen):
                txt = read(f)
                bu = re.search(r'"baseUrl"\s*:\s*"([^"]*)"', txt)
                anchor = (f.parent / bu.group(1)).resolve() if bu else f.parent
                pm = re.search(r'"paths"\s*:\s*\{(.*?)\}', txt, re.S)
                for k, v in re.findall(r'"([^"]+)"\s*:\s*\[\s*"([^"]+)"', pm.group(1)) if pm else []:
                    wild = k.endswith("/*")
                    out.append((k[:-2] if wild else k, wild, (anchor / (v[:-2] if v.endswith("/*") else v)).resolve()))
        if d == root or root not in d.parents:
            break
        d = d.parent
    return out


def ds_vue_aliases(base, pkg, root=None):
    """Import specifiers that mean the DS Vue package: the package name, and aliases (alias_table) whose target lies in the
    package folder."""
    out = set()
    pj = pkg / "package.json"
    if pj.is_file():
        try:
            out.add(json.loads(read(pj)).get("name") or "")
        except ValueError:
            pass
    for k, _w, p in alias_table(base, root or base):
        if p == pkg or pkg in p.parents:
            out.add(k)
    return {x for x in out if x}


def ds_vue_usage(ctx, app, texts, pkg, names):
    """{DS Vue component: uses} of an app: names imported from the DS Vue package (directly, or through a local re-export
    file such as src/ds.ts, also one an alias points to outside the app: "@ds-vue" -> ../shared/ds.ts in a tsconfig of a
    parent folder), counted by template tags (<Button>, <button>-cased kebab too); imported but no tag = 1."""
    base = (ctx.root / app["path"]).resolve()
    root = ctx.root.resolve()
    table = alias_table(base, root) if base.is_dir() else []
    names_pkg = ds_vue_aliases(base, pkg, root) if base.is_dir() else set()
    texts = dict(texts)   # re-export files reached through an alias are read too (never counted as use)
    extra = set()

    def file_of(p):
        for c in (p, p.with_name(p.name + ".ts"), p.with_name(p.name + ".js"), p / "index.ts", p / "index.js"):
            if c in texts:
                return c
            if c.is_file() and c.suffix in (".ts", ".js", ".mjs"):
                texts[c] = read(c)
                extra.add(c)
                return c
        return None

    def target(f, spec):
        """Resolved file of a relative or aliased import, the package folder for a DS specifier, else None."""
        for k, wild, p in table:
            if spec == k and wild is not True:
                q = p
            elif spec.startswith(k + "/") and wild is not False:
                q = p / spec[len(k) + 1:]
            else:
                continue
            if q == pkg or pkg in q.parents:
                return pkg
            return file_of(q)
        if spec in names_pkg or any(spec.startswith(a + "/") for a in names_pkg):
            return pkg
        if spec.startswith("."):
            p = (f.parent / spec).resolve()
            if p == pkg or pkg in p.parents:
                return pkg
            return file_of(p)
        return None

    def bindings(clause, spec):
        """[(local name, exported name)] of an import or export clause; a default import is named after the file."""
        out = []
        m = re.search(r"\{([^}]*)\}", clause)
        for part in (m.group(1).split(",") if m else []):
            bits = part.split()
            if not bits or bits[0] == "type":
                bits = bits[1:]
            if bits:
                src = Path(spec).stem if bits[0] == "default" else bits[0]
                out.append((bits[-1], src))
        head = re.sub(r"\{[^}]*\}", "", clause).strip(" ,")
        if head and head != "*" and not head.startswith("*"):
            out.append((head, Path(spec).stem))
        return out

    exports = {}   # re-export file -> {exported name: DS component}
    for _ in range(3):  # a re-export of a re-export (alias files are read on the way)
        for f, txt in list(texts.items()):
            for kind, clause, spec in IMPORT.findall(txt):
                t_ = target(f, spec)
                if kind == "export" and t_ is not None:
                    src = {} if t_ == pkg else exports.get(t_, {})
                    for loc, ex in bindings(clause, spec):
                        comp = ex if t_ == pkg else src.get(ex)
                        if comp and squash(comp) in names:
                            exports.setdefault(f, {})[loc] = comp
    used = collections.Counter()
    for f, txt in texts.items():
        if f in extra:
            continue   # a file outside the app read only to follow its re-exports
        local = {}
        for kind, clause, spec in IMPORT.findall(txt):
            t_ = target(f, spec)
            if kind != "import" or t_ is None:
                continue
            for loc, ex in bindings(clause, spec):
                comp = ex if t_ == pkg else exports.get(t_, {}).get(ex)
                if comp and squash(comp) in names:
                    local[loc] = comp
        tpl = "\n".join(re.findall(r"<template\b.*</template>", txt, re.S)) if f.suffix == ".vue" else ""
        for loc, comp in local.items():
            kebab_ = re.sub(r"(?<!^)([A-Z])", r"-\1", loc).lower()
            n = len(re.findall(r"<(?:%s|%s)(?=[\s/>])" % (re.escape(loc), re.escape(kebab_)), tpl))
            used[comp] += n or (0 if f in exports else 1)
    return collections.Counter({k: v for k, v in used.items() if v})


def ds_vue_names(ctx, cv):
    """Names of the DS Vue components: .vue files in the package folder (not demo, docs or test folders) and the first
    column of the props map."""
    names = set()
    pkg = ctx.root / cv.get("package", "")
    if pkg.is_dir():
        names |= {squash(f.stem) for f in pkg.rglob("*.vue")
                  if not NOT_COMPONENTS & set(f.relative_to(pkg).parts[:-1]) and squash(f.stem) not in SHELLS}
    pm = cv.get("propsMap")  # absolute path resolved by kitconf.ds_vue
    if pm:
        rows = list(csv.reader(io.StringIO(read(Path(pm)))))
        names |= {squash(r[0]) for r in rows[1:] if r and r[0].strip()}
    return {n for n in names if n}


def rule_rows(ctx, apps):
    """Rows from the rules registry: the check commands of active rules for the review skill (rules.py check)."""
    out = []
    for x in RULES.run_checks(ctx.cfg, skill="review"):
        if x["app"] and x["app"] not in apps:
            continue
        lvl = {"pass": "pass", "skipped": "skipped"}.get(x["status"]) or ("deviation" if x["severity"] == "must" else "note")
        out.append({"_app": x["app"], "name": "%s %s: %s" % (ctx.tr("rule"), x["id"], x["title"]), "command": x["command"],
                    "exit": x["exit"] if x["exit"] is not None else "—", "summary": [x["reason"]] if x["status"] == "skipped" else x["summary"],
                    "level": lvl, "rule": x["id"]})
    return out


NOT_RUN = re.compile(r"ECONNREFUSED|ERR_CONNECTION_REFUSED|Connection refused|command not found|No such file or directory|"
                     r"Cannot find module|can't open file", re.I)


def run_extra(ctx, apps):
    """kit.config.json > review.extraChecks: [{name, command, parse?, level?}] -> rows per app id (None = project).
    A check that did not run is Skipped with the reason, never a Note or Deviation: its URL's server is down, it exited
    77 or printed "SKIP: <reason>" (as rule checks), the command was not found (126, 127), or it failed with a connection
    or missing-file error. The same command line runs once (cached)."""
    out, cache, probed, words = collections.defaultdict(list), {}, {}, RULES.skip_words(ctx.cfg)
    for x in (ctx.cfg.get("review") or {}).get("extraChecks") or []:
        cmd = kitconf.fill_server(x.get("command"), ctx.cfg)   # {server}: kit.config.json > server (env KIT_SERVER)
        if not x.get("name") or not cmd:
            continue
        per_app = any(k in cmd for k in ("{app}", "{path}", "{platform}", "{stack}", "{page}"))
        # {page}: one run per page to open (a page app: each host page)
        for aid, pg in [(a, pg) for a in (apps if per_app else [None])
                        for pg in ((app_pages(ctx.cfg, a) or [""]) if a and "{page}" in cmd else [None])]:
            a_ = (ctx.apps().get(aid) or {}) if aid else {}
            vals = {"app": aid or "", "path": a_.get("path") or "", "platform": a_.get("platform") or "",
                    "stack": a_.get("stack") or ctx.cfg.get("stack") or "", "page": pg or ""}
            line = fill_command(cmd, **vals) if aid else cmd
            name = x["name"] + (" (%s)" % pg if pg and len(app_pages(ctx.cfg, aid)) > 1 else "")
            if a_.get("type") == "page" and url_names_app(cmd):
                out[aid].append({"name": name, "command": line, "exit": "—", "level": "skipped",
                                 "summary": ["page app: the URL names the app id, which is no page of the site; use {page} (host pages: %s)"
                                             % ", ".join(app_pages(ctx.cfg, aid))]})
                continue
            srv = RULES.needs_server(line)
            if srv and srv not in probed:
                probed[srv] = RULES.reachable(*srv)
            if srv and not probed[srv]:
                out[aid].append({"name": name, "command": line, "exit": "—", "level": "skipped",
                                 "summary": ["needs a server at %s:%d, not reachable (start it, then run again)" % srv]})
                continue
            if line not in cache:   # the same command line (a project-wide check listed per app) runs once
                try:
                    r = subprocess.run(line, shell=True, cwd=ctx.root, capture_output=True, text=True, timeout=int(x.get("timeout", 900)))
                    cache[line] = (r.returncode, [ln.rstrip() for ln in (r.stdout + "\n" + r.stderr).splitlines() if ln.strip()])
                except subprocess.TimeoutExpired:
                    cache[line] = (124, ["timed out"])
            code, lines = cache[line]
            why = RULES.skip_line(lines, words) if code in (0, RULES.SKIP_EXIT) else None
            if code == RULES.SKIP_EXIT or why:
                out[aid].append({"name": name, "command": line, "exit": code, "level": "skipped",
                                 "summary": [why or "the check exited %d (does not apply)" % RULES.SKIP_EXIT]})
                continue
            if code in (126, 127) or (code and any(NOT_RUN.search(ln) for ln in lines)):   # the command or its target did not run
                hit = next((ln for ln in lines if NOT_RUN.search(ln)), lines[-1] if lines else "")
                out[aid].append({"name": name, "command": line, "exit": code, "level": "skipped",
                                 "summary": ["did not run: " + hit[:200]]})
                continue
            matched = [ln for ln in lines if re.search(x["parse"], ln)] if x.get("parse") else []
            summary = matched[:6] or lines[-1:]  # parse matched nothing: the last line, as documented
            # with parse, a matched line that counts something (a number other than 0) is a finding even at exit 0
            counted = [ln for ln in matched if re.search(r"(?<![\w.])0*[1-9]\d*(?:[.,]\d+)?(?![\w.])", ln)]
            lvl = "pass" if code == 0 and not counted else ("note" if x.get("level") == "note" else "deviation")
            out[aid].append({"name": name, "command": line, "exit": code, "summary": summary, "level": lvl})
    return out


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
    if ctx.stack in ("react", "vue") and ctx.ds.get("tailwind") is not False:  # ds.json > tailwind: false = no Tailwind
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
    dv = r.get("dsvue")
    if dv:
        R.append((tr("row.dsvue"), tr("res.dsvue", n=dv["components"], package=dv["package"], rebuilt=len(dv["rebuilt"]), shadcn=len(dv["shadcn"]),
                                      used=len(dv.get("used") or [])),
                  level(ctx, len(dv["rebuilt"]) + len(dv["shadcn"]), 0)))
    for x in r.get("extra") or []:
        R.append((x["name"], extra_result(ctx, x), tr("level." + x["level"])))
    return R


def extra_result(ctx, x):
    return ctx.tr("res.extra", code=x["exit"], summary=" / ".join(x["summary"]).replace("|", "/")[:300] or "—")


def codes(xs, fmt="`%s`", n=6):
    return ", ".join(fmt % (x if isinstance(x, tuple) else (x,)) for x in xs[:n])


def report(ctx, r):
    tr, L = ctx.tr, []
    h, tk, c, lo, o = r["hard"], r["tokens"], r["components"], r["local"], r["override"]
    L += ["## %s" % r["name"], "", tr("scanned", files=r["files"], lines=r["css_lines"]), "",
          "| %s | %s | %s |" % (tr("col.item"), tr("col.result"), tr("col.level")), "|---|---|---|"]
    L += ["| %s | %s | %s |" % x for x in rows(ctx, r)]
    L += ["", tr("legend"), ""]
    if r.get("host"):
        hs = r["host"]
        L.append("- " + tr("b.page_host", files=codes(hs["files"], n=4), apps=codes(hs["apps"]) or tr("unknown"),
                            pages=codes(hs["pages"], n=4) or tr("unknown")))
    b = lambda key, items, fmt="`%s`": L.append("- " + tr(key, n=len(items), list=codes(items, fmt))) if items else None
    if r["version"]["inconsistent"]:
        L.append("- " + tr("b.versions", list=", ".join("`%s`" % k for k in sorted(r["version"]["declared"]))))
    b("b.missing", tk["missing"])
    b("b.changed", tk["changed"])
    b("b.redefined", r["redefined"])
    b("b.top_hex", h["top_hex"], "`%s` ×%d")
    if ctx.stack in ("react", "vue") and ctx.ds.get("tailwind") is not False:
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
    if r.get("dsvue"):
        b("b.dsvue_used", r["dsvue"].get("used") or [], "`%s` ×%d")
        b("b.dsvue_rebuilt", r["dsvue"]["rebuilt"])
        b("b.dsvue_shadcn", r["dsvue"]["shadcn"])
    b("b.local_pending", lo["pending"], "%s")
    b("b.local_unregistered", lo["unregistered"], "%s")
    if not lo["registry_found"]:
        L.append("- " + tr("b.no_registry", path=lo["registry"]))
    L.append("")
    return "\n".join(L)


def selftest():
    import shutil
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="audit-selftest-"))
    (d / "ds" / "acme" / "dist").mkdir(parents=True)
    (d / "ds" / "acme" / "dist" / "acme.css").write_text(":root{--acme-bg:#fff}.acme-btn{color:red}")
    (d / "ds" / "acme" / "ds.json").write_text(json.dumps({"name": "acme", "version": "1.0.0", "tokens": {"prefix": "--acme-"},
        "css": {"bundle": "dist/acme.css"}, "components": {"vue": {"package": "packages/acme-vue", "propsMap": "packages/props.csv"}}}))
    (d / "packages" / "acme-vue").mkdir(parents=True)
    (d / "packages" / "acme-vue" / "AcmeButton.vue").write_text("<template><button/></template>")
    (d / "packages" / "props.csv").write_text("component,prop\nAcmeDialog,open\n")
    src = d / "apps" / "acme-vue" / "src"
    (src / "components" / "local").mkdir(parents=True)
    (src / "components" / "local" / "AcmeDialog.vue").write_text("<template><div/></template>")
    (src / "App.vue").write_text('<script setup>import { Button } from "@/components/ui/button"</script><template><Button/></template>')
    py = shlex.quote(sys.executable)
    (d / "kit.config.json").write_text(json.dumps({"ds": "ds/acme", "stack": "vue", "apps": [{"id": "acme-vue", "path": "apps/acme-vue"}],
        "review": {"extraChecks": [{"name": "Flags", "command": py + " -c \"print('flags: 3 off'); print('done')\"", "parse": "^flags"},
                                   {"name": "Per app", "command": py + " -c \"import sys; print('bad', sys.argv[1]); sys.exit(2)\" {app}"}]}}))
    ctx = Ctx(d)
    ex = run_extra(ctx, ["acme-vue"])
    assert ex[None][0]["summary"] == ["flags: 3 off"] and ex[None][0]["level"] == "deviation", "a parsed line with a count is a finding"
    assert ex["acme-vue"][0]["exit"] == 2 and ex["acme-vue"][0]["summary"] == ["bad acme-vue"], ex["acme-vue"]
    r = audit_app(ctx, ctx.apps()["acme-vue"], ds_facts(ctx))
    assert r["dsvue"]["rebuilt"] == ["apps/acme-vue/src/components/local/AcmeDialog.vue"], r["dsvue"]
    # parse that matches nothing -> last line; {path}; build outputs of a page app; catalog.json roots; versions from pages
    cfgj = json.loads((d / "kit.config.json").read_text())
    cfgj["review"]["extraChecks"] = [{"name": "P", "command": py + " -c \"print('x'); print('last')\" {path}", "parse": "^nothing"}]
    cfgj["apps"].append({"id": "pg", "path": "src/pg", "stack": "vue", "type": "page", "usedBy": ["apps/acme-vue/src/pg.js"]})
    (d / "kit.config.json").write_text(json.dumps(cfgj))
    (src / "pg.js").write_text("const a = '#123456'; /* acme 0.1.0 */")
    (src / "old.js").write_text("// acme 0.5.0 changelog")
    (d / "ds" / "acme" / "catalog.json").write_text(json.dumps({"components": [{"class": "acme-btn"}, {"class": "acme-old", "status": "deprecated"}]}))
    ctx = Ctx(d)
    ex = run_extra(ctx, ["acme-vue"])
    assert ex["acme-vue"][0]["summary"] == ["last"], ex
    assert not [f for f in app_files(ctx, ctx.apps()["acme-vue"]) if f.name == "pg.js"], "usedBy output skipped"
    lib = ds_facts(ctx)
    assert lib["roots"] == {"acme-btn"} and lib["roots_from"] == "catalog.json", lib["roots"]
    assert not declared_versions(ctx, app_files(ctx, ctx.apps()["acme-vue"])), "no version labels from scripts"
    assert r["dsvue"]["shadcn"] == ["apps/acme-vue/src/App.vue"] and r["dsvue"]["components"] == 2, r["dsvue"]
    # 0.10: version label only as visible text, meta wins; multi-line LOCAL headers; generated copies and identical rules
    # count once; non-empty line count; {platform}; a parsed line with a count is not a Pass; genericClasses; css.load link
    web = d / "apps" / "web"
    (web / "shared").mkdir(parents=True)
    (web / "index.html").write_text('<meta name="ds-version" content="1.0.0"><footer>acme 1.0.0</footer>'
                                    '<script>/* acme 0.5.0 era */ var a = "acme 0.4.0";</script>'
                                    '<style>/* acme 0.3.0 */\n/* LOCAL: Chip list\n * for tags (.x-*) */ .x-chip{color:#123456}\n'
                                    '.acme-btn{border-color:red}</style><link rel="stylesheet" href="ds.css">')
    (web / "_shell.html").write_text("<style>.x-shell{color:#abcdef}</style>")
    (web / "shared" / "shell.css").write_text(".x-shell { color: #abcdef }\n")
    (web / "ds.css").write_text(":root{--acme-bg:#fff}.acme-btn{color:red}")
    cfgj["apps"] = [{"id": "web", "path": "apps/web", "stack": "html", "platform": "desktop", "generated": ["apps/web/shared/**"],
                     "css": {"load": "link", "linkPath": "ds.css"}}]
    cfgj["review"]["extraChecks"] = [{"name": "Plat", "command": py + " -c \"import sys; print('small targets: 0 on', sys.argv[1])\" {platform}",
                                      "parse": "targets"}]
    (d / "kit.config.json").write_text(json.dumps(cfgj))
    dsj = json.loads((d / "ds" / "acme" / "ds.json").read_text())
    dsj["review"] = {"genericClasses": ["acme-btn"]}
    (d / "ds" / "acme" / "ds.json").write_text(json.dumps(dsj))
    ctx = Ctx(d)
    files = app_files(ctx, ctx.apps()["web"])
    assert not [f for f in files if f.name == "shell.css"], "apps[].generated skipped"
    r = audit_app(ctx, ctx.apps()["web"], ds_facts(ctx))
    assert r["version"]["app"] == "1.0.0" and not r["version"]["inconsistent"], r["version"]
    assert r["local"]["blocks"] == ["Chip list for tags (.x-*)"], r["local"]["blocks"]
    assert r["hard"]["hex"] == 2 and r["tokens"]["embedded"] == 1, (r["hard"]["hex"], r["tokens"])
    assert r["override"]["rules"] == 0, "genericClasses are not overrides"
    # 0.12.7 (K-R10): a class a script looks up is a hook, not a variant; a token name a script completes is not undefined
    (web / "hook.js").write_text("el.innerHTML = '<b class=\"acme-btn apr-reset acme-zzz\"></b>';\n"
                                 "document.querySelector('.apr-reset'); el.style.background = 'var(--acme-bg' + '-' + n + ')';\n"
                                 "el.style.color = 'var(--acme-b' + n + ')';\n")
    (d / "ds" / "acme" / "ds.json").write_text(json.dumps(dict(dsj, review={})))
    c2 = Ctx(d)
    r2 = audit_app(c2, c2.apps()["web"], ds_facts(c2))
    assert r2["components"]["unknown_modifiers"] == [("acme-btn.acme-zzz", 1)], r2["components"]["unknown_modifiers"]
    (web / "hook.js").write_text("el.style.background = 'var(--acme-' + n + ')'; el.style.color = 'var(--acme-nope-' + n + ')';\n")
    r2 = audit_app(ctx, ctx.apps()["web"], ds_facts(ctx))
    assert r2["undefined_tokens"] == ["--acme-nope-"], r2["undefined_tokens"]
    (web / "hook.js").unlink()
    (d / "ds" / "acme" / "ds.json").write_text(json.dumps(dsj))
    assert r["css_lines"] == 3, r["css_lines"]
    ex = run_extra(ctx, ["web"])
    assert ex["web"][0]["command"].endswith(" desktop") and ex["web"][0]["level"] == "pass", ex
    # 0.12: page app with a host: DS version and DS CSS from the host, DS Vue use through an alias and a re-export file,
    # App.vue and the package's demo folder are no rebuilt components, {page} = host page, {app} in a URL skipped
    (d / "packages" / "acme-vue" / "demo").mkdir()
    (d / "packages" / "acme-vue" / "demo" / "App.vue").write_text("<template><div/></template>")
    (web / "pg").mkdir()
    (web / "pg" / "index.html").write_text('<script src="pg.js"></script>')
    pg = d / "src" / "pg"
    (pg / "src").mkdir(parents=True)
    (pg / "vite.config.ts").write_text('export default { resolve: { alias: { "@acme-vue": fileURLToPath(new URL("../../packages/acme-vue", import.meta.url)) } } }')
    (pg / "src" / "ds.ts").write_text('export { default as AcmeButton } from "@acme-vue/AcmeButton.vue"\nexport { registerIcons } from "@acme-vue/icons"\n')
    (pg / "src" / "App.vue").write_text('<script setup lang="ts">\nimport { AcmeButton, registerIcons } from "./ds"\n'
                                        'import AcmeDialog from "@acme-vue/AcmeDialog.vue"\n</script>\n'
                                        '<template><AcmeButton/><acme-button></acme-button><AcmeDialog/><AcmeButtonX/></template>')
    cfgj["apps"].append({"id": "pg", "path": "src/pg", "stack": "vue", "type": "page", "usedBy": ["apps/web/pg/pg.js"]})
    cfgj["review"]["extraChecks"] = [{"name": "A11y", "command": py + " -c \"print('ok')\" http://127.0.0.1:9/apps/{app}/"},
                                     {"name": "Page", "command": py + " -c \"print('ok')\" {page}"}]
    (d / "kit.config.json").write_text(json.dumps(cfgj))
    ctx = Ctx(d)
    lib = ds_facts(ctx)
    r = audit_app(ctx, ctx.apps()["pg"], lib)
    assert r["host"] == {"apps": ["web"], "files": ["apps/web/pg/pg.js"], "pages": ["apps/web/pg/"]}, r.get("host")
    assert r["version"]["app"] == "1.0.0" and r["tokens"]["embedded"] == 1, (r["version"], r["tokens"])
    assert r["dsvue"]["rebuilt"] == [] and r["dsvue"]["components"] == 2, r["dsvue"]
    assert r["dsvue"]["used"] == [("AcmeButton", 2), ("AcmeDialog", 1)], r["dsvue"]["used"]
    assert "apps/web/pg/" in report(ctx, r)
    ex = run_extra(ctx, ["pg", "web"])
    assert ex["pg"][0]["level"] == "skipped" and ex["web"][0]["level"] == "skipped", ex
    assert "not reachable" in ex["web"][0]["summary"][0], "a check whose server is down is Skipped, not a Note (K-R1)"
    assert ex["pg"][1]["command"].endswith(" apps/web/pg/") and ex["web"][1]["command"].endswith(" apps/web/"), ex
    # 0.12.7: checks that did not run are Skipped (exit 77, SKIP line, command not found, connection refused); the same
    # command line runs once (K-R1, K-R11)
    cnt = d / "count.txt"
    cfgj["review"]["extraChecks"] = [
        {"name": "Skip77", "command": py + " -c \"import sys; print('nothing to scan'); sys.exit(77)\" {app}"},
        {"name": "SkipLine", "command": py + " -c \"print('SKIP: no pages')\" {app}"},
        {"name": "NoCmd", "command": "no-such-command-kit-selftest {app}"},
        {"name": "Refused", "command": py + " -c \"import sys; print('Error: connect ECONNREFUSED 127.0.0.1:8765'); sys.exit(1)\" {app}"},
        {"name": "Once", "command": py + " -c \"open(%r, 'a').write('x'); print('ok')\"" % str(cnt)},
        {"name": "Once again", "command": py + " -c \"open(%r, 'a').write('x'); print('ok')\"" % str(cnt)},
        {"name": "Srv", "command": py + " -c \"print('ok')\" {server}/apps/{app}/"}]
    cfgj["server"] = "http://127.0.0.1:9/"
    (d / "kit.config.json").write_text(json.dumps(cfgj))
    ctx = Ctx(d)
    ex = run_extra(ctx, ["web"])
    lv = {x["name"]: x["level"] for x in ex["web"]}
    assert lv == {"Skip77": "skipped", "SkipLine": "skipped", "NoCmd": "skipped", "Refused": "skipped", "Srv": "skipped"}, ex
    assert ex["web"][4]["command"].endswith("http://127.0.0.1:9/apps/web/"), "{server} from kit.config.json > server"
    assert ex["web"][1]["summary"] == ["no pages"] and "ECONNREFUSED" in ex["web"][3]["summary"][0], ex
    assert [x["level"] for x in ex[None]] == ["pass", "pass"] and cnt.read_text() == "x", "same command line runs once"
    # 0.12.7: an alias in a tsconfig of a parent folder (through extends) that points to a re-export file outside the app (K-R3)
    ws = d / "ws"
    (ws / "shared").mkdir(parents=True)
    (ws / "app1" / "src").mkdir(parents=True)
    (ws / "tsconfig.base.json").write_text('{"compilerOptions": {"paths": {"@ds": ["./shared/ds.ts"], "@ds/*": ["../packages/acme-vue/*"]}}}')
    (ws / "app1" / "tsconfig.json").write_text('{"extends": "../tsconfig.base.json", "include": ["src/**/*"]}')
    (ws / "shared" / "ds.ts").write_text('export { default as AcmeButton } from "@ds/AcmeButton.vue"\n')
    (ws / "app1" / "src" / "Page.vue").write_text('<script setup lang="ts">import { AcmeButton } from "@ds"</script>'
                                                  '<template><AcmeButton/><AcmeButton/></template>')
    cfgj["apps"].append({"id": "ws1", "path": "ws/app1", "stack": "vue", "type": "page", "usedBy": ["apps/web/pg/ws1.js"]})
    (d / "kit.config.json").write_text(json.dumps(cfgj))
    ctx = Ctx(d)
    r = audit_app(ctx, ctx.apps()["ws1"], ds_facts(ctx))
    assert r["dsvue"]["used"] == [("AcmeButton", 2)], r["dsvue"]
    shutil.rmtree(d, ignore_errors=True)
    print("audit_app.py selftest OK")


def main():
    ap = argparse.ArgumentParser(description="Static DS compliance audit of the apps in kit.config.json (read-only).",
                                 epilog="Run from the project folder (or pass --project). Exit code 1 on error.")
    ap.add_argument("apps", nargs="*", help="app ids from kit.config.json > apps (default: all)")
    ap.add_argument("--json", help="also write raw numbers to this file")
    ap.add_argument("--roots", help="write the DS root classes (JSON list) for audit_components_browser.js")
    ap.add_argument("--min-rules", type=int, default=3, help="rules a class needs in the DS components CSS to count as a root class (default 3)")
    ap.add_argument("--project", help="project folder (default: the current folder)")
    ap.add_argument("--no-extra", action="store_true", help="do not run kit.config.json > review.extraChecks")
    ap.add_argument("--no-rules", action="store_true", help="do not run the check commands of the rules registry")
    if "--selftest" in sys.argv:
        selftest()
        return
    a = ap.parse_args()
    ctx = Ctx(a.project)
    apps = ctx.apps()
    keys = a.apps or list(apps)
    for k in keys:
        if k not in apps:
            die("app '%s' is not declared in kit.config.json > apps (declared: %s)" % (k, ", ".join(apps) or "none"))
    lib = ds_facts(ctx, a.min_rules)
    labels = {}
    for k in keys:
        c_ = load(a.project, app=k)
        if c_.get("_ds"):
            labels.setdefault("%s %s" % (c_["_ds"]["label"], c_["_ds"]["version"]), []).append(k)
    ds_text = ctx.label() if len(labels) <= 1 else "; ".join("%s (%s)" % (lb, ", ".join(ids)) for lb, ids in labels.items())
    out, js = ["# " + ctx.tr("title"), "", ctx.tr("intro", ds=ds_text, bundle=Path(ctx.bundle_path).relative_to(ctx.root) if ctx.root in Path(ctx.bundle_path).parents else ctx.bundle_path, stack=ctx.stack + ("".join(sorted({", %s: %s" % (k, apps[k]["stack"]) for k in keys if apps[k].get("stack") and apps[k]["stack"] != ctx.stack})))), ""], []
    project_stack = ctx.stack
    extra = {} if a.no_extra else run_extra(ctx, keys)
    for x in ([] if a.no_rules else rule_rows(ctx, keys)):
        extra.setdefault(x.pop("_app"), []).append(x)
    per_profile = {ctx.cfg.get("ds"): (ctx, lib)}
    for k in keys:
        prof = app_ds(ctx.cfg, k)  # apps[].ds: the app is audited against its own DS profile
        if prof not in per_profile:
            c = Ctx(a.project, app=k)
            per_profile[prof] = (c, ds_facts(c, a.min_rules))
        actx, alib = per_profile[prof]
        actx.stack = apps[k].get("stack") or project_stack  # apps[].stack overrides the project stack
        r = audit_app(actx, apps[k], alib)
        r["stack"], r["ds"] = actx.stack, actx.label()
        r["extra"] = extra.get(k, [])
        js.append(r)
        out.append(report(actx, r))
    if extra.get(None):
        out += ["## " + ctx.tr("extra.title"), "", "| %s | %s | %s |" % (ctx.tr("col.item"), ctx.tr("col.result"), ctx.tr("col.level")),
                "|---|---|---|"]
        out += ["| %s | %s | %s |" % (x["name"], extra_result(ctx, x), ctx.tr("level." + x["level"])) for x in extra[None]]
        out.append("")
        js.append({"project_checks": extra[None]})
    print("\n".join(out))
    if a.roots:
        Path(a.roots).write_text(json.dumps(sorted(lib["roots"])), encoding="utf-8")
    if a.json:
        Path(a.json).write_text(json.dumps(js, ensure_ascii=False, indent=1, default=list), encoding="utf-8")


if __name__ == "__main__":
    main()
