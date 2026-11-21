#!/usr/bin/env python3
"""End-to-end fixture test of the kit: builds a throw-away project in a temp folder and runs the scripts on it.

  python3 tests/e2e.py [--keep] [--no-browser]

Flow: adopt (DS profile acme) -> kickoff (multi-page html app, plain vue app with a DS Vue layer) -> prototype checks
(kitconf check, registry update/check, review audit with project checks) -> validate (plan built from the capture
manifest) -> annotate capture (--only, legacy step alias) -> handoff (layer lock, finalize with every check, zip)
-> share (email without demo links), plus one fixture per extension point (sync.command, local.command/fields,
review.extraChecks, handoff.pre/post, email.demoLinks, ds.json > components.vue, tailwind: false, skills hints).
Browser steps need Node with Playwright and Chromium already installed (never runs `playwright install`).
Exit 1 on the first failed check. Runs every script's --selftest first. Never touches the network except localhost.
"""
import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
S = KIT / "skills"
PY = sys.executable
SELFTESTS = [
    [PY, KIT / "scripts/kitconf.py", "--selftest"],
    [PY, S / "handoff/scripts/pkg.py", "--selftest"],
    [PY, S / "wireflow/scripts/demo_links.py", "--selftest"],
    [PY, S / "validate/scripts/validation.py", "--selftest"],
    [PY, S / "sync/scripts/sync_ds.py", "--selftest"],
    [PY, S / "contribute/scripts/registry.py", "--selftest"],
    [PY, S / "review/scripts/audit_app.py", "--selftest"],
    [PY, S / "kickoff/scripts/scaffold.py", "--selftest"],
    ["node", S / "annotate/scripts/capture.js", "--selftest"],
]
OK = []


def run(cmd, cwd, expect=0, env=None):
    cmd = [str(c) for c in cmd]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    out = r.stdout + r.stderr
    if expect is not None and r.returncode != expect:
        print(out[-4000:])
        sys.exit("FAIL: %s exited %d (expected %d)" % (" ".join(cmd[:4]), r.returncode, expect))
    return out


def check(cond, what, detail=""):
    if not cond:
        print(detail[-4000:] if isinstance(detail, str) else detail)
        sys.exit("FAIL: " + what)
    OK.append(what)
    print("ok  " + what)


def serve(folder):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = functools.partial(Quiet, directory=str(folder))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d/" % srv.server_address[1]


def write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main():
    keep, browser = "--keep" in sys.argv, "--no-browser" not in sys.argv
    for c in SELFTESTS:
        out = run(c, KIT)
        check("selftest OK" in out, "selftest " + Path(c[1]).name, out)
    for c in ([PY, S / "handoff/scripts/pkg.py", "--help"], [PY, S / "validate/scripts/validation.py", "--help"],
              [PY, S / "sync/scripts/sync_ds.py", "--help"], [PY, S / "contribute/scripts/registry.py", "--help"],
              [PY, S / "review/scripts/audit_app.py", "--help"], [PY, S / "share/scripts/draft_email.py", "--help"],
              [PY, S / "kickoff/scripts/scaffold.py", "--help"], [PY, S / "wireflow/scripts/demo_links.py", "fill", "--help"],
              [PY, S / "annotate/scripts/spec_md.py", "--help"], ["node", S / "annotate/scripts/capture.js", "--help"],
              ["node", S / "validate/scripts/validate.js", "--help"], [PY, KIT / "scripts/kitconf.py", "--help"]):
        run(c, KIT)
    check(True, "--help of every changed script")

    d = Path(tempfile.mkdtemp(prefix="kit-e2e-"))
    print("project:", d)
    # ---------- adopt + kickoff ----------
    write(d / "kit.config.json", json.dumps({"language": "en", "stack": "html", "ds": "ds/acme", "apps": [
        {"id": "acme-web", "name": "Acme Web", "path": "apps/acme-web", "type": "multi",
         "build": "python3 apps/acme-web/_shell/build.py build", "check": "python3 apps/acme-web/_shell/build.py check",
         "platform": "desktop"},
        {"id": "acme-vue", "name": "Acme Vue", "path": "apps/acme-vue", "stack": "vue", "type": "spa"}],
        "skills": {"handoff": {"model": "sonnet", "effort": "medium"}}}, indent=1))
    run([PY, S / "adopt/scripts/adopt.py", "generate", "--name", "acme", "--label", "Acme DS", "--seed", "#2563eb",
         "--out", "ds/acme"], d)
    run([PY, S / "adopt/scripts/adopt.py", "check", "--out", "ds/acme"], d)
    check((d / "ds/acme/ds.json").is_file(), "adopt: DS profile acme")
    out = run([PY, S / "kickoff/scripts/scaffold.py", "--app", "acme-web", "--name", "Acme Web"], d)
    check((d / "apps/acme-web/settings/index.html").is_file(), "kickoff: html multi app", out)
    run([PY, KIT / "scripts/kitconf.py", "check"], d)
    out = run([PY, KIT / "scripts/kitconf.py", "skills"], d)
    check("handoff" in out and "sonnet" in out, "skills.<name> model/effort hints", out)

    # DS Vue layer + tailwind: false -> plain vue template with the @ds-vue alias
    ds_json = json.loads((d / "ds/acme/ds.json").read_text())
    ds_json["components"] = {"vue": {"package": "packages/acme-vue", "propsMap": "packages/acme-vue/props-map.csv"}}
    ds_json["tailwind"] = False
    write(d / "ds/acme/ds.json", json.dumps(ds_json, indent=1))
    write(d / "packages/acme-vue/AcmeButton.vue", "<template><button class=\"btn\"><slot /></button></template>\n")
    write(d / "packages/acme-vue/props-map.csv", "component,prop,figma\nAcmeButton,variant,Type\nAcmeDialog,open,Open\n")
    out = run([PY, S / "kickoff/scripts/scaffold.py", "--app", "acme-vue", "--name", "Acme Vue"], d)
    vite = (d / "apps/acme-vue/vite.config.ts").read_text()
    pj = json.loads((d / "apps/acme-vue/package.json").read_text())
    check("@ds-vue" in vite and "tailwind" not in vite and "tailwindcss" not in pj["devDependencies"]
          and not (d / "apps/acme-vue/src/components/ui").exists() and "vue-plain" in out,
          "kickoff: components.vue -> plain Vue template, alias @ds-vue, no Tailwind, no shadcn", out)
    write(d / "apps/acme-vue/src/components/local/AcmeDialog.vue", "<!-- LOCAL: Dialog -->\n<template><div class=\"x-dialog\" /></template>\n")

    # ---------- prototype checks: registry with field mapping, review with project checks ----------
    cfg = json.loads((d / "kit.config.json").read_text())
    cfg["local"] = {"fields": {"vs_ds": "compare"}}
    cfg["review"] = {"extraChecks": [
        {"name": "Flag ledger", "command": PY + " -c \"print('flags: 2 off, 0 without a note')\"", "parse": "^flags"},
        {"name": "A11y per app", "command": PY + " -c \"import sys; print('a11y', sys.argv[1], 'ok')\" {app}"}]}
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    home = d / "apps/acme-web/index.html"
    write(home, home.read_text().replace("</head>", "<style>\n/* LOCAL: Drop zone */\n.x-drop { display: grid; }\n</style>\n</head>", 1))
    run([PY, S / "contribute/scripts/registry.py", "update"], d)
    reg = json.loads((d / "docs/local-components.json").read_text())
    reg["components"][0]["demo"] = {"steps": ["open"]}
    write(d / "docs/local-components.json", json.dumps(reg, indent=2))
    run([PY, S / "contribute/scripts/registry.py", "update"], d)
    reg = json.loads((d / "docs/local-components.json").read_text())
    check(all("compare" in e and "vs_ds" not in e for e in reg["components"]) and reg["components"][0].get("demo"),
          "local.fields: project field names written, unknown fields kept")
    out = run([PY, S / "review/scripts/audit_app.py", "--json", d / "audit.json"], d)
    check("Flag ledger" in out and "flags: 2 off" in out and "a11y acme-web ok" in out and "DS Vue components" in out
          and "rebuilt locally" in out, "review.extraChecks rows + DS Vue layer row", out)
    check("Tailwind arbitrary values" not in out, "review: no Tailwind row when ds.json > tailwind is false", out)

    # ---------- extension points: sync.command, local.command ----------
    cfg["sync"] = {"command": PY + " -c \"open('synced.txt','w').write('{app}')\"", "check": PY + " -c \"print('all apps current')\""}
    cfg["local"]["command"] = {"check": PY + " -c \"print('project registry check OK')\""}
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    out = run([PY, S / "sync/scripts/sync_ds.py", "status"], d)
    check("all apps current" in out, "sync.check replaces status", out)
    run([PY, S / "sync/scripts/sync_ds.py", "apply", "--app", "acme-web"], d)
    check((d / "synced.txt").read_text() == "acme-web", "sync.command replaces apply")
    out = run([PY, S / "contribute/scripts/registry.py", "check"], d)
    check("project registry check OK" in out, "local.command.check replaces check", out)
    out = run([PY, S / "contribute/scripts/registry.py", "check", "--builtin"], d, expect=None)
    check("Registry" in out or "PENDING" in out, "--builtin keeps the kit's own check", out)

    # ---------- handoff package (feature, lock) ----------
    item = d / "docs/handover/1234"
    cfg["handoff"] = {"itemLabel": "PBI ", "grepLabels": ["Waiting for Figma"], "specFiles": {"legacy": ["old-archive.md"]},
                      "pre": PY + " -c \"import sys; open(sys.argv[1] + '/pre.txt', 'w').write('pre')\" {pkg}",
                      "post": PY + " -c \"import os,sys; print('post zip', os.path.exists(sys.argv[1]))\" {zip}"}
    cfg["email"] = {"demoLinks": False, "maxItems": 3}
    cfg["deploy"] = {"type": "static", "site": "https://prototypes.example.com"}
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    run([PY, S / "handoff/scripts/pkg.py", "init", "--pbi", "1234", "--title", "Tasks", "--version", "1.0.0", "--app", "acme-web",
         "--treatment", "lock"], d)
    pcj = json.loads((item / "pkg.json").read_text())
    check("ds_label" in pcj and "allow_when" in pcj["lock"] and "page_keys" in pcj["lock"], "init writes ds_label, allow_when, page_keys")
    pkg = item / "out" / "Design - 1234"
    shutil.copytree(d / "apps/acme-web", pkg / "prototype", ignore=shutil.ignore_patterns("_shell"))
    shutil.copytree(pkg / "prototype/settings", pkg / "prototype/notes")
    probe = ('<div id="probe" data-area="tasks"><button id="more" type="button">More</button>'
             '<button id="open-in" type="button" onclick="window.__o=!!window.open(\'settings/index.html\')">in</button>'
             '<button id="open-out" type="button" onclick="window.__o=!!window.open(\'notes/index.html\')">out</button>'
             '<div id="drop" style="height:40px">drop</div></div>'
             '<button id="outside" type="button" onclick="window.__clicked=1">outside</button>'
             '<a id="to-notes" href="notes/index.html">notes</a><a id="to-settings" href="settings/index.html">settings</a>'
             '<script>window.appNav={go:function(k){window.__nav=k;}};</script>')
    idx = pkg / "prototype/index.html"
    idx.write_text(idx.read_text().replace("</body>", probe + "\n</body>"))
    pcj.update({"figma_file": "https://www.figma.com/design/TESTKEY/acme-test", "figma_board": "1:1",
                "figma": {"S01": "1:2", "S02": "1:3", "S03": "1:4"}, "codes": "- S01–S03: screens.", "ds_label": ""})
    pcj["lock"].update({"pages": ["index.html", "settings/index.html"], "page_keys": {"home": "index.html", "settings": "settings/index.html",
                        "notes": "notes/index.html"},
                        "allow": ["[data-area=\"tasks\"]", ".app-nav", "#modeBtn", "[data-x-scope]"],
                        "allow_when": [{"sel": "#more", "hash": "^#/done"}], "nav_functions": ["appNav.go"],
                        "seed": {"localStorage": {"acme-web:notice": "seen"}},
                        "toast": {"class": "acme-toast", "close_class": "acme-toast-close", "icon": "<span class=\"ti\"></span>"}})
    write(item / "pkg.json", json.dumps(pcj, indent=1))
    out = run([PY, S / "handoff/scripts/pkg.py", "layer", "--config", item / "pkg.json", "--kind", "lock", "--into",
               pkg / "prototype/index.html", pkg / "prototype/settings/index.html"], d)
    check("injected into 2" in out and 'content="lock PBI 1234' in idx.read_text(), "layer lock: itemLabel in meta", out)

    # manifest (legacy alias + frame) and capture --only
    write(pkg / "prototype/frame.html", "<!doctype html><html><body><button id=\"inner\">inner</button></body></html>")
    idx.write_text(idx.read_text().replace("</body>", "<iframe id=\"fr\" src=\"frame.html\" title=\"frame\" style=\"width:200px;height:60px\"></iframe>\n</body>"))
    manifest = item / "manifest.js"
    write(manifest, "module.exports = { viewport: { width: 1280, height: 800 }, frames: { F: '#fr' }, screens: [\n"
          " { id: 'S01', name: 'Home', flow: 'f1', steps: [{ goto: 'prototype/index.html#/' }, { wait: 200 }],\n"
          "   pins: [{ ref: 'FR-01.1', sel: '#probe' }, { ref: 'FR-01.2', sel: 'F|#inner' }], next: [{ to: 'S02', action: 'Click \"in\"', trigger: '#open-in' }] },\n"
          " { id: 'S02', name: 'Home after a frame click', flow: 'f1', cont: 1, steps: [{ fclick: '#inner' }, { wait: 100 }], pins: [{ ref: 'FR-02.1', sel: '#more' }] },\n"
          " { id: 'S03', name: 'Settings', flow: 'f2', steps: [{ goto: 'prototype/settings/index.html#/' }], pins: [{ ref: 'FR-02.2', sel: 'main' }] } ] };\n")
    bad = item / "bad-manifest.js"
    write(bad, "module.exports = { screens: [{ id: 'S01', steps: [{ eclick: '#x' }], pins: [{ ref: 'R', sel: 'G|.y' }] }] };\n")
    srv, base = serve(pkg)
    try:
        if browser:
            out = run(["node", S / "annotate/scripts/capture.js", bad, d / "badshots", base], d, expect=1)
            check("frame not declared" in out and "G|.y" in out, "capture: undeclared frame is an ERROR", out)
            shots = item / "shots"
            out = run([PY, S / "handoff/scripts/pkg.py", "capture", "--manifest", manifest, "--shots", shots, "--base", base], d)
            scr = json.loads((shots / "screens.json").read_text())
            check(len(scr) == 3 and scr[1]["steps"][0] == {"click": "#inner", "in": "F"} and scr[0]["pins"][1]["found"],
                  "capture: legacy step alias fclick runs in frame F, F| pin found", out)
            before = {p.name: p.stat().st_mtime_ns for p in shots.glob("*.png")}
            out = run([PY, S / "handoff/scripts/pkg.py", "capture", "--manifest", manifest, "--shots", shots, "--base", base,
                       "--only", "S02"], d)
            after = {p.name: p.stat().st_mtime_ns for p in shots.glob("*.png")}
            check(after["S02.png"] != before["S02.png"] and after["S01.png"] == before["S01.png"]
                  and after["S03.png"] == before["S03.png"] and "Wrote 1 screen" in out, "capture --only: one image rewritten", out)
            # validate: plan from the capture manifest, desktop touch threshold
            out = run([PY, S / "validate/scripts/validation.py", "init", "--app", "acme-web", "--from-manifest", manifest, "--base", base], d)
            plan = json.loads((d / "docs/validation/acme-web/plan.json").read_text())
            check(len(plan["screens"]) == 3 and plan["screens"][1]["steps"][-2] == {"click": "#inner", "in": "F"}
                  and plan["url"] == base, "validate init --from-manifest", out)
            out = run([PY, S / "validate/scripts/validation.py", "run", "--app", "acme-web", "--viewports", "390,1280"], d, expect=None)
            check("Report:" in out, "validate run on the plan from the manifest", out)
            res = json.loads(sorted((d / "docs/validation/acme-web").glob("2*/results.json"))[-1].read_text())
            check(not any(it.get("fatal") for it in res["items"]), "validate: screen steps (frame click) run", json.dumps(res)[:2000])
            # lock behaviour in Chromium
            lock_js = d / "lock-test.js"
            write(lock_js, LOCK_TEST)
            out = run(["node", lock_js, base + "prototype/index.html#/"], d)
            res = json.loads(out.strip().splitlines()[-1])
            check(res["outsideBlocked"] and res["toastIcon"] and res["closeAria"], "lock: click outside -> DS toast with icon, close has aria-label", out)
            check(res["openIn"] and not res["openOut"], "lock: window.open resolved URL (in-package page allowed, other blocked)", out)
            check(res["moreBlocked"] and res["moreAllowedOnRoute"], "lock: allow_when per route", out)
            check(res["navSettings"] == "settings" and res["navNotes"] is None and res["navHome"] == "home", "lock: page_keys", out)
            check(res["linkNotesBlocked"] and not res["linkSettingsBlocked"], "lock: static links by full path, not by suffix", out)
            check(res["dragoverStopped"] and res["seed"] == "seen", "lock: dragover stopped, seed set", out)
    finally:
        srv.shutdown()

    # spec, requirements, README written by the packager (here: a minimal fixture)
    write(pkg / "spec/index.md", '---\npbi: "1234"\ntitle: "Tasks"\nversion: "1.0.0"\nds: "Acme DS 0.0.9"\nprototype: "prototype/index.html"\n---\n'
          "# Tasks\n\n| Unit | Name | Status | File |\n|---|---|---|---|\n| FR01 | Home | Active | [FR01](FR01.md) |\n| FR02 | More | Active | [FR02](FR02.md) |\n\n"
          "## Not matched\n\n- S03\n")
    write(pkg / "spec/FR01.md", "# FR01 · Home\n\n### S01 · Home\n\nRoute: `prototype/index.html#/`\nHow to reach: open the app.\n\n![S01](../screens/S01.png)\n")
    write(pkg / "spec/FR02.md", "# FR02 · More\n\n### S02 · Home after a frame click\n\nHow to reach: click inner.\n")
    write(pkg / "spec/old-archive.md", "# Old archive (legacy name)\n")
    write(pkg / "spec/flows.md", "# Wireflow\n\nImages are in `screens/<id>.webp`.\n\n## WF-01 · Home\n\nS01 → S02\n")
    write(pkg / "requirements/flows.json", json.dumps({"flows": [{"id": "WF-01", "name": "Home", "rows": [{"items": [["n", "S01"], ["e", "Click"], ["n", "S02"]]}]}]}))
    write(pkg / "requirements/changelog.md", "# Changelog\n\n## 1.0.0 · 2026-11-21\n- First release\n- Renamed spec/luu-tru.md\n")
    (pkg / "requirements/checklist-feature.csv").write_text(
        "Code,Feature,Group,Screen / location,Behaviour,Inputs,Expected result,Status,Dependencies\n"
        + "".join("F0%d,Feature %d,Tasks,S01,b,i,e,Full,\n" % (i, i) for i in range(1, 6)), encoding="utf-8-sig")
    (pkg / "requirements/checklist-qc.csv").write_text("Test ID,Steps\nTC1,x\n", encoding="utf-8-sig")
    write(pkg / "README.md", "# Design - 1234\n\nTasks v1.0.0. Read `AGENTS.md`, `spec/index.md`, `spec/gone.md`.\n")
    fin = [PY, S / "handoff/scripts/pkg.py", "finalize", "--pkg", pkg, "--shots", item / "shots", "--config", item / "pkg.json", "--zip"]
    if not browser:
        write(item / "shots/screens.json", json.dumps([{"id": "S01", "page": "prototype/index.html", "hash": "#/", "pins": []},
                                                     {"id": "S02", "page": "prototype/index.html", "hash": "#/", "pins": []},
                                                     {"id": "S03", "page": "prototype/settings/index.html", "hash": "#/", "pins": []}]))
    out = run(fin, d, expect=1)
    check("spec/gone.md is not in the package" in out and "ERROR:" in out, "finalize: missing file reference is an ERROR", out)
    check("WARN:" in out and "spec/luu-tru.md" in out, "finalize: changelog reference to an old file is a WARN", out)
    write(pkg / "README.md", "# Design - 1234\n\nTasks v1.0.0. Read `AGENTS.md`, `spec/index.md`.\n")
    out = run(fin, d)
    check("Acme DS 0.0.9" in out and "(from spec" in out, "finalize: DS label from spec frontmatter (pkg.json ds_label empty)", out)
    check("WARN:  DS label \"Acme DS 0.0.9\" but" in out, "finalize: DS label differs from the pages' <meta> -> WARN", out)
    check("checklist-qc.csv header differs" in out, "finalize: CSV header check", out)
    check("1 units" not in out and "2 units" in out, "spec: legacy special file is not a unit", out)
    check(out.count("WARN:") >= 3, "finalize prints every WARN line", out)
    check((pkg / "pre.txt").exists() and "post zip True" in out, "handoff.pre / handoff.post", out)
    agents = (pkg / "AGENTS.md").read_text()
    check("PBI 1234" in agents and '"Waiting for Figma"' in agents and "Acme DS 0.0.9" in agents, "AGENTS: itemLabel, grepLabels, DS label")
    check("screens/<id>.webp" not in (pkg / "spec/flows.md").read_text(), "finalize: image sentence replaced in flows.md")
    zp = item / "out" / "Design - 1234.zip"
    names = zipfile.ZipFile(zp).namelist()
    check(not [n for n in names if n.endswith(".js")], "zip has no .js file")
    cfg["handoff"]["dsLabelCheck"] = "error"
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    out = run(fin, d, expect=1)
    check("handoff.dsLabelCheck = error" in out, "handoff.dsLabelCheck = error stops", out)

    # ---------- share: no demo links, maxItems ----------
    out = run([PY, "-I", S / "share/scripts/draft_email.py", zp, "--app", "acme-web", "--feature", "[1234] Tasks",
               "--figma", "https://www.figma.com/design/TESTKEY/acme-test", "--demo", "https://prototypes.example.com/x/",
               "--out", d / "email"], d)
    body = (d / "email/body.txt").read_text()
    check("prototypes.example.com" not in body and "2. " in body and "more" in body.lower(),
          "email.demoLinks false: no demo link; email.maxItems", body)

    # ---------- wireflow demo links keep the page folder ----------
    fl = d / "flows-copy.json"
    write(fl, json.dumps({"flows": [{"id": "WF-01", "rows": [{"items": [["n", "S03"]]}]}]}))
    scr = d / "scr.json"
    write(scr, json.dumps([{"id": "S03", "page": "prototype/settings/index.html", "hash": "#/"}]))
    out = run([PY, "-I", S / "wireflow/scripts/demo_links.py", "fill", "--screens", scr, "--flows", fl, "--app", "acme-web",
               "--page-root", "prototype"], d)
    check("/apps/acme-web/settings/#/" in out, "demo links keep the page folder", out)

    print("\n%d checks passed." % len(OK))
    if keep:
        print("kept:", d)
    else:
        shutil.rmtree(d, ignore_errors=True)


LOCK_TEST = r"""
const { chromium } = require('playwright');
(async () => {
  const url = process.argv[2], b = await chromium.launch(), p = await b.newPage(), r = {};
  await p.goto(url); await p.waitForTimeout(300);
  r.seed = await p.evaluate(() => localStorage.getItem('acme-web:notice'));
  await p.click('#outside'); await p.waitForTimeout(100);
  r.outsideBlocked = !(await p.evaluate(() => window.__clicked));
  r.toastIcon = await p.evaluate(() => !!document.querySelector('.acme-toast .ti'));
  r.closeAria = await p.evaluate(() => { const x = document.querySelector('.acme-toast-close'); return !!(x && x.getAttribute('aria-label') && x.querySelector('svg')); });
  await p.click('#open-in'); r.openIn = await p.evaluate(() => window.__o);
  for (const pg of b.contexts()[0].pages()) if (pg !== p) await pg.close();
  await p.click('#open-out'); r.openOut = await p.evaluate(() => window.__o);
  r.moreBlocked = await p.evaluate(() => { let hit = true; const e = new MouseEvent('click', { bubbles: true, cancelable: true });
    document.getElementById('more').dispatchEvent(e); return e.defaultPrevented; });
  r.moreAllowedOnRoute = await p.evaluate(() => { history.replaceState(null, '', '#/done');
    const e = new MouseEvent('click', { bubbles: true, cancelable: true });
    document.getElementById('more').dispatchEvent(e); const ok = !e.defaultPrevented; history.replaceState(null, '', '#/'); return ok; });
  r.navSettings = await p.evaluate(() => { window.__nav = null; appNav.go('settings'); return window.__nav; });
  r.navNotes = await p.evaluate(() => { window.__nav = null; appNav.go('notes'); return window.__nav; });
  r.navHome = await p.evaluate(() => { window.__nav = null; appNav.go('home'); return window.__nav; });
  const linkBlocked = id => p.evaluate(i => { const e = new MouseEvent('click', { bubbles: true, cancelable: true });
    const a = document.getElementById(i); a.closest('#probe') || document.getElementById('probe').appendChild(a);
    a.dispatchEvent(e); return e.defaultPrevented; }, id);
  r.dragoverStopped = await p.evaluate(() => { let reached = false; document.addEventListener('dragover', () => { reached = true; });
    const e = new Event('dragover', { bubbles: true, cancelable: true }); document.getElementById('outside').dispatchEvent(e); return !reached; });
  r.linkNotesBlocked = await linkBlocked('to-notes');
  r.linkSettingsBlocked = await linkBlocked('to-settings');   /* last: an allowed link navigates away */
  await b.close();
  console.log(JSON.stringify(r));
})();
"""

if __name__ == "__main__":
    main()
