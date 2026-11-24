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
    [PY, S / "wireflow/scripts/figma_wireflow.py", "--selftest"],
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
    [PY, S / "define/scripts/extract_rules.py", "--selftest"],
    ["node", S / "annotate/scripts/capture.js", "--selftest"],
    [PY, S / "mockup/scripts/spec_audit.py", "--selftest"],
    ["node", S / "mockup/scripts/audit_selftest.js"],
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
              [PY, S / "define/scripts/extract_rules.py", "--help"],
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
    # review of a page app: DS version and DS CSS from the host, DS Vue use through the vite alias, App.vue no rebuild
    write(d / "pages/tasks/vite.config.ts", 'export default { resolve: { alias: { "@ds-vue": fileURLToPath(new URL("../../packages/acme-vue", import.meta.url)) } } }\n')
    write(d / "pages/tasks/src/App.vue", '<script setup>import AcmeButton from "@ds-vue/AcmeButton.vue"</script>\n'
                                         '<template><AcmeButton>Go</AcmeButton><Tasks /></template>\n')
    write(d / "packages/acme-vue/demo/App.vue", "<template><div /></template>\n")
    out = run([PY, S / "review/scripts/audit_app.py", "acme-page", "--json", d / "audit-page.json", "--no-extra", "--no-rules"], d)
    ap = json.loads((d / "audit-page.json").read_text())[0]
    check(ap["version"]["app"] and not ap["version"]["behind"] and (ap["tokens"]["embedded"] or ap["tokens"]["imported"])
          and ap["host"]["apps"] == ["acme-web"] and ap["host"]["pages"] == ["apps/acme-web/"] and "apps/acme-web/" in out,
          "review: page app reads the DS version and DS CSS from its host app and names the host page", out)
    check(ap["dsvue"]["used"] == [["AcmeButton", 1]] and ap["dsvue"]["rebuilt"] == [],
          "review: page app counts DS Vue imports through the alias; App.vue is no rebuilt component", json.dumps(ap["dsvue"]))
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
    sett = pkg / "prototype/settings/index.html"
    sett.write_text(sett.read_text().replace("</body>", "<script>window.X={nav:function(p){window.__nav=p;}};</script>\n</body>", 1))
    pcj.update({"figma_file": "https://www.figma.com/design/TESTKEY/acme-test", "figma_board": "1:1",
                "figma": {"S01": "1:2", "S02": "1:3", "S03": "1:4"}, "codes": "- S01–S03: screens.", "ds_label": ""})
    pcj["lock"].update({"pages": ["index.html", "settings/index.html"], "page_keys": {"home": "index.html", "settings": "settings/index.html",
                        "notes": "notes/index.html"},
                        "allow": ["[data-area=\"tasks\"]", ".app-nav", "#modeBtn", "[data-x-scope]"],
                        "allow_when": [{"sel": "#more", "hash": "^#/done"}], "nav_functions": ["appNav.go", {"name": "X.nav", "base": "app"}], "open_block": "#branch",
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
            # capture: reload after a hash-only goto (K-F10), short state with noWait + at (K-F11), pointer/focus reset (K-B1)
            write(pkg / "k-test/k.html", "<!doctype html><html><head><style>#hov{background:rgb(1,2,3);color:rgb(1,2,3)}"
                  "#hov:hover{background:rgb(4,5,6)}#hov:focus{color:rgb(7,8,9)}</style></head><body>"
                  "<p id=\"val\"></p><div id=\"sk\">loading</div><button id=\"hov\" type=\"button\">hover me</button>"
                  "<script>document.getElementById('val').textContent='v=' + (localStorage.getItem('k') || 'none');"
                  "setTimeout(function(){document.getElementById('sk').remove();}, 700);</script></body></html>")
            km = item / "k-manifest.js"
            write(km, "module.exports = { viewport: { width: 600, height: 400 }, scale: 1, screens: [\n"
                  " { id: 'K1', flow: 'k', steps: [{ goto: 'k-test/k.html#/a' }, { eval: \"localStorage.setItem('k','set')\" },"
                  " { goto: 'k-test/k.html#/', reload: true }], pins: [{ ref: 'R', sel: '#val' }] },\n"
                  " { id: 'K2', flow: 'k', cont: 1, at: 0, steps: [{ reload: 1, noWait: true }, { waitFor: '#sk' }], pins: [{ ref: 'R', sel: '#sk' }] },\n"
                  " { id: 'K3', flow: 'k', cont: 1, steps: [{ wait: 900 }, { click: '#hov' }], pins: [{ ref: 'R', sel: '#hov' }] },\n"
                  " { id: 'K4', flow: 'k', cont: 1, steps: [{ hover: '#hov' }], pins: [{ ref: 'R', sel: '#hov' }] } ] };\n")
            out = run(["node", S / "annotate/scripts/capture.js", km, d / "kshots", base], d)
            ks = {x["id"]: x for x in json.loads((d / "kshots/screens.json").read_text())}
            check(ks["K1"]["pins"][0]["style"]["text"] == "v=set", "capture: goto with reload: true after a hash-only change (K-F10)", out)
            check(ks["K2"]["pins"][0]["found"] and ks["K2"]["at"] == 0 and (d / "kshots/K2.png").is_file(),
                  "capture: noWait + at captures a short state (K-F11)", json.dumps(ks["K2"])[:800])
            p3, p4 = ks["K3"]["pins"][0]["style"]["props"], ks["K4"]["pins"][0]["style"]["props"]
            check(p3["backgroundColor"] == "rgb(1, 2, 3)" and p3["color"] == "rgb(1, 2, 3)" and p4["backgroundColor"] == "rgb(4, 5, 6)",
                  "capture: pointer off the page and focus blurred before the shot; a hover step keeps its pointer (K-B1)",
                  json.dumps([p3, p4]))
            shutil.rmtree(pkg / "k-test")
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
            nav_js = d / "lock-nav-app.js"
            write(nav_js, LOCK_NAV_APP_TEST)
            out = run(["node", nav_js, base + "prototype/settings/index.html#/"], d)
            res = json.loads(out.strip().splitlines()[-1])
            check(res["self"] == "settings/index.html#/y" and res["home"] == "index.html#/x" and res["notes"] is None,
                  "lock: nav_functions base app resolves paths from the app root, not the page (K-F15)", out)
    finally:
        srv.shutdown()

    # spec, requirements, README written by the packager (here: a minimal fixture)
    write(pkg / "spec/index.md", '---\npbi: "1234"\ntitle: "Tasks"\nversion: "1.0.0"\nacmeVersion: "0.0.9"\nprototype: "prototype/index.html"\n---\n'
          "# Tasks\n\n| Unit | Name | Status | File |\n|---|---|---|---|\n| FR01 | Home | Active | [FR01](FR01.md) |\n| FR02 | More | Active | [FR02](FR02.md) |\n\n"
          "## Not matched\n\n- S03\n")
    write(pkg / "spec/FR01.md", "# FR01 · Home\n\n### S01 · Home\n\nRoute: `prototype/index.html#/`\nHow to reach: open the app.\n\n![S01](../screens/S01.png)\n")
    write(pkg / "spec/FR02.md", "# FR02 · More\n\n### S02 · Home after a frame click\n\nHow to reach: click inner.\nFigma: none yet\n")
    ix = pkg / "spec/index.md"
    ix.write_text(ix.read_text().replace("## Not matched", "## Screens\n\n| Code | Name | Page · route | Figma | Spec |\n|---|---|---|---|---|\n"
                                         "| S01 | Home | `index.html#/` | — | FR01 |\n\n## Not matched"))
    # issue 33: a unit dropped in this version (status line in English) is archived by finalize
    write(pkg / "spec/FR-03.md", "# FR-03 · Bulk edit\nStatus: Dropped in 1.0.0\n\n## Business rules\n1. **FR-03.1** Edit many.\n")
    ix.write_text(ix.read_text().replace("| FR02 | More | Active | [FR02](FR02.md) |\n",
                                         "| FR02 | More | Active | [FR02](FR02.md) |\n| FR-03 | Bulk edit | — | [FR-03](FR-03.md) |\n"))
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
    out = run([PY, "-I", S / "wireflow/scripts/demo_links.py", "fill", "--screens", item / "shots/screens.json",
               "--flows", pkg / "requirements/flows.json", "--app", "acme-web", "--page-root", "prototype"], d)
    fmd = (pkg / "spec/flows.md").read_text()
    check("## WF-01 · Home\n\nOpen demo: [WF-01](https://prototypes.example.com/apps/acme-web/#/)" in fmd and "Wrote demo links" in out,
          "demo_links fill writes the link into spec/flows.md too (K-F14)", fmd + out)
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
    oa, ixs = (pkg / "spec/old-archive.md").read_text(), (pkg / "spec/index.md").read_text()
    check(not (pkg / "spec/FR-03.md").exists() and '<a id="fr-03"></a>' in oa and "[FR-03](old-archive.md#fr-03)" in ixs
          and "FR-03" in agents and "looks dropped" not in out, "finalize: a unit marked dropped is moved to the archive file (#33)", oa + ixs + out)
    fr2, ixs = (pkg / "spec/FR02.md").read_text(), (pkg / "spec/index.md").read_text()
    check("Figma: [S02](https://www.figma.com/design/TESTKEY/acme-test?node-id=1-3)" in fr2 and "none yet" not in fr2
          and "| S01 | Home | `index.html#/` | [Figma](https://www.figma.com/design/TESTKEY/acme-test?node-id=1-2) | FR01 |" in ixs,
          "finalize: Figma lines and the Figma column of spec/index.md refreshed from the screen map (K-B4)", fr2 + ixs)
    zp = item / "out" / "Design - 1234.zip"
    names = zipfile.ZipFile(zp).namelist()
    check(not [n for n in names if n.endswith(".js")], "zip has no .js file")
    # K-B5: draft awaiting Figma (a screen without a node), then relink fills the links and re-zips, nothing else
    pcj = json.loads((item / "pkg.json").read_text())
    check(pcj.get("status") == "final", "finalize: pkg.json > status final", json.dumps(pcj)[:400])
    del pcj["figma"]["S03"]
    write(item / "pkg.json", json.dumps(pcj, indent=1))
    out = run(fin, d, expect=1)
    check("--allow-missing-figma" in out and "S03" in out, "finalize: screen without a Figma node stops", out)
    out = run(fin + ["--allow-missing-figma"], d)
    pcj = json.loads((item / "pkg.json").read_text())
    check(pcj["status"] == "awaiting-figma" and pcj["awaiting_figma"] == ["S03"] and "pkg.py relink" in out,
          "finalize --allow-missing-figma: status awaiting-figma, relink named (K-B5)", out)
    sj = json.loads((pkg / "screens/screens.json").read_text())
    check(not [x for x in sj if x["id"] == "S03" and x.get("figma")], "draft: S03 has no Figma link")
    rl = [PY, S / "handoff/scripts/pkg.py", "relink", "--pkg", pkg, "--config", item / "pkg.json", "--zip"]
    out = run(rl, d, expect=1)
    check("still no Figma node for S03" in out, "relink stops while a screen has no node", out)
    flows_before = (pkg / "spec/flows.md").read_text()
    pcj["figma"]["S03"] = "1:4"
    write(item / "pkg.json", json.dumps(pcj, indent=1))
    out = run(rl, d)
    pcj = json.loads((item / "pkg.json").read_text())
    sj = json.loads((pkg / "screens/screens.json").read_text())
    check(pcj["status"] == "final" and "awaiting_figma" not in pcj and all(x.get("figma") for x in sj)
          and (pkg / "spec/flows.md").read_text() == flows_before and zp.is_file() and "post zip True" in out,
          "relink: Figma links filled, status final, zip rebuilt, other files unchanged (K-B5)", out)
    if browser:   # K-B9: the unpacked package in Chromium
        out = run([PY, S / "handoff/scripts/pkg.py", "smoke", zp, "--widths", "400,1280"], d)
        check("Smoke Design - 1234.zip: 2 route(s) x 2 width(s)" in out and out.rstrip().endswith("OK"), "pkg.py smoke on the zip (K-B9)", out)
        bad_pkg = d / "smoke-bad"
        write(bad_pkg / "screens/screens.json", json.dumps([{"id": "S01", "route": "prototype/index.html#/"}]))
        write(bad_pkg / "prototype/index.html", '<!doctype html><html lang="en"><body><img src="gone.png" alt="x">'
              '<div style="width:2000px">wide</div><script>undefinedFn()</script></body></html>')
        out = run([PY, S / "handoff/scripts/pkg.py", "smoke", bad_pkg, "--widths", "400"], d, expect=1)
        check("404: /prototype/gone.png" in out and "horizontal scroll" in out and "pageerror" in out and "broken image" in out,
              "pkg.py smoke reports 404, broken image, page error, horizontal scroll (K-B9)", out)
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

    # ---------- share: group names, change types, first release, awaiting Figma (K-F17, K-B10, K-B5) ----------
    p2 = d / "item2" / "pkg"
    write(p2 / "README.md", "# Design - 1234\n\nTasks v1.1.0.\n")
    write(p2 / "spec/index.md", "| Unit | Name | Status | File |\n|---|---|---|---|\n| FR01 | Task list | Active | [FR01](FR01.md) |\n")
    (p2 / "requirements").mkdir(parents=True, exist_ok=True)
    (p2 / "requirements/checklist-feature.csv").write_text(
        "Code,Feature,Group,Screen / location,Behaviour,Inputs,Expected result,Status,Dependencies\nF01,Filter tasks,FR01,S01,b,i,e,Full,\n",
        encoding="utf-8-sig")
    write(p2 / "requirements/changelog.md", "# Changelog\n\n## 1.1.0 · 2026-11-22\n- Added: two panes on wide screens (`tasks/index.html#/`)\n"
          "- Changed: the close button says \"Close task\"\n- `--acme-space-2` gap on cards\n\n## 1.0.0 · 2026-11-21\n- First release\n")
    em_args = [PY, "-I", S / "share/scripts/draft_email.py", p2, "--app", "acme-web", "--feature", "[1234] Tasks", "--with-features",
               "--figma", "https://www.figma.com/design/TESTKEY/acme-test", "--template", "docs/mail.html"]
    run(em_args + ["--out", d / "email4"], d)
    body = (d / "email4/body.txt").read_text()
    check("Task list" in body and "FR01" not in body and "Added" in body and "Two panes on wide screens" in body
          and "Changed" in body and body.count("UI refinements") == 1,
          "share: group names from spec/index.md, Added/Changed groups, an Added line with a route is never folded into polish", body)
    write(p2 / "requirements/changelog.md", "# Changelog\n\n## 1.0.0 · 2026-11-21\n- Task list with filters\n")
    (p2 / "requirements/checklist-feature.csv").unlink()
    run(em_args + ["--version", "1.0.0", "--out", d / "email5"], d)
    body = (d / "email5/body.txt").read_text()
    check("Key features" in body and "changes since" not in body and "Task list with filters" in body,
          "share: first version (no earlier one) lists key features, not changes", body)
    write(d / "item2/pkg.json", json.dumps({"status": "awaiting-figma", "awaiting_figma": ["S03"]}))
    out = run(em_args + ["--out", d / "email6"], d, expect=1)
    check("awaiting Figma" in out and "relink" in out, "share: package awaiting Figma is an ERROR", out)
    out = run(em_args + ["--allow-draft", "--out", d / "email6"], d)
    check("do not send" in out, "share: --allow-draft composes a package awaiting Figma with a NOTE", out)

    # ---------- wireflow demo links keep the page folder ----------
    fl = d / "flows-copy.json"
    write(fl, json.dumps({"flows": [{"id": "WF-01", "rows": [{"items": [["n", "S03"]]}]}]}))
    scr = d / "scr.json"
    write(scr, json.dumps([{"id": "S03", "page": "prototype/settings/index.html", "hash": "#/"}]))
    out = run([PY, "-I", S / "wireflow/scripts/demo_links.py", "fill", "--screens", scr, "--flows", fl, "--app", "acme-web",
               "--page-root", "prototype"], d)
    check("/apps/acme-web/settings/#/" in out, "demo links keep the page folder", out)
    # issue 32: fill --manifest reads the capture manifest as a JS module (as capture.js does) and as JSON
    man_js = d / "manifest-links.js"
    write(man_js, "module.exports = { screens: [{ id: 'S03', steps: [{ goto: 'settings/index.html#/' }, { click: '#open' }] }] };\n")
    write(fl, json.dumps({"flows": [{"id": "WF-01", "rows": [{"items": [["n", "S03"]]}]}]}))
    out = run([PY, "-I", S / "wireflow/scripts/demo_links.py", "fill", "--screens", scr, "--flows", fl, "--app", "acme-web",
               "--page-root", "prototype", "--manifest", man_js, "--no-md"], d)
    check("REMINDER: WF-01: first screen S03 needs 2 step(s)" in out, "demo_links fill --manifest takes the JS capture manifest (#32)", out)
    write(d / "manifest-links.json", json.dumps({"screens": [{"id": "S03", "steps": [{"click": "#open"}]}]}))
    out = run([PY, "-I", S / "wireflow/scripts/demo_links.py", "fill", "--screens", scr, "--flows", fl, "--app", "acme-web",
               "--manifest", d / "manifest-links.json", "--no-md", "--dry-run"], d)
    check("needs 1 step(s)" in out, "demo_links fill --manifest still takes JSON (#32)", out)

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
    # 0.12.2 (K3-6, K1a-3): a page app's check URL that names the app opens its host page, or --url
    js = json.loads(run(R + ["check", "--app", "acme-page", "--id", "A11Y-001", "--json", "-"], d))
    js2 = json.loads(run(R + ["check", "--app", "acme-page", "--id", "A11Y-001", "--url", "http://127.0.0.1:9/x/p.html", "--json", "-"], d))
    check(js and "http://127.0.0.1:9/apps/acme-web/" in js[0]["command"] and "not reachable" in js[0]["reason"]
          and "http://127.0.0.1:9/x/p.html" in js2[0]["command"],
          "rules check: a page app's check URL opens its host page (or --url), not a URL with the page app id", json.dumps(js + js2))
    # 0.12.3 (K4-3): {app} of a page app outside a URL is the host app (from usedBy), shown as "page → host"
    js = json.loads(run(R + ["check", "--app", "acme-page", "--id", "BLD-001", "--json", "-"], d))
    out = run(R + ["check", "--app", "acme-page", "--id", "BLD-001"], d)
    check(js and js[0]["command"].endswith(" acme-web") and js[0]["host"] == "acme-web" and js[0]["app"] == "acme-page"
          and "acme-page → acme-web" in out, "rules check: {app} of a page app is its host app id, not the page id (K4-3)", json.dumps(js) + out)
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
    # validate init --page --url: one file, hash-only routes, served URL as plan url (K-F5)
    out = run([PY, S / "validate/scripts/validation.py", "init", "--app", "acme-web", "--page", "settings/index.html",
               "--url", "http://127.0.0.1:9/apps/acme-web/settings/index.html", "--dir", d / "valdir-page"], d)
    vp = json.loads((d / "valdir-page/plan.json").read_text())
    check(vp["url"].endswith("settings/index.html") and all(not s["route"] or s["route"].startswith("#") for s in vp["screens"])
          and "text=200%" in vp["_stateHints"], "validate init --page --url: one page, hash-only routes, state hints", out)
    if browser:
        # validate: named states (theme, text 200%), reload step, axe from a path, waivers, contrast detail, compare (K-F6..F10, F19, B7)
        vt = d / "vt"
        write(vt / "index.html", "<!doctype html><html lang=\"en\"><head><title>t</title></head><body>\n"
              "<div id=\"shell\"><a href=\"#/x\">Shell link</a></div><main><p>Body text</p><div id=\"seen\" hidden>seen</div></main>\n"
              "<script>if (localStorage.getItem('seen')) document.getElementById('seen').hidden = false;\n"
              "new MutationObserver(() => { const h = document.documentElement; if (h.dataset.brand === 'ocean') console.error('brand-applied');\n"
              " if (h.style.fontSize) console.error('font-' + h.style.fontSize); }).observe(document.documentElement, { attributes: true });</script>\n"
              "</body></html>\n")
        write(d / "axe-x/axe.min.js", "/*! axe v4.9.9 stub */\nwindow.axe = { run: async () => ({ violations: [{ id: 'color-contrast', impact: 'serious',"
              " help: 'Contrast', nodes: [\n { target: ['#shell > a'], any: [{ data: { fgColor: '#999999', bgColor: '#ffffff', contrastRatio: 2.85,"
              " expectedContrastRatio: '4.5:1' } }] },\n { target: ['main > p'], any: [{ data: { fgColor: '#777777', bgColor: '#ffffff',"
              " contrastRatio: 4.48, expectedContrastRatio: '4.5:1' } }] }] }] }) };\n")
        vd = d / "valdir-states"
        vplan = {"axe": {"exclude": ["#nothing"]}, "states": ["text=200%"], "screens": [
            {"id": "S01", "route": "", "states": ["brand=ocean"]},
            {"id": "S02", "route": "", "steps": [{"eval": "localStorage.setItem('seen','1')"}, {"goto": "#/", "reload": True}, {"expectVisible": "#seen"}]}],
            "flows": [{"name": "reload step", "steps": [{"eval": "localStorage.setItem('seen','1')"}, {"reload": True}, {"expectVisible": "#seen"}]},
                      {"name": "hash only", "steps": [{"eval": "localStorage.setItem('seen','1')"}, {"goto": "#/"}, {"expectVisible": "#seen", "timeout": 400}]}]}
        write(vd / "plan.json", json.dumps(vplan))
        write(vd / "waivers.json", json.dumps([{"check": "a11y", "id": "color-contrast", "selector": "#shell", "reason": "shared frame, other work"}]))
        srv2, base2 = serve(vt)
        try:
            V = [PY, S / "validate/scripts/validation.py", "run", "--app", "acme-web", "--dir", vd, "--url", base2 + "index.html",
                 "--viewports", "1280", "--modes", "light", "--no-rules"]
            out = run(V, d, expect=1, env=dict(os.environ, KIT_AXE_PATH=str(d / "axe-x/axe.min.js")))
            r1 = sorted(vd.glob("2*/"))[-1]
            res = json.loads((r1 / "results.json").read_text())
            errs = {(it["screen"], it["state"]): " ".join(it["errors"]) for it in res["items"]}
            check("brand-applied" in errs[("S01", "brand=ocean")] and "font-32px" in errs[("S01", "text=200%")],
                  "validate: named states brand=<value> (ds.json theming attr) and text=200%, plan.states on every screen", str(errs))
            check(all(it.get("axe") for it in res["items"]),
                  "validate: axe runs on every state of the plan, not only default and theme states (K11-7)", json.dumps(res["items"])[:2000])
            fl = {f["name"]: f["ok"] for f in res["flows"]}
            check(not any(it.get("fatal") for it in res["items"]) and fl == {"reload step": True, "hash only": False},
                  "validate: reload step and goto reload: true load the page again; a hash-only goto does not", json.dumps(res)[:2000])
            rep = (r1 / "report.md").read_text()
            check(res["axe"]["version"] == "4.9.9" and "main > p 4.48:1 (needs 4.5:1), #777777 on #ffffff" in rep
                  and "#shell > a 2.85:1" in rep and "shared frame, other work" in rep and "## Known / waived (" in rep,
                  "validate: axe from KIT_AXE_PATH, contrast ratio and colours, waived nodes under Known / waived", rep[:3000])
            vplan["setTheme"] = "console.error('via-setTheme ' + key + '=' + value); document.documentElement.setAttribute('data-' + key, value);"
            write(vd / "plan.json", json.dumps(vplan))
            import time
            time.sleep(1.1)
            out = run(V + ["--axe", d / "axe-x"], d, expect=1)
            r2 = sorted(vd.glob("2*/"))[-1]
            res = json.loads((r2 / "results.json").read_text())
            rep = (r2 / "report.md").read_text()
            check(r2 != r1 and any("via-setTheme brand=ocean" in " ".join(it["errors"]) for it in res["items"]),
                  "validate: theme values go through setTheme when set (K-F19)", json.dumps(res["items"])[:2000])
            check(("Compared with run %s" % r1.name) in rep and "carried over" in rep and "| new |" in rep,
                  "validate: report marks rows new or carried over since the previous run (K-B7)", rep[:3000])
        finally:
            srv2.shutdown()

        # validate init --url on a page whose routes and ids come from its script (K11-6); parity of two builds with a
        # global plan.prepare that dismisses an overlay (K11-8, K11-10); a server that stops answering (K11-9)
        page_js = ("<!doctype html><html lang=\"en\"><head><title>Library · Acme Web</title><style>#ovl{position:fixed;inset:0;"
                   "background:#fff}</style></head><body><div id=\"shell\"><button id=\"modeBtn\">Mode</button></div><main id=\"main\"></main>\n"
                   "<div id=\"ovl\">Welcome</div><script>if (localStorage.getItem('ovl-seen')) document.getElementById('ovl').remove();\n"
                   "const T = {'#/docs': '%s', '#/img': 'Images'};\nfunction draw() { const m = document.getElementById('main');\n"
                   " m.innerHTML = '<h1>Library</h1><a href=\"#/docs\">Docs</a><div role=\"tablist\"><button role=\"tab\" id=\"tabImg\">Images</button></div>'\n"
                   "  + '<input id=\"q\" aria-label=\"Search\"><button id=\"grid\" type=\"button\">Grid</button><p id=\"body\">' + (T[location.hash] || 'All') + '</p>';\n"
                   " document.getElementById('tabImg').onclick = () => { location.hash = '#/img'; };\n"
                   " document.getElementById('grid').onclick = () => { localStorage.setItem('view', 'grid'); location.hash = '#/docs'; }; }\n"
                   "addEventListener('hashchange', draw); draw();</script></body></html>\n")
        write(d / "par/a/index.html", page_js % "Docs")
        write(d / "par/b/index.html", page_js % "Files")
        srv3, base3 = serve(d / "par")
        try:
            out = run([PY, S / "validate/scripts/validation.py", "init", "--app", "acme-web", "--page", d / "par/a/index.html",
                       "--url", base3 + "a/index.html", "--dir", d / "valdir-js"], d)
            jp = json.loads((d / "valdir-js/plan.json").read_text())
            routes = [x["route"] for x in jp["screens"]]
            check("#/docs" in routes and "#/img" in routes and jp["screens"][0]["name"] == "Library" and jp.get("contentRoot") == "main"
                  and "#q" in jp["_selectors"] and "#modeBtn" not in jp["_selectors"],
                  "validate init --url: routes, names and selectors read from the rendered page, inside the content root (K11-6)", out)
            pplan = {"prepare": {"js": "localStorage.setItem('ovl-seen', '1')", "reload": True},
                     "screens": [{"id": "S01", "route": ""}, {"id": "S02", "route": "#/docs"}],
                     "flows": [{"name": "grid", "steps": [{"click": "#grid", "timeout": 1500}, {"expectUrl": "#/docs"}]}]}
            write(d / "par/plan.json", json.dumps(pplan))
            out = run([PY, S / "validate/scripts/validation.py", "parity", "--a", base3 + "a/index.html", "--b", base3 + "b/index.html",
                       "--plan", d / "par/plan.json", "--dir", d / "par-out"], d, expect=1)
            pj = json.loads((d / "par-out/parity.json").read_text())
            st = {(r["where"], r["check"]): r for r in pj["rows"]}
            s1 = [r for r in pj["rows"] if r["where"].startswith("S01 ")]
            check(s1 and all(r["status"] == "match" for r in s1) and st[("S02 · default · 1280px · light", "text")]["status"] == "differs"
                  and "Docs" in st[("S02 · default · 1280px · light", "text")]["a"] and "Files" in st[("S02 · default · 1280px · light", "text")]["b"],
                  "validate parity: an equal screen matches, a changed text differs with both values (K11-8)", json.dumps(pj["rows"])[:3000])
            check(st[("flow · grid", "result")]["a"] == "passed" and st[("flow · grid", "storage")]["status"] == "match"
                  and "## Differs (" in (d / "par-out/parity.md").read_text(),
                  "validate: plan.prepare runs before every screen and flow (overlay dismissed); flow URL and storage compared (K11-10)",
                  json.dumps(pj["rows"])[:3000])
        finally:
            srv3.shutdown()
        # 0.12.1: parity URLs relative to each side's entry (another port, another folder) when a flow leaves the page for
        # another page of the app; plan.mask hides a timestamp; init --url on a Vue page folder without src/ and without
        # hash links: the URL as given and the hashes its buttons set become screens, a "Delete" button is not clicked
        card = ("<!doctype html><html lang=\"en\"><head><title>Cards</title></head><body><main id=\"main\"><h1>Cards</h1>"
                "<p>Updated <span class=\"ts\"></span></p><div id=\"view\"></div><button id=\"one\">Open card 1</button>"
                "<button id=\"del\">Delete all</button><button id=\"chat\">Chat</button></main><script>\n"
                "document.querySelector('.ts').textContent = new Date().toISOString();\n"
                "const show = () => { document.getElementById('view').textContent = location.hash ? 'Card ' + location.hash.slice(4) : 'List'; };\n"
                "addEventListener('hashchange', show); show();\n"
                "document.getElementById('one').onclick = () => { location.hash = '#' + '/c/' + 1; };\n"
                "document.getElementById('del').onclick = () => { location.hash = '#' + '/deleted'; };\n"
                "document.getElementById('chat').onclick = () => { location.href = '../chat/' + '#' + '/t/1'; };\n"
                "</script></body></html>\n")
        for side in ("a", "b"):
            write(d / "par2" / side / "cards/index.html", card)
            write(d / "par2" / side / "chat/index.html", "<!doctype html><html lang=\"en\"><head><title>Chat</title></head>"
                  "<body><main><h1>Chat</h1></main></body></html>\n")
        srv4, base4 = serve(d / "par2")
        srv5, base5 = serve(d / "par2")
        cfg_keep = (d / "kit.config.json").read_text()
        try:
            c2 = json.loads(cfg_keep)
            c2["apps"].append({"id": "acme-cards", "path": "par2/a/cards", "stack": "vue"})
            write(d / "kit.config.json", json.dumps(c2, indent=1))
            out = run([PY, S / "validate/scripts/validation.py", "init", "--app", "acme-cards", "--url", base4 + "a/cards/",
                       "--dir", d / "valdir-cards"], d)
            cp = json.loads((d / "valdir-cards/plan.json").read_text())
            routes = [x["route"] for x in cp["screens"]]
            check(routes == ["", "#/c/1"] and cp["screens"][0]["name"] == "Cards" and "Replace the example" not in out,
                  "validate init --url: no route in the files: the URL as given and the hash a button sets are screens, a Delete button is not tried",
                  out + json.dumps(cp)[:2000])
            pplan = {"screens": [{"id": "S01", "route": ""}],
                     "flows": [{"name": "to chat", "steps": [{"click": "#chat"}, {"expectUrl": "#/t/1"}]}]}
            write(d / "par2/plan.json", json.dumps(pplan))
            run([PY, S / "validate/scripts/validation.py", "parity", "--a", base4 + "a/cards/", "--b", base5 + "b/cards/",
                 "--plan", d / "par2/plan.json", "--dir", d / "par2-out0"], d, expect=1)
            pj = json.loads((d / "par2-out0/parity.json").read_text())
            st = {(r["where"], r["check"]): r for r in pj["rows"]}
            check(st[("flow · to chat", "urls")]["status"] == "match" and st[("flow · to chat", "urls")]["a"] == "../chat/#/t/1"
                  and st[("S01 · default · 1280px · light", "text")]["status"] == "differs",
                  "validate parity: URLs relative to each side's entry (port and folder ignored) when a flow leaves the page", json.dumps(pj["rows"])[:3000])
            pplan["mask"] = [".ts"]
            write(d / "par2/plan.json", json.dumps(pplan))
            out = run([PY, S / "validate/scripts/validation.py", "parity", "--a", base4 + "a/cards/", "--b", base5 + "b/cards/",
                       "--plan", d / "par2/plan.json", "--dir", d / "par2-out"], d, expect=None)
            pj = json.loads((d / "par2-out/parity.json").read_text())
            check(pj["differs"] == 0 and any(r["check"] == "text" and r["where"].startswith("S01") for r in pj["rows"]),
                  "validate parity: plan.mask hides a timestamp from text and pixel compare", out + json.dumps(pj["rows"])[:3000])
        finally:
            write(d / "kit.config.json", cfg_keep)
            srv4.shutdown()
            srv5.shutdown()
        # 0.12.2: parity: a prepare that fails on both sides is an error, never a match (K3-3); top-level await in prepare
        # (K3-4); init --url: a dialog a button opens without a hash is a state (K1a-4); axe limited to plan.contentRoot (K3-5)
        dlg = ("<!doctype html><html lang=\"en\"><head><title>Notes</title></head><body><div id=\"shell\"><button aria-haspopup=\"menu\">"
               "Account</button></div><main id=\"main\"><h1>Notes</h1><p id=\"msg\">List</p><button id=\"add\">New note</button></main>"
               "<div role=\"dialog\" id=\"dlg\" aria-label=\"New note\" hidden><p>Title</p></div><script>\n"
               "document.getElementById('add').onclick = () => { document.getElementById('dlg').hidden = false; };\n</script></body></html>\n")
        write(d / "par3/a/index.html", dlg)
        write(d / "par3/b/index.html", dlg)
        srv6, base6 = serve(d / "par3")
        try:
            out = run([PY, S / "validate/scripts/validation.py", "init", "--app", "acme-web", "--page", d / "par3/a/index.html",
                       "--url", base6 + "a/index.html", "--dir", d / "valdir-dlg"], d)
            dp = json.loads((d / "valdir-dlg/plan.json").read_text())
            sts = dp["screens"][0]["states"]
            check(len(dp["screens"]) == 1 and [x["name"] for x in sts] == ["New note"] and dp["flows"]
                  and dp["flows"][-1]["steps"][-1] == {"expectVisible": "#dlg"} and any("Account" in h for h in dp["_stateHints"]),
                  "validate init --url: a dialog a button opens (no hash) is a state and a flow; popup controls outside the root are hints (K1a-4)",
                  out + json.dumps(dp)[:2000])
            pplan = {"contentRoot": "main", "screens": [{"id": "S01", "route": "", "states": [
                {"name": "await", "prepare": "await new Promise(r => setTimeout(r, 50)); document.getElementById('msg').textContent = 'Waited';"},
                {"name": "broken", "prepare": "document.querySelector('#none').click()"}]}],
                "flows": [{"name": "bad prepare", "prepare": "await Promise.reject(new Error('boom'))", "steps": [{"wait": 50}]}]}
            write(d / "par3/plan.json", json.dumps(pplan))
            out = run([PY, S / "validate/scripts/validation.py", "parity", "--a", base6 + "a/index.html", "--b", base6 + "b/index.html",
                       "--plan", d / "par3/plan.json", "--dir", d / "par3-out", "--min-pixels", "400"], d, expect=1)
            pj = json.loads((d / "par3-out/parity.json").read_text())
            st = {(r["where"], r["check"]): r for r in pj["rows"]}
            br = st.get(("S01 · broken · 1280px · light", "prepare")) or {}
            check(br.get("status") == "error" and br.get("side") == "A and B" and "broken" in br.get("a", "") and pj["errors"] == 2
                  and st[("flow · bad prepare", "prepare")]["status"] == "error" and "ERROR: S01 · broken" in out
                  and pj["pixels"]["minPixels"] == 400 and "## Errors (2)" in (d / "par3-out/parity.md").read_text(),
                  "validate parity: a prepare that fails on both builds is an error with the side and the message, exit 1 (K3-3)",
                  out + json.dumps(pj["rows"])[:3000])
            ra = json.loads((d / "par3-out/a/results.json").read_text())
            aw = next(it for it in ra["items"] if it["state"] == "await")
            check(not aw.get("fatal") and "Waited" in aw["snap"]["text"] and st[("S01 · await · 1280px · light", "text")]["status"] == "match",
                  "validate: prepare takes top-level await (K3-4)", json.dumps(aw)[:2000])
            write(d / "axe-ctx/axe.min.js", "/*! axe v4.9.9 stub */\nwindow.axe = { run: async (ctx) => ({ violations: [{ id: 'scope', impact: 'minor',"
                  " help: JSON.stringify(ctx && ctx.include ? ctx.include : 'document'), nodes: [{ target: ['main'] }] }] }) };\n")
            write(d / "valdir-axe/plan.json", json.dumps({"contentRoot": "#nope, main", "screens": [{"id": "S01", "route": ""}]}))
            out = run([PY, S / "validate/scripts/validation.py", "run", "--app", "acme-web", "--dir", d / "valdir-axe", "--url", base6 + "a/index.html",
                       "--viewports", "1280", "--modes", "light", "--no-rules", "--axe", d / "axe-ctx"], d, expect=None)
            rr = json.loads((sorted((d / "valdir-axe").glob("2*/"))[-1] / "results.json").read_text())
            check(rr["items"][0]["axe"][0]["help"] == '[["main"]]' and "NOTE: --no-rules" in out,
                  "validate: without plan.axe.include, axe is limited to the first plan.contentRoot selector that matches (K3-5)",
                  out + json.dumps(rr["items"])[:2000])
        finally:
            srv6.shutdown()
        # 0.12.3: an async IIFE prepare is awaited (K4-4); plan.settle waits for a skeleton after a state's reload, which
        # starts from the data its prepare wrote (K1a-7); a prepare that reloads the page is no error; plan.normalize "ids"
        # (K1a-6); a class difference is a row to look at (K1a-8); parity --app reads <paths.validation>/<app>/plan.json and
        # writes the report in .../parity (K4-1); --artifacts keeps runs, screenshots and diffs out of it (K4-2)
        skel = ("<!doctype html><html lang=\"en\"><head><title>Board</title></head><body><main id=\"main\"><p class=\"skel\">Loading</p>"
                "</main><script>\nconst m = document.getElementById('main'), seed = localStorage.getItem('seed') || 'Empty';\n"
                "setTimeout(() => { m.innerHTML = '<h1>Board</h1><p id=\"s\">' + seed + '</p><a href=\"#/x\" class=\"lnk%s\">Docs</a>"
                "<button id=\"new\">New</button><span id=\"e\"> </span>';\n document.getElementById('new').onclick = () => { const id = 'u' + Date.now().toString(36);"
                " localStorage.setItem('conv.' + id, id); location.hash = '#/c/' + id; }; }, 600);\n</script></body></html>\n")
        write(d / "par4/a/index.html", skel % "")
        write(d / "par4/b/index.html", skel % " brand")
        srv7, base7 = serve(d / "par4")
        try:
            write(d / "par4/iife.json", json.dumps({"contentRoot": "main", "prepare": "(async () => { await new Promise(r => setTimeout(r, 900)) })()",
                                                    "screens": [{"id": "S01", "route": ""}]}))
            run([PY, S / "validate/scripts/validation.py", "parity", "--a", base7 + "a/index.html", "--b", base7 + "a/index.html",
                 "--plan", d / "par4/iife.json", "--dir", d / "par4-iife"], d, expect=None)
            it = json.loads((d / "par4-iife/a/results.json").read_text())["items"][0]
            check("Board" in it["snap"]["text"] and "Loading" not in it["snap"]["text"],
                  "validate: a prepare whose value is a promise (async IIFE) is awaited before the view is read (K4-4)", json.dumps(it)[:2000])
            vplan = {"contentRoot": "main", "settle": ".skel", "normalize": ["ids"],
                     "screens": [{"id": "S01", "route": "", "states": [{"name": "seeded", "prepare": "localStorage.setItem('seed', 'Seeded')", "reload": True},
                                                                      {"name": "reloads", "prepare": "location.reload()"}]}],
                     "flows": [{"name": "new", "steps": [{"click": "#new"}, {"expectUrl": "#/c/"}]}]}
            write(d / "docs/validation/acme-web/plan.json", json.dumps(vplan))
            out = run([PY, S / "validate/scripts/validation.py", "parity", "--app", "acme-web", "--a", base7 + "a/index.html",
                       "--b", base7 + "b/index.html", "--artifacts", d / "art"], d, expect=None)
            pdir = d / "docs/validation/acme-web/parity"
            pj = json.loads((pdir / "parity.json").read_text()) if (pdir / "parity.json").is_file() else {"rows": []}
            st = {(r["where"], r["check"]): r for r in pj["rows"]}
            ra = json.loads((d / "art/acme-web/parity/a/results.json").read_text()) if (d / "art/acme-web/parity/a/results.json").is_file() else {"items": [], "flows": []}
            sv = {it["state"]: it for it in ra["items"]}
            check(pj.get("differs") == 0 and not pj.get("errors") and "Seeded" in sv["seeded"]["snap"]["text"]
                  and "Board" in sv["default"]["snap"]["text"] and not sv["reloads"].get("fatal"),
                  "validate: state reload: true starts from the data its prepare wrote; plan.settle waits for the skeleton; "
                  "a prepare that reloads is no error (K1a-7, K4-4)", out + json.dumps(pj["rows"])[:3000])
            fu = ra["flows"][0]["urls"] if ra["flows"] else []
            rb = json.loads((d / "art/acme-web/parity/b/results.json").read_text())
            check(fu and "#/c/u" in fu[-1] and fu != rb["flows"][0]["urls"] and st[("flow · new", "urls")]["status"] == "match"
                  and st[("flow · new", "storage")]["status"] == "match",
                  "validate parity: plan.normalize ids: generated ids in URLs and localStorage match (K1a-6)", json.dumps(pj["rows"])[:3000])
            cl = st.get(("S01 · default · 1280px · light", "classes")) or {}
            check(cl.get("status") == "review" and "a.brand.lnk" in cl.get("b", "") and pj.get("review", 0) >= 1 and "Parity:" in out
                  and "## To look at (" in (pdir / "parity.md").read_text(),
                  "validate parity: a class added to a link is a row to look at, not a difference (K1a-8)", out + json.dumps(cl))
            check(not (pdir / "a").exists() and not (pdir / "diffs").exists() and list((d / "art/acme-web/parity/a/shots").glob("*.png"))
                  and "art/acme-web/parity" in (pdir / "parity.md").read_text(),
                  "validate parity --app: plan and report in <paths.validation>/<app>, runs and screenshots in --artifacts (K4-1, K4-2)",
                  out + (pdir / "parity.md").read_text()[:1500])
            write(d / "valdir-art/plan.json", json.dumps({"contentRoot": "main", "settle": 700, "screens": [{"id": "S01", "route": ""}],
                                                       "flows": [{"name": "empty", "steps": [{"expectText": ["#e", ""]}]},
                                                                 {"name": "not empty", "steps": [{"expectText": ["#s", ""]}]}]}))
            out = run([PY, S / "validate/scripts/validation.py", "run", "--app", "acme-web", "--dir", d / "valdir-art", "--url", base7 + "a/index.html",
                       "--viewports", "1280", "--modes", "light", "--no-rules", "--artifacts", d / "art2"], d, expect=None)
            rr = sorted((d / "valdir-art").glob("2*/"))[-1]
            check(not (rr / "shots").exists() and list((d / "art2/acme-web" / rr.name / "shots").glob("*.png"))
                  and ("art2/acme-web/%s/shots" % rr.name) in (rr / "report.md").read_text(),
                  "validate run --artifacts: screenshots outside the validation folder, the report names them (K4-2)", out)
            fl = {f["name"]: f for f in json.loads((rr / "results.json").read_text())["flows"]}
            check(fl["empty"]["ok"] and not fl["not empty"]["ok"] and "is not empty" in (fl["not empty"]["error"] or ""),
                  "validate: expectText [selector, \"\"] passes on an element without text, fails on one with text (K5-2)", json.dumps(fl)[:1500])
        finally:
            srv7.shutdown()
        # 0.12.4: a menu teleported into body is compared through plan.portals or a contentRoot list (K7-3); expectVisible
        # passes when any match is visible, expectHidden when none is (K8-1); parity.md lists each flow's result on A and B and
        # the flows that fail on both builds, without changing the exit code (K8-2)
        tele = ("<!doctype html><html lang=\"en\"><head><title>Cards</title></head><body><main id=\"main\"><h1>Cards</h1>"
                "<p class=\"it\" hidden>Old</p><p class=\"it\">Card one</p><button id=\"more\" aria-haspopup=\"menu\">More</button>%s</main>%s"
                "<script>document.getElementById('more').onclick = () => { document.querySelector('.ml').hidden = false; };</script></body></html>\n")
        menu = "<div class=\"ml\" role=\"menu\" hidden><button role=\"menuitem\">Rename</button><button role=\"menuitem\">Delete</button></div>"
        write(d / "par5/a/index.html", tele % (menu, ""))
        write(d / "par5/b/index.html", tele % ("", menu))
        srv8, base8 = serve(d / "par5")
        try:
            tplan = {"contentRoot": "main", "screens": [{"id": "S01", "route": "", "states": [{"name": "menu", "prepare": "document.getElementById('more').click()"}]}],
                     "flows": [{"name": "visible", "steps": [{"expectVisible": ".it"}, {"expectHidden": ".ml"}, {"click": "#more"},
                                                              {"expectVisible": "[role=menuitem]"}]},
                               {"name": "hidden fails", "steps": [{"expectHidden": ".it", "timeout": 500}]},
                               {"name": "first only", "steps": [{"expectVisible": ".it >> nth=0", "timeout": 500}]}]}
            for name, extra in (("no-portal", {}), ("portal", {"portals": ["body > .ml"]}), ("list", {"contentRoot": ["main", ".ml"]})):
                write(d / ("par5/%s.json" % name), json.dumps(dict(tplan, **extra)))
                run([PY, S / "validate/scripts/validation.py", "parity", "--a", base8 + "a/index.html", "--b", base8 + "b/index.html",
                     "--plan", d / ("par5/%s.json" % name), "--dir", d / ("par5-%s" % name)], d, expect=None)
            res = {n: {(r["where"], r["check"]): r for r in json.loads((d / ("par5-%s/parity.json" % n)).read_text())["rows"]}
                   for n in ("no-portal", "portal", "list")}
            mk = ("S01 · menu · 1280px · light", "text")
            check(res["no-portal"][mk]["status"] == "differs" and "Rename" in res["no-portal"][mk]["a"]
                  and all(res[n][mk]["status"] == "match" and res[n][("S01 · menu · 1280px · light", "roles")]["status"] == "match"
                          for n in ("portal", "list")),
                  "validate parity: a menu teleported into body matches through plan.portals or a contentRoot list (K7-3)",
                  json.dumps({n: [r for r in v.values() if r["where"].startswith("S01 · menu")] for n, v in res.items()})[:3000])
            fl = {f["name"]: f for f in json.loads((d / "par5-portal/a/results.json").read_text())["flows"]}
            check(fl["visible"]["ok"] and not fl["hidden fails"]["ok"] and not fl["first only"]["ok"],
                  "validate: expectVisible passes when one match is visible, expectHidden fails while one is; >> nth=0 checks the first (K8-1)",
                  json.dumps(fl)[:2000])
            pj = json.loads((d / "par5-portal/parity.json").read_text())
            md = (d / "par5-portal/parity.md").read_text()
            hf = res["portal"][("flow · hidden fails", "result")]
            check(hf["status"] == "match" and set(pj["flowsFailingBoth"]) == {"hidden fails", "first only"}
                  and "## Flows failing in both builds (to look at) (2)" in md and "## Flow results A / B (3)" in md
                  and "| visible | passed | passed | Match |" in md and "failed at step 1:" in md,
                  "validate parity: flow results of A and B, and flows failing on both builds listed apart (K8-2)", md[-2500:])
        finally:
            srv8.shutdown()
        import socket
        so = socket.socket()
        so.bind(("127.0.0.1", 0))
        dead = "http://127.0.0.1:%d/" % so.getsockname()[1]
        so.close()
        write(d / "valdir-down/plan.json", json.dumps({"screens": [{"id": "S%02d" % i, "route": "#/%d" % i} for i in range(1, 6)]}))
        out = run([PY, S / "validate/scripts/validation.py", "run", "--app", "acme-web", "--dir", d / "valdir-down", "--url", dead + "index.html",
                   "--viewports", "1280", "--modes", "light", "--no-rules"], d, expect=1)
        check(sum(1 for x in out.splitlines() if x.startswith("ERROR:")) == 1 and "does not answer" in out and "screen S01" in out,
              "validate: a server that does not answer stops the run with one ERROR line (K11-9)", out)


    # prototype.post through the generic hook runner; nothing set = nothing run
    out = run([PY, KIT / "scripts/kitconf.py", "hook", "prototype.post", "--app", "acme-web"], d)
    check("not set" in out, "kitconf hook: an unset project command runs nothing", out)
    cfg["prototype"] = {"post": PY + " -c \"import sys; print('posted', sys.argv[1])\" {app}"}
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    out = run([PY, KIT / "scripts/kitconf.py", "hook", "prototype.post", "--app", "acme-web"], d)
    check("posted acme-web" in out and "exit code 0" in out, "prototype.post: project command with {app}, output and exit code", out)

    # prototype: page contract of the app (apps[].pageContract), printed by kitconf.py contract
    out = run([PY, KIT / "scripts/kitconf.py", "contract", "--app", "acme-web"], d)
    check("No page contract" in out, "kitconf contract: empty by default", out)
    cfg["apps"][0]["pageContract"] = ["Call Shell.ready() after the first render"]
    cfg["local"]["vueStyle"] = "css-file"
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    run([PY, KIT / "scripts/kitconf.py", "check"], d)
    out = run([PY, KIT / "scripts/kitconf.py", "contract", "--app", "acme-web"], d)
    check("- Call Shell.ready()" in out, "kitconf contract: apps[].pageContract lines; local.vueStyle css-file is valid", out)

    # define: draft parity rules of an existing page (extract_rules.py)
    write(d / "apps/acme-web/notes.js", "const NOTE_MAX = 80;\nif (v.length > NOTE_MAX) toast('Title is too long');\n"
          "localStorage.setItem('acme-web:notes', s);\n")
    out = run([PY, S / "define/scripts/extract_rules.py", "apps/acme-web/index.html", "apps/acme-web/notes.js",
               "--out", d / "parity.md"], d)
    par = (d / "parity.md").read_text()
    check("Title is too long" in par and "`apps/acme-web/notes.js:2`" in par and "acme-web:notes" in par
          and "NOTE_MAX = 80" in par and "| E001 |" in par, "extract_rules: messages, limits, storage with file:line", par)
    # K11-1..3: storage through a wrapper, routes built at run time, no HTML pieces or directives
    write(d / "apps/acme-web/lib.js", "'use strict';\nvar view = Shell.store.get('libView', 'grid');\n"
          "var h = '<span class=\"ic '+k+' solid\" aria-label=\"'+n+'\">';\nFILES.unshift({n:'Uploaded file'}); toast('success', 'File uploaded.');\n"
          "tab.onclick = function(){ location.hash = '#/' + tab.dataset.k };\nKINDS.forEach(function(k){ R['/' + k] = show; });\n")
    out = run([PY, S / "define/scripts/extract_rules.py", "apps/acme-web/lib.js", "--json"], d)
    rows = {(r["kind"], r["text"]): r.get("note") for r in json.loads(out)}
    check(rows.get(("storage", "Shell.store.get libView")) == "wrapper" and rows.get(("route", "'#/'+tab.dataset.k")) == "dynamic"
          and ("route", "R['/'+k]") in rows and ("message", "File uploaded.") in rows and ("string", "Uploaded file") in rows
          and not any(t in ("use strict", "success") or '="' in t for _k, t in rows),
          "extract_rules: wrapper storage flagged, dynamic routes, messages only from toast calls, no HTML pieces", out)
    cfg["define"] = {"storageCalls": ["Shell.store.get"], "storagePrefix": "acme."}
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    out = run([PY, S / "define/scripts/extract_rules.py", "apps/acme-web/lib.js"], d)
    check("Shell.store.get acme.libView" in out and "built at run time" in out, "extract_rules: define.storageCalls + storagePrefix give the stored key", out)
    del cfg["define"]
    write(d / "kit.config.json", json.dumps(cfg, indent=1))
    # 0.12.2 (K3-2): --skip-shell, --exclude, --function on the command line
    write(d / "apps/acme-web/shelled.html", "<!-- SHELL:top --><nav>Shell menu</nav><!-- /SHELL:top -->\n<main><h1>Own text</h1></main>\n"
          "<script>function save(){ toast('Saved here'); }\nfunction other(){ toast('Not this'); }</script>\n")
    out = run([PY, S / "define/scripts/extract_rules.py", "apps/acme-web/", "--skip-shell", "--exclude", "**/lib.js", "--exclude", "*/notes.js", "--json"], d)
    rows = {r["text"] for r in json.loads(out)}
    out2 = run([PY, S / "define/scripts/extract_rules.py", "apps/acme-web/shelled.html", "--function", "save", "--json"], d)
    check("Own text" in rows and "Shell menu" not in rows and "File uploaded." not in rows and "Title is too long" not in rows
          and {r["text"] for r in json.loads(out2)} == {"Saved here"},
          "extract_rules: --skip-shell leaves out SHELL regions, --exclude skips files, --function reads one function body", out + out2)

    # K11-5: the contract of a page app includes its host app's contract
    out = run([PY, KIT / "scripts/kitconf.py", "contract", "--app", "acme-page"], d)
    check("Page app acme-page" in out and "Host app acme-web (holds apps/acme-web/tasks.js)" in out and "- Call Shell.ready()" in out,
          "kitconf contract: page app lists the host app's contract", out)
    # K11-12: add-page builds a new page app like an existing one; the host's pageHook runs when set
    write(d / "pages/tasks/package.json", json.dumps({"name": "acme-tasks", "private": True}, indent=2))
    write(d / "pages/tasks/vite.config.ts", 'export default { build: { lib: { name: "AcmeTasks", fileName: () => "tasks.js" } } }\n')
    write(d / "pages/tasks/src/main.ts", 'import { createApp } from "vue"\nimport Tasks from "./Tasks.vue"\ncreateApp(Tasks).mount("#page-root")\n')
    keep_cfg = json.dumps(cfg, indent=1)
    out = run([PY, KIT / "scripts/kitconf.py", "add-page", "--like", "acme-page", "--id", "acme-notes", "--host", "acme-web", "--dry-run"], d)
    check("Dry run" in out and not (d / "pages/acme-notes").exists() and "acme-notes" not in (d / "kit.config.json").read_text(),
          "kitconf add-page --dry-run: plan only", out)
    hosted = json.loads(keep_cfg)
    hosted["apps"][0]["pageHook"] = PY + " -c \"import sys; print('hooked', sys.argv[1], sys.argv[2])\" {id} {usedBy}"
    hosted["local"] = dict({k: v for k, v in (hosted.get("local") or {}).items() if k != "vueStyle"}, vueCss="src/page.css")
    write(d / "kit.config.json", json.dumps(hosted, indent=1))
    out = run([PY, KIT / "scripts/kitconf.py", "add-page", "--like", "acme-page", "--id", "acme-notes", "--host", "acme-web"], d)
    newc = json.loads((d / "kit.config.json").read_text())
    ent = next((a for a in newc["apps"] if a["id"] == "acme-notes"), {})
    check("hooked acme-notes apps/acme-web/acme-notes.js" in out and ent.get("type") == "page"
          and ent.get("usedBy") == ["apps/acme-web/acme-notes.js"] and "./Tasks.vue" in out
          and '"acme-notes.js"' in (d / "pages/acme-notes/vite.config.ts").read_text()
          and json.loads((d / "pages/acme-notes/package.json").read_text())["name"] == "acme-notes"
          and not (d / "pages/acme-notes/src/Tasks.vue").exists(), "kitconf add-page: skeleton renamed, entry added, pageHook run", out)
    out = run([PY, KIT / "scripts/kitconf.py", "check"], d, expect=None)
    check("WARN: local.vueCss" not in out, "kitconf check: local.vueCss with a vue spa app is no warning", out)
    newc["apps"] = [a for a in newc["apps"] if a.get("type") != "spa"]
    write(d / "kit.config.json", json.dumps(newc, indent=1))
    out = run([PY, KIT / "scripts/kitconf.py", "check"], d, expect=None)
    check("WARN: local.vueCss" in out, "kitconf check: warns on local.vueCss when every vue app is a page (K11-13)", out)
    for loc in ({"vueCss": "src/styles/local.css"}, {"vueCss": "src/page.css", "vueStyle": "css-file"}):
        newc["local"] = dict({k: v for k, v in (newc.get("local") or {}).items() if k != "vueStyle"}, **loc)
        write(d / "kit.config.json", json.dumps(newc, indent=1))
        out = run([PY, KIT / "scripts/kitconf.py", "check"], d, expect=None)
        check("WARN: local.vueCss" not in out, "kitconf check: no local.vueCss warning for %s with page apps (0.12.1)" % loc, out)
    # 0.12.1: apps[].output as a list (one page, two host builds); add-page inside an npm workspace package
    write(d / "vue/package.json", json.dumps({"name": "acme-pages", "private": True, "workspaces": ["shared", "web"]}))
    write(d / "vue/web/package.json", json.dumps({"name": "@acme/web", "private": True}))
    write(d / "vue/web/app.config.ts", 'export default { pages: [\n  { id: "board", entry: "src/pages/board/main.ts", dest: "board/board.js" },\n] }\n')
    write(d / "vue/web/src/pages/board/main.ts", 'import { createApp } from "vue"\nimport App from "./App.vue"\nimport { X } from "../../bridge"\n'
          'createApp(App).mount("#mod")\nX.ready()\n')
    write(d / "vue/web/src/pages/board/App.vue", "<template><p>Board</p></template>\n")
    wsc = json.loads(keep_cfg)
    wsc["apps"].append({"id": "acme-board", "path": "vue/web/src/pages/board", "stack": "vue", "type": "page",
                        "build": "cd vue && node build.mjs --page board", "output": ["vue/web/dist/board.js", "vue/web2/dist/board.js"],
                        "usedBy": ["apps/acme-web/board/board.js"]})
    write(d / "kit.config.json", json.dumps(wsc, indent=1))
    run([PY, KIT / "scripts/kitconf.py", "check"], d, expect=None)
    out = run([PY, KIT / "scripts/kitconf.py", "check"], d, expect=None)
    check("output must be" not in out, "kitconf check: apps[].output may be a list", out)
    out = run([PY, KIT / "scripts/kitconf.py", "add-page", "--like", "acme-board", "--id", "acme-plan", "--host", "acme-web"], d)
    ent = next((a for a in json.loads((d / "kit.config.json").read_text())["apps"] if a["id"] == "acme-plan"), {})
    pdir = d / "vue/web/src/pages/plan"
    check(sorted(x.name for x in pdir.iterdir()) == ["main.ts"] and "npm install" not in out and "vue/web/app.config.ts" in out
          and 'entry: "src/pages/plan/main.ts"' in out and "--page plan" in out and "./App.vue" in out
          and ent.get("output") == ["vue/web/dist/plan.js", "vue/web2/dist/plan.js"] and not (d / "vue/web/src/pages/plan/package.json").exists(),
          "kitconf add-page in an npm workspace: entry file only, page list and workspace build named, no npm install (0.12.1)", out)
    wsc["apps"][-1]["output"] = ["vue/web/dist/board.js", 3]
    write(d / "kit.config.json", json.dumps(wsc, indent=1))
    out = run([PY, KIT / "scripts/kitconf.py", "check"], d, expect=1)
    check("output must be a build file path or a non-empty list" in out, "kitconf check: a bad apps[].output is an error", out)
    shutil.rmtree(d / "vue")
    write(d / "kit.config.json", keep_cfg)
    shutil.rmtree(d / "pages/acme-notes")

    # catalogue: page patterns (catalog.md '## Patterns', ds.json > patterns) for define step 5
    catmd = d / "ds/acme/catalog.md"
    keep_cat, had_json = catmd.read_text(), (d / "ds/acme/catalog.json").exists()
    write(catmd, keep_cat + "\n## Patterns\n\n### App shell\n\n- Class: `.acme-app`, `.acme-main`\n- Use: top bar, rail and main area\n")
    out = run([PY, S / "document/scripts/catalog.py", "patterns"], d)
    check("app-shell" in out and ".acme-main" in out, "catalog patterns: read from catalog.md without catalog.json", out)
    cj = d / "ds/acme/catalog.json"
    if had_json:
        cj.rename(d / "catalog.json.keep")
    out = run([PY, S / "document/scripts/catalog.py", "find", "shell"], d)
    check("[page pattern]" in out and "no catalog.json" in out, "catalog find: reads catalog.md when catalog.json is missing (K11-4)", out)
    if had_json:
        (d / "catalog.json.keep").rename(cj)
    run([PY, S / "document/scripts/catalog.py", "build"], d)
    out = run([PY, S / "document/scripts/catalog.py", "check"], d) + run([PY, S / "document/scripts/catalog.py", "find", "shell"], d)
    check("Catalog OK" in out and "[page pattern]" in out, "catalog build/check/find: page patterns kept in catalog.json", out)
    write(catmd, keep_cat)
    if not had_json:
        (d / "ds/acme/catalog.json").unlink()  # later steps see the profile as before

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


LOCK_NAV_APP_TEST = r"""
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(), p = await b.newPage(); await p.goto(process.argv[2]); await p.waitForTimeout(300);
  const go = t => p.evaluate(x => { window.__nav = null; X.nav(x); return window.__nav; }, t);
  const r = { self: await go('settings/index.html#/y'), home: await go('index.html#/x'), notes: await go('notes/index.html') };
  await b.close(); console.log(JSON.stringify(r));
})();
"""

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
