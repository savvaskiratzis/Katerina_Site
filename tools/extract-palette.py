#!/usr/bin/env python3
"""Extract the REAL palette from Katerina's welcome artwork + measure the card geometry.

No guessing: adaptive quantisation for the dominant palette, plus mean-colour sampling
of named regions (regions expressed in fractions of the canvas so they survive any resize).
"""
from PIL import Image

SRC = "/home/azureadmin/.hermes/images/dashboard_20260919_130014_a2bfcca0_Gemini_Generated_Image_4qtahm4qtahm4qta.jpg"
im = Image.open(SRC).convert("RGB")
W, H = im.size
print(f"canvas: {W}x{H}  ratio {W/H:.4f}   ({SRC.split('/')[-1]})")

# ---- 1. dominant palette (whole canvas) -------------------------------------
q = im.resize((W // 4, H // 4)).quantize(colors=14, method=Image.MEDIANCUT)
pal, counts = q.getpalette(), sorted(q.getcolors(), reverse=True)
total = sum(c for c, _ in counts)
print("\n== dominant palette (14 colours, % of canvas) ==")
for cnt, idx in counts:
    r, g, b = pal[idx * 3: idx * 3 + 3]
    print(f"  #{r:02x}{g:02x}{b:02x}  {100*cnt/total:5.1f}%   rgb({r},{g},{b})")


def region(name, x0, y0, x1, y1, note=""):
    """mean + median colour of a fractional region"""
    box = (int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))
    crop = im.crop(box)
    px = list(crop.getdata())
    n = len(px)
    mean = tuple(sum(c[i] for c in px) // n for i in range(3))
    med = tuple(sorted(c[i] for c in px)[n // 2] for i in range(3))
    print(f"  {name:26s} #{mean[0]:02x}{mean[1]:02x}{mean[2]:02x} (mean)  "
          f"#{med[0]:02x}{med[1]:02x}{med[2]:02x} (median)  {note}")
    return mean


# ---- 2. named element sampling (fractions read off the artwork) -------------
print("\n== element colours ==")
region("bg top-left paper",     0.02, 0.02, 0.06, 0.06)
region("bg mid hills",          0.46, 0.62, 0.52, 0.66, "sage hills, right of card")
region("bg bottom paper",       0.42, 0.93, 0.50, 0.97)
region("card surface",          0.30, 0.62, 0.34, 0.68, "the central card")
region("card surface (lower)",  0.44, 0.72, 0.52, 0.76)
region("name text",             0.395, 0.165, 0.41, 0.185, "'Κατερίνα Τσίγα'")
region("tagline text",          0.40, 0.235, 0.42, 0.25, "'ΛΟΓΟΘΕΡΑΠΕΥΤΡΙΑ'")
region("quote text",            0.42, 0.36, 0.44, 0.375, "script quote")
region("button fill",           0.44, 0.555, 0.47, 0.575, "'Μάθετε περισσότερα'")
region("button label",          0.435, 0.565, 0.445, 0.575, "text on button")
region("tree branch",           0.055, 0.22, 0.075, 0.24, "branch")
region("tree trunk",            0.065, 0.62, 0.085, 0.68, "trunk")
region("leaf sage",             0.115, 0.135, 0.135, 0.15, "grey-sage leaf")
region("leaf terracotta",       0.345, 0.015, 0.365, 0.035, "pink/terracotta leaf")
region("sun disc",              0.865, 0.075, 0.895, 0.095, "pale sun")
region("house wall",            0.845, 0.32, 0.87, 0.35, "house")
region("icon circle bg",        0.855, 0.855, 0.875, 0.875, "feature icon circle")

# ---- 3. card geometry: find the bright card against the cream paper ---------
print("\n== central card geometry (luminance threshold) ==")
small = im.resize((W // 6, H // 6))
sw, sh = small.size
sp = small.load()
row = int(sh * 0.55)                       # a row through the card
xs = [x for x in range(sw) if sum(sp[x, row]) / 3 > 246]
print(f"  card horizontal span at 55% height: {min(xs)/sw:.3f} – {max(xs)/sw:.3f} "
      f"(width {100*(max(xs)-min(xs))/sw:.1f}% of canvas)")
col = int(sw * 0.42)
ys = [y for y in range(sh) if sum(sp[col, y]) / 3 > 246]
print(f"  card vertical span at 42% width:   {min(ys)/sh:.3f} – {max(ys)/sh:.3f} "
      f"(height {100*(max(ys)-min(ys))/sh:.1f}% of canvas)")
print(f"  card centre: x {(min(xs)+max(xs))/2/sw:.3f}   y {(min(ys)+max(ys))/2/sh:.3f}")
