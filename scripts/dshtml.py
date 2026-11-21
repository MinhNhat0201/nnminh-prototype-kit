"""Small helpers to put the DS into a standalone HTML page (explorations, reports).

    from kitconf import load
    from dshtml import ds_css, html_attrs, version_meta
    cfg = load()
    css = ds_css(cfg)            # bundle text between the DS markers, ready to wrap again
    attrs = html_attrs(cfg)      # ' data-brand="default" data-mode="light"' from ds.json > theming defaults

The app templates are filled by skills/kickoff/scripts/scaffold.py; this module is for pages the kit
writes outside an app. Standard library only.
"""
import html
import re
from pathlib import Path

from kitconf import ds_path, version_label

THEMING_ORDER = ("brand", "mode", "density")


def bundle_inside(text, marker):
    """The bundle may carry its own DS markers: keep only what is between them."""
    rx = re.compile(r"/\*\s*%s[^*]*\*/(.*?)/\*\s*%s[^*]*\*/" % (re.escape(marker["begin"]), re.escape(marker["end"])), re.S)
    m = rx.search(text)
    return (m.group(1) if m else text).strip("\n")


def ds_css(cfg):
    """DS CSS for embedding, or "" when the profile has no local bundle."""
    ds = cfg.get("_ds")
    if not ds or not ds["css"]["bundle"] or "://" in ds["css"]["bundle"]:
        return ""
    p = Path(ds_path(cfg, ds["css"]["bundle"]))
    if not p.is_file():
        return ""
    return bundle_inside(p.read_text(encoding="utf-8"), ds["css"]["marker"])


def wrap_css(cfg, css):
    m = cfg["_ds"]["css"]["marker"] if cfg.get("_ds") else {"begin": "@ds:begin", "end": "@ds:end"}
    return "/* %s */\n%s\n/* %s */" % (m["begin"], css, m["end"])


def theming_defaults(cfg):
    theming = (cfg.get("_ds") or {}).get("theming") or {}
    keys = [k for k in THEMING_ORDER if k in theming] + [k for k in theming if k not in THEMING_ORDER]
    out = []
    for k in keys:
        t = theming.get(k) or {}
        if not isinstance(t, dict):
            continue
        value = t.get("default") or (t.get("values") or [None])[0]
        if t.get("attr") and value:
            out.append((t["attr"], value))
    return out


def html_attrs(cfg):
    return "".join(' %s="%s"' % (k, html.escape(str(v), quote=True)) for k, v in theming_defaults(cfg))


def version_meta(cfg):
    """(meta name, version, footer label) or None without a DS."""
    ds = cfg.get("_ds")
    if not ds:
        return None
    return ds["version_label"]["meta"], ds["version"], version_label(cfg)
