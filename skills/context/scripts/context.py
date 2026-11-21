#!/usr/bin/env python3
"""Product context: the files every skill reads before it plans, explores or builds.

Commands:
  context.py init       Create <paths.context>/ with product-overview.md, personas.md, ux-principles.md,
                        business-rules.md, constraints.md and decisions/index.md, in the project language.
                        Never overwrites: existing files are kept and listed.
  context.py check      Report which files are missing or still unfilled (template prompts left), and run the
                        decision log check. Exit 1 when a file is missing or a decision is invalid.
  context.py summary    Print a short digest for agents: filled files, open template prompts, decisions by status,
                        approved decisions that are not yet implemented.

Never commits, pushes or sends anything.
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[2]
sys.path.insert(0, str(KIT / "scripts"))
sys.path.insert(0, str(HERE))
from kitconf import load, t  # noqa: E402
import decisions as dec  # noqa: E402

FILES = ("product-overview", "personas", "ux-principles", "business-rules", "constraints")
PROMPT = "<!-- fill:"


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def cdir(cfg):
    return Path(cfg["_root"]) / cfg["paths"]["context"]


def cmd_init(cfg, a):
    d = cdir(cfg)
    (d / "decisions").mkdir(parents=True, exist_ok=True)
    made, kept = [], []
    for name in FILES:
        f = d / (name + ".md")
        if f.exists():
            kept.append(f.name)
            continue
        f.write_text(t(cfg, "context.file." + name), encoding="utf-8")
        made.append(f.name)
    if not (d / "decisions" / "index.md").exists():
        dec.write_index(cfg)
        made.append("decisions/index.md")
    rel = d.relative_to(cfg["_root"])
    print("Context folder: %s" % rel)
    if made:
        print("Created: " + ", ".join(made))
    if kept:
        print("Kept (already there): " + ", ".join(kept))
    print("Next: fill each file from the user's answers and existing material; mark anything inferred as observed, with its source.")


def file_state(f):
    if not f.is_file():
        return "missing", 0
    text = f.read_text(encoding="utf-8")
    return ("unfilled" if PROMPT in text else "filled"), text.count(PROMPT)


def cmd_check(cfg, a):
    d = cdir(cfg)
    if not d.is_dir():
        die("no product context in %s (run init)" % d.relative_to(cfg["_root"]))
    errs = 0
    for name in FILES:
        state, n = file_state(d / (name + ".md"))
        if state == "missing":
            print("ERROR: %s.md missing" % name)
            errs += 1
        elif state == "unfilled":
            print("WARN: %s.md has %d prompt(s) left to fill" % (name, n))
    recs, derrs = dec.check_all(cfg)
    for e in derrs:
        print("ERROR: decision " + e)
    errs += len(derrs)
    print("Context OK (%d decisions)" % len(recs) if not errs else "%d error(s)" % errs)
    sys.exit(1 if errs else 0)


def cmd_summary(cfg, a):
    d = cdir(cfg)
    if not d.is_dir():
        print("No product context (%s). Skills work without it; suggest the context skill." % cfg["paths"]["context"])
        return
    print("Product context: %s" % d.relative_to(cfg["_root"]))
    for name in FILES:
        state, n = file_state(d / (name + ".md"))
        print("  %-22s %s%s" % (name + ".md", state, (" (%d prompts left)" % n) if n else ""))
    recs, derrs = dec.load_all(cfg)
    by = {}
    for r in recs:
        by.setdefault(r["status"], []).append(r)
    print("Decisions: %d%s" % (len(recs), ("  " + ", ".join("%s %d" % (s, len(by[s])) for s in dec.STATUSES if s in by)) if recs else ""))
    for r in by.get("approved", []):
        print("  approved, not built yet: %s %s [%s]" % (r["id"], r["title"], r["scope"] or "-"))
    for r in by.get("proposed", []):
        print("  waiting for a human: %s %s" % (r["id"], r["title"]))
    if derrs:
        print("  %d unreadable decision file(s); run check" % len(derrs))


def main():
    ap = argparse.ArgumentParser(description="Product context files and decision log.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create the context folder")
    sub.add_parser("check", help="validate the context and the decision log")
    sub.add_parser("summary", help="short digest for agents")
    a = ap.parse_args()
    cfg = load()
    {"init": cmd_init, "check": cmd_check, "summary": cmd_summary}[a.cmd](cfg, a)


if __name__ == "__main__":
    main()
