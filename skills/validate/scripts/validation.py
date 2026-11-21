#!/usr/bin/env python3
"""Validate a prototype in the browser and write one report that separates failures from items a human must judge.

Commands:
  validation.py init --app <id>
      Write <paths.validation>/<app>/plan.json: screens (id, route, states with a "prepare" script), flows
      (steps: goto, click, fill, select, press, wait, expectVisible, expectHidden, expectText, expectUrl).
      Never overwrites an existing plan.
  validation.py run --app <id> [--url <entry>] [--viewports 390,768,1280] [--modes light,dark] [--threshold 0.5] [--min-pixels 100]
      Run validate.js (Playwright) on the app, compare screenshots with the baseline (Pillow; a screenshot counts as changed
      when at least --min-pixels pixels or --threshold percent differ), write
      <paths.validation>/<app>/<run>/report.md and report.json. Exit 1 when anything fails.
  validation.py baseline --app <id> [--run <run folder>]
      Accept the screenshots of a run (default: the latest) as the new baseline. Only after a human looked.
  validation.py report --app <id> [--run <run folder>]
      Rebuild report.md from a run's results.json (for example after changing the threshold).

Entry: html apps open <path>/<entry> from the file system; react and vue apps open the built single file
<path>/dist/index.html (run the app's build first) unless --url is given.
Checks that need axe-core run only when it is installed (npm i -D axe-core); otherwise they are reported as skipped.
Never edits the app, commits, pushes or sends anything.
"""
import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[2]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, t, app as app_cfg  # noqa: E402

FAIL_IMPACT = {"critical", "serious"}


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def vdir(cfg, app_id):
    return Path(cfg["_root"]) / cfg["paths"]["validation"] / app_id


def entry_url(cfg, a, app):
    if a.url:
        return a.url
    base = Path(cfg["_root"]) / app["path"]
    f = base / "dist" / "index.html" if app.get("stack", cfg["stack"]) in ("react", "vue") else base / app.get("entry", "index.html")
    if not f.is_file():
        die("entry not found: %s%s" % (f.relative_to(cfg["_root"]),
                                     " (run the app build first)" if "dist" in f.parts else ""))
    return f.resolve().as_uri()


def mode_setup(cfg):
    mode = ((cfg.get("_ds") or {}).get("theming") or {}).get("mode") or {}
    values = [v for v in (mode.get("values") or []) if v in ("light", "dark")]
    return (mode.get("attr") or "data-mode"), (values or ["light"])


# ---------- init ----------

PLAN_HELP = {
    "screens": "One entry per screen (S-ids from the plan or the spec). route: '' for the entry, '#/settings' for hash routes. "
               "states: extra states opened by a 'prepare' script run in the page (set localStorage, click, add a class); "
               "list empty, loading, error and success states the screen has.",
    "flows": "Flows a user goes through. Steps: {goto}, {click: selector}, {fill: [selector, text]}, {select: [selector, value]}, "
             "{press: key}, {wait: ms}, {expectVisible: selector}, {expectHidden: selector}, {expectText: [selector, text]}, {expectUrl: part}.",
}


def cmd_init(cfg, a):
    app_cfg(cfg, a.app)
    d = vdir(cfg, a.app)
    f = d / "plan.json"
    if f.exists():
        die("plan exists, nothing written: %s" % f.relative_to(cfg["_root"]))
    d.mkdir(parents=True, exist_ok=True)
    plan = {
        "_help": PLAN_HELP,
        "screens": [{"id": "S01", "name": "Home", "route": "", "states": [
            {"name": "empty", "prepare": "localStorage.clear(); location.reload();"}]}],
        "flows": [{"name": "Open settings", "start": "", "viewport": 1280,
                   "steps": [{"click": "a[href='#/settings']"}, {"expectUrl": "#/settings"}]}],
    }
    f.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wrote %s. Replace the example screens, states and flows with the app's own." % f.relative_to(cfg["_root"]))


# ---------- diff ----------

def diff(base, new, out_png, threshold, min_px):
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return {"status": "skipped", "why": "Pillow not installed"}
    a, b = Image.open(base).convert("RGB"), Image.open(new).convert("RGB")
    if a.size != b.size:
        return {"status": "changed", "why": "size %dx%d → %dx%d" % (a.size + b.size), "pct": None}
    d = ImageChops.difference(a, b)
    mask = d.convert("L").point(lambda v: 255 if v > 24 else 0)
    changed = mask.histogram()[255]
    pct = 100.0 * changed / (a.size[0] * a.size[1])
    if changed >= min_px or pct > threshold:
        hi = Image.composite(Image.new("RGB", b.size, (255, 0, 80)), b.point(lambda v: int(v * 0.35 + 165)), mask)
        hi.save(out_png)
        return {"status": "changed", "pct": round(pct, 2), "px": changed, "diff": out_png.name}
    return {"status": "same", "pct": round(pct, 3), "px": changed}


# ---------- classify + report ----------

def classify(res, diffs):
    fail, review, skipped = [], [], []
    for it in res["items"]:
        where = "%s · %s · %spx · %s" % (it["screen"], it["state"], it["vp"], it["mode"])
        if it.get("fatal"):
            fail.append(("open", where, it["fatal"]))
            continue
        for e in it.get("errors") or []:
            fail.append(("console", where, e))
        if it.get("overflow"):
            o = it["overflow"]
            fail.append(("overflow", where, "page %dpx wide in a %dpx window: %s" % (o["scrollWidth"], o["width"], "; ".join(o["elements"]) or "?")))
        for v in it.get("axe") or []:
            (fail if v["impact"] in FAIL_IMPACT else review).append(
                ("a11y", where, "%s (%s, %d node(s)): %s %s" % (v["id"], v["impact"], v["nodes"], v["help"], v["target"])))
        if it.get("touch"):
            review.append(("touch", where, "; ".join(it["touch"])))
        if it.get("clipped"):
            review.append(("clipped", where, "; ".join(it["clipped"])))
        if it.get("focus") and it["focus"]["missing"]:
            review.append(("focus", where, "%d of %d tab stops show no outline or ring: %s" % (
                len(it["focus"]["missing"]), it["focus"]["tabStops"], "; ".join(it["focus"]["missing"]))))
        dfx = diffs.get(it.get("shot"))
        if dfx and dfx["status"] == "changed":
            review.append(("visual", where, ("%d px changed (%.2f%%)" % (dfx["px"], dfx["pct"]) if dfx.get("pct") is not None else dfx["why"])
                           + (" · diffs/%s" % dfx["diff"] if dfx.get("diff") else "")))
    for f in res.get("flows") or []:
        if not f["ok"]:
            detail = ("step %s: %s" % (f["failedStep"], f["error"])) if f.get("failedStep") else (f.get("error") or "; ".join(f.get("errors") or []))
            fail.append(("flow", f["name"], detail))
    if not res["axe"]["available"]:
        skipped.append(("a11y", "—", "axe-core not installed: npm i -D axe-core in the project, then run again"))
    nobase = [s for s, dfx in diffs.items() if dfx["status"] == "new"]
    if nobase:
        skipped.append(("visual", "—", "no baseline for %d screenshot(s); review them, then run baseline to accept" % len(nobase)))
    return fail, review, skipped


def write_report(cfg, app_id, run, res, diffs):
    fail, review, skipped = classify(res, diffs)
    T = lambda k, **kw: t(cfg, "validate." + k, **kw)
    passed = sum(1 for it in res["items"] if not it.get("fatal") and not it.get("errors") and not it.get("overflow")
                 and not any(v["impact"] in FAIL_IMPACT for v in it.get("axe") or []))
    lines = ["# " + T("title", app=app_id), "",
             T("meta", started=res["started"][:19].replace("T", " "), url=res["url"], viewports=", ".join(map(str, res["viewports"])),
               modes=", ".join(res["modes"]), axe=res["axe"]["version"] or T("notInstalled")), "",
             "| %s | %s | %s | %s | %s |" % (T("views"), T("flows"), T("fail"), T("review"), T("skipped")),
             "|---|---|---|---|---|",
             "| %d (%d %s) | %d (%d %s) | %d | %d | %d |" % (len(res["items"]), passed, T("clean"), len(res["flows"]),
                                                         sum(1 for f in res["flows"] if f["ok"]), T("ok"), len(fail), len(review), len(skipped)), ""]
    for title, rows, note in ((T("failTitle"), fail, T("failNote")), (T("reviewTitle"), review, T("reviewNote")),
                              (T("skippedTitle"), skipped, "")):
        lines += ["## %s (%d)" % (title, len(rows)), ""]
        if note:
            lines += [note, ""]
        if rows:
            lines += ["| %s | %s | %s |" % (T("check"), T("where"), T("detail")), "|---|---|---|"]
            lines += ["| %s | %s | %s |" % (T("kind." + k), w, d.replace("|", "/")) for k, w, d in rows]
        else:
            lines.append("—")
        lines.append("")
    lines += ["## " + T("shotsTitle"), "", T("shotsNote"), ""]
    report = {"app": app_id, "run": run.name, "fail": fail, "review": review, "skipped": skipped, "diffs": diffs}
    (run / "report.md").write_text("\n".join(lines), encoding="utf-8")
    (run / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return fail, review, skipped


def compare_all(cfg, app_id, run, threshold, min_px=100):
    base = vdir(cfg, app_id) / "baseline"
    (run / "diffs").mkdir(exist_ok=True)
    diffs = {}
    for shot in sorted((run / "shots").glob("*.png")):
        b = base / shot.name
        diffs[shot.name] = diff(b, shot, run / "diffs" / shot.name, threshold, min_px) if b.is_file() else {"status": "new"}
    return diffs


def latest_run(cfg, app_id, name=None):
    d = vdir(cfg, app_id)
    if name:
        r = d / name
        if not (r / "results.json").is_file():
            die("run not found: %s" % r)
        return r
    runs = sorted(p for p in d.glob("2*") if (p / "results.json").is_file()) if d.is_dir() else []
    if not runs:
        die("no runs for %s yet (run first)" % app_id)
    return runs[-1]


def cmd_run(cfg, a):
    app = app_cfg(cfg, a.app)
    url = entry_url(cfg, a, app)
    d = vdir(cfg, a.app)
    plan = d / "plan.json"
    if not plan.is_file():
        d.mkdir(parents=True, exist_ok=True)
        plan.write_text(json.dumps({"screens": [{"id": "S01", "name": "Entry", "route": ""}], "flows": []}, indent=2) + "\n", encoding="utf-8")
        print("No plan.json yet: checking the entry page only. Run init and list screens, states and flows for a full check.")
    attr, modes = mode_setup(cfg)
    run = d / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run.mkdir(parents=True)
    cmd = ["node", str(HERE / "validate.js"), "--url", url, "--plan", str(plan), "--out", str(run),
           "--viewports", a.viewports, "--modes", a.modes or ",".join(modes), "--mode-attr", attr, "--project", cfg["_root"]]
    p = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(p.stdout)
    if p.returncode != 0 or not (run / "results.json").is_file():
        sys.stdout.write(p.stderr[-2000:])
        die("browser run failed")
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    diffs = compare_all(cfg, a.app, run, a.threshold, a.min_pixels)
    fail, review, skipped = write_report(cfg, a.app, run, res, diffs)
    print("Report: %s · %d fail · %d to review · %d skipped" % (
        (run / "report.md").relative_to(cfg["_root"]), len(fail), len(review), len(skipped)))
    sys.exit(1 if fail else 0)


def cmd_report(cfg, a):
    run = latest_run(cfg, a.app, a.run)
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    fail, review, skipped = write_report(cfg, a.app, run, res, compare_all(cfg, a.app, run, a.threshold, a.min_pixels))
    print("Report: %s · %d fail · %d to review · %d skipped" % ((run / "report.md").relative_to(cfg["_root"]), len(fail), len(review), len(skipped)))


def cmd_baseline(cfg, a):
    run = latest_run(cfg, a.app, a.run)
    base = vdir(cfg, a.app) / "baseline"
    base.mkdir(parents=True, exist_ok=True)
    n = 0
    for shot in (run / "shots").glob("*.png"):
        shutil.copy2(shot, base / shot.name)
        n += 1
    (base / "SOURCE.txt").write_text("Accepted from run %s on %s\n" % (run.name, dt.date.today().isoformat()), encoding="utf-8")
    print("Baseline: %d screenshot(s) from %s" % (n, run.name))


def main():
    ap = argparse.ArgumentParser(description="Validate a prototype in the browser.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="write a validation plan"); p.add_argument("--app", required=True)
    p = sub.add_parser("run", help="run the checks and write the report")
    p.add_argument("--app", required=True); p.add_argument("--url"); p.add_argument("--viewports", default="390,768,1280")
    p.add_argument("--modes"); p.add_argument("--threshold", type=float, default=0.5, help="percent of pixels")
    p.add_argument("--min-pixels", type=int, default=100, help="changed pixels that count as a visual change")
    p = sub.add_parser("baseline", help="accept a run's screenshots as baseline"); p.add_argument("--app", required=True); p.add_argument("--run")
    p = sub.add_parser("report", help="rebuild the report of a run")
    p.add_argument("--app", required=True); p.add_argument("--run"); p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--min-pixels", type=int, default=100)
    a = ap.parse_args()
    cfg = load()
    {"init": cmd_init, "run": cmd_run, "baseline": cmd_baseline, "report": cmd_report}[a.cmd](cfg, a)


if __name__ == "__main__":
    main()
