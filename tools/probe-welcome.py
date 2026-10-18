#!/usr/bin/env python3
"""Targeted probes on the welcome artwork.

1. Local-contrast mask (pixel vs 51px median) -> exact bboxes of the baked TEXT/ICON
   clusters that HTML must replace. Works because those sit on smooth, flat background.
2. Horizontal scanline through the card: prints the paper->card transition so the card's
   edges can be read off a table instead of guessed from a low-contrast blob detector.
3. Vertical scanline through the card centre for the top/bottom edges.
"""
from PIL import Image, ImageFilter

SRC = "/home/azureadmin/.hermes/images/dashboard_20260919_130014_a2bfcca0_Gemini_Generated_Image_4qtahm4qtahm4qta.jpg"
im = Image.open(SRC).convert("RGB")
W, H = im.size
gray = im.convert("L")
bg = gray.filter(ImageFilter.MedianFilter(51))
gb, bb = gray.load(), bg.load()


def cluster(name, x0f, y0f, x1f, y1f, thr=14, pad=0.006):
    x0, y0, x1, y1 = int(x0f * W), int(y0f * H), int(x1f * W), int(y1f * H)
    xs, ys = [], []
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            if abs(gb[x, y] - bb[x, y]) > thr:
                xs.append(x); ys.append(y)
    if not xs:
        print(f"  {name:30s} (nothing above threshold {thr})"); return
    bx0, bx1 = min(xs) / W - pad, max(xs) / W + pad
    by0, by1 = min(ys) / H - pad, max(ys) / H + pad
    print(f"  {name:30s} x {bx0:.3f}–{bx1:.3f}  y {by0:.3f}–{by1:.3f}"
          f"   (px x{int(bx0*W)}–{int(bx1*W)} y{int(by0*H)}–{int(by1*H)})")


print("== baked clusters (local-contrast mask) ==")
cluster("bottom 4-icon row",   0.30, 0.83, 0.70, 0.97)
cluster("left handwritten note", 0.00, 0.78, 0.24, 0.95)
cluster("bottom-left heart squiggle", 0.05, 0.90, 0.16, 0.99)
cluster("right book/pencil stack", 0.78, 0.72, 1.00, 1.00)
cluster("sun disc",            0.84, 0.03, 0.95, 0.14)
cluster("bird",                0.09, 0.18, 0.17, 0.28)

print("\n== horizontal scanline y=0.40 (paper -> card -> paper) ==")
y = int(0.40 * H)
for f in [0.20, 0.24, 0.27, 0.29, 0.30, 0.31, 0.32, 0.34, 0.40, 0.50, 0.60, 0.66, 0.68, 0.69, 0.70, 0.72, 0.76]:
    c = im.getpixel((int(f * W), y))
    print(f"  x {f:.2f}  rgb({c[0]:3d},{c[1]:3d},{c[2]:3d})  #{c[0]:02x}{c[1]:02x}{c[2]:02x}  lum {int(0.299*c[0]+0.587*c[1]+0.114*c[2])}")

print("\n== vertical scanline x=0.35 (card top/bottom) ==")
x = int(0.35 * W)
for f in [0.06, 0.08, 0.09, 0.10, 0.11, 0.12, 0.14, 0.30, 0.50, 0.68, 0.70, 0.71, 0.72, 0.73, 0.74, 0.76, 0.80]:
    c = im.getpixel((x, int(f * H)))
    print(f"  y {f:.2f}  rgb({c[0]:3d},{c[1]:3d},{c[2]:3d})  #{c[0]:02x}{c[1]:02x}{c[2]:02x}  lum {int(0.299*c[0]+0.587*c[1]+0.114*c[2])}")

print("\n== card interior flatness (is it opaque or frosted?) ==")
for label, (fx, fy) in {
    "card left edge-in": (0.325, 0.30), "card mid": (0.42, 0.30),
    "card right edge-in": (0.66, 0.30), "paper far left": (0.22, 0.30),
    "paper above card": (0.50, 0.075), "paper below card": (0.50, 0.79),
    "card near bottom": (0.40, 0.70),
}.items():
    c = im.getpixel((int(fx * W), int(fy * H)))
    print(f"  {label:20s} #{c[0]:02x}{c[1]:02x}{c[2]:02x}  rgb({c[0]},{c[1]},{c[2]})")
