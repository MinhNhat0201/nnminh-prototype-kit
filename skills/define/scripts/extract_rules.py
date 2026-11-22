#!/usr/bin/env python3
"""Draft business rules of an existing page, for porting it (requirement source "existing running page" in define).

Lists what a user can see or trip over, read from the page and its scripts: visible text, toast and error messages,
input constraints (maxlength, minlength, required, pattern, min, max, step, input types), numeric limits in code,
route patterns (#/…, and a row at each route built at run time) and storage keys (localStorage, sessionStorage, the
project's storage wrapper in kit.config.json > define.storageCalls, and any .get/.put/.set/.remove call with a string key,
marked "via a wrapper?"). Messages are the string arguments of the calls in define.messageCalls (toast, alert…); other
strings of the scripts a user may read (labels, mock data) are listed apart as "text in script". The output is a draft
table (id, kind, text or value, source file:line) for the agent to complete into the parity checklist of the plan. It
never decides a rule.

Usage:
  extract_rules.py <file or folder>… [--json] [--out <file.md>]
      Files: .html .htm .js .mjs .ts .vue .jsx .tsx (a folder is read recursively, node_modules and dist skipped).
      Default output: a Markdown table on stdout in the project language (kit.config.json > language, else English).
  extract_rules.py --selftest

Never edits the page. Never commits or sends anything.
"""
import html as htmllib
import json
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import DEFAULTS, load, t  # noqa: E402

EXT = {".html", ".htm", ".js", ".mjs", ".ts", ".vue", ".jsx", ".tsx"}
SKIP = {"node_modules", "dist", ".git"}
KINDS = ("text", "message", "string", "input", "limit", "route", "storage")
MESSAGE_CALLS = DEFAULTS["define"]["messageCalls"]  # kit.config.json > define.messageCalls
WRAPPER_VERBS = ("get", "put", "set", "remove")
NOT_STORAGE = {"headers", "searchparams", "params", "query", "formdata", "dataset", "attributes", "classlist", "style",
               "map", "cache", "url", "router", "route", "app", "axios", "http", "api", "fetch"}

STR = re.compile(r"""'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`""")
COMMENT = re.compile(r"/\*.*?\*/|(?<![:\\'\"])//[^\n]*", re.S)
LIMIT = [re.compile(p) for p in (
    r"[\w$.\])]*\.length\s*(?:>=?|<=?|===?|!==?)\s*\d+",
    r"\b(?:max|min)\w*\s*[:=]\s*\d+",
    r"\b[A-Z][A-Z0-9_]*(?:MAX|MIN|LIMIT)[A-Z0-9_]*\s*[:=]\s*\d+|\b(?:MAX|MIN|LIMIT)[A-Z0-9_]*\s*[:=]\s*\d+",
    r"\blimit\w*\s*[:=]\s*\d+",
    r"[\w$.\])]*\.(?:slice|substring|substr)\(\s*0\s*,\s*\d+\s*\)",
    r"Math\.(?:min|max)\([^()]*\d+[^()]*\)")]
STORAGE = re.compile(r"(localStorage|sessionStorage)\s*\.\s*(?:getItem|setItem|removeItem)\(\s*['\"`]([^'\"`]+)")
ROUTE_RX = re.compile(r"/\^?#\\/(?:\\.|[^/\\\n])*/[a-z]*")
WS = re.compile(r"\s*")
CALL = re.compile(r"(?<![\w$.])((?:[A-Za-z_$][\w$]*\s*(?:\?\.|\.)\s*)*[A-Za-z_$][\w$]*)\s*\(")
CONCAT = re.compile(r"(?:\s*\+\s*(?:[\w$.]+(?:\[[^\]\n]*\])?(?:\([^()\n]*\))?|'[^'\n]*'|\"[^\"\n]*\"))+")
DYN_KEY = re.compile(r"[\w$\]]\s*\[\s*(['\"`])(#?/[^'\"`\n]*)\1\s*\+[^\]\n]+\]")
TAG = re.compile(r"<([a-zA-Z][\w-]*)((?:\s+[^\s=>/]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?)*)\s*/?>")
ATTR = re.compile(r"([^\s=>/]+)(?:\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+))?")
VISIBLE_ATTRS = ("placeholder", "title", "aria-label", "alt", "label")
INPUT_ATTRS = ("maxlength", "minlength", "required", "pattern", "min", "max", "step", "accept")
INPUT_TYPES = ("email", "number", "tel", "url", "date", "time", "datetime-local", "month", "file", "password")


def visible(s):
    """True when a string literal looks like text a user reads (not a selector, class, key, URL or code)."""
    s = s.strip()
    if len(s) < 2 or not re.search(r"[^\W\d_]", s) or s.startswith(("#", ".", "/", "http", "data:", "--", "@")):
        return False
    if s in ("use strict", "use client") or "<" in s or '="' in s:  # a directive, or a piece of HTML built by concatenation
        return False
    if re.search(r"[{};]|=>|\$\(|^\w+\(|\w\.\w+\(|^[\w-]+:[\w-]", s) or re.fullmatch(r"[\w.\-/]+\.(?:js|css|html|png|svg|json|webp|jpg)", s):
        return False
    if re.search(r"\s", s) or re.search(r"[^\x00-\x7f]", s):
        # a class list or a key list ("btn btn-primary", "is_open is_dirty") is not text
        # ... nor a class list with a size or state token ("s16 ok")
        return not (re.fullmatch(r"[a-z0-9_-]+(?:\s+[a-z0-9_-]+)*", s) and re.search(r"[-_]|\b[a-z]+\d+\b", s))
    return bool(re.fullmatch(r"[A-Z][a-z]+[.!?…]?", s))


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def blank(m):
    return re.sub(r"[^\n]", " ", m.group(0))


def from_markup(text, base, out, src):
    """Visible text, visible attributes, input constraints and #/ links of HTML (or a Vue template)."""
    clean = re.sub(r"<(script|style|svg)\b.*?</\1\s*>|<!--.*?-->", blank, text, flags=re.S | re.I)
    for m in TAG.finditer(clean):
        tag, attrs = m.group(1).lower(), {}
        for a in ATTR.finditer(m.group(2) or ""):
            attrs[a.group(1).lower()] = htmllib.unescape((a.group(2) or "").strip("\"'"))
        ln = base + line_of(text, m.start())
        for k in VISIBLE_ATTRS:
            v = attrs.get(k, "")
            if v and not v.startswith(("{", "$")) and re.search(r"[^\W\d_]", v):
                out.append(("text", "%s: %s" % (k, v), src, ln, None))
        cons = ["%s=%s" % (k, attrs[k]) if attrs[k] else k for k in INPUT_ATTRS if k in attrs]
        if attrs.get("type") in INPUT_TYPES:
            cons.insert(0, "type=" + attrs["type"])
        if cons and tag in ("input", "textarea", "select"):
            who = attrs.get("id") or attrs.get("name") or attrs.get("placeholder") or tag
            out.append(("input", "%s %s: %s" % (tag, who, ", ".join(cons)), src, ln, None))
        for k in ("href", "to", ":to"):
            if attrs.get(k, "").startswith("#/"):
                out.append(("route", attrs[k], src, ln, None))
    for m in re.finditer(r">([^<>]+)<", clean):
        s = re.sub(r"\s+", " ", htmllib.unescape(m.group(1))).strip()
        if s and re.search(r"[^\W\d_]", s) and not re.fullmatch(r"\{\{[^}]*\}\}", s):
            out.append(("text", s, src, base + line_of(text, m.start(1)), None))


def close_paren(code, i):
    """Index of the parenthesis that closes the one at code[i] (strings skipped), or len(code)."""
    depth, j = 0, i
    while j < len(code):
        c = code[j]
        if c in "'\"`":
            m = STR.match(code, j)
            if m:
                j = m.end()
                continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return len(code)


def named(callee, names):
    """True when a call (X.store.get, toast) is one of the names: the whole callee, or its last part ("toast" matches X.toast)."""
    low = callee.lower()
    return any(low == n.lower() or low.endswith("." + n.lower()) for n in names)


def from_script(text, base, out, src, opts=None):
    """Messages (string arguments of the message calls), other strings a user may read, limits, routes (static, and a
    row at each route built at run time), storage keys (Web Storage, configured wrapper calls, other .get/.put calls)."""
    opts = opts or {}
    code = COMMENT.sub(blank, text)
    msg_calls = opts.get("messageCalls") or MESSAGE_CALLS
    store_calls, prefix = opts.get("storageCalls") or [], opts.get("storagePrefix") or ""
    spans = []
    for m in CALL.finditer(code):
        callee = re.sub(r"\s|\?", "", m.group(1))
        if named(callee, msg_calls):
            spans.append((m.end(), close_paren(code, m.end() - 1)))
        arg = STR.match(code, WS.match(code, m.end()).end())
        key = next((g for g in arg.groups() if g is not None), None) if arg else None
        if not key or "${" in key or callee.split(".")[0] in ("localStorage", "sessionStorage"):
            continue
        ln = base + line_of(code, m.start())
        parts = callee.split(".")
        if store_calls and named(callee, store_calls):
            out.append(("storage", "%s %s%s" % (callee, prefix, key), src, ln, None))
        elif len(parts) > 1 and parts[-1] in WRAPPER_VERBS and parts[-2].lower() not in NOT_STORAGE:
            out.append(("storage", "%s %s" % (callee, key), src, ln, "wrapper"))
    for m in STR.finditer(code):
        raw = next(g for g in m.groups() if g is not None)
        ln = line_of(code, m.start())
        s = re.sub(r"\$\{[^{}]*\}", "{…}", raw).replace("\\'", "'").replace('\\"', '"').replace("\\n", " ")
        if s.startswith("#/"):
            tail = CONCAT.match(code, m.end())
            if tail or "${" in raw:  # a route built at run time ('#/' + kind, `#/${id}`)
                out.append(("route", m.group(0) + (re.sub(r"\s+", "", tail.group(0)) if tail else ""), src, base + ln, "dynamic"))
            else:
                out.append(("route", s, src, base + ln, None))
            continue
        if "<" in s and ">" in s:  # an HTML template inside a string
            from_markup(s, base + ln - 1, out, src)
            continue
        if visible(re.sub(r"\$\{[^{}]*\}", "x", raw)):
            kind = "message" if any(a <= m.start() < b for a, b in spans) else "string"
            out.append((kind, s.strip(), src, base + ln, None))
    for m in DYN_KEY.finditer(code):  # R['/' + k] = …: a route table filled at run time
        out.append(("route", re.sub(r"\s+", "", m.group(0)), src, base + line_of(code, m.start()), "dynamic"))
    for rx in LIMIT:
        for m in rx.finditer(code):
            out.append(("limit", re.sub(r"\s+", " ", m.group(0)), src, base + line_of(code, m.start()), None))
    for m in STORAGE.finditer(code):
        out.append(("storage", "%s %s" % (m.group(1), m.group(2)), src, base + line_of(code, m.start()), None))
    for m in ROUTE_RX.finditer(code):
        out.append(("route", m.group(0), src, base + line_of(code, m.start()), None))


def extract(path, rel, opts=None):
    text = path.read_text(encoding="utf-8", errors="replace")
    out = []
    if path.suffix in (".html", ".htm", ".vue"):
        for m in re.finditer(r"<script\b[^>]*>(.*?)</script\s*>", text, re.S | re.I):
            if not re.search(r"\bsrc\s*=", text[m.start():m.start(1)]):
                from_script(m.group(1), line_of(text, m.start(1)) - 1, out, rel, opts)
        from_markup(text, 0, out, rel)
    else:
        from_script(text, 0, out, rel, opts)
    return out


def collect(paths, root, opts=None):
    """Rows of the files: opts = kit.config.json > define (messageCalls, storageCalls, storagePrefix)."""
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files += [f for f in sorted(p.rglob("*")) if f.is_file() and f.suffix in EXT and not (SKIP & set(f.parts))]
        elif p.is_file():
            files.append(p)
        else:
            sys.exit("ERROR: not found: %s" % p)
    rows, seen = [], {}
    for f in files:
        try:
            rel = f.resolve().relative_to(root).as_posix()
        except ValueError:
            rel = f.as_posix()
        for kind, text, src, ln, note in extract(f, rel, opts):
            key = (kind, text, note) + ((src, ln) if note == "dynamic" else ())  # a route built at run time: one row per site
            if key in seen:
                seen[key]["also"] += 1
                continue
            row = {"kind": kind, "text": text, "source": "%s:%d" % (src, ln), "also": 0}
            if note:
                row["note"] = note
            seen[key] = row
            rows.append(row)
    rows.sort(key=lambda r: (KINDS.index(r["kind"]), r["source"].split(":")[0], int(r["source"].rsplit(":", 1)[1])))
    for i, r in enumerate(rows, 1):
        r["id"] = "E%03d" % i
    return rows


def markdown(cfg, rows, sources):
    out = ["# " + t(cfg, "define.extract.title"), "", t(cfg, "define.extract.intro", sources=", ".join(sources)), "",
           "| ID | %s | %s | %s | %s |" % (t(cfg, "define.extract.kind"), t(cfg, "define.extract.text"),
                                         t(cfg, "define.extract.source"), t(cfg, "define.extract.rule")),
           "|---|---|---|---|---|"]
    for r in rows:
        txt = r["text"].replace("|", "\\|") + (" " + t(cfg, "define.extract.note." + r["note"]) if r.get("note") else "")
        src = r["source"] + (" (+%d)" % r["also"] if r["also"] else "")
        out.append("| %s | %s | %s | `%s` | |" % (r["id"], t(cfg, "define.extract.kind." + r["kind"]), txt, src))
    counts = {k: sum(1 for r in rows if r["kind"] == k) for k in KINDS}
    out += ["", t(cfg, "define.extract.counts", **counts), ""]
    return "\n".join(out)


def selftest():
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="extract-rules-"))
    (d / "js").mkdir()
    (d / "index.html").write_text(
        '<!doctype html><html><head><style>.a{color:red}</style></head><body>\n'
        '<h1>Notes</h1>\n<a href="#/n/new">New note</a>\n'
        '<input id="title" maxlength="80" required placeholder="Note title">\n'
        '<input type="email" name="mail">\n'
        '<script>\nconst MAX_NOTES = 50; // keep\nif (t.length > 80) toast("Title is too long");\n'
        "localStorage.setItem('acme:notes', x);\n</script>\n<script src=\"js/app.js\"></script>\n</body></html>\n", encoding="utf-8")
    (d / "js" / "app.js").write_text(
        "const R = /^#\\/n\\/(\\w+)$/;\nfunction del(){ showError(`Could not delete ${name}`); }\n"
        "el.innerHTML = `<button class=\"btn\">Save note</button>`;\nconst cls = 'x-note-card';\n"
        "go('#/');\nconst s = items.slice(0, 20);\nX.toast('Đã lưu');\nconst label = 'Cancel';\n"
        "'use strict';\nvar h = '<span class=\"fti '+f.ft+' solid\" role=\"img\" aria-label=\"'+f.tg+'\">';\nico('check','s16 ok');\n"
        "FILES.unshift({n:'Uploaded file', time:'Just now'}); toast('success', 'File uploaded (mock).');\n"
        "var view = X.store.get('libView', 'grid'); X.store.put('libView', view);\nprefs.set('acme-density', 'compact');\n"
        "u.searchParams.get('q');\nt.onclick = function(){ location.hash = '#/' + t.dataset.k };\n"
        "Object.keys(TABN).forEach(function(k){ R['/' + k] = show; });\ngo(`#/n/${id}`);\n", encoding="utf-8")
    rows = collect([d], d, {"storageCalls": ["X.store.get", "X.store.put"], "storagePrefix": "acme."})
    got = {(r["kind"], r["text"]) for r in rows}
    want = {("text", "Notes"), ("text", "New note"), ("text", "placeholder: Note title"), ("route", "#/n/new"),
            ("input", "input title: maxlength=80, required"), ("input", "input mail: type=email"),
            ("limit", "MAX_NOTES = 50"), ("limit", "t.length > 80"), ("message", "Title is too long"),
            ("storage", "localStorage acme:notes"), ("route", "/^#\\/n\\/(\\w+)$/"), ("message", "Could not delete {…}"),
            ("text", "Save note"), ("route", "#/"), ("limit", "items.slice(0, 20)"), ("message", "Đã lưu"), ("string", "Cancel"),
            ("string", "Uploaded file"), ("string", "Just now"), ("message", "File uploaded (mock)."),
            ("storage", "X.store.get acme.libView"), ("storage", "X.store.put acme.libView"), ("storage", "prefs.set acme-density"),
            ("route", "'#/'+t.dataset.k"), ("route", "R['/'+k]"), ("route", "`#/n/${id}`")}
    assert want <= got, sorted(want - got)
    noise = ("use strict", "s16 ok", "success", "grid")
    assert not any(r["text"] in noise or "<span" in r["text"] or '="' in r["text"] for r in rows), sorted(got)
    notes = {r["text"]: r.get("note") for r in rows}
    assert notes["prefs.set acme-density"] == "wrapper" and notes["X.store.get acme.libView"] is None, notes
    assert notes["R['/'+k]"] == notes["`#/n/${id}`"] == "dynamic" and notes["#/"] is None, notes
    assert not any("searchParams" in r["text"] for r in rows), "URL parameters are not storage"
    plain = {(r["kind"], r["text"]) for r in collect([d / "js"], d)}
    assert ("storage", "X.store.get libView") in plain and ("storage", "X.store.get acme.libView") not in plain, plain
    assert not any(r["text"] in ("x-note-card", "acme:notes", "keep", "btn") for r in rows if r["kind"] in ("text", "message")), got
    assert all(re.fullmatch(r"(index\.html|js/app\.js):\d+", r["source"]) for r in rows), [r["source"] for r in rows]
    src = {r["text"]: r["source"] for r in rows}
    assert src["Title is too long"] == "index.html:8" and src["Could not delete {…}"] == "js/app.js:2", src
    md = markdown("en", rows, ["index.html"])
    assert "| E001 |" in md and "Parity" in md and "Rule" in md and "built at run time" in md and "wrapper" in md, md
    assert "Quy tắc" in markdown("vi", rows, ["index.html"])
    print("extract_rules.py selftest OK")


def main():
    argv = sys.argv[1:]
    if "--selftest" in argv:
        selftest()
        return
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    as_json, out_file, paths = "--json" in argv, None, []
    i = 0
    while i < len(argv):
        if argv[i] == "--out":
            if i + 1 >= len(argv):
                sys.exit("ERROR: --out needs a file")
            out_file, i = argv[i + 1], i + 2
            continue
        if argv[i] != "--json":
            paths.append(argv[i])
        i += 1
    if not paths:
        sys.exit("ERROR: give the page files or folders to read")
    cfg = load(require=False) or {"language": "en"}
    root = Path(cfg.get("_root") or Path.cwd()).resolve()
    opts = cfg.get("define") or {}
    for k in ("messageCalls", "storageCalls"):
        if not isinstance(opts.get(k) or [], list):
            sys.exit("ERROR: kit.config.json > define.%s must be a list of call names" % k)
    rows = collect(paths, root, opts)
    text = json.dumps(rows, ensure_ascii=False, indent=1) if as_json else markdown(cfg, rows, paths)
    if out_file:
        Path(out_file).write_text(text + "\n", encoding="utf-8")
        print("Wrote %s: %d rows" % (out_file, len(rows)))
    else:
        print(text)


if __name__ == "__main__":
    main()
