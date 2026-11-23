#!/usr/bin/env python3
"""Draft business rules of an existing page, for porting it (requirement source "existing running page" in define).

Lists what a user can see or trip over, read from the page and its scripts: visible text, toast and error messages,
input constraints (maxlength, minlength, required, pattern, min, max, step, input types), numeric limits in code,
route patterns (#/…, and a row at each route built at run time), URL parameters (?ext=1, searchParams.get('x'),
URLSearchParams) and storage keys (localStorage, sessionStorage, the project's storage wrapper in kit.config.json >
define.storageCalls, any .get/.put/.set/.remove call and any bare get/put/lsGet/lsSet-like call with a string key, marked
"via a wrapper?"; a key held in a constant, KEY = 'app.pos' then getItem(KEY), is resolved). Messages are the string
arguments of the calls in define.messageCalls (toast, alert…) and data-msg attributes; other strings of the scripts a user
may read (labels, mock data) are listed apart as "text in script"; markup built in script strings (pieces of HTML,
template literals) gives its text and its title, aria-label, placeholder attributes; a tag cut across string pieces
joined with + ('<b title="Open ' + n + ' files">') is read as one piece, so its pieces are never text (K7-1); the second
argument of .replace / .replaceAll (the text put in: 'Comment', 'aria-label="Comment on slide $1"') gives its text and
visible attributes (K7-2). The output is a draft table (id,
kind, text or value, source file:line) for the agent to complete into the parity checklist of the plan. It never decides
a rule.

Usage:
  extract_rules.py <file or folder>… [--json] [--out <file.md>] [--skip-shell] [--exclude <glob>]… [--function <name>]…
      Files: .html .htm .js .mjs .ts .vue .jsx .tsx (a folder is read recursively, node_modules and dist skipped).
      --skip-shell: leave out the regions of the shared shell, by default <!-- SHELL:x --> … <!-- /SHELL:x --> and
      <!-- SHELL:BEGIN … --> … <!-- SHELL:END --> (HTML), /* SHELL:x */ … /* /SHELL:x */ and /* SHELL:BEGIN */ … /* SHELL:END */
      (scripts, CSS); kit.config.json > define.skipRegions replaces them with your own
      regular expressions (each matches a whole region).
      --exclude <glob>: skip files whose path (relative to the project, or to the folder given) matches, e.g. '**/shared/**'.
      --function <name>: in scripts, read only the body of this function (function name(…){…}, name = function…,
      name(…) {…} methods, const name = (…) => {…}); markup outside scripts is then left out. Repeatable.
      Default output: a Markdown table on stdout in the project language (kit.config.json > language, else English).
  extract_rules.py --selftest

Never edits the page. Never commits or sends anything.
"""
import fnmatch
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
KINDS = ("text", "message", "string", "input", "limit", "route", "param", "storage")
MESSAGE_CALLS = DEFAULTS["define"]["messageCalls"]  # kit.config.json > define.messageCalls
WRAPPER_VERBS = ("get", "put", "set", "remove")
# a bare call that looks like a storage helper: get('k', d), put('k', v), lsGet('k'), storeSet('k', v), saveLocal('k', v)
BARE_STORE = re.compile(r"(?i)(?:get|put|set|remove)|(?:ls|store|storage|prefs?|local|session)_?(?:get|set|put|remove|del|load|save)(?:item)?"
                        r"|(?:get|set|put|remove|load|save)_?(?:ls|store|storage|prefs?|local)")
# <!-- SHELL:BEGIN (any note) --> … <!-- SHELL:END -->, and <!-- SHELL:x --> … <!-- /SHELL:x --> (HTML and /* */ in scripts)
SHELL_REGIONS = [r"<!--\s*SHELL:BEGIN\b.*?-->.*?<!--\s*SHELL:END\b.*?-->", r"/\*\s*SHELL:BEGIN\b.*?\*/.*?/\*\s*SHELL:END\b.*?\*/",
                 r"<!--\s*SHELL:([\w-]+)\s*-->.*?<!--\s*/SHELL:\1\s*-->", r"/\*\s*SHELL:([\w-]+)\s*\*/.*?/\*\s*/SHELL:\1\s*\*/"]
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
STORAGE = re.compile(r"(localStorage|sessionStorage)\s*\.\s*(?:getItem|setItem|removeItem)\(\s*(['\"`])([^'\"`]+)\2(\s*\+\s*([A-Za-z_$][\w$]*\b(?!\s*[.(\[]))?)?")
STORAGE_ID = re.compile(r"(localStorage|sessionStorage)\s*\.\s*(?:getItem|setItem|removeItem)\(\s*([A-Za-z_$][\w$]*)\s*[,)]")
CONST = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*=\s*(['\"])([^'\"\n]+)\2\s*[;,\n)]")
PARAM = re.compile(r"(?:searchParams|URLSearchParams\([^()]*(?:\([^()]*\))?[^()]*\)|\b(?:params|query|qs|usp|sp))\s*\.\s*(?:get|has|getAll|set|delete|append)\(\s*['\"`]([\w.\-]+)")
QUERY = re.compile(r"[?&]([A-Za-z_][\w\-]*)=([\w\-.%]*)")
IDENT = re.compile(r"[A-Za-z_$][\w$]*")
QUERY_LIT = re.compile(r"[?&]?([A-Za-z_][\w\-]*)=([\w\-.%]*)")   # a whole literal 'ext=1' (appended after '?' or '&')
# function get(k, d) { … localStorage.getItem('app.' + k) … } (also get = function(k)…, get = (k) => …, get = k => …; the key
# 'app.' + k, `app.${k}` or PREFIX + k with PREFIX = 'app.'): a wrapper, its calls give the stored key (in any file of the run)
WRAP_HEAD = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(\s*([A-Za-z_$][\w$]*)|(?<![\w$.])([A-Za-z_$][\w$]*)\s*[:=]\s*(?:async\s+)?"
                       r"(?:function\b[^(]*\(\s*([A-Za-z_$][\w$]*)|\(\s*([A-Za-z_$][\w$]*)[^()]*\)\s*=>|([A-Za-z_$][\w$]*)\s*=>)")
WRAP_KEY = (r"(localStorage|sessionStorage)\s*\.\s*(?:get|set|remove)Item\(\s*(?:(['\"])([^'\"\n]*)\2\s*\+\s*{p}\b"
            r"|`([^`$]*)\$\{{\s*{p}\s*\}}`|([A-Za-z_$][\w$]*)\s*\+\s*{p}\b)")
# a regular expression literal (/[&<>"']/g): blanked before strings are read, so its quotes start no string
RX_LIT = re.compile(r"/(?![*/])(?:\\.|\[(?:\\.|[^\]\\\n])*\]|[^/\\\n\[])+/[dgimsuyv]*")
RX_AFTER = set("(,=:[!&|?{};+-*%<>~^")
RX_WORDS = {"return", "typeof", "case", "in", "of", "void", "delete", "instanceof", "new", "throw", "else", "do", "yield", "await"}
# a name declared in a file (function x, var x, a parameter x): a wrapper of another file with that name is not this one
DECLARED = r"\bfunction\s+{n}\b|\b(?:var|let|const)\s+{n}\b|\bfunction\b[^(\n]*\([^)]*\b{n}\b[^)]*\)|\([^()]*\b{n}\b[^()]*\)\s*=>|\b{n}\s*=>"
CODEY = re.compile(r"\bfunction\s*\(|=>|[{}]")   # a piece of code, never text a user reads
ROUTE_RX = re.compile(r"/\^?#\\/(?:\\.|[^/\\\n])*/[a-z]*")
WS = re.compile(r"\s*")
CALL = re.compile(r"(?<![\w$.])((?:[A-Za-z_$][\w$]*\s*(?:\?\.|\.)\s*)*[A-Za-z_$][\w$]*)\s*\(")
CONCAT = re.compile(r"(?:\s*\+\s*(?:[\w$.]+(?:\[[^\]\n]*\])?(?:\([^()\n]*\))?|'[^'\n]*'|\"[^\"\n]*\"))+")
DYN_KEY = re.compile(r"[\w$\]]\s*\[\s*(['\"`])(#?/[^'\"`\n]*)\1\s*\+[^\]\n]+\]")
TAG = re.compile(r"<([a-zA-Z][\w-]*)((?:\s+[^\s=>/]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?)*)\s*/?>")
ATTR = re.compile(r"([^\s=>/]+)(?:\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+))?")
VISIBLE_ATTRS = ("placeholder", "title", "aria-label", "alt", "label", "data-title", "data-tip", "data-tooltip", "data-placeholder")
MESSAGE_ATTRS = ("data-msg", "data-message", "data-toast")   # text a click shows as a toast or a notice
INPUT_ATTRS = ("maxlength", "minlength", "required", "pattern", "min", "max", "step", "accept")
INPUT_TYPES = ("email", "number", "tel", "url", "date", "time", "datetime-local", "month", "file", "password")


def visible(s):
    """True when a string literal looks like text a user reads (not a selector, class, key, URL or code)."""
    s = s.strip()
    if len(s) < 2 or not re.search(r"[^\W\d_]", s) or s.startswith(("#", ".", "/", "http", "data:", "--", "@")):
        return False
    if s in ("use strict", "use client") or "<" in s or '="' in s:  # a directive, or a piece of HTML built by concatenation
        return False
    if re.match(r"[\"']\s*(?:\]|/?>|[\w-]+=)", s):   # the end of an attribute or a selector: '" src=', '"] .title'
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


def from_markup(text, base, out, src, fragment=False):
    """Visible text, visible attributes, input constraints and #/ links of HTML (or a Vue template). fragment: a piece of
    HTML from a script string, whose text may start or end the piece ('Delete</b>', '<div class="x">Start')."""
    clean = re.sub(r"<(script|style|svg)\b.*?</\1\s*>|<!--.*?-->", blank, text, flags=re.S | re.I)
    for m in TAG.finditer(clean):
        tag, attrs = m.group(1).lower(), {}
        for a in ATTR.finditer(m.group(2) or ""):
            attrs[a.group(1).lower()] = htmllib.unescape((a.group(2) or "").strip("\"'"))
        ln = base + line_of(text, m.start())
        for k in VISIBLE_ATTRS + MESSAGE_ATTRS:
            v = attrs.get(k, "")
            if v and (v.startswith("{…}") or not v.startswith(("{", "$"))) and re.search(r"[^\W\d_]", v.replace("{…}", "")):
                out.append(("message" if k in MESSAGE_ATTRS else "text", "%s: %s" % (k, v), src, ln, None))
        cons = ["%s=%s" % (k, attrs[k]) if attrs[k] else k for k in INPUT_ATTRS if k in attrs]
        if attrs.get("type") in INPUT_TYPES:
            cons.insert(0, "type=" + attrs["type"])
        if cons and tag in ("input", "textarea", "select"):
            who = attrs.get("id") or attrs.get("name") or attrs.get("placeholder") or tag
            out.append(("input", "%s %s: %s" % (tag, who, ", ".join(cons)), src, ln, None))
        for k in ("href", "to", ":to"):
            if attrs.get(k, "").startswith("#/"):
                out.append(("route", attrs[k], src, ln, None))
    for m in re.finditer(r"(?:^|>)([^<>]+)(?=<|$)" if fragment else r">([^<>]+)<", clean):
        s = re.sub(r"\s+", " ", htmllib.unescape(m.group(1))).strip()
        if fragment and ('="' in s or "='" in s or re.fullmatch(r"[\s{}…]*", s) or CODEY.search(s.replace("{…}", ""))):
            continue   # an attribute piece, only {…}, or code around the piece (function(c){…}, =>)
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


def operand_end(code, i):
    """End of the operand of a concatenation that starts at code[i] (a name, a member, a call, a group), or i."""
    m = re.match(r"[!\-~]*\s*", code[i:])
    j = i + m.end()
    if j < len(code) and code[j] == "(":
        j = close_paren(code, j) + 1
    else:
        n = re.match(r"(?:new\s+)?[A-Za-z_$][\w$]*", code[j:])
        if not n:
            return i
        j += n.end()
    while j < len(code):
        t = re.match(r"\s*(?:\?\.|\.)\s*[A-Za-z_$][\w$]*", code[j:])
        if t:
            j += t.end()
        elif code[j] in "([":
            j = close_paren(code, j) + 1
        else:
            break
    return j


def concat_chain(code, m):
    """The string literals joined to the one matched by m with + ('<b title="' + t + '">' + x + 'Go</b>'): [(match, text)]
    with None for an operand that is no literal."""
    parts, j = [(m, None)], m.end()
    while True:
        p = re.match(r"\s*\+(?![+=])\s*", code[j:])
        if not p:
            return parts
        k = j + p.end()
        lit = STR.match(code, k)
        if lit:
            parts.append((lit, None))
            j = lit.end()
            continue
        e = operand_end(code, k)
        if e == k:
            return parts
        parts.append((None, None))
        j = e


def blank_regex(code):
    """code with its regular expression literals blanked (line numbers kept): a / after an operator, an opening bracket,
    a comma or a keyword such as return starts one; strings are skipped."""
    chars, i, n = list(code), 0, len(code)
    while i < n:
        c = code[i]
        if c in "'\"`":
            m = STR.match(code, i)
            if m:
                i = m.end()
                continue
        elif c == "/":
            j = i - 1
            while j >= 0 and code[j] in " \t\r\n":
                j -= 1
            w = re.search(r"[\w$]+$", code[max(0, j - 11):j + 1]) if j >= 0 else None
            if j < 0 or code[j] in RX_AFTER or (w and w.group(0) in RX_WORDS):
                m = RX_LIT.match(code, i)
                if m:
                    chars[i:m.end()] = " " * (m.end() - i)
                    i = m.end()
                    continue
        i += 1
    return "".join(chars)


def wrappers(code, consts=None):
    """{name: (localStorage|sessionStorage, key prefix, (start, end) of the body)} of the storage wrappers defined in code."""
    out = {}
    for m in WRAP_HEAD.finditer(code):
        name, prm = m.group(1) or m.group(3), m.group(2) or m.group(4) or m.group(5) or m.group(6)
        b = re.match(r"\s*\{" if m.group(0).endswith("=>") else r"[^{;\n]*\{", code[m.end():])
        if b:
            i = m.end() + b.end() - 1
            span = (i, close_paren(code, i) + 1)
        else:   # an arrow with an expression body: to the end of the line
            j = code.find("\n", m.end())
            span = (m.end(), len(code) if j < 0 else j)
        k = re.search(WRAP_KEY.format(p=re.escape(prm)), code[span[0]:span[1]])
        if not k:
            continue
        pre = k.group(3) if k.group(3) is not None else k.group(4) if k.group(4) is not None else (consts or {}).get(k.group(5))
        if pre is not None:
            out.setdefault(name, (k.group(1), pre, span))
    return out


def named(callee, names):
    """True when a call (X.store.get, toast) is one of the names: the whole callee, or its last part ("toast" matches X.toast)."""
    low = callee.lower()
    return any(low == n.lower() or low.endswith("." + n.lower()) for n in names)


def from_script(text, base, out, src, opts=None):
    """Messages (string arguments of the message calls), other strings a user may read, limits, routes (static, and a
    row at each route built at run time), storage keys (Web Storage, configured wrapper calls, other .get/.put calls)."""
    opts = opts or {}
    raw_code = COMMENT.sub(blank, text)
    code = blank_regex(raw_code)   # a regular expression literal is no string, no text (K4-5)
    msg_calls = opts.get("messageCalls") or MESSAGE_CALLS
    store_calls, prefix = opts.get("storageCalls") or [], opts.get("storagePrefix") or ""
    spans = []
    consts = {}   # KEY = 'app.pos': a storage key held in a constant (the first value given to the name)
    for m in CONST.finditer(code):
        consts.setdefault(m.group(1), m.group(3))
    own = wrappers(code, consts)
    wraps = {k: v + (None,) for k, v in own.items()}
    for k, v in (opts.get("_wraps") or {}).items():   # wrappers of other files of the run: (store, prefix, span, file),
        if k not in wraps and v[3] != src and not re.search(DECLARED.format(n=re.escape(k)), code):   # unless the name is
            wraps[k] = v                                                                                # declared here
    repl = []   # x.replace(a, b), f(x).replaceAll(a, b): (start, end) of b, the text put in (K7-2)
    for m in re.finditer(r"\.\s*replace(?:All)?\s*\(", code):
        end, j = close_paren(code, m.end() - 1), m.end()
        while j < end and code[j] != ",":   # the comma after the first argument
            lit = STR.match(code, j) if code[j] in "'\"`" else None
            j = lit.end() if lit else close_paren(code, j) + 1 if code[j] in "([{" else j + 1
        if j < end:
            repl.append((j + 1, end))
    for m in CALL.finditer(code):
        callee = re.sub(r"\s|\?", "", m.group(1))
        if named(callee, msg_calls):
            spans.append((m.end(), close_paren(code, m.end() - 1)))
        at = WS.match(code, m.end()).end()
        arg = STR.match(code, at)
        key = next((g for g in arg.groups() if g is not None), None) if arg else None
        if key is None:   # an identifier argument whose value is a constant string: get(KEY)
            idm = IDENT.match(code, at)
            key = consts.get(idm.group(0)) if idm and re.match(r"\s*[,)]", code[idm.end():]) else None
        if not key or "${" in key or callee.split(".")[0] in ("localStorage", "sessionStorage"):
            continue
        ln = base + line_of(code, m.start())
        parts = callee.split(".")
        if store_calls and named(callee, store_calls):
            out.append(("storage", "%s %s%s" % (callee, prefix, key), src, ln, None))
        elif len(parts) > 1 and parts[-1] in WRAPPER_VERBS and parts[-2].lower() not in NOT_STORAGE:
            out.append(("storage", "%s %s" % (callee, key), src, ln, "wrapper"))
        elif len(parts) == 1 and callee in wraps:   # a wrapper of this file or of another file of the run: the key is known
            w = wraps[callee]
            out.append(("storage", "%s %s%s (%s%s)" % (w[0], w[1], key, callee, ", " + w[3] if w[3] else ""), src, ln, None))
        elif len(parts) == 1 and BARE_STORE.fullmatch(callee) and re.fullmatch(r"[\w.:\-]+", key):
            out.append(("storage", "%s %s" % (callee, key), src, ln, "wrapper"))
    def norm(raw):
        return re.sub(r"\$\{[^{}]*\}", "{…}", raw).replace("\\'", "'").replace('\\"', '"').replace("\\n", " ")

    done = set()   # literals read as part of a concatenated piece of markup
    for m in STR.finditer(code):
        raw = next(g for g in m.groups() if g is not None)
        ln = line_of(code, m.start())
        s = norm(raw)
        if s.startswith("#/"):
            tail = CONCAT.match(code, m.end())
            if tail or "${" in raw:  # a route built at run time ('#/' + kind, `#/${id}`)
                out.append(("route", m.group(0) + (re.sub(r"\s+", "", tail.group(0)) if tail else ""), src, base + ln, "dynamic"))
            else:
                out.append(("route", s, src, base + ln, None))
            continue
        qs = [QUERY_LIT.fullmatch(raw)] if QUERY_LIT.fullmatch(raw) else QUERY.finditer(raw) if "?" in raw else ()
        for q in qs:   # a URL parameter: '?ext=1', 'a.html?tab=2', 'ext=1'
            out.append(("param", "%s=%s" % (q.group(1), q.group(2)), src, base + ln, None))
        if m.start() in done:
            continue
        if re.search(r"<[a-zA-Z][\w-]*(?:\s[^<>]*)?$", s):   # a tag left open: read the pieces joined with + as one (K7-1)
            parts = concat_chain(code, m)
            joined = "".join(norm(next(g for g in p.groups() if g is not None)) if p else "{…}" for p, _x in parts)
            if len(parts) > 1 and not re.search(r"<[a-zA-Z][\w-]*(?:\s[^<>]*)?$", joined):
                done.update(p.start() for p, _x in parts if p)
                n = len(out)
                from_markup(joined, base + ln - 1, out, src, fragment=True)
                for i in range(n, len(out)):   # an operand at the edge of a text is no part of it ('{…}Edit' is Edit)
                    if out[i][0] == "text" and not out[i][1].startswith(VISIBLE_ATTRS):
                        out[i] = (out[i][0], re.sub(r"^(?:\s*\{…\}\s*)+|(?:\s*\{…\}\s*)+$", "", out[i][1])) + out[i][2:]
                continue
        if ("<" in s and ">" in s) or re.search(r"[\"']\s*/?>", s):  # an HTML template inside a string (a whole one or a
            from_markup(s, base + ln - 1, out, src, fragment=True)       # piece of one: '">Next', 'by mail">' is tag)
            continue
        if any(a <= m.start() < b for a, b in repl):   # the text a .replace puts in: 'Comment', 'aria-label="Comment $1"'
            s = re.sub(r"\$[$&`'\d]+", "{…}", s)
            attrs = re.findall(r"(?<![\w-])(%s)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')" % "|".join(map(re.escape, VISIBLE_ATTRS)), s)
            for k, v1, v2 in attrs:
                if re.search(r"[^\W\d_]", v1 or v2):
                    out.append(("text", "%s: %s" % (k, htmllib.unescape(v1 or v2)), src, base + ln, None))
            if attrs:
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
        key, tail = m.group(3), consts.get(m.group(5) or "")   # 'app.' + K with K = 'pos': the whole key is known
        dyn = (bool(m.group(4)) and tail is None) or "${" in key   # 'app.' + k: a key prefix, the stored key is built at run time
        if dyn and any(a <= m.start() < b for _s, _p, (a, b) in own.values()):
            continue   # the prefix inside a wrapper: its calls give the keys
        key = re.sub(r"\$\{[^{}]*\}", "{…}", key) + (tail if tail is not None else "…" if m.group(4) else "")
        out.append(("storage", "%s %s" % (m.group(1), key), src, base + line_of(code, m.start()), "dynamic" if dyn else None))
    for m in STORAGE_ID.finditer(code):   # localStorage.getItem(KEY) with KEY = '…'
        if m.group(2) in consts:
            out.append(("storage", "%s %s" % (m.group(1), consts[m.group(2)]), src, base + line_of(code, m.start()), None))
    for m in PARAM.finditer(code):   # u.searchParams.get('q'), new URLSearchParams(location.search).get('ext')
        out.append(("param", m.group(1), src, base + line_of(code, m.start()), None))
    for m in ROUTE_RX.finditer(raw_code):
        out.append(("route", m.group(0), src, base + line_of(code, m.start()), None))


FUNC_HEAD = r"(?:\bfunction\s*\*?\s*{n}\s*\(|(?<![\w$.]){n}\s*[:=]\s*(?:async\s+)?(?:function\b[^(]*\(|\([^()]*\)\s*=>|[\w$]+\s*=>)|(?<![\w$.]){n}\s*\([^()]*\)\s*\{{)"


def only_functions(code, names):
    """code with everything outside the bodies of the named functions blanked (line numbers kept). [] of names = all."""
    keep = []
    for n in names:
        for m in re.finditer(FUNC_HEAD.format(n=re.escape(n)), code):
            i = code.find("{", m.end() - 1)
            arrow = code[m.start():m.end()].endswith("=>")
            if arrow and not code[m.end():].lstrip().startswith("{"):   # an arrow with an expression body: to the end of the line
                j = code.find("\n", m.end())
                keep.append((m.start(), len(code) if j < 0 else j))
            elif i >= 0:
                keep.append((m.start(), close_paren(code, i) + 1))
    return "".join(c if c == "\n" or any(a <= i < b for a, b in keep) else " " for i, c in enumerate(code))


def skip_regions(text, patterns):
    """text with the regions matched by the patterns blanked (line numbers kept)."""
    for rx in patterns:
        text = re.sub(rx, blank, text, flags=re.S)
    return text


def extract(path, rel, opts=None):
    text = path.read_text(encoding="utf-8", errors="replace")
    opts = opts or {}
    if opts.get("_skipShell"):
        text = skip_regions(text, opts.get("skipRegions") or SHELL_REGIONS)
    funcs = opts.get("_functions") or []
    out = []
    if path.suffix in (".html", ".htm", ".vue"):
        for m in re.finditer(r"<script\b[^>]*>(.*?)</script\s*>", text, re.S | re.I):
            if not re.search(r"\bsrc\s*=", text[m.start():m.start(1)]):
                code = only_functions(m.group(1), funcs) if funcs else m.group(1)
                from_script(code, line_of(text, m.start(1)) - 1, out, rel, opts)
        if not funcs:
            from_markup(text, 0, out, rel)
    else:
        from_script(only_functions(text, funcs) if funcs else text, 0, out, rel, opts)
    return out


def excluded(f, root, base, globs):
    """True when the file matches one of the --exclude globs, relative to the project root or to the folder given."""
    rels = []
    for b in (root, base):
        try:
            rels.append(f.resolve().relative_to(Path(b).resolve()).as_posix())
        except ValueError:
            pass
    rels.append(f.as_posix())
    return any(fnmatch.fnmatch(r, g) or fnmatch.fnmatch(r, g.replace("**/", "")) for r in rels for g in globs)


def collect(paths, root, opts=None, exclude=()):
    """Rows of the files: opts = kit.config.json > define (messageCalls, storageCalls, storagePrefix, skipRegions) plus
    _skipShell and _functions from the command line; exclude = globs of files to leave out."""
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files += [f for f in sorted(p.rglob("*")) if f.is_file() and f.suffix in EXT and not (SKIP & set(f.parts))
                      and not excluded(f, root, p, exclude)]
        elif p.is_file():
            files += [] if excluded(p, root, p.parent, exclude) else [p]
        else:
            sys.exit("ERROR: not found: %s" % p)
    rels = []
    for f in files:
        try:
            rels.append(f.resolve().relative_to(root).as_posix())
        except ValueError:
            rels.append(f.as_posix())
    opts = dict(opts or {}, _wraps={})   # storage wrappers of every file, so a call in another file gives its key (K1a-5)
    for f, rel in zip(files, rels):
        text = f.read_text(encoding="utf-8", errors="replace")
        if f.suffix in (".html", ".htm", ".vue"):   # only the inline scripts of a page
            text = "\n".join(m.group(1) for m in re.finditer(r"<script\b[^>]*>(.*?)</script\s*>", text, re.S | re.I))
        code = blank_regex(COMMENT.sub(blank, text))
        consts = {}
        for m in CONST.finditer(code):
            consts.setdefault(m.group(1), m.group(3))
        for k, (st, pre, span) in wrappers(code, consts).items():
            opts["_wraps"].setdefault(k, (st, pre, span, rel))
    rows, seen = [], {}
    for f, rel in zip(files, rels):
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
    # 0.12.2 (K1a-1): bare storage helpers, a key in a constant, a wrapper of the file, URL parameters
    (d / "k1.js").write_text(
        "function get(k,d){try{var v=localStorage.getItem('app2.'+k);return v==null?d:JSON.parse(v)}catch(e){return d}}\n"
        "var W = get('extW', 420); lsSet('theme', 'x'); var t = lsGet('theme');\n"
        "var KEY='app2.pinPos';\nvar pos = JSON.parse(localStorage.getItem(KEY) || 'null');\n"
        "u.searchParams.delete('ext'); var q = new URLSearchParams(location.search).get('tab');\n"
        "f.src = '../index.html' + '?' + 'ext=1'; go('a.html?mode=lite&x=2');\n", encoding="utf-8")
    k1 = {(r["kind"], r["text"]): r.get("note") for r in collect([d / "k1.js"], d)}
    for want in (("storage", "localStorage app2.extW (get)"), ("storage", "lsSet theme"), ("storage", "lsGet theme"),
                 ("storage", "localStorage app2.pinPos"), ("param", "ext"), ("param", "tab"), ("param", "ext=1"),
                 ("param", "mode=lite"), ("param", "x=2")):
        assert want in k1, (want, sorted(k1))
    assert k1[("storage", "lsSet theme")] == "wrapper" and k1[("storage", "localStorage app2.extW (get)")] is None, k1
    # K3-1: text in markup pieces of script strings and template literals; data-msg is a message
    (d / "k31.js").write_text(
        "var h = '<div class=\"x-e\" data-msg=\"Nothing saved yet\">Empty list</div>';\n"
        "b.innerHTML = '<button aria-label=\"Remove\">' + ico + 'Remove item</button>';\nvar s = '<div class=\"x\">Start here';\n"
        "el.innerHTML = `<p>Drop files ${n}</p>\n<input placeholder=\"Find by name\">`;\nvar p = '\" title=\"' + t + '\">';\n", encoding="utf-8")
    k31 = {(r["kind"], r["text"]) for r in collect([d / "k31.js"], d)}
    for want in (("message", "data-msg: Nothing saved yet"), ("text", "Empty list"), ("text", "Remove item"), ("text", "Start here"),
                 ("text", "aria-label: Remove"), ("text", "Drop files {…}"), ("text", "placeholder: Find by name")):
        assert want in k31, (want, sorted(k31))
    assert not any('="' in t or t in ("{…}", '">') for _k, t in k31), sorted(k31)
    # K3-2: shell regions, --exclude, --function
    (d / "shared").mkdir()
    (d / "shared" / "shell.js").write_text("toast('Shell message');\n", encoding="utf-8")
    (d / "k32.html").write_text("<!-- SHELL:top -->\n<nav><a>Shell menu</a></nav>\n<!-- /SHELL:top -->\n<main><h1>Own page</h1></main>\n"
                                "<script>/* SHELL:js */ toast('Shell toast'); /* /SHELL:js */\nfunction save(v){ if (v.length > 9) toast('Too long'); }\n"
                                "const other = () => { toast('Other'); };\nvar obj = { load(x) { toast('Loaded'); } };</script>\n", encoding="utf-8")
    sh = {r["text"]: r["source"] for r in collect([d / "k32.html", d / "shared"], d, {"_skipShell": True}, exclude=["shared/**"])}
    assert "Own page" in sh and "Too long" in sh and not {"Shell menu", "Shell toast", "Shell message"} & set(sh), sh
    assert sh["Own page"] == "k32.html:4" and sh["Too long"] == "k32.html:6", sh
    full = {r["text"] for r in collect([d / "k32.html"], d)}
    assert {"Shell menu", "Shell toast"} <= full, full
    fn = {r["text"] for r in collect([d / "k32.html"], d, {"_functions": ["save", "load"]})}
    assert fn == {"Too long", "v.length > 9", "Loaded"}, fn
    assert {r["text"] for r in collect([d / "k32.html"], d, {"_functions": ["other"]})} == {"Other"}
    # 0.12.3 (K5-1): <!-- SHELL:BEGIN (note) --> … <!-- SHELL:END --> and /* SHELL:BEGIN */ … /* SHELL:END */ too
    (d / "k51.html").write_text("<!-- SHELL:BEGIN (shared frame; synced by a script) -->\n<nav><a>Frame menu</a></nav>\n<!-- SHELL:END -->\n"
                                "<main><h1>Slide page</h1></main>\n<script>/* SHELL:BEGIN */ toast('Frame toast'); /* SHELL:END */ toast('Page toast');</script>\n",
                                encoding="utf-8")
    k51 = {r["text"] for r in collect([d / "k51.html"], d, {"_skipShell": True})}
    assert {"Slide page", "Page toast"} <= k51 and not {"Frame menu", "Frame toast"} & k51, k51
    custom = {r["text"] for r in collect([d / "k32.html"], d, {"_skipShell": True, "skipRegions": [r"<nav>.*?</nav>"]})}
    assert "Shell menu" not in custom and "Shell toast" in custom, custom
    # 0.12.3 (K1a-5): a wrapper whose key is 'prefix.' + k, `prefix.${k}` or PREFIX + k, called in the same file or in
    # another file of the run; the prefix inside the wrapper is no row of its own, a prefix outside one is a dynamic key
    (d / "k15").mkdir()
    (d / "k15" / "store.js").write_text(
        "function get(k){return localStorage.getItem('oneai2.'+k)}\nvar runs = get('amisChat');\n"
        "const load = k => JSON.parse(sessionStorage.getItem(`p3.${k}`));\nvar PFX = 'app3.';\n"
        "var store = { rd: function (key) { return localStorage.getItem(PFX + key); } };\n"
        "localStorage.setItem('conv.' + id, s);\n", encoding="utf-8")
    (d / "k15" / "page.html").write_text("<script>var a = get('ucStart'); var b = load('tab'); var c = rd('pin');</script>\n", encoding="utf-8")
    (d / "k15" / "other.js").write_text("function store(get, put){ return get('schedQueue', []); }\nvar K_CUS = 'homeBg';\n"
                                        "localStorage.removeItem('oneai2.' + K_CUS);\n", encoding="utf-8")
    k15 = {(r["kind"], r["text"]): (r.get("note"), r["source"]) for r in collect([d / "k15"], d)}
    for want in (("storage", "localStorage oneai2.amisChat (get)"), ("storage", "localStorage oneai2.ucStart (get, k15/store.js)"),
                 ("storage", "sessionStorage p3.tab (load, k15/store.js)"), ("storage", "localStorage app3.pin (rd, k15/store.js)")):
        assert want in k15 and k15[want][0] is None, (want, sorted(k15))
    assert ("storage", "localStorage oneai2.") not in k15 and not any(t.startswith("sessionStorage p3.{") for _k, t in k15), sorted(k15)
    assert k15[("storage", "localStorage conv.…")][0] == "dynamic" and ("storage", "localStorage oneai2.homeBg") in k15, sorted(k15)
    assert not any("schedQueue (get" in t for _k, t in k15), "a parameter named get is not the wrapper of another file"
    # K4-5: a regular expression literal is no string: esc() gives no text row, a route regex and real messages stay
    (d / "k45.js").write_text(
        "function esc(s){return String(s).replace(/[&<>\"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]})}\n"
        "var half = w / 2, q = h / 3; toast('Saved to the list');\nvar m = /^#\\/c\\/([\\w-]+)$/.exec(location.hash);\n"
        "var h = '<b>' + x + '</b>' + (ok ? function(){ return 1 } : 0) + 'Plain label</i>';\n"
        "var p = '<p>Sent by mail at 08:12 (mock); saved to the log.</p>';\n", encoding="utf-8")
    k45 = collect([d / "k45.js"], d)
    txt = {(r["kind"], r["text"]) for r in k45}
    assert ("text", "Sent by mail at 08:12 (mock); saved to the log.") in txt and ("message", "Saved to the list") in txt and ("route", "/^#\\/c\\/([\\w-]+)$/") in txt, sorted(txt)
    assert not any(re.search(r"function|]/g|=>|[{}]", t) and k in ("text", "string", "message") for k, t in txt), sorted(txt)
    assert blank_regex("a = b / c / d; r = /x'y/g;\n") == "a = b / c / d; r = " + " " * 6 + ";\n"
    # 0.12.4 (K7-1): pieces of a tag joined with + are no text; the attributes of the tag are read across the pieces
    (d / "k71.js").write_text(
        "function b(i){return '<button type=\"button\" data-id=\"'+i+'\" aria-label=\"Edit slide '+(i+1)+' with the assistant\">'+orb(0)+'Edit with the assistant</button>'}\n"
        "var t = '<a class=\"x\" title=\"Open '+n+' files\">'+'Open</a>'; var c = '\">Next step';\n", encoding="utf-8")
    k71 = {(r["kind"], r["text"]) for r in collect([d / "k71.js"], d)}
    for want in (("text", "aria-label: Edit slide {…} with the assistant"), ("text", "Edit with the assistant"), ("text", "Next step"),
                 ("text", "title: Open {…} files"), ("text", "Open")):
        assert want in k71, (want, sorted(k71))
    assert not any('">' in t or t.startswith('"') for _k, t in k71), sorted(k71)
    assert not any(t in ("with the assistant", "{…}Edit with the assistant") for _k, t in k71), sorted(k71)
    # K7-2: the text a .replace / .replaceAll puts in (second argument); a regex or string first argument gives nothing new
    (d / "k72.js").write_text(
        "function cm(h){return h.replace('Send','Comment').replace('placeholder=\"Ask anything\"','placeholder=\"Add a comment\"')"
        ".replace(/aria-label=\"Edit slide (\\d+)\"/,'aria-label=\"Comment on slide $1\"').replaceAll('title=\"Go\"', 'title=\"Post\"')}\n", encoding="utf-8")
    k72 = {(r["kind"], r["text"]) for r in collect([d / "k72.js"], d, {"_functions": ["cm"]})}
    for want in (("string", "Comment"), ("text", "placeholder: Add a comment"), ("text", "aria-label: Comment on slide {…}"), ("text", "title: Post")):
        assert want in k72, (want, sorted(k72))
    assert not any("Ask anything" in t or "Edit slide" in t or t == "title: Go" for _k, t in k72), sorted(k72)
    print("extract_rules.py selftest OK")


def main():
    argv = sys.argv[1:]
    if "--selftest" in argv:
        selftest()
        return
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    as_json, out_file, paths, exclude, funcs = "--json" in argv, None, [], [], []
    i = 0
    while i < len(argv):
        if argv[i] in ("--out", "--exclude", "--function"):
            if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
                sys.exit("ERROR: %s needs a value" % argv[i])
            v = argv[i + 1]
            if argv[i] == "--out":
                out_file = v
            elif argv[i] == "--exclude":
                exclude.append(v)
            else:
                funcs.append(v)
            i += 2
            continue
        if argv[i] not in ("--json", "--skip-shell"):
            paths.append(argv[i])
        i += 1
    if not paths:
        sys.exit("ERROR: give the page files or folders to read")
    cfg = load(require=False) or {"language": "en"}
    root = Path(cfg.get("_root") or Path.cwd()).resolve()
    opts = dict(cfg.get("define") or {})
    for k in ("messageCalls", "storageCalls", "skipRegions"):
        if not isinstance(opts.get(k) or [], list):
            sys.exit("ERROR: kit.config.json > define.%s must be a list" % k)
    for rx in opts.get("skipRegions") or []:
        try:
            re.compile(rx)
        except re.error as e:
            sys.exit("ERROR: kit.config.json > define.skipRegions: %r is no regular expression (%s)" % (rx, e))
    opts.update(_skipShell="--skip-shell" in argv, _functions=funcs)
    rows = collect(paths, root, opts, exclude)
    if funcs and not rows:
        print("NOTE: no row inside function(s) %s: check the name (function x(…), x = function, x(…) {…}, const x = (…) =>)" % ", ".join(funcs),
              file=sys.stderr)
    text = json.dumps(rows, ensure_ascii=False, indent=1) if as_json else markdown(cfg, rows, paths)
    if out_file:
        Path(out_file).write_text(text + "\n", encoding="utf-8")
        print("Wrote %s: %d rows" % (out_file, len(rows)))
    else:
        print(text)


if __name__ == "__main__":
    main()
