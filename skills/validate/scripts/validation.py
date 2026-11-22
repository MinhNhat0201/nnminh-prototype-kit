#!/usr/bin/env python3
"""Validate a prototype in the browser and write one report that separates failures from items a human must judge.

Commands:
  validation.py init --app <id> [--from-manifest manifest.js|manifest.json] [--base <capture base URL>] [--blank]
                     [--page <file>] [--routes '#/,#/n/1'] [--url <URL the page is served at>]
      Write <paths.validation>/<app>/plan.json: screens (id, route, states with a "prepare" script), flows
      (steps: goto, reload, click, fill, select, press, wait, expectVisible, expectHidden, expectText, expectUrl).
      --page: read only this file (relative to the app folder, else the project; a built bundle such as dist/index.html
      works too); --routes: use these hash routes instead of the ones found; --url: plan url (the page served over HTTP),
      routes are then hash-only. Routes with a parameter (#/n/:id) are listed under _paramRoutes to fill in by hand.
      Without --from-manifest the starter plan is read from the app: one screen per page and hash route (href="#/…",
      "#/…" in route tables, router paths), one flow per hash link, control ids as selector hints (--blank: template).
      --from-manifest builds the screens from the capture manifest of annotate/handoff instead: each screen gets the
      steps that reach it (steps of the screens it continues from first), its frames, and the plan url = --base (the URL
      the manifest gotos are relative to). A screen with its own viewport, or with actions (click, fill...) recorded at
      the manifest viewport, runs at that width only; route-only screens run at every width. Never overwrites a plan.
  validation.py run --app <id> [--url <entry>] [--viewports 390,768,1280] [--modes light,dark] [--threshold 0.5] [--min-pixels 100]
                    [--touch-min <px>] [--no-rules] [--axe <axe.min.js|folder>] [--waivers <file>] [--compare <run|report.json|none>]
      Run validate.js (Playwright) on the app, compare screenshots with the baseline (Pillow; a screenshot counts as changed
      when at least --min-pixels pixels or --threshold percent differ), write
      <paths.validation>/<app>/<run>/report.md and report.json. Exit 1 when anything fails.
      Also runs the check commands of the active rules for the validate skill (scripts/rules.py check --app): a failing
      must rule is a Fail, a failing should or note rule needs a human, a skipped check (server down, not applicable) is
      Skipped. --rules-scope app (default): only checks of this app ({app}/{path}) can fail the run; failing project-wide
      checks go to "Outside the scope". --rules-scope all = every check; --rules-scope STY-001,A11Y-002 = those only.
      Waivers (--waivers, default <dir>/waivers.json): findings matched by check/id + selector (+ screen) with a required
      reason go to "Known / waived", never Fail. --compare (alias --baseline; default: the previous run) marks each Fail and
      Needs-a-human row new or carried over and counts the ones no longer found. axe-core: --axe, else env KIT_AXE_PATH,
      else kit.config.json > validate.axePath, else node_modules of the project or the kit.
      States: plan.states (every screen) and screen states may be named: "<ds.json theming key>=<value>" ("brand=ocean")
      or "text=200%". Theme values and dark mode go through kit.config.json > validate.setTheme (JS body with key, value)
      when set, else the ds.json > theming.<key>.attr attribute on <html>.
Every command takes --dir <folder>: plan, runs and baseline there instead of <paths.validation>/<app>. Steps without "timeout" wait plan.timeout ms
      (init --from-manifest copies the manifest's timeout; default 8000, the capture.js default).
  validation.py baseline --app <id> [--run <run folder>]
      Accept the screenshots of a run (default: the latest) as the new baseline. Only after a human looked.
  validation.py report --app <id> [--run <run folder>] [--waivers <file>] [--compare <run|report.json|none>]
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
import contextlib
import datetime as dt
import io
import json
import os
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
    th = (cfg.get("_ds") or {}).get("theming") or {}
    mode = th.get("mode") or {}
    values = [v for v in (mode.get("values") or []) if v in ("light", "dark")]
    attrs = {k: v["attr"] for k, v in th.items() if isinstance(v, dict) and v.get("attr")}
    return (mode.get("attr") or "data-mode"), (values or ["light"]), attrs


def state_hints(cfg):
    """Named states a plan can list: one non-default value per theming key (not mode: modes run anyway), and text=200%."""
    th = (cfg.get("_ds") or {}).get("theming") or {}
    hints = []
    for k, v in th.items():
        if k == "mode" or not isinstance(v, dict) or not v.get("attr"):
            continue
        other = [x for x in v.get("values") or [] if x != v.get("default") and x not in ("auto", "default")]
        if other:
            hints.append("%s=%s" % (k, other[0]))
    return hints + ["text=200%"]


# ---------- init ----------

PLAN_HELP = {
    "screens": "One entry per screen (S-ids from the plan or the spec). route: '' for the entry, '#/settings' for hash routes. "
               "states: extra states opened by a 'prepare' script run in the page (set localStorage, click, add a class); "
               "list empty, loading, error and success states the screen has.",
    "flows": "Flows a user goes through. Steps: {goto} (add reload: true when only the hash changes), {reload: true}, {click: selector}, "
             "{fill: [selector, text]}, {select: [selector, value]}, {press: key}, {wait: ms}, {expectVisible: selector}, "
             "{expectHidden: selector}, {expectText: [selector, text]}, {expectUrl: part}.",
    "namedStates": "A state may be a name: '<ds.json theming key>=<value>' (e.g. 'brand=ocean') or 'text=200%'. "
                   "plan.states are added to every screen; _stateHints lists the ones this DS offers.",
    "axe": "plan.axe or screen.axe {include: [selector], exclude: [selector]} limits axe to part of the page. Findings that are "
           "known or outside the work go into waivers.json (check, id, selector, screen, reason), not out of the plan.",
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
        acts = [x for x in run if not set(x) & {"wait", "goto", "reset", "reload"}]
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


def find_page(cfg, app, page):
    """--page: a file relative to the app folder, else to the project root, else as given."""
    for c in (Path(cfg["_root"]) / app["path"] / page, Path(cfg["_root"]) / page, Path(page)):
        if c.is_file():
            return c
    die("page not found: %s (relative to the app folder %s or the project)" % (page, app["path"]))


def plan_from_app(cfg, app, page=None, routes=None, url=None):
    """Starter plan read from the app's files: one screen per page and hash route found (href="#/…", "#/…" strings in
    route tables, router path: '/…' in react/vue sources or a built bundle), one flow per in-page hash link (click it,
    expect the URL), and the ids of the main controls (buttons, links, fields) as selector hints. Never guesses states
    or data. page = only this file; routes = these hash routes instead of the ones found; url = the plan url (the page
    as served), so routes are hash-only."""
    root = Path(cfg["_root"])
    base = root / app["path"]
    stack = app.get("stack") or cfg.get("stack")
    entry = app.get("entry", "index.html")
    one = find_page(cfg, app, page) if page else None
    if one is not None:
        pages = [one]
    elif base.is_file():
        pages = [base]
    elif stack in ("react", "vue"):
        pages = [f for f in sorted((base / "src").rglob("*")) if f.suffix in (".vue", ".tsx", ".jsx", ".ts", ".js")] if (base / "src").is_dir() else []
        pages += [f for f in [base / "dist" / "index.html"] if f.is_file()]   # routes only present in the built bundle
    else:
        pages = [f for f in sorted(base.rglob("*.html")) if not (set(f.relative_to(base).parts[:-1]) & SKIP_PARTS)
                 and not any(x.startswith(("_", ".")) for x in f.relative_to(base).parts[:-1])]
        pages.sort(key=lambda f: (f.relative_to(base).as_posix() != entry, f.relative_to(base).as_posix()))
    screens, flows, seen, ids, params = [], [], set(), [], []
    for f in pages:
        txt = f.read_text(encoding="utf-8", errors="replace")
        if one is not None:   # one page: hash-only routes when it is served at url, else relative to the entry
            rel = "" if url or base.is_file() else Path(os.path.relpath(f, base if base.is_dir() else base.parent)).as_posix()
        else:
            rel = "" if stack in ("react", "vue") or base.is_file() else f.relative_to(base).as_posix()
        page = "" if rel in ("", entry) else rel
        found = HASH_HREF.findall(txt) + HASH_STR.findall(txt) + ["#" + x for x in ROUTER_PATH.findall(txt)]
        params += [r for r in found if ":" in r]
        found = [x if x.startswith("#") else "#" + x for x in routes] if routes is not None else found
        if page or not screens:
            found = [""] + found
        for r in found:
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
    if params:
        plan["_paramRoutes"] = list(dict.fromkeys(params))[:20]
    if url:
        plan["url"] = url
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
    plan = plan_from_app(cfg, app, a.page, [x.strip() for x in a.routes.split(",") if x.strip()] if a.routes else None, a.url) \
        if not a.blank else None
    if plan:
        plan["_stateHints"] = state_hints(cfg)
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


# ---------- waivers + compare ----------

KINDS = ("open", "console", "overflow", "a11y", "touch", "clipped", "focus", "visual", "rule", "flow")


def load_waivers(path):
    """waivers.json: a list (or {"waivers": [...]}) of {check, id, selector | match, screen, reason}. reason is required,
    and check or id: a waiver that names nothing would hide every finding."""
    p = Path(path) if path else None
    if not p or not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        die("waivers file is not JSON: %s (%s)" % (p, e))
    ws = data.get("waivers", []) if isinstance(data, dict) else data
    for i, w in enumerate(ws if isinstance(ws, list) else [None]):
        if not isinstance(w, dict) or not str(w.get("reason") or "").strip():
            die("waiver %d in %s needs a reason" % (i + 1, p))
        if not (w.get("check") or w.get("id")):
            die("waiver %d in %s needs check or id (one of %s, or an axe / rule id)" % (i + 1, p, ", ".join(KINDS)))
        if w.get("check") and w["check"] not in KINDS:
            die("waiver %d in %s: check must be one of %s" % (i + 1, p, ", ".join(KINDS)))
    return ws


def waiver_for(ws, kind, where, rid="", texts=()):
    """The first waiver that matches a finding: same check, same id (axe or rule id), the screen (id at the start of
    where), and its selector or match found in one of texts (a target, a waiver selector the node is inside, an element)."""
    for w in ws:
        if w.get("check") and w["check"] != kind:
            continue
        if w.get("id") and str(w["id"]).lower() != str(rid or "").lower():
            continue
        if w.get("screen") and not (where == w["screen"] or where.startswith(w["screen"] + " ")):
            continue
        sel = w.get("selector") or w.get("match")
        if sel and not any(sel == x or sel in x for x in texts):
            continue
        return w
    return None


def contrast(n):
    exp = re.sub(r":1$", "", str(n.get("expected") or "?"))   # axe gives "4.5:1"
    return (" %s:1 (needs %s:1), %s on %s" % (n["ratio"], exp, n.get("fg") or "?", n.get("bg") or "?")) if n.get("ratio") else ""


def row_key(r):
    return r[3] if len(r) > 3 else "|".join(map(str, r[:3]))


def compare_keys(prev, fail, review):
    """prev = an earlier report.json: which rows are new, which carried over, how many keys are gone."""
    old = {row_key(r) for r in (prev.get("fail") or []) + (prev.get("review") or [])}
    now = {row_key(r) for r in fail + review}
    return {"run": prev.get("run"), "new": sorted(now - old), "carried": sorted(now & old), "fixed": sorted(old - now)}


# ---------- classify + report ----------

def classify(res, diffs, waivers=()):
    fail, review, skipped, known = [], [], [], []

    def add(bucket, kind, where, detail, key, rid="", texts=()):
        w = waiver_for(waivers, kind, where, rid, texts) if waivers else None
        if w:
            known.append((kind, where, detail + " · " + w["reason"], key))
        else:
            bucket.append((kind, where, detail, key))

    def split(kind, where, elems, key, fmt):   # list findings: waive element by element
        keep = []
        for e in elems:
            w = waiver_for(waivers, kind, where, "", (e,)) if waivers else None
            if w:
                known.append((kind, where, e + " · " + w["reason"], key))
            else:
                keep.append(e)
        if keep:
            review.append((kind, where, fmt(keep), key))

    for it in res["items"]:
        where = "%s · %s · %spx · %s" % (it["screen"], it["state"], it["vp"], it["mode"])
        if it.get("fatal"):
            add(fail, "open", where, it["fatal"], "open|" + where)
            continue
        for e in it.get("errors") or []:
            add(fail, "console", where, e, "console|%s|%s" % (where, re.sub(r"\d+", "#", e)), texts=(e,))
        if it.get("overflow"):
            o = it["overflow"]
            add(fail, "overflow", where, "page %dpx wide in a %dpx window: %s" % (o["scrollWidth"], o["width"], "; ".join(o["elements"]) or "?"),
                "overflow|" + where, texts=tuple(o["elements"]))
        for v in it.get("axe") or []:
            bucket = fail if v["impact"] in FAIL_IMPACT else review
            key = "a11y|%s|%s" % (where, v["id"])
            nodes = v.get("list") or [{"target": v["target"], "inside": []}]
            keep, waived = [], {}
            for n in nodes:
                w = waiver_for(waivers, "a11y", where, v["id"], [n["target"]] + list(n.get("inside") or [])) if waivers else None
                (waived.setdefault(w["reason"], []) if w else keep).append(n)
            shown_n = v["nodes"] - sum(len(x) for x in waived.values())
            for reason, ns in waived.items():
                known.append(("a11y", where, "%s (%s, %d node(s)): %s" % (v["id"], v["impact"], len(ns), "; ".join(n["target"] + contrast(n) for n in ns[:5]))
                              + " · " + reason, key))
            if shown_n > 0:
                bucket.append(("a11y", where, "%s (%s, %d node(s)): %s %s" % (
                    v["id"], v["impact"], shown_n, v["help"], "; ".join(n["target"] + contrast(n) for n in keep[:5]) or v["target"]), key))
        if it.get("touch"):
            split("touch", where, it["touch"], "touch|" + where, "; ".join)
        if it.get("clipped"):
            split("clipped", where, it["clipped"], "clipped|" + where, "; ".join)
        if it.get("focus") and it["focus"]["missing"]:
            n = it["focus"]["tabStops"]
            split("focus", where, it["focus"]["missing"], "focus|" + where,
                  lambda m: "%d of %d tab stops show no outline or ring: %s" % (len(m), n, "; ".join(m)))
        dfx = diffs.get(it.get("shot"))
        if dfx and dfx["status"] == "changed":
            add(review, "visual", where, ("%d px changed (%.2f%%)" % (dfx["px"], dfx["pct"]) if dfx.get("pct") is not None else dfx["why"])
                + (" · diffs/%s" % dfx["diff"] if dfx.get("diff") else ""), "visual|" + where)
    outside = []
    for x in res.get("rules") or []:   # rules registry: a failing must rule in scope fails, others need a human
        where = "%s%s" % (x["id"], (" · " + x["app"]) if x.get("app") else "")
        if x.get("status") == "skipped":
            skipped.append(("rule", where, "%s: %s" % (x["title"], x.get("reason") or "skipped"), "rule|" + where))
        elif not x["ok"]:
            row = ("rule", where, "%s (%s): exit %d%s" % (x["title"], x["severity"], x["exit"],
                                                           (" · " + " / ".join(x["summary"])) if x["summary"] else ""), "rule|" + where)
            if x.get("inScope") is False:
                outside.append(row)
            else:
                add(fail if x["severity"] == "must" else review, *row, rid=x["id"])
    res["_outside"] = outside
    for f in res.get("flows") or []:
        if not f["ok"]:
            detail = ("step %s: %s" % (f["failedStep"], f["error"])) if f.get("failedStep") else (f.get("error") or "; ".join(f.get("errors") or []))
            add(fail, "flow", f["name"], detail, "flow|" + f["name"], texts=(detail,))
    if not res["axe"]["available"]:
        skipped.append(("a11y", "—", "axe-core not found: pass --axe <axe.min.js>, set KIT_AXE_PATH or kit.config.json > validate.axePath "
                        "(a copy outside the project is fine); npm i -D axe-core only when the project has a package.json", "a11y|—"))
    nobase = [s for s, dfx in diffs.items() if dfx["status"] == "new"]
    if nobase:
        skipped.append(("visual", "—", "no baseline for %d screenshot(s); review them, then run baseline to accept" % len(nobase), "visual|—"))
    res["_known"] = known
    return fail, review, skipped


def write_report(cfg, app_id, run, res, diffs, waivers=(), prev=None):
    fail, review, skipped = classify(res, diffs, waivers)
    outside = res.pop("_outside", [])
    known = res.pop("_known", [])
    T = lambda k, **kw: t(cfg, "validate." + k, **kw)
    bad = {r[1] for r in fail if r[0] in ("open", "console", "overflow", "a11y")}
    passed = sum(1 for it in res["items"] if "%s · %s · %spx · %s" % (it["screen"], it["state"], it["vp"], it["mode"]) not in bad)
    cmp_ = compare_keys(prev, fail, review) if prev else None
    lines = ["# " + T("title", app=app_id), "",
             T("meta", started=res["started"][:19].replace("T", " "), url=res["url"], viewports=", ".join(map(str, res["viewports"])),
               modes=", ".join(res["modes"]), axe=res["axe"]["version"] or T("notInstalled")), "",
             "| %s | %s | %s | %s | %s | %s |" % (T("views"), T("flows"), T("fail"), T("review"), T("knownTitle"), T("skipped")),
             "|---|---|---|---|---|---|",
             "| %d (%d %s) | %d (%d %s) | %d | %d | %d | %d |" % (len(res["items"]), passed, T("clean"), len(res["flows"]),
                                                              sum(1 for f in res["flows"] if f["ok"]), T("ok"), len(fail), len(review),
                                                              len(known), len(skipped)), ""]
    if cmp_:
        lines += [T("compareNote", run=cmp_["run"] or "?", new=len(cmp_["new"]), carried=len(cmp_["carried"]), fixed=len(cmp_["fixed"])), ""]
    new = set(cmp_["new"]) if cmp_ else set()
    for title, rows, note, since in ((T("failTitle"), fail, T("failNote"), True), (T("reviewTitle"), review, T("reviewNote"), True),
                                     (T("knownTitle"), known, T("knownNote"), False), (T("skippedTitle"), skipped, "", False)) \
            + (((T("outsideTitle"), outside, T("outsideNote"), False),) if outside else ()):
        if title == T("knownTitle") and not rows and not waivers:
            continue
        since = since and cmp_ is not None
        lines += ["## %s (%d)" % (title, len(rows)), ""]
        if note:
            lines += [note, ""]
        if rows:
            lines += ["| %s | %s | %s |%s" % (T("check"), T("where"), T("detail"), " %s |" % T("since") if since else ""),
                      "|---|---|---|" + ("---|" if since else "")]
            lines += ["| %s | %s | %s |%s" % (T("kind." + r[0]), r[1], r[2].replace("|", "/"),
                                              (" %s |" % (T("new") if row_key(r) in new else T("carried"))) if since else "") for r in rows]
        else:
            lines.append("—")
        lines.append("")
    lines += ["## " + T("shotsTitle"), "", T("shotsNote"), ""]
    report = {"app": app_id, "run": run.name, "fail": fail, "review": review, "known": known, "skipped": skipped,
              "outsideScope": outside, "diffs": diffs, "compare": cmp_}
    (run / "report.md").write_text("\n".join(lines), encoding="utf-8")
    (run / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return fail, review, skipped


def previous_report(cfg, app_id, run, spec):
    """--compare: none = no comparison; a run folder name or path, or a report.json; default = the run before this one."""
    if spec == "none":
        return None
    if spec:
        p = Path(spec)
        p = p if p.exists() else vdir(cfg, app_id) / spec
        p = p / "report.json" if p.is_dir() else p
        if not p.is_file():
            die("report to compare with not found: %s" % spec)
        return json.loads(p.read_text(encoding="utf-8"))
    d = vdir(cfg, app_id)
    runs = sorted(x for x in d.glob("2*") if (x / "report.json").is_file() and x.name < run.name)
    return json.loads((runs[-1] / "report.json").read_text(encoding="utf-8")) if runs else None


def waivers_path(cfg, a):
    return Path(a.waivers) if a.waivers else vdir(cfg, a.app) / "waivers.json"


def axe_path(cfg, a):
    """--axe, else env KIT_AXE_PATH, else kit.config.json > validate.axePath (relative to the project root); None = look
    in node_modules. A path that is given but missing is an error, never a silent skip."""
    v = a.axe or os.environ.get("KIT_AXE_PATH") or (cfg.get("validate") or {}).get("axePath")
    if not v:
        return None
    p = Path(v) if Path(v).is_absolute() else Path(cfg["_root"]) / v
    if not p.exists():
        die("axe-core not found at %s (from %s)" % (p, "--axe" if a.axe else "KIT_AXE_PATH" if os.environ.get("KIT_AXE_PATH") else "validate.axePath"))
    return str(p.resolve())


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
    attr, modes, theming = mode_setup(cfg)
    waivers = load_waivers(waivers_path(cfg, a))
    axe = axe_path(cfg, a)
    run = d / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run.mkdir(parents=True)
    cmd = ["node", str(HERE / "validate.js"), "--url", url, "--plan", str(plan), "--out", str(run),
           "--viewports", a.viewports, "--modes", a.modes or ",".join(modes), "--mode-attr", attr, "--project", cfg["_root"],
           "--touch-min", str(a.touch_min or touch_min(cfg, app)), "--theming", json.dumps(theming),
           "--waive", json.dumps(sorted({w["selector"] for w in waivers if w.get("selector")}))]
    if axe:
        cmd += ["--axe", axe]
    st = (cfg.get("validate") or {}).get("setTheme")
    if st:
        cmd += ["--set-theme", st]
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
    fail, review, skipped = write_report(cfg, a.app, run, res, diffs, waivers, previous_report(cfg, a.app, run, a.compare))
    print("Report: %s · %d fail · %d to review · %d skipped" % (
        shown(cfg, run / "report.md"), len(fail), len(review), len(skipped)))
    sys.exit(1 if fail else 0)


def cmd_report(cfg, a):
    run = latest_run(cfg, a.app, a.run)
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    fail, review, skipped = write_report(cfg, a.app, run, res, compare_all(cfg, a.app, run, a.threshold, a.min_pixels),
                                         load_waivers(waivers_path(cfg, a)), previous_report(cfg, a.app, run, a.compare))
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
    # --page (one file, a built bundle), --routes, --url: hash-only routes, parameter routes listed as hints
    (d / "apps" / "w" / "dist").mkdir()
    (d / "apps" / "w" / "dist" / "index.html").write_text('<script>const r=[{path:"/n/:id"},{path:"/done"}];location.hash="#/n/"</script>')
    one = plan_from_app({"_root": str(d), "stack": "html"}, {"path": "apps/w"}, page="dist/index.html", url="http://localhost:9/w/")
    assert [x["route"] for x in one["screens"]] == ["", "#/n/", "#/done"] and one["url"] == "http://localhost:9/w/", one
    assert one["_paramRoutes"] == ["#/n/:id"], one
    rel = plan_from_app({"_root": str(d), "stack": "html"}, {"path": "apps/w"}, page="notes/index.html", routes=["#/n/7"])
    assert [x["route"] for x in rel["screens"]] == ["notes/index.html", "notes/index.html#/n/7"] and "url" not in rel, rel
    assert state_hints({"_ds": {"theming": {"brand": {"attr": "data-brand", "values": ["default", "ocean"]},
                                            "mode": {"attr": "data-mode", "values": ["light", "dark"]}}}}) == ["brand=ocean", "text=200%"]
    assert mode_setup({"_ds": {"theming": {"brand": {"attr": "data-brand"}}}})[2] == {"brand": "data-brand"}
    # waivers: axe nodes inside a waived selector go to Known with the reason; contrast ratio and colours in the detail
    wf = d / "waivers.json"
    wf.write_text(json.dumps([{"check": "a11y", "id": "color-contrast", "selector": "#shell", "reason": "shared frame, other work"},
                              {"check": "touch", "match": "#tiny", "reason": "icon button, accepted"}]))
    ws = load_waivers(wf)
    item = {"screen": "S01", "state": "default", "vp": 1280, "mode": "light", "axe": [
        {"id": "color-contrast", "impact": "serious", "help": "contrast", "nodes": 2, "target": "#shell > a", "list": [
            {"target": "#shell > a", "inside": ["#shell"], "ratio": 2.78, "expected": "4.5:1", "fg": "#8a8a8a", "bg": "#ffffff"},
            {"target": "main p", "inside": [], "ratio": 3.75, "expected": 4.5, "fg": "#777777", "bg": "#ffffff"}]}],
        "touch": ["button#tiny 20x20", "a.more 30x30"]}
    res = {"items": [item], "flows": [], "axe": {"available": True}}
    f, r, _ = classify(res, {}, ws)
    kn = res["_known"]
    assert len(f) == 1 and "1 node(s)" in f[0][2] and "main p 3.75:1 (needs 4.5:1), #777777 on #ffffff" in f[0][2], f
    assert any("#shell > a 2.78:1" in k[2] and "shared frame" in k[2] for k in kn) and any("#tiny" in k[2] for k in kn), kn
    assert r == [("touch", "S01 · default · 1280px · light", "a.more 30x30", "touch|S01 · default · 1280px · light")], r
    for bad in ([{"check": "a11y"}], [{"reason": "x"}], [{"check": "nope", "reason": "x"}]):
        wf.write_text(json.dumps(bad))
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                load_waivers(wf)
            raise AssertionError("bad waiver accepted: %s" % bad)
        except SystemExit:
            pass
    # compare: new vs carried over vs gone (rows of an older report without keys still compare)
    cm = compare_keys({"run": "r1", "fail": [list(f[0]), ["flow", "Old", "x"]]}, f + [("flow", "F2", "x", "flow|F2")], [])
    assert cm["carried"] == [f[0][3]] and cm["new"] == ["flow|F2"] and cm["fixed"] == ["flow|Old|x"], cm
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
    p.add_argument("--page", help="read only this file (relative to the app folder or the project; a built bundle works)")
    p.add_argument("--routes", help="comma list of hash routes to use instead of the ones found, e.g. '#/,#/n/1'")
    p.add_argument("--url", help="plan url: the URL the page is served at (routes are then hash-only)")
    p = sub.add_parser("run", help="run the checks and write the report")
    p.add_argument("--app", required=True); p.add_argument("--url"); p.add_argument("--viewports", default="390,768,1280")
    p.add_argument("--modes"); p.add_argument("--threshold", type=float, default=0.5, help="percent of pixels")
    p.add_argument("--min-pixels", type=int, default=100, help="changed pixels that count as a visual change")
    p.add_argument("--touch-min", type=int, help="smallest touch target in px on phone widths (default: by app platform)")
    p.add_argument("--no-rules", action="store_true", help="do not run the check commands of the rules registry")
    p.add_argument("--axe", help="axe.min.js (or a folder with axe-core) outside the project; else KIT_AXE_PATH, validate.axePath")
    p = sub.add_parser("baseline", help="accept a run's screenshots as baseline"); p.add_argument("--app", required=True); p.add_argument("--run")
    p = sub.add_parser("report", help="rebuild the report of a run")
    p.add_argument("--app", required=True); p.add_argument("--run"); p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--min-pixels", type=int, default=100)
    for sp in sub.choices.values():
        sp.add_argument("--dir", help="folder for the plan, runs and baseline (default <paths.validation>/<app>)")
    for k in ("run", "report"):
        sp = sub.choices[k]
        sp.add_argument("--waivers", help="known or out-of-scope findings with a reason (default <dir>/waivers.json)")
        sp.add_argument("--compare", "--baseline", dest="compare",
                        help="earlier run folder or report.json: mark rows new or carried over (default: previous run; none = off)")
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
