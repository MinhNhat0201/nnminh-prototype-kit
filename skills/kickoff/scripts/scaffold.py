#!/usr/bin/env python3
"""Create a prototype app from the kit template of the project stack.

Usage:
  scaffold.py --app acme-web --name "Acme Web" [--type single|multi|spa] [--path apps/acme-web] [--dry-run]

What it does:
  - reads kit.config.json and the DS profile through scripts/kitconf.py
  - picks the template: html + single -> templates/html, html + multi -> templates/html-multi,
    react -> templates/react, vue -> templates/vue (type spa)
  - react / vue without Tailwind (ds.json > tailwind: false), and vue with the DS's own Vue component layer
    (ds.json > components.vue: {"package": "<folder in the project or npm name@version>", "propsMap": "<csv>"}):
    the plain overlay templates/<stack>-plain (no Tailwind, no shadcn; DS bundle + app-* skeleton CSS). With
    components.vue, the alias @ds-vue points at the package folder (or the npm package is added to dependencies).
  - copies it into the app folder (kit.config.json > apps[].path, default apps/<app>) and fills the placeholders:
    DS CSS (ds.json > css.bundle, html stacks), version label and <meta>, theming defaults on <html>,
    breakpoints, local-component prefix and marker
  - react / vue: copies the DS bundle to src/ds/<bundle file>, wrapped in the ds.json > css.marker comments
  - html multi: runs _shell/build.py build so every page holds the shared shell
  - writes templates/CLAUDE.md to the project CLAUDE.md only when the project has none
  - creates the project rules folder (kit.config.json > paths.rules, default rules/) with a README when it is missing
  - uses the app's own DS profile when kit.config.json > apps[].ds is set

It never overwrites a file: when a target file exists it writes nothing and exits 1 with the list.
It does not run npm install, edit kit.config.json, commit or push.
  scaffold.py --selftest   checks of the template choice and the overlay (no files written in the project)
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, ds_path, version_label, STACKS, t as tr  # noqa: E402

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


def template_for(stack, app_type, ds=None):
    if stack == "html":
        return TEMPLATES / ("html-multi" if app_type == "multi" else "html")
    if plain(stack, ds or {}):
        return TEMPLATES / (stack + "-plain")
    return TEMPLATES / stack


def plain(stack, ds):
    """react/vue without Tailwind and shadcn: ds.json > tailwind is false, or (vue) the DS has its own Vue layer."""
    return stack in ("react", "vue") and (ds.get("tailwind") is False or (stack == "vue" and bool(ds_vue(ds))))


def ds_vue(ds):
    cv = (ds.get("components") or {}).get("vue")
    return cv if isinstance(cv, dict) and cv.get("package") else None  # no package: the layer is not active


def template_files(tdir):
    """(relative path, source file) of a template; an overlay folder (_overlay.json) sits on its base template."""
    ov = tdir / "_overlay.json"
    out = {}
    if ov.is_file():
        meta = json.loads(ov.read_text(encoding="utf-8"))
        base = TEMPLATES / meta["base"]
        drop = [Path(x) for x in meta.get("drop", [])]
        for rel, f in template_files(base):
            if not any(rel == d or d in rel.parents for d in drop):
                out[rel] = f
    for f in sorted(tdir.rglob("*")):
        rel = f.relative_to(tdir)
        if f.is_file() and f.name != "_overlay.json" and not (set(rel.parts) & SKIP):
            out[rel] = f
    return sorted(out.items())


def shell_css(values):
    """Skeleton CSS of the html template (app-* classes, alias variables only), for the plain react/vue overlays."""
    s = (TEMPLATES / "html" / "index.html").read_text(encoding="utf-8")
    m = re.search(r"(/\* ==== App: shell ====.*?)</style>", s, re.S)
    return fill(m.group(1).rstrip(), values, "templates/html/index.html") if m else ""


def ds_vue_values(cv, root, app_dir):
    """Placeholders for the DS Vue layer, and the npm dependency to add (name, version) or None."""
    pkg = cv["package"]
    folder = (root / pkg).resolve()
    pm = cv.get("propsMap") or cv.get("map") or ""
    if folder.is_dir():
        rel = Path(os.path.relpath(folder, app_dir)).as_posix()
        alias = ',\n    "@ds-vue": fileURLToPath(new URL("%s/", import.meta.url))' % rel
        paths = ', "@ds-vue": ["%s"], "@ds-vue/*": ["%s/*"]' % (rel, rel)
        where, dep = "`@ds-vue` (alias of `%s`)" % pkg, None
    else:
        m = re.fullmatch(r"(@?[^@\s]+)@(\d[\w.+-]*)", pkg) or (re.fullmatch(r"(@?[^@\s]+)", pkg) and cv.get("version") and
                                                              re.fullmatch(r"(.+)@(.+)", pkg + "@" + cv["version"]))
        if not m:
            die("ds.json > components.vue.package '%s' is not a folder in the project and not an npm name@version "
                "(or add components.vue.version)" % pkg)
        alias, paths, where, dep = "", "", "`%s`" % m.group(1), (m.group(1), m.group(2))
    readme = ("\n## DS Vue components\n\nScreens use the Vue components of the DS, imported from %s. Props follow the props map%s."
              " Never rebuild a DS component locally and never add shadcn-vue: a missing component goes through the component gate"
              " of the prototype skill.\n" % (where, " `%s`" % pm if pm else " of the DS (`catalog.md > components.map`, Vue column)"))
    return {"EXTRA_ALIASES": alias, "EXTRA_TS_PATHS": paths, "DS_VUE_README": readme,
            "COMPONENT_SOURCE": "the DS Vue components (%s)" % where,
            "SHELL_NOTE": "Use the DS Vue components (%s) for the shell parts the DS has." % where.replace("`", ""),
            "PAGE_NOTE": "Replace this content with DS Vue components from %s." % where.replace("`", "")}, dep


def fill(text, values, src):
    missing = sorted({m for m in PLACEHOLDER.findall(text) if m not in values})
    if missing:
        die("template %s uses unknown placeholder(s): %s" % (src, ", ".join(missing)))
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], text)


def selftest():
    import tempfile
    ds = {"tailwind": False}
    assert template_for("vue", "spa", ds).name == "vue-plain" and template_for("react", "spa", ds).name == "react-plain"
    assert template_for("vue", "spa", {}).name == "vue" and template_for("html", "single", ds).name == "html"
    assert template_for("vue", "spa", {"components": {"vue": {"package": "x"}}}).name == "vue-plain"
    assert template_for("vue", "spa", {"components": {"vue": {"package": None, "map": "m.csv"}}}).name == "vue", "no package: inactive"
    assert template_for("react", "spa", {"components": {"vue": {"package": "x"}}}).name == "react", "components.vue is vue only"
    files = dict(template_files(TEMPLATES / "vue-plain"))
    assert Path("src/components/ui/button/Button.vue") not in files and Path("src/router.ts") in files, "overlay drop/keep"
    assert files[Path("package.json")].parent.name == "vue-plain", "overlay file replaces the base"
    d = Path(tempfile.mkdtemp())
    (d / "pk" / "vue").mkdir(parents=True)
    v, dep = ds_vue_values({"package": "pk/vue", "propsMap": "pk/props.csv"}, d, d / "apps" / "a")
    assert '"../../pk/vue/"' in v["EXTRA_ALIASES"] and dep is None and "pk/props.csv" in v["DS_VUE_README"], v
    v, dep = ds_vue_values({"package": "@acme/vue@1.2.0"}, d, d / "apps" / "a")
    assert dep == ("@acme/vue", "1.2.0") and v["EXTRA_ALIASES"] == "", (v, dep)
    assert "app-top" in shell_css({"BP_MEDIUM": "600"})
    print("scaffold.py selftest OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return 0
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

    cfg = load(app=a.app)  # the app's own DS profile when kit.config.json > apps[].ds is set
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

    tdir = template_for(stack, app_type, ds)
    if not tdir.is_dir():
        die("template folder missing in the kit: %s" % tdir.relative_to(KIT))
    if plain(stack, ds) and ds.get("tailwind") is True:
        print("NOTE: ds.json > components.vue is set: the template has no Tailwind and no shadcn-vue; add Tailwind yourself if the DS needs it.")

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
        "EXTRA_ALIASES": "", "EXTRA_TS_PATHS": "", "DS_VUE_README": "",
        "COMPONENT_SOURCE": "the DS classes in `catalog.md` (or the components it maps)",
        "SHELL_NOTE": "When catalog.md lists an app shell, top bar, navigation rail or tab bar, use it instead.",
        "PAGE_NOTE": "Replace this content with DS components from the catalogue.",
    }
    dep = None
    if stack == "vue" and ds_vue(ds):
        extra, dep = ds_vue_values(ds_vue(ds), root, app_dir)
        values.update(extra)
    if plain(stack, ds):
        values["SHELL_CSS"] = shell_css(values)

    # Plan every write first; write nothing when any target exists.
    plan = []  # (target, text)
    default_markers = ("/* @ds:begin */", "/* @ds:end */")
    real_markers = ("/* %s */" % marker["begin"], "/* %s */" % marker["end"])
    for rel, f in template_files(tdir):
        text = fill(f.read_text(encoding="utf-8"), values, f.relative_to(KIT))
        if dep and rel == Path("package.json"):
            pj = json.loads(text)
            pj.setdefault("dependencies", {})[dep[0]] = dep[1]
            text = json.dumps(pj, indent=2) + "\n"
        if f.suffix in (".html", ".css") and real_markers != default_markers:
            text = text.replace(default_markers[0], real_markers[0]).replace(default_markers[1], real_markers[1])
        plan.append((app_dir / rel, text))
    if stack in ("react", "vue"):
        plan.append((app_dir / "src" / "ds" / bundle_file,
                     "%s\n%s\n%s\n" % (real_markers[0], css, real_markers[1])))

    rules_dir = root / ((cfg.get("paths") or {}).get("rules") or "rules")
    if not rules_dir.exists():  # the project layer of the rules registry (scripts/rules.py)
        plan.append((rules_dir / "README.md", tr(cfg, "rules.readme")))
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
    if ds_vue(ds) and stack == "vue":
        print("DS Vue layer: %s (props map: %s)" % (ds_vue(ds)["package"], ds_vue(ds).get("propsMap") or "none"))
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
