#!/usr/bin/env python3
"""Machine-readable component catalogue: catalog.json next to catalog.md in the DS profile.

catalog.md stays the human source for classes, variants, states, tokens and components.map. catalog.json adds
what agents need to act safely and keeps the fields people maintain: Figma mapping, status (active, experimental,
deprecated with a replacement), usage rules and accessibility notes. Rebuilding never drops those fields.

Commands:
  catalog.py build                 Parse catalog.md (+ components.map) into catalog.json, keeping maintained fields.
  catalog.py check                 Every class exists in the DS CSS bundle, every token is defined, deprecated
                                   components name an existing replacement, ids are unique. Exit 1 on error.
  catalog.py find <words>          Components and page patterns whose name, class, code names or usage match (for agents).
  catalog.py patterns              Page patterns and templates (master-detail, split layouts, list pages…): the
                                   '## Patterns' section of catalog.md ('### <Name>' with '- Class:', '- Use:') and
                                   ds.json > patterns ([{"name", "classes", "use"}]). Works without catalog.json.
  catalog.py show <id>             Print one component as JSON.
  catalog.py set <id> [--status active|experimental|deprecated] [--replaced-by <id>] [--reason "..."]
                      [--figma-component "Button"] [--figma-key <key>] [--figma-node <node id>]
                      [--use "..."] [--avoid "..."] [--a11y "..."]
  catalog.py scan --app <id>       Count component classes used in an app and list deprecated ones still in use
                                   (catalogue of the app's own DS profile when kit.config.json > apps[].ds is set).

Runs from a project (kit.config.json > ds) or with --ds <profile folder>. Never commits or sends anything.
"""
import argparse
import json
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, app as app_cfg, DS_DEFAULTS, _merge, css_load  # noqa: E402

SCHEMA = "kit-catalog/1"
STATUSES = ("active", "experimental", "deprecated")
MAINTAINED = ("figma", "status", "replacedBy", "reason", "usage", "a11y")
FIELD = re.compile(r"^- (Class|Variants|States|Source|Notes|Structure|Tokens|Use):\s*(.*)$")
PATTERN_SECTIONS = ("patterns", "page patterns", "page templates", "templates")
TICK = re.compile(r"`([^`]+)`")
EXT_SCAN = {".html", ".htm", ".tsx", ".jsx", ".ts", ".js", ".vue", ".css"}


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def profile(a):
    if a.ds:
        d = Path(a.ds).resolve()
        f = d / "ds.json"
        if not f.is_file():
            die("ds.json not found in %s" % d)
        ds = _merge(DS_DEFAULTS, json.loads(f.read_text(encoding="utf-8")))
        return {"_ds": ds, "_ds_dir": str(d), "_root": str(d)}, d
    cfg = load(app=getattr(a, "app", None))  # scan --app: the app's own DS profile (apps[].ds)
    if not cfg["_ds"]:
        die("no DS profile linked (kit.config.json > ds)")
    return cfg, Path(cfg["_ds_dir"])


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def split_top(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            out.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def parse_variants(text, base):
    out = []
    if text.strip() in ("", "—", "-"):
        return out
    for item in split_top(text):
        default = "(default)" in item
        m = TICK.search(item)
        if m and m.group(1).startswith("--"):
            name = m.group(1)[2:]
            out.append({"name": name, "class": (base + m.group(1)) if base else None, "default": default})
        else:
            name = re.sub(r"\(.*?\)", "", item).strip(" `")
            note = re.search(r"\((?!default)(.*?)\)", item)
            v = {"name": name, "class": None, "default": default}
            if note:
                v["note"] = note.group(1)
            out.append(v)
    return out


def parse_map(lines):
    rows = {}
    for ln in lines:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 3 or not cells[0].startswith("`."):
            continue
        cls = cells[0].strip("`").lstrip(".")
        rows[cls] = {"react": cells[1], "vue": cells[2], "kind": cells[3] if len(cells) > 3 else ""}
    return rows


def parse_patterns(md):
    """Page patterns of catalog.md: '### <Name>' entries under a '## Patterns' (or 'Page patterns', 'Templates') heading."""
    out, cur, on = [], None, False
    for ln in md.splitlines():
        if ln.startswith("## "):
            on, cur = ln[3:].strip().lower() in PATTERN_SECTIONS, None
            continue
        if not on:
            continue
        if ln.startswith("### "):
            cur = {"id": slug(ln[4:].strip()), "name": ln[4:].strip(), "classes": [], "use": "", "structure": "", "notes": "",
                   "source": "catalog.md"}
            out.append(cur)
            continue
        m = FIELD.match(ln)
        if cur is not None and m:
            k, v = m.group(1).lower(), m.group(2).strip()
            if k == "class":
                cur["classes"] = [x.lstrip(".") for x in TICK.findall(v) if x.startswith(".")]
            elif k in ("use", "structure", "notes"):
                cur[k] = v
    return out


def ds_patterns(ds):
    """ds.json > patterns: [{"name", "classes" (or "class"), "use", "structure"}], for profiles built by a project script."""
    out = []
    for p in (ds or {}).get("patterns") or []:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        cls = p.get("classes") or ([p["class"]] if p.get("class") else [])
        out.append({"id": slug(p["name"]), "name": p["name"], "classes": [c.lstrip(".") for c in cls], "use": p.get("use", ""),
                    "structure": p.get("structure", ""), "notes": p.get("notes", ""), "source": "ds.json"})
    return out


def all_patterns(ds, md):
    """Patterns of catalog.md, then those of ds.json not already listed (same id)."""
    out = parse_patterns(md)
    ids = {p["id"] for p in out}
    return out + [p for p in ds_patterns(ds) if p["id"] not in ids]


def parse_catalog(md):
    lines = md.splitlines()
    comps, cur, section = [], None, None
    map_lines, in_map = [], False
    for ln in lines:
        if ln.startswith("## "):
            section = ln[3:].strip().lower()
            in_map = section.startswith("components.map")
            cur = None
            continue
        if in_map:
            map_lines.append(ln)
            continue
        if section != "components":
            continue
        if ln.startswith("### "):
            cur = {"name": ln[4:].strip(), "_fields": {}}
            comps.append(cur)
            continue
        m = FIELD.match(ln)
        if cur is not None and m:
            cur["_fields"][m.group(1).lower()] = m.group(2).strip()
    cmap = parse_map(map_lines)
    out = []
    for c in comps:
        f = c["_fields"]
        classes = [x.lstrip(".") for x in TICK.findall(f.get("class", "")) if x.startswith(".")]
        base = classes[0] if classes else None
        states = [] if f.get("states", "—").strip() in ("—", "-", "") else [s.strip() for s in split_top(f["states"])]
        src = (f.get("source") or "").split("(")[0].strip() or "unknown"
        m = cmap.get(base or "", {})
        notes = f.get("notes", "")
        out.append({
            "id": slug(c["name"]), "name": c["name"], "class": base, "classes": classes,
            "variants": parse_variants(f.get("variants", ""), base), "states": states, "source": src,
            "structure": f.get("structure", ""), "notes": notes,
            "tokens": TICK.findall(f.get("tokens", "")),
            "code": {"html": ("." + base) if base else "", "react": m.get("react", ""), "vue": m.get("vue", "")},
            "figma": {"component": "", "key": "", "node": ""},
            "status": "active", "replacedBy": None, "reason": "",
            "usage": {"use": [], "avoid": []},
            "a11y": [s.strip() for s in re.split(r"(?<=\.)\s+", notes) if re.search(r"aria|touch target|label|focus|contrast|keyboard", s, re.I)],
        })
    return out


def cat_path(cfg, d):
    return d / (cfg["_ds"].get("catalog_json") or "catalog.json")


def read_cat(cfg, d):
    p = cat_path(cfg, d)
    if not p.is_file():
        die("%s not found: run build first" % p.name)
    return json.loads(p.read_text(encoding="utf-8"))


def write_cat(cfg, d, data):
    cat_path(cfg, d).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_build(cfg, d, a):
    md = d / (cfg["_ds"].get("catalog") or "catalog.md")
    if not md.is_file():
        die("%s not found in the DS profile" % md.name)
    text = md.read_text(encoding="utf-8")
    comps, pats = parse_catalog(text), all_patterns(cfg["_ds"], text)
    if not comps and not pats:
        die("no components found: catalog.md needs a '## Components' section with '### <Name>' entries and '- Class:' lines")
    old = {}
    p = cat_path(cfg, d)
    if p.is_file():
        old = {c["id"]: c for c in json.loads(p.read_text(encoding="utf-8")).get("components", [])}
    kept = set()
    for c in comps:
        o = old.get(c["id"])
        if o:
            for k in MAINTAINED:
                if k in o and o[k] not in (None, "", [], {}, {"component": "", "key": "", "node": ""}, {"use": [], "avoid": []}) and o[k] != c.get(k):
                    c[k] = o[k]
                    kept.add(c["id"])
    gone = sorted(set(old) - {c["id"] for c in comps})
    ds = cfg["_ds"]
    data = {"$schema": SCHEMA, "ds": ds.get("name") or "", "label": ds.get("label") or "", "version": ds.get("version", ""),
            "prefix": ds["tokens"]["prefix"], "generatedFrom": md.name, "components": comps, "patterns": pats}
    write_cat(cfg, d, data)
    print("Wrote %s: %d components, %d page patterns; maintained fields kept for %d" % (p.name, len(comps), len(pats), len(kept))
          + (" (%s)" % ", ".join(sorted(kept)) if kept else ""))
    if not pats:
        print("NOTE: no page patterns (catalog.md '## Patterns' or ds.json > patterns): define and prototype cannot see "
              "list-detail, split or other page layouts the DS has")
    for g in gone:
        print("WARN: %s was in catalog.json but is no longer in catalog.md (its maintained fields are dropped)" % g)
    missing = [c["id"] for c in comps if not c["class"]]
    if missing:
        print("WARN: no class for: " + ", ".join(missing))


def defined(cfg, d):
    b = cfg["_ds"]["css"]["bundle"]
    if not b or "://" in b:
        return None, None
    p = d / b
    if not p.is_file():
        return None, None
    css = p.read_text(encoding="utf-8")
    return set(re.findall(r"\.(-?[a-zA-Z_][\w-]*)", css)), set(re.findall(r"(--[\w-]+)\s*:", css))


def cmd_check(cfg, d, a):
    data = read_cat(cfg, d)
    errs, warns = [], []
    if data.get("$schema") != SCHEMA:
        errs.append("$schema must be %s" % SCHEMA)
    classes, tokens = defined(cfg, d)
    if classes is None:
        warns.append("CSS bundle not readable: class and token checks skipped")
    ids = [c.get("id") for c in data.get("components", [])]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errs.append("duplicate ids: " + ", ".join(dup))
    for c in data.get("components", []):
        i = c.get("id")
        if c.get("status") not in STATUSES:
            errs.append("%s: status must be one of %s" % (i, ", ".join(STATUSES)))
        if c.get("status") == "deprecated":
            if not c.get("replacedBy"):
                errs.append("%s: deprecated without replacedBy" % i)
            elif c["replacedBy"] not in ids:
                errs.append("%s: replacedBy %s is not a component" % (i, c["replacedBy"]))
            if not c.get("reason"):
                warns.append("%s: deprecated without a reason" % i)
        if classes is not None:
            for cl in c.get("classes") or []:
                if cl not in classes:
                    errs.append("%s: class .%s is not in the DS CSS" % (i, cl))
            for v in c.get("variants") or []:
                if v.get("class") and v["class"] not in classes:
                    errs.append("%s: variant class .%s is not in the DS CSS" % (i, v["class"]))
            for tk in c.get("tokens") or []:
                if tk not in tokens:
                    errs.append("%s: token %s is not defined in the DS CSS" % (i, tk))
        if not (c.get("code") or {}).get("react") and not (c.get("code") or {}).get("vue"):
            warns.append("%s: no React or Vue mapping in components.map" % i)
    for pt in data.get("patterns") or []:
        if classes is not None:
            for cl in pt.get("classes") or []:
                if cl not in classes:
                    errs.append("pattern %s: class .%s is not in the DS CSS" % (pt.get("id"), cl))
    for w in warns:
        print("WARN:", w)
    for e in errs:
        print("ERROR:", e)
    print("Catalog OK (%d components)" % len(ids) if not errs else "%d error(s)" % len(errs))
    sys.exit(1 if errs else 0)


def cmd_find(cfg, d, a):
    words = [w.lower() for w in a.words]
    data = read_cat(cfg, d)
    hits = []
    for c in data["components"]:
        hay = " ".join([c["id"], c["name"], c.get("class") or "", c["code"].get("react", ""), c["code"].get("vue", ""),
                        c.get("structure", ""), " ".join(c["usage"].get("use", []))]).lower()
        score = sum(3 if re.search(r"\b%s(?:s|es)?\b" % re.escape(w), hay) else (1 if re.search(r"\b%s" % re.escape(w), hay) else 0) for w in words)
        if score:
            hits.append((score, c))
    for _, c in sorted(hits, key=lambda x: (-x[0], x[1]["name"])):
        flag = " [DEPRECATED → %s]" % c["replacedBy"] if c["status"] == "deprecated" else (" [experimental]" if c["status"] == "experimental" else "")
        print("%-20s .%-22s react: %-30s%s" % (c["id"], c.get("class") or "-", c["code"].get("react", "")[:30], flag))
    for pt in data.get("patterns") or []:
        hay = " ".join([pt["id"], pt["name"], " ".join(pt.get("classes") or []), pt.get("use", ""), pt.get("structure", "")]).lower()
        if any(re.search(r"\b%s" % re.escape(w), hay) for w in words):
            hits.append((0, pt))
            print("%-20s .%-22s [page pattern] %s" % (pt["id"], (pt.get("classes") or ["-"])[0], pt.get("use", "")[:60]))
    if not hits:
        print("No component or page pattern matches. Not in the DS → prototype component gate.")


def cmd_patterns(cfg, d, a):
    p = cat_path(cfg, d)
    if p.is_file():
        pats = json.loads(p.read_text(encoding="utf-8")).get("patterns")
    else:
        pats = None
    if pats is None:  # no catalog.json, or one built before patterns: read the sources
        md = d / (cfg["_ds"].get("catalog") or "catalog.md")
        pats = all_patterns(cfg["_ds"], md.read_text(encoding="utf-8") if md.is_file() else "")
    for pt in pats:
        print("%-22s %-34s %s" % (pt["id"], " ".join("." + c for c in pt.get("classes") or []) or "-", pt.get("use") or pt.get("structure") or ""))
    if not pats:
        print("No page patterns listed (catalog.md '## Patterns' or ds.json > patterns). Search the DS CSS and library before "
              "calling a page layout missing.")


def cmd_show(cfg, d, a):
    for c in read_cat(cfg, d)["components"]:
        if c["id"] == a.id:
            print(json.dumps(c, ensure_ascii=False, indent=2))
            return
    die("component %s not found" % a.id)


def cmd_set(cfg, d, a):
    data = read_cat(cfg, d)
    ids = [c["id"] for c in data["components"]]
    c = next((x for x in data["components"] if x["id"] == a.id), None)
    if not c:
        die("component %s not found" % a.id)
    if a.status:
        if a.status not in STATUSES:
            die("status must be one of %s" % ", ".join(STATUSES))
        if a.status == "deprecated" and not (a.replaced_by or c.get("replacedBy")):
            die("deprecated needs --replaced-by <id>")
        c["status"] = a.status
        if a.status != "deprecated":
            c["replacedBy"] = None
    if a.replaced_by:
        if a.replaced_by not in ids or a.replaced_by == a.id:
            die("--replaced-by must be another component id")
        c["replacedBy"] = a.replaced_by
    if a.reason:
        c["reason"] = a.reason
    for k, v in (("component", a.figma_component), ("key", a.figma_key), ("node", a.figma_node)):
        if v is not None:
            c["figma"][k] = v
    if a.use:
        c["usage"]["use"].append(a.use)
    if a.avoid:
        c["usage"]["avoid"].append(a.avoid)
    if a.a11y:
        c["a11y"].append(a.a11y)
    write_cat(cfg, d, data)
    print("Updated %s" % a.id)


def is_ds_copy(cfg, app, f):
    ds = cfg.get("_ds") or {}
    b = (ds.get("css") or {}).get("bundle")
    if b and "://" not in b and f.name == Path(b).name:
        return True
    lp = css_load(cfg, app.get("id"))["linkPath"]
    return bool(lp) and f.resolve() == (Path(cfg["_root"]) / app["path"] / lp).resolve()


def strip_ds(cfg, text):
    """Text without the embedded DS CSS: the region between ds.json > css.marker and <style id="<css.styleBlocks>…">."""
    css = ((cfg.get("_ds") or {}).get("css") or {})
    mk = css.get("marker") or {"begin": "@ds:begin", "end": "@ds:end"}
    text = re.sub(r"/\*\s*%s[^*]*\*/.*?/\*\s*%s[^*]*\*/" % (re.escape(mk["begin"]), re.escape(mk["end"])), " ", text, flags=re.S)
    if css.get("styleBlocks"):
        text = re.sub(r"<style[^>]*\bid\s*=\s*[\"']%s[^\"']*[\"'][^>]*>.*?</style>" % re.escape(css["styleBlocks"]), " ", text, flags=re.S | re.I)
    return text


def cmd_scan(cfg, d, a):
    if "apps" not in cfg:
        die("scan needs a project (kit.config.json)")
    app = app_cfg(cfg, a.app)
    data = read_cat(cfg, d)
    base = Path(cfg["_root"]) / app["path"]
    text = ""
    for f in sorted(base.rglob("*")):
        if f.is_file() and f.suffix in EXT_SCAN and not ({"node_modules", "dist", "src/ds"} & set(f.parts)) and "/ds/" not in f.as_posix():
            if is_ds_copy(cfg, app, f):
                continue  # a copy of the DS bundle (same name, or the app's css.linkPath) defines every class: not use
            text += strip_ds(cfg, f.read_text(encoding="utf-8", errors="ignore")) + "\n"
    first = lambda c: (c["code"].get("react") or "").split(" ")[0].strip(",")
    owners = {}
    for c in data["components"]:
        owners.setdefault(first(c), []).append(c["id"])
    used = []
    for c in data["components"]:
        if not c.get("class"):
            continue
        n = len(re.findall(r"(?<![\w-])%s(?![\w-])" % re.escape(c["class"]), text))
        react = first(c)
        sole = len(owners.get(react, [])) == 1 or c["id"] == slug(react)  # shared names go to the same-named component
        if app.get("stack", cfg["stack"]) in ("react", "vue") and react and react[0].isupper() and sole:
            n += len(re.findall(r"<%s[\s/>]" % re.escape(react), text))
        if n:
            used.append((c, n))
    print("%s uses %d of %d catalogue components" % (a.app, len(used), len(data["components"])))
    for c, n in sorted(used, key=lambda x: -x[1]):
        print("  %-20s %4d%s" % (c["id"], n, "  DEPRECATED → %s" % c["replacedBy"] if c["status"] == "deprecated" else ""))
    dep = [c for c, _ in used if c["status"] == "deprecated"]
    if dep:
        print("Deprecated still in use: " + ", ".join("%s (use %s)" % (c["id"], c["replacedBy"]) for c in dep))
        sys.exit(1)


def selftest():
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="catalog-selftest-"))
    (d / "apps" / "w").mkdir(parents=True)
    cfg = {"_root": str(d), "_ds": {"css": {"bundle": "dist/acme.css", "marker": {"begin": "@ds:begin", "end": "@ds:end"}, "styleBlocks": "lib"}},
           "apps": [{"id": "w", "path": "apps/w", "css": {"load": "link", "linkPath": "shared/ds.css"}}]}
    app = cfg["apps"][0]
    assert is_ds_copy(cfg, app, d / "apps" / "w" / "acme.css") and is_ds_copy(cfg, app, d / "apps" / "w" / "shared" / "ds.css")
    assert not is_ds_copy(cfg, app, d / "apps" / "w" / "app.css")
    t = strip_ds(cfg, '<style>/* @ds:begin */.btn{}/* @ds:end */</style><style id="libA">.card{}</style><b class="btn">')
    assert ".btn{}" not in t and ".card{}" not in t and 'class="btn"' in t, t
    md = ("## Components\n\n### Button\n\n- Class: `.btn`\n\n## Patterns\n\n### Master detail\n\n- Class: `.pg-split`, `.pg-side`\n"
          "- Use: list on the left, detail on the right; one pane on compact screens\n\n## components.map\n")
    pats = all_patterns({"patterns": [{"name": "Master detail", "classes": ["x"]}, {"name": "Settings page", "class": ".pg-set"}]}, md)
    assert [p["id"] for p in pats] == ["master-detail", "settings-page"] and pats[0]["classes"] == ["pg-split", "pg-side"], pats
    assert pats[0]["source"] == "catalog.md" and pats[1]["classes"] == ["pg-set"] and "compact" in pats[0]["use"], pats
    assert [c["id"] for c in parse_catalog(md)] == ["button"], "patterns are not components"
    print("catalog.py selftest OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    ap = argparse.ArgumentParser(description="Machine-readable component catalogue (catalog.json).",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--ds", help="DS profile folder (default: kit.config.json > ds)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build"); sub.add_parser("check"); sub.add_parser("patterns")
    p = sub.add_parser("find"); p.add_argument("words", nargs="+")
    p = sub.add_parser("show"); p.add_argument("id")
    p = sub.add_parser("set"); p.add_argument("id")
    p.add_argument("--status"); p.add_argument("--replaced-by"); p.add_argument("--reason")
    p.add_argument("--figma-component"); p.add_argument("--figma-key"); p.add_argument("--figma-node")
    p.add_argument("--use"); p.add_argument("--avoid"); p.add_argument("--a11y")
    p = sub.add_parser("scan"); p.add_argument("--app", required=True)
    a = ap.parse_args()
    cfg, d = profile(a)
    {"build": cmd_build, "check": cmd_check, "find": cmd_find, "show": cmd_show, "set": cmd_set, "scan": cmd_scan, "patterns": cmd_patterns}[a.cmd](cfg, d, a)


if __name__ == "__main__":
    main()
