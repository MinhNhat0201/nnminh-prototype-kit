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

  pkg.py finalize --pkg "<package folder>" --shots shots --config pkg.json [--zip [<zip path>]] [--allow-missing-figma]
      Finish the package after spec/*.md, requirements/ and README.md are written:
      1. screens/screens.json, slim: route, how to reach (text and runnable steps), pins, exits, Figma link.
      2. Remove screen images: delete screens/*.webp|png, replace image lines in spec/*.md with "Figma: ...".
      3. Move replaced or removed units to spec/archive.md and fix links.
      4. Keep only pkg.json > changelog_keep versions (default 2) in requirements/changelog.md.
      5. Write AGENTS.md: reading path per role (BA, QC, Dev, wireflow), code conventions, grep labels.
      6. Run spec_md.py check (annotate skill) when present; with --zip, optimise and zip with optimize_package.py.
         --zip without a value writes "<handoff.zipName>.zip" next to the package folder.

pkg.json (one per work item, kept in <handoff.dir>/<pbi>/):
  {"pbi": "1234", "title": "Scheduled tasks", "version": "1.0.0", "app": "acme-web", "mode": "feature",
   "treatment": "lock", "prototype": "prototype", "figma_file": "<file link>", "figma_board": "<node id>",
   "figma": {"S01": "<node id>"}, "codes": "...", "archive": [], "changelog_keep": 2, "agents_note": "",
   "lock": {...}, "hide": {...}}
Generated text comes from locales/<language>/handoff.json. Messages on the console are English.
"""
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, t, version_label  # noqa: E402

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


def ds_label(cfg, pc):
    if pc.get("ds_label"):
        return pc["ds_label"]
    return version_label(cfg) if cfg.get("_ds") else ""


# ---------------- init / name ----------------
def cmd_init(a):
    cfg = load()
    d = Path(a.dir) if a.dir else Path(cfg["_root"]) / cfg["handoff"]["dir"] / a.pbi
    if (d / "pkg.json").exists() and not a.force:
        die(f"{d / 'pkg.json'} already exists (use --force to overwrite)")
    pc = {"pbi": a.pbi, "title": a.title, "version": a.version, "app": a.app, "mode": a.mode,
          "treatment": a.treatment, "prototype": a.prototype, "figma_file": "", "figma_board": "", "figma": {},
          "codes": "", "archive": [], "changelog_keep": 2, "agents_note": ""}
    if a.treatment == "lock":
        pc["lock"] = {"pages": [], "allow": [], "block": [], "nav_functions": [], "shortcuts": [], "open_allow": "",
                      "toast": {"function": "", "container": "", "class": "", "close_class": "", "ms": 5000}}
    if a.treatment == "hide":
        pc["hide"] = {"selectors": [], "shortcuts": [], "dropped_hashes": [], "entry": "", "defaults": []}
    d.mkdir(parents=True, exist_ok=True)
    (d / "pkg.json").write_text(json.dumps(pc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    req = d / "requirements"
    req.mkdir(exist_ok=True)
    for key, f in (("handoff.csv.feature", "checklist-feature.csv"), ("handoff.csv.qc", "checklist-qc.csv")):
        if not (req / f).exists():
            (req / f).write_text(t(cfg, key) + "\n", encoding="utf-8-sig")
    print(f"Created {d / 'pkg.json'} and CSV headers in {req}")
    print(f"Package name: {pkg_name(cfg, pc)}")


def cmd_name(a):
    cfg, pc = load(), read_json(a.config)
    n = pkg_name(cfg, pc)
    print(json.dumps({"folder": n, "zip": n + ".zip"}, ensure_ascii=False))


# ---------------- layer ----------------
LOCK_ID, HIDE_ID, HIDE_CSS_ID = "x-handover-lock", "x-handover-hide-js", "x-handover-hide"


def render_layer(cfg, pc, kind):
    name = f"{pc.get('pbi', '')} · {pc.get('title', '')} v{pc.get('version', '')}".strip()
    if kind == "lock":
        L = pc.get("lock")
        if not L or not L.get("allow"):
            die("pkg.json > lock.allow is empty: list the selectors of the feature (and the menus, dialogs, toasts it uses)")
        conf = {"name": name, "msg": t(cfg, "handoff.lock.toast", name=name), "close": t(cfg, "handoff.lock.close"),
                "pages": L.get("pages", []), "allow": L["allow"], "block": L.get("block", []),
                "navFunctions": L.get("nav_functions", []), "shortcuts": L.get("shortcuts", []), "openAllow": L.get("open_allow", ""),
                "toast": {"function": "", "container": "", "class": "", "close_class": "", "ms": 5000, **L.get("toast", {})}}
        tt = conf["toast"]
        if not tt.get("function") and not tt.get("class"):
            die("pkg.json > lock.toast needs 'function' (the app's toast function) or 'class' (the DS toast classes "
                "from catalog.md): the out-of-scope notice must be a DS toast")
        js = (ASSETS / "scope-lock.js").read_text(encoding="utf-8").replace("/*@CONFIG@*/{}", json.dumps(conf, ensure_ascii=False))
        return {"script": f'<script id="{LOCK_ID}">\n{js}</script>', "style": "", "meta": f"lock {name}"}
    H = pc.get("hide")
    if not H or not H.get("selectors"):
        die("pkg.json > hide.selectors is empty: list stable selectors (data-*, id, aria-label) of what to hide")
    css = ",\n".join(H["selectors"]) + "{display:none !important}"
    conf = {"shortcuts": H.get("shortcuts", []), "droppedHashes": H.get("dropped_hashes", []),
            "entry": H.get("entry", ""), "defaults": H.get("defaults", [])}
    js = (ASSETS / "scope-hide.js").read_text(encoding="utf-8").replace("/*@CONFIG@*/{}", json.dumps(conf, ensure_ascii=False))
    return {"script": f'<script id="{HIDE_ID}">\n{js}</script>',
            "style": f'<style id="{HIDE_CSS_ID}">\n/* Handoff scope: hidden on purpose (see spec, "Out of scope") */\n{css}\n</style>',
            "meta": f"hide {name}"}


def inject(html, layer):
    for tag, i in (("script", LOCK_ID), ("script", HIDE_ID), ("style", HIDE_CSS_ID)):
        html = re.sub(r'\n?<%s id="%s">.*?</%s>' % (tag, i, tag), "", html, flags=re.S)
    html = re.sub(r'\n?<meta name="x-handover"[^>]*>', "", html)
    meta = f'<meta name="x-handover" content="{layer["meta"]}">'
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
    cmd = ["node", str(CAPTURE), a.manifest, str(shots), a.base] + ([a.only] if a.only else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(r.stdout[-3000:])
    sys.stderr.write(r.stderr[-3000:])
    if r.returncode:
        die("capture.js failed")
    ref = prev if prev.exists() else None
    scr = read_json(shots / "screens.json")
    changed, new, missing = [], [], []
    for s in scr:
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
    arc = spec / "archive.md"
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
                    lambda m: f"]({m.group(1)}archive.md#{m.group(2).lower()})", s)
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
    return ", ".join(f'"{w}"' for w in dict.fromkeys(words) if w and "." not in w)


def agents(cfg, pkg, pc, archived):
    has = lambda f: (pkg / f).exists()
    pr = pc.get("prototype", "prototype")
    if pc.get("figma_file") and pc.get("figma_board"):
        base = re.sub(r"([?&])node-id=[^&]*", "", pc["figma_file"]).rstrip("?&")
        board = base + ("&" if "?" in base else "?") + "node-id=" + pc["figma_board"].replace(":", "-")
    else:
        board = t(cfg, "handoff.agents.noBoard")
    dev_last = t(cfg, "handoff.agents.devCross") if has("spec/cross-page.md") else t(cfg, "handoff.agents.devNoCross")
    ds = cfg.get("_ds") or {}
    prefix = (ds.get("tokens") or {}).get("prefix", "")
    L = [t(cfg, "handoff.agents.title", pbi=pc.get("pbi", ""), title=pc.get("title", ""), version=pc.get("version", "")), "",
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
        L.append(t(cfg, "handoff.agents.archived", ids=", ".join(archived)))
    L += ["", t(cfg, "handoff.agents.tokens", ds=ds_label(cfg, pc) or "—", prefix=prefix, local=cfg["local"]["prefix"]),
          "", (t(cfg, "handoff.agents.note") + " " + pc.get("agents_note", "")).strip(), ""]
    (pkg / "AGENTS.md").write_text(re.sub(r"\n{3,}", "\n\n", "\n".join(L)), encoding="utf-8")


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
    scr = slim_screens(cfg, pkg, a.shots, pc)
    strip_images(cfg, pkg, pc)
    archived = archive(cfg, pkg, pc)
    trim_changelog(cfg, pkg, int(pc.get("changelog_keep", 2)))
    agents(cfg, pkg, pc, archived)
    if (pkg / "README.md").exists() and re.search(r"screens/[^`\s)]*\.(webp|png)", (pkg / "README.md").read_text(encoding="utf-8")):
        print("NOTE README.md still mentions images in screens/: the package has no screen images, fix README")
    loose = [str(p.relative_to(pkg)) for p in pkg.rglob("*.js")]
    if loose and not a.zip:
        print(f"NOTE {len(loose)} .js file(s) still in the package; optimize_package.py (--zip) inlines and removes them")
    if SPEC_MD.is_file() and (pkg / "spec").is_dir():
        r = subprocess.run([sys.executable, "-I", str(SPEC_MD), "check", str(pkg)], capture_output=True, text=True)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip())
        if r.returncode:
            print(r.stdout)
            die("spec_md.py check failed")
    elif (pkg / "spec").is_dir():
        print(f"NOTE spec check skipped: {SPEC_MD} not found (annotate skill)")
    size = (pkg / "screens" / "screens.json").stat().st_size
    print(f"screens.json {size / 1024:.0f} KB · {len(scr)} screens · archived: {', '.join(archived) or 'none'} · "
          f"screens without Figma link: {len(nofig)}")
    if a.zip:
        z = Path(a.zip) if a.zip != "auto" else pkg.parent / (want + ".zip")
        r = subprocess.run([sys.executable, "-I", str(OPTIMIZE), str(pkg), "--zip", str(z),
                            "--target-mb", str(cfg["handoff"].get("maxZipMB", 3))], capture_output=True, text=True)
        print("\n".join(r.stdout.strip().splitlines()[-3:]))
        if r.returncode == 2:
            print(r.stderr)
            die("optimize_package.py: some pages still load .js files that could not be inlined")
        if r.returncode == 1:
            print("NOTE zip is over handoff.maxZipMB: follow the size steps in the handoff skill")


def main():
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
