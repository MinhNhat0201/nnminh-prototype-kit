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
    python3 scripts/kitconf.py contract --app acme-web   # the page contract of the app (apps[].pageContract), one line each;
                                                         # for a page app also the contract of each host app (usedBy)
    python3 scripts/kitconf.py add-page --like acme-notes --id acme-tasks --host acme-web [--name "Tasks"] [--dry-run]
        # a new page app built like an existing one: folder skeleton renamed (package.json, vite.config, tsconfig,
        # src/main.ts…, not its components), apps[] entry (type page, pageContract, output, usedBy), host-side steps
        # printed; apps[<host>].pageHook, when set, is run with {id} {path} {host} {like} {output} {usedBy} {root}
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
    "define": {"messageCalls": ["toast", "showToast", "alert", "confirm", "prompt", "notify", "snackbar", "showError",
                                "showMessage", "setCustomValidity"], "storageCalls": [], "storagePrefix": None},
    "figma": {"imageSuffix": None},
    "validate": {"touchTarget": {"default": 44, "desktop": 24}, "axePath": None, "setTheme": None,
                 "contentRoot": "main, #app, [role=main]"},
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


def page_hosts(cfg, app_id):
    """[(host app id or None, usedBy file)] of a page app (type "page"): the host is the app whose path holds the file
    (longest prefix). [] for other apps."""
    apps = (cfg or {}).get("apps") or []
    a = next((x for x in apps if x.get("id") == app_id), None)
    if not a or a.get("type") != "page":
        return []
    out = []
    for u in a.get("usedBy") or []:
        if not isinstance(u, str):
            continue
        un = u.replace("\\", "/").strip("/") + "/"
        hs = [x for x in apps if x.get("id") != app_id and x.get("type") != "page" and x.get("path")
              and un.startswith(x["path"].replace("\\", "/").strip("/") + "/")]
        h = max(hs, key=lambda x: len(x["path"]), default=None)
        out.append((h.get("id") if h else None, u))
    return out


def app_pages(cfg, app_id):
    """Pages to open in a browser for an app, as paths from the project root ({page} in check commands): for a page app
    the folder of each usedBy file when it holds an index.html, else its host app folder; for other apps the app folder
    (a file path stays as it is). Folders end with "/"."""
    root = Path(cfg["_root"])
    apps = {x.get("id"): x for x in cfg.get("apps") or []}
    hosts = page_hosts(cfg, app_id)
    if not hosts:
        p = (apps.get(app_id) or {}).get("path")
        return [p if (root / p).is_file() else p.rstrip("/") + "/"] if p else []
    out = []
    for hid, u in hosts:
        d = Path(u).parent.as_posix()
        hp = (apps.get(hid) or {}).get("path")
        page = d + "/" if (root / d / "index.html").is_file() or not hp else hp.rstrip("/") + "/"
        if page not in out:
            out.append(page)
    return out


def url_names_app(cmd):
    """True when a check command puts {app} inside a URL: wrong for a page app, whose id is no folder of the site."""
    return bool(re.search(r"https?://[^\s'\"]*\{app\}", cmd or ""))


def page_contract(cfg, app_id):
    """Lines of apps[].pageContract: what every page of the app must do for its shell (a string is one line). Default []."""
    for a in (cfg or {}).get("apps") or []:
        if a.get("id") == app_id:
            v = a.get("pageContract") or []
            return [v] if isinstance(v, str) else [str(x) for x in v]
    return []


def contract_text(cfg, app_id):
    """kitconf.py contract output: the app's page contract; for a page app also each host app's contract (the app whose
    path holds a usedBy file), with a heading per section."""
    empty = "No page contract (kit.config.json > apps[].pageContract is empty)."
    own = page_contract(cfg, app_id)
    hosts = page_hosts(cfg, app_id)
    body = "\n".join("- " + x for x in own) if own else empty
    if not hosts:
        return body
    out = ["Page app %s (its own pageContract):" % app_id, body]
    seen = set()
    for hid, used in hosts:
        if hid is None:
            out += ["", "No host app for %s: no apps[].path is a prefix of it." % used]
            continue
        if hid in seen:
            continue
        seen.add(hid)
        files = ", ".join(u for h, u in hosts if h == hid)
        lines = page_contract(cfg, hid)
        out += ["", "Host app %s (holds %s): its pageContract applies too:" % (hid, files),
                "\n".join("- " + x for x in lines) if lines else empty]
    return "\n".join(out)


PAGE_FILES = ("package.json", "package-lock.json", "vite.config.*", "tsconfig*.json", "src/main.ts", "src/main.js",
              "src/env.d.ts", ".gitignore")


def _pascal(s):
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", s) if w)


def plan_page(cfg, like_id, new_id, host_id, name=None):
    """What add-page does: {"path", "files": {rel: text}, "entry", "steps", "missing"} of a new page app built like an
    existing one (folder skeleton renamed, not its components), hosted by host_id. Raises ValueError on a bad request."""
    apps = cfg.get("apps") or []
    by = {a.get("id"): a for a in apps}
    like, host = by.get(like_id), by.get(host_id)
    if not like or like.get("type") != "page":
        raise ValueError("--like must be a declared app of type page: %s" % like_id)
    if not host or host.get("type") == "page":
        raise ValueError("--host must be a declared app that is not a page app: %s" % host_id)
    if new_id in by or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", new_id or ""):
        raise ValueError("--id must be a new app id in lowercase letters, digits and '-': %s" % new_id)
    root, lp = Path(cfg["_root"]), like["path"].strip("/")
    lslug = Path(lp).name
    pre, _, suf = like_id.partition(lslug) if lslug in like_id else ("", "", "")
    nslug = new_id[len(pre):len(new_id) - len(suf)] if lslug in like_id and new_id.startswith(pre) and new_id.endswith(suf) \
        and len(new_id) > len(pre) + len(suf) else new_id
    np_ = (Path(lp).parent / nslug).as_posix()
    if not (root / lp).is_dir():
        raise ValueError("the folder of %s is missing: %s" % (like_id, lp))
    if (root / np_).exists():
        raise ValueError("%s already exists" % np_)
    swaps = [(lp, np_), (like_id, new_id), (lslug, nslug)]
    # library global names (vite build.lib.name): NotesVue -> TasksVue; the slug's own Pascal form only when the id
    # follows the like app's pattern, else "Tasks" in AcmeTasks would become AcmeAcmeNotes
    pascal = [(_pascal(like_id), _pascal(new_id))] + ([(_pascal(lslug), _pascal(nslug))] if nslug != new_id else [])

    def ren(v, config=True):
        if isinstance(v, str):
            for a, b in swaps + (pascal if config else []):
                v = v.replace(a, b)
        return v
    files = {}
    for pat in PAGE_FILES:
        for f in sorted((root / lp).glob(pat)):
            if not f.is_file():
                continue
            rel, text = f.relative_to(root / lp).as_posix(), f.read_text(encoding="utf-8")
            if rel in ("package.json", "package-lock.json"):
                data = json.loads(text)
                pname = data["name"] = new_id  # the package is named after the app id
                if rel == "package.json" and name and "description" in data:
                    data["description"] = name
                if "" in (data.get("packages") or {}):
                    data["packages"][""]["name"] = pname
                text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            else:
                text = ren(text, config=not rel.startswith("src/"))  # src/: keep component names (./Notes.vue)
            files[rel] = text
    missing = []
    for rel in ("src/main.ts", "src/main.js"):
        for m in re.finditer(r"""(?:from\s+|import\s+)["'](\.{1,2}/[^"']+)["']""", files.get(rel, "")):
            tgt = (Path(rel).parent / m.group(1)).as_posix()
            if not any(k == tgt or k.startswith(tgt + ".") or k.startswith(tgt + "/") for k in files):
                missing.append((rel, m.group(1)))
    entry = {k: ren(v) for k, v in like.items() if k not in ("usedBy", "pageContract", "pageHook")}
    entry.update(id=new_id, name=name or new_id, path=np_, type="page")
    used = []
    for hid, u in page_hosts(cfg, like_id):
        if hid is None:
            continue
        rel = Path(u).relative_to(by[hid]["path"].strip("/")).as_posix()
        u2 = (Path(host["path"].strip("/")) / ren(rel)).as_posix()
        if u2 not in used:
            used.append(u2)
    entry["usedBy"] = used or ["%s/%s/%s.js" % (host["path"].strip("/"), nslug, nslug)]
    if like.get("pageContract"):
        entry["pageContract"] = like["pageContract"]
    hb = host.get("build") or ""
    steps = ["cd %s && npm install (node_modules is not copied)" % np_,
             "Write the page in %s/src (App.vue and its components); the like app's components are not copied" % np_]
    for rel in sorted({r for r, _x in missing}):
        steps.append("%s/%s imports %s, which are not copied: write them, or trim %s"
                     % (np_, rel, ", ".join(x for r, x in missing if r == rel), rel))
    steps += ["Host build (apps[%s].build): run `%s` before the host build step%s" % (
                  host_id, entry.get("build") or "the page build", " (now: %s)" % hb if hb else ""),
              "Host build: copy %s to %s" % (entry.get("output") or "the build output", ", ".join(entry["usedBy"])),
              "Host page: the page of %s that loads %s, its route and nav entry (model: the like app's host page)"
              % (host_id, ", ".join(Path(x).name for x in entry["usedBy"])),
              "Read the contract: python3 <kit>/scripts/kitconf.py contract --app %s" % new_id]
    return {"path": np_, "files": files, "entry": entry, "steps": steps, "missing": missing, "like": like_id, "host": host_id}


def add_page(cfg, plan, dry=False):
    """Write the planned folder and the kit.config.json entry (after the like app), print the host-side steps, run
    apps[<host>].pageHook when set. Returns the exit code."""
    root = Path(cfg["_root"])
    print("%s page app %s in %s (like %s, host %s)" % ("Would add" if dry else "Adding", plan["entry"]["id"], plan["path"],
                                                     plan["like"], plan["host"]))
    for rel in plan["files"]:
        print("  %s %s/%s" % ("would write" if dry else "write", plan["path"], rel))
    print("kit.config.json > apps[] entry:\n" + json.dumps(plan["entry"], ensure_ascii=False, indent=2))
    hook = next((a.get("pageHook") for a in cfg.get("apps") or [] if a.get("id") == plan["host"]), None)
    if dry:
        print("Dry run: nothing written.%s" % (" pageHook would run: " + hook if hook else ""))
    else:
        for rel, text in plan["files"].items():
            f = root / plan["path"] / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        cf = root / "kit.config.json"
        text = cf.read_text(encoding="utf-8")
        raw = json.loads(text)
        ids = [a.get("id") for a in raw.get("apps") or []]
        raw.setdefault("apps", []).insert(ids.index(plan["like"]) + 1 if plan["like"] in ids else len(ids), plan["entry"])
        ind = re.search(r"\n( +)\S", text)
        cf.write_text(json.dumps(raw, ensure_ascii=False, indent=len(ind.group(1)) if ind else 2) + "\n", encoding="utf-8")
    code = 0
    if hook and not dry:
        e = plan["entry"]
        code = run_command(cfg, fill_command(hook, id=e["id"], path=e["path"], host=plan["host"], like=plan["like"],
                                             output=e.get("output") or "", usedBy=e["usedBy"][0], root=cfg["_root"]),
                           "apps[%s].pageHook" % plan["host"])
    print("Left to do%s:" % (" (the pageHook may have done some)" if hook else ", by hand (no apps[%s].pageHook)" % plan["host"]))
    for i, x in enumerate(plan["steps"], 1):
        print("  %d. %s" % (i, x))
    return code


def app(cfg, app_id):
    for a in cfg["apps"]:
        if a.get("id") == app_id:
            return _merge({"type": "single", "entry": "index.html", "build": None, "check": None, "stack": cfg["stack"],
                           "pageContract": [], "pageHook": None}, a)
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
    df = cfg.get("define") or {}
    for k in ("messageCalls", "storageCalls"):
        v = df.get(k)
        if v is not None and (not isinstance(v, list) or not all(isinstance(x, str) and x for x in v)):
            errs.append("define.%s must be a list of call names, e.g. [\"X.store.get\", \"toast\"]" % k)
    if df.get("storagePrefix") is not None and not isinstance(df["storagePrefix"], str):
        errs.append("define.storagePrefix must be a string (the prefix the storage wrapper adds to every key) or null")
    for a in cfg["apps"]:
        if a.get("pageHook") is not None and not isinstance(a["pageHook"], str):
            errs.append(f"app '{a.get('id')}': pageHook must be a project command (placeholders {{id}}, {{path}}, ...) or null")
    return errs


def warnings(cfg):
    """Settings that are valid but have no effect: printed by kitconf.py check, never an error."""
    out = []
    try:
        raw = json.loads((Path(cfg["_root"]) / "kit.config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError):
        return out
    vue = [a for a in cfg.get("apps") or [] if a.get("stack", cfg.get("stack")) == "vue"]
    if vue and all(a.get("type") == "page" for a in vue) and "vueCss" in (raw.get("local") or {}):
        out.append("local.vueCss is set, but every vue app is type page (%s): vueCss is only read for vue SPAs. A page app "
                   "puts its local CSS blocks in the host app's CSS, as the host's pageContract says (kitconf.py contract "
                   "--app <page app>); remove local.vueCss or point the pageContract at the host file."
                   % ", ".join(a.get("id") for a in vue))
    return out


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
    # page apps: host app by path prefix; pages to open = host folder of the usedBy file
    assert page_hosts(c, "pg") == [("web", "apps/web/pg.js")] and page_hosts(c, "web") == []
    assert app_pages(c, "pg") == ["apps/web/"] and app_pages(c, "web") == ["apps/web/"], app_pages(c, "pg")
    (d / "apps" / "web" / "pg").mkdir(parents=True)
    (d / "apps" / "web" / "pg" / "index.html").write_text("<script src='pg.js'></script>")
    c["apps"][2]["usedBy"] = ["apps/web/pg/pg.js", "apps/webx/pg.js"]
    assert page_hosts(c, "pg") == [("web", "apps/web/pg/pg.js"), (None, "apps/webx/pg.js")], page_hosts(c, "pg")
    assert app_pages(c, "pg") == ["apps/web/pg/", "apps/webx/"], app_pages(c, "pg")
    assert url_names_app("node a11y.js http://localhost:8765/apps/{app}/") and not url_names_app("x.py {app} http://h/{page}")
    c["apps"][2]["usedBy"] = ["apps/web/pg.js"]
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
    # 0.12: define keys, contract of a page app with its host, add-page, warnings (local.vueCss with page apps only)
    import contextlib
    import io
    c = load(d)
    assert c["define"]["storageCalls"] == [] and "toast" in c["define"]["messageCalls"]
    c["define"] = {"storageCalls": "X.store.get", "storagePrefix": 3}
    assert len([e for e in check(c) if e.startswith("define.")]) == 2, check(c)
    pg = d / "vue" / "notes"
    (pg / "src" / "components").mkdir(parents=True)
    (pg / "package.json").write_text(json.dumps({"name": "notes-vue", "description": "Notes page", "scripts": {}}))
    (pg / "package-lock.json").write_text(json.dumps({"name": "notes-vue", "packages": {"": {"name": "notes-vue"}, "node_modules/x": {"name": "x"}}}))
    (pg / "vite.config.ts").write_text('lib: { name: "NotesVue", fileName: () => "notes.js" }\n')
    (pg / "src" / "main.ts").write_text('import { createApp } from "vue"\nimport App from "./App.vue"\ncreateApp(App).mount("#mod")\n')
    (pg / "src" / "App.vue").write_text("<template><p>Notes</p></template>\n")
    (pg / "src" / "components" / "List.vue").write_text("<template />\n")
    raw = {"ds": "ds/acme", "local": {"vueCss": "src/styles/local.css"}, "apps": [
        {"id": "web", "path": "apps/web", "type": "multi", "pageContract": ["Edit shared/ through build.py only"]},
        {"id": "web2", "path": "apps/web2", "type": "multi", "pageHook": None},
        {"id": "notes-vue", "path": "vue/notes", "stack": "vue", "type": "page", "build": "cd vue/notes && npm run build",
         "output": "vue/notes/dist/notes.js", "usedBy": ["apps/web/notes/notes.js"], "pageContract": ["Call X.ready() once"]}]}
    (d / "kit.config.json").write_text(json.dumps(raw, indent=2))
    c = load(d)
    txt = contract_text(c, "notes-vue")
    assert "Page app notes-vue" in txt and "- Call X.ready() once" in txt and "Host app web (holds apps/web/notes/notes.js)" in txt \
        and "- Edit shared/ through build.py only" in txt, txt
    assert contract_text(c, "web") == "- Edit shared/ through build.py only", "a host app prints its own contract only"
    assert app(c, "web")["pageHook"] is None, "pageHook is off by default"
    assert warnings(c) and "local.vueCss" in warnings(c)[0], warnings(c)
    for bad in (("web", "x-vue", "web"), ("notes-vue", "notes-vue", "web"), ("notes-vue", "tasks-vue", "notes-vue")):
        try:
            plan_page(c, *bad)
            raise AssertionError("plan_page should refuse %s" % (bad,))
        except ValueError:
            pass
    pl = plan_page(c, "notes-vue", "tasks-vue", "web2", "Tasks")
    e = pl["entry"]
    assert pl["path"] == "vue/tasks" and e["usedBy"] == ["apps/web2/tasks/tasks.js"] and e["output"] == "vue/tasks/dist/tasks.js", pl
    assert e["build"] == "cd vue/tasks && npm run build" and e["pageContract"] == ["Call X.ready() once"] and e["name"] == "Tasks", e
    assert set(pl["files"]) == {"package.json", "package-lock.json", "vite.config.ts", "src/main.ts"}, sorted(pl["files"])
    assert '"TasksVue"' in pl["files"]["vite.config.ts"] and '"tasks.js"' in pl["files"]["vite.config.ts"], pl["files"]["vite.config.ts"]
    lock = json.loads(pl["files"]["package-lock.json"])
    assert lock["name"] == lock["packages"][""]["name"] == "tasks-vue" and lock["packages"]["node_modules/x"]["name"] == "x", lock
    assert json.loads(pl["files"]["package.json"])["description"] == "Tasks" and any("./App.vue" in x for x in pl["steps"]), pl["steps"]
    with contextlib.redirect_stdout(io.StringIO()):
        assert add_page(c, pl, dry=True) == 0 and not (d / "vue" / "tasks").exists(), "dry run writes nothing"
        add_page(c, pl)
    assert (d / "vue" / "tasks" / "src" / "main.ts").is_file() and not (d / "vue" / "tasks" / "src" / "App.vue").exists()
    c = load(d)
    assert [a["id"] for a in c["apps"]] == ["web", "web2", "notes-vue", "tasks-vue"] and page_hosts(c, "tasks-vue") == [("web2", "apps/web2/tasks/tasks.js")]
    raw["local"] = {}
    (d / "kit.config.json").write_text(json.dumps(raw, indent=2))
    assert warnings(load(d)) == [], "vueCss left at its default: no warning"
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
        print(contract_text(c, c["_app"]))
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "add-page":
        # kitconf.py add-page --like <page app> --id <new id> --host <host app> [--name "…"] [--dry-run]
        opt = {k: sys.argv[sys.argv.index(k) + 1] for k in ("--like", "--id", "--host", "--name") if k in sys.argv[:-1]}
        if not all(k in opt for k in ("--like", "--id", "--host")):
            print("ERROR: add-page needs --like <page app id> --id <new app id> --host <host app id>")
            sys.exit(1)
        try:
            pl = plan_page(c, opt["--like"], opt["--id"], opt["--host"], opt.get("--name"))
        except ValueError as ex:
            print("ERROR:", ex)
            sys.exit(1)
        sys.exit(1 if add_page(c, pl, "--dry-run" in sys.argv) else 0)
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
        for x in warnings(c):
            print("WARN:", x)
        print("kit.config.json OK" if not e else f"{len(e)} error(s)")
        sys.exit(1 if e else 0)
    print(json.dumps(c, ensure_ascii=False, indent=2))
