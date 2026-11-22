#!/usr/bin/env python3
"""Bring the DS version of the profile (ds.json > version) into the apps of kit.config.json.

Commands:
  status                  per app: DS version found, latest version, files with the embedded DS block
  changes --from X [--to Y]
                          print the DS changelog sections after X up to Y (default: latest)
  apply [--app ID] [--dry-run] [--bundle PATH]
                          in every .html/.css file of the app (dist, build, node_modules skipped):
                          replace the CSS between the ds.json > css.marker comments with the DS bundle,
                          set <meta name="<version_label.meta>"> and the version label text to the latest version.
                          Re-runnable. Touches nothing outside the markers and the version label.
  note --app ID --from X --to Y --summary TEXT [--dry-run]
                          append a localized entry to kit.config.json > paths.changelog
Options: --date YYYY-MM-DD (note; default today)

Project commands (extension point): when kit.config.json > sync.command (or ds.json > sync.command) is set, `apply`
runs that command in the project root instead of replacing blocks; when sync.check is set, `status` runs it instead
of reading versions, and `apply --dry-run` runs it and prints the command it would run. {app} in a command becomes the
--app value (empty when none). The command's output and exit code are reported as they are. --builtin forces the
kit's own status/apply.
  sync.prepare  runs before the sync (project or built-in), e.g. a project that must rebuild its DS from source first.
  sync.post     runs after the sync and the change report (e.g. the project's own docs check); never parsed.
After apply (not --dry-run) the script lists the files that changed per app and the LOCAL blocks
(kit.config.json > local.marker) that were added, removed or changed, then says to update the local registry.
css.load "link" (ds.json or apps[].css): the built-in apply copies the bundle to each app's css.linkPath file (whole
file) instead of replacing a marked block; status lists that file.
DS changelog: ds.json > changelog {"path", "format": "md" | "json"} (default CHANGELOG.md in the profile folder). json =
a list of entries (or {"entries": [...]}) with a version key (changelog.versionKey, default "version" or "v"); an
optional changelog.match {key: value} keeps only matching entries, changelog.fields lists the keys to print (default:
every text field except the version and the match keys).
An app with its own DS profile (kit.config.json > apps[].ds) is compared with and synced from that profile (bundle,
version, label); changes and note --app read the app's profile too.
  sync_ds.py --selftest   checks of the project-command switch (no app files touched)

What this script does not do (the sync skill does it, with the user): package bumps in react/vue apps,
control inventory, local components, hard-coded values, tests, commits.
"""
import argparse
import datetime
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import hashlib  # noqa: E402
import json  # noqa: E402
from kitconf import load as load_cfg, ds_path, t, app as get_app, project_command, for_app, css_load, ds_changelog, \
    run_command, fill_command  # noqa: E402

SKIP_DIRS = {"node_modules", "dist", "build", ".git", ".vite", "coverage"}
EXT = {".html", ".htm", ".css"}
VER = r"\d+(?:\.\d+){1,2}(?:-[0-9A-Za-z.]+)?"


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v.split("-")[0])[:3]) if v else ()


def need_ds(cfg):
    if not cfg.get("_ds"):
        sys.exit("ERROR: DS profile not found (kit.config.json > ds).")
    return cfg["_ds"]


def files_of(cfg, a):
    base = Path(cfg["_root"]) / a["path"]
    if base.is_file():
        return [base]
    return [p for p in sorted(base.rglob("*")) if p.is_file() and p.suffix in EXT
            and not (set(p.relative_to(base).parts[:-1]) & SKIP_DIRS)]


def block_rx(ds):
    mk = ds["css"]["marker"]
    return re.compile(r"(/\*\s*%s[^*]*\*/)(.*?)(/\*\s*%s[^*]*\*/)" % (re.escape(mk["begin"]), re.escape(mk["end"])), re.S)


def meta_rx(ds):
    return re.compile(r'(<meta\s+name="%s"\s+content=")([^"]*)(")' % re.escape(ds["version_label"]["meta"]))


def label_rx(ds):
    """Regex for the version label text with any version, built from ds.json > version_label.text."""
    parts = re.split(r"(\{\w+\})", ds["version_label"]["text"])
    out = []
    for p in parts:
        if p == "{version}":
            out.append("(%s)" % VER)
        elif p == "{label}":
            out.append(re.escape(ds["label"]))
        elif p == "{name}":
            out.append(re.escape(ds.get("name") or ""))
        else:
            out.append(r"\s+".join(re.escape(x) for x in p.split()) if p.strip() else (r"\s+" if p else ""))
    return re.compile("".join(out))


def found_version(cfg, a):
    ds = need_ds(cfg)
    m_rx, l_rx = meta_rx(ds), label_rx(ds)
    for f in files_of(cfg, a):
        s = f.read_text(encoding="utf-8", errors="replace")
        m = m_rx.search(s) or l_rx.search(s)
        if m:
            v = re.search(VER, m.group(2) if m.re is m_rx else m.group(1))
            if v:
                return v.group(0)
    return ""


def bundle_text(cfg, override):
    ds = need_ds(cfg)
    src = override or ds_path(cfg, ds["css"]["bundle"])
    if not src:
        sys.exit("ERROR: ds.json > css.bundle is not set; pass --bundle PATH.")
    if "://" in src:
        sys.exit("ERROR: css.bundle is a URL (%s). Download it, then pass --bundle PATH." % src)
    p = Path(src)
    if not p.is_file():
        sys.exit("ERROR: DS bundle not found: %s" % src)
    s = p.read_text(encoding="utf-8")
    m = block_rx(ds).search(s)  # the bundle may carry its own markers: keep only the inside
    return (m.group(2) if m else s).strip("\n")


def run_project(cfg, a, key):
    """Run the project command sync.<key> when set (and not --builtin). Returns its exit code, or None."""
    cmd = None if getattr(a, "builtin", False) else project_command(cfg, "sync." + key)
    if not cmd:
        return None
    line = cmd.replace("{app}", shlex.quote(a.app) if a.app else "")
    print("Project %s (sync.%s): %s" % ("check" if key == "check" else "sync", key, line))
    r = subprocess.run(line, shell=True, cwd=cfg["_root"], capture_output=True, text=True)
    out = (r.stdout + r.stderr).rstrip()
    if out:
        print(out)
    print("sync.%s exit code %d" % (key, r.returncode))
    return 1 if r.returncode else 0


def cmd_status(cfg, a):
    print("NOTE status compares apps with the DS as built in the profile (bundle, version), not with DS sources."
          + (" sync.prepare is set: after a DS source edit run apply, which runs it first." if project_command(cfg, "sync.prepare") else ""))
    rc = run_project(cfg, a, "check")
    if rc is not None:
        return rc
    ds = need_ds(cfg)
    print("DS %s, latest version %s" % (ds["label"], ds["version"]))
    for app in cfg["apps"]:
        if a.app and app["id"] != a.app:
            continue
        c = for_app(cfg, app["id"])  # apps[].ds: the app follows its own DS profile and version numbering
        ds = need_ds(c)
        rx = block_rx(ds)
        if c.get("ds") != cfg.get("ds"):
            print("   (%s uses the DS profile %s: %s %s)" % (app["id"], c["ds"], ds["label"], ds["version"]))
        files = files_of(c, app)
        marked = [f for f in files if rx.search(f.read_text(encoding="utf-8", errors="replace"))]
        lp = css_load(c, app["id"])["linkPath"]
        if lp:
            lf = Path(cfg["_root"]) / app["path"] / lp
            same = lf.is_file() and lf.read_text(encoding="utf-8", errors="replace").strip("\n") == bundle_text(c, None)
            print("   linked DS file %s: %s" % ((Path(app["path"]) / lp).as_posix(), "same as the bundle" if same else
                                                 "differs from the bundle" if lf.is_file() else "missing"))
        v = found_version(c, app)
        state = "unknown" if not v else ("up to date" if vtuple(v) >= vtuple(ds["version"]) else "behind")
        print("== %s (%s, stack %s): version %s, %s; %d file(s) with the DS block" % (
            app["id"], app.get("type", "single"), app.get("stack") or cfg["stack"], v or "not found", state, len(marked)))
        for f in marked:
            print("   " + f.relative_to(cfg["_root"]).as_posix())
    return 0


def changelog_sections(cfg):
    path, fmt = ds_changelog(cfg)
    p = Path(path)
    if not p.is_file():
        sys.exit("ERROR: DS changelog not found: %s. Set ds.json > changelog {\"path\": ..., \"format\": \"md\" | \"json\"} "
                 "(path relative to the profile folder or the project root), or add CHANGELOG.md to %s." % (p, cfg["ds"]))
    if fmt == "json":
        return json_sections(cfg, p)
    secs, cur = [], None
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+\[?v?(%s)\]?" % VER, line)
        if m:
            cur = [m.group(1), [line]]
            secs.append(cur)
        elif cur:
            cur[1].append(line)
    return secs


def json_sections(cfg, p):
    """[version, lines] per entry of a JSON changelog: a list of objects (or {"entries": [...]})."""
    ch = (cfg["_ds"].get("changelog") or {}) if isinstance(cfg["_ds"].get("changelog"), dict) else {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        sys.exit("ERROR: %s is not valid JSON: %s" % (p, e))
    items = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(items, list):
        sys.exit("ERROR: %s: expected a list of entries (or {\"entries\": [...]})." % p)
    vk, match = ch.get("versionKey"), ch.get("match") or {}
    secs = []
    for e in items:
        if not isinstance(e, dict) or any(str(e.get(k)) != str(v) for k, v in match.items()):
            continue
        v = str(e.get(vk) if vk else e.get("version") or e.get("v") or "")
        if not re.fullmatch(VER, v):
            continue
        keys = ch.get("fields") or [k for k in e if k != (vk or ("version" if "version" in e else "v")) and k not in match]
        texts = [str(e[k]) for k in keys if isinstance(e.get(k), str) and e[k].strip()]
        secs.append([v, ["## %s" % v] + ["- " + x for x in texts]])
    return secs


def cmd_changes(cfg, a):
    ds = need_ds(cfg)
    if not a.from_:
        sys.exit("ERROR: changes needs --from X (the version the app uses now).")
    lo, hi = vtuple(a.from_), vtuple(a.to or ds["version"])
    secs = [s for s in changelog_sections(cfg) if lo < vtuple(s[0]) <= hi]
    if not secs:
        print("No changelog sections between %s and %s." % (a.from_, a.to or ds["version"]))
    for _v, lines in sorted(secs, key=lambda s: vtuple(s[0])):
        print("\n".join(lines).rstrip() + "\n")
    return 0


def snapshot(cfg, apps):
    """{relative path: sha1} of every file of the apps (dist, build, node_modules skipped), and the LOCAL blocks."""
    files, blocks = {}, {}
    marker = re.escape((cfg.get("local") or {}).get("marker") or "LOCAL")
    head = re.compile(r"/\*\s*%s:\s*(.*?)\*/" % marker, re.S)
    root = Path(cfg["_root"])
    for app in apps:
        base = root / app["path"]
        paths = [base] if base.is_file() else [p for p in sorted(base.rglob("*")) if p.is_file()
                                                and not (set(p.relative_to(base).parts[:-1]) & SKIP_DIRS)] if base.exists() else []
        for p in paths:
            data = p.read_bytes()
            rel = p.relative_to(root).as_posix()
            files[rel] = hashlib.sha1(data).hexdigest()
            if p.suffix.lower() in (".html", ".htm", ".css", ".vue", ".js", ".jsx", ".tsx", ".scss"):
                txt = data.decode("utf-8", errors="replace")
                ms = list(head.finditer(txt))
                for i, m in enumerate(ms):
                    name = re.sub(r"\s+", " ", re.sub(r"\n\s*\*(?!/)", "\n", m.group(1))).strip()
                    body = txt[m.end():ms[i + 1].start() if i + 1 < len(ms) else len(txt)]
                    blocks[(app["id"], name)] = hashlib.sha1(re.sub(r"\s+", " ", body).encode()).hexdigest()
    return files, blocks


def change_report(cfg, apps, before, after):
    """Print the files that changed per app and the LOCAL blocks added, removed or changed by the sync."""
    (f0, b0), (f1, b1) = before, after
    changed = sorted(k for k in set(f0) | set(f1) if f0.get(k) != f1.get(k))
    print("Changes made by the sync:")
    for app in apps:
        pre = Path(app["path"]).as_posix().rstrip("/")
        mine = [k for k in changed if k == pre or k.startswith(pre + "/")]
        print("== %s: %d file(s) changed" % (app["id"], len(mine)))
        for k in mine[:40]:
            print("   %s%s" % (k, " (new)" if k not in f0 else " (removed)" if k not in f1 else ""))
        if len(mine) > 40:
            print("   … %d more" % (len(mine) - 40))
        loc = [(n, "added" if (app["id"], n) not in b0 else "removed" if (app["id"], n) not in b1 else "changed")
               for (aid, n) in sorted(set(b0) | set(b1)) if aid == app["id"] and b0.get((aid, n)) != b1.get((aid, n))]
        for n, how in loc:
            print("   LOCAL block %s: %s" % (how, n))
        if loc:
            print("   NEXT update the local registry (%s) and fill the decision of each changed entry."
                  % ("local.command.update" if project_command(cfg, "local.command.update") else "contribute: registry.py update"))


def run_hook(cfg, a, key):
    """sync.prepare / sync.post: a project command, its output and exit code. None when not set."""
    cmd = project_command(cfg, "sync." + key)
    if not cmd:
        return None
    return 1 if run_command(cfg, fill_command(cmd, app=a.app or "", root=cfg["_root"]), "sync." + key) else 0


def cmd_apply(cfg, a):
    scope = [get_app(cfg, a.app)] if a.app else cfg["apps"]
    if a.dry_run and project_command(cfg, "sync.prepare"):
        print("Dry run: would run sync.prepare first: %s" % project_command(cfg, "sync.prepare"))
    elif run_hook(cfg, a, "prepare"):
        sys.exit("ERROR: sync.prepare failed: nothing synced.")
    before = None if a.dry_run else snapshot(cfg, scope)
    if not a.builtin and project_command(cfg, "sync.command"):
        if a.dry_run:
            print("Dry run: would run sync.command: %s" % project_command(cfg, "sync.command").replace("{app}", a.app or ""))
            rc = run_project(cfg, a, "check")
            return 0 if rc is None else rc
        rc = run_project(cfg, a, "command")
    else:
        rc = builtin_apply(cfg, a)
    if not a.dry_run:
        change_report(cfg, scope, before, snapshot(cfg, scope))
        if run_hook(cfg, a, "post"):
            print("ERROR: sync.post failed (exit code above).")
            return 1
    return rc


def builtin_apply(cfg, a):
    apps = [get_app(cfg, a.app)] if a.app else cfg["apps"]
    if not apps:
        sys.exit("ERROR: no apps in kit.config.json > apps.")
    for app in apps:
        c = for_app(cfg, app["id"])  # apps[].ds: bundle, version and label of the app's own DS profile
        ds = need_ds(c)
        body = bundle_text(c, a.bundle)
        new = ds["version"]
        label_new = ds["version_label"]["text"].format(label=ds["label"], version=new, name=ds.get("name"))
        b_rx, m_rx, l_rx = block_rx(ds), meta_rx(ds), label_rx(ds)
        changed, blocks = [], 0
        lp = css_load(c, app["id"])["linkPath"]
        if lp:  # css.load link: the app links one DS file; it becomes the bundle as a whole
            lf = Path(cfg["_root"]) / app["path"] / lp
            old = lf.read_text(encoding="utf-8") if lf.is_file() else None
            if old != body + "\n":
                changed.append(lf)
                if not a.dry_run:
                    lf.parent.mkdir(parents=True, exist_ok=True)
                    lf.write_text(body + "\n", encoding="utf-8")
            blocks += 1
        for f in files_of(cfg, app):
            if lp and f.resolve() == (Path(cfg["_root"]) / app["path"] / lp).resolve():
                continue
            s = f.read_text(encoding="utf-8")
            n_blocks = len(b_rx.findall(s))
            blocks += n_blocks
            u = b_rx.sub(lambda m: m.group(1) + "\n" + body + "\n" + m.group(3), s)
            u = m_rx.sub(lambda m: m.group(1) + new + m.group(3), u)
            u = l_rx.sub(label_new, u)
            if u != s:
                changed.append(f)
                if not a.dry_run:
                    f.write_text(u, encoding="utf-8")
        verb = "would change" if a.dry_run else "changed"
        print("== %s: %d DS block(s), %s %d file(s)" % (app["id"], blocks, verb, len(changed)))
        for f in changed:
            print("   " + f.relative_to(cfg["_root"]).as_posix())
        if not blocks:
            hint = ("embed the DS between /* %s */ and /* %s */ first" % (ds["css"]["marker"]["begin"], ds["css"]["marker"]["end"])
                    if (app.get("stack") or cfg["stack"]) == "html" else "bump the DS package or re-import the tokens in src/index.css")
            print("   NOTE: no DS block found; %s." % hint)
        if app.get("build"):
            print("   NEXT: run the app build: %s" % app["build"])
    return 0


def cmd_note(cfg, a):
    ds = need_ds(cfg)
    app = get_app(cfg, a.app) if a.app else sys.exit("ERROR: note needs --app ID.")
    if not (a.from_ and a.to and a.summary):
        sys.exit("ERROR: note needs --from, --to and --summary.")
    line = t(cfg, "sync.changelog.entry", date=a.date, app=app.get("name", app["id"]), label=ds["label"],
             **{"from": a.from_, "to": a.to}, summary=a.summary)
    p = Path(cfg["_root"]) / cfg["paths"]["changelog"]
    if a.dry_run:
        print(line)
        return 0
    old = p.read_text(encoding="utf-8") if p.is_file() else ""
    p.write_text(old.rstrip("\n") + ("\n" if old else "") + line + "\n", encoding="utf-8")
    print("Appended to %s: %s" % (cfg["paths"]["changelog"], line))
    return 0


def selftest():
    import json
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="sync-selftest-"))
    (d / "ds" / "acme").mkdir(parents=True)
    (d / "ds" / "acme" / "ds.json").write_text(json.dumps({"name": "acme", "version": "1.0.0"}))
    py = shlex.quote(sys.executable)
    (d / "kit.config.json").write_text(json.dumps({"ds": "ds/acme", "apps": [{"id": "acme-web", "path": "apps/acme-web"}],
        "sync": {"command": py + " -c \"open('ran.txt','w').write('{app}')\"",
                 "check": py + " -c \"import sys; print('2 apps behind'); sys.exit(3)\""}}))
    cfg = load_cfg(d)
    A = lambda **k: argparse.Namespace(**dict({"app": None, "dry_run": False, "builtin": False, "bundle": None}, **k))
    assert cmd_status(cfg, A()) == 1, "status runs sync.check and reports failure"
    assert cmd_apply(cfg, A(app="acme-web", dry_run=True)) == 1 and not (d / "ran.txt").exists(), "dry run never syncs"
    assert cmd_apply(cfg, A(app="acme-web")) == 0 and (d / "ran.txt").read_text() == "acme-web", "apply runs sync.command"
    cfg["sync"] = {"command": None, "check": None}
    assert run_project(cfg, A(), "check") is None, "no command: built-in behaviour"
    # sync.prepare before, sync.post after, change report with a LOCAL block, built-in apply in css.load link mode
    import contextlib
    import io
    app = d / "apps" / "acme-web"
    app.mkdir(parents=True)
    (app / "index.html").write_text('<meta name="ds-version" content="0.9.0"><style>/* LOCAL: Chip */ .x-chip{gap:4px}</style>')
    (d / "ds" / "acme" / "dist").mkdir()
    (d / "ds" / "acme" / "dist" / "acme.css").write_text(":root{--ds-a:1px}")
    (d / "ds" / "acme" / "ds.json").write_text(json.dumps({"name": "acme", "version": "1.0.0", "css": {"bundle": "dist/acme.css", "load": "link"},
        "changelog": {"path": "news.json", "match": {"area": "web"}}}))
    (d / "ds" / "acme" / "news.json").write_text(json.dumps([{"v": "1.0.0", "area": "web", "title": "New chip"},
                                                             {"v": "0.9.5", "area": "vue", "title": "Vue only"}]))
    edit = "import re,pathlib; p=pathlib.Path('apps/acme-web/index.html'); p.write_text(p.read_text().replace('gap:4px','gap:8px'))"
    (d / "kit.config.json").write_text(json.dumps({"ds": "ds/acme", "apps": [{"id": "acme-web", "path": "apps/acme-web"}],
        "sync": {"prepare": py + " -c \"open('order.txt','a').write('prepare ')\"",
                 "command": py + " -c \"open('order.txt','a').write('sync '); " + edit.replace('"', '\\"') + "\"",
                 "post": py + " -c \"open('order.txt','a').write('post')\""}}))
    cfg = load_cfg(d)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert cmd_apply(cfg, A(app="acme-web")) == 0
    assert (d / "order.txt").read_text() == "prepare sync post", (d / "order.txt").read_text()
    assert "apps/acme-web/index.html" in out.getvalue() and "LOCAL block changed: Chip" in out.getvalue(), out.getvalue()
    assert [v for v, _ in changelog_sections(cfg)] == ["1.0.0"], "json changelog with match"
    cfg["sync"] = {"command": None, "check": None}
    with contextlib.redirect_stdout(io.StringIO()):
        assert cmd_apply(cfg, A(app="acme-web")) == 0
    assert (app / "acme.css").read_text() == ":root{--ds-a:1px}\n" and 'content="1.0.0"' in (app / "index.html").read_text(), "link mode"
    cfg["_ds"]["changelog"] = {"path": "missing.md"}
    try:
        changelog_sections(cfg)
        raise AssertionError("missing changelog accepted")
    except SystemExit as e:
        assert "ds.json > changelog" in str(e), e
    print("sync_ds.py selftest OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["status", "changes", "apply", "note"])
    ap.add_argument("--app")
    ap.add_argument("--from", dest="from_")
    ap.add_argument("--to")
    ap.add_argument("--bundle")
    ap.add_argument("--summary")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--builtin", action="store_true", help="ignore sync.command / sync.check and use the kit's own status/apply")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    cfg = load_cfg() if a.cmd in ("status", "apply") else load_cfg(app=a.app)  # status/apply resolve apps[].ds per app
    sys.exit({"status": cmd_status, "changes": cmd_changes, "apply": cmd_apply, "note": cmd_note}[a.cmd](cfg, a))


if __name__ == "__main__":
    main()
