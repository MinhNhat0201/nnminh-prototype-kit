#!/usr/bin/env python3
"""Rules registry: one Markdown file per rule, in four layers, read by every skill instead of long rule documents.

Layers (a later layer may override an earlier one, with `overrides: <id>` and a reason):
  kit      <kit>/rules/                       generic rules every project inherits (ids numbered 900-999)
  ds       <DS profile>/rules/                rules of a DS profile; apply to the apps that use that profile
                                             (apps[].ds, else the top-level ds; ids numbered 500-899)
  project  <kit.config.json > paths.rules>/   rules of this project (default rules/; ids numbered 001-499)
  app      same folder, layer: app            rules of some apps only (applies_to is required)

Rule file <layer folder>/<category>/<ID>-<slug>.md:

  ---
  id: STY-001
  title: Use DS tokens only
  category: styling
  layer: project
  applies_to: []                  app ids; empty = every app
  skills: [prototype, review]     skills that must load it; empty = every skill
  severity: must                  must | should | note
  status: active                  proposed | active | deprecated | superseded
  since: 2026-11-22               date, or Unconfirmed (proposed rules only)
  decision: D-003                 decision log id (required for active project/app rules when the log exists)
  check: python3 scripts/x.py {app}   optional command: exit 0 = followed ({app}, {path}, {root} are replaced)
  overrides:                      id of a rule of an earlier layer this rule replaces (needs reason)
  reason:
  superseded_by:
  supersedes:
  exceptions:
    - app: acme-legacy
      note: Keeps raw colours until the rebuild
      decision: D-004
  history:
    - 2026-11-22 · active · D-003
  ---
  Rule text first (one short paragraph), then the reason. Project language.

Front matter: "key: value" lines; "[a, b]" is a list; a key with nothing after the colon takes the indented
"- item" lines below it (strings, or "- key: value" maps whose further keys are indented more). Lines starting with
"#" are comments. Files named README.md or starting with "_" are not rules.

Commands:
  rules.py list     [--app A] [--skill S] [--category C] [--severity must] [--status active|all] [--layer L]
                    [--brief|--full] [--json]   rules in force, layers and exceptions resolved
  rules.py show     <id> [--app A]   (alias: explain) text, where it applies, decision, exceptions, history
  rules.py add      --title "..." --category styling --severity must [--layer project|app|ds] [--applies-to a,b]
                    [--skills prototype,review] [--decision D-003] [--status proposed|active] [--check "cmd"]
                    [--overrides ID --reason "..."] [--exception "app=note[=D-004]"]... [--body "..." | --body-file f]
                    [--since YYYY-MM-DD] [--app A (ds layer: profile of that app)]
  rules.py except   <id> --app A --note "..." [--decision D-004]   add an app exception to a project or DS rule
  rules.py deprecate <id> --reason "..." [--decision D-005]
  rules.py supersede <old> --by <new> [--decision D-006]
  rules.py check    [--app A] [--skill S] [--category C] [--id ID] [--json <file>|-] [--url U]   run the check commands of
                    the active rules in scope; exit 1 when a must rule fails. A page app (apps[].type page) whose check
                    URL names the app ({app} in the URL) opens --url instead, else each host page (usedBy) on that server
  rules.py coverage [--json]        must/should rules with and without an automated check, per category and per app
  rules.py conflicts                format errors, contradicting overrides, stale exceptions, superseded rules without
                    a successor, unknown apps, skills, categories or decisions; exit 1 on error
  rules.py export   [--format md|html|claude] [--app A] [--out <file>] [--into <file>]   "Project rules" page, or
                    the compact block for CLAUDE.md (between <!-- kit:rules:begin --> and <!-- kit:rules:end -->)
  rules.py import-md <file> [--layer project] [--category process] [--map "Heading words=category"]... [--dry-run]
                    draft rule files (status proposed, since and decision Unconfirmed) from an existing rules
                    document: one rule per top-level bullet; writes <rules>/_import-review.md to confirm each one
  rules.py --selftest
Never commits, pushes or sends anything. Messages in English; generated pages in the project language.
"""
import argparse
import datetime as dt
import json
import re
import shlex
import socket
import subprocess
import sys
import unicodedata
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "scripts"))
sys.path.insert(0, str(KIT / "skills" / "context" / "scripts"))
import kitconf  # noqa: E402
from kitconf import load, t, SKILLS  # noqa: E402

LAYERS = ("kit", "ds", "project", "app")
RANK = {k: i for i, k in enumerate(LAYERS)}
SEVERITIES = ("must", "should", "note")
STATUSES = ("proposed", "active", "deprecated", "superseded")
CATEGORIES = {"styling": "STY", "theming": "THM", "density": "DEN", "layout": "LAY", "content": "CNT", "a11y": "A11Y",
              "pages": "PAG", "assets": "AST", "flags": "FLG", "build": "BLD", "data": "DAT", "handoff": "HND",
              "figma": "FIG", "email": "EML", "security": "SEC", "process": "PRC"}
FIELDS = ("id", "title", "category", "layer", "applies_to", "skills", "severity", "status", "since", "decision", "check",
          "overrides", "reason", "superseded_by", "supersedes", "exceptions", "history")
LISTS = ("applies_to", "skills", "exceptions", "history")
REQUIRED = ("id", "title", "category", "layer", "severity", "status", "since")
UNCONFIRMED = "Unconfirmed"
RANGES = {"kit": (900, 999), "ds": (500, 899), "project": (1, 499), "app": (1, 499)}
ID_RX = re.compile(r"^([A-Z][A-Z0-9]{1,5})-(\d{3,})$")
# Activity groups a rule may name in `skills` instead of (or with) skill names: rules for work that is not a skill.
# A rule that names only activities is left out of `list --skill <skill>`. "*" = every skill and activity (like []).
ACTIVITIES = ("scripts", "pr", "commit", "deploy", "release")
PLACEHOLDERS = ("app", "path", "root", "platform", "stack", "page")
SKIP_EXIT = 77   # a check command exits 77 (or prints a line "SKIP: <reason>") when it does not apply or scanned nothing
URL_RX = re.compile(r"https?://([A-Za-z0-9.-]+|\[[0-9a-fA-F:]+\])(?::(\d+))?")
BLOCK = ("<!-- kit:rules:begin -->", "<!-- kit:rules:end -->")


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def today():
    return dt.date.today().isoformat()


def ascii_fold(s):
    """Letters without diacritics (NFKD), d for the stroked d, so file names stay readable in any language."""
    s = s.replace("đ", "d").replace("Đ", "D").replace("ß", "ss").replace("ø", "o").replace("Ø", "O").replace("ł", "l")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", ascii_fold(s).lower()).strip("-")
    return s[:48].strip("-") or "rule"


# ---------- front matter ----------

def _scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in v[1:-1].split(",") if x.strip()]
    return v


def parse_front(text):
    """(fields, body) of a rule file. Raises ValueError on a malformed front matter."""
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n?", text, re.S)
    if not m:
        raise ValueError("missing the front matter (--- ... ---)")
    out, key, item = {}, None, None
    for n, raw in enumerate(m.group(1).splitlines(), 2):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        ind = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if ind == 0:
            if ":" not in line:
                raise ValueError("line %d: expected 'key: value'" % n)
            key, v = line.split(":", 1)
            key, item = key.strip(), None
            out[key] = _scalar(v) if v.strip() else ""
            continue
        if key is None:
            raise ValueError("line %d: indented line before any key" % n)
        if line.startswith("- "):
            if not isinstance(out.get(key), list):
                out[key] = []
            rest = line[2:].strip()
            km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", rest)
            if km and not re.match(r"^\d{4}-\d{2}-\d{2}", rest):
                item = {km.group(1): _scalar(km.group(2))}
                out[key].append(item)
            else:
                item = None
                out[key].append(_scalar(rest))
        elif item is not None and ":" in line:
            k, v = line.split(":", 1)
            item[k.strip()] = _scalar(v)
        else:
            raise ValueError("line %d: cannot read '%s'" % (n, line[:40]))
    return out, text[m.end():]


def _q(v):
    v = str(v)
    return '"%s"' % v.replace('"', "'") if (v[:1] in "[\"'#" or v.strip() != v or ": " in v) else v


def dump_front(rec):
    L = ["---"]
    for k in FIELDS:
        v = rec.get(k, [] if k in LISTS else "")
        if k in ("applies_to", "skills"):
            L.append("%s: [%s]" % (k, ", ".join(v or [])))
        elif k in ("exceptions", "history"):
            L.append(k + ":")
            for x in v or []:
                if isinstance(x, dict):
                    keys = [kk for kk in ("app", "note", "decision") if x.get(kk)] + [kk for kk in x if kk not in ("app", "note", "decision")]
                    L.append("  - %s: %s" % (keys[0], _q(x[keys[0]])))
                    L += ["    %s: %s" % (kk, _q(x[kk])) for kk in keys[1:]]
                else:
                    L.append("  - " + str(x))
        else:
            L.append(("%s: %s" % (k, _q(v))).rstrip() if v != "" else k + ":")
    return "\n".join(L) + "\n---\n"


def norm(rec):
    for k in FIELDS:
        v = rec.get(k)
        if k in LISTS:
            rec[k] = v if isinstance(v, list) else ([x.strip() for x in v.split(",") if x.strip()] if isinstance(v, str) and v else [])
        else:
            rec[k] = v if isinstance(v, str) else ("" if v is None else str(v))
    return rec


# ---------- loading the layers ----------

def rules_dir(cfg):
    return Path(cfg["_root"]) / ((cfg.get("paths") or {}).get("rules") or "rules")


def categories(cfg):
    out = dict(CATEGORIES)
    out.update(((cfg or {}).get("rules") or {}).get("categories") or {})
    return out


def sources(cfg):
    """[(folder, expected layer, profile path or None, app ids of that profile or None)]
    A profile whose ds.json has rules.from inherits the DS-layer rules of that profile: its folder is read once and
    applies to the apps of both profiles (so inherited rules never count twice)."""
    out = [(KIT / "rules", "kit", None, None)]
    folders = {}   # resolved rules folder -> [owner profile path, app ids]
    for rel, apps in kitconf.profiles(cfg).items():
        ds, d = kitconf.read_profile(cfg["_root"], rel)
        seen, cur_rel = set(), rel
        while d and d not in seen:   # this profile's folder, then the chain of rules.from
            seen.add(d)
            key = str((Path(d) / "rules").resolve())
            ent = folders.setdefault(key, [cur_rel, []])
            ent[1] += [a for a in apps if a not in ent[1]]
            frm = kitconf.ds_rules(ds)[1]
            if not frm:
                break
            cur_rel = (Path(cur_rel) / frm).as_posix()
            ds, d = kitconf.read_profile(cfg["_root"], cur_rel)
    for key, (owner, apps) in folders.items():
        out.append((Path(key), "ds", owner, apps))
    out.append((rules_dir(cfg), "project", None, None))
    return out


def read_rule(path, src_layer, profile=None, profile_apps=None):
    text = path.read_text(encoding="utf-8")
    fm, body = parse_front(text)
    rec = norm(fm)
    rec.update(_path=path, _body=body.strip("\n"), _src=src_layer, _profile=profile, _profile_apps=profile_apps)
    return rec


def load_rules(cfg):
    """(rules, parse errors). Every rule carries _path, _body, _src (folder layer), _profile (ds layer)."""
    recs, errs = [], []
    for folder, layer, profile, apps in sources(cfg):
        if not folder.is_dir():
            continue
        for f in sorted(folder.rglob("*.md")):
            if f.name == "README.md" or f.name.startswith("_"):
                continue
            try:
                recs.append(read_rule(f, layer, profile, apps))
            except (ValueError, UnicodeDecodeError) as e:
                errs.append("%s: %s" % (rel(cfg, f), e))
    return recs, errs


def rel(cfg, p):
    p = Path(p)
    for base in (Path(cfg["_root"]), KIT):
        try:
            return p.resolve().relative_to(base.resolve()).as_posix()
        except ValueError:
            pass
    return str(p)


def decision_log(cfg):
    """{id: decision record} of the context decision log, or None when the project keeps no log."""
    try:
        import decisions as D
    except ImportError:
        return None
    d = D.ddir(cfg)
    if not d.is_dir() or not list(d.glob("D-*.md")):
        return None
    recs, _ = D.load_all(cfg)
    return {r["id"].upper(): r for r in recs}


# ---------- scope ----------

def app_ids(cfg):
    return [a.get("id") for a in cfg.get("apps") or [] if a.get("id")]


def in_scope(rule, app):
    """Does the rule (ignoring exceptions and overrides) cover app? app None = the project as a whole."""
    if rule["_src"] == "ds" and app and rule.get("_profile_apps") is not None and app not in rule["_profile_apps"]:
        return False
    return not rule["applies_to"] or app is None or app in rule["applies_to"]


def skill_match(rule, skill):
    """[] and ["*"] = every skill and activity; else the skill or activity must be listed."""
    return not skill or not rule["skills"] or "*" in rule["skills"] or skill in rule["skills"]


def exception_for(rule, app):
    return next((e for e in rule["exceptions"] if isinstance(e, dict) and e.get("app") == app), None) if app else None


def overriders(rules, rule, app):
    """Active rules of a later layer that override `rule` for app."""
    return [o for o in rules if o["overrides"] == rule["id"] and o["status"] == "active" and o is not rule
            and RANK.get(o["layer"], -1) > RANK.get(rule["layer"], 99) and in_scope(o, app)]


def resolve(cfg, rules, app=None, skill=None, category=None, severity=None, status="active", layer=None):
    """(rules in force, [(rule, exception)], [(rule, overriding rules)]) for the filters."""
    keep, excepted, overridden = [], [], []
    for r in rules:
        if status != "all" and r["status"] != status:
            continue
        if category and r["category"] != category or severity and r["severity"] != severity or layer and r["layer"] != layer:
            continue
        if not skill_match(r, skill):
            continue
        if not in_scope(r, app):
            continue
        e = exception_for(r, app)
        if e:
            excepted.append((r, e))
            continue
        o = overriders(rules, r, app) if app else []
        if o:
            overridden.append((r, o))
            continue
        keep.append(r)
    order = {s: i for i, s in enumerate(SEVERITIES)}
    keep.sort(key=lambda r: (order.get(r["severity"], 9), r["category"], RANK.get(r["layer"], 9), r["id"]))
    return keep, excepted, overridden


def statement(rule):
    """First paragraph of the body: the rule itself."""
    return re.split(r"\n\s*\n", rule["_body"].strip(), maxsplit=1)[0].strip() if rule["_body"].strip() else ""


# ---------- validation ----------

def validate(cfg, rules, parse_errs=()):
    """(errors, warnings) over every rule of every layer."""
    err, warn = list(parse_errs), []
    cats, apps, log = categories(cfg), set(app_ids(cfg)), decision_log(cfg)
    by_id = {}
    for r in rules:
        where = "%s (%s)" % (r.get("id") or "?", rel(cfg, r["_path"]))
        for k in REQUIRED:
            if not r.get(k):
                err.append("%s: %s is missing" % (where, k))
        m = ID_RX.match(r["id"] or "")
        if r["id"] and not m:
            err.append("%s: id must look like STY-001 (category prefix, hyphen, number)" % where)
        if r["id"] in by_id:
            err.append("%s: duplicate id (also %s)" % (where, rel(cfg, by_id[r["id"]]["_path"])))
        by_id.setdefault(r["id"], r)
        if r["category"] and r["category"] not in cats:
            err.append("%s: unknown category '%s' (declare it in kit.config.json > rules.categories)" % (where, r["category"]))
        elif m and r["category"] and m.group(1) != cats[r["category"]]:
            err.append("%s: id prefix %s does not match category %s (%s)" % (where, m.group(1), r["category"], cats[r["category"]]))
        if r["layer"] and r["layer"] not in LAYERS:
            err.append("%s: layer must be one of %s" % (where, ", ".join(LAYERS)))
        elif r["layer"] and (r["layer"] != r["_src"] and not (r["_src"] == "project" and r["layer"] == "app")):
            err.append("%s: layer %s does not match its folder (%s layer)" % (where, r["layer"], r["_src"]))
        if m and r["layer"] in RANGES:
            lo, hi = RANGES[r["layer"]]
            if not lo <= int(m.group(2)) <= hi:
                err.append("%s: %s rules are numbered %03d-%03d" % (where, r["layer"], lo, hi))
        if r["severity"] and r["severity"] not in SEVERITIES:
            err.append("%s: severity must be one of %s" % (where, ", ".join(SEVERITIES)))
        if r["status"] and r["status"] not in STATUSES:
            err.append("%s: status must be one of %s" % (where, ", ".join(STATUSES)))
        if r["since"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["since"]):
            if r["since"] != UNCONFIRMED or r["status"] != "proposed":
                err.append("%s: since must be a date YYYY-MM-DD (Unconfirmed only while proposed)" % where)
        if r["layer"] == "app" and not r["applies_to"]:
            err.append("%s: an app rule needs applies_to" % where)
        for a in r["applies_to"]:
            if a not in apps:
                err.append("%s: applies_to names unknown app '%s'" % (where, a))
        for s in r["skills"]:
            if s not in SKILLS and s not in ACTIVITIES and s != "*":
                err.append("%s: unknown skill '%s' (skills: %s; activities: %s; or *)" % (where, s, ", ".join(SKILLS), ", ".join(ACTIVITIES)))
        for x in r["exceptions"]:
            if not isinstance(x, dict) or not x.get("app") or not x.get("note"):
                err.append("%s: every exception needs app and note" % where)
                continue
            if x["app"] not in apps:
                err.append("%s: exception for unknown app '%s'" % (where, x["app"]))
            if r["status"] in ("deprecated", "superseded"):
                warn.append("%s: exception for %s on a %s rule (remove it or move it to the successor)" % (where, x["app"], r["status"]))
            if x.get("decision"):
                _check_decision(err, warn, log, where + " exception " + x["app"], x["decision"], r["status"])
        if r["decision"] == UNCONFIRMED and r["status"] != "proposed":
            err.append("%s: decision Unconfirmed is allowed only while proposed" % where)
        elif r["decision"] and r["decision"] != UNCONFIRMED:
            _check_decision(err, warn, log, where, r["decision"], r["status"])
        elif log is not None and r["layer"] in ("project", "app") and r["status"] == "active":
            err.append("%s: an active %s rule needs a decision (the project keeps a decision log)" % (where, r["layer"]))
        bad = [x for x in re.findall(r"\{(\w+)\}", r["check"] or "") if x not in PLACEHOLDERS]
        if bad:
            err.append("%s: check uses an unknown placeholder {%s} (known: %s)" % (where, bad[0], ", ".join("{%s}" % x for x in PLACEHOLDERS)))
    for r in rules:
        where = "%s (%s)" % (r["id"], rel(cfg, r["_path"]))
        if r["status"] == "superseded":
            s = by_id.get(r["superseded_by"])
            if not r["superseded_by"]:
                err.append("%s: superseded without superseded_by" % where)
            elif not s:
                err.append("%s: superseded_by points to unknown rule %s" % (where, r["superseded_by"]))
            elif s["status"] in ("deprecated", "superseded") and not s["superseded_by"]:
                err.append("%s: successor %s is %s" % (where, s["id"], s["status"]))
        elif r["superseded_by"]:
            warn.append("%s: superseded_by is set but the status is %s" % (where, r["status"]))
        if r["overrides"]:
            o = by_id.get(r["overrides"])
            if not o:
                err.append("%s: overrides unknown rule %s" % (where, r["overrides"]))
            elif RANK.get(r["layer"], -1) <= RANK.get(o["layer"], 99):
                err.append("%s: overrides %s of layer %s; only a later layer may override (kit < ds < project < app)"
                           % (where, o["id"], o["layer"]))
            elif o["status"] != "active" and r["status"] == "active":
                warn.append("%s: overrides %s, which is %s" % (where, o["id"], o["status"]))
            if not r["reason"]:
                err.append("%s: overrides needs a reason" % where)
    active = [r for r in rules if r["status"] == "active" and r["overrides"]]
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            if a["overrides"] == b["overrides"] and (not a["applies_to"] or not b["applies_to"] or set(a["applies_to"]) & set(b["applies_to"])):
                err.append("%s and %s both override %s for the same apps (%s): keep one" % (
                    a["id"], b["id"], a["overrides"], ", ".join(sorted(set(a["applies_to"]) & set(b["applies_to"]))) or "all"))
    return err, warn


def _check_decision(err, warn, log, where, did, status):
    if log is None:
        warn.append("%s: decision %s, but the project keeps no decision log (context skill)" % (where, did))
        return
    d = log.get(did.upper())
    if not d:
        err.append("%s: decision %s is not in the decision log" % (where, did))
    elif d["status"] == "rejected":
        err.append("%s: decision %s was rejected" % (where, did))
    elif d["status"] in ("observed", "proposed") and status == "active":
        err.append("%s: decision %s is only %s; an active rule needs an approved decision" % (where, did, d["status"]))
    elif d["status"] == "superseded":
        warn.append("%s: decision %s is superseded by %s" % (where, did, d.get("superseded_by") or "?"))


# ---------- writing ----------

def find(rules, rid):
    for r in rules:
        if r["id"].upper() == rid.upper():
            return r
    die("rule %s not found" % rid)


def editable(r):
    if r["_src"] == "kit":
        die("%s is a kit rule: the kit layer is read-only. Override it for some apps instead: rules.py add --layer app "
            "--applies-to <app> --overrides %s --reason \"...\"" % (r["id"], r["id"]))


def save(r):
    r["_path"].write_text(dump_front(r) + "\n" + r["_body"].strip() + "\n", encoding="utf-8")


def next_id(cfg, rules, category, layer):
    prefix = categories(cfg).get(category)
    if not prefix:
        die("unknown category '%s' (recommended: %s; or declare it in kit.config.json > rules.categories)"
            % (category, ", ".join(CATEGORIES)))
    lo, hi = RANGES[layer]
    nums = [int(m.group(2)) for m in (ID_RX.match(r["id"]) for r in rules) if m and m.group(1) == prefix and lo <= int(m.group(2)) <= hi]
    n = max(nums or [lo - 1]) + 1
    if n > hi:
        die("no free id left for %s in the %s range" % (prefix, layer))
    return "%s-%03d" % (prefix, n)


def split_csv(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def parse_exception(s):
    parts = [x.strip() for x in s.split("=", 2)]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        die("--exception takes \"app=note\" or \"app=note=D-004\" (found %r)" % s)
    e = {"app": parts[0], "note": parts[1]}
    if len(parts) == 3 and parts[2]:
        e["decision"] = parts[2]
    return e


def add_rule(cfg, title, category, severity, layer="project", applies_to=(), skills=(), decision="", status="",
             check="", overrides="", reason="", exceptions=(), body="", since="", app=None):
    if layer not in ("project", "app", "ds"):
        die("--layer must be project, app or ds (the kit layer ships with the kit)")
    if severity not in SEVERITIES:
        die("--severity must be one of " + ", ".join(SEVERITIES))
    rules, _ = load_rules(cfg)
    log = decision_log(cfg)
    if decision and decision != UNCONFIRMED:
        if log is None or decision.upper() not in log:
            die("decision %s is not in the decision log (record it first: decisions.py add)" % decision)
        dstat = log[decision.upper()]["status"]
        status = status or ("active" if dstat in ("approved", "implemented", "verified") else "proposed")
        if status == "active" and dstat not in ("approved", "implemented", "verified"):
            die("decision %s is %s: the rule can only be proposed until a named person approves it" % (decision, dstat))
    status = status or ("proposed" if log is not None and layer in ("project", "app") else "active")
    if status not in ("proposed", "active"):
        die("--status of a new rule is proposed or active")
    if layer == "ds":
        c = kitconf.for_app(cfg, app) if app else cfg
        if not c.get("_ds_dir"):
            die("no DS profile to write a ds rule into")
        folder = Path(c["_ds_dir"]) / "rules"
    else:
        folder = rules_dir(cfg)
    rid = next_id(cfg, rules, category, layer)
    rec = norm({"id": rid, "title": title.strip(), "category": category, "layer": layer, "applies_to": list(applies_to),
                "skills": list(skills), "severity": severity, "status": status, "since": since or today(),
                "decision": decision.upper() if decision and decision != UNCONFIRMED else decision, "check": check,
                "overrides": overrides.upper(), "reason": reason, "exceptions": list(exceptions),
                "history": ["%s · %s%s" % (today(), status, " · " + decision.upper() if decision else "")]})
    rec.update(_path=folder / category / ("%s-%s.md" % (rid, slugify(title))), _body=body.strip() or "<!-- fill: the rule in one paragraph, then why -->",
               _src="project" if layer in ("project", "app") else "ds", _profile=None, _profile_apps=None)
    if layer == "ds":
        prof = kitconf.app_ds(cfg, app) if app else cfg.get("ds")
        rec["_profile"], rec["_profile_apps"] = prof, kitconf.profiles(cfg).get(prof, [])
    err, _ = validate(cfg, rules + [rec])
    mine = [e for e in err if e.startswith(rid + " ") or (" " + rid + " ") in e]
    if mine:
        for e in mine:
            print("ERROR: " + e)
        die("rule not written")
    rec["_path"].parent.mkdir(parents=True, exist_ok=True)
    save(rec)
    return rec


def add_history(r, line):
    r["history"] = list(r["history"]) + ["%s · %s" % (today(), line)]


# ---------- checks ----------

def needs_server(cmd):
    """(host, port) of the first http(s) URL in a check command, or None: such a check needs a running server."""
    m = URL_RX.search(cmd or "")
    if not m:
        return None
    return m.group(1).strip("[]"), int(m.group(2) or (443 if cmd[m.start():m.start() + 5] == "https" else 80))


def reachable(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def skip_words(cfg):
    """Words that open a "skipped" line: SKIP, SKIPPED, plus the project language (locale rules.check.skipWords)."""
    words = ["SKIPPED", "SKIP"]
    w = t((cfg or {}).get("language") or "en", "rules.check.skipWords")
    if w != "rules.check.skipWords":
        words += [x.strip() for x in w.split(",") if x.strip()]
    return list(dict.fromkeys(words))


def skip_line(lines, words=("SKIPPED", "SKIP")):
    """The reason of a check that says it does not apply or scanned nothing ("SKIP: reason", "SKIPPED ..."), or None."""
    rx = re.compile(r"^\s*(?:%s)(?![\w])[:\s-]*(.*)$" % "|".join(re.escape(w) for w in words), re.I)
    for x in (lines[:1] + lines[-1:]) if lines else []:   # the first or the last line says so, not a word in the middle
        m = rx.match(x)
        if m:
            return m.group(1).strip() or "the check reported %s" % x.strip()
    return None


APP_URL = re.compile(r"(https?://[^/\s'\"]+)/[^\s'\"]*\{app\}[^\s'\"]*")


def page_app_runs(cfg, app_id, cmd, url=None):
    """A check whose URL names the app id, for a page app (no folder of the site): [(command, page)] with that URL
    replaced by url (validation.py run --url) or by the same server and the path of each host page (kitconf.app_pages)."""
    m = APP_URL.search(cmd)
    if not m:
        return [(cmd, None)]
    if url:
        return [(cmd[:m.start()] + shlex.quote(url) + cmd[m.end():], url)]
    pages = kitconf.app_pages(cfg, app_id) if kitconf.page_hosts(cfg, app_id) else []   # no host page: nothing to open
    return [(cmd[:m.start()] + m.group(1) + "/" + pg + cmd[m.end():], pg) for pg in pages]


def run_checks(cfg, app=None, skill=None, category=None, rid=None, timeout=900, url=None):
    """Run the check commands of the active rules in scope. One result per rule and app:
    {id, title, severity, category, app, command, exit, status, ok, reason, summary}.
    status: pass (exit 0), fail, or skipped: the command needs a server or URL that is not reachable, the app folder
    ({path}) does not exist, or the command exited 77 / printed "SKIP: <reason>" (not applicable, scanned nothing).
    ok is True unless the status is fail. url: for a page app, the page a check URL naming the app opens (else its host pages)."""
    rules, _ = load_rules(cfg)
    apps = {a.get("id"): a for a in cfg.get("apps") or []}
    out, probed, words = [], {}, skip_words(cfg)
    for r in rules:
        if r["status"] != "active" or not r["check"] or (rid and r["id"] != rid.upper()):
            continue
        if category and r["category"] != category or not skill_match(r, skill):
            continue
        per_app = any("{%s}" % k in r["check"] for k in ("app", "path", "platform", "stack", "page"))
        if per_app:
            targets = [a for a in ([app] if app else list(apps)) if a in apps and in_scope(r, a) and not exception_for(r, a)
                       and not overriders(rules, r, a)]
        else:
            targets = [app] if (not app or (in_scope(r, app) and not exception_for(r, app) and not overriders(rules, r, app))) else []
        # {page}: one run per page to open (a page app: each host page, kitconf.app_pages); a page app whose check URL
        # names the app: that URL becomes url, else each host page on the same server
        runs = []
        for a in targets:
            if a and "{page}" in r["check"]:
                runs += [(a, r["check"], pg) for pg in kitconf.app_pages(cfg, a) or [""]]
            elif (apps.get(a) or {}).get("type") == "page" and kitconf.url_names_app(r["check"]):
                runs += [(a, c, pg) for c, pg in page_app_runs(cfg, a, r["check"], url)] or [(a, r["check"], None)]
            else:
                runs.append((a, r["check"], None))
        for a, cmd, pg in runs:
            ap = apps.get(a) or {}
            vals = {"app": a or "", "path": ap.get("path", ""), "root": cfg["_root"], "platform": ap.get("platform") or "",
                    "stack": (ap.get("stack") or cfg.get("stack") or "") if a else "", "page": pg or ""}
            line = re.sub(r"\{(%s)\}" % "|".join(PLACEHOLDERS), lambda m: shlex.quote(vals[m.group(1)]) if vals[m.group(1)] else "", cmd)
            res = {"id": r["id"], "title": r["title"], "severity": r["severity"], "category": r["category"],
                   "app": a if per_app else app, "perApp": per_app, "command": line, "exit": None, "status": "skipped", "ok": True,
                   "reason": "", "summary": []}
            if pg is not None:
                res["page"] = pg
            srv = needs_server(line)
            if srv and srv not in probed:
                probed[srv] = reachable(*srv)
            if ap.get("type") == "page" and kitconf.url_names_app(cmd):
                res["reason"] = ("page app: the check URL names the app id, which is no page of the site, and the app has no host page "
                                 "(usedBy) to open instead: pass --url, list usedBy, or use {page} in the check")
            elif srv and not probed[srv]:
                res["reason"] = "needs a server at %s:%d, not reachable (start it, then run again)" % srv
            elif "{path}" in r["check"] and a and not (Path(cfg["_root"]) / ap.get("path", "")).exists():
                res["reason"] = "app folder %s not found: nothing to scan" % ap.get("path", "")
            else:
                try:
                    p = subprocess.run(line, shell=True, cwd=cfg["_root"], capture_output=True, text=True, timeout=timeout)
                    code, lines = p.returncode, [x.rstrip() for x in (p.stdout + "\n" + p.stderr).splitlines() if x.strip()]
                except subprocess.TimeoutExpired:
                    code, lines = 124, ["timed out"]
                why = skip_line(lines, words) if code in (0, SKIP_EXIT) else None
                res.update(exit=code, summary=lines[-3:])
                if code == SKIP_EXIT or why:
                    res["reason"] = why or "the check exited %d (does not apply)" % SKIP_EXIT
                else:
                    res.update(status="pass" if code == 0 else "fail", ok=code == 0)
            out.append(res)
    return out


# ---------- text output ----------

def T(cfg, key, **kw):
    return t(cfg, "rules." + key, **kw)


def where_text(cfg, r):
    if r["_src"] == "ds" and not r["applies_to"]:
        return T(cfg, "appsOfProfile", profile=r["_profile"] or "", apps=", ".join(r["_profile_apps"] or []) or "—")
    return ", ".join(r["applies_to"]) if r["applies_to"] else T(cfg, "allApps")


def explain(cfg, rules, r, app=None):
    log = decision_log(cfg) or {}
    L = ["# %s · %s" % (r["id"], r["title"]), "",
         "- %s: %s" % (T(cfg, "f.severity"), T(cfg, "sev." + r["severity"])),
         "- %s: %s" % (T(cfg, "f.category"), T(cfg, "cat." + r["category"]) if t(cfg, "rules.cat." + r["category"]) != "rules.cat." + r["category"] else r["category"]),
         "- %s: %s" % (T(cfg, "f.layer"), T(cfg, "layer." + r["layer"])),
         "- %s: %s" % (T(cfg, "f.status"), T(cfg, "status." + r["status"]) + (" · " + T(cfg, "since", date=r["since"]) if r["since"] else "")),
         "- %s: %s" % (T(cfg, "f.appliesTo"), where_text(cfg, r)),
         "- %s: %s" % (T(cfg, "f.skills"), ", ".join(r["skills"]) or T(cfg, "allSkills"))]
    if app:
        e, o = exception_for(r, app), overriders(rules, r, app)
        state = (T(cfg, "forApp.exception", note=e["note"]) if e else T(cfg, "forApp.overridden", ids=", ".join(x["id"] for x in o)) if o
                 else T(cfg, "forApp.applies") if in_scope(r, app) else T(cfg, "forApp.notInScope"))
        L.append("- %s: %s" % (T(cfg, "f.forApp", app=app), state))
    d = log.get((r["decision"] or "").upper())
    if r["decision"]:
        L.append("- %s: %s" % (T(cfg, "f.decision"), ("%s · %s · %s%s" % (d["id"], d["title"], t(cfg, "context.status." + d["status"]),
                                                                          (" · " + d["by"]) if d.get("by") else "")) if d else r["decision"]))
    if r["overrides"]:
        L.append("- %s: %s (%s)" % (T(cfg, "f.overrides"), r["overrides"], r["reason"] or "—"))
    by = [x["id"] for x in rules if x["overrides"] == r["id"] and x["status"] == "active"]
    if by:
        L.append("- %s: %s" % (T(cfg, "f.overriddenBy"), ", ".join(by)))
    if r["superseded_by"]:
        L.append("- %s: %s" % (T(cfg, "f.supersededBy"), r["superseded_by"]))
    if r["supersedes"]:
        L.append("- %s: %s" % (T(cfg, "f.supersedes"), r["supersedes"]))
    L.append("- %s: %s" % (T(cfg, "f.check"), ("`%s`" % r["check"]) if r["check"] else T(cfg, "noCheck")))
    L += ["", "## " + T(cfg, "h.text"), "", r["_body"].strip() or "—", ""]
    if r["exceptions"]:
        L += ["## " + T(cfg, "h.exceptions"), ""]
        L += ["- %s: %s%s" % (e.get("app"), e.get("note"), (" (%s)" % e["decision"]) if e.get("decision") else "") for e in r["exceptions"] if isinstance(e, dict)]
        L.append("")
    if r["history"]:
        L += ["## " + T(cfg, "h.history"), ""] + ["- " + h for h in r["history"]] + [""]
    L.append(T(cfg, "source", file=rel(cfg, r["_path"])))
    return "\n".join(L)


def export_md(cfg, rules, app=None):
    keep, excepted, overridden = resolve(cfg, rules, app=app)
    cats = categories(cfg)
    L = ["# " + (T(cfg, "export.titleApp", app=app) if app else T(cfg, "export.title")), "", T(cfg, "export.intro"), "",
         T(cfg, "export.count", n=len(keep), must=sum(r["severity"] == "must" for r in keep),
           should=sum(r["severity"] == "should" for r in keep)), ""]
    for c in [c for c in cats if any(r["category"] == c for r in keep)] + sorted({r["category"] for r in keep} - set(cats)):
        L += ["## " + (T(cfg, "cat." + c) if t(cfg, "rules.cat." + c) != "rules.cat." + c else c), ""]
        for r in [r for r in keep if r["category"] == c]:
            L += ["### %s · %s" % (r["id"], r["title"]), "",
                  "*%s · %s · %s: %s%s*" % (T(cfg, "sev." + r["severity"]), T(cfg, "layer." + r["layer"]), T(cfg, "f.appliesTo"),
                                           where_text(cfg, r), (" · " + T(cfg, "f.decision") + " " + r["decision"]) if r["decision"] else ""), "",
                  r["_body"].strip() or "—", ""]
            ex = [e for e in r["exceptions"] if isinstance(e, dict)]
            if ex:
                L += ["%s: %s" % (T(cfg, "h.exceptions"), "; ".join("%s (%s)" % (e["app"], e["note"]) for e in ex)), ""]
    if excepted or overridden:
        L += ["## " + T(cfg, "h.notForApp", app=app), ""]
        L += ["- %s · %s: %s" % (r["id"], r["title"], e["note"]) for r, e in excepted]
        L += ["- %s · %s: %s" % (r["id"], r["title"], T(cfg, "forApp.overridden", ids=", ".join(x["id"] for x in o))) for r, o in overridden]
        L.append("")
    return "\n".join(L)


def export_claude(cfg, rules):
    keep, _, _ = resolve(cfg, rules)
    L = [BLOCK[0], "## " + T(cfg, "claude.title"), "", T(cfg, "claude.intro"), ""]
    for r in keep:
        if r["severity"] == "note":
            continue
        L.append("- **%s** (%s): %s%s" % (r["id"], r["severity"], r["title"],
                                         (" [%s]" % ", ".join(r["applies_to"])) if r["applies_to"] else ""))
    L += ["", BLOCK[1]]
    return "\n".join(L)


def export_html(cfg, md):
    sys.path.insert(0, str(KIT / "skills" / "annotate" / "scripts"))
    from spec_md import md_to_html  # noqa: E402
    title = md.split("\n", 1)[0].lstrip("# ").strip()
    css = (":root{--kit-bg:#fff;--kit-fg:#1f2328;--kit-muted:#59636e;--kit-line:#d1d9e0}"
           "@media (prefers-color-scheme:dark){:root{--kit-bg:#0d1117;--kit-fg:#e6edf3;--kit-muted:#9198a1;--kit-line:#3d444d}}"
           "body{margin:0;background:var(--kit-bg);color:var(--kit-fg);font:15px/1.6 system-ui,sans-serif}"
           "main{max-width:860px;margin:0 auto;padding:24px 16px}h2{border-bottom:1px solid var(--kit-line);padding-bottom:4px}"
           "em{color:var(--kit-muted)}code{font-size:13px}")
    return ('<!doctype html><html lang="%s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title><style>%s</style></head><body><main>%s</main></body></html>\n'
            % (cfg.get("language", "en"), title.replace("<", "&lt;"), css, md_to_html(md, ids=False)))


# ---------- import ----------

CODE_SPAN = re.compile(r"`([^`]*)`")


def plain_text(md):
    """Markdown of one bullet -> plain text: links keep their text, code spans keep their content as written
    (`/* LOCAL`, `FLAG_NAME`), emphasis markers (**x**, *x*, __x__, _x_) are dropped only around words."""
    keep = []
    s = CODE_SPAN.sub(lambda m: keep.append(m.group(1)) or "\x00%d\x00" % (len(keep) - 1), md)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"\2", s)
    s = re.sub(r"(?<![\w*])\*(?=[^\s*])([^*\n]+?)(?<=\S)\*(?![\w*])", r"\1", s)
    s = re.sub(r"(?<![\w])_(?=[^\s_])([^_\n]+?)(?<=\S)_(?![\w])", r"\1", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], s)


def must_words(cfg):
    """Words that make an imported bullet a must rule: English always, plus the project language (locale
    rules.import.mustWords, comma separated). A language without the list keeps every draft at should."""
    words = []
    for lang in dict.fromkeys(["en", (cfg or {}).get("language") or "en"]):
        w = t(lang, "rules.import.mustWords")
        if w != "rules.import.mustWords":
            words += [x.strip().lower() for x in w.split(",") if x.strip()]
    return words


def infer_severity(text, words):
    low = " " + re.sub(r"\s+", " ", text.lower()) + " "
    return "must" if any(re.search(r"(?<![\w])%s(?![\w])" % re.escape(w), low) for w in words) else "should"


def import_md(cfg, src, layer="project", category="process", maps=(), dry=False, app=None):
    p = Path(src)
    if layer == "ds":
        c = kitconf.for_app(cfg, app) if app else cfg
        if not c.get("_ds_dir"):
            die("no DS profile to import ds rules into (kit.config.json > ds, or apps[].ds of --app)")
        dest, prof = Path(c["_ds_dir"]) / "rules", c.get("ds")
    else:
        dest, prof = rules_dir(cfg), None
    if not p.is_file():
        die("file not found: %s" % src)
    cats = categories(cfg)
    if category not in cats:
        die("unknown --category '%s'" % category)
    mapping = []
    for m in maps:
        if "=" not in m or m.split("=", 1)[1].strip() not in cats:
            die("--map takes \"heading words=category\" with a known category (found %r)" % m)
        w, c = m.split("=", 1)
        mapping.append((w.strip().lower(), c.strip()))
    items, heading, cur, skipped = [], "", None, 0
    lines = p.read_text(encoding="utf-8").splitlines()
    in_code = False
    for ln in lines:
        if ln.startswith("```"):
            in_code = not in_code
            cur = None
            continue
        if in_code:
            continue
        h = re.match(r"^#{1,6}\s+(.*)", ln)
        b = re.match(r"^(?:[-*]|\d+[.)])\s+(.*)", ln)
        if h:
            heading, cur = h.group(1).strip(), None
        elif b:
            cur = {"heading": heading, "lines": [b.group(1).strip()]}
            items.append(cur)
        elif cur and ln.startswith((" ", "\t")) and ln.strip():
            cur["lines"].append(ln.strip())
        else:
            if ln.strip() and not ln.lstrip().startswith("|"):
                skipped += 1
            cur = None
    rules, _ = load_rules(cfg)
    made, review = [], []
    words = must_words(cfg)
    for it in items:
        text = " ".join(it["lines"]).strip()
        hl = it["heading"].lower()
        cat = next((c for w, c in mapping if w in hl), None) or next((c for c in cats if re.search(r"\b%s\b" % re.escape(c), hl)), None)
        confirmed_cat = bool(cat)
        cat = cat or category
        plain = plain_text(text)
        title = re.split(r"(?<=[.!?])\s", plain, maxsplit=1)[0].rstrip(".:; ")
        title = title if len(title) <= 90 else title[:87].rsplit(" ", 1)[0] + "…"
        sev = infer_severity(plain, words)
        rid = next_id(cfg, rules + made, cat, layer)
        body = "%s\n\n%s" % (text, T(cfg, "import.source", file=p.name, section=it["heading"] or "—", date=today()))
        rec = norm({"id": rid, "title": title, "category": cat, "layer": layer, "severity": sev, "status": "proposed",
                    "since": UNCONFIRMED, "decision": UNCONFIRMED if layer in ("project", "app") else "",
                    "history": ["%s · proposed · %s" % (today(), T(cfg, "import.historyNote", file=p.name))]})
        rec.update(_path=dest / cat / ("%s-%s.md" % (rid, slugify(title))), _body=body,
                   _src="ds" if layer == "ds" else "project", _profile=prof,
                   _profile_apps=kitconf.profiles(cfg).get(prof, []) if prof else None)
        made.append(rec)
        todo = ["severity", "since"] + (["decision"] if layer in ("project", "app") else []) + ([] if confirmed_cat else ["category"])
        if layer == "app":
            todo.append("applies_to")
        review.append((rec, it["heading"], todo))
    if not dry:
        for r in made:
            r["_path"].parent.mkdir(parents=True, exist_ok=True)
            save(r)
        L = ["# " + T(cfg, "import.reviewTitle", file=p.name), "", T(cfg, "import.reviewIntro"), "",
             "| ID | %s | %s | %s |" % (T(cfg, "import.colSection"), T(cfg, "import.colTitle"), T(cfg, "import.colConfirm")), "|---|---|---|---|"]
        L += ["| [%s](%s) | %s | %s | %s |" % (r["id"], r["_path"].relative_to(dest).as_posix(), (h or "—").replace("|", "/"),
                                              r["title"].replace("|", "/"), UNCONFIRMED + ": " + ", ".join(todo)) for r, h, todo in review]
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "_import-review.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return made, review, skipped


# ---------- commands ----------

def cmd_list(cfg, a):
    rules, perr = load_rules(cfg)
    for e in perr:
        print("ERROR: " + e)
    c = kitconf.for_app(cfg, a.app) if a.app else cfg
    if a.app and a.app not in app_ids(cfg):
        die("app '%s' is not declared in kit.config.json > apps" % a.app)
    keep, excepted, overridden = resolve(c, rules, a.app, a.skill, a.category, a.severity, a.status, a.layer)
    if a.json:
        js = {"app": a.app, "skill": a.skill, "rules": [{k: r[k] for k in FIELDS} | {"text": statement(r), "file": rel(cfg, r["_path"])} for r in keep],
              "exceptions": [{"id": r["id"], "title": r["title"], "note": e["note"], "decision": e.get("decision", "")} for r, e in excepted],
              "overridden": [{"id": r["id"], "by": [x["id"] for x in o]} for r, o in overridden]}
        print(json.dumps(js, ensure_ascii=False, indent=1))
        return 0
    head = "Rules in force" + (" for app %s" % a.app if a.app else "") + (", skill %s" % a.skill if a.skill else "")
    print("%s: %d (must %d, should %d, note %d)" % (head, len(keep), *(sum(r["severity"] == s for r in keep) for s in SEVERITIES)))
    for r in keep:
        print("%-9s %-6s %-9s %-7s %s" % (r["id"], r["severity"], r["category"][:9], r["layer"], r["title"]))
        if a.full:
            print("\n".join("          " + x for x in r["_body"].splitlines()))
        elif not a.brief and statement(r):
            print("          " + statement(r).replace("\n", " ")[:400])
    for r, e in excepted:
        print("EXCEPTION %s (%s) for %s: %s%s" % (r["id"], r["title"], a.app, e["note"], (" [%s]" % e["decision"]) if e.get("decision") else ""))
    for r, o in overridden:
        print("OVERRIDDEN %s by %s" % (r["id"], ", ".join("%s (%s)" % (x["id"], x["reason"]) for x in o)))
    if not (KIT / "rules").is_dir() and not keep:
        print("No rules found.")
    ds = c.get("_ds") or {}
    doc, frm = kitconf.ds_rules(ds)
    if ds and c.get("_ds_dir") and not frm and not (Path(c["_ds_dir"]) / "rules").is_dir() and (Path(c["_ds_dir"]) / doc).is_file():
        print("NOTE the DS profile keeps its rules in %s, not as rule files: read it too, or split it with import-md --layer ds." % doc)
    return 1 if perr else 0


def cmd_show(cfg, a):
    rules, _ = load_rules(cfg)
    print(explain(kitconf.for_app(cfg, a.app) if a.app else cfg, rules, find(rules, a.id), a.app))
    return 0


def cmd_add(cfg, a):
    body = Path(a.body_file).read_text(encoding="utf-8") if a.body_file else (a.body or "")
    if a.overrides and not a.reason:
        die("--overrides needs --reason")
    rec = add_rule(cfg, a.title, a.category, a.severity, a.layer, split_csv(a.applies_to), split_csv(a.skills), a.decision,
                   a.status, a.check, a.overrides, a.reason, [parse_exception(x) for x in a.exception], body, a.since, a.app)
    print("Recorded %s (%s, %s): %s" % (rec["id"], rec["status"], rec["layer"], rel(cfg, rec["_path"])))
    if not body:
        print("NEXT write the rule text in the file (first paragraph = the rule, then why), in the project language.")
    return 0


def cmd_except(cfg, a):
    rules, _ = load_rules(cfg)
    r = find(rules, a.id)
    editable(r)
    if a.app not in app_ids(cfg):
        die("app '%s' is not declared in kit.config.json > apps" % a.app)
    if exception_for(r, a.app):
        die("%s already has an exception for %s" % (r["id"], a.app))
    if a.decision:
        log = decision_log(cfg)
        if log is None or a.decision.upper() not in log:
            die("decision %s is not in the decision log" % a.decision)
    e = {"app": a.app, "note": a.note}
    if a.decision:
        e["decision"] = a.decision.upper()
    r["exceptions"] = list(r["exceptions"]) + [e]
    add_history(r, "exception %s%s" % (a.app, " · " + a.decision.upper() if a.decision else ""))
    save(r)
    print("%s: exception for %s recorded" % (r["id"], a.app))
    return 0


def cmd_deprecate(cfg, a):
    rules, _ = load_rules(cfg)
    r = find(rules, a.id)
    editable(r)
    if r["status"] in ("deprecated", "superseded"):
        die("%s is already %s" % (r["id"], r["status"]))
    r["status"] = "deprecated"
    add_history(r, "deprecated · %s%s" % (a.reason, " · " + a.decision.upper() if a.decision else ""))
    save(r)
    print("%s is now deprecated" % r["id"])
    return 0


def cmd_supersede(cfg, a):
    rules, _ = load_rules(cfg)
    old, new = find(rules, a.old), find(rules, a.by)
    editable(old)
    if old is new:
        die("a rule cannot supersede itself")
    if old["status"] in ("deprecated", "superseded"):
        die("%s is already %s" % (old["id"], old["status"]))
    if new["status"] not in ("active", "proposed"):
        die("the successor %s is %s; it must be active or proposed" % (new["id"], new["status"]))
    if a.decision:
        log = decision_log(cfg)
        if log is None or a.decision.upper() not in log:
            die("decision %s is not in the decision log" % a.decision)
    old.update(status="superseded", superseded_by=new["id"])
    add_history(old, "superseded by %s%s" % (new["id"], " · " + a.decision.upper() if a.decision else ""))
    save(old)
    if new["_src"] != "kit":
        new["supersedes"] = old["id"]
        add_history(new, "supersedes %s" % old["id"])
        save(new)
    print("%s is superseded by %s" % (old["id"], new["id"]))
    if old["exceptions"]:
        print("NOTE %s had %d exception(s): add them to %s if they still hold (rules.py except)." % (old["id"], len(old["exceptions"]), new["id"]))
    return 0


def cmd_check(cfg, a):
    res = run_checks(cfg, a.app, a.skill, a.category, a.id, url=a.url)
    if a.json:
        txt = json.dumps(res, ensure_ascii=False, indent=1)
        if a.json == "-":
            print(txt)
        else:
            Path(a.json).write_text(txt, encoding="utf-8")
    if a.json != "-":
        for x in res:
            tag = {"pass": "ok", "fail": "FAIL", "skipped": "skip"}[x["status"]]
            code = "" if x["exit"] is None else " · exit %d" % x["exit"]
            print("%-4s %-9s %-6s %s%s%s%s" % (tag, x["id"], x["severity"], x["title"], (" · " + x["app"]) if x["app"] else "", code,
                                             (" · " + x["reason"]) if x["status"] == "skipped" else
                                             ("\n     " + "\n     ".join(x["summary"])) if x["status"] == "fail" and x["summary"] else ""))
        must = [x for x in res if x["status"] == "fail" and x["severity"] == "must"]
        print("Rule checks: %d run, %d failed (%d must), %d skipped" % (
            sum(x["status"] != "skipped" for x in res), sum(x["status"] == "fail" for x in res), len(must),
            sum(x["status"] == "skipped" for x in res)))
    return 1 if any(x["status"] == "fail" and x["severity"] == "must" for x in res) else 0


def coverage(cfg, rules):
    """Per category and app: {"must": [with check, without], "should": [...], "server": n checks that need a server}."""
    active = [r for r in rules if r["status"] == "active" and r["severity"] in ("must", "should")]
    by_cat, by_app = {}, {}
    for r in active:
        c = by_cat.setdefault(r["category"], {"must": [0, 0], "should": [0, 0], "server": 0})
        c[r["severity"]][0 if r["check"] else 1] += 1
        c["server"] += bool(needs_server(r["check"]))
    for a in app_ids(cfg):
        keep, _, _ = resolve(kitconf.for_app(cfg, a), rules, app=a)
        c = by_app.setdefault(a, {"must": [0, 0], "should": [0, 0], "server": 0})
        for r in keep:
            if r["severity"] in ("must", "should"):
                c[r["severity"]][0 if r["check"] else 1] += 1
                c["server"] += bool(needs_server(r["check"]))
    return {"categories": by_cat, "apps": by_app}


def cmd_coverage(cfg, a):
    rules, _ = load_rules(cfg)
    cov = coverage(cfg, rules)
    if a.json:
        print(json.dumps(cov, ensure_ascii=False, indent=1))
        return 0
    for title, rows in (("Category", cov["categories"]), ("App", cov["apps"])):
        print("| %s | must with check | must without | should with check | should without | checks that need a server |" % title)
        print("|---|---|---|---|---|---|")
        for k, v in rows.items():
            print("| %s | %d | %d | %d | %d | %d |" % (k, v["must"][0], v["must"][1], v["should"][0], v["should"][1], v["server"]))
        print()
    tot = [sum(v[s][i] for v in cov["categories"].values()) for s in ("must", "should") for i in (0, 1)]
    srv = sum(v["server"] for v in cov["categories"].values())
    print("Automated: %d of %d must rules, %d of %d should rules (%d check(s) need a running server: skipped when it is down)"
          % (tot[0], tot[0] + tot[1], tot[2], tot[2] + tot[3], srv))
    return 0


def cmd_conflicts(cfg, a):
    rules, perr = load_rules(cfg)
    err, warn = validate(cfg, rules, perr)
    for w in warn:
        print("WARN:  " + w)
    for e in err:
        print("ERROR: " + e)
    print("Rules OK (%d rules, %d warning(s))" % (len(rules), len(warn)) if not err else "%d error(s)" % len(err))
    return 1 if err else 0


def cmd_export(cfg, a):
    rules, _ = load_rules(cfg)
    c = kitconf.for_app(cfg, a.app) if a.app else cfg
    if a.format == "claude":
        txt = export_claude(c, rules)
        if a.into:
            p = Path(a.into)
            old = p.read_text(encoding="utf-8") if p.is_file() else ""
            if BLOCK[0] in old and BLOCK[1] in old:
                new = old[:old.index(BLOCK[0])] + txt + old[old.index(BLOCK[1]) + len(BLOCK[1]):]
            else:
                new = old.rstrip("\n") + ("\n\n" if old else "") + txt + "\n"
            p.write_text(new, encoding="utf-8")
            print("Wrote the rules block into %s" % a.into)
            return 0
    else:
        txt = export_md(c, rules, a.app)
        if a.format == "html":
            txt = export_html(c, txt)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(txt, encoding="utf-8")
        print("Wrote %s" % a.out)
    else:
        print(txt)
    return 0


def cmd_import(cfg, a):
    made, review, skipped = import_md(cfg, a.file, a.layer, a.category, a.map, a.dry_run, a.app)
    for r, h, todo in review:
        print("%s %-9s %s  [%s] (%s: %s)" % ("would write" if a.dry_run else "draft", r["id"], r["title"][:70], h[:30] or "-",
                                            UNCONFIRMED, ", ".join(todo)))
    print("%d draft rule(s)%s; %d line(s) outside bullets not imported" % (
        len(made), "" if a.dry_run else ", review list %s" % rel(cfg, (made[0]["_path"].parents[1] if made else rules_dir(cfg)) / "_import-review.md"), skipped))
    if not a.dry_run and made:
        print("NEXT confirm each draft with the user (severity, category, since, decision), then set status: active.")
    return 0


# ---------- selftest ----------

def selftest():
    import shutil
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="rules-selftest-"))
    try:
        fm, body = parse_front("---\nid: STY-001\ntitle: \"A: b\"\nskills: [prototype, review]\nexceptions:\n  - app: a1\n    note: n\n"
                               "    decision: D-001\nhistory:\n  - 2026-01-01 · active\n# comment\n---\nText.\n\nWhy.\n")
        assert fm["title"] == "A: b" and fm["skills"] == ["prototype", "review"] and fm["exceptions"] == [{"app": "a1", "note": "n", "decision": "D-001"}]
        assert fm["history"] == ["2026-01-01 · active"] and body.startswith("Text."), (fm, body)
        r = norm(dict(fm))
        assert parse_front(dump_front(r) + "x")[0]["exceptions"] == fm["exceptions"], "dump/parse round trip"
        for bad in ("no front\n", "---\n  - x\n---\n", "---\nkey\n---\n"):
            try:
                parse_front(bad)
                raise AssertionError("accepted: %r" % bad)
            except ValueError:
                pass
        (d / "ds" / "acme" / "rules" / "styling").mkdir(parents=True)
        (d / "ds" / "acme" / "ds.json").write_text(json.dumps({"name": "acme", "version": "1.0.0"}))
        (d / "ds" / "mob").mkdir(parents=True)
        (d / "ds" / "mob" / "ds.json").write_text(json.dumps({"name": "mob", "version": "2.0.0"}))
        (d / "kit.config.json").write_text(json.dumps({"ds": "ds/acme", "language": "vi", "apps": [
            {"id": "web", "path": "apps/web"}, {"id": "old", "path": "apps/old"}, {"id": "phone", "path": "apps/phone", "ds": "ds/mob"}]}))
        (d / "ds" / "acme" / "rules" / "styling" / "STY-501-ds-radius.md").write_text(
            "---\nid: STY-501\ntitle: Radius tokens\ncategory: styling\nlayer: ds\nseverity: should\nstatus: active\nsince: 2026-01-01\n---\nUse radius tokens.\n")
        cfg = load(d)
        r1 = add_rule(cfg, "No raw colours", "styling", "must", skills=["prototype", "review"], check="test {app} != old",
                      exceptions=[{"app": "old", "note": "legacy until rebuild"}], body="Only tokens.\n\nReason.")
        assert r1["id"] == "STY-001" and r1["status"] == "active", r1["id"]
        r2 = add_rule(cfg, "Old app may keep its density", "density", "should", layer="app", applies_to=["old"],
                      overrides="DEN-901", reason="rebuild planned", body="x")
        rules, perr = load_rules(cfg)
        err, warn = validate(cfg, rules, perr)
        assert not err, err
        keep, exc, ovr = resolve(cfg, rules, app="old", skill="review")
        ids = {r["id"] for r in keep}
        assert "STY-001" not in ids and exc[0][0]["id"] == "STY-001" and "DEN-901" in {r["id"] for r, _ in ovr}, (ids, exc, ovr)
        assert "STY-501" in ids, "ds rule applies to apps of its profile"
        keep_p, _, _ = resolve(kitconf.for_app(cfg, "phone"), rules, app="phone")
        assert "STY-501" not in {r["id"] for r in keep_p} and "STY-001" in {r["id"] for r in keep_p}, "other profile"
        assert all(r["severity"] == "must" for r in keep[:1])
        res = run_checks(cfg, skill="review")
        assert {(x["app"], x["ok"]) for x in res if x["id"] == "STY-001"} == {("web", True), ("phone", True)}, res
        (d / "product-context" / "decisions").mkdir(parents=True)
        import decisions as D
        did, _ = D.add_decision(cfg, "Pill buttons", status="approved", by="Lan")
        pdid, _ = D.add_decision(cfg, "Maybe", status="proposed")
        r3 = add_rule(cfg, "Pill buttons", "styling", "must", decision=did, body="Buttons are pills.")
        assert r3["status"] == "active" and r3["decision"] == did
        r4 = add_rule(cfg, "Maybe rule", "content", "note", decision=pdid, body="x")
        assert r4["status"] == "proposed"
        rules, _ = load_rules(cfg)
        err, _ = validate(cfg, rules)
        assert any("STY-001" in e and "needs a decision" in e for e in err), err   # log exists now: active project rules need one
        r = find(rules, "STY-001")
        r["decision"] = did
        save(r)
        new = find(load_rules(cfg)[0], r3["id"])
        cmd_supersede(cfg, argparse.Namespace(old="STY-001", by=new["id"], decision=did))
        rules, _ = load_rules(cfg)
        assert find(rules, "STY-001")["status"] == "superseded" and find(rules, new["id"])["supersedes"] == "STY-001"
        err, warn = validate(cfg, rules)
        assert not [e for e in err if "STY-001" in e] and any("exception for old" in w for w in warn), (err, warn)
        # conflicts: two overrides of one rule for the same app, unknown app, bad prefix
        bad = dict(find(rules, r2["id"]), id="DEN-002", _path=d / "x.md")
        err, _ = validate(cfg, rules + [bad])
        assert any("both override" in e for e in err), err
        bad = norm({"id": "THM-001", "title": "x", "category": "styling", "layer": "project", "severity": "must", "status": "active",
                    "since": "2026-01-01", "applies_to": ["nope"], "skills": ["nope"], "decision": did})
        bad.update(_path=d / "y.md", _body="", _src="project", _profile=None, _profile_apps=None)
        err, _ = validate(cfg, rules + [bad])
        assert sum(("THM-001" in e) for e in err) == 3, err
        cov = coverage(cfg, rules)
        assert cov["categories"]["styling"]["must"][1] >= 1 and "web" in cov["apps"], cov
        md = export_md(cfg, rules)
        assert "### STY-901 · " in md and t(cfg, "rules.export.title") in md, md[:400]
        assert BLOCK[0] in export_claude(cfg, rules) and "STY-901" in export_claude(cfg, rules)
        assert "<main>" in export_html(cfg, md)
        assert "Lan" in explain(cfg, rules, find(rules, r3["id"]), "web")
        src = d / "old-rules.md"
        src.write_text("# Rules\n\n## Styling\n\n- Use tokens only. No hex.\n  Also no rgb().\n- **Never** override DS CSS.\n\n"
                       "## Pages\n\nIntro paragraph.\n\n1. Ask before a new page.\n```\n- not a rule\n```\n")
        made, review, skipped = import_md(cfg, src, maps=["pages=pages"])
        assert [r["category"] for r in made] == ["styling", "styling", "pages"] and skipped == 1, ([r["category"] for r in made], skipped)
        assert made[0]["_body"].startswith("Use tokens only. No hex. Also no rgb().") and made[0]["since"] == UNCONFIRMED
        rules, perr = load_rules(cfg)
        err, _ = validate(cfg, rules, perr)
        assert not [e for e in err if any(m["id"] in e for m in made)], err
        assert (d / "rules" / "_import-review.md").is_file()
        # 0.10: import keeps code spans and underscores, titles are not cut at ":", must words, readable file names
        assert slugify("Thư viện đầu tiên") == "thu-vien-dau-tien", slugify("Thư viện đầu tiên")
        assert plain_text("Each `/* LOCAL: … */` block and the `FLAG_NAME` flag, **never** _hex_") == "Each /* LOCAL: … */ block and the FLAG_NAME flag, never hex"
        assert infer_severity("Never override DS CSS", must_words(cfg)) == "must"
        assert infer_severity("Cấm dùng mã màu", must_words(cfg)) == "must" and infer_severity("Use tokens", must_words(cfg)) == "should"
        src.write_text("## Pages\n\n- Two groups: STOP and ask first. Then build.\n- Each `/* LOCAL: x */` block has a name.\n")
        made, _, _ = import_md(cfg, src, dry=True)
        assert made[0]["title"] == "Two groups: STOP and ask first" and "/* LOCAL: x */" in made[1]["title"], [m["title"] for m in made]
        made, _, _ = import_md(cfg, src, layer="ds", app="phone")
        assert made[0]["_path"].parent.parent == d / "ds" / "mob" / "rules" and made[0]["id"].endswith("-500"), made[0]["_path"]
        # 0.10: check results pass / fail / skipped
        py = shlex.quote(sys.executable)
        for rid, cmd in (("STY-020", py + " -c \"import sys; sys.exit(77)\" {app}"),
                         ("STY-021", py + " -c \"print('SKIP: vue apps are not scanned')\" {app}"),
                         ("STY-022", "curl -s http://127.0.0.1:9/apps/{app}/"),
                         ("STY-023", "ls {path}")):
            (d / "rules" / "styling" / (rid + ".md")).write_text(
                "---\nid: %s\ntitle: t\ncategory: styling\nlayer: project\nskills: [review]\nseverity: must\nstatus: active\n"
                "since: 2026-01-01\ndecision: %s\ncheck: %s\n---\nx\n" % (rid, did, cmd))
        res = {(x["id"], x["app"]): x for x in run_checks(cfg, skill="review") if x["id"] in ("STY-020", "STY-021", "STY-022", "STY-023")}
        assert {k[0] for k, x in res.items() if x["status"] == "skipped"} == {"STY-020", "STY-021", "STY-022", "STY-023"}, res
        assert "vue apps" in res[("STY-021", "web")]["reason"] and "not reachable" in res[("STY-022", "web")]["reason"]
        assert "not found" in res[("STY-023", "web")]["reason"] and all(x["ok"] for x in res.values())
        cov = coverage(cfg, load_rules(cfg)[0])
        assert cov["categories"]["styling"]["server"] == 1, cov["categories"]["styling"]
        # 0.10: activity groups in skills; "*"
        for rid, sk in (("PRC-020", "[pr]"), ("PRC-021", "[\"*\"]")):
            (d / "rules" / "process").mkdir(exist_ok=True)
            (d / "rules" / "process" / (rid + ".md")).write_text(
                "---\nid: %s\ntitle: t\ncategory: process\nlayer: project\nskills: %s\nseverity: should\nstatus: active\n"
                "since: 2026-01-01\ndecision: %s\n---\nx\n" % (rid, sk, did))
        rules, perr = load_rules(cfg)
        assert not [e for e in validate(cfg, rules, perr)[0] if "PRC-02" in e], validate(cfg, rules, perr)[0]
        ids = lambda sk: {r["id"] for r in resolve(cfg, rules, skill=sk)[0]}
        assert "PRC-020" not in ids("prototype") and "PRC-020" in ids("pr") and "PRC-021" in ids("prototype") and "PRC-021" in ids("pr")
        # 0.10: ds.json > rules.from: the mobile profile inherits the web profile's DS rules, read once
        (d / "ds" / "mob" / "ds.json").write_text(json.dumps({"name": "mob", "version": "2.0.0", "rules": {"from": "../acme"}}))
        shutil.rmtree(d / "ds" / "mob" / "rules")
        rules, perr = load_rules(cfg)
        assert sum(r["id"] == "STY-501" for r in rules) == 1, "inherited rules are read once"
        keep_p, _, _ = resolve(kitconf.for_app(cfg, "phone"), rules, app="phone")
        assert "STY-501" in {r["id"] for r in keep_p}, "inherited through rules.from"
        assert not [e for e in validate(cfg, rules, perr)[0] if "duplicate" in e or "STY-501" in e], validate(cfg, rules, perr)[0]
        # 0.12.2 (K3-6, K1a-3): a page app's check URL that names the app opens --url, else each host page on that server
        (d / "apps" / "web" / "notes").mkdir(parents=True, exist_ok=True)
        (d / "apps" / "web" / "notes" / "index.html").write_text("<main></main>")
        pc = dict(cfg, apps=list(cfg["apps"]) + [{"id": "notes-vue", "type": "page", "path": "vue/notes", "usedBy": ["apps/web/notes/notes.js"]}])
        cmd = "node a11y.js http://localhost:8765/apps/{app}/ --{platform}"
        assert page_app_runs(pc, "notes-vue", cmd) == [("node a11y.js http://localhost:8765/apps/web/notes/ --{platform}", "apps/web/notes/")]
        assert page_app_runs(pc, "notes-vue", cmd, "http://127.0.0.1:9/x/?a=1&b=2")[0][0] == "node a11y.js 'http://127.0.0.1:9/x/?a=1&b=2' --{platform}"
        assert page_app_runs(dict(pc, apps=pc["apps"][:-1] + [dict(pc["apps"][-1], usedBy=[])]), "notes-vue", cmd) == []
        print("rules.py selftest OK")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    if "--selftest" in sys.argv:
        selftest()
        return 0
    ap = argparse.ArgumentParser(description="Rules registry (kit, DS, project and app layers).",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="rules in force for an app and a skill")
    for k in ("app", "skill", "category", "severity", "layer"):
        p.add_argument("--" + k)
    p.add_argument("--status", default="active", help="active (default), proposed, deprecated, superseded or all")
    p.add_argument("--brief", action="store_true"); p.add_argument("--full", action="store_true"); p.add_argument("--json", action="store_true")
    for name in ("show", "explain"):
        p = sub.add_parser(name, help="explain one rule"); p.add_argument("id"); p.add_argument("--app")
    p = sub.add_parser("add", help="record a new rule")
    p.add_argument("--title", required=True); p.add_argument("--category", required=True); p.add_argument("--severity", required=True)
    p.add_argument("--layer", default="project")
    for k in ("applies-to", "skills", "decision", "status", "check", "overrides", "reason", "body", "body-file", "since", "app"):
        p.add_argument("--" + k, default="")
    p.add_argument("--exception", action="append", default=[], help='"app=note" or "app=note=D-004"; repeat for more')
    p = sub.add_parser("except", help="add an app exception to a rule")
    p.add_argument("id"); p.add_argument("--app", required=True); p.add_argument("--note", required=True); p.add_argument("--decision", default="")
    p = sub.add_parser("deprecate", help="retire a rule")
    p.add_argument("id"); p.add_argument("--reason", required=True); p.add_argument("--decision", default="")
    p = sub.add_parser("supersede", help="replace a rule by another")
    p.add_argument("old"); p.add_argument("--by", required=True); p.add_argument("--decision", default="")
    p = sub.add_parser("check", help="run the check commands of the rules in scope")
    for k in ("app", "skill", "category", "id", "json"):
        p.add_argument("--" + k)
    p.add_argument("--url", help="page app: the page a check URL that names the app opens (default: its host pages)")
    p = sub.add_parser("coverage", help="automated checks per category and app"); p.add_argument("--json", action="store_true")
    sub.add_parser("conflicts", help="validate every rule and the relations between them")
    p = sub.add_parser("export", help="Project rules page or the CLAUDE.md block")
    p.add_argument("--format", choices=("md", "html", "claude"), default="md"); p.add_argument("--app")
    p.add_argument("--out"); p.add_argument("--into", help="claude format: replace the block in this file")
    p = sub.add_parser("import-md", help="draft rule files from an existing rules document")
    p.add_argument("file"); p.add_argument("--layer", default="project", choices=("project", "app", "ds"))
    p.add_argument("--app", help="ds layer: the DS profile of this app (apps[].ds); default the top-level ds")
    p.add_argument("--category", default="process"); p.add_argument("--map", action="append", default=[])
    p.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = load()
    return {"list": cmd_list, "show": cmd_show, "explain": cmd_show, "add": cmd_add, "except": cmd_except,
            "deprecate": cmd_deprecate, "supersede": cmd_supersede, "check": cmd_check, "coverage": cmd_coverage,
            "conflicts": cmd_conflicts, "export": cmd_export, "import-md": cmd_import}[a.cmd](cfg, a)


if __name__ == "__main__":
    sys.exit(main())
