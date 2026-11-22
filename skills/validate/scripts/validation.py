#!/usr/bin/env python3
"""Validate a prototype in the browser and write one report that separates failures from items a human must judge.

Commands:
  validation.py init --app <id> [--from-manifest manifest.js|manifest.json] [--base <capture base URL>] [--blank]
      Write <paths.validation>/<app>/plan.json: screens (id, route, states with a "prepare" script), flows
      (steps: goto, click, fill, select, press, wait, expectVisible, expectHidden, expectText, expectUrl).
      Without --from-manifest the starter plan is read from the app: one screen per page and hash route (href="#/…",
      "#/…" in route tables, router paths), one flow per hash link, control ids as selector hints (--blank: template).
      --from-manifest builds the screens from the capture manifest of annotate/handoff instead: each screen gets the
      steps that reach it (steps of the screens it continues from first), its frames, and the plan url = --base (the URL
      the manifest gotos are relative to). A screen with its own viewport, or with actions (click, fill...) recorded at
      the manifest viewport, runs at that width only; route-only screens run at every width. Never overwrites a plan.
  validation.py run --app <id> [--url <entry>] [--viewports 390,768,1280] [--modes light,dark] [--threshold 0.5] [--min-pixels 100]
                    [--touch-min <px>] [--no-rules]
      Run validate.js (Playwright) on the app, compare screenshots with the baseline (Pillow; a screenshot counts as changed
      when at least --min-pixels pixels or --threshold percent differ), write
      <paths.validation>/<app>/<run>/report.md and report.json. Exit 1 when anything fails.
      Also runs the check commands of the active rules for the validate skill (scripts/rules.py check --app): a failing
      must rule is a Fail, a failing should or note rule needs a human, a skipped check (server down, not applicable) is
      Skipped. --rules-scope app (default): only checks of this app ({app}/{path}) can fail the run; failing project-wide
      checks go to "Outside the scope". --rules-scope all = every check; --rules-scope STY-001,A11Y-002 = those only.
Every command takes --dir <folder>: plan, runs and baseline there instead of <paths.validation>/<app>. Steps without "timeout" wait plan.timeout ms
      (init --from-manifest copies the manifest's timeout; default 8000, the capture.js default).
  validation.py baseline --app <id> [--run <run folder>]
      Accept the screenshots of a run (default: the latest) as the new baseline. Only after a human looked.
  validation.py report --app <id> [--run <run folder>]
      Rebuild report.md from a run's results.json (for example after changing the threshold).

Entry: --url, else plan.json > url, else html apps open <path>/<entry> from the file system; react and vue apps open the
built single file <path>/dist/index.html (run the app's build first).
Touch targets: smallest size on phone widths = --touch-min, else kit.config.json > validate.touchTarget for the app's
platform (apps[].platform, e.g. "desktop": 24 px, WCAG 2.2 target size minimum), else ds.json > touchTarget, else
validate.touchTarget.default (44 px).
  validation.py --selftest   checks of the plan builder and the touch threshold (no browser).
Checks that need axe-core run only when it is installed (npm i -D axe-core); otherwise they are reported as skipped.
Never edits the app, commits, pushes or sends anything.
"""
import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[2]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, t, app as app_cfg  # noqa: E402
import rules as RULES  # noqa: E402  (scripts/rules.py)

FAIL_IMPACT = {"critical", "serious"}
STEP_TIMEOUT = 8000  # ms a step waits when it has no "timeout": the same default as capture.js (a screen it captures must not fail here)


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


OUT_DIR = None   # --dir: plans, runs and baseline in this folder instead of <paths.validation>/<app>


def vdir(cfg, app_id):
    return Path(OUT_DIR) if OUT_DIR else Path(cfg["_root"]) / cfg["paths"]["validation"] / app_id


def shown(cfg, p):
    """A path for messages: relative to the project when it is inside it."""
    try:
        return Path(p).resolve().relative_to(Path(cfg["_root"]).resolve()).as_posix()
    except ValueError:
        return str(p)


def entry_url(cfg, a, app, plan=None):
    if a.url:
        return a.url
    if plan and plan.get("url"):
        return plan["url"]
    base = Path(cfg["_root"]) / app["path"]
    f = base / "dist" / "index.html" if app.get("stack", cfg["stack"]) in ("react", "vue") else base / app.get("entry", "index.html")
    if not f.is_file():
        die("entry not found: %s%s" % (shown(cfg, f),
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


def touch_min(cfg, app):
    """Smallest touch target on phone widths for this app (see the module docstring)."""
    plat = app.get("platform") or ""
    tt = dict((cfg.get("validate") or {}).get("touchTarget") or {})
    ds_tt = (cfg.get("_ds") or {}).get("touchTarget") or {}
    for src in (tt, ds_tt):
        if plat and plat in src:
            return int(src[plat])
    return int(tt.get("default") or ds_tt.get("default") or 44)


ALIAS_STEPS = ("click", "hover", "fill", "type", "waitFor", "wait", "files")


def norm_step(st):
    """Legacy manifest step names (fclick = click inside frame F), as capture.js reads them."""
    for k in list(st):
        m = re.fullmatch(r"([a-z])([a-z][A-Za-z]*)", k)
        if m and m.group(2) in ALIAS_STEPS and k not in ("click", "hover", "fill", "type", "files", "wait"):
            rest = {x: v for x, v in st.items() if x != k}
            step = "waitFor" if m.group(2) == "wait" and isinstance(st[k], str) else m.group(2)
            return dict(rest, **{step: st[k], "in": m.group(1).upper()})
    return st


def read_manifest(path):
    p = Path(path)
    if not p.is_file():
        die("manifest not found: %s" % path)
    if p.suffix == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    r = subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require(process.argv[1])))", str(p.resolve())],
                       capture_output=True, text=True)
    if r.returncode:
        die("cannot read %s with node: %s" % (path, r.stderr.strip()[-300:]))
    return json.loads(r.stdout)


def plan_from_manifest(m, base, att_dir):
    """Plan screens from capture-manifest screens: each one runnable on its own (continued steps are inlined)."""
    screens, by_id = [], {}
    for s in m.get("screens", []):
        steps = [norm_step(x) for x in s.get("steps") or []]
        if s.get("cont") and s.get("flow"):
            prev = next((x for x in reversed(screens) if x["_flow"] == s["flow"]), None)
            if prev:
                steps = prev["_all"] + steps
        e = {"id": s["id"], "name": s.get("name", ""), "route": "", "_flow": s.get("flow"), "_all": steps}
        run = list(steps)
        if run and "goto" in run[0] and len(run[0]) == 1:
            e["route"] = str(run.pop(0)["goto"])
        if run:
            e["steps"] = run
        vp = s.get("viewport") or m.get("viewport")
        acts = [x for x in run if not set(x) & {"wait", "goto", "reset"}]
        if vp and (s.get("viewport") or acts):  # steps were recorded at this width: other widths may not reach the screen
            e["viewports"] = [int(vp["width"])]
        screens.append(e)
        by_id[s["id"]] = e
    for e in screens:
        e.pop("_flow"), e.pop("_all")
    plan = {"_help": PLAN_HELP, "_source": "built from a capture manifest; screens run their steps from the plan url",
            "url": base, "screens": screens, "flows": [], "timeout": int(m.get("timeout") or STEP_TIMEOUT)}
    if m.get("frames"):
        plan["frames"] = m["frames"]
    if att_dir:
        plan["att"] = att_dir
    return plan


HASH_HREF = re.compile(r"""href\s*=\s*["'](#/[^"'\s]*)["']""")
HASH_STR = re.compile(r"""["'`](#/[\w\-/:.]*)["'`]""")
ROUTER_PATH = re.compile(r"""\bpath\s*:\s*["'](/[\w\-/:]*)["']""")
ID_CTRL = re.compile(r"""<(button|a|input|select|textarea)\b[^>]*\bid\s*=\s*["']([A-Za-z][\w-]*)["']""", re.I)
SKIP_PARTS = {"node_modules", "dist", "build", ".git", "shared", "assets"}


def plan_from_app(cfg, app):
    """Starter plan read from the app's files: one screen per page and hash route found (href="#/…", "#/…" strings in
    route tables, router path: '/…' in react/vue sources), one flow per in-page hash link (click it, expect the URL),
    and the ids of the main controls (buttons, links, fields) as selector hints. Never guesses states or data."""
    root = Path(cfg["_root"])
    base = root / app["path"]
    stack = app.get("stack") or cfg.get("stack")
    entry = app.get("entry", "index.html")
    if base.is_file():
        pages = [base]
    elif stack in ("react", "vue"):
        pages = [f for f in sorted((base / "src").rglob("*")) if f.suffix in (".vue", ".tsx", ".jsx", ".ts", ".js")] if (base / "src").is_dir() else []
    else:
        pages = [f for f in sorted(base.rglob("*.html")) if not (set(f.relative_to(base).parts[:-1]) & SKIP_PARTS)
                 and not any(x.startswith(("_", ".")) for x in f.relative_to(base).parts[:-1])]
        pages.sort(key=lambda f: (f.relative_to(base).as_posix() != entry, f.relative_to(base).as_posix()))
    screens, flows, seen, ids = [], [], set(), []
    for f in pages:
        txt = f.read_text(encoding="utf-8", errors="replace")
        rel = "" if stack in ("react", "vue") or base.is_file() else f.relative_to(base).as_posix()
        page = "" if rel in ("", entry) else rel
        routes = HASH_HREF.findall(txt) + HASH_STR.findall(txt) + ["#" + x for x in ROUTER_PATH.findall(txt)]
        if page or not screens:
            routes = [""] + routes
        for r in routes:
            r = "" if r == "#/" else r
            key = page + r
            if key in seen or ":" in r:
                continue
            seen.add(key)
            screens.append({"id": "S%02d" % (len(screens) + 1), "name": (page or entry) + (r or ""), "route": key, "states": []})
        for h in dict.fromkeys(HASH_HREF.findall(txt)):
            if len(flows) < 8 and h != "#/":
                flows.append({"name": "Open %s%s" % (page, h), "start": page, "viewport": 1280,
                              "steps": [{"click": "a[href='%s']" % h}, {"expectUrl": h}]})
        ids += ["#" + m.group(2) for m in ID_CTRL.finditer(txt)]
    plan = {"_help": PLAN_HELP, "_source": "starter plan read from the app files: check every route, add the states (empty, "
                                           "error, loading) and the flows the work needs",
            "screens": screens[:60], "flows": flows}
    if ids:
        plan["_selectors"] = list(dict.fromkeys(ids))[:40]
    return plan


def cmd_init(cfg, a):
    app_cfg(cfg, a.app)
    d = vdir(cfg, a.app)
    f = d / "plan.json"
    if f.exists():
        die("plan exists, nothing written: %s" % shown(cfg, f))
    if a.from_manifest:
        m = read_manifest(a.from_manifest)
        if not m.get("screens"):
            die("the manifest has no screens[]")
        mp = Path(a.from_manifest).resolve()
        plan = plan_from_manifest(m, a.base or "http://localhost:8791/", str(mp.parent / (m.get("att") or "att")))
        d.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Wrote %s: %d screens from %s. Serve the prototype at %s (as for capture), or pass run --url. Add states and flows."
              % (shown(cfg, f), len(plan["screens"]), a.from_manifest, plan["url"]))
        return
    d.mkdir(parents=True, exist_ok=True)
    app = app_cfg(cfg, a.app)
    plan = plan_from_app(cfg, app) if not a.blank else None
    if plan and plan["screens"]:
        f.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Wrote %s: %d screens and %d flows read from the app (%d selector hints). Check the routes, add states and flows."
              % (shown(cfg, f), len(plan["screens"]), len(plan["flows"]), len(plan.get("_selectors") or [])))
        return
    plan = {
        "_help": PLAN_HELP,
        "screens": [{"id": "S01", "name": "Home", "route": "", "states": [
            {"name": "empty", "prepare": "localStorage.clear(); location.reload();"}]}],
        "flows": [{"name": "Open settings", "start": "", "viewport": 1280,
                   "steps": [{"click": "a[href='#/settings']"}, {"expectUrl": "#/settings"}]}],
    }
    f.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wrote %s. Replace the example screens, states and flows with the app's own." % shown(cfg, f))


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
    outside = []
    for x in res.get("rules") or []:   # rules registry: a failing must rule in scope fails, others need a human
        where = "%s%s" % (x["id"], (" · " + x["app"]) if x.get("app") else "")
        if x.get("status") == "skipped":
            skipped.append(("rule", where, "%s: %s" % (x["title"], x.get("reason") or "skipped")))
        elif not x["ok"]:
            row = ("rule", where, "%s (%s): exit %d%s" % (x["title"], x["severity"], x["exit"],
                                                           (" · " + " / ".join(x["summary"])) if x["summary"] else ""))
            if x.get("inScope") is False:
                outside.append(row)
            else:
                (fail if x["severity"] == "must" else review).append(row)
    res["_outside"] = outside
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
    outside = res.pop("_outside", [])
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
                              (T("skippedTitle"), skipped, "")) + (((T("outsideTitle"), outside, T("outsideNote")),) if outside else ()):
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
    report = {"app": app_id, "run": run.name, "fail": fail, "review": review, "skipped": skipped, "outsideScope": outside, "diffs": diffs}
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


def rules_in_scope(results, scope="app"):
    """Mark each rule check result inScope: app = checks that ran for this app ({app}/{path} in the command);
    all = every check; a comma list = only those rule ids. A failing check outside the scope is reported, never a Fail."""
    ids = None if scope in ("app", "all") else {x.strip().upper() for x in scope.split(",") if x.strip()}
    for x in results:
        x["inScope"] = (x["id"].upper() in ids) if ids is not None else (scope == "all" or bool(x.get("perApp")))
    return results


def cmd_run(cfg, a):
    app = app_cfg(cfg, a.app)
    d = vdir(cfg, a.app)
    plan = d / "plan.json"
    url = entry_url(cfg, a, app, json.loads(plan.read_text(encoding="utf-8")) if plan.is_file() else None)
    if not plan.is_file():
        d.mkdir(parents=True, exist_ok=True)
        plan.write_text(json.dumps({"screens": [{"id": "S01", "name": "Entry", "route": ""}], "flows": []}, indent=2) + "\n", encoding="utf-8")
        print("No plan.json yet: checking the entry page only. Run init and list screens, states and flows for a full check.")
    attr, modes = mode_setup(cfg)
    run = d / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run.mkdir(parents=True)
    cmd = ["node", str(HERE / "validate.js"), "--url", url, "--plan", str(plan), "--out", str(run),
           "--viewports", a.viewports, "--modes", a.modes or ",".join(modes), "--mode-attr", attr, "--project", cfg["_root"],
           "--touch-min", str(a.touch_min or touch_min(cfg, app))]
    p = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(p.stdout)
    if p.returncode != 0 or not (run / "results.json").is_file():
        sys.stdout.write(p.stderr[-2000:])
        die("browser run failed")
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    if not a.no_rules:
        res["rules"] = rules_in_scope(RULES.run_checks(cfg, app=a.app, skill="validate"), a.rules_scope)
        (run / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    diffs = compare_all(cfg, a.app, run, a.threshold, a.min_pixels)
    fail, review, skipped = write_report(cfg, a.app, run, res, diffs)
    print("Report: %s · %d fail · %d to review · %d skipped" % (
        shown(cfg, run / "report.md"), len(fail), len(review), len(skipped)))
    sys.exit(1 if fail else 0)


def cmd_report(cfg, a):
    run = latest_run(cfg, a.app, a.run)
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    fail, review, skipped = write_report(cfg, a.app, run, res, compare_all(cfg, a.app, run, a.threshold, a.min_pixels))
    print("Report: %s · %d fail · %d to review · %d skipped" % (shown(cfg, run / "report.md"), len(fail), len(review), len(skipped)))


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


def selftest():
    m = {"frames": {"F": "#d iframe"}, "screens": [
        {"id": "S01", "flow": "f1", "steps": [{"goto": "apps/a/index.html#/"}, {"wait": 300}]},
        {"id": "S02", "flow": "f1", "cont": 1, "steps": [{"fclick": "#x"}], "viewport": {"width": 1280, "height": 900}},
        {"id": "S03", "steps": [{"goto": "apps/a/index.html#/b"}]}]}
    p = plan_from_manifest(m, "http://localhost:9/", "")
    s1, s2, s3 = p["screens"]
    assert s1["route"] == "apps/a/index.html#/" and s1["steps"] == [{"wait": 300}], s1
    assert s2["route"] == "apps/a/index.html#/" and s2["steps"][-1] == {"click": "#x", "in": "F"}, s2
    assert s2["viewports"] == [1280] and "steps" not in s3 and "viewports" not in s1 and p["frames"]["F"] and p["url"] == "http://localhost:9/"
    assert p["timeout"] == STEP_TIMEOUT and plan_from_manifest(dict(m, timeout=12000), "", "")["timeout"] == 12000, "step timeout"
    res = {"items": [], "flows": [], "axe": {"available": True}, "rules": [
        {"id": "STY-001", "title": "t", "severity": "must", "app": "a", "exit": 1, "ok": False, "summary": ["bad"]},
        {"id": "A11Y-001", "title": "t", "severity": "should", "app": "a", "exit": 1, "ok": False, "summary": []},
        {"id": "X-001", "title": "t", "severity": "must", "app": "a", "exit": 0, "ok": True, "summary": []}]}
    f, r, _ = classify(res, {})
    assert [x[1] for x in f] == ["STY-001 · a"] and [x[1] for x in r] == ["A11Y-001 · a"], (f, r)
    # rules scope: a project-wide check outside the scope never fails the run; skipped checks are listed as skipped
    res["rules"] = rules_in_scope([dict(res["rules"][0], perApp=False), dict(res["rules"][1], perApp=True),
                                   {"id": "A11Y-002", "title": "t", "severity": "should", "app": "a", "exit": None, "ok": True,
                                    "status": "skipped", "reason": "needs a server", "summary": [], "perApp": True}])
    f, r, sk = classify(res, {})
    assert not f and [x[1] for x in r] == ["A11Y-001 · a"] and [x[1] for x in res["_outside"]] == ["STY-001 · a"], (f, r, res["_outside"])
    assert any(x[1] == "A11Y-002 · a" and "needs a server" in x[2] for x in sk), sk
    assert rules_in_scope([{"id": "STY-001"}], "sty-001")[0]["inScope"] and not rules_in_scope([{"id": "X-1"}], "STY-001")[0]["inScope"]
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="validation-selftest-"))
    (d / "apps" / "w" / "notes").mkdir(parents=True)
    (d / "apps" / "w" / "index.html").write_text('<a href="#/settings">S</a><button id="saveBtn">x</button><script>const R={"#/":1,"#/list":2};</script>')
    (d / "apps" / "w" / "notes" / "index.html").write_text('<a href="#/n/1">n</a>')
    sp = plan_from_app({"_root": str(d), "stack": "html"}, {"path": "apps/w"})
    assert [x["route"] for x in sp["screens"]] == ["", "#/settings", "#/list", "notes/index.html", "notes/index.html#/n/1"], sp["screens"]
    assert sp["flows"][0]["steps"][0] == {"click": "a[href='#/settings']"} and sp["_selectors"] == ["#saveBtn"], sp
    cfg = {"validate": {"touchTarget": {"default": 44, "desktop": 24}}, "_ds": {"touchTarget": {"tablet": 40}}}
    assert touch_min(cfg, {}) == 44 and touch_min(cfg, {"platform": "desktop"}) == 24 and touch_min(cfg, {"platform": "tablet"}) == 40
    print("validation.py selftest OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    ap = argparse.ArgumentParser(description="Validate a prototype in the browser.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="write a validation plan"); p.add_argument("--app", required=True)
    p.add_argument("--from-manifest", help="capture manifest (manifest.js or .json) to build the screens from")
    p.add_argument("--base", help="URL the manifest gotos are relative to (default http://localhost:8791/)")
    p.add_argument("--blank", action="store_true", help="write the example template instead of reading the app")
    p = sub.add_parser("run", help="run the checks and write the report")
    p.add_argument("--app", required=True); p.add_argument("--url"); p.add_argument("--viewports", default="390,768,1280")
    p.add_argument("--modes"); p.add_argument("--threshold", type=float, default=0.5, help="percent of pixels")
    p.add_argument("--min-pixels", type=int, default=100, help="changed pixels that count as a visual change")
    p.add_argument("--touch-min", type=int, help="smallest touch target in px on phone widths (default: by app platform)")
    p.add_argument("--no-rules", action="store_true", help="do not run the check commands of the rules registry")
    p = sub.add_parser("baseline", help="accept a run's screenshots as baseline"); p.add_argument("--app", required=True); p.add_argument("--run")
    p = sub.add_parser("report", help="rebuild the report of a run")
    p.add_argument("--app", required=True); p.add_argument("--run"); p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--min-pixels", type=int, default=100)
    for sp in sub.choices.values():
        sp.add_argument("--dir", help="folder for the plan, runs and baseline (default <paths.validation>/<app>)")
    p = sub.choices["run"]
    p.add_argument("--rules-scope", default="app",
                   help="rule checks that can fail the run: app (default: checks of this app, i.e. with {app}/{path}; "
                        "project-wide checks are reported as outside the scope), all, or a comma list of rule ids")
    a = ap.parse_args()
    global OUT_DIR
    OUT_DIR = a.dir
    cfg = load(app=a.app)  # the app's own DS profile (apps[].ds): theming attributes, touch targets
    {"init": cmd_init, "run": cmd_run, "baseline": cmd_baseline, "report": cmd_report}[a.cmd](cfg, a)


if __name__ == "__main__":
    main()
