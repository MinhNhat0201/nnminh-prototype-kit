#!/usr/bin/env python3
"""Decision log: one Markdown file per design or product decision, with a status lifecycle.

Lifecycle (who moves it):
  observed     seen in the product or an existing app, never decided here        (agent, with a source)
  proposed     suggested, waiting for a human                                     (agent or designer)
  approved     a named person said yes                                            (human, --by required)
  implemented  built in a prototype                                               (agent, after prototype)
  verified     checked in the developer build                                     (agent, after verify)
  rejected     a named person said no                                             (human, --by required)
  superseded   replaced by a newer decision                                       (set through --supersedes)

Allowed moves:
  observed -> proposed, approved, rejected
  proposed -> approved, rejected
  approved -> implemented
  implemented -> verified, approved (rework)
  verified -> implemented (regression)
Any status except rejected -> superseded (only through a newer decision's --supersedes).

Commands:
  decisions.py add --title "..." [--status proposed] [--scope S01,R-03,acme-web] [--source "..."]
                   [--context "..."] [--decision "..."] [--alternatives "..."] [--by "name"] [--supersedes D-002]
  decisions.py set <id> <status> [--by "name"] [--note "..."]
  decisions.py list [--status approved] [--scope S01]
  decisions.py show <id>
  decisions.py index        write decisions/index.md
  decisions.py check        validate every record and the moves in its history; exit 1 on error

Files live in <paths.context>/decisions/D-001-<slug>.md. Never commits, pushes or sends anything.
"""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, t  # noqa: E402

STATUSES = ("observed", "proposed", "approved", "implemented", "verified", "rejected", "superseded")
MOVES = {
    "observed": {"proposed", "approved", "rejected"},
    "proposed": {"approved", "rejected"},
    "approved": {"implemented"},
    "implemented": {"verified", "approved"},
    "verified": {"implemented"},
    "rejected": set(),
    "superseded": set(),
}
HUMAN = {"approved", "rejected"}
FIELDS = ("id", "title", "status", "date", "by", "scope", "source", "supersedes", "superseded_by")
HEAD = re.compile(r"^<!--\s*decision\s*\n(.*?)\n-->\s*\n", re.S)
SECTIONS = ("context", "decision", "alternatives", "consequences", "history")


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def today():
    return dt.date.today().isoformat()


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:48].strip("-") or "decision"


def ddir(cfg):
    return Path(cfg["_root"]) / cfg["paths"]["context"] / "decisions"


# ---------- read / write ----------

def parse(path):
    text = path.read_text(encoding="utf-8")
    m = HEAD.match(text)
    if not m:
        raise ValueError("%s: missing the <!-- decision ... --> header" % path.name)
    rec = {k: "" for k in FIELDS}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            rec[k.strip()] = v.strip()
    body = text[m.end():]
    rec["_path"] = path
    rec["_body"] = body
    last = body.rsplit("\n## ", 1)[-1]  # History is always the last section
    rec["_history"] = [h.strip()[2:] for h in last.split("\n") if re.match(r"^\s*- \d{4}-\d{2}-\d{2} · ", h)]
    return rec


def head(rec):
    return "<!-- decision\n%s\n-->\n" % "\n".join("%s: %s" % (k, rec.get(k, "")) for k in FIELDS)


def render(cfg, rec, sections):
    T = lambda k: t(cfg, "context.decision." + k)
    out = [head(rec), "# %s · %s" % (rec["id"], rec["title"]), ""]
    for k in SECTIONS:
        out += ["## " + T(k), "", sections.get(k, "").strip() or "—", ""]
    return "\n".join(out)


def load_all(cfg):
    d = ddir(cfg)
    recs, errs = [], []
    for f in sorted(d.glob("D-*.md")) if d.is_dir() else []:
        try:
            recs.append(parse(f))
        except ValueError as e:
            errs.append(str(e))
    return recs, errs


def find(cfg, did):
    recs, _ = load_all(cfg)
    for r in recs:
        if r["id"].upper() == did.upper():
            return r
    die("decision %s not found in %s" % (did, ddir(cfg)))


def next_id(cfg):
    recs, _ = load_all(cfg)
    n = max([int(r["id"].split("-")[1]) for r in recs if re.match(r"^D-\d+$", r["id"])] or [0])
    return "D-%03d" % (n + 1)


def rewrite_head(rec, updates, history_line=None):
    text = rec["_path"].read_text(encoding="utf-8")
    m = HEAD.match(text)
    new = dict(rec)
    new.update(updates)
    body = text[m.end():]
    if history_line:
        body = body.rstrip("\n")
        body = re.sub(r"\n—$", "", body)  # replace the empty-history dash
        body += "\n- " + history_line + "\n"
    rec["_path"].write_text(head(new) + body, encoding="utf-8")


# ---------- public helpers (used by other kit scripts) ----------

def add_decision(cfg, title, status="proposed", scope="", source="", context="", decision="", alternatives="",
                 by="", supersedes="", consequences=""):
    if status not in STATUSES or status == "superseded":
        die("status must be one of %s" % ", ".join(s for s in STATUSES if s != "superseded"))
    if status in HUMAN and not by.strip():
        die("status %s needs --by: the person who decided" % status)
    if status == "observed" and not source.strip():
        die("an observed decision needs --source: where it was seen")
    d = ddir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    did = next_id(cfg)
    rec = {k: "" for k in FIELDS}
    rec.update(id=did, title=title.strip(), status=status, date=today(), by=by.strip(), scope=scope.strip(),
               source=source.strip(), supersedes=supersedes.strip().upper())
    hist = "%s · %s%s" % (today(), status, (" · " + by.strip()) if by.strip() else "")
    rec["_path"] = d / ("%s-%s.md" % (did, slugify(title)))
    rec["_path"].write_text(render(cfg, rec, {"context": context, "decision": decision, "alternatives": alternatives,
                                              "consequences": consequences, "history": "- " + hist}), encoding="utf-8")
    if rec["supersedes"]:
        old = find(cfg, rec["supersedes"])
        if old["status"] == "rejected":
            die("%s is rejected; a rejected decision cannot be superseded" % old["id"])
        rewrite_head(old, {"status": "superseded", "superseded_by": did}, "%s · superseded by %s" % (today(), did))
    write_index(cfg)
    return did, rec["_path"]


def set_status(cfg, did, status, by="", note=""):
    rec = find(cfg, did)
    if status not in STATUSES:
        die("status must be one of %s" % ", ".join(STATUSES))
    if status == "superseded":
        die("superseded is set by adding a newer decision with --supersedes %s" % rec["id"])
    if status not in MOVES.get(rec["status"], set()):
        die("%s is %s; it cannot move to %s (allowed: %s)" % (rec["id"], rec["status"], status,
                                                               ", ".join(sorted(MOVES.get(rec["status"], ()))) or "none"))
    if status in HUMAN and not by.strip():
        die("status %s needs --by: the person who decided" % status)
    line = "%s · %s%s%s" % (today(), status, (" · " + by.strip()) if by.strip() else "", (" · " + note.strip()) if note.strip() else "")
    updates = {"status": status}
    if status in HUMAN:
        updates.update(by=by.strip(), date=today())
    rewrite_head(rec, updates, line)
    write_index(cfg)
    return rec["id"]


def write_index(cfg):
    recs, _ = load_all(cfg)
    T = lambda k: t(cfg, "context.index." + k)
    lines = ["# " + T("title"), "", T("intro"), "",
             "| ID | %s | %s | %s | %s |" % (T("decision"), T("status"), T("scope"), T("date")), "|---|---|---|---|---|"]
    for r in recs:
        lines.append("| [%s](%s) | %s | %s | %s | %s |" % (r["id"], r["_path"].name, r["title"].replace("|", "/"),
                                                         t(cfg, "context.status." + r["status"]), r["scope"] or "—", r["date"]))
    if not recs:
        lines.append("| — | | | | |")
    d = ddir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def check_all(cfg):
    recs, errs = load_all(cfg)
    ids = {}
    for r in recs:
        if not re.match(r"^D-\d{3,}$", r["id"]):
            errs.append("%s: id must look like D-001" % r["_path"].name)
        if r["id"] in ids:
            errs.append("duplicate id %s (%s, %s)" % (r["id"], ids[r["id"]], r["_path"].name))
        ids[r["id"]] = r["_path"].name
        if not r["_path"].name.startswith(r["id"] + "-"):
            errs.append("%s: file name must start with %s-" % (r["_path"].name, r["id"]))
        if r["status"] not in STATUSES:
            errs.append("%s: unknown status %r" % (r["id"], r["status"]))
        if not r["title"]:
            errs.append("%s: title is empty" % r["id"])
        if r["status"] in HUMAN and not r["by"]:
            errs.append("%s: %s without the name of who decided (by:)" % (r["id"], r["status"]))
        if r["status"] == "observed" and not r["source"]:
            errs.append("%s: observed without a source" % r["id"])
        hist = [h.split(" · ")[1].split(" ")[0] for h in r["_history"] if len(h.split(" · ")) > 1]
        hist = [h for h in hist if h in STATUSES]
        for a, b in zip(hist, hist[1:]):
            if b != "superseded" and b not in MOVES.get(a, set()):
                errs.append("%s: history moves %s -> %s, which is not allowed" % (r["id"], a, b))
        if hist and hist[-1] != r["status"]:
            errs.append("%s: status is %s but the last history line says %s" % (r["id"], r["status"], hist[-1]))
    for r in recs:
        for k in ("supersedes", "superseded_by"):
            if r[k] and r[k] not in ids:
                errs.append("%s: %s points to unknown %s" % (r["id"], k, r[k]))
        if r["status"] == "superseded" and not r["superseded_by"]:
            errs.append("%s: superseded without superseded_by" % r["id"])
    return recs, errs


def rule_hint(did, status):
    """An approved decision that states a rule the team must keep: offer to record it in the rules registry."""
    if status == "approved":
        print("NEXT if this decision is a rule the team must keep, offer: python3 <kit>/scripts/rules.py add --decision %s "
              "--title \"...\" --category <category> --severity must|should [--applies-to <apps>] [--skills <skills>]" % did)


# ---------- commands ----------

def main():
    ap = argparse.ArgumentParser(description="Decision log with a status lifecycle.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add", help="record a decision")
    p.add_argument("--title", required=True); p.add_argument("--status", default="proposed")
    for k in ("scope", "source", "context", "decision", "alternatives", "consequences", "by", "supersedes"):
        p.add_argument("--" + k, default="")
    p = sub.add_parser("set", help="move a decision to a new status")
    p.add_argument("id"); p.add_argument("status"); p.add_argument("--by", default=""); p.add_argument("--note", default="")
    p = sub.add_parser("list", help="list decisions"); p.add_argument("--status"); p.add_argument("--scope")
    p = sub.add_parser("show", help="print one decision"); p.add_argument("id")
    sub.add_parser("index", help="write decisions/index.md")
    sub.add_parser("check", help="validate every decision")
    a = ap.parse_args()
    cfg = load()
    if a.cmd == "add":
        did, path = add_decision(cfg, a.title, a.status, a.scope, a.source, a.context, a.decision, a.alternatives,
                                 a.by, a.supersedes, a.consequences)
        print("Recorded %s (%s): %s" % (did, a.status, path.relative_to(cfg["_root"])))
        rule_hint(did, a.status)
    elif a.cmd == "set":
        did = set_status(cfg, a.id, a.status, a.by, a.note)
        print("%s is now %s" % (did, a.status))
        rule_hint(did, a.status)
    elif a.cmd == "list":
        recs, _ = load_all(cfg)
        rows = [r for r in recs if (not a.status or r["status"] == a.status)
                and (not a.scope or a.scope.lower() in [s.strip().lower() for s in r["scope"].split(",")])]
        for r in rows:
            print("%-6s %-12s %-24s %s" % (r["id"], r["status"], (r["scope"] or "-")[:24], r["title"]))
        if not rows:
            print("No decisions match.")
    elif a.cmd == "show":
        print(find(cfg, a.id)["_path"].read_text(encoding="utf-8"))
    elif a.cmd == "index":
        write_index(cfg)
        print("Wrote %s" % (ddir(cfg) / "index.md").relative_to(cfg["_root"]))
    elif a.cmd == "check":
        recs, errs = check_all(cfg)
        for e in errs:
            print("ERROR:", e)
        print("Decisions OK (%d)" % len(recs) if not errs else "%d error(s)" % len(errs))
        sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
