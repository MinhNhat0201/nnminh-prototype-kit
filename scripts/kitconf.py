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
    python3 scripts/kitconf.py --selftest
"""
import json
import os
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]

DEFAULTS = {
    "language": "en",
    "stack": "html",
    "ds": None,
    "apps": [],
    "local": {"prefix": "x-", "marker": "LOCAL", "registry": "docs/local-components.json",
              "command": {"update": None, "check": None}, "fields": {}},
    "handoff": {"dir": "docs/handover", "zipName": "Design - {pbi}", "maxZipMB": 3, "figmaRequired": True,
                "itemLabel": "", "grepLabels": [], "dsLabel": "auto", "dsLabelCheck": "warn",
                "specFiles": {"archive": "archive.md", "crossPage": "cross-page.md", "legacy": []},
                "csv": {"feature": None, "qc": None}, "pre": None, "post": None},
    "email": {"subject": "[{app}] Design - {feature} - {version}", "attachLimitMB": 3, "demoLinks": True, "maxItems": 12},
    "deploy": {"type": "none", "site": None},
    "sync": {"command": None, "check": None},
    "review": {"extraChecks": []},
    "validate": {"touchTarget": {"default": 44, "desktop": 24}},
    "skills": {},
    "paths": {"changelog": "CHANGELOG.md", "plans": "docs/plans", "audits": "docs/audits", "explorations": "docs/explorations", "context": "product-context", "validation": "docs/validation", "verify": "docs/verify"},
}

DS_DEFAULTS = {
    "label": None,
    "version": "0.0.0",
    "platforms": ["web"],
    "tokens": {"prefix": "--ds-", "roles": {}, "scale": {}, "file": "tokens.json"},
    "css": {"bundle": None, "sources": [], "marker": {"begin": "@ds:begin", "end": "@ds:end"}},
    "version_label": {"text": "{label} {version}", "meta": "ds-version"},
    "theming": {},
    "breakpoints": {"compact": 0, "medium": 600, "expanded": 840},
    "icons": {},
    "catalog": "catalog.md",
    "catalog_json": "catalog.json",
    "rules": "rules.md",
    "library": {},
    "figma": {"libraries": [], "collections": {}, "modes": {}},
    "preset": {},
}

STACKS = ("html", "react", "vue")
APP_TYPES = ("single", "multi", "spa")
SKILLS = ("brief", "kickoff", "adopt", "define", "context", "explore", "prototype", "validate", "annotate", "wireflow",
          "mockup", "handoff", "share", "verify", "review", "sync", "contribute", "document")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
DS_LABEL_SOURCES = ("auto", "pkg", "spec", "ds", "prototype")
CHECK_LEVELS = ("off", "warn", "error")
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


def load(start=None, require=True):
    root = find_root(start)
    if root is None:
        if require:
            sys.exit("ERROR: kit.config.json not found in this folder or any parent. Run the kickoff skill first.")
        return None
    cfg = _merge(DEFAULTS, json.loads((root / "kit.config.json").read_text(encoding="utf-8")))
    cfg["_root"] = str(root)
    cfg["_ds"], cfg["_ds_dir"] = None, None
    if cfg.get("ds"):
        ds_dir = (root / cfg["ds"]).resolve()
        f = ds_dir / "ds.json"
        if f.is_file():
            ds = _merge(DS_DEFAULTS, json.loads(f.read_text(encoding="utf-8")))
            ds["label"] = ds.get("label") or ds.get("name")
            cfg["_ds"], cfg["_ds_dir"] = ds, str(ds_dir)
    return cfg


def ds_path(cfg, rel):
    """Resolve a path from ds.json (relative to the profile folder). URLs are returned unchanged."""
    if rel is None:
        return None
    if "://" in rel:
        return rel
    return str(Path(cfg["_ds_dir"]) / rel)


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
    """Names of the special spec files: {"archive": ..., "crossPage": ..., "special": set of stems that are not units}."""
    sf = ((cfg or {}).get("handoff") or {}).get("specFiles") or {}
    arc, cross = sf.get("archive") or "archive.md", sf.get("crossPage") or "cross-page.md"
    stems = {"index", "flows", Path(arc).stem, Path(cross).stem, "archive", "cross-page"}
    stems |= {Path(x).stem for x in sf.get("legacy") or []}
    return {"archive": arc, "crossPage": cross, "special": stems}


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


def app(cfg, app_id):
    for a in cfg["apps"]:
        if a.get("id") == app_id:
            return _merge({"type": "single", "entry": "index.html", "build": None, "check": None, "stack": cfg["stack"]}, a)
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
    ds = cfg["_ds"]
    if ds:
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
    print("kitconf selftest OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    c = load()
    if len(sys.argv) > 1 and sys.argv[1] == "skills":
        for k in SKILLS:
            h = skill_hint(c, k)
            if h:
                print("%-11s model=%s effort=%s" % (k, h.get("model", "-"), h.get("effort", "-")))
        print("(no skills.<name> hints in kit.config.json)" if not c.get("skills") else "")
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        e = check(c)
        for x in e:
            print("ERROR:", x)
        print("kit.config.json OK" if not e else f"{len(e)} error(s)")
        sys.exit(1 if e else 0)
    print(json.dumps(c, ensure_ascii=False, indent=2))
