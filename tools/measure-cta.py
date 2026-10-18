#!/usr/bin/env python3
"""Locate the baked "Μάθετε περισσότερα" button inside the ORIGINAL artwork, precisely.

The owner wants the image used EXACTLY as sent, with that painted button actually clickable.
So the button cannot be re-drawn — an invisible HTML hit area must be positioned over it. That
needs its true bounding box, measured from the pixels.

The first probe over `bbox_of(BTN, d=22)` returned the search window's own edges (0.351–0.648):
a tolerance of 22 matched the muted background too, so the result was the window, not the
button. This version scans a narrow band, requires a LONG contiguous run per row (a button is
~460px wide, the background never is), and reports the per-row run so the shape is visible.

Run: ~/.venvs/img/bin/python tools/measure-cta.py
"""
import os
import sys
import statistics

from PIL import Image

SRC = sys.argv[1] if len(sys.argv) > 1 else "/home/azureadmin/.hermes/images/dashboard_20260919_130014_a2bfcca0_Gemini_Generated_Image_4qtahm4qtahm4qta.jpg"
im = Image.open(SRC).convert("RGB")
W, H = im.size
print(f"original {W}x{H}")

# sample the button's own fill first, from a point clearly inside it
BTN_PX = im.getpixel((int(0.46 * W), int(0.575 * H)))
print(f"button fill sampled at (0.46, 0.575) -> #{BTN_PX[0]:02x}{BTN_PX[1]:02x}{BTN_PX[2]:02x}")


def near(c, ref, d):
    return abs(c[0] - ref[0]) <= d and abs(c[1] - ref[1]) <= d and abs(c[2] - ref[2]) <= d


TOL = 26
print("\n== rows with a long contiguous run of button fill ==")
rows = {}
for y in range(int(0.50 * H), int(0.65 * H), 2):
    best = run = 0
    bs = 0
    for x in range(int(0.30 * W), int(0.72 * W)):
        if near(im.getpixel((x, y)), BTN_PX, TOL):
            if run == 0:
                bs = x
            run += 1
            best = max(best, run)
        else:
            run = 0
    if best > 0.10 * W:                       # a button row: >10% of the width
        rows[y] = (best, bs, bs + best)
        print(f"  y {y/W*0+ y/H:.4f}  run {best}px  x {bs/W:.4f}-{(bs+best)/W:.4f}")

if rows:
    ys = list(rows)
    xs0 = [rows[y][1] for y in ys]
    xs1 = [rows[y][2] for y in ys]
    bx0, bx1 = min(xs0) / W, max(xs1) / W
    by0, by1 = min(ys) / H, max(ys) / H
    print(f"\nBUTTON bbox  x {bx0:.4f}–{bx1:.4f}   y {by0:.4f}–{by1:.4f}"
          f"   (w {bx1-bx0:.4f}  h {by1-by0:.4f})")
    print(f"  px: x {int(bx0*W)}–{int(bx1*W)}  y {int(by0*H)}–{int(by1*H)}")
    print("\nfor the CSS (percentages of the displayed image):")
    print(f"  left: {bx0*100:.2f}%;  top: {by0*100:.2f}%;  width: {(bx1-bx0)*100:.2f}%;  height: {(by1-by0)*100:.2f}%;")
    # sanity: is the box centred, as it looks in the image?
    print(f"  centre x {100*(bx0+bx1)/2:.2f}% (the artwork is centred, so ~50% is expected)")
else:
    print("  nothing found — widen TOL or the scan band")
