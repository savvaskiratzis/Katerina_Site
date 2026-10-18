#!/usr/bin/env python3
"""Numeric quality check of the cleaned welcome artwork.

"My eye says it looks fine" is not evidence, and a 2x zoom amplifies JPEG noise into
artefacts that are invisible at real size. So measure two things against a CONTROL region
of the same image that was never touched:

  streak   — std-dev of (pixel - 61x61 horizontal median). Vertical banding from a bad fill
             shows up as a higher streak score than the untouched control.
  step     — the biggest jump between neighbouring 8px column means inside the patch
             boundary band, i.e. a visible vertical seam.

Run: ~/.venvs/img/bin/python tools/check-welcome-assets.py
"""
import os
import statistics
from PIL import Image, ImageFilter

P = os.path.expanduser("~/tsiga-speech-therapy-v2/artwork-src/welcome-art-clean.png")
im = Image.open(P).convert("RGB")
W, H = im.size
gray = im.convert("L")
hmed = gray.filter(ImageFilter.MedianFilter(61))
g, m = gray.load(), hmed.load()
print(f"clean master {W}x{H}")


def streak(name, box, step=3):
    bx0, by0, bx1, by1 = (int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H))
    d = [abs(g[x, y] - m[x, y]) for y in range(by0, by1, step) for x in range(bx0, bx1, step)]
    print(f"  {name:34s} mean |dev| {statistics.mean(d):4.2f}   sd {statistics.pstdev(d):4.2f}")
    return statistics.pstdev(d)


print("== streak score (higher than the control = visible banding) ==")
control = streak("CONTROL (untouched paper, right)", (0.72, 0.30, 0.82, 0.44))
a = streak("patched: bottom 4-icon row", (0.325, 0.856, 0.672, 0.950))
b = streak("patched: left note", (0.028, 0.782, 0.232, 0.925))
print(f"  -> patched/control ratio: bottom {a/control:.2f}x, note {b/control:.2f}x  "
      f"(want <= ~1.5x)")

print("\n== seam check: 8px column means across each patch's left/right boundary ==")
for name, (ax0, ax1, yy0, yy1) in {
    "bottom row": (0.325, 0.672, 0.86, 0.95),
    "left note": (0.028, 0.232, 0.79, 0.92),
}.items():
    for edge, xs in (("left", ax0), ("right", ax1)):
        cols = [xs * W + k * 8 for k in range(-4, 5)]
        means = []
        for cx in cols:
            vals = [g[int(cx), y] for y in range(int(yy0 * H), int(yy1 * H), 4)]
            means.append(sum(vals) / len(vals))
        jumps = [abs(means[i + 1] - means[i]) for i in range(len(means) - 1)]
        print(f"  {name:11s} {edge:5s} boundary: max 8px-column jump {max(jumps):5.2f} levels "
              f"(a visible seam is > ~3)")

print("\n== is the card panel truly flat and equal to the CSS colour? ==")
px = im.load()
vals = [px[x, y] for y in range(int(0.12 * H), int(0.72 * H), 7) for x in range(int(0.33 * W), int(0.67 * W), 7)]
fr = [c[0] for c in vals]; fg = [c[1] for c in vals]; fb = [c[2] for c in vals]
print(f"  card region mean  #{sum(fr)//len(fr):02x}{sum(fg)//len(fg):02x}{sum(fb)//len(fb):02x}"
      f"   spread R {min(fr)}-{max(fr)}  G {min(fg)}-{max(fg)}  B {min(fb)}-{max(fb)}")

# ---------------------------------------------------------------------------------
# D. THE ONE THAT MATTERS: is the baked-in text actually GONE?
#    A smooth-but-still-there label (the bug that shipped in the first attempt) scores
#    perfectly on every smoothness metric. So measure STRUCTURE (local contrast), and
#    measure it against the original artwork in the same box.
# ---------------------------------------------------------------------------------
print("\n== D. removal check: structure left in the patched boxes (vs the original) ==")
orig = Image.open("/home/azureadmin/.hermes/images/dashboard_20260919_130014_a2bfcca0_Gemini_Generated_Image_4qtahm4qtahm4qta.jpg").convert("RGB")


def structure(img, box, thr=12):
    """% of pixels whose local contrast exceeds thr — i.e. visible glyph/icon structure."""
    bx0, by0, bx1, by1 = (int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H))
    sub = img.crop((bx0, by0, bx1, by1)).convert("L")
    med = sub.filter(ImageFilter.MedianFilter(31))
    p, q = sub.load(), med.load()
    hits = tot = 0
    for y in range(0, sub.size[1], 2):
        for x in range(0, sub.size[0], 2):
            tot += 1
            if abs(p[x, y] - q[x, y]) > thr:
                hits += 1
    return 100.0 * hits / max(1, tot)


REGIONS = {
    "bottom 4-icon row (baked icons+labels)": (0.333, 0.858, 0.665, 0.948),
    "left handwritten note": (0.030, 0.784, 0.228, 0.922),
    "CONTROL: untouched paper (right)": (0.72, 0.30, 0.82, 0.44),
    "CONTROL: untouched hills (left)": (0.02, 0.60, 0.14, 0.74),
}
bad = 0
for name, box in REGIONS.items():
    o, c = structure(orig, box), structure(im, box)
    control = "  <- CONTROL" if name.startswith("CONTROL") else ""
    verdict = ""
    if not name.startswith("CONTROL"):
        ctrl = structure(im, REGIONS["CONTROL: untouched paper (right)"])
        ok = c <= max(1.0, ctrl * 3)
        verdict = "  ✓ σβήστηκε" if ok else "  ✗ ΥΠΑΡΧΕΙ ΑΚΟΜΑ ΔΟΜΗ"
        if not ok:
            bad += 1
    print(f"  {name:40s} original {o:5.2f}%  cleaned {c:5.2f}%{verdict}{control}")

if bad:
    raise SystemExit(f"\n✗ {bad} περιοχή/-ές κρατούν ακόμη δομή — το baked κείμενο ΔΕΝ έφυγε.")
print("\n✓ Καμία υπολειμματική δομή στις περιοχές που καθαρίστηκαν.")
