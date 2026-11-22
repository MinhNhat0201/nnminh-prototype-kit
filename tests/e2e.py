#!/usr/bin/env python3
"""End-to-end fixture test of the kit: builds a throw-away project in a temp folder and runs the scripts on it.

  python3 tests/e2e.py [--keep] [--no-browser]

Flow: adopt (DS profile acme) -> kickoff (multi-page html app, plain vue app with a DS Vue layer) -> prototype checks
(kitconf check, registry update/check, review audit with project checks) -> validate (plan built from the capture
manifest) -> annotate capture (--only, legacy step alias) -> handoff (layer lock, finalize with every check, zip)
-> share (email without demo links), plus one fixture per extension point (sync.command, local.command/fields,
review.extraChecks, handoff.pre/post, email.demoLinks, ds.json > components.vue, tailwind: false, skills hints),
the rules registry (every rules.py command, rule checks in review and validate), apps[].ds (a second DS profile),
apps[].type page + usedBy, handoff.specFields, email.template and the 0.8 handoff and validate fixes.
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
    [PY, KIT / "scripts/rules.py", "--selftest"],
    [PY, S / "share/scripts/draft_email.py", "--selftest"],
    [PY, S / "review/scripts/audit_map_tokens.py", "--selftest"],
    [PY, S / "annotate/scripts/spec_md.py", "--selftest"],
    [PY, S / "document/scripts/catalog.py", "--selftest"],
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
              ["node", S / "validate/scripts/validate.js", "--help"], [PY, KIT / "scripts/kitconf.py", "--help"],
              [PY, KIT / "scripts/rules.py", "--help"], [PY, S / "context/scripts/decisions.py", "--help"],
              [PY, S / "document/scripts/catalog.py", "--help"], [PY, S / "verify/scripts/verify.py", "--help"],
              [PY, S / "explore/scripts/explore.py", "--help"]):
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
    check((d / "rules/README.md").is_file(), "kickoff: creates the project rules folder", out)
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
        {"name": "A11y per app", "command": PY + " -c \"import sys; print('a11y', sys.argv[1], 'ok')\" {app}"},
        {"name": "Path per app", "command": PY + " -c \"import sys; print('x'); print('path', sys.argv[1])\" {path}", "parse": "^nothing"}]}
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

    # ---------- apps[].ds (second DS profile), apps[].type page + usedBy ----------
    mob = json.loads((d / "ds/acme/ds.json").read_text())
    shutil.copytree(d / "ds/acme", d / "ds/acme-mobile")
    mob.update(name="acme-mobile", label="Acme Mobile", version="3.1.0")
    mob.pop("components", None)
    write(d / "ds/acme-mobile/ds.json", json.dumps(mob, indent=1))
    cfg["apps"].append({"id": "acme-mobile", "name": "Acme Mobile", "path": "apps/acme-mobile", "ds": "ds/acme-mobile",
                        "platform": "mobile"})
    cfg["apps"].append({"id": "acme-page", "name": "Tasks page", "path": "pages/tasks", "stack": "vue", "type": "page",
                        "build": None, "usedBy": ["apps/acme-web/tasks.js"]})
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    out = run([PY, KIT / "scripts/kitconf.py", "check"], d)
    check("OK" in out, "kitconf check: apps[].ds and type page + usedBy are valid", out)
    out = run([PY, S / "kickoff/scripts/scaffold.py", "--app", "acme-mobile", "--name", "Acme Mobile"], d)
    mhtml = (d / "apps/acme-mobile/index.html").read_text()
    check("Acme Mobile 3.1.0" in out and "Acme Mobile 3.1.0" in mhtml, "kickoff: app built from its own DS profile (apps[].ds)", out)
    write(d / "pages/tasks/src/Tasks.vue", "<template><div class=\"tasks\" /></template>\n")
    write(d / "apps/acme-web/tasks.js", "/* built from pages/tasks */ const c = '#abcdef'; // Acme DS 0.0.1\n")
    out = run([PY, S / "sync/scripts/sync_ds.py", "status", "--builtin"], d)
    check("acme-mobile" in out and "ds/acme-mobile" in out and "3.1.0" in out, "sync status: apps[].ds profile and version", out)
    out = run([PY, KIT / "scripts/kitconf.py", "--app", "acme-mobile"], d)
    check('"label": "Acme Mobile"' in out, "kitconf --app: merged config with the app's profile", out)
    bad = dict(cfg, apps=cfg["apps"] + [{"id": "bad", "path": "x", "ds": "ds/none"}, {"id": "pg2", "path": "y", "type": "page"}])
    write(d / "kit.config.json", json.dumps(bad, indent=1))
    out = run([PY, KIT / "scripts/kitconf.py", "check"], d, expect=1)
    check("apps[].ds" in out and "type page needs usedBy" in out, "kitconf check: bad apps[].ds and page without usedBy", out)
    write(d / "kit.config.json", json.dumps(cfg, indent=1))

    # ---------- rules registry ----------
    R = [PY, KIT / "scripts/rules.py"]
    out = run(R + ["list", "--app", "acme-web", "--skill", "prototype"], d)
    check("STY-901" in out and "PAG-901" in out and "EML-901" not in out, "rules list: kit rules for app + skill (other skills' rules left out)", out)
    run([PY, S / "context/scripts/decisions.py", "add", "--title", "Legacy colours in the mobile app", "--status", "approved", "--by", "Lan"], d)
    out = run([PY, S / "context/scripts/decisions.py", "add", "--title", "Status chips", "--status", "approved", "--by", "Lan"], d)
    check("rules.py add --decision D-002" in out, "decisions: approved decision offers rules.py add", out)
    out = run(R + ["add", "--title", "No raw colours in app CSS", "--category", "styling", "--severity", "must", "--decision", "D-001",
                   "--skills", "prototype,review,validate", "--check", PY + " -c \"import sys; sys.exit(0 if sys.argv[1] != 'acme-web' else 1)\" {app}",
                   "--exception", "acme-mobile=Legacy colours until the rebuild=D-001", "--body", "Only DS tokens in app CSS.\n\nWhy: themes."], d)
    check("STY-001" in out and (d / "rules/styling").is_dir(), "rules add: next id, file, decision link, exception", out)
    out = run(R + ["add", "--title", "Status chips use the DS tag", "--category", "content", "--severity", "should", "--decision", "D-002",
                   "--check", PY + " -c \"print('2 chips off'); raise SystemExit(1)\"", "--body", "Chips are tags."], d)
    out = run(R + ["add", "--title", "Bad", "--category", "styling", "--severity", "must", "--applies-to", "nope"], d, expect=1)
    check("unknown app" in out, "rules add: refuses an unknown app", out)
    out = run(R + ["add", "--title", "Mobile keeps compact density", "--category", "density", "--severity", "should", "--layer", "app",
                   "--applies-to", "acme-mobile", "--overrides", "DEN-901", "--reason", "small screens", "--decision", "D-001", "--body", "Compact."], d)
    out = run(R + ["list", "--app", "acme-mobile"], d)
    check("EXCEPTION STY-001" in out and "OVERRIDDEN DEN-901 by DEN-001" in out, "rules list: app exception and app-layer override", out)
    out = run(R + ["list", "--app", "acme-web", "--json"], d)
    js = json.loads(out)
    check(any(r["id"] == "STY-001" and r["text"].startswith("Only DS tokens") for r in js["rules"]), "rules list --json: rule text", out)
    out = run(R + ["explain", "STY-001", "--app", "acme-mobile"], d)
    check("Lan" in out and "Legacy colours until the rebuild" in out and "acme-mobile" in out, "rules explain: decision, exception, app state", out)
    out = run(R + ["check", "--app", "acme-web"], d, expect=1)
    check("FAIL STY-001" in out and "1 must" in out, "rules check: failing must rule exits 1", out)
    out = run(R + ["check", "--app", "acme-vue", "--json", "-"], d, expect=0)
    check(any(x["id"] == "CNT-001" and not x["ok"] for x in json.loads(out)), "rules check --json: should failure does not fail the run", out)
    out = run(R + ["coverage"], d)
    check("| styling | 1 |" in out and "acme-mobile" in out, "rules coverage", out)
    out = run(R + ["conflicts"], d)
    check("Rules OK" in out, "rules conflicts: clean registry", out)
    write(d / "rules/styling/STY-099-broken.md", "---\nid: STY-099\ntitle: Broken\ncategory: styling\nlayer: project\nseverity: must\n"
          "status: superseded\nsince: 2026-01-01\ndecision: D-009\nskills: [nope]\n---\nx\n")
    out = run(R + ["conflicts"], d, expect=1)
    check("superseded without superseded_by" in out and "unknown skill" in out and "D-009" in out, "rules conflicts: errors found", out)
    (d / "rules/styling/STY-099-broken.md").unlink()
    run(R + ["export", "--format", "claude", "--into", "CLAUDE.md"], d)
    run(R + ["export", "--format", "claude", "--into", "CLAUDE.md"], d)
    cm = (d / "CLAUDE.md").read_text()
    check(cm.count("<!-- kit:rules:begin -->") == 1 and "**STY-001** (must)" in cm, "rules export claude: block in CLAUDE.md, idempotent")
    run(R + ["export", "--format", "html", "--app", "acme-mobile", "--out", "docs/rules.html"], d)
    rh = (d / "docs/rules.html").read_text()
    check("<main>" in rh and "STY-001" in rh and "DEN-001" in rh, "rules export html for an app")
    write(d / "docs/old-rules.md", "# Old rules\n\n## Assets\n\n- Images live in files, never base64.\n- Logos stay as SVG.\n\n"
          "## Flags\n\nSome intro.\n\n1. Every flag has a note with the date.\n")
    out = run(R + ["import-md", "docs/old-rules.md", "--map", "flags=flags"], d)
    check("3 draft rule(s)" in out and (d / "rules/_import-review.md").is_file() and (d / "rules/assets").is_dir(),
          "rules import-md: drafts and review list", out)
    out = run(R + ["conflicts"], d)
    check("Rules OK" in out, "rules conflicts: imported drafts are valid proposed rules", out)
    out = run(R + ["add", "--title", "Tokens and no overrides", "--category", "styling", "--severity", "must", "--decision", "D-001",
                   "--body", "Tokens, no overrides."], d)
    run(R + ["supersede", "STY-001", "--by", "STY-002", "--decision", "D-001"], d)
    out = run(R + ["show", "STY-001"], d)
    check("STY-002" in out, "rules supersede: old rule points to the successor", out)
    run(R + ["except", "STY-002", "--app", "acme-mobile", "--note", "Legacy colours until the rebuild", "--decision", "D-001"], d)
    run(R + ["deprecate", "AST-001", "--reason", "covered by the asset pipeline"], d)
    out = run(R + ["list", "--status", "deprecated"], d)
    check("AST-001" in out, "rules deprecate", out)
    out = run(R + ["deprecate", "STY-901", "--reason", "x"], d, expect=1)
    check("read-only" in out, "rules: kit layer is read-only", out)
    run(R + ["add", "--title", "No raw colours in app CSS", "--category", "styling", "--severity", "must", "--decision", "D-001",
             "--skills", "review,validate", "--check", PY + " -c \"import sys; sys.exit(0 if sys.argv[1] != 'acme-web' else 1)\" {app}",
             "--body", "Only DS tokens in app CSS."], d)

    # ---------- extension points: sync.command, local.command ----------
    cfg["sync"] = {"command": PY + " -c \"open('synced.txt','w').write('{app}')\"", "check": PY + " -c \"print('all apps current')\""}
    cfg["local"]["command"] = {"check": PY + " -c \"print('project registry check OK')\""}
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    out = run([PY, S / "review/scripts/audit_app.py", "--json", d / "audit.json"], d)
    aud = {x["app"]: x for x in json.loads((d / "audit.json").read_text()) if "app" in x}
    check(aud["acme-mobile"]["ds"] == "Acme Mobile 3.1.0" and aud["acme-web"]["ds"].startswith("Acme DS"), "review: each app against its own DS profile", out)
    check(any(x.get("rule") == "STY-003" and x["level"] == "deviation" for x in aud["acme-web"]["extra"])
          and any(x.get("rule") == "STY-003" and x["level"] == "pass" for x in aud["acme-vue"]["extra"]), "review: rule check rows per app", out)
    check("abcdef" not in json.dumps(aud["acme-web"]["hard"]) and not [v for v in aud["acme-web"]["version"]["declared"] if "0.0.1" in v],
          "review: build output of a page app skipped (usedBy)", out)
    check("path apps/acme-web" in out, "review.extraChecks: {path}", out)
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
    cfg["handoff"] = {"itemLabel": "PBI ", "grepLabels": ["Waiting for Figma"], "specFields": {"ds": "acmeVersion"},
                      "specFiles": {"legacy": {"archive": ["old-archive.md"], "crossPage": ["old-cross.md"]}},
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
             '<button id="open-branch" type="button" onclick="window.__o=!!window.open(\'settings/index.html#branch\')">branch</button>'
             '<div id="drop" style="height:40px">drop</div>'
             '<span id="sr-text" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap">'
             'Text for screen readers only, long enough to be clipped</span>'
             '<input type="file" id="fin" aria-label="file" style="position:absolute;width:1px;height:1px;opacity:0">'
             '<p>Read the <a id="inl" href="#/terms">terms</a> before you start.</p></div>'
             '<button id="outside" type="button" onclick="window.__clicked=1">outside</button>'
             '<a id="to-notes" href="notes/index.html">notes</a><a id="to-settings" href="settings/index.html">settings</a>'
             '<script>window.appNav={go:function(k){window.__nav=k;}};</script>')
    idx = pkg / "prototype/index.html"
    idx.write_text(idx.read_text().replace("</body>", probe + "\n</body>")
                   .replace("</head>", "<script>window.__seedAtLoad = localStorage.getItem('acme-web:notice');</script>\n</head>", 1))
    pcj.update({"figma_file": "https://www.figma.com/design/TESTKEY/acme-test", "figma_board": "1:1",
                "figma": {"S01": "1:2", "S02": "1:3", "S03": "1:4"}, "codes": "- S01–S03: screens.", "ds_label": ""})
    pcj["lock"].update({"pages": ["index.html", "settings/index.html"], "page_keys": {"home": "index.html", "settings": "settings/index.html",
                        "notes": "notes/index.html"},
                        "allow": ["[data-area=\"tasks\"]", ".app-nav", "#modeBtn", "[data-x-scope]"],
                        "allow_when": [{"sel": "#more", "hash": "^#/done"}], "nav_functions": ["appNav.go"], "open_block": "#branch",
                        "seed": {"localStorage": {"acme-web:notice": "seen"}},
                        "toast": {"class": "acme-toast", "close_class": "acme-toast-close", "icon": "<span class=\"ti\"></span>"}})
    write(item / "pkg.json", json.dumps(pcj, indent=1))
    out = run([PY, S / "handoff/scripts/pkg.py", "layer", "--config", item / "pkg.json", "--kind", "lock", "--into",
               pkg / "prototype/index.html", pkg / "prototype/settings/index.html"], d)
    check("injected into 2" in out and 'content="lock PBI 1234' in idx.read_text(), "layer lock: itemLabel in meta", out)
    h = idx.read_text()
    check(h.index('id="x-handover-seed"') < h.index("__seedAtLoad"), "layer: seed script injected in <head> before app scripts (K-1)")

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
            check(plan["timeout"] == 8000, "validate plan: step timeout as capture.js (K-10)", out)
            out = run([PY, S / "validate/scripts/validation.py", "run", "--app", "acme-web", "--viewports", "390,1280"], d, expect=None)
            check("Report:" in out, "validate run on the plan from the manifest", out)
            res = json.loads(sorted((d / "docs/validation/acme-web").glob("2*/results.json"))[-1].read_text())
            check(not any(it.get("fatal") for it in res["items"]), "validate: screen steps (frame click) run", json.dumps(res)[:2000])
            phone = [it for it in res["items"] if it["vp"] == 390]
            txt = json.dumps([(it.get("touch"), it.get("clipped")) for it in phone])
            check(phone and "#fin" not in txt and "#inl" not in txt and "#sr-text" not in txt,
                  "validate: no 'needs a human' for screen-reader text, hidden file input, link in a sentence (K-11)", txt)
            rep = sorted((d / "docs/validation/acme-web").glob("2*/report.md"))[-1].read_text()
            check(any(x["id"] == "STY-003" and not x["ok"] for x in res.get("rules", [])) and "STY-003" in rep,
                  "validate: rules registry checks in the report", rep[:1500])
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
            check(res["seedAtLoad"] == "seen", "lock: seed set before app code reads it (K-1)", out)
            check(res["openBranch"] is False, "lock: open_block blocks an in-package page by hash (K-4)", out)
    finally:
        srv.shutdown()

    # spec, requirements, README written by the packager (here: a minimal fixture)
    write(pkg / "spec/index.md", '---\npbi: "1234"\ntitle: "Tasks"\nversion: "1.0.0"\nacmeVersion: "0.0.9"\nprototype: "prototype/index.html"\n---\n'
          "# Tasks\n\n| Unit | Name | Status | File |\n|---|---|---|---|\n| FR01 | Home | Active | [FR01](FR01.md) |\n| FR02 | More | Active | [FR02](FR02.md) |\n\n"
          "## Not matched\n\n- S03\n")
    write(pkg / "spec/FR01.md", "# FR01 · Home\n\n### S01 · Home\n\nRoute: `prototype/index.html#/`\nHow to reach: open the app.\n\n![S01](../screens/S01.png)\n")
    write(pkg / "spec/FR02.md", "# FR02 · More\n\n### S02 · Home after a frame click\n\nHow to reach: click inner.\n")
    write(pkg / "spec/old-archive.md", "# Old archive (legacy name)\n")
    write(pkg / "spec/old-cross.md", "# Cross-page contract (legacy name)\n")
    write(pkg / "spec/flows.md", "# Wireflow\n\nEach step: screen → action → screen. Images are in `screens/<id>.webp`. "
          "Spec in [index](index.md).\n\n## WF-01 · Home\n\nS01 → S02\n")
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
    fl = (pkg / "spec/flows.md").read_text()
    check("screens/<id>.webp" not in fl and "Each step: screen → action → screen. " in fl and "Spec in [index](index.md)." in fl,
          "finalize: only the image sentence replaced in flows.md (K-2)", fl)
    check("spec/old-cross.md" in agents, "AGENTS: Dev path points at the legacy cross-page file (K-3)", agents)
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

    # ---------- share: project email template (email.template, {language} in the path) ----------
    write(d / "docs/mail-en.md", "{greeting}\n\n{intro}\n\nFigma: {figma}\n\n{sections}\n\nFile: {attachment}. {nope}\n\nBest,\n{signature}\n")
    cfg["email"]["template"] = "docs/mail-{language}.md"
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    run([PY, KIT / "scripts/kitconf.py", "check"], d)
    out = run([PY, "-I", S / "share/scripts/draft_email.py", zp, "--app", "acme-web", "--feature", "[1234] Tasks",
               "--figma", "https://www.figma.com/design/TESTKEY/acme-test", "--signature", "Designer", "--out", d / "email2"], d)
    body, em = (d / "email2/body.txt").read_text(), json.loads((d / "email2/email.json").read_text())
    check(body.startswith("Hi") and "Figma: https://www.figma.com/design/TESTKEY/acme-test" in body and "1. " not in body
          and "File: Design - 1234.zip" in body and body.rstrip().endswith("Designer") and "{nope}" in body
          and '<a href="https://www.figma.com/design/TESTKEY/acme-test">' in em["htmlBody"] and "unknown placeholders" in out,
          "email.template: project layout, {language}, HTML built, unknown placeholder kept with a NOTE", body + out)
    write(d / "docs/mail.html", "<style>p{margin:0}</style><p>{greeting}</p><p>Figma: {figma}</p>{sections}<p>{thanks}</p>")
    out = run([PY, "-I", S / "share/scripts/draft_email.py", zp, "--app", "acme-web", "--feature", "[1234] Tasks", "--template", "docs/mail.html",
               "--figma", "https://www.figma.com/design/TESTKEY/acme-test", "--out", d / "email3"], d)
    em = json.loads((d / "email3/email.json").read_text())
    check(em["htmlBody"].startswith("<style>p{margin:0}</style>") and "Figma: https://www.figma.com/design/TESTKEY/acme-test" in em["body"],
          "email.template .html: HTML body from the template, plain body from its text", json.dumps(em)[:1500])

    # ---------- wireflow demo links keep the page folder ----------
    fl = d / "flows-copy.json"
    write(fl, json.dumps({"flows": [{"id": "WF-01", "rows": [{"items": [["n", "S03"]]}]}]}))
    scr = d / "scr.json"
    write(scr, json.dumps([{"id": "S03", "page": "prototype/settings/index.html", "hash": "#/"}]))
    out = run([PY, "-I", S / "wireflow/scripts/demo_links.py", "fill", "--screens", scr, "--flows", fl, "--app", "acme-web",
               "--page-root", "prototype"], d)
    check("/apps/acme-web/settings/#/" in out, "demo links keep the page folder", out)

    # ---------- 0.10 ----------
    # rules: skipped checks (server down, exit 77, SKIP line), activity groups, rules.from inheritance, import-md --layer ds
    cfg = json.loads((d / "kit.config.json").read_text())
    run(R + ["add", "--title", "Accessibility script", "--category", "a11y", "--severity", "should", "--decision", "D-001",
             "--skills", "review,validate", "--check", "curl -s http://127.0.0.1:9/apps/{app}/", "--body", "Run the a11y script."], d)
    run(R + ["add", "--title", "Html apps only", "--category", "build", "--severity", "must", "--decision", "D-001", "--skills", "review",
             "--check", PY + " -c \"import sys; print('SKIPPED - not an html app') if sys.argv[1] == 'acme-vue' else None\" {app}",
             "--body", "Only html apps."], d)
    run(R + ["add", "--title", "Branch per change", "--category", "process", "--severity", "must", "--decision", "D-001", "--skills", "pr",
             "--body", "One branch per change."], d)
    out = run(R + ["check", "--app", "acme-vue", "--skill", "review"], d, expect=None)
    check("skip A11Y-001" in out and "not reachable" in out and "skip BLD-001" in out and "not an html app" in out
          and "skipped" in out.splitlines()[-1], "rules check: skipped status with the reason (server down, SKIP line)", out)
    js = json.loads(run(R + ["check", "--app", "acme-web", "--id", "A11Y-001", "--json", "-"], d))
    check(js and js[0]["status"] == "skipped" and js[0]["ok"] is True, "rules check --json: status skipped, ok true", json.dumps(js))
    out = run(R + ["coverage"], d)
    check("need a running server" in out, "rules coverage: checks that need a server", out)
    out_p, out_pr = run(R + ["list", "--skill", "prototype", "--brief"], d), run(R + ["list", "--skill", "pr", "--brief"], d)
    check("PRC-001" not in out_p and "PRC-001" in out_pr, "rules: activity group pr stays out of list --skill prototype", out_p + out_pr)
    write(d / "ds/acme/rules/styling/STY-500-radius-tokens.md", "---\nid: STY-500\ntitle: Radius tokens\ncategory: styling\nlayer: ds\n"
          "severity: should\nstatus: active\nsince: 2026-01-01\n---\nUse radius tokens.\n")
    mob = json.loads((d / "ds/acme-mobile/ds.json").read_text())
    mob["rules"] = {"file": "rules.md", "from": "../acme"}
    write(d / "ds/acme-mobile/ds.json", json.dumps(mob, indent=1))
    out = run(R + ["list", "--app", "acme-mobile", "--brief"], d)
    out2 = run(R + ["conflicts"], d, expect=None)   # earlier steps left a deprecated draft with Unconfirmed dates on purpose
    check("STY-500" in out and "STY-500" not in out2 and "duplicate" not in out2, "rules.from: the mobile profile inherits the DS rules, no duplicate ids", out + out2)
    write(d / "docs/ds-rules.md", "# DS rules\n\n## Styling\n\n- Never set `FLAG_NAME` by hand: the `/* LOCAL: x */` block owns it.\n")
    out = run(R + ["import-md", "docs/ds-rules.md", "--layer", "ds"], d)
    drafts = list((d / "ds/acme/rules/styling").glob("STY-501-*.md"))
    check(drafts and "severity: must" in drafts[0].read_text() and "FLAG_NAME" in drafts[0].read_text()
          and "/* LOCAL: x */" in drafts[0].read_text(), "rules import-md --layer ds: DS folder, must inferred, code spans kept", out)
    drafts[0].unlink()

    # css.load link: kickoff links one DS file, review treats it as DS, built-in sync rewrites the file
    cfg["apps"].append({"id": "acme-link", "name": "Acme Link", "path": "apps/acme-link", "css": {"load": "link", "linkPath": "acme-ds.css"}})
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    out = run([PY, S / "kickoff/scripts/scaffold.py", "--app", "acme-link", "--name", "Acme Link"], d)
    lh = (d / "apps/acme-link/index.html").read_text()
    check('<link rel="stylesheet" href="acme-ds.css">' in lh and "@ds:begin" not in lh and (d / "apps/acme-link/acme-ds.css").is_file(),
          "css.load link: kickoff writes one DS file and links it", lh[:600])
    write(d / "apps/acme-link/acme-ds.css", "/* stale */\n")
    out = run([PY, S / "sync/scripts/sync_ds.py", "apply", "--app", "acme-link", "--builtin"], d)
    check("acme-ds.css" in out and len((d / "apps/acme-link/acme-ds.css").read_text()) > 1000, "css.load link: built-in sync rewrites the linked file", out)
    out = run([PY, S / "review/scripts/audit_app.py", "acme-link", "--json", d / "audit-link.json", "--no-extra", "--no-rules"], d)
    al = json.loads((d / "audit-link.json").read_text())[0]
    check(al["tokens"]["embedded"] > 0 and al["hard"]["hex"] == 0 and al["override"]["rules"] == 0, "css.load link: review treats the linked file as DS CSS", out)

    # sync.prepare / sync.post around sync.command, and the change report (files, LOCAL blocks)
    edit = "import pathlib; p=pathlib.Path('apps/acme-web/index.html'); p.write_text(p.read_text().replace('display: grid','display: flex'))"
    cfg["sync"] = {"prepare": PY + " -c \"open('order.txt','a').write('prepare ')\"",
                   "command": PY + " -c \"open('order.txt','a').write('sync '); " + edit.replace("'", "\\'").replace("\\'", "'") + "\"",
                   "post": PY + " -c \"open('order.txt','a').write('post')\""}
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    out = run([PY, S / "sync/scripts/sync_ds.py", "apply", "--app", "acme-web"], d)
    check((d / "order.txt").read_text() == "prepare sync post" and "apps/acme-web/index.html" in out and "LOCAL block changed: Drop zone" in out,
          "sync.prepare / sync.post run around sync.command; changed files and LOCAL blocks listed", out)

    # review: apps[].generated skipped, identical rules in a source and its copy count once
    write(d / "apps/acme-web/_shell/extra.css", ".x-gen { color: #13579b; }\n")
    write(d / "apps/acme-web/shared/gen.css", "/* built */\n.x-gen{color:#13579b}\n.x-only-gen{color:#2468ac}\n")
    out = run([PY, S / "review/scripts/audit_app.py", "acme-web", "--json", d / "a1.json", "--no-extra", "--no-rules"], d)
    h1 = json.loads((d / "a1.json").read_text())[0]["hard"]
    cfg["apps"][0]["generated"] = ["apps/acme-web/shared/**"]
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    run([PY, KIT / "scripts/kitconf.py", "check"], d)
    run([PY, S / "review/scripts/audit_app.py", "acme-web", "--json", d / "a2.json", "--no-extra", "--no-rules"], d)
    h2 = json.loads((d / "a2.json").read_text())[0]["hard"]
    top1, top2 = dict(h1["top_hex"]), dict(h2["top_hex"])
    check(top1.get("#13579b") == 1 and top1.get("#2468ac") == 1 and top2.get("#13579b") == 1 and "#2468ac" not in top2,
          "review: identical rules count once; apps[].generated files are skipped", json.dumps([h1["top_hex"], h2["top_hex"]]))

    # validate init reads the app; --dir keeps the plan outside paths.validation
    out = run([PY, S / "validate/scripts/validation.py", "init", "--app", "acme-web", "--dir", d / "valdir"], d)
    vp = json.loads((d / "valdir/plan.json").read_text())
    check(len(vp["screens"]) >= 2 and any(s["route"].startswith("settings/") for s in vp["screens"]),
          "validate init: starter plan read from the app, written to --dir", out)

    # prototype.post through the generic hook runner; nothing set = nothing run
    out = run([PY, KIT / "scripts/kitconf.py", "hook", "prototype.post", "--app", "acme-web"], d)
    check("not set" in out, "kitconf hook: an unset project command runs nothing", out)
    cfg["prototype"] = {"post": PY + " -c \"import sys; print('posted', sys.argv[1])\" {app}"}
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    out = run([PY, KIT / "scripts/kitconf.py", "hook", "prototype.post", "--app", "acme-web"], d)
    check("posted acme-web" in out and "exit code 0" in out, "prototype.post: project command with {app}, output and exit code", out)

    # handoff: pkg.py proto copies pages and only the files they load
    write(d / "apps/acme-web/assets/used.png", "png")
    write(d / "apps/acme-web/assets/unused.png", "png")
    home2 = d / "apps/acme-web/index.html"
    home2.write_text(home2.read_text().replace("</body>", '<img src="assets/used.png" alt="">\n</body>', 1))
    out = run([PY, S / "handoff/scripts/pkg.py", "proto", "--app", "acme-web", "--pages", "index.html", "--into", d / "proto-copy"], d)
    check((d / "proto-copy/assets/used.png").is_file() and not (d / "proto-copy/assets/unused.png").exists()
          and not (d / "proto-copy/settings/index.html").exists() and "settings/index.html" in out,
          "pkg.py proto: pages plus the files they load, other pages left out", out)

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
  await p.click('#open-branch'); r.openBranch = await p.evaluate(() => window.__o);
  for (const pg of b.contexts()[0].pages()) if (pg !== p) await pg.close();
  r.seedAtLoad = await p.evaluate(() => window.__seedAtLoad);
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
