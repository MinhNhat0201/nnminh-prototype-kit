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
      to one file. lock = option (b): capture-phase listener + DS toast, nothing is disabled; lock.open_block blocks
      matching URLs even for pages of the package. hide = option (c): display:none CSS block + guard script
      (shortcuts, hashes of dropped pages, defaults). lock.seed / hide.seed: a separate script at the top of <head>,
      before app code. The app's own DS profile (apps[].ds of pkg.json > app) gives the toast pattern.

  pkg.py capture  --manifest manifest.js --shots shots --base http://localhost:8791/ [--only S01,S02] [--app <id>]
      Run capture.js of the annotate skill (2x screenshots), keep the previous run in <shots>.prev, compare pixels
      and write <shots>/changed.json (new screens, changed screens). Only these need a visual check and a Figma update.
      --only captures just those screens (and runs the earlier screens of their flow that set up the state).

      --baseline <screens.json | image folder of the previous package> compares with that package instead of the last run
      (new = not in its screens.json; changed = route or a pin style differs, or the image differs; images at another
      scale are resized first), so the first kit run on an older board still lists what changed. changed.json says why.

  pkg.py proto    --pages index.html notes/index.html --into "<package>/prototype" (--root <app folder> | --app <id>)
      Copy the pages and only the files they load (href, src, srcset, url(), @import, file names quoted in scripts,
      followed through CSS, JS and JSON), keeping relative paths. Linked pages not in --pages are left out (NOTE: lock or
      hide every way in); references not found are listed (paths built at run time). Bare file names quoted in scripts
      (no folder, often sample data) are only counted (--verbose lists them). Pages of the app folder that no static
      reference reaches (a page registry or router in a script) are listed too.

  pkg.py finalize --pkg "<package folder>" --shots shots --config pkg.json [--zip [<zip path>]] [--allow-missing-figma]
      Finish the package after spec/*.md, requirements/ and README.md are written:
      1. screens/screens.json, slim: route, how to reach (text and runnable steps), pins, exits, Figma link.
      2. Remove screen images: delete screens/*.webp|png, replace image lines in spec/*.md with "Figma: ...".
      2b. Only the sentence of a line that points at screen images becomes the locale sentence; the rest stays.
      2c. Refresh the Figma links of spec/*.md from pkg.json > figma: the "Figma:" line of each "### Sxx" screen and the
          Figma column of tables whose first column is a screen code (index.md "Screens").
      3. Move replaced or removed units to spec/archive.md and fix links (an older name from handoff.specFiles.legacy
         when the package already has that file or README/AGENTS/changelog point at it).
      4. Keep only pkg.json > changelog_keep versions (default 2) in requirements/changelog.md.
      5. Write AGENTS.md: reading path per role (BA, QC, Dev, wireflow), code conventions, grep labels. The Dev path and
         the archive line name the special files the package really has (older names included).
      6. Checks: DS label against the <meta> of the package pages and spec/index.md (handoff.dsLabelCheck; older
         frontmatter keys through handoff.specFields);
         every file reference (spec/..., screens/..., requirements/..., prototype/...) in README, AGENTS, spec and
         changelog points to a file in the package; CSV headers match handoff.csv; spec_md.py check (annotate skill),
         printing every WARN and ERROR line.
      7. With --zip, optimise and zip with optimize_package.py.
         --zip without a value writes "<handoff.zipName>.zip" next to the package folder.
      kit.config.json > handoff.pre / handoff.post: project commands run before step 1 and after step 7
      ({pkg}, {config}, {zip}, {root} are replaced, shell-quoted). A failing command stops with ERROR.

      Figma gate: every screen needs a node (pkg.json > figma) unless --allow-missing-figma; then pkg.json > status is
      "awaiting-figma" (draft, screens listed in awaiting_figma; spec gets a "Figma: <not yet>" line), else "final".

  pkg.py relink   --pkg "<package folder>" --config pkg.json [--zip [<zip path>]]
      For a package finalized as awaiting-figma, after the wireflow skill mapped the screens (setmap): write the Figma
      links into screens/screens.json, the "Figma:" lines and Figma columns of spec/*.md and the board link of AGENTS.md,
      set status final and re-zip. Nothing else changes (no capture, no archive, no changelog trim). Then run share.

  pkg.py smoke    <zip | package folder> [--widths 400,768,1280] [--keep]
      Unzip to a temp folder, serve it over HTTP from the package folder and open every route of screens/screens.json
      at each width (handoff.smokeWidths) in Chromium (smoke.js): page errors, console errors, responses >= 400, failed
      requests, broken images, horizontal scroll; a zip is also checked for blocked files. Exit 1 on any problem.
      Routes only (no click steps): flows are checked by the validate skill.

  pkg.py --selftest
      Run the built-in checks of the pure functions (no browser, no network).

pkg.json (one per work item, kept in <handoff.dir>/<pbi>/):
  {"pbi": "1234", "title": "Scheduled tasks", "version": "1.0.0", "app": "acme-web", "mode": "feature",
   "treatment": "lock", "prototype": "prototype", "figma_file": "<file link>", "figma_board": "<node id>",
   "figma": {"S01": "<node id>"}, "codes": "...", "archive": [], "changelog_keep": 2, "agents_note": "",
   "ds_label": "<DS label of the packaged prototype, e.g. Acme DS 1.4.0; empty = see handoff.dsLabel>",
   "lock": {...}, "hide": {...}, "csv": {"feature": ..., "qc": ...}, "status": "final|awaiting-figma"}
  csv (optional) overrides kit.config.json > handoff.csv for this package (headers kept from its earlier versions).
Generated text comes from locales/<language>/handoff.json. Messages on the console are English.
"""
import argparse, functools, http.server, json, os, re, shlex, shutil, subprocess, sys, tempfile, threading, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, t, version_label, spec_files, csv_header, for_app  # noqa: E402
import kitconf  # noqa: E402

ANNOTATE = KIT / "skills" / "annotate" / "scripts"
CAPTURE = ANNOTATE / "capture.js"
SPEC_MD = ANNOTATE / "spec_md.py"
OPTIMIZE = HERE / "optimize_package.py"
SMOKE = HERE / "smoke.js"
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


def spec_meta(pkg, cfg=None):
    """Frontmatter of spec/index.md as a dict ({} when missing), with the key aliases of handoff.specFields."""
    p = Path(pkg) / "spec" / "index.md" if pkg else None
    if not p or not p.is_file():
        return {}
    m = re.match(r"---\n(.*?)\n---\n", p.read_text(encoding="utf-8"), re.S)
    out = {}
    for ln in (m.group(1).split("\n") if m else []):
        if ":" in ln:
            k, v = ln.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return kitconf.spec_meta(cfg, out) if cfg else out


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
             "spec": lambda: spec_meta(pkg, cfg).get("ds", ""),
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
    sv = spec_meta(pkg, cfg).get("ds", "")
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
                      "shortcuts": [], "open_allow": "", "open_block": "", "seed": {},
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
LOCK_ID, HIDE_ID, HIDE_CSS_ID, SEED_ID = "x-handover-lock", "x-handover-hide-js", "x-handover-hide", "x-handover-seed"


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
                "block": L.get("block", []), "navFunctions": nav_functions(L), "shortcuts": L.get("shortcuts", []),
                "openAllow": L.get("open_allow", ""), "openBlock": L.get("open_block", ""), "toast": toast}
        if not toast.get("function") and not toast.get("class"):
            die("pkg.json > lock.toast needs 'function' (the app's toast function) or 'class' (the DS toast classes "
                "from catalog.md, or ds.json > toast): the out-of-scope notice must be a DS toast")
        for k in ("open_allow", "open_block"):
            try:
                re.compile(L.get(k) or "")
            except re.error as e:
                die(f"pkg.json > lock.{k} is not a valid regex: {e}")
        js = (ASSETS / "scope-lock.js").read_text(encoding="utf-8").replace("/*@CONFIG@*/{}", js_json(conf))
        return {"script": f'<script id="{LOCK_ID}">\n{js}</script>', "style": "", "meta": t(cfg, "handoff.layer.lock", name=name),
                "seed": seed_script(L.get("seed"))}
    H = pc.get("hide")
    if not H or not H.get("selectors"):
        die("pkg.json > hide.selectors is empty: list stable selectors (data-*, id, aria-label) of what to hide")
    css = ",\n".join(H["selectors"]) + "{display:none !important}"
    conf = {"shortcuts": H.get("shortcuts", []), "droppedHashes": H.get("dropped_hashes", []),
            "entry": H.get("entry", ""), "defaults": H.get("defaults", [])}
    js = (ASSETS / "scope-hide.js").read_text(encoding="utf-8").replace("/*@CONFIG@*/{}", js_json(conf))
    return {"script": f'<script id="{HIDE_ID}">\n{js}</script>',
            "style": f'<style id="{HIDE_CSS_ID}">\n/* Handoff scope: hidden on purpose (see spec, "Out of scope") */\n{css}\n</style>',
            "meta": t(cfg, "handoff.layer.hide", name=name), "seed": seed_script(H.get("seed"))}


NAV_BASES = ("page", "app")


def nav_functions(L):
    """pkg.json > lock.nav_functions as [{"name", "base"}]. An entry is a dotted name ("appNav.go") or
    {"name": ..., "base": "page"|"app"}; base says what a relative path argument is relative to: the current page
    (default, lock.nav_base) or the app root, i.e. the package prototype folder (K-F15)."""
    dflt = L.get("nav_base") or "page"
    if dflt not in NAV_BASES:
        die("pkg.json > lock.nav_base must be one of " + ", ".join(NAV_BASES))
    out = []
    for i, x in enumerate(L.get("nav_functions") or []):
        x = {"name": x} if isinstance(x, str) else x
        if not isinstance(x, dict) or not x.get("name") or (x.get("base") or dflt) not in NAV_BASES:
            die(f"pkg.json > lock.nav_functions[{i}] must be a dotted name or {{\"name\": ..., \"base\": \"page\"|\"app\"}}")
        out.append({"name": x["name"], "base": x.get("base") or dflt})
    return out


def seed_script(seed):
    """<script id="x-handover-seed">: storage keys the package needs, set when absent. Injected at the top of <head>,
    before any script of the page, so app code that reads them while it loads sees the values."""
    seed = {k: v for k, v in (seed or {}).items() if k in ("localStorage", "sessionStorage") and v}
    if not seed:
        return ""
    js = ("(function(){var S=%s;['localStorage','sessionStorage'].forEach(function(k){var o=S[k];if(!o)return;"
          "try{Object.keys(o).forEach(function(n){if(window[k].getItem(n)===null)window[k].setItem(n,String(o[n]));});}"
          "catch(e){}});})();") % js_json(seed)
    return f'<script id="{SEED_ID}">{js}</script>'


def inject(html, layer):
    for tag, i in (("script", LOCK_ID), ("script", HIDE_ID), ("style", HIDE_CSS_ID), ("script", SEED_ID)):
        html = re.sub(r'\n?<%s id="%s">.*?</%s>' % (tag, i, tag), "", html, flags=re.S)
    html = re.sub(r'\n?<meta name="x-handover"[^>]*>', "", html)
    meta = '<meta name="x-handover" content="%s">' % layer["meta"].replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    head = meta + ("\n" + layer["style"] if layer["style"] else "")
    if re.search(r"</head>", html, re.I):
        html = re.sub(r"</head>", head + "\n</head>", html, count=1, flags=re.I)
    else:
        html = head + "\n" + html
    if layer.get("seed"):  # first thing in <head> (after <meta charset> when it opens the head), before every app script
        m = re.search(r"<head\b[^>]*>(\s*<meta\s+charset[^>]*>)?", html, re.I)
        at = m.end() if m else (re.search(r"<script\b", html, re.I).start() if re.search(r"<script\b", html, re.I) else 0)
        html = html[:at] + "\n" + layer["seed"] + html[at:]
    if re.search(r"</body>", html, re.I):
        idx = [m.start() for m in re.finditer(r"</body>", html, re.I)][-1]
        html = html[:idx] + layer["script"] + "\n" + html[idx:]
    else:
        html += "\n" + layer["script"] + "\n"
    return html


def cmd_layer(a):
    pc = read_json(a.config)
    cfg = load(app=pc.get("app") or None)  # the app's own DS profile (apps[].ds): toast pattern
    if pc.get("lock") and pc.get("hide") and (pc["lock"].get("allow") and pc["hide"].get("selectors")):
        die("pkg.json has both lock and hide: one package uses one treatment, never both")
    layer = render_layer(cfg, pc, a.kind)
    if a.out:
        body = (layer["seed"] + "\n" if layer.get("seed") else "") + (layer["style"] + "\n" if layer["style"] else "") + layer["script"] + "\n"
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
def diff_ratio(a, b, rescale=False):
    from PIL import Image, ImageChops, ImageFilter
    A, B = Image.open(a).convert("L"), Image.open(b).convert("L")
    cut = 24
    if rescale:   # an earlier package (another scale, lossy WebP): compare at the smaller size, softened, with a wider margin
        if A.size != B.size and B.size[0] and abs(A.size[0] / B.size[0] - A.size[1] / B.size[1]) < 0.02:
            A = A.resize(B.size, Image.LANCZOS) if A.size[0] > B.size[0] else A
            B = B.resize(A.size, Image.LANCZOS) if B.size != A.size else B
        A, B, cut = A.filter(ImageFilter.GaussianBlur(1)), B.filter(ImageFilter.GaussianBlur(1)), 48
    if A.size != B.size:
        return 1.0
    d = ImageChops.difference(A, B).point(lambda v: 255 if v > cut else 0)
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
    cmd = ["node", str(CAPTURE), a.manifest, str(shots), a.base] + (["--only", ",".join(only)] if only else []) \
        + (["--app", a.app] if a.app else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(r.stdout[-3000:])
    sys.stderr.write(r.stderr[-3000:])
    if r.returncode:
        die("capture.js failed")
    ref = prev if prev.exists() else None
    scr = read_json(shots / "screens.json")
    base_ids, base_img, base_scr = baseline_of(a.baseline) if a.baseline else (None, {}, {})
    changed, new, missing, why = [], [], [], {}
    for s in scr:
        if only and s["id"] not in only:
            continue
        p = shots / (s["id"] + ".png")
        if not p.exists():
            missing.append(s["id"])
            continue
        if a.baseline:   # compare with the previous package (its screens.json and/or images), not with the last run
            if base_ids is not None and s["id"] not in base_ids:
                new.append(s["id"])
                continue
            r = screen_change(s, base_scr.get(s["id"])) if base_scr else ""
            q = base_img.get(s["id"])
            if not r and q and diff_ratio(p, q, rescale=True) > a.threshold:
                r = "pixels"
            if not r and not q and base_ids is None:
                new.append(s["id"])
                continue
            if r:
                changed.append(s["id"])
                why[s["id"]] = r
            continue
        q = ref / (s["id"] + ".png") if ref else None
        if not q or not q.exists():
            new.append(s["id"])
        elif diff_ratio(p, q) > a.threshold:
            changed.append(s["id"])
    lost = [f"{s['id']}:{p['sel']}" for s in scr for p in s.get("pins", []) if not p.get("found")]
    errs = [f"{s['id']}: {e}" for s in scr for e in s.get("errors", [])]
    out = {"new": new, "changed": changed, "missing": missing, "pins_not_found": lost, "errors": errs}
    if a.baseline:
        out.update(baseline=str(a.baseline), why=why)
    (shots / "changed.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"New: {len(new)} · changed: {len(changed)} · no image: {len(missing)} · pins not found: {len(lost)} · console errors: {len(errs)}")
    print("Check by eye and update on Figma:", ", ".join(new + changed) or "(none)")
    if a.baseline:
        print("Compared with the baseline %s: %s" % (a.baseline, ", ".join("%s (%s)" % (k, v) for k, v in why.items()) or "no changed screen"))


IMG_EXT = (".png", ".webp", ".jpg", ".jpeg")
STYLE_PROPS = ("color", "backgroundColor", "borderColor", "borderWidth", "borderRadius", "fontSize", "fontWeight",
               "lineHeight", "padding", "gap", "boxShadow")


def baseline_of(path):
    """(screen ids or None, {id: image path}, {id: screen entry}) of an earlier package: its screens.json (file), or a
    folder with screens.json and/or <id>.png|webp|jpg images (a package's screens/ folder, or an old capture)."""
    p = Path(path)
    if not p.exists():
        die(f"baseline not found: {p}")
    folder = p if p.is_dir() else p.parent
    js = p if p.is_file() else (p / "screens.json" if (p / "screens.json").is_file() else None)
    scr = {x["id"]: x for x in read_json(js)} if js else {}
    imgs = {}
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() in IMG_EXT and re.fullmatch(SCREEN, f.stem):
            imgs.setdefault(f.stem, f)
    return (set(scr) if scr else None), imgs, scr


def screen_change(cur, old):
    """Why a screen differs from its baseline entry: "route", "style" (a pin style both captures recorded), or ""."""
    if old is None:
        return ""
    if (cur.get("page"), cur.get("hash")) != (old.get("page", cur.get("page")), old.get("hash", cur.get("hash"))):
        return "route"
    olds = {(p.get("sel") or p.get("selector")): p for p in old.get("pins") or []}
    for p in cur.get("pins") or []:
        o = olds.get(p.get("sel"))
        a_, b_ = ((p.get("style") or {}).get("props") or {}), (((o or {}).get("style") or {}).get("props") or {})
        if any(k in a_ and k in b_ and a_[k] != b_[k] for k in STYLE_PROPS):
            return "style"
    return ""


# ---------------- prototype copy ----------------
REF_ATTR = re.compile(r"""\b(?:href|src|poster|data-src|srcset)\s*=\s*["']([^"']+)["']""", re.I)
CSS_URL = re.compile(r"""url\(\s*["']?([^"')]+?)["']?\s*\)|@import\s+["']([^"']+)["']""", re.I)
# any relative path with a file extension, anywhere in the text (quoted, escaped, after "+ROOT+"): only files that exist
# under the app folder are copied, so a word that only looks like a path costs nothing
ASSET_STR = re.compile(r"""(?<![\w/.%-])((?:\.\.?/)*[\w@%-][\w@.%-]*(?:/[\w@.%-]+)*\.(?:png|jpe?g|webp|gif|svg|avif|ico|bmp|css|js|mjs|json|woff2?|ttf|otf|eot|mp4|webm|mp3|wav|pdf))(?![\w-])""", re.I)
TEXT_EXT = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".svg"}


def refs_of(f, text, kinds=False):
    """Relative file references of one HTML, CSS, JS, JSON or SVG file: href/src/srcset, url() and @import, and quoted
    strings that name a file (paths built in scripts). External URLs, data: URIs and anchors are skipped.
    kinds=True: (ref, sure) pairs; sure is False for a bare file name found only in script text (no folder), which is
    often sample data, not a file the page loads (K-F16)."""
    out = []
    if f.suffix.lower() in (".html", ".htm", ".svg"):
        for m in REF_ATTR.finditer(text):
            out += [(x.strip().split(" ")[0], True) for x in m.group(1).split(",")] if "srcset" in m.group(0).lower() \
                else [(m.group(1), True)]
    out += [(m.group(1) or m.group(2), True) for m in CSS_URL.finditer(text)]
    out += [(m.group(1), "/" in m.group(1)) for m in ASSET_STR.finditer(text)]
    keep = []
    for r, sure in out:
        r = re.sub(r"^(?:\$\{[^}]*\}|\{\{[^}]*\}\})+", "", r.strip())   # ${ROOT}assets/x.png, {{ROOT}}assets/x.png
        r = re.split(r"[?#]", r, maxsplit=1)[0]
        if r and not re.match(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", r, re.I) and "${" not in r and "{{" not in r:
            keep.append((r, sure))
    return keep if kinds else [r for r, _ in keep]


def proto_files(root, pages, weak=None):
    """(files to copy, linked pages left out, references not found): the pages plus every file they load, followed
    through CSS, scripts and JSON (relative to the file, else to the app root). Other pages are never pulled in.
    weak (a set): receives the bare file names quoted in scripts that were not found (kept out of the missing list)."""
    root = root.resolve()
    want = {(root / p).resolve() for p in pages}
    for p in want:
        if not p.is_file():
            die(f"page not found: {p}")
    todo, files, left, missing = list(want), set(want), set(), set()
    while todo:
        f = todo.pop()
        if f.suffix.lower() not in TEXT_EXT:
            continue
        for r, sure in refs_of(f, f.read_text(encoding="utf-8", errors="replace"), kinds=True):
            hit = next((c for c in ((f.parent / r).resolve(), (root / r.lstrip("/")).resolve()) if c.is_file() and root in c.parents), None)
            if not hit:
                if not r.lower().endswith((".html", ".htm")):
                    (missing if sure else (weak if weak is not None else set())).add(r)
                continue
            if hit.suffix.lower() in (".html", ".htm") and hit not in want:
                left.add(hit.relative_to(root).as_posix())
                continue
            if hit not in files:
                files.add(hit)
                todo.append(hit)
    if weak is not None:
        weak -= missing
    return sorted(files), sorted(left), sorted(missing)


SKIP_DIRS = {"node_modules", "dist", "build"}


def other_pages(root, files, left):
    """HTML pages under the app folder that are neither copied nor linked statically: pages reached only through a
    page registry or router in a script (K-F16). Folders starting with . or _ and node_modules, dist, build are skipped."""
    root = root.resolve()
    seen = {f.relative_to(root).as_posix() for f in files} | set(left)
    found = set()
    for f in root.rglob("*.htm*"):
        rel = f.relative_to(root)
        if f.suffix.lower() in (".html", ".htm") and not any(x.startswith((".", "_")) or x in SKIP_DIRS for x in rel.parts[:-1]):
            found.add(rel.as_posix())
    return sorted(found - seen)


def cmd_proto(a):
    root = Path(a.root) if a.root else None
    if not root:
        cfg = load()
        root = Path(cfg["_root"]) / kitconf.app(cfg, a.app)["path"] if a.app else die("proto needs --root <app folder> or --app <id>")
    if not root.is_dir():
        die(f"app folder not found: {root}")
    weak = set()
    files, left, missing = proto_files(root, a.pages, weak)
    others = other_pages(root, files, left)
    into = Path(a.into)
    if into.exists() and any(into.iterdir()) and not a.force:
        die(f"{into} is not empty (use --force to add to it)")
    size = 0
    for f in files:
        dst = into / f.relative_to(root.resolve())
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        size += f.stat().st_size
    print(f"Copied {len(a.pages)} page(s) and {len(files) - len(a.pages)} file(s) they load ({size / 1048576:.2f} MB) into {into}")
    if left:
        print(f"NOTE {len(left)} linked page(s) left out (not in --pages; lock or hide every way in): " + ", ".join(left[:12])
              + (" …" if len(left) > 12 else ""))
    if others:
        print(f"NOTE {len(others)} other page(s) of the app are not linked statically (page registry or router in a script): lock or hide every way in, or add them to --pages: " + ", ".join(others[:12])
              + (" …" if len(others) > 12 else ""))
    if missing:
        print(f"NOTE {len(missing)} reference(s) not found in {root} (built at run time, or missing): "
              + ", ".join(missing if a.verbose else missing[:12]) + (" …" if len(missing) > 12 and not a.verbose else ""))
    if weak:
        print(f"NOTE {len(weak)} bare file name(s) quoted in scripts were not found (often sample data, not loaded files)"
              + (": " + ", ".join(sorted(weak)) if a.verbose else "; --verbose lists them"))


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


def last_query(steps):
    """Query string ("?a=1") of the last goto step, or ""."""
    q = ""
    for st in steps or []:
        if isinstance(st, dict) and st.get("goto"):
            m = re.search(r"\?[^#]*", str(st["goto"]))
            q = m.group(0) if m else ""
    return q


def slim_screens(cfg, pkg, shots, pc):
    full = read_json(Path(shots) / "screens.json")
    how = how_map(cfg, pkg / "spec")
    proto = pc.get("prototype", "prototype").strip("/")
    single = proto.endswith(".html")
    out, last = [], {}
    for s in full:
        q = s.get("search") or last_query(s.get("steps"))   # ?demo=1 of the last goto stays in the route
        page = s.get("page", "")
        if not single and page.startswith(proto + "/"):   # captured with the package folder served: no double prefix
            page = page[len(proto) + 1:]
        route = f"{proto}{q}{s.get('hash', '')}" if single else f"{proto}/{page}{q}{s.get('hash', '')}"
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


IMG_REF = re.compile(r"\bscreens/[^\s`)]*\.(?:webp|png|jpe?g)\b")


def image_sentences(cfg, line):
    """Replace the sentences of a line that point at screen images by the locale sentence (once), keep the others.
    When the line already points at the Figma board, the image sentences are only dropped."""
    board = t(cfg, "handoff.spec.imagesOnBoard")
    parts, out, hit = re.split(r"(?<=[.!?])\s+", line.strip()), [], False
    for x in parts:
        if IMG_REF.search(x):
            if not hit:
                out.append(None)
            hit = True
        else:
            out.append(x)
    has_board = any(x and (board in x or "figma" in x.lower()) for x in out)
    return " ".join(x for x in ((board if not has_board else "") if x is None else x for x in out) if x)


def special_name(cfg, pkg, kind):
    """File name of a special spec file (kind archive or crossPage) in this package: the configured name, or an older
    name (handoff.specFiles.legacy) when that file is in the package or README/AGENTS/changelog already point at it."""
    sf = spec_files(cfg)
    names = [sf[kind]] + sf["legacy"][kind]
    for n in names:
        if (pkg / "spec" / n).exists():
            return n
    text = "".join((pkg / f).read_text(encoding="utf-8") for f in ("README.md", "AGENTS.md", "requirements/changelog.md")
                   if (pkg / f).is_file())
    return next((n for n in names[1:] if "spec/" + n in text), sf[kind])


def strip_images(cfg, pkg, pc):
    spec = pkg / "spec"
    if not spec.is_dir():
        return
    col = {t(cfg, "handoff.spec.colImage"), t("en", "handoff.spec.colImage")}
    for p in spec.glob("*.md"):
        s = p.read_text(encoding="utf-8")

        def img(m):   # no link yet (draft, awaiting Figma): a placeholder line that relink / finalize fills later
            u = figma_url(pc, m.group(1))
            return f"Figma: [{m.group(1)}]({u})\n" if u else f"Figma: {t(cfg, 'handoff.spec.figmaPending')}\n"
        s2 = re.sub(r"^!\[[^\]]*\]\(\.\./screens/(%s)\.(?:webp|png|jpe?g)\)\n?" % SCREEN, img, s, flags=re.M)
        # other sentences that point at screen images (e.g. "Images are in `screens/<id>.webp`"): only that sentence
        # becomes the locale sentence; the rest of the line stays
        s2 = re.sub(r"^(\s*(?:[-*]\s+)?)(?!\|)([^\n]*\bscreens/[^\s`)]*\.(?:webp|png|jpe?g)\b[^\n]*)$",
                    lambda m: m.group(1) + image_sentences(cfg, m.group(2)), s2, flags=re.M)
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


FIG_LINE = re.compile(r"^(\s*(?:[-*]\s+)?)Figma\s*:(.*)$")


def refresh_figma(cfg, pkg, pc):
    """K-B4: write the Figma link of each screen into spec/*.md from the screen map (pkg.json > figma): the "Figma:" line
    under "### Sxx · ..." (or a "Figma: [Sxx](...)" line anywhere) and the Figma column of every table whose first column
    is a screen code. Returns the number of lines changed. Screens without a node keep their line."""
    spec = pkg / "spec"
    if not spec.is_dir():
        return 0
    cols = {t(cfg, "annotate.col.figma"), t("en", "annotate.col.figma"), "Figma"}
    n = 0
    for p in sorted(spec.glob("*.md")):
        lines, cur, col, changed = p.read_text(encoding="utf-8").split("\n"), None, None, False
        for i, ln in enumerate(lines):
            h = re.match(r"^#{2,4}\s+(%s)\s+·" % SCREEN, ln)
            if h or re.match(r"^#{1,3}\s", ln):
                cur = h.group(1) if h else None
            if ln.startswith("|"):
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if re.match(r"^\|[\s:|-]+\|$", nxt):          # header row of a table
                    col = next((k for k, c in enumerate(cells) if c in cols), None)
                    continue
                if col is not None and col < len(cells) and re.fullmatch(SCREEN, cells[0]):
                    u = figma_url(pc, cells[0])
                    want = f"[Figma]({u})" if u else cells[col]
                    if cells[col] != want:
                        cells[col] = want
                        lines[i] = "| " + " | ".join(cells) + " |"
                        changed, n = True, n + 1
                continue
            col = None
            m = FIG_LINE.match(ln)
            if not m:
                continue
            sid = (re.match(r"\s*\[(%s)\]" % SCREEN, m.group(2)) or [None, cur])[1]
            u = figma_url(pc, sid) if sid else ""
            if u and ln != f"{m.group(1)}Figma: [{sid}]({u})":
                lines[i] = f"{m.group(1)}Figma: [{sid}]({u})"
                changed, n = True, n + 1
        if changed:
            p.write_text("\n".join(lines), encoding="utf-8")
    return n


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
    arc_name = special_name(cfg, pkg, "archive")
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
    keys = ("annotate.label.needsConfirm", "annotate.label.deviation", "annotate.label.outOfScope", "annotate.label.notVerified",
            "annotate.label.intentional", "annotate.label.noScreen")
    words = [t(cfg, k).rstrip(".") for k in keys] + t(cfg, "handoff.archive.status").split("|")
    words += [w for w in cfg["handoff"].get("grepLabels") or [] if isinstance(w, str)]
    return ", ".join(f'"{w}"' for w in dict.fromkeys(words) if w and not re.fullmatch(r"[a-z]+(\.[A-Za-z]+)+", w))


def board_url(pc):
    if not (pc.get("figma_file") and pc.get("figma_board")):
        return ""
    base = re.sub(r"([?&])node-id=[^&]*", "", pc["figma_file"]).rstrip("?&")
    return base + ("&" if "?" in base else "?") + "node-id=" + pc["figma_board"].replace(":", "-")


def agents(cfg, pkg, pc, archived, label=None):
    has = lambda f: (pkg / f).exists()
    pr = pc.get("prototype", "prototype")
    board = board_url(pc) or t(cfg, "handoff.agents.noBoard")
    cross, arc = special_name(cfg, pkg, "crossPage"), special_name(cfg, pkg, "archive")
    dev_last = t(cfg, "handoff.agents.devCross", file=cross) if has("spec/" + cross) else t(cfg, "handoff.agents.devNoCross")
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
        L.append(t(cfg, "handoff.agents.archived", ids=", ".join(archived), file=arc))
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


def with_pkg_csv(cfg, pc):
    """pkg.json > csv {"feature": ..., "qc": ...} overrides kit.config.json > handoff.csv for this package (a package that
    keeps the headers of its earlier versions)."""
    over = pc.get("csv") if isinstance(pc.get("csv"), dict) else {}
    if not over:
        return cfg
    out = dict(cfg)
    out["handoff"] = dict(cfg["handoff"], csv=dict(cfg["handoff"].get("csv") or {}, **{k: v for k, v in over.items() if v}))
    return out


def cmd_finalize(a):
    pc = read_json(a.config)
    cfg = with_pkg_csv(load(app=pc.get("app") or None), pc)  # the app's DS profile (apps[].ds); pkg.json > csv headers
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
    set_status(a.config, pc, "awaiting-figma" if (nofig or not pc.get("figma_file")) else "final", nofig)
    zpath = (Path(a.zip) if a.zip != "auto" else pkg.parent / (want + ".zip")) if a.zip else ""
    run_hook(cfg, "pre", pkg=pkg, config=a.config, zip=zpath)
    scr = slim_screens(cfg, pkg, a.shots, pc)
    strip_images(cfg, pkg, pc)
    refresh_figma(cfg, pkg, pc)
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
        zip_package(cfg, pkg, zpath)
    if pc.get("status") == "awaiting-figma":
        print(f"Package status: awaiting-figma ({', '.join(nofig[:12]) or 'no figma_file'}). Draft only: do not send it. "
              f"After the wireflow skill has mapped the screens (setmap): pkg.py relink --pkg \"{pkg}\" --config {a.config} --zip")
    run_hook(cfg, "post", pkg=pkg, config=a.config, zip=zpath)


def zip_package(cfg, pkg, z):
    r = subprocess.run([sys.executable, "-I", str(OPTIMIZE), str(pkg), "--zip", str(z),
                        "--target-mb", str(cfg["handoff"].get("maxZipMB", 3))], capture_output=True, text=True)
    print("\n".join(r.stdout.strip().splitlines()[-3:]))
    if r.returncode == 2:
        print(r.stderr)
        die("optimize_package.py: some pages still load .js files that could not be inlined")
    if r.returncode == 1:
        print("NOTE zip is over handoff.maxZipMB: follow the size steps in the handoff skill")


def set_status(config, pc, status, waiting=()):
    """K-B5: pkg.json > status "awaiting-figma" (draft: screens without a Figma node, listed in awaiting_figma) or
    "final". Written back into pkg.json, other keys kept."""
    pc["status"] = status
    if status == "awaiting-figma":
        pc["awaiting_figma"] = list(waiting)
    else:
        pc.pop("awaiting_figma", None)
    Path(config).write_text(json.dumps(pc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_relink(a):
    """K-B5: fill the Figma links of a finalized package (screens.json, spec "Figma:" lines and columns, AGENTS board
    link), set status final and re-zip. Nothing else of the package changes."""
    pc = read_json(a.config)
    cfg = with_pkg_csv(load(app=pc.get("app") or None), pc)
    pkg = Path(a.pkg)
    sj = pkg / "screens" / "screens.json"
    if not sj.is_file():
        die(f"{sj} not found: run pkg.py finalize first (relink only fills Figma links of a finalized package)")
    scr = read_json(sj)
    nofig = [x["id"] for x in scr if not figma_url(pc, x["id"])]
    if nofig or not pc.get("figma_file"):
        die("still no Figma node for " + (", ".join(nofig[:12]) if pc.get("figma_file") else "the package (no figma_file)")
            + ": build or update the board with the wireflow skill, then figma_wireflow.py setmap --config " + str(a.config))
    for e in scr:
        e["figma"] = figma_url(pc, e["id"])
    sj.write_text(json.dumps(scr, ensure_ascii=False, separators=(",", ":")).replace('},{"id"', '},\n{"id"'), encoding="utf-8")
    n = refresh_figma(cfg, pkg, pc)
    ag, board = pkg / "AGENTS.md", board_url(pc)
    if ag.is_file() and board:
        s = ag.read_text(encoding="utf-8")
        s2 = s.replace(t(cfg, "handoff.agents.noBoard"), board, 1) if board not in s else s
        if s2 != s:
            ag.write_text(s2, encoding="utf-8")
            n += 1
    waited = pc.get("awaiting_figma") or []
    set_status(a.config, pc, "final")
    print(f"Relinked {len(scr)} screen(s) in screens.json, {n} line(s) in spec/ and AGENTS.md; status final"
          + (f" (were awaiting Figma: {', '.join(waited)})" if waited else ""))
    zpath = (Path(a.zip) if a.zip != "auto" else pkg.parent / (pkg_name(cfg, pc) + ".zip")) if a.zip else ""
    if a.zip:
        zip_package(cfg, pkg, zpath)
    run_hook(cfg, "post", pkg=pkg, config=a.config, zip=zpath)


# ---------------- smoke ----------------
def package_root(folder):
    """The package folder inside an unzipped package: the folder itself or its only subfolder with screens/ or prototype."""
    folder = Path(folder)
    for c in [folder] + sorted(p for p in folder.iterdir() if p.is_dir()):
        if (c / "screens" / "screens.json").is_file() or (c / "prototype").exists() or (c / "prototype.html").is_file():
            return c
    return None


def smoke_routes(root):
    """[{id, route}] from screens/screens.json (one per distinct route), else the prototype entry."""
    sj, out, seen = root / "screens" / "screens.json", [], set()
    for s in (read_json(sj) if sj.is_file() else []):
        r = s.get("route")
        if r and r not in seen:
            seen.add(r)
            out.append({"id": s.get("id", ""), "route": r})
    if not out:
        entry = next((e for e in ("prototype.html", "prototype/index.html") if (root / e).is_file()), None)
        out = [{"id": "entry", "route": entry}] if entry else []
    return out


def blocked_names(names):
    sys.path.insert(0, str(HERE))
    from optimize_package import BLOCKED, NESTED
    return [n for n in names if Path(n).suffix.lower() in BLOCKED | NESTED]


def smoke_widths(cfg, arg):
    w = arg or ",".join(str(x) for x in ((cfg or {}).get("handoff") or {}).get("smokeWidths") or [400, 768, 1280])
    try:
        ws = [int(x) for x in str(w).split(",") if x.strip()]
    except ValueError:
        ws = []
    if not ws or min(ws) < 200:
        die(f"widths must be comma-separated px values of at least 200 (got {w})")
    return ws


def cmd_smoke(a):
    """K-B9 (steps 4 and 9.5): unzip the package to a temp folder (or use the folder), serve it over HTTP from the
    package folder, open every route of screens.json at each width in Chromium and report page errors, console
    errors, 4xx/5xx, failed requests, broken images and horizontal scroll. A zip is also checked for blocked files."""
    src, cfg = Path(a.package), load(require=False)
    widths = smoke_widths(cfg, a.widths)
    tmp, problems = None, 0
    if src.is_file():
        if not zipfile.is_zipfile(src):
            die(f"not a zip file: {src}")
        z = zipfile.ZipFile(src)
        bad = blocked_names(z.namelist())
        if bad:
            print("ERROR: blocked file(s) in the zip (mail filters): " + ", ".join(bad[:12]))
            problems += len(bad)
        tmp = Path(tempfile.mkdtemp(prefix="pkg-smoke-"))
        z.extractall(tmp)   # zipfile never writes outside the target folder
        base_dir = tmp
    elif src.is_dir():
        base_dir = src
    else:
        die(f"package not found: {src}")
    root = package_root(base_dir)
    if root is None:
        die(f"no package in {src} (no screens/screens.json, prototype/ or prototype.html)")
    routes = smoke_routes(root)
    if not routes:
        die("no route to open: screens/screens.json has no route and there is no prototype entry")

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *x):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    rf = Path(tempfile.mkstemp(prefix="pkg-smoke-", suffix=".json")[1])
    try:
        rf.write_text(json.dumps(routes), encoding="utf-8")
        r = subprocess.run(["node", str(SMOKE), "http://127.0.0.1:%d/" % srv.server_address[1], str(rf),
                            "--widths", ",".join(map(str, widths))], capture_output=True, text=True)
    finally:
        srv.shutdown()
        rf.unlink()
        if tmp and not a.keep:
            shutil.rmtree(tmp, ignore_errors=True)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode or not last.startswith("["):
        print(r.stdout[-2000:] + r.stderr[-2000:])
        die("smoke.js failed")
    res = json.loads(last)
    for x in res:
        for i in x["issues"]:
            print(f"FAIL  {x['id']} {x['route']} @{x['width']}: {i}")
    problems += sum(len(x["issues"]) for x in res)
    print(f"Smoke {src.name}: {len(routes)} route(s) x {len(widths)} width(s) ({', '.join(map(str, widths))} px) from "
          f"{root.relative_to(base_dir).as_posix() if root != base_dir else '.'}: "
          + (f"{problems} problem(s)" if problems else "OK") + (f"; unzipped at {tmp}" if tmp and a.keep else ""))
    if problems:
        sys.exit(1)


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
    assert conf["pageKeys"] == {"tasks": "tasks/index.html"} and conf["allowWhen"][0]["sel"] == "#more" and "seed" not in conf
    assert L["meta"].startswith("lock PBI 1234"), L["meta"]
    html = inject('<html><head><meta charset="utf-8"><script src="app.js"></script></head><body></body></html>', L)
    assert html.count("x-handover-lock") == 1 and inject(html, L).count("x-handover-lock") == 1, "layer is idempotent"
    assert html.index("x-handover-seed") < html.index('src="app.js"') and html.index("charset") < html.index("x-handover-seed"), \
        "seed runs first in <head>, before app scripts"
    assert inject(html, L).count("x-handover-seed") == 1
    pc["lock"]["open_block"] = "#branch"
    assert json.loads(re.search(r"var C = (\{.*?\});\n", render_layer(cfg, pc, "lock")["script"]).group(1))["openBlock"] == "#branch"
    # K-2: only the image sentence of a line is replaced; a line that already points at Figma gets no locale sentence
    board = t(cfg, "handoff.spec.imagesOnBoard")
    assert image_sentences(cfg, "Each step: screen. Images are in `screens/<id>.webp`. Spec in [index](index.md).") == \
        "Each step: screen. " + board + " Spec in [index](index.md).", image_sentences(cfg, "a. b `screens/x.webp`. c.")
    assert image_sentences(cfg, "Images: `screens/S01.png`. Open the Figma board.") == "Open the Figma board."
    # K-3: an older special-file name in the package (or named in README) is the one AGENTS points at
    cfg["handoff"]["specFiles"]["legacy"] = {"archive": ["luu-tru.md"], "crossPage": ["old-cross.md"]}
    (pkg / "spec" / "old-cross.md").write_text("# cross\n")
    (pkg / "README.md").write_text("See `spec/luu-tru.md`.\n")
    assert special_name(cfg, pkg, "crossPage") == "old-cross.md" and special_name(cfg, pkg, "archive") == "luu-tru.md"
    shutil.rmtree(d, ignore_errors=True)
    # 0.10: route keeps the query of the last goto; pkg.json > csv; grep labels; proto copy; baseline comparison
    assert last_query([{"goto": "index.html"}, {"goto": "index.html?demo=1#/x"}, {"click": "#a"}]) == "?demo=1"
    c2 = with_pkg_csv(cfg, {"csv": {"qc": "Old ID,Old steps"}})
    assert csv_header(c2, "qc")[0] == "Old ID,Old steps" and csv_header(cfg, "qc")[0] == "ID,Steps", "pkg.json > csv overrides"
    assert t(cfg, "annotate.label.intentional") in grep_labels(cfg), grep_labels(cfg)
    app = d / "app"
    (app / "assets").mkdir(parents=True)
    (app / "notes").mkdir()
    (app / "index.html").write_text('<link rel="stylesheet" href="ds.css"><img src="assets/a.png" srcset="assets/a2.png 2x">'
                                    '<script src="app.js"></script><a href="notes/index.html">n</a>')
    (app / "ds.css").write_text(".x{background:url('assets/bg.webp')}")
    (app / "app.js").write_text('el.innerHTML = "<img src=\\"" + ROOT + "assets/js.webp\\">"; var u = `${ROOT}assets/t.svg`;')
    for f in ("a.png", "a2.png", "bg.webp", "js.webp", "t.svg", "unused.png"):
        (app / "assets" / f).write_text("x")
    (app / "notes" / "index.html").write_text("<p>other page</p>")
    files, left, _miss = proto_files(app, ["index.html"])
    names = sorted(f.relative_to(app.resolve()).as_posix() for f in files)
    assert names == ["app.js", "assets/a.png", "assets/a2.png", "assets/bg.webp", "assets/js.webp", "assets/t.svg", "ds.css", "index.html"], names
    assert left == ["notes/index.html"], left
    old = {"id": "S01", "page": "a.html", "hash": "#/", "pins": [{"sel": "#b", "style": {"props": {"color": "rgb(0, 0, 0)"}}}]}
    assert screen_change(dict(old, hash="#/x"), old) == "route" and screen_change(old, old) == ""
    assert screen_change({"id": "S01", "page": "a.html", "hash": "#/", "pins": [{"sel": "#b", "style": {"props": {"color": "red"}}}]}, old) == "style"
    # K-F16: bare file names in scripts are weak (counted, not listed); pages reached only by a script registry are listed
    (app / "app.js").write_text((app / "app.js").read_text() + ' var demo = ["report-q3.pdf", "data/missing.json"];'
                                ' var PAGES = {lib: "library/"};')
    (app / "library").mkdir()
    (app / "library" / "index.html").write_text("<p>library</p>")
    (app / "_shell").mkdir()
    (app / "_shell" / "index.html").write_text("<p>source</p>")
    weak = set()
    files, left, miss = proto_files(app, ["index.html"], weak)
    assert miss == ["data/missing.json"] and weak == {"report-q3.pdf"}, (miss, weak)
    assert other_pages(app, files, left) == ["library/index.html"], other_pages(app, files, left)
    # K-F15: nav_functions keep the string form; {name, base} and lock.nav_base set the base of relative paths
    assert nav_functions({"nav_functions": ["appNav.go", {"name": "X.nav", "base": "app"}]}) == \
        [{"name": "appNav.go", "base": "page"}, {"name": "X.nav", "base": "app"}]
    assert nav_functions({"nav_functions": ["go"], "nav_base": "app"}) == [{"name": "go", "base": "app"}]
    # K-B4: Figma lines and the Figma column of the screen table come from pkg.json > figma
    e = Path(tempfile.mkdtemp(prefix="pkg-selftest-"))
    (e / "spec").mkdir()
    (e / "spec" / "index.md").write_text("# x\n\n| Code | Name | Page · route | Figma | Spec |\n|---|---|---|---|---|\n"
                                         "| S01 | Home | `index.html#/` | — | FR-01 |\n| S02 | New | `#/n` | [Figma](old) | FR-01 |\n\nFigma: board\n")
    (e / "spec" / "FR-01.md").write_text("# FR-01\n\n### S01 · Home\nRoute: x\nFigma: none yet\n\n### S02 · New\nFigma: [S02](old)\n"
                                         "\n### S03 · Later\nFigma: none yet\n")
    pf = {"figma_file": "https://www.figma.com/design/KEY/x", "figma": {"S01": "1:2", "S02": "1:3"}}
    assert refresh_figma(cfg, e, pf) == 4 and refresh_figma(cfg, e, pf) == 0
    ix, u1 = (e / "spec" / "index.md").read_text(), "https://www.figma.com/design/KEY/x?node-id=1-2"
    assert f"| S01 | Home | `index.html#/` | [Figma]({u1}) | FR-01 |" in ix and "Figma: board" in ix, ix
    un = (e / "spec" / "FR-01.md").read_text()
    assert f"Figma: [S01]({u1})" in un and "Figma: [S02](https://www.figma.com/design/KEY/x?node-id=1-3)" in un \
        and un.rstrip().endswith("Figma: none yet"), un
    # K-B5: status in pkg.json
    cf = e / "pkg.json"
    pj = {"pbi": "1", "figma": {}}
    set_status(cf, pj, "awaiting-figma", ["S03"])
    assert json.loads(cf.read_text())["awaiting_figma"] == ["S03"]
    set_status(cf, pj, "final")
    assert json.loads(cf.read_text()) == {"pbi": "1", "figma": {}, "status": "final"}
    # K-B9: package root and routes of an unzipped package, blocked names, widths
    (e / "Design - 1" / "screens").mkdir(parents=True)
    (e / "Design - 1" / "screens" / "screens.json").write_text(json.dumps(
        [{"id": "S01", "route": "prototype/index.html#/"}, {"id": "S02", "route": "prototype/index.html#/"},
         {"id": "S03", "route": "prototype/b/index.html"}]))
    shutil.rmtree(e / "spec")
    cf.unlink()
    root = package_root(e)
    assert root == e / "Design - 1" and [x["id"] for x in smoke_routes(root)] == ["S01", "S03"]
    assert blocked_names(["a/x.html", "a/y.js", "b.zip", "c.map"]) == ["a/y.js", "b.zip", "c.map"]
    assert smoke_widths({"handoff": {"smokeWidths": [390, 1280]}}, "") == [390, 1280] and smoke_widths(None, "400,800") == [400, 800]
    shutil.rmtree(e, ignore_errors=True)
    shutil.rmtree(d, ignore_errors=True)
    print("pkg.py selftest OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    ap = argparse.ArgumentParser(description="Handoff package pipeline (see the module docstring for details).",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="{init,name,layer,capture,proto,finalize,relink,smoke}")
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
    c.add_argument("--app", default="", help="app id: token names from its DS profile (apps[].ds); default manifest.app")
    c.add_argument("--threshold", type=float, default=0.001,
                   help="share of different pixels that marks a screen as changed (default 0.1%%)")
    c.add_argument("--baseline", default="", help="screens.json or image folder of the previous package: list screens changed since it")
    pr = sub.add_parser("proto", help="copy pages and only the shared files they load into the package prototype folder")
    pr.add_argument("--pages", nargs="+", required=True, help="pages relative to the app folder (index.html notes/index.html)")
    pr.add_argument("--into", required=True, help="target folder, e.g. <package>/prototype")
    pr.add_argument("--root", default="", help="app folder (default: apps[].path of --app)")
    pr.add_argument("--app", default="")
    pr.add_argument("--force", action="store_true", help="copy into a folder that is not empty")
    pr.add_argument("--verbose", action="store_true", help="list every reference not found, bare file names in scripts too")
    f = sub.add_parser("finalize", help="slim screens.json, drop images, archive, AGENTS.md, check, zip")
    f.add_argument("--pkg", required=True)
    f.add_argument("--shots", required=True)
    f.add_argument("--config", required=True)
    f.add_argument("--zip", nargs="?", const="auto", default="", help="zip path; no value = <zipName>.zip next to the package")
    f.add_argument("--allow-missing-figma", action="store_true", help="only when the user accepts a draft without a wireflow")
    rl = sub.add_parser("relink", help="fill Figma links of a finalized (awaiting-figma) package, status final, re-zip")
    rl.add_argument("--pkg", required=True)
    rl.add_argument("--config", required=True)
    rl.add_argument("--zip", nargs="?", const="auto", default="", help="zip path; no value = <zipName>.zip next to the package")
    sm = sub.add_parser("smoke", help="run the unpacked package in Chromium: errors, 4xx, broken images, horizontal scroll")
    sm.add_argument("package", help="package zip or folder")
    sm.add_argument("--widths", default="", help="comma-separated px (default kit.config.json > handoff.smokeWidths)")
    sm.add_argument("--keep", action="store_true", help="keep the unzipped copy")
    a = ap.parse_args()
    {"init": cmd_init, "name": cmd_name, "layer": cmd_layer, "capture": cmd_capture, "proto": cmd_proto, "finalize": cmd_finalize,
     "relink": cmd_relink, "smoke": cmd_smoke}[a.cmd](a)


if __name__ == "__main__":
    main()
