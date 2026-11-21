#!/usr/bin/env python3
"""Build a base DS profile from a public preset (default: shadcn).

Two layers: the AESTHETIC layer (tokens and component recipes) comes from the
preset; the STRUCTURE layer (window size classes, 48 px touch targets, bottom
sheet, tab bar, navigation rail, FAB, density) follows Material Design 3.

Commands:
  adopt.py [generate] --name acme --label "Acme DS" --prefix --acme- --seed "#2563eb"
           --radius 8 --font Inter --out ds/acme [--no-dark] [--preset shadcn]
           [--platforms web,mobile,tablet] [--lang en] [--force]
      Generate the profile folder. Stops with ERROR if a contrast pair still
      fails after automatic tone adjustment, or if --out is not empty (use --force).
  adopt.py check --out ds/acme
      Validate a generated profile: files, bundle markers, semantic-only
      component CSS, defined tokens, alias layer, contrast pairs.
  adopt.py figma-script --out ds/acme [--js FILE]
      Print (or write) the use_figma code that pushes variables and text styles
      (assets/figma-push.js filled with the profile's figma-variables.json).

Python 3.9+, standard library only. Never commits, publishes or sends anything.
"""
import argparse
import datetime
import json
import math
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
KIT = HERE.parents[3]
ASSETS = HERE.parents[1] / "assets"
sys.path.insert(0, str(KIT / "scripts"))
from kitconf import load as kit_load, t as kit_t  # noqa: E402

PROFILE_VERSION = "0.1.0"
TEXT, NONTEXT = 4.5, 3.0
DENSITIES = ["comfortable", "standard", "compact"]
ALIASES_EXTRA = {"--destructive-foreground": "text-on-danger"}


def die(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


# ---------------------------------------------------------------- colour math
def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def _cbrt(x):
    return math.copysign(abs(x) ** (1 / 3), x)


def rgb_to_oklch(r, g, b):
    r, g, b = _lin(r), _lin(g), _lin(b)
    l = _cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = _cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = _cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(A, B), math.degrees(math.atan2(B, A)) % 360


def oklch_to_rgb_linear(L, C, H):
    A, B = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
    m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
    s = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def in_gamut(L, C, H):
    return all(-1e-4 <= x <= 1 + 1e-4 for x in oklch_to_rgb_linear(L, C, H))


def clamp_chroma(L, C, H):
    if in_gamut(L, C, H):
        return C
    lo, hi = 0.0, C
    for _ in range(30):
        mid = (lo + hi) / 2
        if in_gamut(L, mid, H):
            lo = mid
        else:
            hi = mid
    return lo


def oklch_to_hex(L, C, H):
    C = clamp_chroma(L, C, H)
    rgb = [min(1.0, max(0.0, _gam(min(1.0, max(0.0, x))))) for x in oklch_to_rgb_linear(L, C, H)]
    return "#" + "".join(f"{round(x * 255):02x}" for x in rgb)


def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def hex_oklch(h):
    return rgb_to_oklch(*hex_rgb(h))


def parse_colour(s):
    """'#rrggbb' or 'oklch(L C H)' -> '#rrggbb'."""
    s = s.strip()
    if s.startswith("#"):
        return s.lower()
    m = re.match(r"oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)", s)
    if not m:
        die(f"cannot read colour '{s}'")
    return oklch_to_hex(float(m.group(1)), float(m.group(2)), float(m.group(3)))


def luminance(h):
    r, g, b = (_lin(x) for x in hex_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ------------------------------------------------------------- tonal palettes
STEPS = ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950"]
L_TARGET = {"50": 0.97, "100": 0.932, "200": 0.882, "300": 0.809, "400": 0.707, "500": 0.623,
            "600": 0.546, "700": 0.488, "800": 0.424, "900": 0.379, "950": 0.282}
C_FACTOR = {"50": 0.06, "100": 0.13, "200": 0.24, "300": 0.41, "400": 0.67, "500": 0.87,
            "600": 1.0, "700": 0.99, "800": 0.81, "900": 0.6, "950": 0.37}


def tonal(seed_hex):
    """Tonal scale 50-950 in OKLCH around the seed; the seed keeps its exact value at its nearest step."""
    L, C, H = hex_oklch(seed_hex)
    seed_step = min(STEPS, key=lambda s: abs(L_TARGET[s] - L))
    peak = C / max(C_FACTOR[seed_step], 0.3)
    out = {}
    for s in STEPS:
        out[s] = seed_hex.lower() if s == seed_step else oklch_to_hex(L_TARGET[s], peak * C_FACTOR[s], H)
    return out, seed_step


class Palettes:
    def __init__(self):
        self.p = {}      # name -> {step: hex}
        self.seed = {}   # name -> seed step
        self.orig = {}   # name -> steps before tone adjustment

    def add(self, name, steps, seed=None):
        self.p[name] = dict(steps)
        self.orig[name] = list(steps)
        if seed:
            self.seed[name] = seed

    def order(self, name):
        return sorted(self.p[name], key=lambda s: float(s))

    def walk_seq(self, name, start, direction):
        """Steps from start in direction (+1 darker, -1 lighter), with half steps between neighbours."""
        base = [s for s in self.order(name) if s in self.orig[name]]
        if start not in base:
            return [start]
        i = base.index(start)
        seq = [start]
        while 0 <= i + direction < len(base):
            a, b = base[i], base[i + direction]
            seq += [self.mid_name(a, b), b]
            i += direction
        return seq

    @staticmethod
    def mid_name(a, b):
        v = (float(a) + float(b)) / 2
        return str(int(v)) if v == int(v) else str(v).replace(".", "-")

    def hex(self, name, step):
        if step in self.p[name]:
            return self.p[name][step]
        # half step: average L and C of the neighbours in OKLCH, keep hue of the darker one
        base = [s for s in self.order(name) if s in self.orig[name]]
        v = float(step.replace("-", "."))
        lo = max((s for s in base if float(s) < v), key=float)
        hi = min((s for s in base if float(s) > v), key=float)
        l1, c1, h1 = hex_oklch(self.p[name][lo])
        l2, c2, h2 = hex_oklch(self.p[name][hi])
        h = h2 if c2 > 0.02 else h1
        return oklch_to_hex((l1 + l2) / 2, (c1 + c2) / 2, h)

    def materialise(self, name, step):
        if step not in self.p[name]:
            self.p[name][step] = self.hex(name, step)


def parse_ref(ref, pals):
    """'neutral.950' / 'brand.seed' / 'neutral.0/10' -> (palette, step, alpha or None)."""
    alpha = None
    if "/" in ref:
        ref, a = ref.split("/")
        alpha = int(a)
    pal, step = ref.split(".", 1)
    if pal not in pals.p:
        die(f"unknown palette '{pal}' in ref '{ref}'")
    if step == "seed":
        step = pals.seed[pal]
    return pal, step, alpha


def hex_alpha(h, alpha):
    return h + f"{round(alpha / 100 * 255):02x}"


# ---------------------------------------------------------- contrast pairs
def contrast_pairs():
    P = []

    def add(fg, bgs, m):
        P.extend((fg, b, m) for b in bgs)
    add("bg-brand", ["bg-canvas", "bg-brand-subtle"], NONTEXT)
    add("bg-danger", ["bg-canvas"], NONTEXT)
    add("stroke-strong", ["bg-canvas", "bg-surface"], NONTEXT)
    add("stroke-focus", ["bg-canvas", "bg-surface"], NONTEXT)
    add("stroke-brand", ["bg-canvas"], NONTEXT)
    add("stroke-danger", ["bg-canvas", "bg-surface"], NONTEXT)
    add("text-primary", ["bg-canvas", "bg-surface", "bg-raised", "bg-sidebar", "bg-subtle", "bg-hover", "bg-pressed", "bg-selected"], TEXT)
    add("text-secondary", ["bg-canvas", "bg-surface", "bg-raised", "bg-sidebar", "bg-subtle"], TEXT)
    add("text-on-brand", ["bg-brand", "bg-brand-hover"], TEXT)
    add("text-brand", ["bg-canvas", "bg-surface", "bg-brand-subtle", "bg-selected"], TEXT)
    add("text-link", ["bg-canvas", "bg-surface", "bg-sidebar"], TEXT)
    add("text-on-danger", ["bg-danger", "bg-danger-hover"], TEXT)
    add("text-danger", ["bg-canvas", "bg-surface", "bg-raised", "bg-danger-subtle"], TEXT)
    for s in ("success", "warning", "info"):
        add(f"text-{s}", ["bg-canvas", "bg-surface", f"bg-{s}-subtle"], TEXT)
    add("text-inverse", ["bg-inverse"], TEXT)
    add("icon-primary", ["bg-canvas", "bg-surface", "bg-subtle", "bg-hover"], NONTEXT)
    add("icon-secondary", ["bg-canvas", "bg-surface", "bg-sidebar", "bg-subtle"], NONTEXT)
    add("icon-brand", ["bg-canvas", "bg-sidebar", "bg-brand-subtle"], NONTEXT)
    add("icon-on-brand", ["bg-brand", "bg-brand-hover"], NONTEXT)
    for s in ("danger", "success", "warning", "info"):
        add(f"icon-{s}", ["bg-canvas", "bg-raised", f"bg-{s}-subtle"], NONTEXT)
    add("icon-inverse", ["bg-inverse"], NONTEXT)
    return P


EXEMPT = ["text-disabled", "icon-disabled", "stroke-default (decorative)", "bg-scrim", "chart-1..5 (data colours)"]
CATEGORY_ORDER = ["bg-", "stroke-", "icon-", "text-", "chart-"]


def resolve_mode(mode, semantic, pals, pairs):
    """Resolve every semantic token for one mode; walk tones until its contrast pairs pass."""
    direction = 1 if mode == "light" else -1
    res = {}  # token -> dict(ref, hex, start, adjusted)
    tokens = sorted(semantic, key=lambda t: (next(i for i, c in enumerate(CATEGORY_ORDER) if t.startswith(c)),
                                             1 if semantic[t][mode].startswith("hover:") else 0,
                                             1 if any(f == t for f, _, _ in pairs) else 0))
    white, black = pals.p["neutral"]["0"], pals.p["neutral"]["950"]

    def checks_for(tok):
        return [(b, m) for f, b, m in pairs if f == tok and b in res]

    def passes(tok, hx):
        if not all(contrast(hx, res[b]["hex"]) >= m for b, m in checks_for(tok)):
            return False
        if tok in ("bg-brand", "bg-danger"):  # some on-colour must reach 4.5:1
            return max(contrast(white, hx), contrast(black, hx)) >= TEXT
        return True

    for tok in tokens:
        spec = semantic[tok][mode]
        if spec.startswith("on:"):
            bg = res[spec[3:]]["hex"]
            cands = ["neutral.0", "neutral.950"]
            if contrast(white, bg) < TEXT and contrast(black, bg) > contrast(white, bg):
                cands.reverse()
            pick = next((c for c in cands if passes(tok, pals.p["neutral"][c.split(".")[1]])), cands[0])
            res[tok] = {"ref": pick, "hex": pals.p["neutral"][pick.split(".")[1]], "start": pick, "adjusted": False}
            continue
        if spec.startswith("hover:"):
            base = spec[6:]
            pal, step, _ = parse_ref(res[base]["ref"], pals)
            on_white = contrast(white, res[base]["hex"]) >= contrast(black, res[base]["hex"])
            seq = pals.walk_seq(pal, step, 1 if on_white else -1)
            nxt = seq[2] if len(seq) > 2 else seq[-1]
            pals.materialise(pal, nxt)
            res[tok] = {"ref": f"{pal}.{nxt}", "hex": pals.p[pal][nxt], "start": f"{pal}.{nxt}", "adjusted": False}
            continue
        pal, step, alpha = parse_ref(spec, pals)
        start = f"{pal}.{step}"
        if alpha is not None:
            res[tok] = {"ref": f"{pal}.{step}/{alpha}", "hex": hex_alpha(pals.p[pal][step], alpha), "start": start, "adjusted": False, "alpha": alpha}
            continue
        walk = any(f == tok for f, _, _ in pairs)
        chosen = step
        if walk and not passes(tok, pals.hex(pal, step)):
            for s in pals.walk_seq(pal, step, direction)[1:]:
                if passes(tok, pals.hex(pal, s)):
                    chosen = s
                    break
        pals.materialise(pal, chosen)
        res[tok] = {"ref": f"{pal}.{chosen}", "hex": pals.p[pal][chosen], "start": start, "adjusted": chosen != step}
    return res


def verify(mode, res, pairs):
    rows = []
    for f, b, m in pairs:
        if f not in res or b not in res:
            continue
        r = contrast(res[f]["hex"], res[b]["hex"])
        status = "FAIL" if r < m else ("ADJUSTED" if res[f]["adjusted"] else "PASS")
        rows.append({"mode": mode, "fg": f, "bg": b, "fgHex": res[f]["hex"], "bgHex": res[b]["hex"],
                     "ratio": round(r, 2), "min": m, "status": status})
    return rows


# ---------------------------------------------------------------- helpers
def px(v):
    return "0" if v == 0 else f"{v}px"


def var(prefix, name):
    return f"var({prefix}{name})"


def ref_var(prefix, ref):
    pal, step = ref.split("/")[0].split(".")
    return var(prefix, f"color-{pal}-{step}")


def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write(p, text):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


WEIGHT_STYLE = {400: "Regular", 500: "Medium", 600: "Semi Bold", 700: "Bold"}
LETTER = {"display": -2, "headline": -1}


# ---------------------------------------------------------------- generate
def generate(a):
    preset_dir = KIT / "presets" / a.preset
    if not (preset_dir / "preset.json").is_file():
        die(f"preset '{a.preset}' not found in {KIT / 'presets'}")
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,30}", a.name):
        die("--name must be lowercase letters, digits and hyphens, e.g. acme")
    prefix = a.prefix or f"--{a.name}-"
    if not re.fullmatch(r"--[a-z][a-z0-9-]*-", prefix):
        die("--prefix must look like --acme- (two leading hyphens, one trailing hyphen)")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", a.seed or ""):
        die("--seed must be a hex colour like #2563eb")
    if not 0 <= a.radius <= 32:
        die("--radius must be between 0 and 32 (px)")
    if not re.fullmatch(r"[A-Za-z0-9 ]{2,40}", a.font):
        die("--font must be a plain family name, e.g. Inter")
    out = Path(a.out).resolve()
    if out.exists() and any(out.iterdir()) and not a.force:
        die(f"{a.out} is not empty. Choose another --out or pass --force to overwrite the generated files.")

    preset = read_json(preset_dir / "preset.json")
    base = read_json(preset_dir / "tokens.base.json")
    comps = read_json(preset_dir / "components.json")["components"]
    cfg = kit_load(require=False)
    lang = a.lang or (cfg or {}).get("language", "en")
    T = lambda key, **kw: kit_t(lang, key, **kw)  # noqa: E731
    dark = not a.no_dark
    modes = ["light", "dark"] if dark else ["light"]
    cls = prefix[2:]          # class prefix, e.g. "acme-"
    label = a.label or a.name.capitalize() + " DS"
    platforms = [p.strip() for p in a.platforms.split(",") if p.strip()]
    today = datetime.date.today().isoformat()
    seed = a.seed.lower()

    # palettes
    pals = Palettes()
    pals.add("neutral", {k: parse_colour(v) for k, v in base["palettes"]["neutral"].items()})
    steps, seed_step = tonal(seed)
    pals.add("brand", steps, seed_step)
    for name, spec in base["generated_palettes"].items():
        if name.startswith("$"):
            continue
        st, ss = tonal(parse_colour(spec["seed"]))
        pals.add(name, st, ss)
    for name in ("chart", "chart-dark"):
        pals.add(name, {k: parse_colour(v) for k, v in base["palettes"][name].items()})

    semantic = base["semantic"]
    pairs = contrast_pairs()
    res, rows = {}, []
    for m in modes:
        res[m] = resolve_mode(m, semantic, pals, pairs)
        rows += verify(m, res[m], pairs)
    fails = [r for r in rows if r["status"] == "FAIL"]
    print_contrast(rows)
    if fails:
        for r in fails:
            print(f"ERROR: contrast {r['mode']} {r['fg']} on {r['bg']}: {r['ratio']}:1 < {r['min']}:1 after adjustment")
        die(f"{len(fails)} contrast pair(s) fail. Try another seed colour (a darker or more saturated tone).")

    # numbers
    sp = base["spacing"]["scale"]
    typo = base["typography"]
    rscale = base["radius"]["scale"]
    radius = {k: round(a.radius * v) for k, v in rscale.items()}
    radius["none"], radius["full"] = 0, 9999
    sizes = {k: v for k, v in base["size"].items() if not k.startswith("$")}
    dens = base["density"]["tokens"]
    fixed = base["spacing"]["fixed"]
    font_stack = f"\"{a.font}\", {typo['fallback']['sans']}"
    mono_stack = f"{typo['family']['mono']}, {typo['fallback']['mono']}"
    styles = typo["styles"]

    # ------------------------------------------------------------ tokens.css
    L = [f"/* tokens.css · {label} {PROFILE_VERSION} · generated by adopt from the {a.preset} preset. Do not edit by hand: rerun adopt or edit tokens. */",
         ":root {", "  color-scheme: light;", "  /* primitives: colour */"]
    for pal in pals.p:
        for s in pals.order(pal):
            L.append(f"  {prefix}color-{pal}-{s}: {pals.p[pal][s]};")
    L.append("  /* primitives: numbers */")
    L += [f"  {prefix}num-spacing-{k}: {px(v)};" for k, v in sp.items()]
    L += [f"  {prefix}num-font-size-{k}: {px(v)};" for k, v in typo["size"].items()]
    L += [f"  {prefix}num-line-height-{k}: {px(v)};" for k, v in typo["lineHeight"].items()]
    L += [f"  {prefix}num-font-weight-{k}: {v};" for k, v in typo["weight"].items()]
    L.append("  /* semantic: colour (light) */")
    L += sem_lines(prefix, res["light"])
    L.append("  /* semantic: radius, type, shadow, space, size, motion, z */")
    L += [f"  {prefix}radius-{k}: {px(v)};" for k, v in radius.items()]
    L += [f"  {prefix}font-family-sans: {font_stack};", f"  {prefix}font-family-mono: {mono_stack};"]
    L += [f"  {prefix}font-weight-{k}: {var(prefix, 'num-font-weight-' + k)};" for k in typo["weight"]]
    for st, v in styles.items():
        L += [f"  {prefix}font-size-{st}: {var(prefix, 'num-font-size-' + v['size'])};",
              f"  {prefix}line-height-{st}: {var(prefix, 'num-line-height-' + v['lineHeight'])};",
              f"  {prefix}font-weight-{st}: {var(prefix, 'num-font-weight-' + v['weight'])};"]
    L += [f"  {prefix}shadow-{k}: {v};" for k, v in base["shadow"]["light"].items()]
    L += [f"  {prefix}space-{k}: {var(prefix, 'num-spacing-' + v)};" for k, v in fixed.items()]
    L += [f"  {prefix}size-{k}: {px(v)};" for k, v in sizes.items()]
    L += [f"  {prefix}motion-{k}: {v};" for k, v in base["motion"].items()]
    L += [f"  {prefix}z-{k}: {v};" for k, v in base["z"].items()]
    L.append("}")
    L.append("")
    L.append("/* density (Material Design 3 levels): auto = comfortable below 840 px or on touch screens, standard on wide screens with a mouse */")

    def dens_block(sel, mode):
        return [f"{sel} {{"] + [f"  {prefix}space-{k}: {var(prefix, 'num-spacing-' + v[mode])};" for k, v in dens.items()] + ["}"]
    L += dens_block(':root, [data-density="auto"], [data-density="comfortable"]', "comfortable")
    L += ["@media (min-width: 840px) and (pointer: fine) {"]
    L += ["  " + x for x in dens_block(':root:not([data-density]), [data-density="auto"]', "standard")]
    L += ["}"]
    L += dens_block('[data-density="standard"]', "standard")
    L += dens_block('[data-density="compact"]', "compact")
    L.append("")
    L.append("/* alias layer for shadcn/ui and shadcn-vue (contract with the react and vue templates). Recomputed wherever data-mode or .dark is set. */")
    L.append(":root, [data-mode], .dark {")
    alias = {}
    for tok, spec in semantic.items():
        for al in [x.strip() for x in spec.get("alias", "").split(",") if x.strip()]:
            alias[al] = tok
    alias.update({"--card-foreground": "text-primary", "--popover-foreground": "text-primary",
                  "--secondary-foreground": "text-primary", "--accent-foreground": "text-primary",
                  "--sidebar-foreground": "text-primary", "--sidebar-primary": "bg-brand",
                  "--sidebar-primary-foreground": "text-on-brand", "--sidebar-accent": "bg-hover",
                  "--sidebar-accent-foreground": "text-primary", "--sidebar-border": "stroke-default",
                  "--sidebar-ring": "stroke-focus"})
    alias.update(ALIASES_EXTRA)
    for al in sorted(alias):
        L.append(f"  {al}: {var(prefix, alias[al])};")
    L.append(f"  --radius: {var(prefix, 'radius-lg')};")
    L.append("}")
    tokens_css = "\n".join(L) + "\n"

    dark_css = None
    if dark:
        D = [f"/* tokens-dark.css · {label} {PROFILE_VERSION} · dark mode: <html data-mode=\"dark\"> (also .dark for shadcn/ui and shadcn-vue). */",
             '[data-mode="dark"], .dark {', "  color-scheme: dark;"]
        D += sem_lines(prefix, res["dark"])
        D += [f"  {prefix}shadow-{k}: {v};" for k, v in base["shadow"]["dark"].items()]
        D.append("}")
        dark_css = "\n".join(D) + "\n"

    def fill(text):
        return text.replace("--T-", prefix).replace("ZZ-", cls)
    base_css = fill((preset_dir / "templates/base.css").read_text(encoding="utf-8"))
    comp_css = fill((preset_dir / "templates/components.css").read_text(encoding="utf-8"))
    resp_css = fill((preset_dir / "templates/responsive.css").read_text(encoding="utf-8"))

    sources = ["tokens.css"] + (["tokens-dark.css"] if dark else []) + ["base.css", "components.css", "responsive.css"]
    texts = {"tokens.css": tokens_css, "tokens-dark.css": dark_css, "base.css": base_css,
             "components.css": comp_css, "responsive.css": resp_css}
    bundle = (f"/* @ds:begin */\n/* {label} {PROFILE_VERSION} · {a.preset} preset (MIT) + Material Design 3 structure · see NOTICE */\n"
              + "\n".join(f"/* ---- {s} ---- */\n{texts[s]}" for s in sources) + "/* @ds:end */\n")

    # ------------------------------------------------------------ write files
    out.mkdir(parents=True, exist_ok=True)
    for s in sources:
        write(out / s, texts[s])
    if not dark and (out / "tokens-dark.css").exists():
        (out / "tokens-dark.css").unlink()
    write(out / "dist" / f"{a.name}.css", bundle)

    adjusted = [(m, tok, r["start"], r["ref"]) for m in modes for tok, r in res[m].items() if r["adjusted"]]
    ds = {
        "name": a.name, "label": label, "version": PROFILE_VERSION, "platforms": platforms,
        "tokens": {
            "prefix": prefix,
            "roles": {"text": f"{prefix}text-", "bg": f"{prefix}bg-", "stroke": f"{prefix}stroke-", "icon": f"{prefix}icon-",
                      "radius": f"{prefix}radius-", "fontSize": f"{prefix}font-size-", "lineHeight": f"{prefix}line-height-",
                      "spacing": f"{prefix}space-", "shadow": f"{prefix}shadow-"},
            "scale": {"spacing": f"{prefix}num-spacing-"},
            "file": "tokens.json"},
        "css": {"bundle": f"dist/{a.name}.css", "sources": sources, "marker": {"begin": "@ds:begin", "end": "@ds:end"}},
        "version_label": {"text": "{label} {version}", "meta": "ds-version"},
        "theming": {
            "brand": {"attr": "data-brand", "values": ["default"]},
            "mode": {"attr": "data-mode", "values": modes, "default": "light"},
            "density": {"attr": "data-density", "values": ["auto"] + DENSITIES, "default": "auto"}},
        "breakpoints": {"compact": 0, "medium": 600, "expanded": 840},
        "icons": {"set": "tabler", "file": "icons.json"},
        "catalog": "catalog.md", "rules": "rules.md", "library": {"page": "library.html"},
        "figma": {"libraries": [],
                  "collections": {"primitives": "Primitives", "semantic": "Semantic", "spacing": "Spacing"},
                  "modes": {"light": "Light", "dark": "Dark"} if dark else {"light": "Light"},
                  "variables": "figma-variables.json"},
        "preset": {"name": a.preset, "version": preset["values"]["upstream_version"]},
    }
    write(out / "ds.json", json.dumps(ds, ensure_ascii=False, indent=2) + "\n")

    write(out / "tokens.json", json.dumps(dtcg(prefix, pals, res, modes, sp, typo, radius, base, fixed, dens, sizes, styles, font_stack, label, a.preset),
                                          ensure_ascii=False, indent=2) + "\n")
    write(out / "figma-variables.json", json.dumps(figma_data(prefix, pals, res, modes, sp, typo, radius, fixed, dens, sizes, styles, a.font, label),
                                                   ensure_ascii=False, indent=2) + "\n")
    icons = read_json(ASSETS / "icons.json")
    write(out / "icons.json", json.dumps(icons, ensure_ascii=False, indent=2) + "\n")

    write(out / "catalog.md", catalog_md(T, label, prefix, cls, a.preset, preset, comps, comp_css + resp_css, modes))
    write(out / "rules.md", rules_md(T, label, prefix, a.font, adjusted, comps, rows))
    write(out / "library.html", library_html(T, lang, label, a.name, prefix, cls, bundle, res, pals, modes, styles, typo, radius, a.font, icons))
    write(out / "flutter" / f"{a.name.replace('-', '_')}_theme.dart", flutter_dart(a.name, label, res, modes, sp, typo, radius, styles, a.font, dens, sizes))
    notice = (f"{label} {PROFILE_VERSION}\nGenerated on {today} by the adopt skill of the prototype kit from the {a.preset} preset.\n"
              f"Brand palette generated from the seed {seed}; prefix {prefix}; radius {a.radius} px; font {a.font} (not bundled).\n\n"
              + (preset_dir / "NOTICE").read_text(encoding="utf-8"))
    write(out / "NOTICE", notice)
    yes_no = T("adopt.yes") if dark else T("adopt.no")
    cl = [f"# {T('adopt.changelog.title')}", "", f"## {PROFILE_VERSION} · {today}", "",
          "- " + T("adopt.changelog.entry", preset=a.preset, upstream=preset["values"]["upstream_version"], seed=seed,
                   prefix=prefix, radius=a.radius, font=a.font, dark=yes_no, platforms=", ".join(platforms)),
          "- " + T("adopt.changelog.adjusted", n=len(adjusted))]
    write(out / "CHANGELOG.md", "\n".join(cl) + "\n")

    print()
    print(f"Profile written to {a.out}")
    for f in sorted(p.relative_to(out) for p in out.rglob("*") if p.is_file()):
        print(f"  {f}")
    print(f"Brand seed {seed} sits at brand-{seed_step}. Adjusted tones: {len(adjusted)}.")
    for m, tok, s, r in adjusted:
        print(f"  {m}: {tok} {s} -> {r}")
        if tok == "bg-brand":
            print(f"WARNING: in {m} mode the seed itself fails contrast as a fill; buttons use {r}. Tell the designer.")
    print("Flutter theme is generated, not compiled: run `flutter analyze` in a Flutter project.")
    print(f"Next: python3 {HERE} check --out {a.out}")


def sem_lines(prefix, res):
    out = []
    for tok, r in res.items():
        if r.get("alpha") is not None:
            out.append(f"  {prefix}{tok}: {r['hex']};")
        else:
            out.append(f"  {prefix}{tok}: {ref_var(prefix, r['ref'])};")
    return out


def print_contrast(rows):
    print(f"{'mode':5} {'foreground':16} {'background':18} {'ratio':>6} {'min':>4}  result")
    for r in rows:
        print(f"{r['mode']:5} {r['fg']:16} {r['bg']:18} {r['ratio']:6.2f} {r['min']:4}  {r['status']}")
    n = {s: sum(1 for r in rows if r["status"] == s) for s in ("PASS", "ADJUSTED", "FAIL")}
    print(f"Contrast: {len(rows)} pairs · {n['PASS']} pass · {n['ADJUSTED']} pass after tone adjustment · {n['FAIL']} fail")


# ---------------------------------------------------------------- tokens.json
def dtcg(prefix, pals, res, modes, sp, typo, radius, base, fixed, dens, sizes, styles, font_stack, label, preset):
    prim = {"color": {}}
    for pal in pals.p:
        prim["color"][pal] = {s: {"$type": "color", "$value": pals.p[pal][s]} for s in pals.order(pal)}
    prim["spacing"] = {k: {"$type": "dimension", "$value": px(v)} for k, v in sp.items()}
    prim["fontSize"] = {k: {"$type": "dimension", "$value": px(v)} for k, v in typo["size"].items()}
    prim["lineHeight"] = {k: {"$type": "dimension", "$value": px(v)} for k, v in typo["lineHeight"].items()}
    prim["fontWeight"] = {k: {"$type": "fontWeight", "$value": v} for k, v in typo["weight"].items()}
    sem = {}
    for tok in res["light"]:
        role, name = tok.split("-", 1)
        entry = {"$type": "color"}
        ext = {}
        for m in modes:
            r = res[m][tok]
            if r.get("alpha") is not None:
                val = r["hex"]
            else:
                pal, step = r["ref"].split(".")
                val = "{primitive.color.%s.%s}" % (pal, step)
            ext[m] = {"value": val, "hex": r["hex"], "adjusted": r["adjusted"]}
        entry["$value"] = ext["light"]["value"]
        entry["$extensions"] = {"kit.modes": ext, "kit.css": f"{prefix}{tok}"}
        sem.setdefault(role, {})[name] = entry
    sem["radius"] = {k: {"$type": "dimension", "$value": px(v)} for k, v in radius.items()}
    sem["shadow"] = {k: {"$type": "shadow", "$value": v, "$extensions": {"kit.modes": {"dark": base["shadow"]["dark"][k]}}}
                     for k, v in base["shadow"]["light"].items()}
    sem["space"] = {k: {"$type": "dimension", "$value": "{primitive.spacing.%s}" % v} for k, v in fixed.items()}
    for k, v in dens.items():
        sem["space"][k] = {"$type": "dimension", "$value": "{primitive.spacing.%s}" % v["comfortable"],
                           "$extensions": {"kit.density": {d: "{primitive.spacing.%s}" % v[d] for d in DENSITIES}}}
    sem["size"] = {k: {"$type": "dimension", "$value": px(v)} for k, v in sizes.items()}
    sem["fontFamily"] = {"sans": {"$type": "fontFamily", "$value": font_stack}}
    sem["typography"] = {st: {"$type": "typography", "$value": {
        "fontFamily": "{semantic.fontFamily.sans}", "fontSize": "{primitive.fontSize.%s}" % v["size"],
        "lineHeight": "{primitive.lineHeight.%s}" % v["lineHeight"], "fontWeight": "{primitive.fontWeight.%s}" % v["weight"]}}
        for st, v in styles.items()}
    return {"$description": f"{label} {PROFILE_VERSION}: W3C Design Tokens (DTCG). Semantic colours: $value is the light mode; $extensions.kit.modes holds every mode. Generated by adopt ({preset} preset).",
            "primitive": prim, "semantic": sem}


# ---------------------------------------------------------------- figma
def figma_data(prefix, pals, res, modes, sp, typo, radius, fixed, dens, sizes, styles, font, label):
    P = []
    for pal in pals.p:
        for s in pals.order(pal):
            P.append({"name": f"color/{pal}/{s}", "type": "COLOR", "values": {"Value": pals.p[pal][s]}, "scopes": [],
                      "code": f"{prefix}color-{pal}-{s}"})
    P += [{"name": f"spacing/{k}", "type": "FLOAT", "values": {"Value": v}, "scopes": [], "code": f"{prefix}num-spacing-{k}"} for k, v in sp.items()]
    P += [{"name": f"radius/{k}", "type": "FLOAT", "values": {"Value": v}, "scopes": ["CORNER_RADIUS"], "code": f"{prefix}radius-{k}"} for k, v in radius.items()]
    P += [{"name": f"font-size/{k}", "type": "FLOAT", "values": {"Value": v}, "scopes": ["FONT_SIZE"], "code": f"{prefix}num-font-size-{k}"} for k, v in typo["size"].items()]
    P += [{"name": f"line-height/{k}", "type": "FLOAT", "values": {"Value": v}, "scopes": ["LINE_HEIGHT"], "code": f"{prefix}num-line-height-{k}"} for k, v in typo["lineHeight"].items()]
    P += [{"name": f"font-weight/{k}", "type": "FLOAT", "values": {"Value": v}, "scopes": ["FONT_WEIGHT"], "code": f"{prefix}num-font-weight-{k}"} for k, v in typo["weight"].items()]
    scopes = {"text": ["TEXT_FILL"], "bg": ["FRAME_FILL", "SHAPE_FILL"], "stroke": ["STROKE_COLOR"],
              "icon": ["SHAPE_FILL", "STROKE_COLOR"], "chart": ["SHAPE_FILL", "STROKE_COLOR"]}
    mode_names = {"light": "Light", "dark": "Dark"}
    S = []
    for tok in res["light"]:
        role, name = tok.split("-", 1)
        vals = {}
        for m in modes:
            r = res[m][tok]
            if r.get("alpha") is not None:
                vals[mode_names[m]] = r["hex"]
            else:
                pal, step = r["ref"].split(".")
                vals[mode_names[m]] = {"alias": f"Primitives/color/{pal}/{step}"}
        S.append({"name": f"{role}/{name}", "type": "COLOR", "values": vals, "scopes": scopes[role], "code": f"{prefix}{tok}"})
    dnames = {d: d.capitalize() for d in DENSITIES}
    SP = []
    for k, v in fixed.items():
        SP.append({"name": f"space/{k}", "type": "FLOAT", "values": {dnames[d]: {"alias": f"Primitives/spacing/{v}"} for d in DENSITIES},
                   "scopes": ["GAP"], "code": f"{prefix}space-{k}"})
    for k, v in dens.items():
        sc = ["WIDTH_HEIGHT"] if k.endswith("-h") or k.startswith("control-h") or k == "row-h" else ["GAP"]
        SP.append({"name": f"space/{k}", "type": "FLOAT", "values": {dnames[d]: {"alias": f"Primitives/spacing/{v[d]}"} for d in DENSITIES},
                   "scopes": sc, "code": f"{prefix}space-{k}"})
    for k, v in sizes.items():
        SP.append({"name": f"size/{k}", "type": "FLOAT", "values": {dnames[d]: v for d in DENSITIES}, "scopes": ["WIDTH_HEIGHT"], "code": f"{prefix}size-{k}"})
    text_styles = [{"name": f"{label}/{st}", "fontFamily": font, "fontStyle": WEIGHT_STYLE[typo["weight"][v["weight"]]],
                    "fontSize": typo["size"][v["size"]], "lineHeight": typo["lineHeight"][v["lineHeight"]],
                    "letterSpacing": LETTER.get(st, 0), "description": f"{prefix}font-size-{st}"} for st, v in styles.items()]
    return {"$description": "Figma level 1 data for skills/adopt/assets/figma-push.js (use_figma).",
            "collections": {
                "primitives": {"name": "Primitives", "modes": ["Value"], "variables": P},
                "semantic": {"name": "Semantic", "modes": [mode_names[m] for m in modes], "variables": S},
                "spacing": {"name": "Spacing", "modes": [dnames[d] for d in DENSITIES], "variables": SP}},
            "textStyles": text_styles}


# ---------------------------------------------------------------- catalog / rules
def block_tokens(css, prefix):
    blocks = {}
    for m in re.finditer(r"/\* == component: ([a-z0-9-]+) == \*/(.*?)(?=/\* == component:|\Z)", css, re.S):
        found = sorted(set(re.findall(r"var\((" + re.escape(prefix) + r"[a-z0-9-]+)\)", m.group(2))))
        blocks[m.group(1)] = found
    return blocks


def catalog_md(T, label, prefix, cls, preset_name, preset, comps, css, modes):
    toks = block_tokens(css, prefix)
    L = [f"# {T('adopt.catalog.title', label=label)}", "",
         T("adopt.catalog.intro", preset=preset_name, version=preset["values"]["upstream_version"], cls=cls, prefix=prefix), "",
         f"## {T('adopt.catalog.theming')}", "",
         T("adopt.catalog.themingBody", modes=", ".join(modes), densities="auto, " + ", ".join(DENSITIES)), "",
         f"## {T('adopt.catalog.layout')}", "", T("adopt.catalog.layoutBody", cls=cls), "",
         f"## {T('adopt.catalog.components')}", ""]
    for c in comps:
        src = T("adopt.catalog.composed") if c["source"] == "composed" else T("adopt.catalog.preset")
        L += [f"### {c['name']}", "",
              f"- {T('adopt.catalog.class')}: `.{cls}{c['class']}`",
              f"- {T('adopt.catalog.variants')}: " + ", ".join(f"`{v}`" if v.startswith("--") else v for v in c["variants"]),
              f"- {T('adopt.catalog.states')}: " + (", ".join(c["states"]) or "—"),
              f"- {T('adopt.catalog.source')}: {src}"]
        if c.get("structure"):
            L.append(f"- {T('adopt.catalog.structure')}: {c['structure']}")
        if c.get("notes"):
            notes = re.sub(r"(^|[\s(,]|label|span|details|input)\.([a-z][a-z-]*[a-z])", lambda m: f"{m.group(1)}.{cls}{m.group(2)}", c["notes"])
            L.append(f"- {T('adopt.catalog.notes')}: {notes}")
        t = toks.get(c["id"], [])
        L.append(f"- {T('adopt.catalog.tokens')}: " + (" ".join(f"`{x}`" for x in t) if t else "—"))
        L.append("")
    L += [f"## {T('adopt.catalog.map')}", "", T("adopt.catalog.mapIntro"), "",
          "| HTML class | React (shadcn/ui) | Vue (shadcn-vue) | " + T("adopt.catalog.source") + " |", "|---|---|---|---|"]
    for c in comps:
        L.append(f"| `.{cls}{c['class']}` | {c['react']} | {c['vue']} | {c['source']} |")
    L.append("")
    return "\n".join(L)


def rules_md(T, label, prefix, font, adjusted, comps, rows):
    L = [f"# {T('adopt.rules.title', label=label)}", "", f"## {T('adopt.rules.hard')}", ""]
    for i in range(1, 13):
        L.append(f"{i}. " + T(f"adopt.rules.r{i}", prefix=prefix, font=font))
    L += ["", f"## {T('adopt.rules.deviations')}", ""]
    L.append("- " + T("adopt.rules.devInput"))
    L.append("- " + T("adopt.rules.devFocus"))
    if adjusted:
        for m, tok, s, r in adjusted:
            row = next((x for x in rows if x["mode"] == m and x["fg"] == tok), None)
            L.append("- " + T("adopt.rules.adjusted", token=f"{prefix}{tok}", mode=m, frm=s, to=r,
                              ratio=row["ratio"] if row else "?", min=row["min"] if row else "?"))
    else:
        L.append("- " + T("adopt.rules.noneAdjusted"))
    L += ["", f"## {T('adopt.rules.composed')}", "", T("adopt.rules.composedIntro"), ""]
    L += [f"- {c['name']}: {c.get('structure', '')}" for c in comps if c["source"] == "composed"]
    L += ["", f"## {T('adopt.rules.contrast')}", "", T("adopt.rules.contrastIntro", exempt=", ".join(EXEMPT)), "",
          f"| {T('adopt.rules.colMode')} | {T('adopt.rules.colFg')} | {T('adopt.rules.colBg')} | {T('adopt.rules.colRatio')} | {T('adopt.rules.colMin')} | {T('adopt.rules.colResult')} |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['mode']} | `{r['fg']}` {r['fgHex']} | `{r['bg']}` {r['bgHex']} | {r['ratio']}:1 | {r['min']}:1 | {r['status']} |")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------- library page
def library_html(T, lang, label, name, prefix, cls, bundle, res, pals, modes, styles, typo, radius, font, icons):
    tpl = (ASSETS / "library.html").read_text(encoding="utf-8")
    svg = icons["svg"]

    def icon(n):
        return svg.replace("{body}", icons["icons"][n])
    sw = []
    for tok in res["light"]:
        hexes = " / ".join(res[m][tok]["hex"] for m in modes)
        sw.append(f'<div class="lib-swatch"><i style="background: var({prefix}{tok})"></i><span><code>{tok}</code><br>{hexes}</span></div>')
    ramps = []
    for pal in ["brand", "neutral", "danger", "warning", "success", "info"]:
        cells = "".join(f'<i title="{pal}-{s} {pals.p[pal][s]}" style="background: var({prefix}color-{pal}-{s})"></i>'
                        for s in pals.order(pal) if s in pals.orig[pal])
        ramps.append(f'<div class="lib-block"><span class="lib-ramp-name">{pal}</span><div class="lib-ramp">{cells}</div></div>')
    ty = "".join(f'<div><code>{st} {typo["size"][v["size"]]}/{typo["lineHeight"][v["lineHeight"]]}</code><span class="ZZ-text-{st}">The quick brown fox</span></div>'
                 for st, v in styles.items())
    rad = "".join(f'<div class="lib-box" style="border-radius: var({prefix}radius-{k}); box-shadow: var({prefix}shadow-{s})">{k}</div>'
                  for k, s in [("sm", "xs"), ("md", "sm"), ("lg", "md"), ("xl", "lg"), ("2xl", "lg")])
    css = bundle.replace("/* @ds:begin */\n", "").replace("/* @ds:end */\n", "")
    html = tpl
    rep = {"{{LANG}}": lang, "{{LABEL}}": label, "{{VERSION}}": PROFILE_VERSION, "{{VERSION_LABEL}}": f"{label} {PROFILE_VERSION}",
           "{{META}}": "ds-version", "{{DENSITY_DEFAULT}}": "auto", "{{INITIAL}}": label[:1].upper(), "{{FONT}}": font,
           "{{SWATCHES_SEMANTIC}}": "".join(sw), "{{SWATCHES_PALETTES}}": "".join(ramps), "{{TYPE}}": ty, "{{RADII}}": rad,
           "{{HAS_DARK}}": "true" if "dark" in modes else "false",
           "{{DARK_HIDDEN}}": "" if "dark" in modes else "hidden", "{{DARK_DISABLED}}": "" if "dark" in modes else "disabled"}
    for k, v in rep.items():
        html = html.replace(k, v)
    html = re.sub(r"\{\{i:([a-z0-9-]+)\}\}", lambda m: icon(m.group(1)), html)
    html = re.sub(r"\{\{t:([a-zA-Z0-9.]+)\}\}", lambda m: T(m.group(1)), html)
    html = html.replace("--T-", prefix).replace("ZZ-", cls)
    html = html.replace("{{CSS}}", css)  # last: the bundle already carries the real prefixes
    return html


# ---------------------------------------------------------------- flutter
def _camel(s):
    parts = re.split(r"[-_]", s)
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def _dart_color(h):
    h = h.lstrip("#")
    a = h[6:8] if len(h) == 8 else "ff"
    return f"Color(0x{a.upper()}{h[:6].upper()})"


def flutter_dart(name, label, res, modes, sp, typo, radius, styles, font, dens, sizes):
    C = "".join(p.capitalize() for p in name.split("-"))
    toks = list(res["light"])
    f = [f"// {label} {PROFILE_VERSION}: Flutter theme generated by the adopt skill from tokens.json.",
         "// NOT COMPILED. Run `flutter analyze` in a Flutter project before use.",
         "// Material Design 3 structure: ColorScheme + ThemeExtension for the DS roles.",
         "import 'package:flutter/material.dart';", "",
         "@immutable", f"class {C}Colors extends ThemeExtension<{C}Colors> {{",
         f"  const {C}Colors({{" + " ".join(f"required this.{_camel(t)}," for t in toks) + "});"]
    f += [f"  final Color {_camel(t)};" for t in toks]
    for m in modes:
        f.append(f"  static const {m} = {C}Colors(")
        f += [f"    {_camel(t)}: {_dart_color(res[m][t]['hex'])}," for t in toks]
        f.append("  );")
    f.append("  @override")
    f.append(f"  {C}Colors copyWith({{" + " ".join(f"Color? {_camel(t)}," for t in toks) + "}) {")
    f.append(f"    return {C}Colors(" + " ".join(f"{_camel(t)}: {_camel(t)} ?? this.{_camel(t)}," for t in toks) + ");")
    f.append("  }")
    f.append("  @override")
    f.append(f"  {C}Colors lerp(ThemeExtension<{C}Colors>? other, double t) {{")
    f.append(f"    if (other is! {C}Colors) return this;")
    f.append(f"    return {C}Colors(" + " ".join(f"{_camel(t)}: Color.lerp({_camel(t)}, other.{_camel(t)}, t)!," for t in toks) + ");")
    f.append("  }")
    f.append("}")
    f.append("")
    f.append(f"class {C}Space {{")
    f += [f"  static const double s{k.replace('-', '_')} = {v}.0;" for k, v in sp.items()]
    f += [f"  static const double {_camel(k)}{d.capitalize()} = {sp[v[d]]}.0;" for k, v in dens.items() for d in DENSITIES]
    f += [f"  static const double size{_camel(k)[:1].upper() + _camel(k)[1:]} = {v}.0;" for k, v in sizes.items()]
    f.append("}")
    f.append("")
    f.append(f"class {C}Radius {{")
    f += [f"  static const double r{k.replace('-', '_')} = {v}.0;" for k, v in radius.items()]
    f.append("}")
    f.append("")
    wmap = {400: "w400", 500: "w500", 600: "w600", 700: "w700"}
    f.append(f"TextTheme {_camel(name)}TextTheme(Color color) => TextTheme(")
    m3 = {"display": "displaySmall", "headline": "headlineSmall", "title": "titleLarge", "subtitle": "titleMedium",
          "body-large": "bodyLarge", "body": "bodyMedium", "label": "labelLarge", "caption": "bodySmall"}
    for st, v in styles.items():
        size, lh, w = typo["size"][v["size"]], typo["lineHeight"][v["lineHeight"]], typo["weight"][v["weight"]]
        f.append(f"  {m3[st]}: TextStyle(fontFamily: '{font}', fontSize: {size}, height: {lh}/{size}, fontWeight: FontWeight.{wmap[w]}, color: color),")
    f.append(");")
    f.append("")
    f.append(f"ThemeData {_camel(name)}Theme({{Brightness brightness = Brightness.light, VisualDensity density = VisualDensity.standard}}) {{")
    has_dark = "dark" in modes
    f.append(f"  final c = brightness == Brightness.dark ? {C}Colors.dark : {C}Colors.light;" if has_dark else f"  final c = {C}Colors.light; // dark mode not enabled")
    f.append("  final scheme = ColorScheme(")
    f += ["    brightness: brightness,", "    primary: c.bgBrand,", "    onPrimary: c.textOnBrand,",
          "    primaryContainer: c.bgBrandSubtle,", "    onPrimaryContainer: c.textBrand,",
          "    secondary: c.bgSubtle,", "    onSecondary: c.textPrimary,", "    error: c.bgDanger,", "    onError: c.textOnDanger,",
          "    errorContainer: c.bgDangerSubtle,", "    onErrorContainer: c.textDanger,",
          "    surface: c.bgSurface,", "    onSurface: c.textPrimary,", "    onSurfaceVariant: c.textSecondary,",
          "    surfaceContainerLow: c.bgSidebar,", "    surfaceContainerHighest: c.bgSubtle,",
          "    outline: c.strokeStrong,", "    outlineVariant: c.strokeDefault,", "    inverseSurface: c.bgInverse,",
          "    onInverseSurface: c.textInverse,", "    scrim: c.bgScrim,", "  );"]
    f += ["  return ThemeData(", "    useMaterial3: true,", "    colorScheme: scheme,", "    scaffoldBackgroundColor: c.bgCanvas,",
          f"    fontFamily: '{font}',", f"    textTheme: {_camel(name)}TextTheme(c.textPrimary),", "    visualDensity: density,",
          "    materialTapTargetSize: MaterialTapTargetSize.padded, // 48 dp touch targets",
          f"    extensions: [c],", "  );", "}", ""]
    return "\n".join(f)


# ---------------------------------------------------------------- check
def check(a):
    out = Path(a.out)
    errs, warns = [], []
    f = out / "ds.json"
    if not f.is_file():
        die(f"{f} not found")
    ds = read_json(f)
    prefix = ds.get("tokens", {}).get("prefix", "")
    for k in ("name", "label", "version", "platforms", "tokens", "css", "version_label", "theming", "breakpoints", "catalog", "rules", "figma", "preset"):
        if k not in ds:
            errs.append(f"ds.json: missing key '{k}'")
    need = [ds["tokens"]["file"], ds["css"]["bundle"], ds["catalog"], ds["rules"], ds.get("library", {}).get("page", "library.html"),
            "NOTICE", "CHANGELOG.md", ds["figma"].get("variables", "figma-variables.json"), ds.get("icons", {}).get("file", "icons.json")]
    need += ds["css"]["sources"]
    for n in need:
        if n and not (out / n).is_file():
            errs.append(f"missing file {n}")
    if not list((out / "flutter").glob("*.dart")):
        warns.append("no Flutter theme in flutter/")
    if errs:
        return report(errs, warns)
    bundle = (out / ds["css"]["bundle"]).read_text(encoding="utf-8")
    if not bundle.startswith("/* @ds:begin */") or not bundle.rstrip().endswith("/* @ds:end */"):
        errs.append("bundle is not wrapped in /* @ds:begin */ ... /* @ds:end */")
    srcs = {s: (out / s).read_text(encoding="utf-8") for s in ds["css"]["sources"]}
    defined = set()
    for s in ("tokens.css", "tokens-dark.css"):
        if s in srcs:
            defined |= set(re.findall(r"(--[a-z0-9-]+)\s*:", srcs[s]))
    for s in ("base.css", "components.css", "responsive.css"):
        css = re.sub(r"/\*.*?\*/", "", srcs.get(s, ""), flags=re.S)
        css_no_mask = re.sub(r'url\("data:[^"]*"\)', "url()", css)
        body = re.sub(r"@media[^{]*\{", "{", css_no_mask)
        for pat, what in [(r"#[0-9a-fA-F]{3,8}\b", "hex colour"), (r"\b(rgb|rgba|hsl|hsla|oklch)\(", "raw colour function"),
                          (re.escape(prefix) + r"(color|num)-", "primitive token")]:
            for m in re.finditer(pat, body):
                errs.append(f"{s}: {what} '{m.group(0)}'")
        if s != "base.css":
            for m in re.finditer(r"(?<![\w.-])\d*\.?\d+px\b", body):
                errs.append(f"{s}: px value '{m.group(0)}' (use a token)")
        for v in set(re.findall(r"var\((" + re.escape(prefix) + r"[a-z0-9-]+)", css)):
            if v not in defined:
                errs.append(f"{s}: token {v} is used but not defined")
    must = ["--background", "--foreground", "--card", "--card-foreground", "--popover", "--popover-foreground", "--primary",
            "--primary-foreground", "--secondary", "--secondary-foreground", "--muted", "--muted-foreground", "--accent",
            "--accent-foreground", "--destructive", "--border", "--input", "--ring", "--radius"] + [f"--chart-{i}" for i in range(1, 6)] + \
           ["--sidebar", "--sidebar-foreground", "--sidebar-primary", "--sidebar-primary-foreground", "--sidebar-accent",
            "--sidebar-accent-foreground", "--sidebar-border", "--sidebar-ring"]
    for al in must:
        if not re.search(re.escape(al) + r"\s*:\s*var\(" + re.escape(prefix), bundle):
            errs.append(f"alias {al} missing or not pointing at a DS token")
    tj = read_json(out / ds["tokens"]["file"])
    res = {}
    for role, group in tj.get("semantic", {}).items():
        for nm, e in group.items():
            for m, v in e.get("$extensions", {}).get("kit.modes", {}).items():
                if isinstance(v, dict) and "hex" in v:
                    res.setdefault(m, {})[f"{role}-{nm}"] = {"hex": v["hex"], "adjusted": v.get("adjusted", False)}
    rows = []
    for m in ds["theming"]["mode"]["values"]:
        if m not in res:
            errs.append(f"tokens.json has no '{m}' values")
            continue
        rows += verify(m, res[m], contrast_pairs())
    bad = [r for r in rows if r["status"] == "FAIL"]
    for r in bad:
        errs.append(f"contrast {r['mode']} {r['fg']} on {r['bg']}: {r['ratio']}:1 < {r['min']}:1")
    print(f"Contrast: {len(rows)} pairs checked, {len(bad)} fail, {sum(1 for r in rows if r['status'] == 'ADJUSTED')} adjusted by adopt.")
    lib = (out / ds["library"]["page"]).read_text(encoding="utf-8")
    if re.search(r"<(script|link)[^>]+(src|href)=\"https?://", lib):
        errs.append("library.html loads external files")
    if re.search(r"\{\{[^}]+\}\}", lib):
        errs.append("library.html has unfilled placeholders")
    return report(errs, warns)


def report(errs, warns):
    for w in warns:
        print("WARNING:", w)
    for e in errs:
        print("ERROR:", e)
    print("Profile OK" if not errs else f"{len(errs)} error(s)")
    sys.exit(1 if errs else 0)


def figma_script(a):
    out = Path(a.out)
    ds = read_json(out / "ds.json")
    data = (out / ds["figma"].get("variables", "figma-variables.json")).read_text(encoding="utf-8")
    data = json.dumps(json.loads(data), ensure_ascii=False, separators=(",", ":"))
    js = (ASSETS / "figma-push.js").read_text(encoding="utf-8").replace("const DATA = __DATA__;", f"const DATA = {data};")
    if a.js:
        write(a.js, js)
        print(f"use_figma code written to {a.js} ({len(js)} characters)")
    else:
        sys.stdout.write(js)


# ---------------------------------------------------------------- cli
def main(argv):
    # allow "--prefix --acme-" (argparse would read --acme- as an option)
    fixed = []
    i = 0
    while i < len(argv):
        if argv[i] == "--prefix" and i + 1 < len(argv) and argv[i + 1].startswith("--"):
            fixed.append("--prefix=" + argv[i + 1])
            i += 2
            continue
        fixed.append(argv[i])
        i += 1
    cmd = "generate"
    if fixed and fixed[0] in ("generate", "check", "figma-script"):
        cmd = fixed.pop(0)
    p = argparse.ArgumentParser(prog="adopt.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, help="profile folder, e.g. ds/acme")
    if cmd == "generate":
        p.add_argument("--name", required=True, help="DS name: lowercase, e.g. acme")
        p.add_argument("--label", help='display name, e.g. "Acme DS"')
        p.add_argument("--prefix", help="token prefix, e.g. --acme- (default --<name>-)")
        p.add_argument("--seed", required=True, help="brand seed colour, #rrggbb")
        p.add_argument("--radius", type=int, default=10, help="base radius in px (preset default 10)")
        p.add_argument("--font", default="Inter", help="font family name (default Inter)")
        p.add_argument("--no-dark", action="store_true", help="light mode only")
        p.add_argument("--preset", default="shadcn", help="preset folder under presets/ (default shadcn)")
        p.add_argument("--platforms", default="web,mobile,tablet", help="comma list (default web,mobile,tablet)")
        p.add_argument("--lang", help="language of generated documents (default kit.config.json > language, else en)")
        p.add_argument("--force", action="store_true", help="overwrite generated files in a non-empty --out")
    if cmd == "figma-script":
        p.add_argument("--js", help="write the code to this file instead of stdout")
    a = p.parse_args(fixed)
    {"generate": generate, "check": check, "figma-script": figma_script}[cmd](a)


if __name__ == "__main__":
    main(sys.argv[1:])
