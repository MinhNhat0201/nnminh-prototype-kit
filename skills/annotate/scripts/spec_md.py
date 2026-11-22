#!/usr/bin/env python3
"""Markdown spec (source of truth) and the HTML viewer generated from it when someone needs one.

  python3 -I spec_md.py check  <spec folder> [--screens <screens.json>]
  python3 -I spec_md.py notes  <spec folder> [--screens <screens.json>] [--baseline <old screens.json>] [--units FR-01,FR-02] [--check]
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
        Without screens/screens.json (a package source folder) and without --screens, the screen, pin and image
        checks are skipped with one NOTE line. A generated "Design notes" block whose pin codes no longer match
        screens.json is an ERROR (run notes).
notes:  write or refresh the generated parts of each spec/<unit>.md from screens.json (and requirements/spec-map.json):
        the screen sections ("### S01 · name", route, how to reach, Figma) and the "Design notes" table, one row per pin.
        Only text between <!-- kit:screens:begin --> / <!-- kit:notes:begin {...} --> and their :end markers is
        rewritten; the notes marker keeps each pin code's stable key (screen | rule | selector), so a new pin renumbers
        the codes without losing the hand-written cells (element, DS component, states, style change). Without markers,
        the block goes under the "Screens" / "Design notes" heading (a hand-written table there is taken over, its rows
        matched by pin code, through --baseline numbering when given). --baseline also fills the style change column.
        Renumbered codes still written outside the markers are listed as WARN. --check writes nothing and exits 1 when
        a file is stale.
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


def screens_file(root, override=None):
    """screens.json to read: --screens, else screens/screens.json of the folder; None when there is none."""
    if override:
        f = Path(override)
        if not f.is_file():
            fail("screens.json not found: " + str(override))
        return f
    f = Path(root) / "screens" / "screens.json"
    return f if f.is_file() else None


def read_folder(root, screens_override=None):
    root = Path(root)
    spec = root / "spec"
    if not (spec / "index.md").exists():
        fail("spec/index.md not found in " + str(root))
    scr = screens_file(root, screens_override)
    screens = {s["id"]: s for s in json.loads(scr.read_text(encoding="utf-8"))} if scr else {}
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
    root, spec, screens, flows, units = read_folder(a.root, getattr(a, "screens", None))
    cfg = config(root)
    err, warn = [], []
    scr_file = screens_file(root, getattr(a, "screens", None))
    has_screens = scr_file is not None
    if not has_screens:   # a package source folder keeps screens.json in the capture folder (K-F13)
        print(f"NOTE: no screens/screens.json in {root} (a package source folder?): screen, pin and image checks skipped. "
              "Pass --screens <capture folder>/screens.json to run them.")
    img_dirs = [scr_file.parent] if has_screens else []
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
            shot = "screens/" in img
            if shot and not has_screens:
                pass
            elif not (p.parent / img).exists() and not (shot and any((d / Path(img).name).exists() for d in img_dirs)):
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
            if has_screens:
                err += stale_notes(p.name, s, screens)
            for pin_s, pin_n in re.findall(r"\|\s*(S\d+[a-z]?)-(\d+)\s*\|", s) if has_screens else []:
                sc = screens.get(pin_s)
                if not sc:
                    err.append(f"{p.name}: pin {pin_s}-{pin_n} points to a screen that is not in screens.json.")
                elif int(pin_n) > len(sc.get("pins", [])):
                    err.append(f"{p.name}: pin {pin_s}-{pin_n} exceeds the pin count of the screen ({len(sc.get('pins', []))}).")
    heads = {t(lang(cfg), "annotate.h.unmatched"), t("en", "annotate.h.unmatched")}
    unmatched = section(index, heads)
    for sid in screens if has_screens else []:
        if sid not in used and not (unmatched and re.search(r"\b%s\b" % re.escape(sid), unmatched)):
            in_flow = any(sid == it[1] for f in flows.get("flows", []) for r in f.get("rows", [])
                          for it in r.get("items", []) if it[0] == "n")
            warn.append(f'Screen {sid} is not used by any unit and not listed under "{t(lang(cfg), 'annotate.h.unmatched')}" in index.md'
                        + (" (it is in the wireflow)" if in_flow else "") + ".")
    for f in flows.get("flows", []):
        for r in f.get("rows", []):
            for it in r.get("items", []):
                if has_screens and it[0] in ("n", "chip") and it[1] not in screens:
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


# ---------------- generated screen sections and design notes (notes) ----------------
MARK = re.compile(r"<!-- kit:(screens|notes):begin(?: (.*?))? -->\n?(.*?)<!-- kit:\1:end -->\n?", re.S)
NOTE_COLS = ("pin", "rule", "element", "component", "token", "states", "styleChange")


def owns(ref, uid):
    """A pin belongs to unit uid when its rule code is uid or uid.<n>."""
    ref = str(ref or "")
    return ref.split(".")[0] == uid or ref.startswith(uid + ".")


def pin_keys(screens):
    """{stable key: pin code} for a screens.json list. Key = screen|rule|selector (a repeat gets #2, #3)."""
    out = {}
    for s in screens:
        for n, p in enumerate(s.get("pins", []), 1):
            k = "%s|%s|%s" % (s["id"], p.get("ref", ""), p.get("sel") or p.get("selector") or "")
            base, i = k, 2
            while k in out:
                k, i = "%s#%d" % (base, i), i + 1
            out[k] = "%s-%d" % (s["id"], n)
    return out


def mark_json(d):
    """Marker payload: JSON with no "--", so the HTML comment cannot end early."""
    return json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("--", "-\\u002d")


def blocks(md):
    """{name: (payload dict, body, match)} of the generated blocks of a file."""
    out = {}
    for m in MARK.finditer(md):
        try:
            payload = json.loads(m.group(2)) if m.group(2) else {}
        except ValueError:
            payload = {}
        out[m.group(1)] = (payload, m.group(3), m)
    return out


def cell(x):
    """One Markdown table cell: one line, escaped pipes (multi-line pin text broke tables)."""
    return re.sub(r"(?<!\\)\|", r"\\|", re.sub(r"\s+", " ", str(x or "")).strip())   # an escaped pipe stays as it is


def table_rows(md):
    """Rows of the first Markdown table in md as lists of cells (header and separator dropped)."""
    rows = []
    for ln in md.split("\n"):
        if not ln.lstrip().startswith("|"):
            if rows:
                break
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", ln.strip().strip("|"))]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def token_cell(cfg, style):
    toks = (style or {}).get("tokens") or {}
    parts = []
    for k in TOKEN_KEYS + ("padding",):
        names = toks.get(k) or []
        if names:
            parts.append("%s %s" % (t(lang(cfg), "annotate.style.p." + k), " / ".join("`%s`" % n for n in names)))
    return "; ".join(parts)


def stale_notes(name, md, screens):
    """ERROR lines when a generated notes block names a pin by a code that screens.json now gives another pin."""
    b = blocks(md).get("notes")
    if not b or not b[0]:
        return []
    now = pin_keys(list(screens.values()))
    bad = ["%s → %s" % (code, now.get(key, "gone")) for code, key in b[0].items() if now.get(key) != code]
    return ["%s: design notes are stale (%s): run spec_md.py notes." % (name, ", ".join(bad))] if bad else []


def section_span(md, titles):
    """(start, end) of the body of the first '## <title>' section, or None."""
    pat = "|".join(re.escape(x) for x in titles)
    m = re.search(r"^##\s+(?:%s)\s*$\n?" % pat, md, re.M)
    if not m:
        return None
    nxt = re.search(r"^##\s", md[m.end():], re.M)
    return m.end(), m.end() + nxt.start() if nxt else len(md)


def put_block(md, name, payload, body, titles, title, before_titles):
    """Replace the block between the markers, or place it under its heading (taking over a hand-written table for
    notes), or add the heading before one of before_titles (else at the end)."""
    head = "<!-- kit:%s:begin%s -->\n" % (name, (" " + mark_json(payload)) if payload else "")
    blk = head + body + "<!-- kit:%s:end -->\n" % name
    b = blocks(md).get(name)
    if b:
        m = b[2]
        return md[:m.start()] + blk + md[m.end():]
    span = section_span(md, titles)
    if span:
        a, z = span
        sec = md[a:z]
        if name == "notes":
            tm = re.search(r"(^[ \t]*\|.*\n?)+", sec, re.M)
            if tm:
                return md[:a] + sec[:tm.start()] + blk + sec[tm.end():] + md[z:]
        sec = sec.rstrip("\n")
        return md[:a] + (sec + "\n\n" if sec.strip() else "\n") + blk + "\n" + md[z:].lstrip("\n")
    add = "## %s\n\n%s\n" % (title, blk)
    nb = section_span(md, before_titles) if before_titles else None
    if nb:
        h = md.rfind("\n##", 0, nb[0]) + 1
        return md[:h] + add + md[h:]
    return md.rstrip("\n") + "\n\n" + add


def screens_body(cfg, ids, screens, old_body):
    """Screen sections of the generated block; lines other than the heading and the route survive a refresh."""
    L = lambda k: t(lang(cfg), "annotate." + k)
    route_l, reach_l = L("line.route"), L("line.reach")
    route_all = {route_l, t("en", "annotate.line.route")}
    old = {}
    for m in re.finditer(r"^###\s+(S\d+[a-z]?)\s+·[^\n]*\n(.*?)(?=^###\s|\Z)", old_body, re.S | re.M):
        old[m.group(1)] = [ln for ln in m.group(2).split("\n") if ln.strip()
                           and not any(ln.startswith(x + ":") for x in route_all)]
    if not ids:
        return L("label.noScreen") + "\n"
    out = []
    for sid in ids:
        s = screens[sid]
        route = s.get("route") or ((s.get("page") or "") + (s.get("search") or "") + (s.get("hash") or ""))
        keep = old.get(sid, [])
        reach_keys = (reach_l + ":", t("en", "annotate.line.reach") + ":")
        if not any(ln.startswith(reach_keys) for ln in keep):
            keep.append("%s: %s" % (reach_l, L("label.needsConfirm")))
        fig = [i for i, ln in enumerate(keep) if ln.startswith("Figma:")]
        if s.get("figma"):
            line = "Figma: [%s](%s)" % (sid, s["figma"])
            if fig:
                keep[fig[0]] = line
            else:
                keep.append(line)
        elif not fig:
            keep.append("Figma: " + L("label.needsConfirm"))
        out.append("### %s · %s\n%s: `%s`\n%s\n" % (sid, s.get("name", ""), route_l, route, "\n".join(keep)))
    return "\n".join(out)


def notes_body(cfg, uid, order, screens, old_body, old_keys, baseline):
    """(table text, {code: key}, [(old code, new code)]) for the pins of unit uid."""
    L = lambda k: t(lang(cfg), "annotate." + k)
    keys = pin_keys([screens[i] for i in order])
    code_key = {v: k for k, v in keys.items()}
    old_rows = {}
    for r in table_rows(old_body):
        if r and old_keys.get(r[0]):
            old_rows[old_keys[r[0]]] = (r[0], r + [""] * (len(NOTE_COLS) - len(r)))
    base_pin = {}
    if baseline is not None:
        for s in baseline:
            for p in s.get("pins", []):
                base_pin[(s["id"], p.get("sel") or p.get("selector"))] = p
    base_ids = {s["id"] for s in baseline or []}
    rows, payload, moved = [], {}, []
    for sid in order:
        for n, p in enumerate(screens[sid].get("pins", []), 1):
            if not owns(p.get("ref"), uid):
                continue
            code = "%s-%d" % (sid, n)
            key = code_key[code]
            payload[code] = key
            oc, o = old_rows.get(key, (None, [""] * len(NOTE_COLS)))
            if oc and oc != code:
                moved.append((oc, code))
            st = p.get("style") or {}
            elem = o[2] or (cell(st.get("text"))[:60] if st.get("text") else "`%s`" % cell(p.get("sel") or ""))
            comp = o[3] or (" ".join("`%s`" % c for c in str(st.get("cls") or "").split()[:3]))
            tok = L("label.needsConfirm") if p.get("found") is False else (token_cell(cfg, st) or o[4])
            if baseline is None:
                ch = o[6]
            elif sid not in base_ids:
                ch = L("style.newScreen")
            elif p.get("found") is False:
                ch = L("label.needsConfirm")
            else:
                ch = "; ".join(style_changes(cfg, sid, p, base_pin.get((sid, p.get("sel") or p.get("selector")))))
            rows.append([code, cell(p.get("ref")), cell(elem), cell(comp), cell(tok), cell(o[5]), cell(ch)])
    head = "| %s |\n|%s\n" % (" | ".join(L("col." + c) for c in NOTE_COLS), "---|" * len(NOTE_COLS))
    return head + "".join("| %s |\n" % " | ".join(r) for r in rows), payload, moved


def notes(a):
    root = Path(a.root)
    _r, spec, screens, _f, units = read_folder(root, a.screens)
    if not screens_file(root, a.screens):
        fail("no screens.json: pass --screens <capture folder>/screens.json (written by capture.js).")
    cfg = config(root) or {"language": "en"}
    order = list(screens)
    baseline = json.loads(Path(a.baseline).read_text(encoding="utf-8")) if a.baseline else None
    smap = root / "requirements" / "spec-map.json"
    mapped = {}
    for e in (json.loads(smap.read_text(encoding="utf-8")) if smap.exists() else []):
        mapped.setdefault(e.get("unit"), []).extend(e.get("screens") or [])
    want = set(a.units.split(",")) if a.units else None
    for u in mapped:
        if (not want or u in want) and not (spec / f"{u}.md").exists():
            print(f"NOTE: spec-map.json names {u} but spec/{u}.md does not exist: write the unit (BA text) first.")
    h_scr = {t(lang(cfg), "annotate.h.screens"), t("en", "annotate.h.screens")}
    h_not = {t(lang(cfg), "annotate.h.designNotes"), t("en", "annotate.h.designNotes")}
    h_dev = {t(lang(cfg), "annotate.h.deviations"), t("en", "annotate.h.deviations")}
    base_keys = {v: k for k, v in pin_keys(baseline).items()} if baseline is not None else None
    cur_keys = {v: k for k, v in pin_keys([screens[i] for i in order]).items()}
    stale, all_moved = [], []
    for p in units:
        uid = p.stem
        if want and uid not in want:
            continue
        md = p.read_text(encoding="utf-8")
        b = blocks(md)
        outside = MARK.sub("", md)
        hand = set(re.findall(r"^###\s+(S\d+[a-z]?)\s+·", outside, re.M))
        ids = [i for i in order if (i in mapped.get(uid, []) or any(owns(x.get("ref"), uid) for x in screens[i].get("pins", [])))]
        gen = [i for i in ids if i not in hand]
        new = md
        if gen or not hand or "screens" in b:   # every screen already has a hand-written section: no block needed
            body = screens_body(cfg, gen, screens, b["screens"][1] if "screens" in b else "") if (gen or not hand) else ""
            new = put_block(md, "screens", None, body, h_scr, t(lang(cfg), "annotate.h.screens"), h_not | h_dev)
        if "notes" in b:
            old_body, old_keys = b["notes"][1], b["notes"][0] or cur_keys
        else:
            span = section_span(md, h_not)
            old_body, old_keys = (md[span[0]:span[1]] if span else ""), (base_keys or cur_keys)
        body, payload, moved = notes_body(cfg, uid, order, screens, old_body, old_keys, baseline)
        new = put_block(new, "notes", payload, body, h_not, t(lang(cfg), "annotate.h.designNotes"), h_dev)
        all_moved += moved
        n = len(payload)
        if new != md:
            stale.append(p.name)
            if not a.check:
                p.write_text(new, encoding="utf-8")
        print("%s %s: screens %s; %d pin(s)%s" % ("STALE" if a.check and new != md else ("wrote" if new != md else "same "),
              p.name, ", ".join(ids) or "-", n, "; renumbered " + ", ".join("%s → %s" % m for m in moved) if moved else ""))
    if all_moved:
        olds = {o for o, _n in all_moved}
        for f in sorted(spec.glob("*.md")):
            text = MARK.sub("", f.read_text(encoding="utf-8"))
            for i, ln in enumerate(text.split("\n"), 1):
                hit = sorted(c for c in olds if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(c), ln))
                if hit:
                    print(f"WARN:  {f.name}: line {i} (outside the generated blocks) mentions {', '.join(hit)}: pin codes changed.")
    if a.check and stale:
        print("ERROR: %d file(s) stale: run spec_md.py notes without --check." % len(stale))
        sys.exit(1)


def selftest():
    old = {"style": {"props": {"color": "rgb(0, 0, 0)", "fontSize": "14px"}, "tokens": {"color": ["--acme-text-main"]}}}
    new = {"style": {"props": {"color": "rgb(1, 1, 1)", "fontSize": "14px", "gap": "8px", "borderWidth": "1px"},
                     "tokens": {"color": ["--acme-text-sub"]}}}
    ch = style_changes({"language": "en"}, "S01", new, old)
    assert len(ch) == 1 and "--acme-text-main → --acme-text-sub" in ch[0] and "var(" not in ch[0] and "None" not in ch[0], ch
    selftest_notes()
    print("spec_md.py selftest OK")


def selftest_notes():
    """notes: generated blocks, stable pin keys over a renumbering, hand cells kept; check without screens/."""
    import contextlib
    import io
    import os
    import tempfile
    from types import SimpleNamespace as NS
    pin = lambda ref, sel, text, tok: {"ref": ref, "sel": sel, "found": True, "leftPct": 1, "topPct": 1,
                                       "style": {"props": {"color": "rgb(0, 0, 0)"}, "tokens": {"color": [tok]}, "cls": "acme-btn", "text": text}}
    scr = [{"id": "S01", "name": "List", "page": "index.html", "hash": "#/", "pins": [
        pin("FR-01.1", "#new", "New\ntask", "--acme-text-main"), pin("FR-01.2", "#save", "Save | now", "--acme-text-sub")]}]
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)   # no project config: English labels
        try:
            r = Path(d)
            (r / "spec").mkdir()
            (r / "screens").mkdir()
            (r / "spec/index.md").write_text('---\npbi: "1"\ntitle: "T"\nversion: "1.0.0"\nds: "Acme DS 0.1.0"\n---\n'
                                             "# T\n| [FR-01](FR-01.md) |\n", encoding="utf-8")
            unit = r / "spec/FR-01.md"
            unit.write_text("# FR-01 · List\nHand text stays.\n\n## Business rules (BA wording, verbatim)\n1. **FR-01.1** Rule.\n\n"
                            "## Deviations from spec\n- None.\n", encoding="utf-8")
            sj = r / "screens/screens.json"
            sj.write_text(json.dumps(scr), encoding="utf-8")
            run = lambda **kw: notes(NS(**{"root": d, "screens": None, "baseline": None, "units": None, "check": False, **kw}))
            with contextlib.redirect_stdout(io.StringIO()):
                run()
            md = unit.read_text(encoding="utf-8")
            assert "Hand text stays." in md and "<!-- kit:screens:begin -->" in md and "### S01 · List" in md, md
            assert "Page · route: `index.html#/`" in md and "How to reach: needs confirmation" in md, md
            assert md.index("## Design notes") < md.index("## Deviations from spec"), md
            assert "| S01-2 | FR-01.2 | Save \\| now |" in md and "New task" in md and "text colour `--acme-text-main`" in md, md
            assert "--acme" not in md.split("kit:notes:begin")[1].split("-->")[0], "marker payload must not hold --"
            # hand edits inside the blocks: a state for FR-01.2 and a how-to-reach line
            md = md.replace("| S01-2 | FR-01.2 | Save \\| now | `acme-btn` | text colour `--acme-text-sub` |  |",
                            "| S01-2 | FR-01.2 | Save \\| now | `acme-btn` | text colour `--acme-text-sub` | Disabled until valid |")
            md = md.replace("How to reach: needs confirmation", 'How to reach: click "New task".') + "\nSee S01-2.\n"
            unit.write_text(md, encoding="utf-8")
            scr[0]["pins"].insert(0, pin("FR-01.0", "#title", "Tasks", "--acme-text-main"))
            sj.write_text(json.dumps(scr), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.suppress(SystemExit):
                check(NS(root=d, screens=None))
            assert "design notes are stale (S01-1 → S01-2, S01-2 → S01-3)" in out.getvalue(), out.getvalue()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                run()
            md = unit.read_text(encoding="utf-8")
            assert "| S01-3 | FR-01.2 | Save \\| now | `acme-btn` | text colour `--acme-text-sub` | Disabled until valid |" in md, md
            assert 'How to reach: click "New task".' in md and md.count("<!-- kit:notes:begin") == 1, md
            assert "renumbered S01-1 → S01-2, S01-2 → S01-3" in out.getvalue() and "mentions S01-2" in out.getvalue(), out.getvalue()
            with contextlib.redirect_stdout(io.StringIO()):
                run(check=True)   # fresh: no exit
            # a package source folder: no screens/ -> one NOTE, no screen errors
            sj.unlink()
            (r / "screens").rmdir()
            unit.write_text(md + "\n![S01](../screens/S01.png)\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.suppress(SystemExit):
                check(NS(root=d, screens=None))
            o = out.getvalue()
            assert o.count("NOTE: no screens/screens.json") == 1 and "ERROR" not in o, o
        finally:
            os.chdir(cwd)


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    ap = argparse.ArgumentParser(description="Markdown spec checker, HTML viewer and style diff for the annotate skill.",
                                 epilog="Commands: check, notes, html, styles. Run '<command> --help' for options.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="validate the spec folder")
    c.add_argument("root", help="folder that holds spec/, screens/, requirements/")
    c.add_argument("--screens", help="screens.json to check against (default <root>/screens/screens.json; without one, "
                   "screen, pin and image checks are skipped)")
    n = sub.add_parser("notes", help="write or refresh the generated screen sections and design notes of spec/<unit>.md")
    n.add_argument("root", help="folder that holds spec/ (and requirements/spec-map.json)")
    n.add_argument("--screens", help="screens.json from capture.js (default <root>/screens/screens.json)")
    n.add_argument("--baseline", help="screens.json of the previous version: fills the style change column")
    n.add_argument("--units", help="only these units, e.g. FR-01,FR-02")
    n.add_argument("--check", action="store_true", help="write nothing; exit 1 when a file is stale")
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
    {"check": check, "notes": notes, "html": render, "styles": styles}[a.cmd](a)


if __name__ == "__main__":
    main()
