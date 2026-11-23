#!/usr/bin/env python3
"""Validate a prototype in the browser and write one report that separates failures from items a human must judge.

Commands:
  validation.py init --app <id> [--from-manifest manifest.js|manifest.json] [--base <capture base URL>] [--blank]
                     [--page <file>] [--routes '#/,#/n/1'] [--url <URL the page is served at>]
      Write <paths.validation>/<app>/plan.json: screens (id, route, states with a "prepare" script), flows
      (steps: goto, reload, click, fill, select, press, wait, expectVisible, expectHidden, expectText, expectUrl).
      --page: read only this file (relative to the app folder, else the project; a built bundle such as dist/index.html
      works too); --routes: use these hash routes instead of the ones found; --url: plan url (the page served over HTTP),
      routes are then hash-only, and the page is opened in Chromium (--no-browser: files only) so routes and ids that its
      scripts build (a Vue or React bundle) are found too: hash links, data-route attributes, the hash a tab or nav button
      sets, and ids / aria-labels of visible controls inside the content root (--content-root, else plan or
      kit.config.json > validate.contentRoot, default "main, #app, [role=main]": the first that matches, never the shell);
      screens are named from the page title and heading; other buttons of the content root are each clicked once in a
      fresh page (never one named like delete, remove, reset) and a hash they set becomes a screen; with no route in the
      files the URL as given is the first screen. A button that opens a dialog, menu, tab panel, [data-view] or panel
      without changing the hash becomes a state of the first screen (a prepare that clicks it; a flow when the opened
      element has an id); hidden dialogs and popup controls outside the content root are listed in _stateHints.
      Routes with a parameter (#/n/:id) are listed under _paramRoutes.
      When nothing is found the sample plan is written with a NOTE (pass --routes).
      Without --from-manifest the starter plan is read from the app: one screen per page and hash route (href="#/…",
      "#/…" in route tables, router paths), one flow per hash link, control ids as selector hints (--blank: template).
      --from-manifest builds the screens from the capture manifest of annotate/handoff instead: each screen gets the
      steps that reach it (steps of the screens it continues from first), its frames, and the plan url = --base (the URL
      the manifest gotos are relative to). A screen with its own viewport, or with actions (click, fill...) recorded at
      the manifest viewport, runs at that width only; route-only screens run at every width. Never overwrites a plan.
  validation.py run --app <id> [--url <entry>] [--viewports 390,768,1280] [--modes light,dark] [--threshold 0.5] [--min-pixels 100]
                    [--touch-min <px>] [--no-rules] [--axe <axe.min.js|folder>] [--waivers <file>] [--compare <run|report.json|none>]
                    [--artifacts <folder>]
      Run validate.js (Playwright) on the app, compare screenshots with the baseline (Pillow; a screenshot counts as changed
      when at least --min-pixels pixels or --threshold percent differ; defaults plan.minPixels / plan.threshold, else
      kit.config.json > validate.minPixels / validate.threshold, else 100 px and 0.5 %), write
      <paths.validation>/<app>/<run>/report.md and report.json. Exit 1 when anything fails. Screenshots and diffs go to
      <run>/shots and <run>/diffs, or with --artifacts (default kit.config.json > validate.artifactsDir) to
      <artifacts>/<app>/<run>/shots and diffs, outside the repository; the report names the folders.
      A page app (apps[].type page) without --url opens an .html of apps[].output, else its first host page (usedBy).
      Also runs the check commands of the active rules for the validate skill (scripts/rules.py check --app): a failing
      must rule is a Fail, a failing should or note rule needs a human, a skipped check (server down, not applicable) is
      Skipped. --rules-scope app (default): only checks of this app ({app}/{path}) can fail the run; failing project-wide
      checks go to "Outside the scope". --rules-scope all = every check; --rules-scope STY-001,A11Y-002 = those only.
      For a page app, a check URL that names the app (http://host/apps/{app}/) opens this run's http(s) entry, else each
      host page on that server; {app} elsewhere in a check is the host app id (from usedBy), a NOTE when none is found.
      Every skipped check is printed as a NOTE with its reason.
      Waivers (--waivers, default <dir>/waivers.json): findings matched by check/id + selector (+ screen) with a required
      reason go to "Known / waived", never Fail. --compare (alias --baseline; default: the previous run) marks each Fail and
      Needs-a-human row new or carried over and counts the ones no longer found; axe findings match by rule id, screen,
      state and the text of the failing elements, so a changed selector is not a new finding. axe-core: --axe, else env KIT_AXE_PATH,
      else kit.config.json > validate.axePath, else node_modules of the project or the kit.
      States: plan.states (every screen) and screen states may be named: "<ds.json theming key>=<value>" ("brand=ocean")
      or "text=200%". Theme values and dark mode go through kit.config.json > validate.setTheme (JS body with key, value)
      when set, else the ds.json > theming.<key>.attr attribute on <html>.
Every command takes --dir <folder>: plan, runs and baseline there instead of <paths.validation>/<app>. Steps without "timeout" wait plan.timeout ms
      (init --from-manifest copies the manifest's timeout; default 8000, the capture.js default).
      plan.prepare (JS string or {"js": …, "reload": true}): run after every page load of every screen and flow, before
      their own steps and prepare (dismiss a shell overlay once for the whole plan). Every prepare and eval step may use
      await at the top level (run as the body of an async function); a script whose value is a promise (an async IIFE)
      is awaited, and a prepare that reloads the page waits for the new page. A state or flow with "reload": true runs its
      prepare, reloads the page, then is checked (seed localStorage, then load). plan.settle (ms, a selector that must be
      hidden such as a skeleton, or {wait, waitForHidden, waitFor}) is waited for right before every view and flow end is
      read and captured, after every step, prepare and reload. axe runs on every state of the plan at the widest
      width; "axe": false on a state or a screen opts out; without plan.axe.include it is limited to the first
      plan.contentRoot selector that matches. The server of an http(s) entry is checked before
      each screen and flow: when it does not answer, the run stops with one ERROR line.
  validation.py parity --a <url> --b <url> [--plan <plan.json>] [--dir <out>] [--app <id>] [--viewports 1280] [--modes light]
                       [--threshold 0.5] [--min-pixels 100] [--classes review|differs|off] [--artifacts <folder>]
      Run the same plan (screens, states, flows) on two builds (an HTML page and its Vue port, before and after a
      refactor) and compare per screen and state: visible text, interactive elements by role and name, aria states,
      console errors, screenshot pixels (Pillow, when installed), and the tag and classes of the elements both builds have
      (by role and name, or own text: a link that gained a class), a "to look at" row unless --classes differs (or
      plan.classes "differs") counts it as a difference; per flow: result, URL after each step, localStorage at the end. URLs are compared relative to each side's entry folder, path only (scheme, host and port ignored), so a
      flow that leaves for another page of the same app matches. plan.mask (CSS selectors: clocks, timestamps) is masked
      in screenshots and its text replaced before text compare; plan.normalize ["time"] replaces clock and relative times,
      "ids" generated ids (#/c/umwrwh5d4, conv.umwrwh5d4, my-mwrwl3pr, t15d5: letters and digits mixed, epoch and base-36
      times) and {"pattern": regex, "replace": text} anything else, in text, names, flow URLs and localStorage keys and values.
      A prepare that fails on either side (or a view that opens on neither) is an Error with the side and the message,
      never a Match. Pixels differ from --min-pixels (default plan.minPixels, validate.minPixels, 100) or --threshold %.
      Writes <out>/parity.md and parity.json (Errors, then Match / Differs with both values, flow results on A and B, and
      flows failing on both builds, listed to look at without changing the exit code); exit 1 when anything differs or
      fails. plan.portals: parts teleported into body (menus, popovers), compared on both sides; plan.contentRoot may be
      an array of selectors (every region that matches). --dir: the report folder (default <paths.validation>/<app>/parity with --app); --plan: default
      <dir>/plan.json, else <paths.validation>/<app>/plan.json. The two runs (a/, b/) and diffs/ go to the report folder,
      or with --artifacts (default validate.artifactsDir) to <artifacts>/<app>/parity, outside the repository.
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
import difflib
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
import kitconf  # noqa: E402
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


def page_entry(cfg, app):
    """The file to open for a page app (apps[].type page): an .html entry of apps[].output, else the index.html of the
    first host page (usedBy, kitconf.app_pages). None when there is none."""
    root = Path(cfg["_root"])
    cands = [o for o in kitconf.outputs(app) if o.endswith((".html", ".htm"))]
    cands += [p + "index.html" if p.endswith("/") else p for p in kitconf.app_pages(cfg, app.get("id"))]
    return next((root / c for c in cands if (root / c).is_file()), None)


def entry_url(cfg, a, app, plan=None):
    if a.url:
        return a.url
    if plan and plan.get("url"):
        return plan["url"]
    if app.get("type") == "page":
        f = page_entry(cfg, app)
        if f is None:
            die("page app %s: no page to open (no .html in apps[].output, no host page in usedBy): pass --url" % app.get("id"))
        return f.resolve().as_uri()
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
             "{expectHidden: selector}, {expectText: [selector, text]} (text \"\" = the element has no text), {expectUrl: part}. "
             "expectVisible passes when any element that matches is visible, expectHidden when none is ('sel >> nth=0': the first only).",
    "namedStates": "A state may be a name: '<ds.json theming key>=<value>' (e.g. 'brand=ocean') or 'text=200%'. "
                   "plan.states are added to every screen; _stateHints lists the ones this DS offers.",
    "axe": "plan.axe or screen.axe {include: [selector], exclude: [selector]} limits axe to part of the page. Findings that are "
           "known or outside the work go into waivers.json (check, id, selector, screen, reason), not out of the plan. axe runs on "
           "every state; \"axe\": false on a state or screen opts out.",
    "prepare": "plan.prepare: JS (or {js, reload: true}) run after every page load of every screen and flow, before their own "
               "steps, e.g. to dismiss a shell overlay. A state or flow with reload: true runs its prepare, reloads, then is checked "
               "(seed localStorage, then load). plan.settle: ms, a selector that must be hidden (a skeleton) or {wait, waitForHidden, "
               "waitFor}, waited for right before every view and flow end is read. contentRoot: the page's own content (selectors, parity text): "
               "a selector list (the first that matches) or an array (every region that matches). portals: [selector] of parts "
               "teleported into body (menus, popovers), read on both sides after the root text.",
    "mask": "plan.mask: CSS selectors of parts that change on every run (clocks, timestamps): masked in screenshots, and their "
            "text replaced by '▒' before parity compares text and names. plan.normalize: [\"time\"] also replaces clock times "
            "(09:27) and relative times ('5 min ago'), \"ids\" generated ids (#/c/umwrwh5d4), {\"pattern\": regex, \"replace\": text} "
            "anything else, in parity text, URLs and localStorage. plan.classes: \"review\" (default), \"differs\" or \"off\" for "
            "tag and class differences.",
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
TITLE = re.compile(r"<title[^>]*>([^<]+)</title>", re.I)
CONTENT_ROOT = "main, #app, [role=main]"


def page_title(txt):
    """The <title> of a page file, for screen names (never 'index.html')."""
    m = TITLE.search(txt)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def discover(url, content_root):
    """Open url in Chromium (validate.js --discover) and read the rendered page: title, heading, routes, selectors of
    the content root. None when the browser cannot run (the plan is then read from the files only)."""
    r = subprocess.run(["node", str(HERE / "validate.js"), "--discover", "--url", url, "--content-root", content_root],
                       capture_output=True, text=True)
    line = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode == 2:   # server down: say so, the plan is still read from the files
        print("WARNING: " + line.replace("ERROR: ", "", 1))
        return None
    try:
        return json.loads(line) if r.returncode == 0 else None
    except ValueError:
        return None


def merge_discovered(plan, disc, routes_given=False):
    """Add what the rendered page showed to a starter plan read from files: hash routes (unless --routes was given), screen
    names from the heading or title, a click flow per route, and the selectors inside the content root instead of the
    file's ids (those include the shell around the page)."""
    label = disc.get("heading") or disc.get("title") or ""
    screens, flows = plan["screens"], plan["flows"]
    for sc in screens:
        if label and sc["route"] == "":
            sc["name"] = label
    have = {sc["route"] for sc in screens}
    if not screens:   # nothing in the files: the page as it opened (the URL given) is the first screen
        h = disc.get("hash") or ""
        screens.append({"id": "S01", "name": label or h or "Entry", "route": "", "states": []})
        have.add("")
        if h.startswith("#/") and h != "#/":
            have.add(h)
    for r in disc.get("routes") or []:
        route = "" if r["route"] == "#/" else r["route"]
        if ":" in route:
            continue
        if not routes_given and route not in have:
            have.add(route)
            screens.append({"id": "S%02d" % (len(screens) + 1), "name": " · ".join(x for x in (label, r.get("name") or route) if x),
                            "route": route, "states": []})
        click = r.get("via") or "a[href='%s']" % r["route"]
        if route and len(flows) < 8 and not any(f["steps"][0].get("click") == click for f in flows if f.get("steps")):
            flows.append({"name": "Open %s" % (r.get("name") or route), "start": "", "viewport": 1280,
                          "steps": [{"click": click}, {"expectUrl": r["route"]}]})
    # no hash route, but a dialog, panel or view opened by a button: a state of the first screen (and a flow when it has
    # a selector to expect)
    first = next((sc for sc in screens if sc["route"] == ""), None)
    for st in disc.get("states") or []:
        if first is None or any(x.get("name") == st["name"] for x in first["states"]):
            continue
        first["states"].append({"name": st["name"], "_opens": st.get("opens") or "",
                                "prepare": "document.querySelector(%s).click(); await new Promise(r => setTimeout(r, 300));" % json.dumps(st["css"])})
        if st.get("sel") and len(flows) < 8:
            flows.append({"name": "Open %s" % st["name"], "start": "", "viewport": 1280,
                          "steps": [{"click": st.get("via") or st["css"]}, {"expectVisible": st["sel"]}]})
    if disc.get("hints"):
        plan["_domHints"] = disc["hints"]
    if disc.get("selectors"):
        plan["_selectors"] = disc["selectors"]
    if disc.get("contentRoot"):
        plan["contentRoot"] = disc["contentRoot"]
    else:
        plan["_contentRoot"] = "no content root matched: selectors come from the whole page; set --content-root"
    plan["_source"] = ("starter plan read from the rendered page (routes, names, selectors inside %s) and the app files: check every "
                       "route, add the states (empty, error, loading) and the flows the work needs" % (disc.get("contentRoot") or "the page"))
    return plan


def find_page(cfg, app, page):
    """--page: a file relative to the app folder, else to the project root, else as given."""
    for c in (Path(cfg["_root"]) / app["path"] / page, Path(cfg["_root"]) / page, Path(page)):
        if c.is_file():
            return c
    die("page not found: %s (relative to the app folder %s or the project)" % (page, app["path"]))


def plan_from_app(cfg, app, page=None, routes=None, url=None, browser=False, content_root=None):
    """Starter plan read from the app's files: one screen per page and hash route found (href="#/…", "#/…" strings in
    route tables, router path: '/…' in react/vue sources or a built bundle), one flow per in-page hash link (click it,
    expect the URL), and the ids of the main controls (buttons, links, fields) as selector hints. Never guesses states
    or data. page = only this file; routes = these hash routes instead of the ones found; url = the plan url (the page
    as served), so routes are hash-only; browser = also read the rendered page at url (merge_discovered)."""
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
        srcd = base / "src" if (base / "src").is_dir() else base   # a page folder inside a workspace package has no src/
        pages = [f for f in sorted(srcd.rglob("*")) if f.suffix in (".vue", ".tsx", ".jsx", ".ts", ".js")
                 and "node_modules" not in f.parts and "dist" not in f.relative_to(base).parts] if base.is_dir() else []
        pages += [f for f in [base / "dist" / "index.html"] if f.is_file()]   # routes only present in the built bundle
    else:
        pages = [f for f in sorted(base.rglob("*.html")) if not (set(f.relative_to(base).parts[:-1]) & SKIP_PARTS)
                 and not any(x.startswith(("_", ".")) for x in f.relative_to(base).parts[:-1])]
        pages.sort(key=lambda f: (f.relative_to(base).as_posix() != entry, f.relative_to(base).as_posix()))
    screens, flows, seen, ids, params = [], [], set(), [], []
    for f in pages:
        txt = f.read_text(encoding="utf-8", errors="replace")
        ttl = page_title(txt)
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
            screens.append({"id": "S%02d" % (len(screens) + 1), "name": (ttl + (" " + r if r else "")) if ttl else (page or entry) + (r or ""),
                            "route": key, "states": []})
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
    if url and browser:
        disc = discover(url, content_root or (cfg.get("validate") or {}).get("contentRoot") or CONTENT_ROOT)
        if disc is None:
            print("WARNING: could not read %s in Chromium: routes and selectors come from the files only (serve the page "
                  "and run init again for the routes its scripts build)" % url)
        else:
            merge_discovered(plan, disc, routes is not None)
            plan["screens"] = plan["screens"][:60]
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
    plan = plan_from_app(cfg, app, a.page, [x.strip() for x in a.routes.split(",") if x.strip()] if a.routes else None, a.url,
                         browser=not a.no_browser, content_root=a.content_root) if not a.blank else None
    if plan:
        dom = plan.pop("_domHints", [])
        plan["_stateHints"] = state_hints(cfg) + dom
        n_states = sum(len(sc.get("states") or []) for sc in plan["screens"])
        if len(plan["screens"]) <= 1 and not n_states and dom:
            print("NOTE: one screen and no state found; _stateHints lists %d control(s) or dialog(s) of the page to add as states" % len(dom))
    if plan and plan["screens"]:
        f.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Wrote %s: %d screens, %d states and %d flows read from the %s (%d selector hints%s). Check the routes, add states and flows."
              % (shown(cfg, f), len(plan["screens"]), n_states, len(plan["flows"]),
                 "rendered page and files" if plan.get("contentRoot") or plan.get("_contentRoot") else "app",
                 len(plan.get("_selectors") or []), ", inside " + ", ".join(plan["contentRoot"] if isinstance(plan["contentRoot"], list) else [plan["contentRoot"]])
                 if plan.get("contentRoot") else ""))
        return
    plan = {
        "_help": PLAN_HELP,
        "screens": [{"id": "S01", "name": "Home", "route": "", "states": [
            {"name": "empty", "prepare": "localStorage.clear();", "reload": True}]}],
        "flows": [{"name": "Open settings", "start": "", "viewport": 1280,
                   "steps": [{"click": "a[href='#/settings']"}, {"expectUrl": "#/settings"}]}],
    }
    f.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wrote %s. Replace the example screens, states and flows with the app's own." % shown(cfg, f))
    if not a.blank:
        print("NOTE: this is the sample plan: no route was found in the app files%s. Pass --routes '#/,#/n/1' (concrete "
              "routes, a parameter route needs a real id) or --url <the page served over HTTP> so the rendered page is read."
              % (" nor in the rendered page" if a.url and not a.no_browser else
                 " (no --url: the rendered page was not read)" if not a.url else " (--no-browser: the rendered page was not read)"))


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


def a11y_key(where, rid, nodes):
    """Key of an axe row: rule id, screen view and the normalized text of its failing elements (never the selector, so
    a changed selector is the same finding)."""
    texts = sorted({re.sub(r"[\s|~]+", " ", str(n.get("text") or "")).strip().lower() for n in nodes} - {""})
    return "a11y|%s|%s|%s" % (where, rid, "~".join(texts))


def _a11y_parts(k):
    p = k.split("|")
    if p[0] != "a11y" or len(p) < 3:
        return None
    return "|".join(p[:3]), set(filter(None, (p[3] if len(p) > 3 else "").split("~")))


def compare_keys(prev, fail, review):
    """prev = an earlier report.json: which rows are new, which carried over, how many keys are gone. axe rows match
    on rule id + screen view when their element texts overlap (or either side has none, e.g. a report from before 0.12)."""
    old = {row_key(r) for r in (prev.get("fail") or []) + (prev.get("review") or [])}
    now = {row_key(r) for r in fail + review}
    carried, matched = [], set()
    for k in sorted(now):
        o = k if k in old else None
        a = _a11y_parts(k) if o is None else None
        if a:
            o = next((x for x in sorted(old - matched) if (_a11y_parts(x) or ("",))[0] == a[0]
                      and (not a[1] or not _a11y_parts(x)[1] or a[1] & _a11y_parts(x)[1])), None)
        if o is not None:
            carried.append(k)
            matched.add(o)
    return {"run": prev.get("run"), "new": sorted(now - set(carried)), "carried": carried, "fixed": sorted(old - matched)}


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
            nodes = v.get("list") or [{"target": v["target"], "inside": []}]
            key = a11y_key(where, v["id"], nodes)
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
                + (" · %s" % (dfx.get("diffPath") or "diffs/" + dfx["diff"]) if dfx.get("diff") else ""), "visual|" + where)
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
    shots, dd = run_dirs(run, res)
    lines += ["## " + T("shotsTitle"), "", T("shotsNote"), "", T("shotsWhere", shots=shown(cfg, shots), diffs=shown(cfg, dd)), ""]
    report = {"app": app_id, "run": run.name, "shotsDir": shown(cfg, shots), "diffsDir": shown(cfg, dd), "fail": fail, "review": review,
              "known": known, "skipped": skipped, "outsideScope": outside, "diffs": diffs, "compare": cmp_}
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


PIXELS = {"threshold": 0.5, "minPixels": 100}   # a screenshot counts as changed from this many pixels (or percent)


def pixel_limits(cfg, a, plan=None):
    """(threshold %, min pixels): the command line, else plan.threshold / plan.minPixels, else kit.config.json >
    validate.threshold / validate.minPixels, else 0.5 % and 100 px (the same defaults for run, report and parity)."""
    v = cfg.get("validate") or {}
    pick = lambda arg, k: arg if arg is not None else (plan or {}).get(k, v.get(k, PIXELS[k]))
    try:
        return float(pick(a.threshold, "threshold")), int(pick(a.min_pixels, "minPixels"))
    except (TypeError, ValueError):
        die("threshold must be a number and minPixels a whole number (command line, plan or validate.*)")


def artifacts_root(cfg, a):
    """--artifacts, else kit.config.json > validate.artifactsDir (relative to the project root): the folder screenshots and
    diffs go to instead of the validation folder (keep them out of the repository). None = inside the validation folder."""
    v = getattr(a, "artifacts", None) or (cfg.get("validate") or {}).get("artifactsDir")
    if not v:
        return None
    p = Path(v) if Path(v).is_absolute() or getattr(a, "artifacts", None) else Path(cfg["_root"]) / v
    return p.resolve()


def run_dirs(run, res=None):
    """(shots, diffs) folders of a run: where results.json says (an artifacts folder), else <run>/shots and <run>/diffs."""
    res = res if res is not None else json.loads((run / "results.json").read_text(encoding="utf-8"))
    return Path(res.get("shotsDir") or run / "shots"), Path(res.get("diffsDir") or run / "diffs")


def compare_all(cfg, app_id, run, threshold, min_px=100, res=None):
    base = vdir(cfg, app_id) / "baseline"
    shots, dd = run_dirs(run, res)
    dd.mkdir(parents=True, exist_ok=True)
    diffs = {}
    for shot in sorted(shots.glob("*.png")):
        b = base / shot.name
        diffs[shot.name] = diff(b, shot, dd / shot.name, threshold, min_px) if b.is_file() else {"status": "new"}
        if diffs[shot.name].get("diff"):
            diffs[shot.name]["diffPath"] = shown(cfg, dd / shot.name)
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
    art = artifacts_root(cfg, a)
    shots = art / a.app / run.name / "shots" if art else run / "shots"   # screenshots outside the repository (K4-2)
    cmd = ["node", str(HERE / "validate.js"), "--url", url, "--plan", str(plan), "--out", str(run), "--shots", str(shots),
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
    if p.returncode == 2:   # the server stopped answering: validate.js printed the one ERROR line
        sys.exit(1)
    if p.returncode != 0 or not (run / "results.json").is_file():
        sys.stdout.write(p.stderr[-2000:])
        die("browser run failed")
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    if art:
        res.update(shotsDir=str(shots), diffsDir=str(shots.parent / "diffs"))
        (run / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    if not a.no_rules:   # a page app: a check URL that names the app opens this run's http entry, else its host pages
        res["rules"] = rules_in_scope(RULES.run_checks(cfg, app=a.app, skill="validate", url=url if re.match(r"https?:", url) else None),
                                      a.rules_scope)
        (run / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        for x in res["rules"]:
            if x.get("note"):
                print("NOTE: rule %s · %s: %s" % (x["id"], x.get("app") or "", x["note"]))
            if x["status"] == "skipped":
                print("NOTE: rule %s%s skipped: %s" % (x["id"], (" · " + x["app"]) if x.get("app") else "", x.get("reason") or "?"))
    else:
        print("NOTE: --no-rules: the rule checks of the rules registry were not run")
    diffs = compare_all(cfg, a.app, run, *pixel_limits(cfg, a, json.loads(plan.read_text(encoding="utf-8"))), res=res)
    fail, review, skipped = write_report(cfg, a.app, run, res, diffs, waivers, previous_report(cfg, a.app, run, a.compare))
    print("Report: %s · %d fail · %d to review · %d skipped" % (
        shown(cfg, run / "report.md"), len(fail), len(review), len(skipped)))
    sys.exit(1 if fail else 0)


def cmd_report(cfg, a):
    run = latest_run(cfg, a.app, a.run)
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    pf = vdir(cfg, a.app) / "plan.json"
    lim = pixel_limits(cfg, a, json.loads(pf.read_text(encoding="utf-8")) if pf.is_file() else None)
    fail, review, skipped = write_report(cfg, a.app, run, res, compare_all(cfg, a.app, run, *lim, res=res),
                                         load_waivers(waivers_path(cfg, a)), previous_report(cfg, a.app, run, a.compare))
    print("Report: %s · %d fail · %d to review · %d skipped" % (shown(cfg, run / "report.md"), len(fail), len(review), len(skipped)))


def cmd_baseline(cfg, a):
    run = latest_run(cfg, a.app, a.run)
    base = vdir(cfg, a.app) / "baseline"
    base.mkdir(parents=True, exist_ok=True)
    n = 0
    for shot in run_dirs(run)[0].glob("*.png"):
        shutil.copy2(shot, base / shot.name)
        n += 1
    (base / "SOURCE.txt").write_text("Accepted from run %s on %s\n" % (run.name, dt.date.today().isoformat()), encoding="utf-8")
    print("Baseline: %d screenshot(s) from %s" % (n, run.name))


# ---------- parity: the same plan on two builds ----------

def _short(v, n=300):
    v = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return v if len(v) <= n else v[:n - 1] + "…"


def _cmp_dict(a, b):
    """(a side, b side) of the keys whose values differ; None when equal."""
    a, b = a or {}, b or {}
    ks = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    if not ks:
        return None
    return ("; ".join("%s: %s" % (k, a.get(k, "—")) for k in ks[:8]), "; ".join("%s: %s" % (k, b.get(k, "—")) for k in ks[:8]))


def _cmp_lines(a, b):
    a, b = a or [], b or []
    if a == b:
        return None
    if sorted(a) == sorted(b):
        i = next(i for i, (x, y) in enumerate(zip(a, b)) if x != y)
        return ("order differs at line %d: %s" % (i + 1, a[i]), "order differs at line %d: %s" % (i + 1, b[i]))
    only_a, only_b = [], []   # lines that a line-by-line diff removes from a and adds in b
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op != "equal":
            only_a += a[i1:i2]
            only_b += b[j1:j2]
    return ("only here (%d): %s" % (len(only_a), " / ".join(only_a[:6]) or "—"), "only here (%d): %s" % (len(only_b), " / ".join(only_b[:6]) or "—"))


def _errs(x):
    return sorted({re.sub(r"\d+", "#", e) for e in (x.get("errors") or [])})


ID_TOKEN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{5,}(?![A-Za-z0-9])")


def _is_id(tok, now=None):
    """A generated id: letters and digits mixed (t15d5, umwrwh5d4), an epoch time in ms or s, or a base-36 time
    (Date.now().toString(36), with up to 3 letters before it) within the last 90 days."""
    if re.search(r"[A-Za-z]\d+[A-Za-z]|\d[A-Za-z]+\d", tok) or re.fullmatch(r"\d{10}|\d{13}", tok):
        return True
    now = now or __import__("time").time() * 1000
    for i in range(0, min(4, len(tok) - 7)):
        if tok[i:i + 8] != tok[i:i + 8].lower():
            continue
        try:
            v = int(tok[i:i + 8], 36)
        except ValueError:
            continue
        if now - 90 * 864e5 <= v <= now + 864e5:
            return True
    return False


TIME_RX = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AaPp][Mm])?\b"
                     r"|\b\d+\s*(?:s|secs?|seconds?|m|mins?|minutes?|h|hrs?|hours?|d|days?|w|weeks?|months?|y|years?)\s+ago\b"
                     r"|\b\d+\s*(?:giây|phút|giờ|ngày|tuần|tháng|năm)\s+trước\b", re.I)
# plan.normalize: "time" = clock times (09:27) and relative times (5 min ago); "ids" = generated ids (#/c/umwrwh5d4,
# conv.umwrwh5d4, my-mwrwl3pr, t15d5) and epoch times; {"pattern": regex, "replace": text} = any other run-to-run value
NORMALIZERS = {"time": lambda v: TIME_RX.sub("<time>", v),
               "ids": lambda v: ID_TOKEN.sub(lambda m: "<id>" if _is_id(m.group(0)) else m.group(0), v)}


def normalizer(items):
    """One function str -> str for plan.normalize (names and {pattern, replace} items, in order); stops on a bad item."""
    fs = []
    for n in items or ():
        if isinstance(n, dict) and isinstance(n.get("pattern"), str):
            try:
                rx = re.compile(n["pattern"])
            except re.error as e:
                die("plan.normalize: %r is no regular expression (%s)" % (n["pattern"], e))
            fs.append(lambda v, rx=rx, r=str(n.get("replace", "")): rx.sub(r, v))
        elif isinstance(n, str) and n in NORMALIZERS:
            fs.append(NORMALIZERS[n])
        else:
            die("plan.normalize: unknown %s (known: %s, or {\"pattern\": regex, \"replace\": text})"
                % (json.dumps(n, ensure_ascii=False), ", ".join(NORMALIZERS)))
    return (lambda v: __import__("functools").reduce(lambda x, g: g(x), fs, v)) if fs else None


def _norm_keys(d, f, add=False):
    out = {}
    for k, v in (d or {}).items():
        out[f(k)] = out.get(f(k), 0) + v if add else v
    return out


def normalize_snap(snap, f):
    """A parity snapshot with plan.normalize applied to its text lines and to the names of roles, aria states and classes."""
    if not f or not snap:
        return snap
    return dict(snap, text=[f(x) for x in snap.get("text") or []], roles=_norm_keys(snap.get("roles"), f, True),
                aria={f(k): f(v) for k, v in (snap.get("aria") or {}).items()}, classes=_norm_keys(snap.get("classes"), f))


CLASS_MODES = ("review", "differs", "off")


def parity_compare(ra, rb, diffs=None, normalize=(), classes="review"):
    """Rows {where, check, status: match|differs|review|error, a, b} for two results.json of the same plan (validate.js
    --parity). Views match on screen, state, width and mode; flows on name. diffs = {shot: diff()} of A vs B screenshots.
    normalize = plan.normalize (["time", "ids", {"pattern", "replace"}]): applied on both sides to text, names, flow URLs
    and localStorage keys and values before they are compared. classes: the tag and classes of the elements both builds
    have (by role and name, or own text) that differ are a "review" row (default), a "differs" row, or not compared (off)."""
    rows, diffs = [], diffs or {}
    f = normalizer(normalize)
    if classes not in CLASS_MODES:
        die("classes must be one of %s" % ", ".join(CLASS_MODES))

    def add(where, check, d, same_a="", same_b=None, status="differs"):
        rows.append({"where": where, "check": check, "status": status if d else "match",
                     "a": _short(d[0]) if d else same_a, "b": _short(d[1]) if d else (same_a if same_b is None else same_b)})

    def broken(where, x, y, both_fatal=False):
        """An error row when a prepare failed on either side (or the view failed to open on both): never a match."""
        pa, pb = x.get("prepareError"), y.get("prepareError")
        if not (pa or pb or both_fatal):
            return False
        side = "A and B" if (pa and pb) or (both_fatal and not (pa or pb)) else "A" if pa else "B"
        rows.append({"where": where, "check": "prepare" if pa or pb else "open", "status": "error", "side": side,
                     "a": _short(pa or x.get("fatal") or x.get("error") or "ok"), "b": _short(pb or y.get("fatal") or y.get("error") or "ok")})
        return True

    def snap_rows(where, x, y):
        sx, sy = normalize_snap(x.get("snap") or {}, f), normalize_snap(y.get("snap") or {}, f)
        add(where, "text", _cmp_lines(sx.get("text"), sy.get("text")), "%d lines" % len(sx.get("text") or []))
        add(where, "roles", _cmp_dict(sx.get("roles"), sy.get("roles")), "%d elements" % sum((sx.get("roles") or {}).values()))
        add(where, "aria", _cmp_dict(sx.get("aria"), sy.get("aria")), "%d states" % len(sx.get("aria") or {}))
        ca, cb = sx.get("classes"), sy.get("classes")
        if classes != "off" and ca is not None and cb is not None:   # only the elements both builds have (K1a-8)
            both = set(ca) & set(cb)
            add(where, "classes", _cmp_dict({k: ca[k] for k in both}, {k: cb[k] for k in both}), "%d elements" % len(both),
                status=classes)

    def pixels(where, x):
        dfx = diffs.get(x.get("shot"))
        if not dfx:
            return
        if dfx["status"] == "skipped":
            rows.append({"where": where, "check": "pixels", "status": "skipped", "a": dfx.get("why", ""), "b": ""})
        else:
            d = None if dfx["status"] == "same" else (dfx.get("why") or "%s px (%s%%)" % (dfx.get("px"), dfx.get("pct")),
                                                      (dfx.get("diffPath") or "diffs/" + dfx["diff"]) if dfx.get("diff") else "")
            add(where, "pixels", d, "%s%% px differ" % dfx.get("pct", 0), "")

    key = lambda it: (it["screen"], it["state"], it["vp"], it["mode"])
    ia, ib = {key(x): x for x in ra.get("items") or []}, {key(x): x for x in rb.get("items") or []}
    for k in list(dict.fromkeys(list(ia) + list(ib))):
        where = "%s · %s · %spx · %s" % k
        x, y = ia.get(k), ib.get(k)
        if x is None or y is None:
            add(where, "open", ("not run" if x is None else "run", "not run" if y is None else "run"))
            continue
        if broken(where, x, y, bool(x.get("fatal") and y.get("fatal"))):
            continue
        if x.get("fatal") or y.get("fatal"):
            add(where, "open", (x.get("fatal") or "opened", y.get("fatal") or "opened"))
            continue
        snap_rows(where, x, y)
        ea, eb = _errs(x), _errs(y)
        add(where, "errors", None if ea == eb else ("; ".join(ea) or "none", "; ".join(eb) or "none"), "%d" % len(ea))
        pixels(where, x)
    fa, fb = {f["name"]: f for f in ra.get("flows") or []}, {f["name"]: f for f in rb.get("flows") or []}
    for n in list(dict.fromkeys(list(fa) + list(fb))):
        x, y = fa.get(n), fb.get(n)
        where = "flow · " + n
        if x is None or y is None:
            add(where, "result", ("not run" if x is None else "run", "not run" if y is None else "run"))
            continue
        if broken(where, x, y):
            continue
        res = lambda f: "passed" if f["ok"] else "step %s: %s" % (f.get("failedStep") or "-", f.get("error") or "; ".join(f.get("errors") or []))
        add(where, "result", None if res(x) == res(y) else (res(x), res(y)), res(x))
        side = lambda f: {"ok": bool(f["ok"]), "step": f.get("failedStep"), "error": _short(f.get("error") or "; ".join(f.get("errors") or []))}
        rows[-1]["flow"] = {"name": n, "a": side(x), "b": side(y)}   # each build's own result, for parity.md (K8-2)
        ua, ub = [f(u) for u in x.get("urls") or []] if f else x.get("urls") or [], [f(u) for u in y.get("urls") or []] if f else y.get("urls") or []
        steps = [i for i in range(max(len(ua), len(ub))) if (ua[i:i + 1] or ["—"]) != (ub[i:i + 1] or ["—"])]
        add(where, "urls", ("; ".join("step %d: %s" % (i + 1, (ua[i:i + 1] or ["—"])[0]) for i in steps[:6]),
                            "; ".join("step %d: %s" % (i + 1, (ub[i:i + 1] or ["—"])[0]) for i in steps[:6])) if steps else None,
            ua[-1] if ua else "—")
        stamp = lambda st: {(f(k) if f else k): re.sub(r"\b\d{10,13}\b", "<time>", f(str(v)) if f else str(v)) for k, v in (st or {}).items()}   # epoch times differ per run
        add(where, "storage", _cmp_dict(stamp(x.get("storage")), stamp(y.get("storage"))), "%d keys" % len(x.get("storage") or {}))
        snap_rows(where, x, y)
        ea, eb = _errs(x), _errs(y)
        add(where, "errors", None if ea == eb else ("; ".join(ea) or "none", "; ".join(eb) or "none"), "%d" % len(ea))
        pixels(where, x)
    return rows


def write_parity(cfg, out, a_url, b_url, plan_path, rows, limits=None, shots=None):
    T = lambda k, **kw: t(cfg, "validate.parity." + k, **kw)
    diff_rows = [r for r in rows if r["status"] == "differs"]
    err_rows = [r for r in rows if r["status"] == "error"]
    rev_rows = [r for r in rows if r["status"] == "review"]
    n_match = sum(1 for r in rows if r["status"] == "match")
    flows = [r for r in rows if r.get("flow")]
    both_bad = [r for r in flows if not r["flow"]["a"]["ok"] and not r["flow"]["b"]["ok"]]
    checks = list(dict.fromkeys(r["check"] for r in rows))
    lines = ["# " + T("title"), "", T("meta", a=a_url, b=b_url, plan=plan_path) + (" · " + T("pixelsMeta", **limits) if limits else ""), ""]
    if shots:
        lines += [T("shotsMeta", dir=shots), ""]
    lines += [T("summary", match=n_match, differs=len(diff_rows), skipped=len(rows) - n_match - len(diff_rows) - len(err_rows) - len(rev_rows)) +
              (" " + T("reviewSummary", n=len(rev_rows)) if rev_rows else "") + (" " + T("errorsSummary", n=len(err_rows)) if err_rows else ""), ""]
    if err_rows:
        lines += ["## %s (%d)" % (T("errorsTitle"), len(err_rows)), "", T("errorsNote"), "",
                  "| %s | %s | %s | A | B |" % (T("where"), T("check"), T("side")), "|---|---|---|---|---|"]
        lines += ["| %s | %s | %s | %s | %s |" % (r["where"], T("check." + r["check"]), r["side"], r["a"].replace("|", "/"), r["b"].replace("|", "/"))
                  for r in err_rows] + [""]
    lines += ["## %s (%d)" % (T("differsTitle"), len(diff_rows)), "", T("differsNote"), ""]
    if diff_rows:
        lines += ["| %s | %s | A | B |" % (T("where"), T("check")), "|---|---|---|---|"]
        lines += ["| %s | %s | %s | %s |" % (r["where"], T("check." + r["check"]), r["a"].replace("|", "/"), r["b"].replace("|", "/"))
                  for r in diff_rows]
    else:
        lines.append("—")
    if rev_rows:   # class and structure differences: a look, not a failure (unless --classes differs)
        lines += ["", "## %s (%d)" % (T("reviewTitle"), len(rev_rows)), "", T("reviewNote"), "",
                  "| %s | %s | A | B |" % (T("where"), T("check")), "|---|---|---|---|"]
        lines += ["| %s | %s | %s | %s |" % (r["where"], T("check." + r["check"]), r["a"].replace("|", "/"), r["b"].replace("|", "/"))
                  for r in rev_rows]
    fres = lambda x: T("flowPassed") if x["ok"] else T("flowFailed", step=x["step"] or "-", error=x["error"].replace("|", "/"))
    if both_bad:   # the same failure on both sides is a match, but a flow that fails everywhere proves nothing (K8-2)
        lines += ["", "## %s (%d)" % (T("bothFailTitle"), len(both_bad)), "", T("bothFailNote"), "",
                  "| %s | A | B |" % T("flow"), "|---|---|---|"]
        lines += ["| %s | %s | %s |" % (r["flow"]["name"], fres(r["flow"]["a"]), fres(r["flow"]["b"])) for r in both_bad]
    if flows:
        lines += ["", "## %s (%d)" % (T("flowsTitle"), len(flows)), "", "| %s | A | B | %s |" % (T("flow"), T("parity")), "|---|---|---|---|"]
        lines += ["| %s | %s | %s | %s |" % (r["flow"]["name"], fres(r["flow"]["a"]), fres(r["flow"]["b"]), T(r["status"])) for r in flows]
    lines += ["", "## " + T("allTitle"), "", "| %s | %s |" % (T("where"), " | ".join(T("check." + c) for c in checks)),
              "|---|" + "---|" * len(checks)]
    by = {}
    for r in rows:
        by.setdefault(r["where"], {})[r["check"]] = r["status"]
    for w, cs in by.items():
        lines.append("| %s | %s |" % (w, " | ".join(T(cs[c]) if c in cs else "" for c in checks)))
    lines.append("")
    (out / "parity.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "parity.json").write_text(json.dumps({"a": a_url, "b": b_url, "plan": str(plan_path), "match": n_match,
                                                 "differs": len(diff_rows), "errors": len(err_rows), "review": len(rev_rows),
                                                 "flowsFailingBoth": [r["flow"]["name"] for r in both_bad],
                                                 "pixels": limits, "shots": shots, "rows": rows},
                                                ensure_ascii=False, indent=2), encoding="utf-8")
    return n_match, len(diff_rows), len(err_rows)


def cmd_parity(cfg, a):
    """--app without --dir: the plan <paths.validation>/<app>/plan.json and the report in <paths.validation>/<app>/parity/
    (K4-1); --artifacts or validate.artifactsDir: the two runs (a/, b/ with their screenshots) and diffs/ go there (K4-2)."""
    if not a.dir and not a.app:
        die("parity needs --dir <folder> for the report, or --app <id> (report in <paths.validation>/<app>/parity)")
    if not a.dir and not cfg.get("paths"):
        die("parity --app needs a kit.config.json (paths.validation): pass --dir")
    out = Path(a.dir) if a.dir else vdir(cfg, a.app) / "parity"
    plan = Path(a.plan) if a.plan else (Path(a.dir) if a.dir and (Path(a.dir) / "plan.json").is_file() else vdir(cfg, a.app) if a.app else Path(a.dir)) / "plan.json"
    if not plan.is_file():
        die("plan not found: %s%s" % (plan, "" if a.plan else " (pass --plan)"))
    art = artifacts_root(cfg, a)
    work = art / (a.app or out.name) / "parity" if art else out   # a/, b/ and diffs/: outside the repository when set
    out.mkdir(parents=True, exist_ok=True)
    attr, modes, theming = mode_setup(cfg)
    res = {}
    for side, url in (("a", a.a), ("b", a.b)):
        d = work / side
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        cmd = ["node", str(HERE / "validate.js"), "--parity", "--url", url, "--plan", str(plan), "--out", str(d),
               "--viewports", a.viewports, "--modes", a.modes or modes[0], "--mode-attr", attr, "--project", cfg["_root"],
               "--theming", json.dumps(theming)]
        st = (cfg.get("validate") or {}).get("setTheme")
        if st:
            cmd += ["--set-theme", st]
        print("%s: %s" % (side.upper(), url))
        p = subprocess.run(cmd, capture_output=True, text=True)
        sys.stdout.write(p.stdout)
        if p.returncode == 2:
            sys.exit(1)
        if p.returncode != 0 or not (d / "results.json").is_file():
            sys.stdout.write(p.stderr[-2000:])
            die("browser run failed on %s" % url)
        res[side] = json.loads((d / "results.json").read_text(encoding="utf-8"))
    (work / "diffs").mkdir(exist_ok=True)
    diffs = {}
    pl = json.loads(plan.read_text(encoding="utf-8"))
    thr, min_px = pixel_limits(cfg, a, pl)
    for shot in sorted((work / "a" / "shots").glob("*.png")):
        b = work / "b" / "shots" / shot.name
        if b.is_file():
            diffs[shot.name] = diff(shot, b, work / "diffs" / shot.name, thr, min_px)
            if diffs[shot.name].get("diff"):
                diffs[shot.name]["diffPath"] = shown(cfg, work / "diffs" / shot.name) if art else "diffs/" + shot.name
    rows = parity_compare(res["a"], res["b"], diffs, pl.get("normalize") or (), a.classes or pl.get("classes") or "review")
    m, n, e = write_parity(cfg, out, a.a, a.b, shown(cfg, plan), rows, {"threshold": thr, "minPixels": min_px},
                           shown(cfg, work) if art else None)
    for r in rows:
        if r["status"] == "error":
            print("ERROR: %s · %s failed on %s: A: %s · B: %s" % (r["where"], r["check"], r["side"], r["a"], r["b"]))
    nr = sum(1 for r in rows if r["status"] == "review")
    for r in rows:
        if r.get("flow") and not r["flow"]["a"]["ok"] and not r["flow"]["b"]["ok"]:
            print("NOTE: flow %s fails on A (step %s) and on B (step %s): see parity.md" % (r["flow"]["name"], r["flow"]["a"]["step"] or "-",
                                                                                     r["flow"]["b"]["step"] or "-"))
    print("Parity: %s · %d match · %d differ%s%s" % (shown(cfg, out / "parity.md"), m, n, " · %d to look at (classes)" % nr if nr else "",
                                                    " · %d error(s)" % e if e else ""))
    sys.exit(1 if n or e else 0)


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
    # compare: axe rows match on rule + view + element text, not on the selector; legacy keys without text still match
    W = "S01 · menu · 1280px · light"
    k1 = a11y_key(W, "aria-required-children", [{"target": "button[data-k='']", "text": "Filter"}])
    k2 = a11y_key(W, "aria-required-children", [{"target": ".tab:nth-child(1)", "text": " filter "}])
    k3 = a11y_key(W, "aria-required-children", [{"target": ".x", "text": "Sort"}])
    assert k1 == k2 and "button" not in k1, (k1, k2)
    cm = compare_keys({"fail": [["a11y", W, "d", k1], ["a11y", W, "d", "a11y|%s|label" % W]]},
                      [("a11y", W, "d", k3), ("a11y", W, "d", a11y_key(W, "label", [{"text": "Search"}]))], [])
    assert cm["carried"] == [a11y_key(W, "label", [{"text": "Search"}])] and cm["new"] == [k3] and cm["fixed"] == [k1], cm
    # init --url: what the rendered page shows is merged into the starter plan
    assert page_title("<title> Library ·\n Acme Web </title>") == "Library · Acme Web" and page_title("<p>x</p>") == ""
    base_plan = {"screens": [{"id": "S01", "name": "index.html", "route": "", "states": []}], "flows": [], "_selectors": ["#modeBtn"]}
    disc = {"title": "Library · Acme Web", "heading": "Library", "contentRoot": "main", "selectors": ["#q", "button[aria-label=\"Filter\"]"],
            "routes": [{"route": "#/docs", "name": "Docs"}, {"route": "#/img", "name": "Images", "via": "#tabImg"}, {"route": "#/n/:id", "name": "x"}]}
    mp = merge_discovered(json.loads(json.dumps(base_plan)), disc)
    assert [(x["route"], x["name"]) for x in mp["screens"]] == [("", "Library"), ("#/docs", "Library · Docs"), ("#/img", "Library · Images")], mp
    assert [f["steps"][0]["click"] for f in mp["flows"]] == ["a[href='#/docs']", "#tabImg"] and mp["_selectors"][0] == "#q", mp
    assert mp["contentRoot"] == "main" and "#modeBtn" not in mp["_selectors"], mp
    mp = merge_discovered(json.loads(json.dumps(base_plan)), dict(disc, contentRoot=None, selectors=[]), routes_given=True)
    assert len(mp["screens"]) == 1 and mp["_selectors"] == ["#modeBtn"] and "_contentRoot" in mp, mp
    # parity: equal views match; a text, a role, a storage and a URL difference are reported with both values
    snap = {"text": ["Library", "Docs"], "roles": {'button "Filter"': 1}, "aria": {'button "Filter"': "expanded=false"}}
    view = {"screen": "S01", "state": "default", "vp": 1280, "mode": "light", "errors": [], "shot": "s.png", "snap": snap}
    flow = {"name": "Open filter", "ok": True, "urls": ["#/", "#/docs"], "storage": {"k": "grid", "t": '{"at":1795337192295}'}, "errors": [], "snap": snap}
    ra = {"items": [view, dict(view, state="menu")], "flows": [flow]}
    rb = {"items": [view, dict(view, state="menu", snap=dict(snap, text=["Library", "Files"], roles={'listbox "Filter"': 1}))],
          "flows": [dict(flow, urls=["#/", "#/files"], storage={"k": "list", "t": '{"at":1795337245027}'})]}
    rows = parity_compare(ra, rb, {"s.png": {"status": "same", "pct": 0.0, "px": 0}})
    st = {(r["where"], r["check"]): r for r in rows}
    assert all(r["status"] == "match" for r in rows if r["where"].startswith("S01 · default")), rows
    assert st[("S01 · default · 1280px · light", "pixels")]["status"] == "match"
    tx = st[("S01 · menu · 1280px · light", "text")]
    assert tx["status"] == "differs" and "Docs" in tx["a"] and "Files" in tx["b"], tx
    assert st[("S01 · menu · 1280px · light", "roles")]["status"] == "differs" and st[("S01 · menu · 1280px · light", "aria")]["status"] == "match"
    assert st[("flow · Open filter", "urls")]["b"] == "step 2: #/files" and st[("flow · Open filter", "storage")]["a"] == "k: grid", rows
    assert st[("flow · Open filter", "result")]["status"] == "match"
    n_m, n_d, _ = write_parity({"language": "en"}, d, "http://a/", "http://b/", "plan.json", rows)
    pm = (d / "parity.md").read_text()
    assert n_d == 4 and "## Differs (4)" in pm and "| Visible text |" in pm and json.loads((d / "parity.json").read_text())["differs"] == 4, pm
    # 0.12.1: plan.normalize ["time"]: clock and relative times on both sides; unknown names stop the run
    ta = dict(view, snap=dict(snap, text=["Chat", "Today 09:27", "5 min ago", "2 phút trước"], roles={'button "Sent 09:27"': 1}))
    tb = dict(view, snap=dict(snap, text=["Chat", "Today 09:28", "6 min ago", "3 phút trước"], roles={'button "Sent 09:28"': 1}))
    assert any(r["status"] == "differs" for r in parity_compare({"items": [ta]}, {"items": [tb]}))
    assert all(r["status"] == "match" for r in parity_compare({"items": [ta]}, {"items": [tb]}, normalize=["time"]) if r["check"] != "pixels")
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            parity_compare({"items": []}, {"items": []}, normalize=["dates"])
        raise AssertionError("unknown normalizer accepted")
    except SystemExit:
        pass
    # init --url: no screen in the files (a page folder of a workspace package, routes built at run time): the URL as
    # given is the first screen, routes found by clicking buttons are added
    mp = merge_discovered({"screens": [], "flows": []}, {"heading": "Notes", "hash": "#/n/7", "contentRoot": "main",
                                                         "routes": [{"route": "#/n/7", "name": "x"}, {"route": "#/n/8", "name": "Card 8", "via": "role=button[name=\"Card 8\"]"}]})
    assert [(x["route"], x["name"]) for x in mp["screens"]] == [("", "Notes"), ("#/n/8", "Notes · Card 8")], mp["screens"]
    (d / "ws" / "pg" / "lib").mkdir(parents=True)
    (d / "ws" / "pg" / "App.vue").write_text('<a href="#/list">L</a><button id="addBtn">+</button>')
    (d / "ws" / "pg" / "lib" / "r.ts").write_text('const R = [{ path: "/n/:id" }]')
    pp = plan_from_app({"_root": str(d), "stack": "html"}, {"path": "ws/pg", "stack": "vue"})
    assert [x["route"] for x in pp["screens"]] == ["", "#/list"] and pp["_paramRoutes"] == ["#/n/:id"] and "#addBtn" in pp["_selectors"], pp
    # 0.12.2 (K3-3): a prepare that fails on either side, or a view that opens on neither, is an error, never a match
    bad_a = dict(view, state="p", fatal="prepare of state \"p\" failed: x is not defined", prepareError="prepare of state \"p\" failed: x is not defined")
    for xa, xb, side in ((bad_a, bad_a, "A and B"), (bad_a, dict(view, state="p"), "A"), (dict(view, state="p"), bad_a, "B"),
                         (dict(view, state="p", fatal="net"), dict(view, state="p", fatal="net"), "A and B")):
        er = [r for r in parity_compare({"items": [xa]}, {"items": [xb]}) if r["status"] == "error"]
        assert len(er) == 1 and er[0]["side"] == side and er[0]["check"] == ("open" if "prepareError" not in xa and "prepareError" not in xb else "prepare"), er
    fl_bad = dict(flow, ok=False, error="flow prepare failed: boom", prepareError="flow prepare failed: boom")
    er = parity_compare({"flows": [fl_bad]}, {"flows": [fl_bad]})
    assert [r["status"] for r in er] == ["error"] and "boom" in er[0]["a"], er
    n_m, n_d, n_e = write_parity({"language": "en"}, d, "http://a/", "http://b/", "plan.json", er, {"threshold": 0.5, "minPixels": 400})
    pm = (d / "parity.md").read_text()
    assert n_e == 1 and n_m == 0 and "## Errors (1)" in pm and "from 400 px" in pm and json.loads((d / "parity.json").read_text())["errors"] == 1, pm
    # K1a-2: pixel limits from the command line, else the plan, else validate.*, else 0.5 % / 100 px (run, report, parity alike)
    ns = argparse.Namespace(threshold=None, min_pixels=None)
    assert pixel_limits({}, ns) == (0.5, 100) and pixel_limits({"validate": {"minPixels": 300}}, ns) == (0.5, 300)
    assert pixel_limits({"validate": {"minPixels": 300}}, ns, {"minPixels": 800}) == (0.5, 800)
    assert pixel_limits({"validate": {"minPixels": 300}}, argparse.Namespace(threshold=1.0, min_pixels=50), {"minPixels": 800}) == (1.0, 50)
    # K1a-4: a dialog or panel a button opens without a hash becomes a state of the first screen, and a flow when it has a selector
    mp = merge_discovered({"screens": [], "flows": []}, {"heading": "Notes", "contentRoot": "main", "routes": [], "hints": ["hidden dialog #d"],
                                                         "states": [{"name": "New note", "css": "#add", "via": "role=button[name=\"New note\"]",
                                                                     "opens": "dialog \"New note\"", "sel": "#dlg"},
                                                                    {"name": "Grid", "css": "#grid", "via": "#grid", "opens": "[data-view] \"grid\"", "sel": None}]})
    st0 = mp["screens"][0]["states"]
    assert [x["name"] for x in st0] == ["New note", "Grid"] and "await" in st0[0]["prepare"] and '"#add"' in st0[0]["prepare"], st0
    assert [f["steps"] for f in mp["flows"]] == [[{"click": "role=button[name=\"New note\"]"}, {"expectVisible": "#dlg"}]] and mp["_domHints"], mp
    # K3-6: a page app opens an .html of apps[].output, else its first host page
    (d / "host" / "pg").mkdir(parents=True)
    (d / "host" / "pg" / "index.html").write_text("<main></main>")
    pc = {"_root": str(d), "apps": [{"id": "host", "path": "host"}, {"id": "pg", "type": "page", "path": "src/pg", "usedBy": ["host/pg/pg.js"]}]}
    assert page_entry(pc, pc["apps"][1]) == d / "host" / "pg" / "index.html"
    pc2 = dict(pc, apps=[pc["apps"][0], dict(pc["apps"][1], usedBy=[], output=["dist/x.js", "host/pg/index.html"])])
    assert page_entry(pc2, pc2["apps"][1]) == d / "host" / "pg" / "index.html"
    pc2["apps"][1]["output"] = "dist/x.js"
    assert page_entry(pc2, pc2["apps"][1]) is None
    # 0.12.3 (K1a-6): plan.normalize "ids" and {"pattern", "replace"} on text, names, flow URLs and localStorage keys and values
    import time as _t

    def b36(n):   # Date.now().toString(36)
        n, o = int(n), ""
        while n:
            n, o = n // 36, "0123456789abcdefghijklmnopqrstuvwxyz"[n % 36] + o
        return o
    now = int(_t.time() * 1000)
    ida, idb = "u" + b36(now), "u" + b36(now + 98765)
    ids = NORMALIZERS["ids"]
    assert ids("#/c/umwrwh5d4 · oneai2.conv.umwrwh5d4 · my-mwrwl3pr · t15d5 · 1795337192295") == "#/c/<id> · oneai2.conv.<id> · my-<id> · <id> · <id>"
    assert ids("#/p/" + ida) == "#/p/<id>" and ids("p" + b36(now - 5 * 864e5)) == "<id>", (ida, ids("#/p/" + ida))
    for keep in ("1280px", "oneai2", "brand=blue", "Phân tích kỹ thuật", "h264", "mountain", "Settings"):
        assert ids(keep) == keep, keep
    fa = dict(flow, urls=["#/", "#/c/" + ida], storage={"oneai2.conv." + ida: '{"id":"%s","t":"Hi"}' % ida, "n": "item-7a1"},
              snap=dict(snap, text=["Chat " + ida], classes={}))
    fb = dict(flow, urls=["#/", "#/c/" + idb], storage={"oneai2.conv." + idb: '{"id":"%s","t":"Hi"}' % idb, "n": "item-7b2"},
              snap=dict(snap, text=["Chat " + idb], classes={}))
    raw = {r["check"]: r["status"] for r in parity_compare({"flows": [fa]}, {"flows": [fb]})}
    assert raw["urls"] == raw["storage"] == raw["text"] == "differs", raw
    nz = {r["check"]: r["status"] for r in parity_compare({"flows": [fa]}, {"flows": [fb]},
                                                          normalize=["ids", {"pattern": r"item-\w+", "replace": "item-#"}])}
    assert set(nz.values()) == {"match"}, nz
    for bad in ([{"pattern": "("}], [{"replace": "x"}]):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                parity_compare({"items": []}, {"items": []}, normalize=bad)
            raise AssertionError("bad normalize accepted: %s" % bad)
        except SystemExit:
            pass
    # K1a-8: tag and classes of the elements both builds have: a "review" row by default, "differs" on request, off
    ca = dict(view, snap=dict(snap, classes={'link "Docs"': "a.lnk", 'text "New"': "span.tag", 'text "Only A"': "p"}))
    cb = dict(view, snap=dict(snap, classes={'link "Docs"': "a.brand.lnk", 'text "New"': "span.solid.tag", 'text "Only B"': "div"}))
    cr = [r for r in parity_compare({"items": [ca]}, {"items": [cb]}) if r["check"] == "classes"]
    assert len(cr) == 1 and cr[0]["status"] == "review" and "a.lnk" in cr[0]["a"] and "a.brand.lnk" in cr[0]["b"] and "Only" not in cr[0]["a"], cr
    assert [r["status"] for r in parity_compare({"items": [ca]}, {"items": [cb]}, classes="differs") if r["check"] == "classes"] == ["differs"]
    assert not [r for r in parity_compare({"items": [ca]}, {"items": [cb]}, classes="off") if r["check"] == "classes"]
    assert [r["status"] for r in parity_compare({"items": [ca]}, {"items": [ca]}) if r["check"] == "classes"] == ["match"]
    n_m, n_d, n_e = write_parity({"language": "en"}, d, "http://a/", "http://b/", "plan.json", cr, None, "/tmp/art/x/parity")
    pm = (d / "parity.md").read_text()
    assert n_d == 0 and "## To look at (1)" in pm and "Class / structure" in pm and "/tmp/art/x/parity" in pm \
        and json.loads((d / "parity.json").read_text())["review"] == 1, pm
    # K4-2: --artifacts (relative to the current folder) or validate.artifactsDir (relative to the project), run folders
    ac = {"_root": str(d), "validate": {"artifactsDir": "../art"}}
    assert artifacts_root(ac, argparse.Namespace(artifacts=None)) == (d / "../art").resolve()
    assert artifacts_root({"_root": str(d)}, argparse.Namespace(artifacts=None)) is None
    assert artifacts_root(ac, argparse.Namespace(artifacts=str(d / "x"))) == (d / "x").resolve()
    assert run_dirs(d / "r1", {"shotsDir": "/a/shots", "diffsDir": "/a/diffs"}) == (Path("/a/shots"), Path("/a/diffs"))
    assert run_dirs(d / "r1", {}) == (d / "r1" / "shots", d / "r1" / "diffs")
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
    p.add_argument("--url", help="plan url: the URL the page is served at (routes are then hash-only; the page is opened to read "
                                 "routes and selectors its scripts build)")
    p.add_argument("--content-root", help="selector list of the page's own content (default validate.contentRoot, 'main, #app, [role=main]')")
    p.add_argument("--no-browser", action="store_true", help="with --url: read the files only, do not open the page")
    p = sub.add_parser("run", help="run the checks and write the report")
    p.add_argument("--app", required=True); p.add_argument("--url"); p.add_argument("--viewports", default="390,768,1280")
    p.add_argument("--modes"); p.add_argument("--threshold", type=float, help="percent of pixels (default plan, validate.threshold, 0.5)")
    p.add_argument("--min-pixels", type=int, help="changed pixels that count as a visual change (default plan.minPixels, validate.minPixels, 100)")
    p.add_argument("--touch-min", type=int, help="smallest touch target in px on phone widths (default: by app platform)")
    p.add_argument("--no-rules", action="store_true", help="do not run the check commands of the rules registry")
    p.add_argument("--axe", help="axe.min.js (or a folder with axe-core) outside the project; else KIT_AXE_PATH, validate.axePath")
    p = sub.add_parser("parity", help="run one plan on two builds and compare them")
    p.add_argument("--a", required=True, help="URL of the first build (e.g. the HTML page)")
    p.add_argument("--b", required=True, help="URL of the second build (e.g. its Vue port)")
    p.add_argument("--plan", help="plan.json with the screens, states and flows to run on both (default <dir>/plan.json, "
                                  "else <paths.validation>/<app>/plan.json)")
    p.add_argument("--classes", choices=CLASS_MODES, help="tag and class differences of the elements both builds have: review "
                                                          "(default, plan.classes), differs (count as a difference) or off")
    p.add_argument("--app", help="app id: its DS profile gives the theming attributes for named states")
    p.add_argument("--viewports", default="1280"); p.add_argument("--modes", help="default: the DS's first mode")
    p.add_argument("--threshold", type=float, help="percent of pixels (default plan.threshold, validate.threshold, 0.5)")
    p.add_argument("--min-pixels", type=int, help="fewer changed pixels never differ, e.g. anti-aliasing noise (default plan.minPixels, "
                                                 "validate.minPixels, 100: the same as run)")
    p = sub.add_parser("baseline", help="accept a run's screenshots as baseline"); p.add_argument("--app", required=True); p.add_argument("--run")
    p = sub.add_parser("report", help="rebuild the report of a run")
    p.add_argument("--app", required=True); p.add_argument("--run"); p.add_argument("--threshold", type=float)
    p.add_argument("--min-pixels", type=int)
    for sp in sub.choices.values():
        sp.add_argument("--dir", help="folder for the plan, runs and baseline (default <paths.validation>/<app>; parity: the report "
                                      "folder, default <paths.validation>/<app>/parity)")
    for k in ("run", "parity"):
        sub.choices[k].add_argument("--artifacts", help="folder for screenshots and diffs outside the repository (default "
                                                        "kit.config.json > validate.artifactsDir, else inside the validation folder)")
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
    if a.cmd == "parity":   # works outside a project too (two URLs and a plan)
        cfg = load(require=False, app=a.app) or {"language": "en", "_root": os.getcwd(), "_ds": {}}
    else:
        cfg = load(app=a.app)  # the app's own DS profile (apps[].ds): theming attributes, touch targets
    {"init": cmd_init, "run": cmd_run, "baseline": cmd_baseline, "report": cmd_report, "parity": cmd_parity}[a.cmd](cfg, a)


if __name__ == "__main__":
    main()
