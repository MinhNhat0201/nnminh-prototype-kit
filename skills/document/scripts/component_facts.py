#!/usr/bin/env python3
"""Build the fact sheet of a DS component from its CSS, as input for writing docs.

Every size, token, variant and state in a doc must come from the real CSS, never from memory.
Read-only: changes no file.

The CSS defaults to the DS profile: the css.sources entries of ds.json whose name contains "component"
(for example components.css), or css.bundle when there is none. Pass --css to read another file.

Usage:
  python3 component_facts.py --list                 inventory of root classes and rule counts
  python3 component_facts.py btn                    facts of .btn
  python3 component_facts.py tabs tab --json        several classes, JSON output
  python3 component_facts.py chip --key-only        compact: size, colour and text declarations only
  python3 component_facts.py --css path.css btn     read another CSS file
"""
import argparse
import json
import re
import sys
from collections import OrderedDict, Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from kitconf import load, ds_path  # noqa: E402

STATE_PSEUDO = ("hover", "active", "focus-visible", "focus-within", "focus", "disabled",
                "checked", "indeterminate", "read-only", "placeholder", "has", "not", "first-child",
                "last-child", "before", "after")
KEY_PROPS = ("height", "min-height", "max-height", "width", "min-width", "max-width", "padding",
             "padding-left", "padding-right", "padding-top", "padding-bottom", "gap", "margin",
             "border-radius", "border", "border-color", "font-size", "font-weight", "line-height",
             "background", "background-color", "background-image", "color", "outline",
             "outline-offset", "box-shadow", "opacity", "cursor", "display", "flex", "transition")


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def split_top(text, sep):
    """Split on sep outside brackets and strings."""
    out, depth, quote, cur = [], 0, None, []
    for ch in text:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            cur.append(ch)
        elif ch in "([":
            depth += 1
            cur.append(ch)
        elif ch in ")]":
            depth -= 1
            cur.append(ch)
        elif ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return [s.strip() for s in out if s.strip()]


def parse_blocks(css, ctx=""):
    """Return [(ctx, selector, body)]; ctx is the enclosing @media / @supports condition."""
    rules, i, n = [], 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j == -1:
            break
        head = css[i:j].strip()
        depth, k, quote = 1, j + 1, None
        while k < n and depth:
            ch = css[k]
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            k += 1
        body = css[j + 1:k - 1]
        if head.startswith("@media") or head.startswith("@supports"):
            rules += parse_blocks(body, (ctx + " " + head).strip())
        elif head.startswith("@"):
            pass  # keyframes, property, font-face: skipped
        elif head:
            rules.append((ctx, head, body))
        i = k
    return rules


def parse_decls(body):
    out = OrderedDict()
    for d in split_top(body, ";"):
        if ":" in d:
            p, v = d.split(":", 1)
            out[p.strip()] = v.strip()
    return out


def class_re(cls):
    return re.compile(r"(?<![\w-])\." + re.escape(cls) + r"(?![\w-])")


def compounds(sel):
    """Split a selector into compounds on combinators (space, >, +, ~)."""
    parts, depth, cur = [], 0, []
    for ch in sel:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if depth == 0 and ch in " >+~":
            if cur:
                parts.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts


def describe(sel, cls, ctx):
    """Classify one selector that contains .cls."""
    comps = compounds(sel)
    rx = class_re(cls)
    idx = [i for i, c in enumerate(comps) if rx.search(c)]
    ti = idx[-1]
    comp = comps[ti]
    mods = [m for m in re.findall(r"\.([\w-]+)", comp) if m != cls and not m.startswith("is-")]
    states = []
    for m in re.findall(r":([a-z-]+)", comp):
        if m in STATE_PSEUDO and m not in ("before", "after", "not", "has"):
            states.append(m)
    states += re.findall(r"\.(is-[\w-]+)", comp)
    states += re.findall(r"\[(aria-[\w-]+|disabled|readonly|hidden|open)[^\]]*\]", comp)
    pseudo_el = re.findall(r"::?(before|after|placeholder)", comp)
    dark = bool(re.search(r"data-mode=.?dark|data-theme=.?dark|\.dark\b|prefers-color-scheme:\s*dark", sel + " " + ctx))
    responsive = re.findall(r"\((?:max|min)-width:\s*[\w.]+\)", ctx)
    outer = [c for i, c in enumerate(comps) if i != ti and not re.search(r"data-mode|data-theme|:root|^\.(dark|light)$", c)]
    kinds = []
    if dark:
        kinds.append("dark")
    if responsive:
        kinds.append("responsive " + ",".join(responsive))
    if ti != len(comps) - 1:
        kinds.append("child of ." + cls)
    elif outer:
        kinds.append("inside " + " ".join(outer))
    if mods:
        kinds.append("variant " + "+".join(mods))
    if states:
        kinds.append("state " + ",".join(dict.fromkeys(states)))
    if pseudo_el:
        kinds.append("pseudo " + ",".join(dict.fromkeys(pseudo_el)))
    if not kinds:
        kinds.append("base")
    return {"kinds": kinds, "mods": mods, "states": list(dict.fromkeys(states)), "dark": dark}


def hardcoded(decls):
    found = []
    for p, v in decls.items():
        v2 = re.sub(r"url\([^)]*\)", "url()", v)
        for m in re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)", v2):
            found.append(f"{p}: {m}")
    return found


def facts(rules, cls, key_only=False):
    rx = class_re(cls)
    rows, tokens, hard, mods, states = [], Counter(), [], Counter(), Counter()
    for ctx, head, body in rules:
        sels = [s for s in split_top(head, ",") if rx.search(s)]
        if not sels:
            continue
        decls = parse_decls(body)
        toks = sorted(set(re.findall(r"var\((--[\w-]+)", body)))
        for t in toks:
            tokens[t] += 1
        for h in hardcoded(decls):
            hard.append((head if len(sels) > 1 else sels[0], h))
        for s in sels:
            d = describe(s, cls, ctx)
            for m in d["mods"]:
                mods[m] += 1
            for st in d["states"]:
                states[st] += 1
            key = [(p, v) for p, v in decls.items() if not key_only or p in KEY_PROPS or p.startswith("--")]
            rows.append({"selector": s, "kinds": d["kinds"], "decls": dict(key), "tokens": toks})
    return {"class": cls, "rows": rows, "modifiers": dict(mods), "states": dict(states),
            "tokens": dict(tokens), "hardcoded": hard}


def trunc(s, n=110):
    return s if len(s) <= n else s[:n - 1] + "…"


def to_md(f, src):
    out = [f"# Fact sheet: `.{f['class']}`  (source: {src})", ""]
    if not f["rows"]:
        return "\n".join(out + ["No rule contains this class."])
    out.append(f"**Variants (combined classes):** {', '.join(sorted(f['modifiers'])) or '(none)'}")
    out.append(f"**States in the CSS:** {', '.join(sorted(f['states'])) or '(none)'}")
    out.append("")
    out.append("## Rules")
    out.append("| Selector | Kind | Main declarations |")
    out.append("|---|---|---|")
    for r in f["rows"]:
        ds = "; ".join(f"{p}: {trunc(v)}" for p, v in r["decls"].items()) or "—"
        ds = ds.replace("|", "\\|")
        kinds = " · ".join(r["kinds"])
        out.append(f"| `{trunc(r['selector'], 90)}` | {kinds} | {ds} |")
    out.append("")
    out.append(f"## Tokens used ({len(f['tokens'])})")
    for t, c in sorted(f["tokens"].items()):
        out.append(f"- `{t}` ×{c}")
    out.append("")
    out.append("## Hard-coded values to review")
    if f["hardcoded"]:
        for s, h in f["hardcoded"]:
            out.append(f"- `{trunc(s, 80)}` → {h}")
        out.append("")
        out.append("Put these under \"Known issues\" in the Dev section of the doc or report them to the user; never invent a new token.")
    else:
        out.append("- (none)")
    return "\n".join(out)


def list_classes(rules):
    c = Counter()
    for _, head, _ in rules:
        for s in split_top(head, ","):
            m = re.search(r"(?<![\w-])\.([a-zA-Z][\w-]*)", s)
            if m:
                c[m.group(1)] += 1
    return c


def default_css():
    cfg = load(require=False)
    if not cfg or not cfg.get("_ds"):
        return None
    ds = cfg["_ds"]
    srcs = [ds_path(cfg, x) for x in ds["css"]["sources"] if "component" in x.lower()]
    srcs = [x for x in srcs if "://" not in x and Path(x).is_file()]
    if srcs:
        return srcs
    b = ds_path(cfg, ds["css"]["bundle"])
    return [b] if b and "://" not in b and Path(b).is_file() else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("classes", nargs="*", help="class names, without the dot")
    ap.add_argument("--css", action="append", help="CSS file to read (repeatable); default: the DS profile components CSS")
    ap.add_argument("--list", action="store_true", help="list root classes and their rule counts")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--key-only", action="store_true", help="only size, colour and text declarations (shorter)")
    a = ap.parse_args()
    files = a.css or default_css()
    if not files:
        print("ERROR: no CSS to read: pass --css, or run inside a project whose ds.json has css.sources or css.bundle.")
        sys.exit(1)
    for f in files:
        if not Path(f).is_file():
            print("ERROR: CSS file not found: %s" % f)
            sys.exit(1)
    rules = parse_blocks(strip_comments("\n".join(open(f, encoding="utf-8").read() for f in files)))
    src = ", ".join(files)
    if a.list:
        for k, v in sorted(list_classes(rules).items(), key=lambda x: (-x[1], x[0])):
            print(f"{k}\t{v}")
        return
    if not a.classes:
        print("ERROR: give at least one class, or use --list")
        sys.exit(1)
    res = [facts(rules, c, a.key_only) for c in a.classes]
    if a.json:
        json.dump(res, sys.stdout, ensure_ascii=False, indent=2)
    else:
        print("\n\n".join(to_md(f, src) for f in res))


if __name__ == "__main__":
    main()
