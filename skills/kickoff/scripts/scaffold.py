#!/usr/bin/env python3
"""Create a prototype app from the kit template of the project stack.

Usage:
  scaffold.py --app acme-web --name "Acme Web" [--type single|multi|spa] [--path apps/acme-web] [--dry-run]

What it does:
  - reads kit.config.json and the DS profile through scripts/kitconf.py
  - picks the template: html + single -> templates/html, html + multi -> templates/html-multi,
    react -> templates/react, vue -> templates/vue (type spa)
  - copies it into the app folder (kit.config.json > apps[].path, default apps/<app>) and fills the placeholders:
    DS CSS (ds.json > css.bundle, html stacks), version label and <meta>, theming defaults on <html>,
    breakpoints, local-component prefix and marker
  - react / vue: copies the DS bundle to src/ds/<bundle file>, wrapped in the ds.json > css.marker comments
  - html multi: runs _shell/build.py build so every page holds the shared shell
  - writes templates/CLAUDE.md to the project CLAUDE.md only when the project has none

It never overwrites a file: when a target file exists it writes nothing and exits 1 with the list.
It does not run npm install, edit kit.config.json, commit or push.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, ds_path, version_label, STACKS  # noqa: E402

TEMPLATES = KIT / "templates"
SKIP = {"node_modules", "dist", "dist-handoff", "__pycache__", ".vite"}
PLACEHOLDER = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
LANGUAGES = {"en": "English", "vi": "Vietnamese", "fr": "French", "de": "German", "es": "Spanish", "pt": "Portuguese",
             "it": "Italian", "nl": "Dutch", "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "th": "Thai",
             "id": "Indonesian"}
THEMING_ORDER = ("brand", "mode", "density")


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def html_attr(v):
    return str(v).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def theming_defaults(theming):
    keys = [k for k in THEMING_ORDER if k in theming] + [k for k in theming if k not in THEMING_ORDER]
    out = []
    for k in keys:
        t = theming.get(k) or {}
        value = t.get("default") or (t.get("values") or [None])[0]
        if t.get("attr") and value:
            out.append((t["attr"], value))
    return out


def bundle_inside(text, marker):
    """The bundle may carry its own DS markers: keep only what is between them."""
    rx = re.compile(r"/\*\s*%s[^*]*\*/(.*?)/\*\s*%s[^*]*\*/" % (re.escape(marker["begin"]), re.escape(marker["end"])), re.S)
    m = rx.search(text)
    return (m.group(1) if m else text).strip("\n")


def template_for(stack, app_type):
    if stack == "html":
        return TEMPLATES / ("html-multi" if app_type == "multi" else "html")
    return TEMPLATES / stack


def template_files(tdir):
    for f in sorted(tdir.rglob("*")):
        if f.is_file() and not (set(f.relative_to(tdir).parts) & SKIP):
            yield f


def fill(text, values, src):
    missing = sorted({m for m in PLACEHOLDER.findall(text) if m not in values})
    if missing:
        die("template %s uses unknown placeholder(s): %s" % (src, ", ".join(missing)))
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], text)


def main():
    ap = argparse.ArgumentParser(description="Create a prototype app from the kit template of the project stack.")
    ap.add_argument("--app", required=True, help="app id, lowercase with hyphens (e.g. acme-web)")
    ap.add_argument("--name", required=True, help='display name (e.g. "Acme Web")')
    ap.add_argument("--type", choices=("single", "multi", "spa"), help="html: single (default) or multi; react/vue: spa")
    ap.add_argument("--path", help="app folder relative to the project root (default: kit.config.json > apps[].path or apps/<app>)")
    ap.add_argument("--stack", choices=STACKS, help="stack of this app (default: apps[].stack, else kit.config.json > stack)")
    ap.add_argument("--dry-run", action="store_true", help="list what would be written, write nothing")
    a = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", a.app):
        die("--app must be lowercase letters, digits and hyphens (found '%s')" % a.app)
    if not a.name.strip() or re.search(r'["\\<>&`]', a.name):
        die('--name must not be empty or contain " \\ < > & or a backtick')

    cfg = load()
    root = Path(cfg["_root"])
    declared = next((x for x in cfg["apps"] if x.get("id") == a.app), None)
    stack = a.stack or (declared or {}).get("stack") or cfg["stack"]  # apps[].stack overrides the project stack
    if stack not in STACKS:
        die("kit.config.json > stack must be one of %s (found '%s')" % (", ".join(STACKS), stack))
    ds = cfg["_ds"]
    if not ds:
        die("DS profile not found (kit.config.json > ds = %s). Run kickoff step 4, or adopt to create one." % cfg.get("ds"))

    app_type = a.type or (declared or {}).get("type") or ("single" if stack == "html" else "spa")
    allowed = ("single", "multi") if stack == "html" else ("spa",)
    if app_type not in allowed:
        die("type '%s' does not fit stack '%s' (use %s)" % (app_type, stack, " or ".join(allowed)))
    rel_app = a.path or (declared or {}).get("path") or "apps/" + a.app
    app_dir = (root / rel_app).resolve()
    if root not in app_dir.parents:
        die("app path must be inside the project: %s" % rel_app)

    tdir = template_for(stack, app_type)
    if not tdir.is_dir():
        die("template folder missing in the kit: %s" % tdir.relative_to(KIT))

    bundle = ds["css"].get("bundle")
    if not bundle:
        die("ds.json > css.bundle is not set: the app needs the DS CSS bundle.")
    bpath = ds_path(cfg, bundle)
    if "://" in bpath:
        die("ds.json > css.bundle is a URL (%s). Download it into the profile folder and point css.bundle at the file." % bundle)
    if not Path(bpath).is_file():
        die("DS bundle not found: %s" % bpath)
    marker = ds["css"]["marker"]
    css = bundle_inside(Path(bpath).read_text(encoding="utf-8"), marker)
    bundle_file = Path(bpath).name

    theming = {k: {kk: vv for kk, vv in (v or {}).items() if kk in ("attr", "values", "default")}
               for k, v in (ds.get("theming") or {}).items() if isinstance(v, dict) and v.get("attr")}
    defaults = theming_defaults(theming)
    mode = theming.get("mode") or {}
    mode_values = mode.get("values") or []
    if not mode:
        print("WARNING: ds.json > theming.mode is missing: dark mode uses data-mode=\"dark\" in src/index.css and the mode button is hidden.")
    bps = ds.get("breakpoints") or {}
    lang = cfg.get("language") or "en"
    loc = cfg["local"]
    ds_rel = cfg["ds"].rstrip("/")

    values = {
        "APP_ID": a.app,
        "APP_NAME": a.name.strip(),
        "LANGUAGE": lang,
        "LANGUAGE_NAME": LANGUAGES.get(lang.split("-")[0].lower(), "the language with code " + lang),
        "STACK": stack,
        "DS_NAME": ds.get("name") or "",
        "DS_LABEL": ds["label"],
        "DS_PATH": ds_rel,
        "DS_BUNDLE": "%s/%s" % (ds_rel, bundle),
        "DS_BUNDLE_FILE": bundle_file,
        "CATALOG": "%s/%s" % (ds_rel, ds.get("catalog") or "catalog.md"),
        "RULES": "%s/%s" % (ds_rel, ds.get("rules") or "rules.md"),
        "DS_CSS": css,
        "VERSION": ds["version"],
        "VERSION_LABEL": html_attr(version_label(cfg)),
        "VERSION_META": ds["version_label"]["meta"],
        "TOKEN_PREFIX": ds["tokens"]["prefix"],
        "HTML_ATTRS": "".join(' %s="%s"' % (k, html_attr(v)) for k, v in defaults),
        "THEMING_JSON": json.dumps(theming, ensure_ascii=False).replace("<", "\\u003c"),
        "THEMING_ATTRS_NOTE": (" (" + ", ".join("`%s`" % t["attr"] for t in theming.values()) + ")") if theming else "",
        "MODE_ATTR": mode.get("attr") or "data-mode",
        "MODE_DARK": "dark" if "dark" in mode_values or not mode_values else mode_values[-1],
        "DENSITY_DEFAULT": "`%s`" % ((theming.get("density") or {}).get("default") or "auto"),
        "BP_MEDIUM": str(bps.get("medium", 600)),
        "BP_EXPANDED": str(bps.get("expanded", 840)),
        "LOCAL_PREFIX": loc["prefix"],
        "LOCAL_MARKER": loc["marker"],
        "LOCAL_REGISTRY": loc["registry"],
        "CHANGELOG": cfg["paths"]["changelog"],
    }

    # Plan every write first; write nothing when any target exists.
    plan = []  # (target, text)
    default_markers = ("/* @ds:begin */", "/* @ds:end */")
    real_markers = ("/* %s */" % marker["begin"], "/* %s */" % marker["end"])
    for f in template_files(tdir):
        rel = f.relative_to(tdir)
        text = fill(f.read_text(encoding="utf-8"), values, f.relative_to(KIT))
        if f.suffix in (".html", ".css") and real_markers != default_markers:
            text = text.replace(default_markers[0], real_markers[0]).replace(default_markers[1], real_markers[1])
        plan.append((app_dir / rel, text))
    if stack in ("react", "vue"):
        plan.append((app_dir / "src" / "ds" / bundle_file,
                     "%s\n%s\n%s\n" % (real_markers[0], css, real_markers[1])))

    claude_md = root / "CLAUDE.md"
    write_claude = not claude_md.exists()
    if write_claude:
        plan.append((claude_md, fill((TEMPLATES / "CLAUDE.md").read_text(encoding="utf-8"), values, "templates/CLAUDE.md")))

    conflicts = [t for t, _ in plan if t.exists()]
    if conflicts:
        print("ERROR: %d file(s) already exist; nothing was written:" % len(conflicts))
        for t in conflicts:
            print("  " + str(t.relative_to(root)))
        print("Remove or move them, or choose another --app / --path.")
        sys.exit(1)

    if a.dry_run:
        print("Dry run: %d file(s) would be written:" % len(plan))
        for t, _ in plan:
            print("  " + str(t.relative_to(root)))
        return 0

    for t, text in plan:
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(text, encoding="utf-8")

    if stack == "html" and app_type == "multi":
        r = subprocess.run([sys.executable, str(app_dir / "_shell" / "build.py"), "build"], capture_output=True, text=True)
        if r.returncode != 0:
            die("shell build failed:\n" + (r.stdout + r.stderr).strip())

    rel = app_dir.relative_to(root)
    print("Created %s (%s, %s) from templates/%s: %d file(s)." % (rel, stack, app_type, tdir.name, len(plan) - (1 if write_claude else 0)))
    print("DS: %s, bundle %s" % (version_label(cfg), bundle))
    print("CLAUDE.md: " + ("written from templates/CLAUDE.md" if write_claude else "exists, left unchanged"))
    if not declared:
        entry = {"id": a.app, "name": a.name.strip(), "path": str(rel), "entry": "index.html", "type": app_type,
                 "build": None, "check": None}
        if app_type == "multi":
            entry["build"] = "python3 %s/_shell/build.py build" % rel
            entry["check"] = "python3 %s/_shell/build.py check" % rel
        if stack in ("react", "vue"):
            entry["build"] = "npm --prefix %s run build" % rel
        if stack != cfg["stack"]:
            entry["stack"] = stack
        print("NOTE: app '%s' is not in kit.config.json > apps. Add:\n  %s" % (a.app, json.dumps(entry, ensure_ascii=False)))
    print("Next:")
    if stack == "html":
        print("  open %s/index.html in a browser (Playwright smoke test: kickoff step 7)" % rel)
        if app_type == "multi":
            print("  after editing _shell/: python3 %s/_shell/build.py build, then check" % rel)
    else:
        print("  cd %s && npm install && npm run build && npm run build:handoff" % rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
