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

What this script does not do (the sync skill does it, with the user): package bumps in react/vue apps,
control inventory, local components, hard-coded values, tests, commits.
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from kitconf import load as load_cfg, ds_path, t, app as get_app  # noqa: E402

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


def cmd_status(cfg, a):
    ds = need_ds(cfg)
    rx = block_rx(ds)
    print("DS %s, latest version %s" % (ds["label"], ds["version"]))
    for app in cfg["apps"]:
        if a.app and app["id"] != a.app:
            continue
        files = files_of(cfg, app)
        marked = [f for f in files if rx.search(f.read_text(encoding="utf-8", errors="replace"))]
        v = found_version(cfg, app)
        state = "unknown" if not v else ("up to date" if vtuple(v) >= vtuple(ds["version"]) else "behind")
        print("== %s (%s, stack %s): version %s, %s; %d file(s) with the DS block" % (
            app["id"], app.get("type", "single"), app.get("stack") or cfg["stack"], v or "not found", state, len(marked)))
        for f in marked:
            print("   " + f.relative_to(cfg["_root"]).as_posix())
    return 0


def changelog_sections(cfg):
    p = Path(cfg["_ds_dir"]) / "CHANGELOG.md"
    if not p.is_file():
        sys.exit("ERROR: no CHANGELOG.md in the DS profile folder (%s)." % cfg["ds"])
    secs, cur = [], None
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+\[?v?(%s)\]?" % VER, line)
        if m:
            cur = [m.group(1), [line]]
            secs.append(cur)
        elif cur:
            cur[1].append(line)
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


def cmd_apply(cfg, a):
    ds = need_ds(cfg)
    apps = [get_app(cfg, a.app)] if a.app else cfg["apps"]
    if not apps:
        sys.exit("ERROR: no apps in kit.config.json > apps.")
    body = bundle_text(cfg, a.bundle)
    new = ds["version"]
    label_new = ds["version_label"]["text"].format(label=ds["label"], version=new, name=ds.get("name"))
    b_rx, m_rx, l_rx = block_rx(ds), meta_rx(ds), label_rx(ds)
    for app in apps:
        changed, blocks = [], 0
        for f in files_of(cfg, app):
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["status", "changes", "apply", "note"])
    ap.add_argument("--app")
    ap.add_argument("--from", dest="from_")
    ap.add_argument("--to")
    ap.add_argument("--bundle")
    ap.add_argument("--summary")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    cfg = load_cfg()
    sys.exit({"status": cmd_status, "changes": cmd_changes, "apply": cmd_apply, "note": cmd_note}[a.cmd](cfg, a))


if __name__ == "__main__":
    main()
