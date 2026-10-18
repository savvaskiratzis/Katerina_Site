#!/usr/bin/env python3
"""Measure the welcome artwork precisely: card bbox + corner radius, button bbox,
and the bounding boxes of every baked-in text/icon cluster that must be MASKED
(via local clone-stamping) so real HTML can take their place.

Everything is reported in canvas fractions so the rebuild is resolution-independent.
"""
from PIL import Image, ImageFilter

SRC = "/home/azureadmin/.hermes/images/dashboard_20260919_130014_a2bfcca0_Gemini_Generated_Image_4qtahm4qtahm4qta.jpg"
im = Image.open(SRC).convert("RGB")
W, H = im.size
px = im.load()
CARD = (253, 243, 234)          # sampled card fill
BTN = (117, 124, 109)           # sampled button fill


def near(c, ref, d=7):
    return abs(c[0] - ref[0]) <= d and abs(c[1] - ref[1]) <= d and abs(c[2] - ref[2]) <= d


def bbox_of(ref, d=7, min_run=0.05, search=None):
    """Rows/cols where a long run of `ref`-like pixels exists -> bbox in fractions."""
    x0f, y0f, x1f, y1f = search or (0.0, 0.0, 1.0, 1.0)
    x0, x1 = int(x0f * W), int(x1f * W)
    y0, y1 = int(y0f * H), int(y1f * H)
    span = x1 - x0
    rows, cols = [], []
    for y in range(y0, y1, 2):
        run = best = 0
        for x in range(x0, x1, 2):
            run = run + 1 if near(px[x, y], ref, d) else 0
            best = max(best, run)
        if best > min_run * span / 2:
            rows.append(y)
    if not rows:
        return None
    ys = range(min(rows), max(rows) + 1, 2)
    for x in range(x0, x1, 2):
        run = best = 0
        for y in ys:
            run = run + 1 if near(px[x, y], ref, d) else 0
            best = max(best, run)
        if best > min_run * (max(rows) - min(rows)):
            cols.append(x)
    return (min(cols) / W, min(rows) / H, max(cols) / W, max(rows) / H)


print("== GEOMETRY (canvas fractions) ==")
card = bbox_of(CARD, 7, 0.25)
print(f"card bbox      x {card[0]:.3f}–{card[2]:.3f}  y {card[1]:.3f}–{card[3]:.3f}"
      f"   -> w {card[2]-card[0]:.3f} h {card[3]-card[1]:.3f}")
btn = bbox_of(BTN, 22, 0.02, search=(0.35, 0.50, 0.65, 0.65))
print(f"button bbox    x {btn[0]:.3f}–{btn[2]:.3f}  y {btn[1]:.3f}–{btn[3]:.3f}"
      f"   -> w {btn[2]-btn[0]:.3f} h {btn[3]-btn[1]:.3f}")

# corner radius of the card: along the card's top row, how far in does the fill start?
cx0, cy0 = int(card[0] * W), int(card[1] * H)
top = cy0 + 3
first = next(x for x in range(cx0 - 40, cx0 + 200) if near(px[x, top], CARD, 10))
print(f"card corner: fill starts {first - cx0}px inside the bbox at the top edge "
      f"-> radius ~{100*(first-cx0)/W:.2f}% of width (~{((first-cx0)/W)*100:.1f}vw at 16:10)")

# darkest-pixel colour of a text cluster (glyph colour, robust to antialiasing)
def ink(name, x0f, y0f, x1f, y1f, pct=0.03):
    box = (int(x0f * W), int(y0f * H), int(x1f * W), int(y1f * H))
    data = list(im.crop(box).getdata())
    data.sort(key=lambda c: c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114)
    take = max(1, int(len(data) * pct))
    sel = data[:take]
    m = tuple(sum(c[i] for c in sel) // len(sel) for i in range(3))
    print(f"  {name:22s} #{m[0]:02x}{m[1]:02x}{m[2]:02x}")


print("\n== INK (darkest 3% of each cluster) ==")
ink("name", 0.36, 0.16, 0.64, 0.21)
ink("tagline", 0.35, 0.23, 0.65, 0.27)
ink("quote", 0.36, 0.34, 0.64, 0.43)
ink("body line", 0.36, 0.44, 0.64, 0.51)
ink("pill line", 0.36, 0.51, 0.64, 0.55)
ink("feature labels", 0.33, 0.66, 0.67, 0.72)
ink("bottom labels", 0.28, 0.91, 0.72, 0.96)
ink("left note", 0.02, 0.79, 0.20, 0.92)

print("\n== MASK CLUSTERS to cover with HTML (bboxes for clone-stamping) ==")
for name, bb in [
    ("the 3 feature icons+lil text", (0.33, 0.63, 0.67, 0.73)),
    ("bottom icon row (4 icons+labels)", (0.27, 0.83, 0.73, 0.97)),
    ("left handwritten note", (0.015, 0.78, 0.20, 0.94)),
]:
    print(f"  {name:32s} x {bb[0]:.3f}–{bb[2]:.3f}  y {bb[1]:.3f}–{bb[3]:.3f}")

print("\n== aspect check ==")
print(f"  {W}x{H} -> {W/H:.3f} (3:2 = 1.5). For a 100vh hero on 16:9 desktop, cover-crop keeps "
      f"{100*(16/9)/(W/H):.0f}% of the width.")
