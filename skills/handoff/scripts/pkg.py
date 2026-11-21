#!/usr/bin/env python3
"""Handoff package pipeline: one command per step, shared by every work item.

Commands:

  pkg.py init     --pbi 1234 --title "Scheduled tasks" --version 1.0.0 --app acme-web [--dir <source folder>]
      Create the package source folder (default: <handoff.dir>/<pbi>/) with pkg.json and header-only
      requirements/checklist-feature.csv and checklist-qc.csv (UTF-8 with BOM, headers in the project language).

  pkg.py name     --config pkg.json
      Print the package folder and zip name from kit.config.json > handoff.zipName.

  pkg.py layer    --config pkg.json --kind lock|hide (--into page.html ... | --out <file>)
      Render the scope layer from pkg.json > lock or > hide and inject it into each page (idempotent), or write it
      to one file. lock = option (b): capture-phase listener + DS toast, nothing is disabled.
      hide = option (c): display:none CSS block + guard script (shortcuts, hashes of dropped pages, defaults).

  pkg.py capture  --manifest manifest.js --shots shots --base http://localhost:8791/ [--only S01,S02]
      Run capture.js of the annotate skill (2x screenshots), keep the previous run in <shots>.prev, compare pixels
      and write <shots>/changed.json (new screens, changed screens). Only these need a visual check and a Figma update.
      --only captures just those screens (and runs the earlier screens of their flow that set up the state).

  pkg.py finalize --pkg "<package folder>" --shots shots --config pkg.json [--zip [<zip path>]] [--allow-missing-figma]
      Finish the package after spec/*.md, requirements/ and README.md are written:
      1. screens/screens.json, slim: route, how to reach (text and runnable steps), pins, exits, Figma link.
      2. Remove screen images: delete screens/*.webp|png, replace image lines in spec/*.md with "Figma: ...".
      3. Move replaced or removed units to spec/archive.md and fix links.
      4. Keep only pkg.json > changelog_keep versions (default 2) in requirements/changelog.md.
      5. Write AGENTS.md: reading path per role (BA, QC, Dev, wireflow), code conventions, grep labels.
      6. Checks: DS label against the <meta> of the package pages and spec/index.md (handoff.dsLabelCheck);
         every file reference (spec/..., screens/..., requirements/..., prototype/...) in README, AGENTS, spec and
         changelog points to a file in the package; CSV headers match handoff.csv; spec_md.py check (annotate skill),
         printing every WARN and ERROR line.
      7. With --zip, optimise and zip with optimize_package.py.
         --zip without a value writes "<handoff.zipName>.zip" next to the package folder.
      kit.config.json > handoff.pre / handoff.post: project commands run before step 1 and after step 7
      ({pkg}, {config}, {zip}, {root} are replaced, shell-quoted). A failing command stops with ERROR.

  pkg.py --selftest
      Run the built-in checks of the pure functions (no browser, no network).

pkg.json (one per work item, kept in <handoff.dir>/<pbi>/):
  {"pbi": "1234", "title": "Scheduled tasks", "version": "1.0.0", "app": "acme-web", "mode": "feature",
   "treatment": "lock", "prototype": "prototype", "figma_file": "<file link>", "figma_board": "<node id>",
   "figma": {"S01": "<node id>"}, "codes": "...", "archive": [], "changelog_keep": 2, "agents_note": "",
   "ds_label": "<DS label of the packaged prototype, e.g. Acme DS 1.4.0; empty = see handoff.dsLabel>",
   "lock": {...}, "hide": {...}}
Generated text comes from locales/<language>/handoff.json. Messages on the console are English.
"""
import argparse, json, os, re, shlex, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, t, version_label, spec_files, csv_header  # noqa: E402

ANNOTATE = KIT / "skills" / "annotate" / "scripts"
CAPTURE = ANNOTATE / "capture.js"
SPEC_MD = ANNOTATE / "spec_md.py"
OPTIMIZE = HERE / "optimize_package.py"
ASSETS = HERE.parent / "assets"
SCREEN = r"S\d+[a-z]?"
VER_RX = re.compile(r"\b\d+\.\d+\.\d+\b")


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def read_json(p):
    p = Path(p)
    if not p.is_file():
        die(f"file not found: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        die(f"{p} is not valid JSON: {e}")


def pkg_name(cfg, pc):
    return cfg["handoff"]["zipName"].format_map(_Safe(pbi=pc.get("pbi", ""), title=pc.get("title", ""),
                                                      version=pc.get("version", "")))


class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def spec_meta(pkg):
    """Frontmatter of spec/index.md as a dict ({} when missing)."""
    p = Path(pkg) / "spec" / "index.md" if pkg else None
    if not p or not p.is_file():
        return {}
    m = re.match(r"---\n(.*?)\n---\n", p.read_text(encoding="utf-8"), re.S)
    out = {}
    for ln in (m.group(1).split("\n") if m else []):
        if ":" in ln:
            k, v = ln.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def page_versions(cfg, pkg):
    """{version: [pages]} read from <meta name="<ds.json version_label.meta>"> of the HTML pages in the package."""
    ds = cfg.get("_ds") or {}
    name = ((ds.get("version_label") or {}).get("meta")) or "ds-version"
    rx = re.compile(r'<meta\s+name="%s"\s+content="([^"]*)"' % re.escape(name))
    out = {}
    for f in sorted(Path(pkg).rglob("*.html")) if pkg else []:
        if f.name == "design-spec.html":
            continue
        for v in rx.findall(f.read_text(encoding="utf-8", errors="replace")):
            m = VER_RX.search(v)
            out.setdefault(m.group(0) if m else v, []).append(f.relative_to(pkg).as_posix())
    return out


def label_from_version(cfg, version):
    ds = cfg.get("_ds") or {}
    if not ds or not version:
        return ""
    return ds["version_label"]["text"].format(label=ds["label"], version=version, name=ds.get("name"))


def ds_label(cfg, pc, pkg=None):
    """(label, source) of the DS version the package states. handoff.dsLabel picks the source:
    auto = pkg.json > ds_label, then spec/index.md frontmatter "ds", then ds.json; or pkg, spec, ds, prototype."""
    src = cfg["handoff"].get("dsLabel") or "auto"
    found = {"pkg": lambda: pc.get("ds_label") or "",
             "spec": lambda: spec_meta(pkg).get("ds", ""),
             "ds": lambda: version_label(cfg) if cfg.get("_ds") else "",
             "prototype": lambda: label_from_version(cfg, next(iter(page_versions(cfg, pkg)), "") if pkg else "")}
    for k in (("pkg", "spec", "ds") if src == "auto" else (src,)):
        v = found[k]()
        if v:
            return v, k
    return "", ""


def ds_label_issues(cfg, pc, pkg, label):
    """Messages when the label disagrees with the pages' version meta or with spec/index.md."""
    out, lv = [], VER_RX.search(label or "")
    pages = page_versions(cfg, pkg)
    if lv and pages:
        other = {v: p for v, p in pages.items() if v != lv.group(0)}
        for v, p in other.items():
            out.append("DS label \"%s\" but %d page(s) state version %s (%s)" % (label, len(p), v, ", ".join(p[:3])))
    sv = spec_meta(pkg).get("ds", "")
    if sv and label and sv != label:
        out.append("DS label \"%s\" but spec/index.md states ds: \"%s\"" % (label, sv))
    return out


def run_hook(cfg, key, **kw):
    """Run kit.config.json > handoff.<key> (pre or post) in the project root; stop on failure."""
    cmd = cfg["handoff"].get(key)
    if not cmd:
        return
    vals = {k: shlex.quote(str(v)) for k, v in dict(kw, root=cfg["_root"]).items()}
    line = cmd.format_map(_Safe(vals)) if isinstance(cmd, str) else " ".join(shlex.quote(str(x).format_map(_Safe(kw))) for x in cmd)
    print(f"handoff.{key}: {line}")
    env = dict(os.environ, **{"KIT_" + k.upper(): str(v) for k, v in kw.items()})
    r = subprocess.run(line, shell=True, cwd=cfg["_root"], capture_output=True, text=True, env=env)
    for ln in (r.stdout + r.stderr).strip().splitlines()[-40:]:
        print("  " + ln)
    if r.returncode:
        die(f"handoff.{key} failed (exit {r.returncode})")


# ---------------- init / name ----------------
def cmd_init(a):
    cfg = load()
    d = Path(a.dir) if a.dir else Path(cfg["_root"]) / cfg["handoff"]["dir"] / a.pbi
    if (d / "pkg.json").exists() and not a.force:
        die(f"{d / 'pkg.json'} already exists (use --force to overwrite)")
    pc = {"pbi": a.pbi, "title": a.title, "version": a.version, "app": a.app, "mode": a.mode,
          "treatment": a.treatment, "prototype": a.prototype, "ds_label": "", "figma_file": "", "figma_board": "", "figma": {},
          "codes": "", "archive": [], "changelog_keep": 2, "agents_note": ""}
    if a.treatment == "lock":
        pc["lock"] = {"pages": [], "page_keys": {}, "allow": [], "allow_when": [], "block": [], "nav_functions": [],
                      "shortcuts": [], "open_allow": "", "seed": {},
                      "toast": {"function": "", "args": [], "container": "", "class": "", "close_class": "", "icon": "",
                                "close_html": "", "ms": 5000}}
    if a.treatment == "hide":
        pc["hide"] = {"selectors": [], "shortcuts": [], "dropped_hashes": [], "entry": "", "defaults": [], "seed": {}}
    d.mkdir(parents=True, exist_ok=True)
    (d / "pkg.json").write_text(json.dumps(pc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    req = d / "requirements"
    req.mkdir(exist_ok=True)
    for kind, f in (("feature", "checklist-feature.csv"), ("qc", "checklist-qc.csv")):
        if not (req / f).exists():
            (req / f).write_text(csv_header(cfg, kind)[0] + "\n", encoding="utf-8-sig")
    print(f"Created {d / 'pkg.json'} and CSV headers in {req}")
    print(f"Package name: {pkg_name(cfg, pc)}")


def cmd_name(a):
    cfg, pc = load(), read_json(a.config)
    n = pkg_name(cfg, pc)
    print(json.dumps({"folder": n, "zip": n + ".zip"}, ensure_ascii=False))


# ---------------- layer ----------------
LOCK_ID, HIDE_ID, HIDE_CSS_ID = "x-handover-lock", "x-handover-hide-js", "x-handover-hide"


def layer_name(cfg, pc):
    item = cfg["handoff"].get("itemLabel") or ""
    return f"{item}{pc.get('pbi', '')} · {pc.get('title', '')} v{pc.get('version', '')}".strip()


def js_json(x):
    return json.dumps(x, ensure_ascii=False).replace("</", "<\\/")


def render_layer(cfg, pc, kind):
    name = layer_name(cfg, pc)
    if kind == "lock":
        L = pc.get("lock")
        if not L or not L.get("allow"):
            die("pkg.json > lock.allow is empty: list the selectors of the feature (and the menus, dialogs, toasts it uses)")
        for i, w in enumerate(L.get("allow_when") or []):
            if not isinstance(w, dict) or not w.get("sel") or not (w.get("hash") or w.get("path")):
                die(f"pkg.json > lock.allow_when[{i}] needs sel and hash or path (regex), e.g. "
                    '{"sel": "#more", "hash": "^#/tasks/"}')
        pk = L.get("page_keys") or {}
        missing = [k for k, f in pk.items() if L.get("pages") and f not in L["pages"]]
        if missing:
            print("NOTE pkg.json > lock.page_keys point to files not in lock.pages (blocked): " + ", ".join(missing))
        ds_toast = (cfg.get("_ds") or {}).get("toast") or {}  # the DS profile may declare its toast pattern
        toast = {"function": "", "args": [], "container": "", "class": "", "close_class": "", "icon": "", "close_html": "",
                 "ms": 5000}
        toast.update({k: v for k, v in ds_toast.items() if k in toast and v})
        toast.update({k: v for k, v in (L.get("toast") or {}).items() if v not in ("", None, [])})
        conf = {"name": name, "msg": t(cfg, "handoff.lock.toast", name=name), "close": t(cfg, "handoff.lock.close"),
                "pages": L.get("pages", []), "pageKeys": pk, "allow": L["allow"], "allowWhen": L.get("allow_when", []),
                "block": L.get("block", []), "navFunctions": L.get("nav_functions", []), "shortcuts": L.get("shortcuts", []),
                "openAllow": L.get("open_allow", ""), "seed": L.get("seed", {}), "toast": toast}
        if not toast.get("function") and not toast.get("class"):
            die("pkg.json > lock.toast needs 'function' (the app's toast function) or 'class' (the DS toast classes "
                "from catalog.md, or ds.json > toast): the out-of-scope notice must be a DS toast")
        js = (ASSETS / "scope-lock.js").read_text(encoding="utf-8").replace("/*@CONFIG@*/{}", js_json(conf))
        return {"script": f'<script id="{LOCK_ID}">\n{js}</script>', "style": "", "meta": t(cfg, "handoff.layer.lock", name=name)}
    H = pc.get("hide")
    if not H or not H.get("selectors"):
        die("pkg.json > hide.selectors is empty: list stable selectors (data-*, id, aria-label) of what to hide")
    css = ",\n".join(H["selectors"]) + "{display:none !important}"
    conf = {"shortcuts": H.get("shortcuts", []), "droppedHashes": H.get("dropped_hashes", []),
            "entry": H.get("entry", ""), "defaults": H.get("defaults", []), "seed": H.get("seed", {})}
    js = (ASSETS / "scope-hide.js").read_text(encoding="utf-8").replace("/*@CONFIG@*/{}", js_json(conf))
    return {"script": f'<script id="{HIDE_ID}">\n{js}</script>',
            "style": f'<style id="{HIDE_CSS_ID}">\n/* Handoff scope: hidden on purpose (see spec, "Out of scope") */\n{css}\n</style>',
            "meta": t(cfg, "handoff.layer.hide", name=name)}


def inject(html, layer):
    for tag, i in (("script", LOCK_ID), ("script", HIDE_ID), ("style", HIDE_CSS_ID)):
        html = re.sub(r'\n?<%s id="%s">.*?</%s>' % (tag, i, tag), "", html, flags=re.S)
    html = re.sub(r'\n?<meta name="x-handover"[^>]*>', "", html)
    meta = '<meta name="x-handover" content="%s">' % layer["meta"].replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    head = meta + ("\n" + layer["style"] if layer["style"] else "")
    if re.search(r"</head>", html, re.I):
        html = re.sub(r"</head>", head + "\n</head>", html, count=1, flags=re.I)
    else:
        html = head + "\n" + html
    if re.search(r"</body>", html, re.I):
        idx = [m.start() for m in re.finditer(r"</body>", html, re.I)][-1]
        html = html[:idx] + layer["script"] + "\n" + html[idx:]
    else:
        html += "\n" + layer["script"] + "\n"
    return html


def cmd_layer(a):
    cfg, pc = load(), read_json(a.config)
    if pc.get("lock") and pc.get("hide") and (pc["lock"].get("allow") and pc["hide"].get("selectors")):
        die("pkg.json has both lock and hide: one package uses one treatment, never both")
    layer = render_layer(cfg, pc, a.kind)
    if a.out:
        body = (layer["style"] + "\n" if layer["style"] else "") + layer["script"] + "\n"
        Path(a.out).write_text(body, encoding="utf-8")
        print(f"Wrote {a.out}")
        return
    if not a.into:
        die("give --into <page.html> ... or --out <file>")
    for p in a.into:
        p = Path(p)
        if not p.is_file():
            die(f"page not found: {p}")
        p.write_text(inject(p.read_text(encoding="utf-8"), layer), encoding="utf-8")
    print(f"{a.kind} layer injected into {len(a.into)} page(s)")


# ---------------- capture ----------------
def diff_ratio(a, b):
    from PIL import Image, ImageChops
    A, B = Image.open(a).convert("L"), Image.open(b).convert("L")
    if A.size != B.size:
        return 1.0
    d = ImageChops.difference(A, B).point(lambda v: 255 if v > 24 else 0)
    return sum(d.histogram()[255:]) / (A.size[0] * A.size[1])


def cmd_capture(a):
    if not CAPTURE.is_file():
        die(f"capture.js not found at {CAPTURE} (it ships with the annotate skill)")
    shots, prev = Path(a.shots), Path(a.shots + ".prev")
    if shots.exists() and not a.only:
        if prev.exists():
            shutil.rmtree(prev)
        shutil.copytree(shots, prev)
    only = [x.strip() for x in a.only.split(",") if x.strip()]
    if only and shots.exists():  # compare the re-captured screens with their images before this run
        if prev.exists():
            shutil.rmtree(prev)
        prev.mkdir(parents=True)
        for sid in only:
            if (shots / (sid + ".png")).exists():
                shutil.copy2(shots / (sid + ".png"), prev / (sid + ".png"))
    cmd = ["node", str(CAPTURE), a.manifest, str(shots), a.base] + (["--only", ",".join(only)] if only else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(r.stdout[-3000:])
    sys.stderr.write(r.stderr[-3000:])
    if r.returncode:
        die("capture.js failed")
    ref = prev if prev.exists() else None
    scr = read_json(shots / "screens.json")
    changed, new, missing = [], [], []
    for s in scr:
        if only and s["id"] not in only:
            continue
        p = shots / (s["id"] + ".png")
        if not p.exists():
            missing.append(s["id"])
            continue
        q = ref / (s["id"] + ".png") if ref else None
        if not q or not q.exists():
            new.append(s["id"])
        elif diff_ratio(p, q) > a.threshold:
            changed.append(s["id"])
    lost = [f"{s['id']}:{p['sel']}" for s in scr for p in s.get("pins", []) if not p.get("found")]
    errs = [f"{s['id']}: {e}" for s in scr for e in s.get("errors", [])]
    out = {"new": new, "changed": changed, "missing": missing, "pins_not_found": lost, "errors": errs}
    (shots / "changed.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"New: {len(new)} · changed: {len(changed)} · no image: {len(missing)} · pins not found: {len(lost)} · console errors: {len(errs)}")
    print("Check by eye and update on Figma:", ", ".join(new + changed) or "(none)")


# ---------------- finalize ----------------
def figma_url(pc, sid):
    node = (pc.get("figma") or {}).get(sid)
    f = pc.get("figma_file", "")
    if not node or not f:
        return ""
    base = re.sub(r"([?&])node-id=[^&]*", "", f).rstrip("?&")
    return base + ("&" if "?" in base else "?") + "node-id=" + node.replace(":", "-")


def how_map(cfg, spec):
    """'How to reach' line of each screen, read from the '### Sxx · ...' sections of spec/*.md."""
    labels = {t(cfg, "annotate.line.reach"), t("en", "annotate.line.reach")}
    lab = "|".join(re.escape(x) for x in labels)
    rx = re.compile(r"^###\s+(%s)\s+·[^\n]*\n(?:[^\n]*\n)*?(?:%s):\s*([^\n]+)" % (SCREEN, lab), re.M)
    out = {}
    for p in spec.glob("*.md"):
        for m in rx.finditer(p.read_text(encoding="utf-8")):
            out.setdefault(m.group(1), m.group(2).strip())
    return out


def slim_screens(cfg, pkg, shots, pc):
    full = read_json(Path(shots) / "screens.json")
    how = how_map(cfg, pkg / "spec")
    proto = pc.get("prototype", "prototype").strip("/")
    single = proto.endswith(".html")
    out, last = [], {}
    for s in full:
        route = f"{proto}{s.get('hash', '')}" if single else f"{proto}/{s.get('page', '')}{s.get('hash', '')}"
        e = {"id": s["id"], "name": s.get("name", ""), "route": route}
        if how.get(s["id"]):
            e["how"] = how[s["id"]]
        if s.get("steps"):
            e["steps"] = s["steps"]
        if s.get("cont") and last.get(s.get("flow")):
            e["after"] = last[s["flow"]]  # continue from that screen (run its steps first)
        last[s.get("flow")] = s["id"]
        if s.get("viewport"):
            e["viewport"] = s["viewport"]
        u = figma_url(pc, s["id"])
        if u:
            e["figma"] = u
        e["pins"] = [{k: p[k] for k in ("ref", "sel", "found", "leftPct", "topPct") if k in p} for p in s.get("pins", [])]
        if s.get("exits"):
            e["exits"] = [{k: x[k] for k in ("to", "action", "found", "leftPct", "topPct") if k in x and x[k] is not None}
                          for x in s["exits"]]
        out.append(e)
    sd = pkg / "screens"
    sd.mkdir(exist_ok=True)
    for f in sd.iterdir():
        if f.suffix.lower() in (".webp", ".png", ".jpg", ".jpeg"):
            f.unlink()
    txt = json.dumps(out, ensure_ascii=False, separators=(",", ":")).replace('},{"id"', '},\n{"id"')
    (sd / "screens.json").write_text(txt, encoding="utf-8")
    return out


def strip_images(cfg, pkg, pc):
    spec = pkg / "spec"
    if not spec.is_dir():
        return
    col = {t(cfg, "handoff.spec.colImage"), t("en", "handoff.spec.colImage")}
    for p in spec.glob("*.md"):
        s = p.read_text(encoding="utf-8")

        def img(m):
            u = figma_url(pc, m.group(1))
            return f"Figma: [{m.group(1)}]({u})\n" if u else ""
        s2 = re.sub(r"^!\[[^\]]*\]\(\.\./screens/(%s)\.(?:webp|png|jpe?g)\)\n?" % SCREEN, img, s, flags=re.M)
        # other sentences that point at screen images (e.g. "Images are in `screens/<id>.webp`"): the locale sentence
        s2 = re.sub(r"^(\s*(?:[-*]\s+)?)(?!\|)[^\n]*\bscreens/[^\s`)]*\.(?:webp|png|jpe?g)\b[^\n]*$",
                    lambda m: m.group(1) + t(cfg, "handoff.spec.imagesOnBoard"), s2, flags=re.M)
        if p.name == "index.md":
            lines = s2.split("\n")
            for i, ln in enumerate(lines[:-1]):
                if ln.startswith("|") and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
                    for c in col:
                        ln = ln.replace(f"| {c} |", "| Figma |")
                    lines[i] = ln
            s2 = "\n".join(lines)
        s2 = re.sub(r"`screens/(%s)\.(?:webp|png|jpe?g)`" % SCREEN,
                    lambda m: f"[Figma]({figma_url(pc, m.group(1))})" if figma_url(pc, m.group(1)) else "—", s2)
        if s2 != s:
            p.write_text(s2, encoding="utf-8")


def archive(cfg, pkg, pc):
    spec = pkg / "spec"
    idx_p = spec / "index.md"
    if not idx_p.exists():
        return []
    idx = idx_p.read_text(encoding="utf-8")
    ids = set(pc.get("archive") or [])
    status = "|".join(sorted({t(cfg, "handoff.archive.status"), t("en", "handoff.archive.status")}))
    rx = r"^\|\s*([A-Z]+\d+)\s*\|[^\n]*?\|\s*(?:%s)[^|]*\|\s*\[\1\]\(\1\.md\)\s*\|\s*$" % status
    for m in re.finditer(rx, idx, re.M):
        ids.add(m.group(1))
    ids = sorted(i for i in ids if (spec / f"{i}.md").exists())
    arc_name = spec_files(cfg)["archive"]
    arc = spec / arc_name
    before = re.findall(r'<a id="([a-z]+\d+)"></a>', arc.read_text(encoding="utf-8")) if arc.exists() else []
    if not ids:
        return [x.upper() for x in before]
    if before:  # add to the archive of an earlier run
        parts = [arc.read_text(encoding="utf-8").rstrip() + "\n"]
    else:
        parts = [t(cfg, "handoff.archive.title"), "", t(cfg, "handoff.archive.intro"), ""]
    for i in ids:
        s = (spec / f"{i}.md").read_text(encoding="utf-8")
        s = re.sub(r"^(#+)\s", lambda m: "#" + m.group(1) + " ", s, flags=re.M)  # one heading level down
        parts.append(f'<a id="{i.lower()}"></a>\n' + s.strip() + "\n")
        (spec / f"{i}.md").unlink()
    arc.write_text("\n".join(parts), encoding="utf-8")
    for p in list(spec.glob("*.md")) + [pkg / "AGENTS.md", pkg / "README.md"]:
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8")
        s2 = re.sub(r"\]\(((?:\./|spec/)?)(%s)\.md\)" % "|".join(ids),
                    lambda m: f"]({m.group(1)}{arc_name}#{m.group(2).lower()})", s)
        if s2 != s:
            p.write_text(s2, encoding="utf-8")
    return sorted(set(ids) | {x.upper() for x in before})


def trim_changelog(cfg, pkg, keep):
    p = pkg / "requirements" / "changelog.md"
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")
    secs = re.split(r"(?m)^(?=## )", s)
    head, body = secs[0], secs[1:]
    older_heads = {t(cfg, "handoff.changelog.older").strip(), t("en", "handoff.changelog.older").strip()}
    prev = [x for x in body if x.split("\n", 1)[0].strip() in older_heads]   # left by an earlier run
    body = [x for x in body if x not in prev]
    if len(body) <= keep:
        return
    old = [re.match(r"## ([^\n·]+)", x).group(1).strip() for x in body[keep:]]
    for x in prev:
        old += [v for v in VER_RX.findall(x) if v not in old]
    p.write_text(head + "".join(body[:keep]).rstrip() + "\n\n" + t(cfg, "handoff.changelog.older") + "\n"
                 + t(cfg, "handoff.changelog.olderBody", versions=", ".join(old)) + "\n", encoding="utf-8")


def grep_labels(cfg):
    keys = ("annotate.label.needsConfirm", "annotate.label.deviation", "annotate.label.outOfScope", "annotate.label.notVerified")
    words = [t(cfg, k) for k in keys] + t(cfg, "handoff.archive.status").split("|")
    words += [w for w in cfg["handoff"].get("grepLabels") or [] if isinstance(w, str)]
    return ", ".join(f'"{w}"' for w in dict.fromkeys(words) if w and not re.fullmatch(r"[a-z]+(\.[A-Za-z]+)+", w))


def agents(cfg, pkg, pc, archived, label=None):
    has = lambda f: (pkg / f).exists()
    pr = pc.get("prototype", "prototype")
    if pc.get("figma_file") and pc.get("figma_board"):
        base = re.sub(r"([?&])node-id=[^&]*", "", pc["figma_file"]).rstrip("?&")
        board = base + ("&" if "?" in base else "?") + "node-id=" + pc["figma_board"].replace(":", "-")
    else:
        board = t(cfg, "handoff.agents.noBoard")
    sf = spec_files(cfg)
    dev_last = t(cfg, "handoff.agents.devCross", file=sf["crossPage"]) if has("spec/" + sf["crossPage"]) else t(cfg, "handoff.agents.devNoCross")
    ds = cfg.get("_ds") or {}
    prefix = (ds.get("tokens") or {}).get("prefix", "")
    item = cfg["handoff"].get("itemLabel") or ""
    L = [t(cfg, "handoff.agents.title", pbi=item + pc.get("pbi", ""), title=pc.get("title", ""), version=pc.get("version", "")), "",
         t(cfg, "handoff.agents.intro", board=board, prototype=pr + ("#…" if pr.endswith(".html") else "/…")), "",
         t(cfg, "handoff.agents.rolesTitle"),
         "| " + t(cfg, "handoff.agents.colRole") + " | " + t(cfg, "handoff.agents.colRead") + " |", "|---|---|",
         t(cfg, "handoff.agents.ba"), t(cfg, "handoff.agents.qc"), t(cfg, "handoff.agents.dev", last=dev_last),
         t(cfg, "handoff.agents.design"), t(cfg, "handoff.agents.versions", keep=pc.get("changelog_keep", 2)), "",
         t(cfg, "handoff.agents.viewTitle"), t(cfg, "handoff.agents.view1"), t(cfg, "handoff.agents.view2"),
         t(cfg, "handoff.agents.view3"), t(cfg, "handoff.agents.view4"), "",
         t(cfg, "handoff.agents.codesTitle"), pc.get("codes", ""),
         t(cfg, "handoff.agents.grep", labels=grep_labels(cfg))]
    if archived:
        L.append(t(cfg, "handoff.agents.archived", ids=", ".join(archived), file=sf["archive"]))
    label = ds_label(cfg, pc, pkg)[0] if label is None else label
    L += ["", t(cfg, "handoff.agents.tokens", ds=label or "—", prefix=prefix, local=cfg["local"]["prefix"]),
          "", (t(cfg, "handoff.agents.note") + " " + pc.get("agents_note", "")).strip(), ""]
    (pkg / "AGENTS.md").write_text(re.sub(r"\n{3,}", "\n\n", "\n".join(L)), encoding="utf-8")


REF_RX = re.compile(r"(?<![\w/.-])((?:spec|screens|requirements|attachments|assets|prototype)/[^\s`)\]\"'<>|*#?]+"
                    r"\.(?:md|webp|png|jpe?g|json|csv|html|xlsx|docx|pptx|pdf))")


def file_refs(pkg):
    """(errors, warnings): file references in README, AGENTS, spec/*.md and the changelog that point to no file.
    The changelog may name files of earlier versions, so its misses are warnings."""
    err, warn = [], []
    files = [pkg / "README.md", pkg / "AGENTS.md"] + sorted((pkg / "spec").glob("*.md")) + [pkg / "requirements" / "changelog.md"]
    for f in files:
        if not f.is_file():
            continue
        for ref in dict.fromkeys(REF_RX.findall(f.read_text(encoding="utf-8"))):
            if not (pkg / ref).exists():
                (warn if f.name == "changelog.md" else err).append(f"{f.relative_to(pkg).as_posix()}: {ref} is not in the package")
    return err, warn


def csv_issues(cfg, pkg):
    out = []
    for kind, f in (("feature", "checklist-feature.csv"), ("qc", "checklist-qc.csv")):
        p = pkg / "requirements" / f
        if not p.is_file():
            continue
        first = p.read_text(encoding="utf-8-sig").split("\n", 1)[0].strip()
        got = [x.strip().strip('"') for x in first.split(",")]
        want = [x.strip() for x in csv_header(cfg, kind)[0].split(",")]
        if got != want:
            out.append(f"requirements/{f} header differs from the declared header (handoff.csv.{kind} or the locale): "
                       f"{','.join(got)[:120]} != {','.join(want)[:120]}")
    return out


def cmd_finalize(a):
    cfg, pc = load(), read_json(a.config)
    pkg = Path(a.pkg)
    if not pkg.is_dir():
        die(f"package folder not found: {pkg}")
    want = pkg_name(cfg, pc)
    if pkg.name != want:
        print(f"NOTE package folder is '{pkg.name}', kit.config.json > handoff.zipName gives '{want}'")
    # Figma gate first, so a refused run leaves the package untouched
    nofig = [x["id"] for x in read_json(Path(a.shots) / "screens.json") if not figma_url(pc, x["id"])]
    if nofig or not pc.get("figma_file"):
        why = "pkg.json has no figma_file" if not pc.get("figma_file") else \
            f"{len(nofig)} screen(s) have no Figma node: " + ", ".join(nofig[:12])
        msg = (f"wireflow on Figma is required: {why}. Build or update the board with the wireflow skill, then map "
               "screen -> node into pkg.json > figma.")
        if cfg["handoff"].get("figmaRequired", True) and not a.allow_missing_figma:
            die(msg + " Draft without a wireflow (only when the user agrees): add --allow-missing-figma.")
        print("NOTE " + msg)
    zpath = (Path(a.zip) if a.zip != "auto" else pkg.parent / (want + ".zip")) if a.zip else ""
    run_hook(cfg, "pre", pkg=pkg, config=a.config, zip=zpath)
    scr = slim_screens(cfg, pkg, a.shots, pc)
    strip_images(cfg, pkg, pc)
    archived = archive(cfg, pkg, pc)
    trim_changelog(cfg, pkg, int(pc.get("changelog_keep", 2)))
    label, source = ds_label(cfg, pc, pkg)
    print(f"DS label: {label or '(none)'} (from {source or 'nothing'}; handoff.dsLabel = {cfg['handoff'].get('dsLabel')})")
    agents(cfg, pkg, pc, archived, label)
    level = cfg["handoff"].get("dsLabelCheck", "warn")
    issues = ds_label_issues(cfg, pc, pkg, label) if level != "off" else []
    for m in issues:
        print(("ERROR: " if level == "error" else "WARN:  ") + m + ". Set pkg.json > ds_label to the version of the packaged "
              "prototype, or run sync before packaging.")
    if issues and level == "error":
        die("DS label does not match the package (handoff.dsLabelCheck = error)")
    for m in csv_issues(cfg, pkg):
        print("WARN:  " + m)
    ref_err, ref_warn = file_refs(pkg)
    for m in ref_warn:
        print("WARN:  " + m)
    for m in ref_err:
        print("ERROR: " + m)
    if ref_err:
        die(f"{len(ref_err)} file reference(s) point to files that are not in the package: fix the text or add the file")
    if (pkg / "README.md").exists() and re.search(r"screens/[^`\s)]*\.(webp|png)", (pkg / "README.md").read_text(encoding="utf-8")):
        print("NOTE README.md still mentions images in screens/: the package has no screen images, fix README")
    loose = [str(p.relative_to(pkg)) for p in pkg.rglob("*.js")]
    if loose and not a.zip:
        print(f"NOTE {len(loose)} .js file(s) still in the package; optimize_package.py (--zip) inlines and removes them")
    if SPEC_MD.is_file() and (pkg / "spec").is_dir():
        r = subprocess.run([sys.executable, "-I", str(SPEC_MD), "check", str(pkg)], capture_output=True, text=True)
        lines = r.stdout.strip().splitlines()
        for ln in lines[:-1]:
            if ln.startswith(("ERROR", "WARN")):
                print(ln)
        print(lines[-1] if lines else r.stderr.strip())
        if r.returncode:
            die("spec_md.py check failed")
    elif (pkg / "spec").is_dir():
        print(f"NOTE spec check skipped: {SPEC_MD} not found (annotate skill)")
    size = (pkg / "screens" / "screens.json").stat().st_size
    print(f"screens.json {size / 1024:.0f} KB · {len(scr)} screens · archived: {', '.join(archived) or 'none'} · "
          f"screens without Figma link: {len(nofig)}")
    if a.zip:
        z = zpath
        r = subprocess.run([sys.executable, "-I", str(OPTIMIZE), str(pkg), "--zip", str(z),
                            "--target-mb", str(cfg["handoff"].get("maxZipMB", 3))], capture_output=True, text=True)
        print("\n".join(r.stdout.strip().splitlines()[-3:]))
        if r.returncode == 2:
            print(r.stderr)
            die("optimize_package.py: some pages still load .js files that could not be inlined")
        if r.returncode == 1:
            print("NOTE zip is over handoff.maxZipMB: follow the size steps in the handoff skill")
    run_hook(cfg, "post", pkg=pkg, config=a.config, zip=zpath)


def selftest():
    """Checks of the pure parts on a throw-away project (no browser)."""
    d = Path(tempfile.mkdtemp(prefix="pkg-selftest-"))
    (d / "ds" / "acme").mkdir(parents=True)
    (d / "ds" / "acme" / "ds.json").write_text(json.dumps({"name": "acme", "label": "Acme DS", "version": "2.0.0",
                                                           "version_label": {"text": "{label} {version}", "meta": "acme-version"},
                                                           "toast": {"class": "acme-toast", "icon": "<svg></svg>"}}))
    (d / "kit.config.json").write_text(json.dumps({"ds": "ds/acme", "handoff": {
        "itemLabel": "PBI ", "grepLabels": ["Waiting for Figma"], "specFiles": {"archive": "old-units.md"},
        "csv": {"qc": "ID,Steps"}}}))
    cfg = load(d)
    pkg = d / "pkg"
    (pkg / "spec").mkdir(parents=True)
    (pkg / "requirements").mkdir()
    (pkg / "prototype").mkdir()
    (pkg / "screens").mkdir()
    (pkg / "screens" / "screens.json").write_text("[]")
    (pkg / "prototype" / "index.html").write_text('<meta name="acme-version" content="1.9.0">')
    (pkg / "spec" / "index.md").write_text('---\npbi: "1"\nds: "Acme DS 1.9.0"\n---\n# x\n')
    (pkg / "spec" / "flows.md").write_text("# Flows\nImages are in `screens/<id>.webp`.\n| S01 | `screens/S01.webp` |\n")
    (pkg / "README.md").write_text("See `spec/index.md`, `spec/gone.md` and [p](prototype/index.html#/x).\n")
    (pkg / "requirements" / "changelog.md").write_text("## 1.0.0\n- renamed spec/luu-tru.md\n")
    (pkg / "requirements" / "checklist-qc.csv").write_text("ID,Steps,Extra\n", encoding="utf-8-sig")
    pc = {"pbi": "1234", "title": "Tasks", "version": "1.0.0", "ds_label": ""}
    assert ds_label(cfg, pc, pkg) == ("Acme DS 1.9.0", "spec"), ds_label(cfg, pc, pkg)
    assert ds_label(cfg, dict(pc, ds_label="Acme DS 1.8.0"), pkg)[1] == "pkg"
    (pkg / "spec" / "index.md").write_text("# no frontmatter\n")
    assert ds_label(cfg, pc, pkg) == ("Acme DS 2.0.0", "ds")
    cfg["handoff"]["dsLabel"] = "prototype"
    assert ds_label(cfg, pc, pkg) == ("Acme DS 1.9.0", "prototype")
    issues = ds_label_issues(cfg, pc, pkg, "Acme DS 2.0.0")
    assert len(issues) == 1 and "1.9.0" in issues[0], issues
    assert ds_label_issues(cfg, pc, pkg, "Acme DS 1.9.0") == []
    assert len(csv_issues(cfg, pkg)) == 1
    strip_images(cfg, pkg, {})
    fl = (pkg / "spec" / "flows.md").read_text()
    assert t(cfg, "handoff.spec.imagesOnBoard") in fl and "| S01 | — |" in fl, fl
    err, warn = file_refs(pkg)
    assert err == ["README.md: spec/gone.md is not in the package"] and len(warn) == 1, (err, warn)
    assert '"Waiting for Figma"' in grep_labels(cfg)
    pc["lock"] = {"pages": ["index.html", "tasks/index.html"], "page_keys": {"tasks": "tasks/index.html"},
                  "allow": ["#tasks"], "allow_when": [{"sel": "#more", "hash": "^#/tasks/"}], "seed": {"localStorage": {"k": "1"}},
                  "toast": {"args": ["warning"]}}
    L = render_layer(cfg, pc, "lock")
    conf = json.loads(re.search(r"var C = (\{.*?\});\n", L["script"]).group(1))
    assert conf["toast"]["class"] == "acme-toast" and conf["toast"]["args"] == ["warning"], conf["toast"]
    assert conf["pageKeys"] == {"tasks": "tasks/index.html"} and conf["allowWhen"][0]["sel"] == "#more" and conf["seed"]
    assert L["meta"].startswith("lock PBI 1234"), L["meta"]
    html = inject("<html><head></head><body></body></html>", L)
    assert html.count("x-handover-lock") == 1 and inject(html, L).count("x-handover-lock") == 1, "layer is idempotent"
    shutil.rmtree(d, ignore_errors=True)
    print("pkg.py selftest OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    ap = argparse.ArgumentParser(description="Handoff package pipeline (see the module docstring for details).",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="{init,name,layer,capture,finalize}")
    i = sub.add_parser("init", help="create pkg.json and CSV headers for a work item")
    i.add_argument("--pbi", required=True, help="work-item code")
    i.add_argument("--title", required=True, help="feature or app title")
    i.add_argument("--version", default="1.0.0")
    i.add_argument("--app", default="", help="app id from kit.config.json > apps")
    i.add_argument("--mode", choices=("feature", "app"), default="feature")
    i.add_argument("--treatment", choices=("keep", "lock", "hide"), default="keep", help="a keep, b lock, c hide")
    i.add_argument("--prototype", default="prototype", help="'prototype' (folder) or 'prototype.html' (single file)")
    i.add_argument("--dir", default="", help="source folder (default <handoff.dir>/<pbi>)")
    i.add_argument("--force", action="store_true")
    n = sub.add_parser("name", help="print folder and zip name")
    n.add_argument("--config", required=True)
    ly = sub.add_parser("layer", help="render and inject the lock or hide layer")
    ly.add_argument("--config", required=True)
    ly.add_argument("--kind", choices=("lock", "hide"), required=True)
    ly.add_argument("--into", nargs="*", default=[], help="HTML pages to inject into")
    ly.add_argument("--out", default="", help="write the layer to this file instead")
    c = sub.add_parser("capture", help="screenshot screens and list new or changed ones (needs Node + Playwright)")
    c.add_argument("--manifest", required=True)
    c.add_argument("--shots", required=True)
    c.add_argument("--base", default="http://localhost:8791/")
    c.add_argument("--only", default="")
    c.add_argument("--threshold", type=float, default=0.001,
                   help="share of different pixels that marks a screen as changed (default 0.1%%)")
    f = sub.add_parser("finalize", help="slim screens.json, drop images, archive, AGENTS.md, check, zip")
    f.add_argument("--pkg", required=True)
    f.add_argument("--shots", required=True)
    f.add_argument("--config", required=True)
    f.add_argument("--zip", nargs="?", const="auto", default="", help="zip path; no value = <zipName>.zip next to the package")
    f.add_argument("--allow-missing-figma", action="store_true", help="only when the user accepts a draft without a wireflow")
    a = ap.parse_args()
    {"init": cmd_init, "name": cmd_name, "layer": cmd_layer, "capture": cmd_capture, "finalize": cmd_finalize}[a.cmd](a)


if __name__ == "__main__":
    main()
