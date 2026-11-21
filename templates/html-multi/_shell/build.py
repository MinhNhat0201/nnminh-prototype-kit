#!/usr/bin/env python3
"""Build the shared shell into every page of this multi-page app.

Each page file listed in _shell/shell.json holds four regions, each between two comments:
  <!-- SHELL:css --> ... <!-- /SHELL:css -->    _shell/shell.css inside <style>
  <!-- SHELL:top --> ... <!-- /SHELL:top -->    _shell/top.html with the navigation (relative links)
  <!-- SHELL:foot --> ... <!-- /SHELL:foot -->  _shell/foot.html (version label)
  <!-- SHELL:js --> ... <!-- /SHELL:js -->      _shell/shell.js inside <script>
Never edit inside a region: edit the file in _shell/ and build again. The DS CSS
(between the ds.json > css.marker comments) and the <meta> version tag stay in each page.

Commands:
  build   write the regions into every page
  check   exit 1 when a page differs from what build would write
"""
import json
import posixpath
import re
import sys
from pathlib import Path

SHELL = Path(__file__).resolve().parent
APP = SHELL.parent
REGIONS = ("css", "top", "foot", "js")


def read(name):
    return (SHELL / name).read_text(encoding="utf-8")


def nav(pages, current):
    here = posixpath.dirname(current)
    out = []
    for p in pages:
        if p.get("nav", True) is False:
            continue
        href = posixpath.relpath(p["file"], here or ".")
        cur = ' aria-current="page"' if p["file"] == current else ""
        out.append('    <a href="%s"%s>\n      %s\n      <span>%s</span>\n    </a>' % (href, cur, p.get("icon", ""), p["title"]))
    return "\n".join(out)


def regions(cfg, file):
    return {
        "css": "<style>\n" + read("shell.css") + "</style>",
        "top": read("top.html").rstrip("\n").replace("<!-- @nav -->", nav(cfg["pages"], file)),
        "foot": read("foot.html").rstrip("\n"),
        "js": "<script>\n" + read("shell.js") + "</script>",
    }


def fill(text, parts, file):
    for name in REGIONS:
        rx = re.compile(r"(<!-- SHELL:%s -->)(.*?)(<!-- /SHELL:%s -->)" % (name, name), re.S)
        if not rx.search(text):
            sys.exit("ERROR: %s has no <!-- SHELL:%s --> region." % (file, name))
        text = rx.sub(lambda m: m.group(1) + "\n" + parts[name] + "\n" + m.group(3), text, count=1)
    return text


def main(argv):
    if len(argv) != 2 or argv[1] not in ("build", "check"):
        print(__doc__)
        return 0 if len(argv) == 2 and argv[1] in ("-h", "--help") else 1
    cfg = json.loads(read("shell.json"))
    stale = []
    for p in cfg["pages"]:
        f = APP / p["file"]
        if not f.is_file():
            sys.exit("ERROR: page %s listed in _shell/shell.json does not exist." % p["file"])
        old = f.read_text(encoding="utf-8")
        new = fill(old, regions(cfg, p["file"]), p["file"])
        if new != old:
            stale.append(p["file"])
            if argv[1] == "build":
                f.write_text(new, encoding="utf-8")
    if argv[1] == "check":
        for s in stale:
            print("ERROR: %s is out of date with _shell/. Run: python3 _shell/build.py build" % s)
        print("Shell OK: %d page(s)" % len(cfg["pages"]) if not stale else "%d page(s) out of date" % len(stale))
        return 1 if stale else 0
    print("Built %d page(s), %d changed" % (len(cfg["pages"]), len(stale)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
