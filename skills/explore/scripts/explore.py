#!/usr/bin/env python3
"""Design explorations: two to four directions for one design question, a comparison page and the decision.

Commands:
  explore.py init <slug> --title "..." [--question "..."] [--directions 3] [--app acme-web]
      Create <paths.explorations>/<slug>/: brief.md, directions.json and one HTML page per direction
      (a/index.html, b/index.html, ...) with the DS CSS embedded, theming defaults on <html>, the
      version label and an "exploration" banner. Never overwrites: an existing folder is an error.
  explore.py check <slug>
      Validate the exploration: every direction page exists, embeds the DS markers and the version meta,
      has no raw hex/rgb colours outside the DS block; directions.json has a name, summary, pros, cons
      and effort for every direction; statuses agree with the decision. Exit 1 on error.
  explore.py compare <slug>
      Write compare.html: the directions side by side (or one at a time) in a phone, tablet or desktop
      frame, with summary, pros, cons, risks and DS fit under each. Opens from the folder (file://).
  explore.py choose <slug> <id> --reason "..." [--by "name"] [--merge "b: keep the filter bar" ...]
      Record the human decision: the chosen direction becomes "chosen", the others "rejected" (or keep
      "merged" parts with --merge), write decision.md and refresh compare.html. Run only after the user
      picked a direction; the skill never chooses.
  explore.py list
      List explorations with their status and chosen direction.

Never commits, pushes, publishes or sends anything.
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load, t, for_app  # noqa: E402
from dshtml import ds_css, wrap_css, html_attrs, version_meta  # noqa: E402

LETTERS = "abcd"
STATUSES = ("draft", "chosen", "rejected", "merged")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RAW_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
E = html.escape


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def folder(cfg, slug, must_exist=True):
    if not SLUG.match(slug):
        die("slug must be lowercase letters, digits and hyphens: %r" % slug)
    d = Path(cfg["_root"]) / cfg["paths"]["explorations"] / slug
    if must_exist and not (d / "directions.json").is_file():
        die("exploration not found: %s (run init first)" % d)
    return d


def read_json(d):
    return json.loads((d / "directions.json").read_text(encoding="utf-8"))


def write_json(d, data):
    (d / "directions.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def today():
    return dt.date.today().isoformat()


# ---------- init ----------

def direction_page(cfg, title, letter, css):
    meta = version_meta(cfg)
    meta_tag = '<meta name="%s" content="%s">' % (E(meta[0]), E(meta[1])) if meta else ""
    label = E(meta[2]) if meta else ""
    lang = cfg.get("language", "en")
    banner = E(t(cfg, "explore.banner", letter=letter.upper()))
    return """<!doctype html>
<html lang="{lang}"{attrs}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{meta}
<meta name="kit-exploration" content="{letter}">
<title>{letter_up} · {title}</title>
<style>{css}</style>
<style>
/* Exploration page. Build this direction with DS classes and tokens only (catalog.md, rules.md).
   No raw colours, no CSS over DS components. Keep it light: enough to judge the idea, not a finished prototype. */
.kit-explore-banner {{ position: sticky; top: 0; z-index: 10; padding: 6px 12px; font: 600 12px/1.4 system-ui, sans-serif;
  background: var(--muted, #f4f4f5); color: var(--muted-foreground, #52525b); border-bottom: 1px solid var(--border, #e4e4e7); }}
</style>
</head>
<body>
<div class="kit-explore-banner" data-kit-banner>{banner}</div>
<main id="main">
  <!-- Direction {letter_up}: build the screens of this direction here. -->
</main>
<footer><span class="app-version">{label}</span></footer>
</body>
</html>
""".format(lang=E(lang), attrs=html_attrs(cfg), meta=meta_tag, letter=letter, letter_up=letter.upper(),
           title=E(title), css=wrap_css(cfg, css), banner=banner, label=label)


def cmd_init(cfg, a):
    d = folder(cfg, a.slug, must_exist=False)
    if d.exists():
        die("folder exists, nothing written: %s" % d)
    n = a.directions
    if not 2 <= n <= 4:
        die("--directions must be 2, 3 or 4")
    css = ds_css(cfg)
    if not css:
        die("no DS CSS bundle found (ds.json > css.bundle). Link a DS profile first (kickoff or adopt).")
    d.mkdir(parents=True)
    data = {
        "slug": a.slug, "title": a.title, "question": a.question or "", "app": a.app or "",
        "created": today(), "status": "exploring",
        "directions": [{"id": LETTERS[i], "name": "", "summary": "", "bestFor": "", "pros": [], "cons": [], "risks": [],
                        "dsFit": {"available": [], "missing": []}, "effort": "", "status": "draft"} for i in range(n)],
        "decision": None,
    }
    write_json(d, data)
    for i in range(n):
        (d / LETTERS[i]).mkdir()
        (d / LETTERS[i] / "index.html").write_text(direction_page(cfg, a.title, LETTERS[i], css), encoding="utf-8")
    (d / "brief.md").write_text(t(cfg, "explore.briefTemplate", title=a.title, question=a.question or "…",
                                  date=today(), app=a.app or "…"), encoding="utf-8")
    print("Created %s with %d directions: %s" % (d.relative_to(cfg["_root"]), n, ", ".join(LETTERS[:n])))
    print("Next: fill brief.md and directions.json, build each direction page, then check, compare, and ask the user to choose.")


# ---------- check ----------

def check_errors(cfg, d, data):
    errs, warns = [], []
    ids = [x.get("id") for x in data.get("directions", [])]
    if not 2 <= len(ids) <= 4:
        errs.append("an exploration needs 2 to 4 directions (found %d)" % len(ids))
    if len(set(ids)) != len(ids):
        errs.append("direction ids must be unique")
    marker = cfg["_ds"]["css"]["marker"] if cfg.get("_ds") else {"begin": "@ds:begin", "end": "@ds:end"}
    meta = version_meta(cfg)
    names = set()
    for x in data.get("directions", []):
        i = x.get("id", "?")
        for k in ("name", "summary", "effort"):
            if not str(x.get(k) or "").strip():
                errs.append("direction %s: %s is empty" % (i, k))
        for k in ("pros", "cons"):
            if not [v for v in x.get(k) or [] if str(v).strip()]:
                errs.append("direction %s: list at least one item in %s" % (i, k))
        if x.get("effort") and x["effort"] not in ("S", "M", "L"):
            errs.append("direction %s: effort must be S, M or L" % i)
        if x.get("status") not in STATUSES:
            errs.append("direction %s: status must be one of %s" % (i, ", ".join(STATUSES)))
        if x.get("name"):
            if x["name"].strip().lower() in names:
                errs.append("direction %s: two directions share the name %r" % (i, x["name"]))
            names.add(x["name"].strip().lower())
        page = d / i / "index.html"
        if not page.is_file():
            errs.append("direction %s: %s missing" % (i, page.relative_to(d)))
            continue
        text = page.read_text(encoding="utf-8")
        if marker["begin"] not in text or marker["end"] not in text:
            errs.append("direction %s: DS CSS markers missing (%s … %s)" % (i, marker["begin"], marker["end"]))
        if meta and ('name="%s"' % meta[0]) not in text:
            errs.append("direction %s: version <meta name=\"%s\"> missing" % (i, meta[0]))
        outside = re.sub(r"/\*\s*%s.*?%s[^*]*\*/" % (re.escape(marker["begin"]), re.escape(marker["end"])), "", text, flags=re.S)
        outside = re.sub(r"\.kit-explore-banner\s*\{[^}]*\}", "", outside)
        raw = RAW_COLOUR.findall(outside)
        if raw:
            errs.append("direction %s: %d raw colour value(s) outside the DS block, e.g. %s" % (i, len(raw), raw[0]))
        body = re.sub(r"<!--.*?-->", "", text.split("<main", 1)[-1].split("</main>", 1)[0], flags=re.S)
        if not re.search(r"<[a-z]", body.split(">", 1)[-1]):
            warns.append("direction %s: <main> is still empty" % i)
    dec = data.get("decision")
    chosen = [x["id"] for x in data.get("directions", []) if x.get("status") == "chosen"]
    if dec:
        if chosen != [dec.get("chosen")]:
            errs.append("decision says %r but chosen direction(s) are %s" % (dec.get("chosen"), chosen or "none"))
        if not str(dec.get("reason") or "").strip():
            errs.append("decision has no reason")
    elif chosen:
        errs.append("direction %s is chosen but no decision is recorded (use choose)" % chosen[0])
    return errs, warns


def cmd_check(cfg, a):
    d = folder(cfg, a.slug)
    errs, warns = check_errors(cfg, d, read_json(d))
    for w in warns:
        print("WARN:", w)
    for e in errs:
        print("ERROR:", e)
    print("Exploration OK" if not errs else "%d error(s)" % len(errs))
    sys.exit(1 if errs else 0)


# ---------- compare ----------

def ul(items):
    items = [i for i in items or [] if str(i).strip()]
    return "<ul>%s</ul>" % "".join("<li>%s</li>" % E(str(i)) for i in items) if items else '<p class="none">—</p>'


def compare_page(cfg, data):
    T = lambda k, **kw: E(t(cfg, "explore." + k, **kw))
    cols = []
    for x in data["directions"]:
        st = x.get("status", "draft")
        fit = x.get("dsFit") or {}
        cols.append("""<article class="dir dir--{st}" data-dir="{id}">
  <header><span class="letter">{ID}</span><h2>{name}</h2><span class="badge">{badge}</span></header>
  <div class="frame"><div class="screen"><iframe src="{id}/index.html" title="{ID} · {name}" loading="lazy"></iframe></div></div>
  <p class="summary">{summary}</p>
  <dl>
    <dt>{l_best}</dt><dd>{best}</dd>
    <dt>{l_pros}</dt><dd>{pros}</dd>
    <dt>{l_cons}</dt><dd>{cons}</dd>
    <dt>{l_risks}</dt><dd>{risks}</dd>
    <dt>{l_fit}</dt><dd><p>{l_avail}: {avail}</p><p>{l_missing}: {missing}</p></dd>
    <dt>{l_effort}</dt><dd>{effort}</dd>
  </dl>
  <a class="open" href="{id}/index.html" target="_blank" rel="noopener">{l_open}</a>
</article>""".format(
            st=E(st), id=E(x["id"]), ID=E(x["id"].upper()), name=E(x.get("name") or "—"),
            badge=T("status." + st), summary=E(x.get("summary") or ""),
            l_best=T("bestFor"), best=E(x.get("bestFor") or "—"),
            l_pros=T("pros"), pros=ul(x.get("pros")), l_cons=T("cons"), cons=ul(x.get("cons")),
            l_risks=T("risks"), risks=ul(x.get("risks")), l_fit=T("dsFit"),
            l_avail=T("available"), avail=E(", ".join(fit.get("available") or []) or "—"),
            l_missing=T("missing"), missing=E(", ".join(fit.get("missing") or []) or "—"),
            l_effort=T("effort"), effort=E(x.get("effort") or "—"), l_open=T("open")))
    dec = data.get("decision")
    decision = ""
    if dec:
        merged = "".join("<li>%s</li>" % E(m) for m in dec.get("merge") or [])
        decision = '<section class="decision"><h2>{h}</h2><p>{chosen}</p><p>{reason}</p>{merged}<p class="meta">{meta}</p></section>'.format(
            h=T("decisionTitle"), chosen=T("decisionChosen", id=dec["chosen"].upper(),
                                            name=next((x.get("name") or "" for x in data["directions"] if x["id"] == dec["chosen"]), "")),
            reason=E(dec.get("reason") or ""), merged=("<ul>%s</ul>" % merged) if merged else "",
            meta=T("decisionMeta", by=dec.get("by") or "—", on=dec.get("on") or ""))
    return """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · {l_compare}</title>
<style>
:root {{ --kit-bg: #f6f6f7; --kit-panel: #fff; --kit-fg: #18181b; --kit-muted: #52525b; --kit-line: #e4e4e7; --kit-accent: #1d4ed8; --kit-ok: #047857; --kit-off: #a1a1aa; color-scheme: light; }}
@media (prefers-color-scheme: dark) {{ :root {{ --kit-bg: #0b0b0d; --kit-panel: #16161a; --kit-fg: #f4f4f5; --kit-muted: #a1a1aa; --kit-line: #2a2a30; --kit-accent: #93b4ff; --kit-ok: #34d399; --kit-off: #71717a; color-scheme: dark; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--kit-bg); color: var(--kit-fg); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
.top {{ padding: 24px 24px 8px; max-width: 1600px; margin: 0 auto; }}
h1 {{ margin: 0 0 4px; font-size: 22px; }}
.question {{ margin: 0; color: var(--kit-muted); max-width: 70ch; }}
.bar {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 0; }}
.bar button {{ font: inherit; font-size: 13px; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--kit-line); background: var(--kit-panel); color: var(--kit-fg); cursor: pointer; }}
.bar button[aria-pressed="true"] {{ background: var(--kit-fg); color: var(--kit-bg); }}
.grid {{ display: grid; grid-template-columns: repeat({n}, minmax(0, 1fr)); gap: 16px; padding: 16px 24px 32px; max-width: 1600px; margin: 0 auto; }}
.grid.one {{ grid-template-columns: minmax(0, 1fr); }}
.grid.one .dir:not(.is-shown) {{ display: none; }}
.dir {{ background: var(--kit-panel); border: 1px solid var(--kit-line); border-radius: 12px; padding: 14px; min-width: 0; }}
.dir--chosen {{ border-color: var(--kit-ok); box-shadow: 0 0 0 2px var(--kit-ok); }}
.dir--rejected {{ opacity: .72; }}
.dir header {{ display: flex; align-items: center; gap: 8px; }}
.letter {{ width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-size: 13px; background: var(--kit-fg); color: var(--kit-bg); flex: none; }}
.dir h2 {{ margin: 0; font-size: 16px; flex: 1; min-width: 0; }}
.badge {{ font-size: 12px; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--kit-line); color: var(--kit-muted); white-space: nowrap; }}
.dir--chosen .badge {{ color: var(--kit-ok); border-color: var(--kit-ok); }}
.frame {{ margin: 12px 0; border: 1px solid var(--kit-line); border-radius: 8px; overflow: hidden; background: var(--kit-bg); }}
.screen {{ position: relative; width: 100%; }}
.screen iframe {{ position: absolute; top: 0; left: 0; border: 0; background: #fff; transform-origin: 0 0; }}
.summary {{ margin: 0 0 8px; }}
dl {{ margin: 0; font-size: 13px; }}
dt {{ font-weight: 600; margin-top: 8px; }}
dd {{ margin: 2px 0 0; color: var(--kit-muted); }}
dd ul {{ margin: 0; padding-left: 18px; }}
dd p {{ margin: 0; }}
.none {{ margin: 0; }}
.open {{ display: inline-block; margin-top: 12px; font-size: 13px; color: var(--kit-accent); }}
.decision {{ max-width: 1600px; margin: 0 auto 32px; padding: 0 24px; }}
.decision h2 {{ font-size: 16px; margin: 0 0 4px; }}
.decision p {{ margin: 0 0 4px; }}
.decision .meta {{ color: var(--kit-muted); font-size: 13px; }}
@media (max-width: 900px) {{ .grid {{ grid-template-columns: minmax(0, 1fr); }} }}
</style>
</head>
<body>
<div class="top">
  <h1>{title}</h1>
  <p class="question">{question}</p>
  <div class="bar" role="toolbar" aria-label="{l_view}">
    <button type="button" data-vp="390" aria-pressed="false">{l_phone}</button>
    <button type="button" data-vp="768" aria-pressed="false">{l_tablet}</button>
    <button type="button" data-vp="1280" aria-pressed="true">{l_desktop}</button>
    <button type="button" data-layout="side" aria-pressed="true">{l_side}</button>
    {one}
  </div>
</div>
{decision}
<div class="grid" id="grid">
{cols}
</div>
<script>
(function () {{
  var vp = 1280, grid = document.getElementById('grid');
  var ratio = {{390: 844, 768: 1024, 1280: 800}};
  function fit() {{
    document.querySelectorAll('.screen').forEach(function (s) {{
      var w = s.clientWidth, scale = w / vp, f = s.querySelector('iframe');
      f.style.width = vp + 'px'; f.style.height = ratio[vp] + 'px'; f.style.transform = 'scale(' + scale + ')';
      s.style.height = Math.round(ratio[vp] * scale) + 'px';
    }});
  }}
  document.querySelectorAll('[data-vp]').forEach(function (b) {{
    b.addEventListener('click', function () {{
      vp = +b.getAttribute('data-vp');
      document.querySelectorAll('[data-vp]').forEach(function (x) {{ x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); }});
      fit();
    }});
  }});
  document.querySelectorAll('[data-layout], [data-show]').forEach(function (b) {{
    b.addEventListener('click', function () {{
      var show = b.getAttribute('data-show');
      grid.classList.toggle('one', !!show);
      document.querySelectorAll('.dir').forEach(function (d) {{ d.classList.toggle('is-shown', d.getAttribute('data-dir') === show); }});
      document.querySelectorAll('[data-layout], [data-show]').forEach(function (x) {{ x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); }});
      fit();
    }});
  }});
  window.addEventListener('resize', fit);
  fit();
}})();
</script>
</body>
</html>
""".format(lang=E(cfg.get("language", "en")), title=E(data.get("title") or data["slug"]), l_compare=T("compareTitle"),
           question=E(data.get("question") or ""), n=len(data["directions"]), l_view=T("view"),
           l_phone=T("phone"), l_tablet=T("tablet"), l_desktop=T("desktop"), l_side=T("sideBySide"),
           one="".join('<button type="button" data-show="%s" aria-pressed="false">%s</button>' % (E(x["id"]), T("only", id=x["id"].upper()))
                       for x in data["directions"]),
           decision=decision, cols="\n".join(cols))


def cmd_compare(cfg, a):
    d = folder(cfg, a.slug)
    (d / "compare.html").write_text(compare_page(cfg, read_json(d)), encoding="utf-8")
    print("Wrote %s" % (d / "compare.html").relative_to(cfg["_root"]))


# ---------- choose ----------

def cmd_choose(cfg, a):
    d = folder(cfg, a.slug)
    data = read_json(d)
    ids = [x["id"] for x in data["directions"]]
    if a.id not in ids:
        die("unknown direction %r (have %s)" % (a.id, ", ".join(ids)))
    if not a.reason.strip():
        die("--reason is required: write why the user chose this direction")
    ctx_dir = Path(cfg["_root"]) / cfg["paths"]["context"]
    if ctx_dir.is_dir() and not (a.by or "").strip():
        die("--by is required: the project keeps a decision log (%s) and an approved decision names who decided" % cfg["paths"]["context"])
    errs, _ = check_errors(cfg, d, data)
    errs = [e for e in errs if "decision" not in e and "chosen" not in e]
    if errs:
        for e in errs:
            print("ERROR:", e)
        die("fix the exploration before recording a decision")
    merged_ids = {m.split(":", 1)[0].strip().lower() for m in a.merge or []}
    for x in data["directions"]:
        x["status"] = "chosen" if x["id"] == a.id else ("merged" if x["id"] in merged_ids else "rejected")
    data["decision"] = {"chosen": a.id, "reason": a.reason.strip(), "by": a.by or "", "on": today(), "merge": a.merge or []}
    data["status"] = "decided"
    write_json(d, data)
    chosen = next(x for x in data["directions"] if x["id"] == a.id)
    lines = [t(cfg, "explore.decisionMdTitle", title=data.get("title") or a.slug), "",
             t(cfg, "explore.decisionMdChosen", id=a.id.upper(), name=chosen.get("name") or ""), "",
             t(cfg, "explore.decisionMdReason", reason=a.reason.strip()), ""]
    if a.merge:
        lines += [t(cfg, "explore.decisionMdMerge"), ""] + ["- " + m for m in a.merge] + [""]
    lines += [t(cfg, "explore.decisionMdRejected"), ""]
    lines += ["- %s · %s" % (x["id"].upper(), x.get("name") or "") for x in data["directions"] if x["status"] == "rejected"] or ["- —"]
    lines += ["", t(cfg, "explore.decisionMdMeta", by=a.by or "—", on=today()), ""]
    (d / "decision.md").write_text("\n".join(lines), encoding="utf-8")
    (d / "compare.html").write_text(compare_page(cfg, data), encoding="utf-8")
    print("Recorded: %s chose %s (%s). Wrote decision.md and compare.html." % (a.by or "user", a.id.upper(), chosen.get("name") or ""))
    if ctx_dir.is_dir():
        sys.path.insert(0, str(KIT / "skills" / "context" / "scripts"))
        import decisions  # noqa: E402
        others = ["%s · %s: %s" % (x["id"].upper(), x.get("name") or "", x["status"]) for x in data["directions"] if x["id"] != a.id]
        did, path = decisions.add_decision(
            cfg, "%s: %s" % (data.get("title") or a.slug, chosen.get("name") or a.id.upper()), status="approved",
            scope=",".join(v for v in [data.get("app") or "", "exploration:" + a.slug] if v),
            source=str((d / "decision.md").relative_to(cfg["_root"])), context=data.get("question") or "",
            decision=(chosen.get("summary") or "") + "\n\n" + a.reason.strip()
                     + ("".join("\n- " + m for m in a.merge) if a.merge else ""),
            alternatives="\n".join("- " + o for o in others), by=a.by.strip())
        print("Decision log: %s (approved) %s" % (did, path.relative_to(cfg["_root"])))
    print("Next: prototype, with %s/%s/index.html as the approved direction." % (d.relative_to(cfg["_root"]), a.id))


def cmd_list(cfg, a):
    base = Path(cfg["_root"]) / cfg["paths"]["explorations"]
    rows = []
    for f in sorted(base.glob("*/directions.json")) if base.is_dir() else []:
        data = json.loads(f.read_text(encoding="utf-8"))
        dec = data.get("decision") or {}
        rows.append("%-28s %-10s %-3s %s" % (data.get("slug"), data.get("status", "?"), (dec.get("chosen") or "-").upper(), data.get("title") or ""))
    print("\n".join(rows) if rows else "No explorations in %s" % cfg["paths"]["explorations"])


def main():
    ap = argparse.ArgumentParser(description="Design explorations: directions, comparison page, decision.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="create an exploration folder")
    p.add_argument("slug"); p.add_argument("--title", required=True); p.add_argument("--question")
    p.add_argument("--directions", type=int, default=3); p.add_argument("--app")
    p = sub.add_parser("check", help="validate an exploration"); p.add_argument("slug")
    p = sub.add_parser("compare", help="write compare.html"); p.add_argument("slug")
    p = sub.add_parser("choose", help="record the user's choice")
    p.add_argument("slug"); p.add_argument("id"); p.add_argument("--reason", required=True)
    p.add_argument("--by"); p.add_argument("--merge", action="append", help='"<id>: part to keep", repeatable')
    sub.add_parser("list", help="list explorations")
    a = ap.parse_args()
    cfg = load()
    app_id = getattr(a, "app", None)  # the app's own DS profile (apps[].ds): markers and version meta
    slug = getattr(a, "slug", None)
    if not app_id and slug and SLUG.match(slug) and (folder(cfg, slug, False) / "directions.json").is_file():
        app_id = read_json(folder(cfg, slug)).get("app")
    cfg = for_app(cfg, app_id)
    {"init": cmd_init, "check": cmd_check, "compare": cmd_compare, "choose": cmd_choose, "list": cmd_list}[a.cmd](cfg, a)


if __name__ == "__main__":
    main()
