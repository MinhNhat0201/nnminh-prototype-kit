#!/usr/bin/env python3
"""Markdown spec (source of truth) and the HTML viewer generated from it when someone needs one.

  python3 -I spec_md.py check  <spec folder>
  python3 -I spec_md.py html   <spec folder> [--out design-spec.html] [--img <capture folder>] [--css <bundle.css>] [--no-ds]
  python3 -I spec_md.py styles <screens.json> --baseline <old screens.json> [--json <out.json>]

Folder layout (see skills/annotate/references/spec-format.md):
  spec/index.md        frontmatter (pbi, title, version, date, ds, prototype), units table, screens table,
                       "Not matched", "Out of scope", "Deviations from spec" (headings in the project language)
  spec/flows.md        wireflow as text, plus a Mermaid diagram for Markdown viewers
  spec/<unit id>.md    one file per spec unit (FR-01.md ...); each screen is a "### S01 · <name>" section
  spec/cross-page.md   multi-page prototypes only   } names from kit.config.json > handoff.specFiles
  spec/archive.md      optional: replaced or dropped units  } (crossPage, archive); handoff.specFiles.legacy lists
                       older names that are still read as special files, not as units
  screens/screens.json written by capture.js: route, steps, pins (with computed style), exits, Figma link
  requirements/flows.json, requirements/spec-map.json

check:  every unit file is listed in index.md; linked files and images exist; every screen in screens.json is used
        by a unit or listed under "Not matched"; every pin code (S01-2) exists in screens.json; every screen in
        flows.json exists in screens.json; every flow demo link (flows.json url) appears in spec/flows.md;
        the DS version in the frontmatter matches ds.json (warning). Older frontmatter keys are read through
        kit.config.json > handoff.specFields (e.g. {"ds": "acmeVersion"}; a bare version becomes the version label), and
        "app: <id>" in the frontmatter compares with that app's DS profile (apps[].ds).
html:   self-contained design-spec.html without JavaScript: wireflow with images and exit rings, unit blocks with
        pinned screenshots. The page chrome uses its own --kit-* variables; the DS bundle (ds.json > css.bundle)
        is embedded in a low-priority cascade layer. Images come from --img (PNG/WebP named by screen id, path
        relative to the HTML file) or screens/ of an older package; without images a screen cell shows its route.
styles: compare pin styles with a baseline capture and print "property: before → after" lines per pin.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import kitconf  # noqa: E402
from kitconf import t  # noqa: E402

E = lambda s: html.escape(str(s), quote=True)


def special(cfg):
    """Stems of the spec files that are not units (index, flows, cross-page, archive and their configured names)."""
    return kitconf.spec_files(cfg)["special"]


def fail(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def config(root):
    """Project config found from the spec folder, then from the current folder; None outside a project."""
    return kitconf.load(root, require=False) or kitconf.load(require=False)


def lang(cfg):
    return (cfg or {}).get("language", "en")


# ---------------- minimal Markdown (enough for the spec templates) ----------------
def md_href(h):
    """Links between .md files become anchors in the merged HTML page."""
    m = re.match(r"^(?:\./)?([\w.-]+)\.md(?:#(.+))?$", h)
    if not m:
        return h
    if m.group(2):
        return "#" + m.group(2)
    return "#" + {"index": "top", "flows": "wireflow"}.get(m.group(1), m.group(1))


def inline(s):
    s = E(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1" loading="lazy">', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: '<a href="%s">%s</a>' % (md_href(m.group(2)), m.group(1)), s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", s)
    return s


ID_RE = r"([A-Z]{1,4}-\d+(?:\.\d+)*[a-z]?|S\d+[a-z]?|WF-\d+)\b"
BLOCK_START = r"(#{1,6}\s|```|\s*\||>|\s*([-*]|\d+[.)])\s)"


def md_to_html(md, shift=0, ids=True):
    lines = md.split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("```"):
            code_lang, buf = ln[3:].strip(), []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            if code_lang != "mermaid":  # the HTML draws the wireflow from flows.json instead
                out.append("<pre><code>%s</code></pre>" % E("\n".join(buf)))
            continue
        m = re.match(r"(#{1,6})\s+(.*)", ln)
        if m:
            n, txt = min(6, len(m.group(1)) + shift), m.group(2).strip()
            idm = re.match(ID_RE, txt) if ids else None
            out.append("<h%d%s>%s</h%d>" % (n, ' id="%s"' % idm.group(1) if idm else "", inline(txt), n))
            i += 1
            continue
        if re.match(r"^\s*(---|\*\*\*)\s*$", ln):
            out.append("<hr>")
            i += 1
            continue
        if ln.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head = rows[0]
            body = [r for r in rows[1:] if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
            out.append('<div class="kit-scroll"><table class="kit-table"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (
                "".join("<th>%s</th>" % inline(c) for c in head),
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in body)))
            continue
        if ln.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i][1:].strip())
                i += 1
            out.append("<blockquote>%s</blockquote>" % md_to_html("\n".join(buf), shift, ids))
            continue
        lm = re.match(r"(\s*)([-*]|\d+[.)])\s+(.*)", ln)
        if lm:
            ordered, items = lm.group(2)[0].isdigit(), []
            while i < len(lines):
                mm = re.match(r"(\s*)([-*]|\d+[.)])\s+(.*)", lines[i])
                if mm and len(mm.group(1)) < 2:
                    items.append([mm.group(3)])
                    i += 1
                elif lines[i].startswith("  ") and lines[i].strip() and items:
                    items[-1].append(lines[i][2:])
                    i += 1
                else:
                    break

            def li(parts):
                first, rest = parts[0], parts[1:]
                idm = re.match(r"\*\*([A-Z]{1,4}-\d+(?:\.\d+)+)\*\*", first)
                return "<li%s>%s%s</li>" % (' id="%s"' % idm.group(1) if idm else "", inline(first),
                                            md_to_html("\n".join(rest), shift, ids) if rest else "")
            tag = "ol" if ordered else "ul"
            out.append("<%s>%s</%s>" % (tag, "".join(li(p) for p in items), tag))
            continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(BLOCK_START, lines[i]):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>%s</p>" % inline(" ".join(buf)))
    return "\n".join(out)


def frontmatter(md):
    m = re.match(r"---\n(.*?)\n---\n", md, re.S)
    if not m:
        return {}, md
    meta = {}
    for ln in m.group(1).split("\n"):
        if ":" in ln:
            k, v = ln.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, md[m.end():]


# ---------------- read the folder ----------------
def natural(p):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p.stem)]


def read_folder(root):
    root = Path(root)
    spec = root / "spec"
    if not (spec / "index.md").exists():
        fail("spec/index.md not found in " + str(root))
    scr = root / "screens" / "screens.json"
    screens = {s["id"]: s for s in json.loads(scr.read_text(encoding="utf-8"))} if scr.exists() else {}
    fl = root / "requirements" / "flows.json"
    flows = json.loads(fl.read_text(encoding="utf-8")) if fl.exists() else {"flows": []}
    units = sorted([p for p in spec.glob("*.md") if p.stem not in special(config(root))], key=natural)
    return root, spec, screens, flows, units


def section(md, titles):
    """Body of the first heading whose text starts with one of titles (any level), or None."""
    pat = "|".join(re.escape(x) for x in titles)
    m = re.search(r"^#+\s*(?:%s).*?(?=\n#+\s|\Z)" % pat, md, re.S | re.M)
    return m.group(0) if m else None


def check(a):
    root, spec, screens, flows, units = read_folder(a.root)
    cfg = config(root)
    err, warn = [], []
    index = (spec / "index.md").read_text(encoding="utf-8")
    meta, _ = frontmatter(index)
    if cfg:  # app: in the frontmatter -> that app's DS profile; handoff.specFields -> older key names
        cfg = kitconf.for_app(cfg, meta.get("app"))
        meta = kitconf.spec_meta(cfg, meta)
    for k in ("pbi", "title", "version", "ds"):
        if not meta.get(k):
            err.append(f'spec/index.md: frontmatter is missing "{k}".')
    if cfg and cfg.get("_ds") and meta.get("ds"):
        cur = kitconf.version_label(cfg)
        if meta["ds"] != cur:
            warn.append(f'spec/index.md states DS "{meta["ds"]}" but the project uses "{cur}". Re-check styles or note the mismatch.')
    used = set()
    for p in [spec / f"{n}.md" for n in sorted(special(cfg))] + units:
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8")
        for img in re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", s):
            if not (p.parent / img).exists():
                err.append(f"{p.relative_to(root)}: image not found: {img}")
            m = re.search(r"([^/]+)\.(webp|png|jpg)$", img)
            if m and p in units:
                used.add(m.group(1))
        for link in re.findall(r"\]\(([^)\s#]+\.md)(?:#[^)]*)?\)", s):
            if not (p.parent / link).exists():
                err.append(f"{p.relative_to(root)}: link to a missing file: {link}")
        if p in units:
            used.update(re.findall(r"^#{3}\s+(S\d+[a-z]?)\s+·", s, re.M))
            if f"({p.name}" not in index and f"{p.name})" not in index:
                err.append(f"spec/index.md does not list {p.name}.")
            for pin_s, pin_n in re.findall(r"\|\s*(S\d+[a-z]?)-(\d+)\s*\|", s):
                sc = screens.get(pin_s)
                if not sc:
                    err.append(f"{p.name}: pin {pin_s}-{pin_n} points to a screen that is not in screens.json.")
                elif int(pin_n) > len(sc.get("pins", [])):
                    err.append(f"{p.name}: pin {pin_s}-{pin_n} exceeds the pin count of the screen ({len(sc.get('pins', []))}).")
    heads = {t(lang(cfg), "annotate.h.unmatched"), t("en", "annotate.h.unmatched")}
    unmatched = section(index, heads)
    for sid in screens:
        if sid not in used and not (unmatched and re.search(r"\b%s\b" % re.escape(sid), unmatched)):
            in_flow = any(sid == it[1] for f in flows.get("flows", []) for r in f.get("rows", [])
                          for it in r.get("items", []) if it[0] == "n")
            warn.append(f'Screen {sid} is not used by any unit and not listed under "{t(lang(cfg), 'annotate.h.unmatched')}" in index.md'
                        + (" (it is in the wireflow)" if in_flow else "") + ".")
    for f in flows.get("flows", []):
        for r in f.get("rows", []):
            for it in r.get("items", []):
                if it[0] in ("n", "chip") and it[1] not in screens:
                    err.append(f"flows.json {f.get('id')}: screen {it[1]} is not in screens.json.")
    if flows.get("flows"):
        if not (spec / "flows.md").exists():
            err.append("requirements/flows.json exists but spec/flows.md (the text wireflow) is missing.")
        else:
            fmd = (spec / "flows.md").read_text(encoding="utf-8")
            for f in flows["flows"]:
                if f.get("url") and f["url"] not in fmd:
                    err.append(f"flows.json {f.get('id')} has demo link {f['url']} but spec/flows.md does not show it.")
            if not any(f.get("url") for f in flows["flows"]):
                warn.append("flows.json has no demo link for any flow (fill flows[].url, see the wireflow skill).")
    for e in err:
        print("ERROR: " + e)
    for w in warn:
        print("WARN:  " + w)
    total = sum(p.stat().st_size for p in spec.glob("*.md"))
    print(f"Markdown spec: {len(units)} units, {len(screens)} screens, {len(flows.get('flows', []))} flows, "
          f"text {total / 1024:.0f} KB" + (f", {len(err)} error(s)" if err else ", OK"))
    sys.exit(1 if err else 0)


# ---------------- HTML viewer ----------------
# Page chrome: own neutral variables, so the viewer works with any DS. Colours here are the viewer's,
# not the prototype's; the prototype itself is only shown as screenshots.
CSS = """
:root{--kit-bg:#ffffff;--kit-fg:#1f2328;--kit-muted:#59636e;--kit-line:#d1d9e0;--kit-surface:#f6f8fa;--kit-accent:#0969da;
--kit-on-accent:#ffffff;--kit-radius:8px;--kit-radius-sm:4px;--kit-gap:24px;--kit-node-w:200px;
--kit-font:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--kit-bg:#0d1117;--kit-fg:#e6edf3;--kit-muted:#9198a1;--kit-line:#3d444d;
--kit-surface:#151b23;--kit-accent:#4493f8;--kit-on-accent:#0d1117}}
body{margin:0;background:var(--kit-bg);color:var(--kit-fg);font-family:var(--kit-font);font-size:14px;line-height:22px}
.kit-page{max-width:1200px;margin:0 auto;padding:var(--kit-gap) 16px}
.kit-page h1,.kit-page h2,.kit-page h3{line-height:1.3}
.kit-page h2{margin-top:40px;padding-top:16px;border-top:1px solid var(--kit-line)}
.kit-page a{color:var(--kit-accent)}
.kit-page code{background:var(--kit-surface);border-radius:var(--kit-radius-sm);padding:0 4px;font-size:.92em}
.kit-page blockquote{margin:0;padding:8px 16px;border-left:4px solid var(--kit-accent);background:var(--kit-surface);border-radius:var(--kit-radius-sm)}
.kit-scroll{overflow-x:auto}.kit-table{width:100%;border-collapse:collapse;margin:8px 0 16px}
.kit-table th,.kit-table td{padding:8px 12px;border-bottom:1px solid var(--kit-line);text-align:left;vertical-align:top;font-size:13px}
.kit-table th{font-weight:600;background:var(--kit-surface)}
.kit-block{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--kit-gap);align-items:start;
padding-block:var(--kit-gap);border-top:1px solid var(--kit-line)}
.kit-text{min-width:0}.kit-text h3{font-size:20px;margin-top:0}.kit-text h4{font-size:15px;margin:20px 0 8px}
.kit-visual{display:flex;flex-direction:column;gap:16px;min-width:0;position:sticky;top:8px}
.kit-shot{margin:0}.kit-frame{position:relative}
.kit-frame img{display:block;width:100%;height:auto;border:1px solid var(--kit-line);border-radius:var(--kit-radius)}
.kit-noimg{display:grid;place-items:center;aspect-ratio:16/11;padding:8px;font-size:12px;text-align:center;
border:1px dashed var(--kit-line);border-radius:var(--kit-radius)}
.kit-shot figcaption{font-size:12px;color:var(--kit-muted);margin-top:4px}
.kit-pin{position:absolute;transform:translate(-50%,-50%);width:22px;height:22px;border-radius:50%;display:grid;place-items:center;
font-size:11px;font-weight:600;background:var(--kit-accent);color:var(--kit-on-accent);box-shadow:0 0 0 2px var(--kit-bg)}
.kit-wf-row{display:flex;flex-wrap:wrap;align-items:center;gap:16px;padding-block:12px}
.kit-wf-label{flex-basis:100%;font-size:13px;font-weight:600;margin:0}
.kit-wf-node{display:block;width:var(--kit-node-w);color:inherit;text-decoration:none}
.kit-wf-title{font-size:12px;margin:6px 0 0}
.kit-wf-out,.kit-wf-chip{border:1px dashed var(--kit-line);border-radius:var(--kit-radius);padding:12px;text-align:center;font-size:12px}
.kit-wf-trigger{position:absolute;transform:translate(-50%,-50%);width:18px;height:18px;border-radius:50%;border:2px solid var(--kit-accent)}
.kit-wf-edge{display:flex;flex-direction:column;align-items:center;gap:2px;max-width:120px;font-size:12px;text-align:center;color:var(--kit-muted)}
.kit-wf-edge::after{content:"\\2192";font-size:20px;color:var(--kit-muted)}.kit-wf-u{border-bottom:1px dashed var(--kit-muted)}
.kit-wf-x{font-size:11px;border:1px dashed var(--kit-muted);border-radius:var(--kit-radius-sm);padding:0 4px}
.kit-foot{margin-top:40px;padding-top:12px;border-top:1px solid var(--kit-line);font-size:12px;color:var(--kit-muted)}
@media (max-width:720px){.kit-block{grid-template-columns:1fr}.kit-visual{position:static}
.kit-wf-row{flex-direction:column;align-items:stretch}.kit-wf-node{width:100%;max-width:var(--kit-node-w)}.kit-wf-edge::after{content:"\\2193"}}
"""


class Viewer:
    def __init__(self, cfg, root, img_dir, out):
        self.cfg, self.root, self.img_dir = cfg, root, img_dir
        self.base = Path(out).resolve().parent

    def tr(self, key, **kw):
        return t(lang(self.cfg), "annotate." + key, **kw)

    def img_of(self, sid):
        """Image path of a screen, relative to the HTML file: --img first, then screens/ of an older package."""
        for d in ([self.img_dir] if self.img_dir else []) + [str(self.root / "screens")]:
            base = Path(d) if Path(d).is_absolute() else self.base / d
            for ext in ("webp", "png", "jpg"):
                f = base / f"{sid}.{ext}"
                if f.exists():
                    try:
                        return f.resolve().relative_to(self.base).as_posix()
                    except ValueError:
                        return f.resolve().as_posix()
        return None

    def frame(self, s, inner):
        img = self.img_of(s["id"])
        if img:
            return '<img src="%s" alt="%s · %s" loading="lazy">%s' % (E(img), E(s["id"]), E(s.get("name", "")), inner)
        route = s.get("route") or ((s.get("page") or "") + (s.get("hash") or ""))
        return '<span class="kit-noimg">%s<br><code>%s</code></span>' % (E(s.get("name", "")), E(route))

    def shot(self, s, unit):
        def mine(p):
            ref = str(p.get("ref", ""))
            return ref.split(".")[0] == unit or ref.startswith(unit + ".")
        pins = "".join('<span class="kit-pin" style="left:%s%%;top:%s%%" title="%s">%d</span>' % (p["leftPct"], p["topPct"], E(p.get("ref", "")), n + 1)
                       for n, p in enumerate(s.get("pins", [])) if p.get("found") and mine(p))
        vp = s.get("viewport", {})
        return '<figure class="kit-shot"><div class="kit-frame">%s</div><figcaption>%s · %s · %s×%s</figcaption></figure>' % (
            self.frame(s, pins if self.img_of(s["id"]) else ""), E(s["id"]), E(s.get("name", "")), vp.get("width", ""), vp.get("height", ""))

    def wireflow(self, flows, screens):
        units, out = flows.get("units", {}), []
        for f in flows.get("flows", []):
            out.append('<h3 id="%s">%s · %s</h3>' % (E(f["id"]), E(f["id"]), E(f.get("name", ""))))
            for r in f.get("rows", []):
                cells = ['<p class="kit-wf-label">%s</p>' % E(r["label"])] if r.get("label") else []
                for it in r.get("items", []):
                    k = it[0]
                    if k == "n":
                        s = screens.get(it[1], {"id": it[1], "name": ""})
                        trig = "".join('<span class="kit-wf-trigger" style="left:%s%%;top:%s%%"></span>' % (x["leftPct"], x["topPct"])
                                       for x in s.get("exits", []) if x.get("found") and x.get("leftPct") is not None)
                        cells.append('<a class="kit-wf-node" href="#%s"><div class="kit-frame">%s</div><p class="kit-wf-title">%s · %s%s</p></a>' % (
                            E(units.get(it[1], it[1])), self.frame(s, trig if self.img_of(it[1]) else ""), E(it[1]), E(s.get("name", "")),
                            (" · " + E(units[it[1]])) if it[1] in units else ""))
                    elif k == "e":
                        flag = it[2] if len(it) > 2 else ""
                        label = E(it[1]) + (" (%s)" % E(self.tr("label.needsConfirm")) if flag == "u" else "")
                        xpage = ' <span class="kit-wf-x">%s</span>' % E(self.tr("label.pageChange")) if flag == "x" else ""
                        cells.append('<span class="kit-wf-edge%s">%s%s</span>' % (" kit-wf-u" if flag == "u" else "", label, xpage))
                    elif k == "chip":
                        cells.append('<a class="kit-wf-chip" href="#%s">%s</a>' % (E(it[1]), E(self.tr("label.backTo", id=it[1]))))
                    elif k == "out":
                        cells.append('<span class="kit-wf-out">%s</span>' % E(it[1]))
                out.append('<div class="kit-wf-row">%s</div>' % "".join(cells))
        if flows.get("offflow"):
            out.append("<p>%s</p>" % E(self.tr("label.offflow", list=", ".join(flows["offflow"]))))
        return "\n".join(out)

    def unit_block(self, p, screens):
        md = p.read_text(encoding="utf-8")
        uid = p.stem
        ids = re.findall(r"!\[[^\]]*\]\(\.\./screens/([^)/]+)\.(?:webp|png|jpg)\)", md) + re.findall(r"^#{3}\s+(S\d+[a-z]?)\s+·", md, re.M)
        body = re.sub(r"!\[[^\]]*\]\([^)]+\)\n?", "", md)
        vis = "".join(self.shot(screens[s], uid) for s in dict.fromkeys(ids) if s in screens) or "<p>%s</p>" % E(self.tr("label.noScreen"))
        body = re.sub(r"^#{2,}\s+[^\n]*\n\s*(?=^#|\Z)", "", body, flags=re.M)  # drop headings left empty by moved images
        return '<section class="kit-block" id="%s"><div class="kit-text">%s</div><div class="kit-visual">%s</div></section>' % (
            E(uid), md_to_html(body, shift=2, ids=False), vis)


def ds_css(cfg, override, skip):
    """DS bundle text, or '' with a warning. A URL bundle becomes an @import."""
    if skip:
        return ""
    src = override
    if not src and cfg and cfg.get("_ds"):
        src = kitconf.ds_path(cfg, cfg["_ds"]["css"].get("bundle"))
    if not src:
        print("WARN:  no DS bundle (ds.json > css.bundle or --css): the viewer uses its own neutral styles only.")
        return ""
    if "://" in src:
        return '@import url("%s") layer(ds);' % src
    f = Path(src)
    if not f.is_file():
        print(f"WARN:  DS bundle not found: {src}. The viewer uses its own neutral styles only.")
        return ""
    # A low-priority layer: the DS fonts and tokens are available, the viewer chrome (unlayered) still wins.
    return "@layer ds{\n%s\n}" % re.sub(r"@charset[^;]*;", "", f.read_text(encoding="utf-8"))


def render(a):
    root, spec, screens, flows, units = read_folder(a.root)
    cfg = config(root)
    out = Path(a.out) if a.out else root / "design-spec.html"
    v = Viewer(cfg, root, a.img, out)
    meta, index = frontmatter((spec / "index.md").read_text(encoding="utf-8"))
    meta = kitconf.spec_meta(cfg, meta) if cfg else meta
    head = index.split("\n## ")[0]
    parts = ['<header id="top">%s</header>' % md_to_html(head)]
    if flows.get("flows"):
        fl = (spec / "flows.md").read_text(encoding="utf-8") if (spec / "flows.md").exists() else ""
        parts.append('<section id="wireflow"><h2>%s</h2>%s<h3>%s</h3>%s</section>' % (
            E(v.tr("html.wireflow")), v.wireflow(flows, screens), E(v.tr("html.textVersion")),
            md_to_html(re.sub(r"^#\s.*\n", "", fl), shift=2, ids=False)))
    cross = spec / kitconf.spec_files(cfg)["crossPage"]
    if cross.exists():
        parts.append('<section id="cross-page">%s</section>' % md_to_html(cross.read_text(encoding="utf-8")))
    parts.append(md_to_html(index[len(head):]))
    parts.append("<h2>%s</h2>" % E(v.tr("html.units")))
    parts += [v.unit_block(p, screens) for p in units]
    parts.append('<p class="kit-foot">%s</p>' % E(v.tr("html.footer", pbi=meta.get("pbi", ""), title=meta.get("title", ""),
                                                        version=meta.get("version", ""), ds=meta.get("ds", ""))))
    doc = ('<!doctype html><html lang="%s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           '<title>%s</title><style>%s</style><style>%s</style></head><body><main class="kit-page">%s</main></body></html>') % (
        E(lang(cfg)), E(meta.get("title") or v.tr("html.title")), ds_css(cfg, a.css, a.no_ds), CSS, "\n".join(parts))
    out.write_text(doc, encoding="utf-8")
    print(f"Wrote {out} ({len(doc) / 1024:.0f} KB, {len(units)} units, {len(screens)} screens); "
          f"images use relative paths ({a.img or 'screens'}), no JavaScript.")


# ---------------- style changes against a baseline ----------------
PROPS = ("color", "backgroundColor", "borderColor", "borderWidth", "borderRadius", "fontSize", "fontWeight",
         "lineHeight", "padding", "gap", "boxShadow", "width", "height")
# Properties whose token list in screens.json describes the whole value (padding tokens describe padding-top only).
TOKEN_KEYS = ("color", "backgroundColor", "borderColor", "borderRadius", "fontSize", "lineHeight", "gap", "boxShadow")


def style_changes(cfg, sid, pin, old):
    """List of 'property: before → after' strings, or one status string."""
    tr = lambda k, **kw: t(lang(cfg), "annotate.style." + k, **kw)
    if old is None:
        return [tr("newPin")]
    if not pin.get("style") or not old.get("style"):
        return [tr("noBaseline")]
    ot, nt = old["style"].get("tokens", {}), pin["style"].get("tokens", {})
    o, n = old["style"]["props"], pin["style"]["props"]

    def val(tok, props, k, raw=False):
        x = props.get(k)
        if k == "backgroundColor" and x in ("rgba(0, 0, 0, 0)", "transparent"):
            return tr("transparent")
        names = [] if raw or k not in TOKEN_KEYS else (tok.get(k) or [])
        return names[0] if names else x   # token name as the spec writes it, never var(--…)

    out = []
    for k in PROPS:
        if o.get(k) == n.get(k) or o.get(k) is None or n.get(k) is None:
            continue  # same value, or one capture did not record the property (older format): nothing to compare
        if k in ("width", "height"):
            try:
                if abs(float(o[k][:-2]) - float(n[k][:-2])) <= 2:  # sub-pixel and rounding noise
                    continue
            except (KeyError, TypeError, ValueError):
                pass
        if k == "borderColor" and n.get("borderWidth") == "0px" and o.get("borderWidth") == "0px":
            continue
        before, after = val(ot, o, k), val(nt, n, k)
        if before == after:  # same token on both sides: the raw value changed under it
            before, after = val(ot, o, k, True), val(nt, n, k, True)
        out.append("%s: %s → %s" % (tr("p." + k), before, after))
    return out or [tr("noChange")]


def styles(a):
    cfg = config(Path(a.screens).resolve().parent)
    cur = json.loads(Path(a.screens).read_text(encoding="utf-8"))
    base = json.loads(Path(a.baseline).read_text(encoding="utf-8"))
    old = {}
    for s in base:
        for p in s.get("pins", []):
            old[(s["id"], p.get("sel") or p.get("selector"))] = p
    old_ids = {s["id"] for s in base}
    rows = []
    for s in cur:
        for n, p in enumerate(s.get("pins", []), 1):
            code = f"{s['id']}-{n}"
            if s["id"] not in old_ids:
                ch = [t(lang(cfg), "annotate.style.newScreen")]
            elif not p.get("found"):
                ch = [t(lang(cfg), "annotate.label.needsConfirm")]
            else:
                ch = style_changes(cfg, s["id"], p, old.get((s["id"], p.get("sel") or p.get("selector"))))
            rows.append({"pin": code, "ref": p.get("ref", ""), "changes": ch})
    print("| %s | %s | %s |\n|---|---|---|" % (t(lang(cfg), "annotate.col.pin"), t(lang(cfg), "annotate.col.rule"),
                                               t(lang(cfg), "annotate.col.styleChange")))
    for r in rows:
        print("| %s | %s | %s |" % (r["pin"], r["ref"], "; ".join(r["changes"]).replace("|", "\\|")))
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def selftest():
    old = {"style": {"props": {"color": "rgb(0, 0, 0)", "fontSize": "14px"}, "tokens": {"color": ["--acme-text-main"]}}}
    new = {"style": {"props": {"color": "rgb(1, 1, 1)", "fontSize": "14px", "gap": "8px", "borderWidth": "1px"},
                     "tokens": {"color": ["--acme-text-sub"]}}}
    ch = style_changes({"language": "en"}, "S01", new, old)
    assert len(ch) == 1 and "--acme-text-main → --acme-text-sub" in ch[0] and "var(" not in ch[0] and "None" not in ch[0], ch
    print("spec_md.py selftest OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    ap = argparse.ArgumentParser(description="Markdown spec checker, HTML viewer and style diff for the annotate skill.",
                                 epilog="Commands: check, html, styles. Run '<command> --help' for options.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="validate the spec folder")
    c.add_argument("root", help="folder that holds spec/, screens/, requirements/")
    h = sub.add_parser("html", help="generate the self-contained HTML viewer")
    h.add_argument("root")
    h.add_argument("--out", help="output file (default <root>/design-spec.html)")
    h.add_argument("--img", help="capture folder with <screen id>.png/.webp, relative to the HTML file or absolute")
    h.add_argument("--css", "--lib", dest="css", help="DS CSS bundle to embed (default ds.json > css.bundle)")
    h.add_argument("--no-ds", action="store_true", help="do not embed the DS bundle")
    s = sub.add_parser("styles", help="pin style changes against a baseline capture")
    s.add_argument("screens", help="current screens.json")
    s.add_argument("--baseline", required=True, help="screens.json of the previous version")
    s.add_argument("--json", help="also write the rows to this JSON file")
    a = ap.parse_args()
    {"check": check, "html": render, "styles": styles}[a.cmd](a)


if __name__ == "__main__":
    main()
