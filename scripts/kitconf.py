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
    "local": {"prefix": "x-", "marker": "LOCAL", "registry": "docs/local-components.json"},
    "handoff": {"dir": "docs/handover", "zipName": "Design - {pbi}", "maxZipMB": 3, "figmaRequired": True},
    "email": {"subject": "[{app}] Design - {feature} - {version}"},
    "deploy": {"type": "none", "site": None},
    "paths": {"changelog": "CHANGELOG.md", "plans": "docs/plans", "audits": "docs/audits"},
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
    "rules": "rules.md",
    "library": {},
    "figma": {"libraries": [], "collections": {}, "modes": {}},
    "preset": {},
}

STACKS = ("html", "react", "vue")
APP_TYPES = ("single", "multi", "spa")


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


def app(cfg, app_id):
    for a in cfg["apps"]:
        if a.get("id") == app_id:
            return _merge({"type": "single", "entry": "index.html", "build": None, "check": None}, a)
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
        if a.get("type", "single") not in APP_TYPES:
            errs.append(f"app '{a.get('id')}': type must be one of {', '.join(APP_TYPES)}")
    ds = cfg["_ds"]
    if ds:
        if not ds["tokens"]["prefix"].startswith("--"):
            errs.append("ds.json > tokens.prefix must start with '--'")
        b = ds["css"]["bundle"]
        if b and "://" not in b and not Path(ds_path(cfg, b)).is_file():
            errs.append(f"ds.json > css.bundle not found: {b}")
    return errs


if __name__ == "__main__":
    c = load()
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        e = check(c)
        for x in e:
            print("ERROR:", x)
        print("kit.config.json OK" if not e else f"{len(e)} error(s)")
        sys.exit(1 if e else 0)
    print(json.dumps(c, ensure_ascii=False, indent=2))
