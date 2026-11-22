#!/usr/bin/env python3
"""Verify a developer build against the approved prototype and record what was checked.

Commands:
  verify.py init <name> --app <id> [--implementation <base URL>]
      Write <paths.verify>/<name>/pairs.json: prototype base (the app's entry), implementation base, viewports,
      one example screen pair and one example flow. Never overwrites.
  verify.py run <name> [--threshold 1.0] [--min-pixels 500]
      Run verify.js (Playwright) on both sides, then write <run>/report.md and report.json:
        Fail                 implementation does not open, page or console errors, a flow that passes in the
                             prototype but fails in the implementation, axe-core critical or serious
        Differences          visual difference of at least --min-pixels pixels or --threshold percent (side-by-side image), colours, font sizes
                             and radii that match no DS token and are not in the prototype, DS components of the
                             prototype missing in the implementation, prototype texts missing in the implementation
        Approved deviations  differences accepted with a decision from the decision log (accept)
        Skipped              with the reason
      Exit 1 when anything fails.
  verify.py accept <name> <finding id> --decision D-007 [--by "name"]
      Mark a difference as an approved deviation. The decision must exist in the log and be approved,
      implemented or verified. Accepted findings stay accepted in later runs while their id is the same.
  verify.py close <name> --by "name" [--all-reviewed]
      After the latest run has no failures: move the decisions in scope that are implemented to verified.
      Refuses while differences are neither accepted nor confirmed as reviewed by a person (--all-reviewed).
  verify.py report <name>
      Rebuild the latest report (for example after accept).

Never edits the implementation or the prototype, commits, pushes or sends anything.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[2]
sys.path.insert(0, str(KIT / "scripts"))
sys.path.insert(0, str(KIT / "skills" / "context" / "scripts"))
from kitconf import load, t, ds_path, app as app_cfg, for_app  # noqa: E402

FAIL_IMPACT = {"critical", "serious"}


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def vdir(cfg, name):
    if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", name):
        die("name must be lowercase letters, digits and hyphens")
    return Path(cfg["_root"]) / cfg["paths"]["verify"] / name


def fid(*parts):
    return "F-" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:6]


def prototype_base(cfg, app):
    base = Path(cfg["_root"]) / app["path"]
    f = base / "dist" / "index.html" if app.get("stack", cfg["stack"]) in ("react", "vue") else base / app.get("entry", "index.html")
    return f.resolve().as_uri()


# ---------- init ----------

def cmd_init(cfg, a):
    app = app_cfg(cfg, a.app)
    d = vdir(cfg, a.name)
    f = d / "pairs.json"
    if f.exists():
        die("pairs.json exists, nothing written: %s" % f.relative_to(cfg["_root"]))
    d.mkdir(parents=True, exist_ok=True)
    pairs = {
        "_help": {
            "screens": "One pair per screen: prototype route (as in the app) and implementation path or URL. prepare: JS run on "
                       "each side to reach the same state. mask: selectors hidden on both sides (dates, avatars, live data).",
            "flows": "Same user goal on both sides; selectors may differ. Steps as in validate: click, fill, select, press, goto, "
                     "wait, expectVisible, expectHidden, expectText, expectUrl.",
        },
        "app": a.app,
        "prototypeBase": prototype_base(cfg, app),
        "implementationBase": a.implementation or "http://localhost:3000/",
        "viewports": [390, 1280],
        "screens": [{"id": "S01", "name": "Home", "prototype": "", "implementation": "", "mask": []}],
        "flows": [{"name": "Open settings", "viewport": 1280,
                   "prototype": {"start": "", "steps": [{"click": "a[href='#/settings']"}, {"expectUrl": "#/settings"}]},
                   "implementation": {"start": "", "steps": [{"click": "a[href='/settings']"}, {"expectUrl": "/settings"}]}}],
    }
    f.write_text(json.dumps(pairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wrote %s. List the approved screens and flows, then run." % f.relative_to(cfg["_root"]))


# ---------- tokens ----------

def token_names(cfg):
    ds = cfg.get("_ds")
    if not ds or not ds["css"]["bundle"] or "://" in ds["css"]["bundle"]:
        return None
    p = Path(ds_path(cfg, ds["css"]["bundle"]))
    if not p.is_file():
        return None
    prefix = ds["tokens"]["prefix"]
    names = sorted(set(re.findall(r"(%s[\w-]+)\s*:" % re.escape(prefix), p.read_text(encoding="utf-8"))))
    return {"prefix": prefix, "names": names}


# ---------- images ----------

def side_by_side(run, item, threshold):
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return None
    sh = run / "shots"
    p, i = item.get("prototype", {}).get("shot"), item.get("implementation", {}).get("shot")
    if not p or not i:
        return None
    a, b = Image.open(sh / p).convert("RGB"), Image.open(sh / i).convert("RGB")
    w, h = max(a.width, b.width), max(a.height, b.height)
    pa, pb = Image.new("RGB", (w, h), (255, 255, 255)), Image.new("RGB", (w, h), (255, 255, 255))
    pa.paste(a, (0, 0)); pb.paste(b, (0, 0))
    mask = ImageChops.difference(pa, pb).convert("L").point(lambda v: 255 if v > 24 else 0)
    changed = mask.histogram()[255]
    pct = 100.0 * changed / (w * h)
    diff = Image.composite(Image.new("RGB", (w, h), (255, 0, 80)), pb.point(lambda v: int(v * 0.35 + 165)), mask)
    gap = 16
    out = Image.new("RGB", (w * 3 + gap * 2, h), (230, 230, 235))
    out.paste(pa, (0, 0)); out.paste(pb, (w + gap, 0)); out.paste(diff, (2 * (w + gap), 0))
    (run / "side").mkdir(exist_ok=True)
    name = "%s__%s.png" % (item["screen"].lower(), item["vp"])
    if max(out.size) > 6000:
        out.thumbnail((6000, 6000))
    out.save(run / "side" / name)
    return {"pct": round(pct, 2), "px": changed, "image": "side/" + name, "sizeA": a.size, "sizeB": b.size}


# ---------- classify ----------

def classify(cfg, res, run, threshold, accepted, min_px=500):
    fail, diffs, skipped = [], [], []
    tok = res.get("tokens") or {"color": {}, "length": {}}
    colours, lengths = set(tok.get("color", {})), set(tok.get("length", {}))
    any_ds = any(sum((it.get("implementation") or {}).get("comps", {}).values()) for it in res["screens"])
    for it in res["screens"]:
        where = "%s · %spx" % (it["screen"], it["vp"])
        pr, im = it.get("prototype") or {}, it.get("implementation") or {}
        if pr.get("fatal"):
            fail.append((fid("proto-open", where), "open", where, "prototype: " + pr["fatal"]))
        if im.get("fatal"):
            fail.append((fid("open", where), "open", where, "implementation: " + im["fatal"]))
            continue
        for e in im.get("errors") or []:
            fail.append((fid("console", where, e), "console", where, e))
        for v in im.get("axe") or []:
            row = (fid("a11y", where, v["id"]), "a11y", where, "%s (%s, %d node(s)): %s" % (v["id"], v["impact"], v["nodes"], v["help"]))
            (fail if v["impact"] in FAIL_IMPACT else diffs).append(row)
        if pr.get("fatal"):
            continue
        vis = side_by_side(run, it, threshold)
        if vis and (vis["px"] >= min_px or vis["pct"] > threshold or vis["sizeA"] != vis["sizeB"]):
            size = "" if vis["sizeA"] == vis["sizeB"] else " · page %dx%d → %dx%d" % (tuple(vis["sizeA"]) + tuple(vis["sizeB"]))
            diffs.append((fid("visual", where), "visual", where, "%d px differ (%.2f%%)%s · %s" % (vis["px"], vis["pct"], size, vis["image"])))
        for kind, pool in (("color", colours), ("background", colours), ("border", colours), ("fontSize", lengths), ("radius", lengths)):
            proto_vals = set((pr.get("used") or {}).get(kind, {}))
            off = [(v, n) for v, n in ((im.get("used") or {}).get(kind) or {}).items() if v not in pool and v not in proto_vals]
            if off and pool:
                off.sort(key=lambda x: -x[1])
                detail = "; ".join("%s ×%d (%s)" % (v, n, (im.get("sample") or {}).get(kind + v, "?")) for v, n in off[:6])
                diffs.append((fid("token", where, kind, ",".join(sorted(v for v, _ in off))), "token", where, "%s: %s" % (kind, detail)))
        if any_ds:
            missing = sorted(set(pr.get("comps") or {}) - set(im.get("comps") or {}))
            if missing:
                diffs.append((fid("component", where, ",".join(missing)), "component", where, ", ".join("." + m for m in missing)))
        lost = [x for x in pr.get("texts") or [] if x not in set(im.get("texts") or [])]
        if lost:
            diffs.append((fid("copy", where, "|".join(sorted(lost))), "copy", where, "; ".join('"%s"' % x for x in lost[:8])
                          + (" (+%d)" % (len(lost) - 8) if len(lost) > 8 else "")))
    for f in res.get("flows") or []:
        p, i = f.get("prototype") or {}, f.get("implementation") or {}
        if p.get("ok") and not i.get("ok"):
            fail.append((fid("flow", f["name"]), "flow", f["name"], "implementation: " + (("step %s: %s" % (i.get("step"), i.get("error"))) if i.get("step") else (i.get("error") or "; ".join(i.get("errors") or [])))))
        elif not p.get("ok"):
            diffs.append((fid("flow-proto", f["name"]), "flow", f["name"], "fails in the prototype too: " + (p.get("error") or "")))
    if not res.get("axe"):
        skipped.append(("-", "a11y", "—", "axe-core not installed: npm i -D axe-core, then run again"))
    if not any_ds:
        skipped.append(("-", "component", "—", "the implementation exposes no DS component classes; component comparison skipped"))
    if not colours:
        skipped.append(("-", "token", "—", "no DS token values could be read from the prototype; token comparison skipped"))
    approved = [r + (accepted[r[0]]["decision"],) for r in diffs if r[0] in accepted]
    diffs = [r for r in diffs if r[0] not in accepted]
    return fail, diffs, approved, skipped


def scope_decisions(cfg, res, app_id):
    try:
        import decisions
    except ImportError:
        return []
    recs, _ = decisions.load_all(cfg)
    keys = {s["screen"].lower() for s in res["screens"]} | {app_id.lower()}
    return [r for r in recs if keys & {x.strip().lower() for x in r["scope"].split(",") if x.strip()}]


def write_report(cfg, name, run, res, threshold, min_px=500):
    d = run.parent
    accepted = json.loads((d / "accepted.json").read_text(encoding="utf-8")) if (d / "accepted.json").is_file() else {}
    pairs = json.loads((d / "pairs.json").read_text(encoding="utf-8"))
    fail, diffs, approved, skipped = classify(cfg, res, run, threshold, accepted, min_px)
    decs = scope_decisions(cfg, res, pairs.get("app", ""))
    T = lambda k, **kw: t(cfg, "verify." + k, **kw)
    L = ["# " + T("title", name=name), "",
         T("meta", started=res["started"][:19].replace("T", " "), proto=pairs.get("prototypeBase", ""), impl=pairs.get("implementationBase", ""),
           viewports=", ".join(map(str, res["viewports"]))), "",
         "| %s | %s | %s | %s |" % (T("fail"), T("differences"), T("approved"), T("skipped")), "|---|---|---|---|",
         "| %d | %d | %d | %d |" % (len(fail), len(diffs), len(approved), len(skipped)), ""]

    def table(rows, extra=False):
        if not rows:
            return ["—", ""]
        out = ["| ID | %s | %s | %s |%s" % (T("check"), T("where"), T("detail"), (" %s |" % T("decision")) if extra else ""),
               "|---|---|---|---|%s" % ("---|" if extra else "")]
        for r in rows:
            out.append("| %s | %s | %s | %s |%s" % (r[0], T("kind." + r[1]), r[2], r[3].replace("|", "/"), (" %s |" % r[4]) if extra else ""))
        return out + [""]
    L += ["## %s (%d)" % (T("failTitle"), len(fail)), "", T("failNote"), ""] + table(fail)
    L += ["## %s (%d)" % (T("diffTitle"), len(diffs)), "", T("diffNote"), ""] + table(diffs)
    L += ["## %s (%d)" % (T("approvedTitle"), len(approved)), ""] + table(approved, extra=True)
    L += ["## %s (%d)" % (T("skippedTitle"), len(skipped)), ""] + table(skipped)
    L += ["## " + T("decisionsTitle"), ""]
    if decs:
        L += ["| ID | %s | %s | %s |" % (T("decision"), T("status"), T("scope")), "|---|---|---|---|"]
        L += ["| %s | %s | %s | %s |" % (r["id"], r["title"], r["status"], r["scope"]) for r in decs] + [""]
    else:
        L += [T("noDecisions"), ""]
    L += [T("imagesNote"), ""]
    (run / "report.md").write_text("\n".join(L), encoding="utf-8")
    (run / "report.json").write_text(json.dumps({"fail": fail, "differences": diffs, "approved": approved, "skipped": skipped,
                                                 "decisions": [r["id"] for r in decs]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return fail, diffs, approved, skipped


def latest(cfg, name):
    d = vdir(cfg, name)
    runs = sorted(p for p in d.glob("2*") if (p / "results.json").is_file()) if d.is_dir() else []
    if not runs:
        die("no runs for %s yet" % name)
    return runs[-1]


def cmd_run(cfg, a):
    d = vdir(cfg, a.name)
    pairs = d / "pairs.json"
    if not pairs.is_file():
        die("pairs.json not found (run init)")
    tok = token_names(cfg)
    run = d / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run.mkdir(parents=True)
    (run / "tokens.json").write_text(json.dumps(tok or {"prefix": "--ds-", "names": []}), encoding="utf-8")
    p = subprocess.run(["node", str(HERE / "verify.js"), "--pairs", str(pairs), "--tokens", str(run / "tokens.json"),
                        "--out", str(run), "--project", cfg["_root"]], capture_output=True, text=True)
    sys.stdout.write(p.stdout)
    if p.returncode != 0 or not (run / "results.json").is_file():
        sys.stdout.write(p.stderr[-2000:])
        die("browser run failed")
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    fail, diffs, approved, skipped = write_report(cfg, a.name, run, res, a.threshold, a.min_pixels)
    print("Report: %s · %d fail · %d differences · %d approved · %d skipped" % (
        (run / "report.md").relative_to(cfg["_root"]), len(fail), len(diffs), len(approved), len(skipped)))
    sys.exit(1 if fail else 0)


def cmd_report(cfg, a):
    run = latest(cfg, a.name)
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    fail, diffs, approved, skipped = write_report(cfg, a.name, run, res, a.threshold, a.min_pixels)
    print("Report: %s · %d fail · %d differences · %d approved · %d skipped" % (
        (run / "report.md").relative_to(cfg["_root"]), len(fail), len(diffs), len(approved), len(skipped)))


def cmd_accept(cfg, a):
    import decisions
    rec = decisions.find(cfg, a.decision)
    if rec["status"] not in ("approved", "implemented", "verified"):
        die("%s is %s; only approved, implemented or verified decisions can cover a deviation" % (rec["id"], rec["status"]))
    run = latest(cfg, a.name)
    rep = json.loads((run / "report.json").read_text(encoding="utf-8"))
    ids = {r[0]: r for r in rep["differences"]}
    if a.finding not in ids:
        if a.finding in {r[0] for r in rep["fail"]}:
            die("%s is a failure, not a difference; failures are fixed, not accepted" % a.finding)
        die("%s is not an open difference in the latest run" % a.finding)
    f = vdir(cfg, a.name) / "accepted.json"
    acc = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    acc[a.finding] = {"decision": rec["id"], "by": a.by or "", "on": dt.date.today().isoformat(), "detail": ids[a.finding][3]}
    f.write_text(json.dumps(acc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("%s accepted as an approved deviation under %s" % (a.finding, rec["id"]))
    cmd_report(cfg, argparse.Namespace(name=a.name, threshold=a.threshold, min_pixels=a.min_pixels))


def cmd_close(cfg, a):
    import decisions
    run = latest(cfg, a.name)
    rep = json.loads((run / "report.json").read_text(encoding="utf-8"))
    if rep["fail"]:
        die("the latest run has %d failure(s); fix them and run again" % len(rep["fail"]))
    if rep["differences"] and not a.all_reviewed:
        die("%d difference(s) are neither accepted nor reviewed; accept them with a decision, or confirm a person reviewed "
            "them with --all-reviewed" % len(rep["differences"]))
    moved = []
    for did in rep.get("decisions") or []:
        rec = decisions.find(cfg, did)
        if rec["status"] == "implemented":
            decisions.set_status(cfg, did, "verified", by=a.by, note="verify %s/%s" % (a.name, run.name))
            moved.append(did)
    print("Verified: %s" % (", ".join(moved) if moved else "no implemented decisions in scope"))


def main():
    ap = argparse.ArgumentParser(description="Verify a developer build against the approved prototype.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("name"); p.add_argument("--app", required=True); p.add_argument("--implementation")
    p = sub.add_parser("run"); p.add_argument("name"); p.add_argument("--threshold", type=float, default=1.0)
    p.add_argument("--min-pixels", type=int, default=500)
    p = sub.add_parser("report"); p.add_argument("name"); p.add_argument("--threshold", type=float, default=1.0)
    p.add_argument("--min-pixels", type=int, default=500)
    p = sub.add_parser("accept"); p.add_argument("name"); p.add_argument("finding"); p.add_argument("--decision", required=True)
    p.add_argument("--by"); p.add_argument("--threshold", type=float, default=1.0); p.add_argument("--min-pixels", type=int, default=500)
    p = sub.add_parser("close"); p.add_argument("name"); p.add_argument("--by", required=True); p.add_argument("--all-reviewed", action="store_true")
    a = ap.parse_args()
    cfg = load()
    app_id = a.app if a.cmd == "init" else None  # the app's own DS profile (apps[].ds) for the token names
    if not app_id and (vdir(cfg, a.name) / "pairs.json").is_file():
        app_id = json.loads((vdir(cfg, a.name) / "pairs.json").read_text(encoding="utf-8")).get("app")
    cfg = for_app(cfg, app_id)
    {"init": cmd_init, "run": cmd_run, "report": cmd_report, "accept": cmd_accept, "close": cmd_close}[a.cmd](cfg, a)


if __name__ == "__main__":
    main()
