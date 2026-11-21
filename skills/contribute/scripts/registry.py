#!/usr/bin/env python3
"""Local-component registry: scan apps for local blocks and keep the registry in step with the code.

A local component is code that is not (yet) part of the DS:
  - CSS (every stack): a block that opens with  /* <local.marker>: <name> */  and holds classes with the
    local prefix (kit.config.json > local.prefix). The block ends at the next local marker, a DS marker
    (ds.json > css.marker), </style>, <script, a section comment /* ==== */, or the end of the file.
  - react / vue: a file under <app>/src/components/local/ with a header comment
    /* <marker>: <name> */ (also // <marker>: <name> or <!-- <marker>: <name> --> in .vue).

Registry (kit.config.json > local.registry), JSON:
  - written by this script: file, line, size, classes, uses, fp (fingerprint), history
  - written by people or the agent: title, kind, status, summary, where, vs_ds, decision, decided_on,
    demo, and a proposal block when status is "propose"

Commands:
  scan        print what the scan finds (writes nothing)
  update      write new / changed / removed blocks into the registry (new entries get status "pending")
  check       compare code and registry; exit 1 when they differ or a proposal is incomplete or stale
  ack <id>    confirm that the proposal of <id> was reviewed against the current block
  list        list entries (--app, --status filters)
  report      write a Markdown summary (--out FILE, default stdout), in the project language
Options: --date YYYY-MM-DD (default today)
"""
import argparse
import collections
import datetime
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from kitconf import load as load_cfg, t  # noqa: E402

STATUSES = ("keep", "propose", "pending", "replaced", "removed")
KINDS = ("component", "override", "pattern", "layout", "data")
HIDDEN = ("replaced", "removed")  # kept for traceability, not shown in reviews
PROPOSAL_TYPES = ("component", "variant", "pattern")
PROPOSAL_BUMPS = ("patch", "minor", "major")
PROPOSAL_REQ = ("name", "type", "purpose", "anatomy", "rules", "tokens", "bump")
PROPOSAL_OPT = ("variants", "states", "reuse", "missing")

SKIP_DIRS = {"node_modules", "dist", "build", ".git", ".vite", "coverage"}
BLOCK_EXT = {".html", ".htm", ".css", ".scss", ".vue"}
USE_EXT = BLOCK_EXT | {".js", ".mjs", ".ts", ".tsx", ".jsx"}
LOCAL_DIR = "src/components/local"


class Ctx:
    def __init__(self, cfg):
        self.cfg = cfg
        self.root = Path(cfg["_root"])
        loc = cfg["local"]
        self.prefix, self.marker = loc["prefix"], loc["marker"]
        self.reg_path = self.root / loc["registry"]
        self.stack = cfg["stack"]
        ds = cfg.get("_ds") or {}
        mk = (ds.get("css") or {}).get("marker") or {"begin": "@ds:begin", "end": "@ds:end"}
        self.ds_begin, self.ds_end = mk["begin"], mk["end"]
        self.meta = ((ds.get("version_label") or {}).get("meta")) or "ds-version"
        m = re.escape(self.marker)
        self.comment = re.compile(r"/\*\s*%s:\s*(.*?)\*/" % m, re.S)
        self.header = re.compile(r"(?:/\*\s*%s:\s*(.*?)\*/|//\s*%s:\s*([^\n]*)|<!--\s*%s:\s*(.*?)-->)" % (m, m, m), re.S)
        self.stop = re.compile(r"/\*\s*%s:|/\*\s*%s|/\*\s*%s|</style>|<script|/\*\s*=+"
                               % (m, re.escape(self.ds_begin), re.escape(self.ds_end)))
        self.ds_region = re.compile(r"/\*\s*%s.*?/\*\s*%s[^*]*\*/" % (re.escape(self.ds_begin), re.escape(self.ds_end)), re.S)
        p = re.escape(self.prefix)
        self.xtoken = re.compile(r"(?<![A-Za-z0-9_-])%s[a-z0-9][a-z0-9-]*" % p)
        self.xclass = re.compile(r"\.(%s[a-z0-9][a-z0-9-]*)" % p)

    def rel(self, p):
        return p.relative_to(self.root).as_posix()


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def fp_of(text):
    return hashlib.sha1(norm(text).encode("utf-8")).hexdigest()[:12]


def title_from(name):
    s = re.sub(r"^[\s.:—–-]+", "", norm(name)).split(". ")[0].strip()
    return (s[:90].rsplit(" ", 1)[0] + "…") if len(s) > 90 else (s or "(unnamed)")


def slug(s):
    s = s.lower().replace("đ", "d")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:48] or "item"


def app_files(ctx, app):
    base = ctx.root / app["path"]
    if base.is_file():
        return [base]
    out = []
    for p in sorted(base.rglob("*")):
        if p.is_file() and p.suffix in USE_EXT and not (set(p.relative_to(base).parts[:-1]) & SKIP_DIRS):
            out.append(p)
    return out


def scan(ctx, app):
    files = app_files(ctx, app)
    texts = [(f, f.read_text(encoding="utf-8", errors="replace")) for f in files]
    local_dir = (ctx.root / app["path"] / LOCAL_DIR).resolve()
    app_stack = app.get("stack") or ctx.stack  # apps[].stack overrides the project stack
    spans, unmarked = [], []
    seen_fp, count = {}, collections.Counter()

    def add(name, f, s, a, b, kind):
        key, fp = norm(name), fp_of(s[a:b])
        if seen_fp.get((key, fp)):
            return  # generated copy of the same block (shared shell built into many files): count once
        seen_fp[(key, fp)] = True
        count[key] += 1
        anchor = key if count[key] == 1 else "%s #%d" % (key, count[key])
        spans.append({"anchor": anchor, "path": f, "text": s, "a": a, "b": b, "kind": kind, "fp": fp})

    for f, s in texts:
        in_local = app_stack in ("react", "vue") and local_dir in f.resolve().parents
        if in_local and f.suffix in (".tsx", ".jsx", ".ts", ".js", ".vue"):
            m = ctx.header.search(s[:2000])
            if m:
                add(next(g for g in m.groups() if g is not None), f, s, 0, len(s), "file")
            else:
                unmarked.append(ctx.rel(f))
            continue
        if f.suffix not in BLOCK_EXT:
            continue
        clean = ctx.ds_region.sub(lambda m: " " * len(m.group(0)), s)  # never read inside the embedded DS
        for m in ctx.comment.finditer(clean):
            e = ctx.stop.search(clean, m.end())
            add(m.group(1), f, s, m.start(), e.start() if e else len(s), "css")

    total = collections.Counter()
    for _f, s in texts:
        total.update(ctx.xtoken.findall(ctx.ds_region.sub("", s)))
    inside = collections.Counter()
    for sp in spans:
        inside.update(ctx.xtoken.findall(sp["text"][sp["a"]:sp["b"]]))
    blocks, defined = [], set()
    for sp in spans:
        text = sp["text"][sp["a"]:sp["b"]]
        found = ctx.xclass.findall(text) if sp["kind"] == "css" else ctx.xtoken.findall(text)
        cls = list(dict.fromkeys(found))
        defined.update(cls)
        uses = sum(max(total[c] - inside[c], 0) for c in cls)
        if sp["kind"] == "file":  # component usages: <Name …> in other files (and <name-kebab> for vue)
            stem = sp["path"].stem
            kebab = re.sub(r"(?<!^)([A-Z])", r"-\1", stem).lower()
            pat = re.compile(r"<(?:%s|%s)\b" % (re.escape(stem), re.escape(kebab)))
            uses += sum(len(pat.findall(s)) for f, s in texts if f != sp["path"])
        blocks.append({"anchor": sp["anchor"], "file": ctx.rel(sp["path"]), "line": sp["text"].count("\n", 0, sp["a"]) + 1,
                       "size": sp["b"] - sp["a"], "classes": cls, "uses": uses, "fp": sp["fp"]})
    loose = sorted(x for x in total if x not in defined and total[x] - inside[x] > 0)
    ver = None
    rx = re.compile(r'<meta\s+name="%s"\s+content="[^"\d]*([\d.]+)"' % re.escape(ctx.meta))
    for _f, s in texts:
        ver = ver or rx.search(s)
    return {"blocks": blocks, "loose": loose, "unmarked": unmarked, "ds": ver.group(1) if ver else "",
            "dups": [k for k, n in count.items() if n > 1]}


def load_reg(ctx):
    if ctx.reg_path.is_file():
        return json.loads(ctx.reg_path.read_text(encoding="utf-8"))
    return {"updated": "", "apps": {}, "unassigned": {}, "components": []}


def save_reg(ctx, reg, date):
    reg["updated"] = date
    ctx.reg_path.parent.mkdir(parents=True, exist_ok=True)
    ctx.reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def diff_classes(old, new):
    a, b = [c for c in new if c not in old], [c for c in old if c not in new]
    parts = (["added " + ", ".join(a[:6]) + ("…" if len(a) > 6 else "")] if a else []) + \
            (["removed " + ", ".join(b[:6]) + ("…" if len(b) > 6 else "")] if b else [])
    return "; ".join(parts) or "block content changed, same classes"


def plan(ctx, reg):
    """Compare code with the registry. Returns ([(kind, app_id, payload, note)], scans)."""
    out, scans = [], {}
    by_anchor = {(e["app"], e.get("anchor")): e for e in reg["components"] if e.get("anchor")}
    declared = {a["id"] for a in ctx.cfg["apps"]}
    for app in ctx.cfg["apps"]:
        aid = app["id"]
        sc = scans[aid] = scan(ctx, app)
        matched = set()
        for b in sc["blocks"]:
            e = by_anchor.get((aid, b["anchor"]))
            if not e:
                out.append(("new", aid, b, "new block: " + title_from(b["anchor"])))
                continue
            matched.add(id(e))
            if e.get("status") == "removed":
                out.append(("back", aid, (e, b), "removed block is back: " + e["title"]))
            elif e.get("fp") != b["fp"]:
                out.append(("mod", aid, (e, b), "%s: %s" % (e["title"], diff_classes(e.get("classes", []), b["classes"]))))
        for e in reg["components"]:
            if e["app"] == aid and e.get("anchor") and id(e) not in matched and e.get("status") != "removed":
                out.append(("gone", aid, e, "block no longer in the app: " + e["title"]))
        base = set(reg.get("unassigned", {}).get(aid, []))
        new_loose = [x for x in sc["loose"] if x not in base]
        if new_loose:
            out.append(("loose", aid, new_loose, "%s classes outside a %s block: %s" % (
                ctx.prefix, ctx.marker, ", ".join(new_loose[:8]) + ("…" if len(new_loose) > 8 else ""))))
        for f in sc["unmarked"]:
            out.append(("unmarked", aid, f, "file in %s has no /* %s: <name> */ header: %s" % (LOCAL_DIR, ctx.marker, f)))
        if sc["dups"]:
            out.append(("dup", aid, sc["dups"], "two different blocks share a name (numbered #2, #3…); give each a unique name"))
    for e in reg["components"]:
        if e["app"] not in declared and e.get("status") not in HIDDEN:
            out.append(("orphan", e["app"], e, "entry for an app not declared in kit.config.json: " + e["title"]))
    return out, scans


ERRORS = ("new", "mod", "gone", "back", "loose", "unmarked")


def proposal_missing(e):
    pr = e.get("proposal") or {}
    miss = [k for k in PROPOSAL_REQ if not str(pr.get(k, "")).strip()]
    if pr.get("type") and pr["type"] not in PROPOSAL_TYPES:
        miss.append("type must be one of " + ", ".join(PROPOSAL_TYPES))
    if pr.get("bump") and pr["bump"] not in PROPOSAL_BUMPS:
        miss.append("bump must be one of " + ", ".join(PROPOSAL_BUMPS))
    return miss


def proposal_errors(reg):
    errs = []
    for e in reg["components"]:
        if e.get("status") != "propose":
            continue
        miss = proposal_missing(e)
        if miss:
            errs.append("[%s] proposal incomplete: %s (missing: %s)" % (e["app"], e["id"], ", ".join(miss)))
        elif e.get("anchor") and (e.get("proposal") or {}).get("fp") != e.get("fp"):
            errs.append("[%s] block changed since the proposal was reviewed: %s. Review the proposal, then run: ack %s"
                        % (e["app"], e["id"], e["id"]))
    return errs


def field_errors(reg):
    errs = []
    for e in reg["components"]:
        if e.get("status") not in STATUSES:
            errs.append("[%s] %s: status must be one of %s" % (e["app"], e["id"], ", ".join(STATUSES)))
        if e.get("kind", "component") not in KINDS:
            errs.append("[%s] %s: kind must be one of %s" % (e["app"], e["id"], ", ".join(KINDS)))
    return errs


def cmd_scan(ctx, _a):
    for app in ctx.cfg["apps"]:
        sc = scan(ctx, app)
        print("== %s (DS %s): %d blocks, %d loose %s classes" % (app["id"], sc["ds"] or "unknown", len(sc["blocks"]), len(sc["loose"]), ctx.prefix))
        for b in sc["blocks"]:
            print("  %s:%-5d %3d classes %4d uses  %s" % (b["file"], b["line"], len(b["classes"]), b["uses"], title_from(b["anchor"])))
        for f in sc["unmarked"]:
            print("  unmarked file: " + f)
    return 0


def cmd_check(ctx, _a):
    reg = load_reg(ctx)
    out, _ = plan(ctx, reg)
    for kind, aid, _x, note in out:
        print(("ERROR: " if kind in ERRORS else "NOTE: ") + "[%s] %s" % (aid, note))
    perr = proposal_errors(reg) + field_errors(reg)
    for m in perr:
        print("ERROR: " + m)
    pend = [e for e in reg["components"] if e.get("status") == "pending"]
    for e in pend:
        print("PENDING: [%s] %s: %s" % (e["app"], e["id"], e["title"]))
    errs = [o for o in out if o[0] in ERRORS]
    if errs or perr:
        if any(o[0] not in ("loose", "unmarked") for o in errs):
            print("\nRegistry does not match the code. Run update, fill in the judgement fields of new or changed entries, then check again.")
        if any(o[0] in ("loose", "unmarked") for o in errs):
            print("\nMove loose %s classes into a /* %s: <name> */ block (or add the header to the file), then run again. update never accepts them." % (ctx.prefix, ctx.marker))
        return 1
    print("Registry matches the apps (%d entries, %d pending, %d proposals)." % (
        len([e for e in reg["components"] if e.get("status") not in HIDDEN]), len(pend),
        len([e for e in reg["components"] if e.get("status") == "propose"])))
    return 0


def cmd_update(ctx, a):
    reg, date = load_reg(ctx), a.date
    out, scans = plan(ctx, reg)
    first = {x["id"] for x in ctx.cfg["apps"] if x["id"] not in reg.get("unassigned", {})}
    ids = {e["id"] for e in reg["components"]}
    for kind, aid, x, _note in out:
        if kind == "new":
            title = title_from(x["anchor"])
            base = "%s-%s" % (aid, slug(title))
            i, n = base, 2
            while i in ids:
                i, n = "%s-%d" % (base, n), n + 1
            ids.add(i)
            reg["components"].append({
                "id": i, "app": aid, "anchor": x["anchor"], "title": title, "kind": "component", "status": "pending",
                "summary": "", "where": "", "vs_ds": "", "decision": "", "decided_on": "",
                "file": x["file"], "line": x["line"], "size": x["size"], "classes": x["classes"], "uses": x["uses"], "fp": x["fp"],
                "history": [{"date": date, "change": "added", "note": "%d classes, line %d" % (len(x["classes"]), x["line"])}],
            })
        elif kind in ("mod", "back"):
            e, b = x
            if kind == "back":
                e["status"] = "pending"
                e.pop("removed_on", None)
                e["history"].append({"date": date, "change": "added", "note": "block is back in the app; confirm the decision again"})
            else:
                e["history"].append({"date": date, "change": "modified", "note": diff_classes(e.get("classes", []), b["classes"])})
            e.update({k: b[k] for k in ("file", "line", "size", "classes", "uses", "fp")})
        elif kind == "gone":
            x["status"], x["removed_on"] = "removed", date
            x["history"].append({"date": date, "change": "removed", "note": "block no longer in the app"})
    for app in ctx.cfg["apps"]:
        aid, sc = app["id"], scans[app["id"]]
        for b in sc["blocks"]:  # refresh line and use counts of unchanged entries
            for e in reg["components"]:
                if e["app"] == aid and e.get("anchor") == b["anchor"] and e.get("fp") == b["fp"]:
                    e.update({k: b[k] for k in ("file", "line", "size", "uses")})
        # loose classes found on the first run are recorded as existing debt; the list only shrinks afterwards
        old = reg.setdefault("unassigned", {}).get(aid)
        reg["unassigned"][aid] = sc["loose"] if old is None else [x for x in old if x in sc["loose"]]
        reg.setdefault("apps", {})[aid] = {"name": app.get("name", aid), "path": app["path"], "ds": sc["ds"]}
    save_reg(ctx, reg, date)
    for kind, aid, x, note in out:
        if kind == "loose" and aid in first:
            print("BASELINE: [%s] %s (first scan: recorded as existing debt; new ones later are errors)" % (aid, note))
        elif kind in ("loose", "unmarked"):
            print("NOT RECORDED: [%s] %s" % (aid, note))
        elif kind in ("dup", "orphan"):
            print("NOTE: [%s] %s" % (aid, note))
        else:
            print("Recorded: [%s] %s" % (aid, note))
            if kind == "mod" and x[0].get("status") == "propose":
                print("  The proposal of %s must be reviewed again, then run: ack %s" % (x[0]["id"], x[0]["id"]))
    if not out:
        print("Nothing to record.")
    pend = [e for e in reg["components"] if e.get("status") == "pending"]
    if pend:
        print("\nFill in status, summary, where, vs_ds, decision, decided_on for %d pending entries:" % len(pend))
        for e in pend:
            print("  - %s (%s)" % (e["id"], e["title"]))
    return 0


def cmd_ack(ctx, a):
    if not a.target:
        sys.exit("ERROR: ack needs an entry id.")
    reg = load_reg(ctx)
    e = next((x for x in reg["components"] if x["id"] == a.target), None)
    if not e:
        sys.exit("ERROR: no entry with id '%s'." % a.target)
    if e.get("status") != "propose":
        sys.exit("ERROR: entry '%s' is not in status 'propose'." % a.target)
    miss = proposal_missing(e)
    if miss:
        sys.exit("ERROR: proposal incomplete, cannot acknowledge. Missing: " + ", ".join(miss))
    e["proposal"]["fp"], e["proposal"]["updated"] = e.get("fp", ""), a.date
    e.setdefault("history", []).append({"date": a.date, "change": "proposal", "note": "proposal reviewed against the current block"})
    save_reg(ctx, reg, a.date)
    print("Acknowledged proposal: %s" % e["id"])
    return 0


def select(reg, a):
    rows = reg["components"]
    if a.app:
        rows = [e for e in rows if e["app"] == a.app]
    if a.status:
        rows = [e for e in rows if e.get("status") in a.status.split(",")]
    elif not a.all:
        rows = [e for e in rows if e.get("status") not in HIDDEN]
    return rows


def cmd_list(ctx, a):
    rows = select(load_reg(ctx), a)
    if not rows:
        print("No entries.")
        return 0
    w = max(len(e["id"]) for e in rows)
    print("%-*s  %-14s %-8s %-10s %5s  %s" % (w, "id", "app", "status", "kind", "uses", "title"))
    for e in rows:
        print("%-*s  %-14s %-8s %-10s %5s  %s" % (w, e["id"], e["app"][:14], e.get("status", ""), e.get("kind", ""), e.get("uses", ""), e["title"]))
    return 0


def cmd_report(ctx, a):
    cfg, reg = ctx.cfg, load_reg(ctx)
    rows = select(reg, a)
    L = ["# " + t(cfg, "contribute.report.title"), "", t(cfg, "contribute.report.updated", date=reg.get("updated") or "-"), ""]
    names = {x["id"]: x.get("name", x["id"]) for x in cfg["apps"]}
    for aid in dict.fromkeys(e["app"] for e in rows):
        L += ["## " + names.get(aid, aid), "",
              "| %s |" % " | ".join(t(cfg, "contribute.report.col." + c) for c in ("id", "title", "status", "kind", "uses", "decision")),
              "|---|---|---|---|---|---|"]
        for e in (x for x in rows if x["app"] == aid):
            st = t(cfg, "contribute.status." + e.get("status", "pending"))
            L.append("| `%s` | %s | %s | %s | %s | %s |" % (e["id"], e["title"].replace("|", "\\|"), st, e.get("kind", ""),
                                                          e.get("uses", ""), (e.get("decision") or "").replace("|", "\\|")))
        L.append("")
    props = [e for e in rows if e.get("status") == "propose"]
    if props:
        L += ["## " + t(cfg, "contribute.report.proposals"), ""]
        for e in props:
            pr = e.get("proposal") or {}
            L += ["### %s (`%s`)" % (pr.get("name") or e["title"], e["id"]), "", "> " + t(cfg, "contribute.report.notStandard"), ""]
            for k in PROPOSAL_REQ[1:] + PROPOSAL_OPT:
                if str(pr.get(k, "")).strip():
                    L.append("- **%s:** %s" % (t(cfg, "contribute.proposal." + k), pr[k]))
            L.append("")
    pend = [e for e in rows if e.get("status") == "pending"]
    if pend:
        L += ["## " + t(cfg, "contribute.report.pending"), ""] + ["- `%s` %s" % (e["id"], e["title"]) for e in pend] + [""]
    text = "\n".join(L)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print("Wrote " + a.out)
    else:
        print(text)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["scan", "update", "check", "ack", "list", "report"])
    ap.add_argument("target", nargs="?", help="entry id (ack)")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--app", help="list/report: only this app id")
    ap.add_argument("--status", help="list/report: comma-separated statuses")
    ap.add_argument("--all", action="store_true", help="list/report: include replaced and removed entries")
    ap.add_argument("--out", help="report: output Markdown file")
    a = ap.parse_args()
    ctx = Ctx(load_cfg())
    sys.exit({"scan": cmd_scan, "update": cmd_update, "check": cmd_check, "ack": cmd_ack,
              "list": cmd_list, "report": cmd_report}[a.cmd](ctx, a))


if __name__ == "__main__":
    main()
