#!/usr/bin/env python3
"""Final palette + WCAG contrast audit for the new light theme.

Samples the remaining accent colours from the artwork (pale icon circles, terracotta leaves)
and computes contrast ratios for every text/background pair the CSS will actually use, so the
choice of ink/sage shades is evidence, not taste.
"""


def srgb(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lum(hexs):
    h = hexs.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b)


def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


try:
    from PIL import Image
    SRC = "/home/azureadmin/.hermes/images/dashboard_20260919_130014_a2bfcca0_Gemini_Generated_Image_4qtahm4qtahm4qta.jpg"
    im = Image.open(SRC).convert("RGB")
    W, H = im.size

    def sample(name, fx, fy, k=6):
        vals = [im.getpixel((int(fx * W) + dx, int(fy * H) + dy))
                for dx in range(-k, k + 1) for dy in range(-k, k + 1)]
        m = tuple(sum(v[i] for v in vals) // len(vals) for i in range(3))
        print(f"  {name:28s} #{m[0]:02x}{m[1]:02x}{m[2]:02x}")
        return f"#{m[0]:02x}{m[1]:02x}{m[2]:02x}"

    print("== accents sampled from the artwork ==")
    circle = sample("icon circle fill", 0.3635, 0.869)     # just above the glyph
    sample("icon circle fill 2", 0.4515, 0.869)
    leaf = sample("sage leaf (light)", 0.118, 0.140)
    sample("sage leaf (dark)", 0.108, 0.205)
    terra = sample("terracotta leaf", 0.352, 0.020)
    sample("pale petals", 0.145, 0.240)
    hill = sample("sage hill band", 0.30, 0.815)
    sample("deep cream wave", 0.90, 0.86)
except Exception as e:
    print("(sampling skipped:", e, ")")

print("\n== WCAG contrast audit (the pairs the CSS will use) ==")
PAPER, PAPER2, WHITE = "#fdf4ec", "#faede3", "#fffdf9"
INK, INK_SOFT, INK_MUTED = "#3b3a33", "#4a4b43", "#5f5f56"
SAGE, SAGE_DARK = "#757c6d", "#5f6656"
TERRA = "#c98a71"
pairs = [
    ("body ink on paper", INK, PAPER),
    ("body ink on card white", INK, WHITE),
    ("soft ink on paper", INK_SOFT, PAPER),
    ("muted ink on paper", INK_MUTED, PAPER),
    ("muted ink on card white", INK_MUTED, WHITE),
    ("sage text on paper (links)", SAGE_DARK, PAPER),
    ("sage as fill, white label on it", "#ffffff", SAGE),
    ("sage-dark fill, white label", "#ffffff", SAGE_DARK),
    ("sage as fill, ink label on it", INK, SAGE),
    ("terracotta text on paper", TERRA, PAPER),
    ("terracotta on card white", TERRA, WHITE),
]
for name, fg, bg in pairs:
    r = ratio(fg, bg)
    tag = "AAA" if r >= 7 else ("AA" if r >= 4.5 else ("AA-large" if r >= 3 else "FAIL"))
    print(f"  {name:34s} {fg:>8s} on {bg:>8s}  {r:5.2f}:1  {tag}")
