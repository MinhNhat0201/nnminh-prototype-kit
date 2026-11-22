"""Load kit.config.json and the DS profile it points to.

Usage in a script:

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[N] / "scripts"))
    from kitconf import load, t
    cfg = load()            # dict with defaults filled, plus cfg["_root"], cfg["_ds"], cfg["_ds_dir"]
    print(t(cfg, "handoff.done", zip="Design - 123.zip"))

Command line:

    python3 scripts/kitconf.py           # print the merged configuration
    python3 scripts/kitconf.py check     # validate; exit 1 on error
    python3 scripts/kitconf.py skills    # model and effort hints per skill (kit.config.json > skills)
    python3 scripts/kitconf.py --app acme-mobile   # the merged configuration with that app's DS profile (apps[].ds)
    python3 scripts/kitconf.py hook prototype.post --app acme-web   # run an optional project command ({app}, {path}, {root})
    python3 scripts/kitconf.py contract --app acme-web   # the page contract of the app (apps[].pageContract), one line each
    python3 scripts/kitconf.py --selftest
"""
import json
import os
import re
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]

DEFAULTS = {
    "language": "en",
    "stack": "html",
    "ds": None,
    "apps": [],
    "local": {"prefix": "x-", "marker": "LOCAL", "registry": "docs/local-components.json",
              "command": {"update": None, "check": None}, "fields": {}, "vueStyle": "sfc", "vueCss": "src/styles/local.css"},
    "handoff": {"dir": "docs/handover", "zipName": "Design - {pbi}", "maxZipMB": 3, "figmaRequired": True,
                "itemLabel": "", "grepLabels": [], "dsLabel": "auto", "dsLabelCheck": "warn",
                "specFiles": {"archive": "archive.md", "crossPage": "cross-page.md", "legacy": []},
                "csv": {"feature": None, "qc": None}, "pre": None, "post": None, "specFields": {},
                "smokeWidths": [400, 768, 1280]},
    "email": {"subject": "[{app}] Design - {feature} - {version}", "attachLimitMB": 3, "demoLinks": True, "maxItems": 12,
              "template": None},
    "deploy": {"type": "none", "site": None},
    "sync": {"command": None, "check": None, "prepare": None, "post": None},
    "review": {"extraChecks": []},
    "prototype": {"post": None},
    "figma": {"imageSuffix": None},
    "validate": {"touchTarget": {"default": 44, "desktop": 24}, "axePath": None, "setTheme": None},
    "skills": {},
    "rules": {"categories": {}},
    "paths": {"changelog": "CHANGELOG.md", "plans": "docs/plans", "audits": "docs/audits", "explorations": "docs/explorations", "context": "product-context", "validation": "docs/validation", "verify": "docs/verify", "rules": "rules"},
}

DS_DEFAULTS = {
    "label": None,
    "version": "0.0.0",
    "platforms": ["web"],
    "tokens": {"prefix": "--ds-", "roles": {}, "scale": {}, "file": "tokens.json", "ignorePrefixes": []},
    "css": {"bundle": None, "sources": [], "marker": {"begin": "@ds:begin", "end": "@ds:end"}, "load": "embed", "linkPath": None},
    "version_label": {"text": "{label} {version}", "meta": "ds-version"},
    "theming": {},
    "breakpoints": {"compact": 0, "medium": 600, "expanded": 840},
    "icons": {},
    "catalog": "catalog.md",
    "catalog_json": "catalog.json",
    "rules": "rules.md",
    "changelog": None,
    "review": {"genericClasses": []},
    "library": {},
    "figma": {"libraries": [], "collections": {}, "modes": {}},
    "preset": {},
    "patterns": [],
}

STACKS = ("html", "react", "vue")
APP_TYPES = ("single", "multi", "spa", "page")
SPEC_KEYS = ("pbi", "title", "version", "date", "ds", "prototype")
SKILLS = ("brief", "kickoff", "adopt", "define", "context", "explore", "prototype", "validate", "annotate", "wireflow",
          "mockup", "handoff", "share", "verify", "review", "sync", "contribute", "document")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
DS_LABEL_SOURCES = ("auto", "pkg", "spec", "ds", "prototype")
CHECK_LEVELS = ("off", "warn", "error")
CSS_LOADS = ("embed", "link")
VUE_STYLES = ("sfc", "css-file")
CHANGELOG_FORMATS = ("md", "json")
CSV_ROLES = {
    "feature": ("code", "feature", "group", "screen", "behaviour", "inputs", "expected", "status", "dependencies"),
    "qc": ("id", "unit", "preconditions", "steps", "expected", "result", "notes"),
}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def find_root(start=None):
    """Return the folder that holds kit.config.json, walking up from start (default: cwd)."""
    p = Path(start or os.getcwd()).resolve()
    for d in [p, *p.parents]:
        if (d / "kit.config.json").is_file():
            return d
    return None


def read_profile(root, rel):
    """(ds dict with defaults, absolute profile folder) of a DS profile folder, or (None, None)."""
    if not rel:
        return None, None
    ds_dir = (Path(root) / rel).resolve()
    f = ds_dir / "ds.json"
    if not f.is_file():
        return None, None
    ds = _merge(DS_DEFAULTS, json.loads(f.read_text(encoding="utf-8")))
    ds["label"] = ds.get("label") or ds.get("name")
    return ds, str(ds_dir)


def load(start=None, require=True, app=None):
    """Merged configuration. app = an app id: the DS profile is that app's (apps[].ds), see for_app."""
    root = find_root(start)
    if root is None:
        if require:
            sys.exit("ERROR: kit.config.json not found in this folder or any parent. Run the kickoff skill first.")
        return None
    cfg = _merge(DEFAULTS, json.loads((root / "kit.config.json").read_text(encoding="utf-8")))
    cfg["_root"] = str(root)
    cfg["_ds"], cfg["_ds_dir"] = read_profile(root, cfg.get("ds"))
    cfg["_app"] = None
    return for_app(cfg, app) if app else cfg


def app_ds(cfg, app_id):
    """The DS profile path of an app: apps[].ds when set, else the top-level ds."""
    for a in cfg.get("apps") or []:
        if a.get("id") == app_id and a.get("ds"):
            return a["ds"]
    return cfg.get("ds")


def for_app(cfg, app_id):
    """A copy of cfg whose DS profile (ds, _ds, _ds_dir) is the app's own (apps[].ds), so a project can keep a web
    profile and a mobile profile with their own version numbers. Unknown app or no apps[].ds: cfg unchanged."""
    if not app_id or not cfg:
        return cfg
    rel = app_ds(cfg, app_id)
    out = dict(cfg)
    out["_app"] = app_id
    if rel and rel != cfg.get("ds"):
        out["ds"] = rel
        out["_ds"], out["_ds_dir"] = read_profile(cfg["_root"], rel)
    return out


def profiles(cfg):
    """{profile path: [app ids]} of every DS profile in use (top-level ds for apps without apps[].ds)."""
    out = {}
    if cfg.get("ds"):
        out[cfg["ds"]] = []
    for a in cfg.get("apps") or []:
        out.setdefault(app_ds(cfg, a.get("id")) or "", []).append(a.get("id"))
    out.pop("", None)
    return out


def spec_meta(cfg, meta):
    """Frontmatter of spec/index.md with the project's key aliases (handoff.specFields = {kit key: old key or list}).
    A DS alias holding only a version ("2.4.1") becomes the version label of the profile ("Acme DS 2.4.1")."""
    out = dict(meta or {})
    for k, alias in (((cfg or {}).get("handoff") or {}).get("specFields") or {}).items():
        for x in ([alias] if isinstance(alias, str) else alias or []):
            if not out.get(k) and out.get(x):
                out[k] = out[x]
        if k == "ds" and re.fullmatch(r"\d+\.\d+\.\d+", out.get("ds") or "") and (cfg or {}).get("_ds"):
            d = cfg["_ds"]
            out["ds"] = d["version_label"]["text"].format(label=d["label"], version=out["ds"], name=d.get("name"))
    return out


def ds_path(cfg, rel):
    """Resolve a path from ds.json (relative to the profile folder). URLs are returned unchanged."""
    if rel is None:
        return None
    if "://" in rel:
        return rel
    return str(Path(cfg["_ds_dir"]) / rel)


def ds_rules(ds):
    """(rules document name, profile path the DS-layer rules are inherited from or None) of a DS profile.
    ds.json > rules is a file name ("rules.md") or an object {"file": "rules.md", "from": "../acme"}."""
    r = (ds or {}).get("rules")
    if isinstance(r, dict):
        return r.get("file") or "rules.md", r.get("from") or None
    return r or "rules.md", None


def css_load(cfg, app_id=None):
    """How an app loads the DS CSS: {"load": "embed" | "link", "linkPath": file next to the pages or None}.
    ds.json > css.load / css.linkPath, overridden per app by apps[].css.load / apps[].css.linkPath. linkPath defaults
    to the bundle's file name. embed (default) = the bundle between the css.marker comments of each page."""
    css = ((cfg or {}).get("_ds") or {}).get("css") or {}
    load_, link = css.get("load") or "embed", css.get("linkPath")
    for a in (cfg or {}).get("apps") or []:
        if a.get("id") == app_id and isinstance(a.get("css"), dict):
            load_, link = a["css"].get("load") or load_, a["css"].get("linkPath") or link
    if load_ == "link" and not link and css.get("bundle") and "://" not in css["bundle"]:
        link = Path(css["bundle"]).name
    return {"load": load_, "linkPath": link if load_ == "link" else None}


def ds_changelog(cfg):
    """(absolute path, format) of the DS changelog: ds.json > changelog {"path", "format": "md" | "json"} (path relative to
    the profile folder, else to the project root), default CHANGELOG.md (md) in the profile folder."""
    ch = ((cfg or {}).get("_ds") or {}).get("changelog")
    if isinstance(ch, str):
        ch = {"path": ch}
    ch = ch or {}
    rel = ch.get("path") or "CHANGELOG.md"
    fmt = ch.get("format") or ("json" if rel.lower().endswith(".json") else "md")
    bases = [cfg.get("_ds_dir")] + ([cfg.get("_root")] if ch.get("path") else [])
    for b in [x for x in bases if x]:
        if (Path(b) / rel).is_file():
            return str((Path(b) / rel).resolve()), fmt
    return str(Path(cfg.get("_ds_dir") or ".") / rel), fmt


def run_command(cfg, line, title):
    """Run a project command in the project root, print it, its output and exit code. Returns the exit code."""
    import subprocess
    print("%s: %s" % (title, line))
    r = subprocess.run(line, shell=True, cwd=cfg["_root"], capture_output=True, text=True)
    out = (r.stdout + r.stderr).rstrip()
    if out:
        print(out)
    print("%s exit code %d" % (title, r.returncode))
    return r.returncode


def fill_command(cmd, **vals):
    """Replace {key} placeholders of a project command with shell-quoted values (empty value = nothing)."""
    import shlex
    return re.sub(r"\{(\w+)\}", lambda m: (shlex.quote(str(vals[m.group(1)])) if vals[m.group(1)] else "")
                  if m.group(1) in vals else m.group(0), cmd)


def version_label(cfg):
    ds = cfg["_ds"]
    return ds["version_label"]["text"].format(label=ds["label"], version=ds["version"], name=ds.get("name"))


def project_command(cfg, key):
    """Project command of an extension point (kit.config.json first, then ds.json for sync), or None.
    key is a dotted path such as "sync.command" or "local.command.update"."""
    def get(d, parts):
        for x in parts:
            d = d.get(x) if isinstance(d, dict) else None
        return d
    parts = key.split(".")
    v = get(cfg, parts)
    if v is None and parts[0] == "sync":
        v = get(cfg.get("_ds") or {}, parts)
    return v or None


def spec_files(cfg):
    """Names of the special spec files: {"archive": ..., "crossPage": ..., "special": set of stems that are not units,
    "legacy": {"archive": [...], "crossPage": [...]}}. handoff.specFiles.legacy is a list of older names (special files,
    not units) or an object {"archive": [...], "crossPage": [...]} that also says which file each old name was."""
    sf = ((cfg or {}).get("handoff") or {}).get("specFiles") or {}
    arc, cross = sf.get("archive") or "archive.md", sf.get("crossPage") or "cross-page.md"
    leg = sf.get("legacy") or []
    kinds = {"archive": list(leg.get("archive") or []), "crossPage": list(leg.get("crossPage") or [])} if isinstance(leg, dict) \
        else {"archive": [], "crossPage": []}
    names = leg if isinstance(leg, list) else kinds["archive"] + kinds["crossPage"]
    stems = {"index", "flows", Path(arc).stem, Path(cross).stem, "archive", "cross-page"}
    stems |= {Path(x).stem for x in names}
    return {"archive": arc, "crossPage": cross, "special": stems, "legacy": kinds}


def csv_header(cfg, kind):
    """(header line, [role per column or None]) of requirements/checklist-<kind>.csv.
    handoff.csv.<kind> may be null (locale header), a comma string or a list (standard column order),
    or an object {role: header} (any order, any subset of roles)."""
    roles = CSV_ROLES[kind]
    v = ((cfg.get("handoff") or {}).get("csv") or {}).get(kind)
    if isinstance(v, dict):
        cols = list(v.items())
        return ",".join(h for _r, h in cols), [r if r in roles else None for r, _h in cols]
    if isinstance(v, (list, str)) and v:
        names = [x.strip() for x in (v.split(",") if isinstance(v, str) else v)]
    else:
        names = [x.strip() for x in t(cfg, "handoff.csv." + kind).split(",")]
    return ",".join(names), [roles[i] if i < len(roles) else None for i in range(len(names))]


def ds_vue(cfg):
    """The DS's own Vue component layer (ds.json > components.vue), or None when it has no package.
    Returns {"package": str, "propsMap": absolute path or None, "raw": the entry}. "map" is read as "propsMap";
    the props map path is relative to the project root, else to the profile folder."""
    ds = (cfg or {}).get("_ds") or {}
    cv = (ds.get("components") or {}).get("vue")
    if not isinstance(cv, dict) or not cv.get("package"):
        return None
    pm, found = cv.get("propsMap") or cv.get("map"), None
    for base in ([cfg.get("_root")] if cfg.get("_root") else []) + ([cfg.get("_ds_dir")] if cfg.get("_ds_dir") else []):
        if pm and (Path(base) / pm).is_file():
            found = str(Path(base) / pm)
            break
    return {"package": cv["package"], "propsMap": found, "raw": cv}


def skill_hint(cfg, name):
    """{"model": ..., "effort": ...} for a skill from kit.config.json > skills (empty dict when not set)."""
    h = ((cfg or {}).get("skills") or {}).get(name) or {}
    return {k: h[k] for k in ("model", "effort") if h.get(k)}


def page_contract(cfg, app_id):
    """Lines of apps[].pageContract: what every page of the app must do for its shell (a string is one line). Default []."""
    for a in (cfg or {}).get("apps") or []:
        if a.get("id") == app_id:
            v = a.get("pageContract") or []
            return [v] if isinstance(v, str) else [str(x) for x in v]
    return []


def app(cfg, app_id):
    for a in cfg["apps"]:
        if a.get("id") == app_id:
            return _merge({"type": "single", "entry": "index.html", "build": None, "check": None, "stack": cfg["stack"],
                           "pageContract": []}, a)
    sys.exit(f"ERROR: app '{app_id}' is not declared in kit.config.json > apps.")


_LOCALES = {}


def _locale(lang):
    if lang not in _LOCALES:
        d, merged = KIT_ROOT / "locales" / lang, {}
        for f in sorted(d.glob("*.json")) if d.is_dir() else []:
            merged.update(json.loads(f.read_text(encoding="utf-8")))
        _LOCALES[lang] = merged
    return _LOCALES[lang]


def t(cfg_or_lang, key, **kw):
    """Template string in the project language, falling back to English, then to the key itself."""
    lang = cfg_or_lang if isinstance(cfg_or_lang, str) else (cfg_or_lang or {}).get("language", "en")
    s = _locale(lang).get(key) or _locale("en").get(key) or key
    return s.format(**kw) if kw else s


def _check_profile(ds, ds_dir, rel):
    """Errors of the 0.10 keys of one DS profile (they would otherwise fail late, in review, sync or rules)."""
    errs = []
    if (ds["css"].get("load") or "embed") not in CSS_LOADS:
        errs.append(f"{rel}/ds.json > css.load must be one of {', '.join(CSS_LOADS)}")
    ch = ds.get("changelog")
    if ch is not None and not isinstance(ch, (str, dict)):
        errs.append(f"{rel}/ds.json > changelog must be a path or an object {{\"path\", \"format\"}}")
    elif isinstance(ch, dict) and (ch.get("format") or "md") not in CHANGELOG_FORMATS:
        errs.append(f"{rel}/ds.json > changelog.format must be one of {', '.join(CHANGELOG_FORMATS)}")
    for k, v in (("tokens.ignorePrefixes", ds["tokens"].get("ignorePrefixes")),
                 ("review.genericClasses", (ds.get("review") or {}).get("genericClasses"))):
        if v is not None and (not isinstance(v, list) or not all(isinstance(x, str) for x in v)):
            errs.append(f"{rel}/ds.json > {k} must be a list of strings")
    _f, frm = ds_rules(ds)
    if frm and not (Path(ds_dir) / frm / "ds.json").is_file():
        errs.append(f"{rel}/ds.json > rules.from: no DS profile at {frm} (a path relative to {rel})")
    return errs


def check(cfg):
    errs = []
    if cfg["stack"] not in STACKS:
        errs.append(f"stack must be one of {', '.join(STACKS)} (found '{cfg['stack']}')")
    if not cfg.get("ds"):
        errs.append("ds is missing: point it at a DS profile folder, e.g. \"ds/acme\"")
    elif cfg["_ds"] is None:
        errs.append(f"ds.json not found in {cfg['ds']}")
    ids = set()
    for a in cfg["apps"]:
        if not a.get("id") or not a.get("path"):
            errs.append(f"every app needs id and path: {a}")
        if a.get("id") in ids:
            errs.append(f"duplicate app id '{a.get('id')}'")
        ids.add(a.get("id"))
        if a.get("stack", cfg["stack"]) not in STACKS:
            errs.append(f"app '{a.get('id')}': stack must be one of {', '.join(STACKS)}")
        if a.get("type", "single") not in APP_TYPES:
            errs.append(f"app '{a.get('id')}': type must be one of {', '.join(APP_TYPES)}")
        ub = a.get("usedBy")
        if ub is not None and (not isinstance(ub, list) or not all(isinstance(x, str) and x for x in ub)):
            errs.append(f"app '{a.get('id')}': usedBy must be a list of file paths (where the build output is copied)")
        if a.get("type") == "page" and not ub:
            errs.append(f"app '{a.get('id')}': type page needs usedBy (the files of other apps its build output becomes)")
        for k in ("sources", "generated"):
            v = a.get(k)
            if v is not None and (not isinstance(v, list) or not all(isinstance(x, str) and x for x in v)):
                errs.append(f"app '{a.get('id')}': {k} must be a list of glob patterns (paths from the project root)")
        pc = a.get("pageContract")
        if pc is not None and not isinstance(pc, str) and (not isinstance(pc, list) or not all(isinstance(x, str) and x for x in pc)):
            errs.append(f"app '{a.get('id')}': pageContract must be a list of lines (what every page must do for the shell)")
        ac = a.get("css")
        if ac is not None and (not isinstance(ac, dict) or (ac.get("load") or "embed") not in CSS_LOADS):
            errs.append(f"app '{a.get('id')}': css must be an object {{\"load\": \"embed\" | \"link\", \"linkPath\": ...}}")
        if a.get("ds"):
            pds, pdir = read_profile(cfg["_root"], a["ds"])
            if pds is not None:
                errs += ["app '%s': %s" % (a.get("id"), e) for e in _check_profile(pds, pdir, a["ds"])]
            if pds is None:
                errs.append(f"app '{a.get('id')}': ds.json not found in {a['ds']} (apps[].ds)")
            elif not pds["tokens"]["prefix"].startswith("--"):
                errs.append(f"app '{a.get('id')}': {a['ds']}/ds.json > tokens.prefix must start with '--'")
            elif pds["css"]["bundle"] and "://" not in pds["css"]["bundle"] and not (Path(cfg["_root"]) / a["ds"] / pds["css"]["bundle"]).is_file():
                errs.append(f"app '{a.get('id')}': {a['ds']}/ds.json > css.bundle not found: {pds['css']['bundle']}")
    ds = cfg["_ds"]
    if ds:
        errs += _check_profile(ds, cfg["_ds_dir"], cfg["ds"])
        if not ds["tokens"]["prefix"].startswith("--"):
            errs.append("ds.json > tokens.prefix must start with '--'")
        b = ds["css"]["bundle"]
        if b and "://" not in b and not Path(ds_path(cfg, b)).is_file():
            errs.append(f"ds.json > css.bundle not found: {b}")
        cv = (ds.get("components") or {}).get("vue")
        if cv is not None and not isinstance(cv, dict):
            errs.append("ds.json > components.vue must be an object {\"package\": ..., \"propsMap\": ...}")
        elif ds_vue(cfg) and not ds_vue(cfg)["propsMap"] and (cv.get("propsMap") or cv.get("map")):
            errs.append("ds.json > components.vue.propsMap not found (relative to the project root or the profile folder)")
    h = cfg["handoff"]
    if h.get("dsLabel") not in DS_LABEL_SOURCES:
        errs.append("handoff.dsLabel must be one of " + ", ".join(DS_LABEL_SOURCES))
    if h.get("dsLabelCheck") not in CHECK_LEVELS:
        errs.append("handoff.dsLabelCheck must be one of " + ", ".join(CHECK_LEVELS))
    if not isinstance(h.get("grepLabels"), list):
        errs.append("handoff.grepLabels must be a list of strings")
    sw = h.get("smokeWidths")
    if not isinstance(sw, list) or not sw or not all(isinstance(x, int) and x >= 200 for x in sw):
        errs.append("handoff.smokeWidths must be a non-empty list of widths in px (at least 200), e.g. [400, 768, 1280]")
    for kind in ("feature", "qc"):
        v = (h.get("csv") or {}).get(kind)
        if isinstance(v, dict):
            bad = [r for r in v if r not in CSV_ROLES[kind]]
            if bad:
                errs.append("handoff.csv.%s: unknown role(s) %s (roles: %s)" % (kind, ", ".join(bad), ", ".join(CSV_ROLES[kind])))
        elif v is not None and not isinstance(v, (str, list)):
            errs.append("handoff.csv.%s must be null, a comma string, a list or an object {role: header}" % kind)
    for i, x in enumerate((cfg.get("review") or {}).get("extraChecks") or []):
        if not isinstance(x, dict) or not x.get("name") or not x.get("command"):
            errs.append("review.extraChecks[%d] needs name and command" % i)
    for k, v in (cfg.get("skills") or {}).items():
        if k not in SKILLS:
            errs.append("skills.%s: unknown skill (skills: %s)" % (k, ", ".join(SKILLS)))
        elif not isinstance(v, dict) or set(v) - {"model", "effort"}:
            errs.append("skills.%s takes only model and effort" % k)
        elif v.get("effort") and v["effort"] not in EFFORTS:
            errs.append("skills.%s.effort must be one of %s" % (k, ", ".join(EFFORTS)))
    if not isinstance((cfg.get("local") or {}).get("fields"), dict):
        errs.append("local.fields must be an object {kit field: project field}")
    if (cfg.get("local") or {}).get("vueStyle", "sfc") not in VUE_STYLES:
        errs.append("local.vueStyle must be one of " + ", ".join(VUE_STYLES))
    sf = h.get("specFields")
    if not isinstance(sf, dict) or any(k not in SPEC_KEYS or not isinstance(v, (str, list)) for k, v in sf.items()):
        errs.append("handoff.specFields must be an object {kit key: old key or list of old keys}; kit keys: " + ", ".join(SPEC_KEYS))
    tpl = (cfg.get("email") or {}).get("template")
    if tpl and not (Path(cfg["_root"]) / tpl.replace("{language}", cfg.get("language") or "en")).is_file():
        errs.append(f"email.template not found: {tpl} (a .md, .txt or .html file in the project)")
    cats = (cfg.get("rules") or {}).get("categories")
    if not isinstance(cats, dict) or any(not re.fullmatch(r"[A-Z][A-Z0-9]{1,5}", str(v)) for v in cats.values()):
        errs.append("rules.categories must be an object {category: ID prefix of 2-6 capital letters or digits}")
    return errs


def selftest():
    import tempfile
    d = Path(tempfile.mkdtemp())
    (d / "ds" / "acme").mkdir(parents=True)
    (d / "ds" / "acme" / "ds.json").write_text(json.dumps({"name": "acme", "version": "1.2.3"}))
    (d / "kit.config.json").write_text(json.dumps({"ds": "ds/acme", "language": "vi", "handoff": {
        "csv": {"qc": {"id": "ID", "steps": "Steps"}}, "specFiles": {"archive": "old-units.md", "legacy": ["luu-tru.md"]}},
        "skills": {"handoff": {"model": "m1", "effort": "high"}}}))
    c = load(d)
    assert c["email"]["demoLinks"] is True and c["email"]["maxItems"] == 12, "email defaults"
    assert c["handoff"]["zipName"] == "Design - {pbi}" and c["handoff"]["dsLabel"] == "auto", "handoff defaults kept"
    assert check(c) == [], check(c)
    sf = spec_files(c)
    assert sf["archive"] == "old-units.md" and {"old-units", "luu-tru", "cross-page", "archive"} <= sf["special"], sf
    sf2 = spec_files({"handoff": {"specFiles": {"legacy": {"archive": ["old-a.md"], "crossPage": ["old-c.md"]}}}})
    assert sf2["legacy"]["crossPage"] == ["old-c.md"] and {"old-a", "old-c"} <= sf2["special"], sf2
    assert csv_header(c, "qc") == ("ID,Steps", ["id", "steps"]), csv_header(c, "qc")
    h, roles = csv_header(c, "feature")
    assert roles[0] == "code" and roles[7] == "status" and h.startswith("Mã,"), (h, roles)
    assert skill_hint(c, "handoff") == {"model": "m1", "effort": "high"} and skill_hint(c, "sync") == {}
    assert project_command(c, "sync.command") is None
    c["_ds"]["components"] = {"vue": {"package": None, "map": "m.csv"}}
    assert ds_vue(c) is None and check(c) == [], "components.vue without package is inactive"
    (d / "ds" / "acme" / "m.csv").write_text("component\n")
    c["_ds"]["components"]["vue"]["package"] = "pk"
    assert ds_vue(c)["propsMap"].endswith("m.csv"), "map read as propsMap, from the profile folder"
    c["_ds"]["sync"] = {"command": "make sync"}
    assert project_command(c, "sync.command") == "make sync", "ds.json > sync fallback"
    c["skills"] = {"nope": {}, "share": {"effort": "huge"}}
    assert len(check(c)) == 2, check(c)
    c["skills"] = {}
    # apps[].ds: a second profile with its own version; type page + usedBy
    (d / "ds" / "acme-mobile").mkdir(parents=True)
    (d / "ds" / "acme-mobile" / "ds.json").write_text(json.dumps({"name": "acme-mobile", "label": "Acme Mobile", "version": "3.0.0"}))
    c["apps"] = [{"id": "web", "path": "apps/web"}, {"id": "mob", "path": "apps/mob", "ds": "ds/acme-mobile"},
                 {"id": "pg", "path": "src/pg", "type": "page", "usedBy": ["apps/web/pg.js"]}]
    assert check(c) == [], check(c)
    m = for_app(c, "mob")
    assert m["_ds"]["version"] == "3.0.0" and c["_ds"]["version"] == "1.2.3" and for_app(c, "web")["_ds"]["version"] == "1.2.3"
    assert profiles(c) == {"ds/acme": ["web", "pg"], "ds/acme-mobile": ["mob"]}, profiles(c)
    assert version_label(m) == "Acme Mobile 3.0.0"
    c["apps"] += [{"id": "bad", "path": "x", "ds": "ds/none"}, {"id": "pg2", "path": "y", "type": "page"}]
    assert len(check(c)) == 2, check(c)
    c["apps"] = c["apps"][:3]
    # handoff.specFields: old frontmatter key, bare version -> label
    c["handoff"]["specFields"] = {"ds": ["acmeVersion"]}
    assert spec_meta(c, {"acmeVersion": "1.2.0"})["ds"] == "acme 1.2.0", spec_meta(c, {"acmeVersion": "1.2.0"})
    assert spec_meta(c, {"ds": "Acme 9", "acmeVersion": "1"})["ds"] == "Acme 9", "the kit key wins"
    c["handoff"]["specFields"] = {"nope": "x"}
    c["email"]["template"] = "missing.md"
    c["rules"]["categories"] = {"motion": "mo"}
    assert len(check(c)) == 3, check(c)
    # 0.10: css.load, rules.from, changelog, placeholders
    c = load(d)
    assert css_load(c, "web") == {"load": "embed", "linkPath": None}, "embed by default"
    c["_ds"]["css"].update(load="link", bundle="dist/acme.css")
    assert css_load(c, "web")["linkPath"] == "acme.css", css_load(c, "web")
    c["apps"] = [{"id": "web", "path": "apps/web", "css": {"load": "embed"}}, {"id": "m", "path": "m", "css": {"linkPath": "shared/ds.css"}}]
    assert css_load(c, "web")["load"] == "embed" and css_load(c, "m") == {"load": "link", "linkPath": "shared/ds.css"}
    assert ds_rules({"rules": "rules.md"}) == ("rules.md", None) and ds_rules({"rules": {"from": "../acme"}}) == ("rules.md", "../acme")
    assert ds_changelog(c)[1] == "md" and ds_changelog(c)[0].endswith("ds/acme/CHANGELOG.md")
    (d / "docs").mkdir()
    (d / "docs" / "news.json").write_text("[]")
    c["_ds"]["changelog"] = {"path": "docs/news.json"}
    assert ds_changelog(c) == (str((d / "docs" / "news.json").resolve()), "json"), "project-root fallback, format from the name"
    assert fill_command("x {app} {path} {other}", app="a b", path="") == "x 'a b'  {other}"
    c["_ds"]["css"]["load"] = "inline"
    c["_ds"]["changelog"] = {"format": "yaml"}
    c["_ds"]["rules"] = {"from": "../none"}
    c["apps"][0]["generated"] = "shared/*"
    new = [e for e in check(c) if any(k in e for k in ("generated", "css.load", "changelog.format", "rules.from"))]
    assert len(new) == 4, check(c)
    # apps[].pageContract, local.vueStyle
    c = load(d)
    assert c["local"]["vueStyle"] == "sfc" and page_contract(c, "web") == [], "defaults keep the earlier behaviour"
    c["apps"] = [{"id": "web", "path": "w", "pageContract": ["Call Shell.ready() after the first render"]},
                 {"id": "one", "path": "o", "pageContract": "Load shared/shell.js first"}]
    assert page_contract(c, "web") == ["Call Shell.ready() after the first render"] and page_contract(c, "one") == ["Load shared/shell.js first"]
    new = lambda: [e for e in check(c) if "pageContract" in e or "vueStyle" in e]  # earlier cases leave other errors
    assert app(c, "web")["pageContract"] and app(c, "one")["type"] == "single" and new() == [], check(c)
    c["apps"][0]["pageContract"] = [1]
    c["local"]["vueStyle"] = "scoped"
    assert len(new()) == 2, check(c)
    c["local"]["vueStyle"] = "sfc"  # c["local"] may be the DEFAULTS object
    print("kitconf selftest OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    c = load(app=sys.argv[sys.argv.index("--app") + 1] if "--app" in sys.argv[:-1] else None)
    if len(sys.argv) > 1 and sys.argv[1] == "skills":
        for k in SKILLS:
            h = skill_hint(c, k)
            if h:
                print("%-11s model=%s effort=%s" % (k, h.get("model", "-"), h.get("effort", "-")))
        print("(no skills.<name> hints in kit.config.json)" if not c.get("skills") else "")
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "contract":
        # python3 scripts/kitconf.py contract --app acme-web: what every page of the app must do for its shell
        if not c.get("_app"):
            print("ERROR: contract needs --app <id>")
            sys.exit(1)
        lines = page_contract(c, c["_app"])
        print("\n".join("- " + x for x in lines) if lines else "No page contract (kit.config.json > apps[].pageContract is empty).")
        sys.exit(0)
    if len(sys.argv) > 2 and sys.argv[1] == "hook":
        # python3 scripts/kitconf.py hook prototype.post --app acme-web: run an optional project command, if set
        cmd = project_command(c, sys.argv[2])
        if not cmd:
            print("%s is not set in kit.config.json: nothing to run." % sys.argv[2])
            sys.exit(0)
        aid = c.get("_app") or ""
        ap = next((x for x in c.get("apps") or [] if x.get("id") == aid), {})
        sys.exit(1 if run_command(c, fill_command(cmd, app=aid, path=ap.get("path", ""), root=c["_root"]), sys.argv[2]) else 0)
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        e = check(c)
        for x in e:
            print("ERROR:", x)
        print("kit.config.json OK" if not e else f"{len(e)} error(s)")
        sys.exit(1 if e else 0)
    print(json.dumps(c, ensure_ascii=False, indent=2))
