#!/usr/bin/env python3
"""Χτίζει το ΕΙΚΟΝΙΔΙΟ του λογοτύπου (σπίτι + χαμόγελο) με διαφανές φόντο.

Πηγή: ~/.hermes/images/dashboard_20261018_184046_4d5f70dd_Embracing_Family_House_Logo.png
       1254x1254, RGB, φόντο σχεδόν λευκό (254,253,250).

Το artwork είναι μόνο το σήμα (χωρίς κείμενο) — το «Κατερίνα Τσίγα / ΛΟΓΟΘΕΡΑΠΕΥΤΡΑ» μένει
ζωντανό κείμενο στο HTML (όπως πριν), ώστε να αλλάζει/μεταφράζεται χωρίς νέα εικόνα.

Alpha από το λευκό (un-premultiply), ώστε να μη «πλυθούν» τα απαλά ροζ/πράσινα άκρα:
  d = 254 - min(R,G,B);  d<=LO διαφανές, d>=HI αδιαφανές, ενδιάμεσα ramp.

Χρήση: python3 tools/build-logo-mark.py
"""
from PIL import Image

SRC = "/home/ubuntu/.hermes/images/dashboard_20261018_184046_4d5f70dd_Embracing_Family_House_Logo.png"
OUT = "images/logo-kt-house"
PAD = 0.03
WIDTHS = [96, 144, 192]      # η εμφάνιση είναι ~48px ύψος → 2x/3x/4x
WHITE = 254.0
LO, HI = 10.0, 45.0


def to_rgba(im):
    im = im.convert("RGB")
    w, h = im.size
    sp = im.load()
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dp = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b = sp[x, y]
            d = WHITE - min(r, g, b)
            if d <= LO:
                continue
            a = 1.0 if d >= HI else (d - LO) / (HI - LO)
            if a < 1.0:
                rr = (r - WHITE * (1 - a)) / a
                gg = (g - WHITE * (1 - a)) / a
                bb = (b - WHITE * (1 - a)) / a
                r, g, b = (max(0, min(255, round(v))) for v in (rr, gg, bb))
            dp[x, y] = (r, g, b, round(a * 255))
    return out


def main():
    rgba = to_rgba(Image.open(SRC))
    bbox = rgba.getbbox()
    if not bbox:
        raise SystemExit("άδεια εικόνα — δεν βρέθηκε μελάνι")
    x0, y0, x1, y1 = bbox
    cw, ch = x1 - x0, y1 - y0
    padx, pady = int(cw * PAD), int(ch * PAD)
    crop = (max(0, x0 - padx), max(0, y0 - pady),
            min(rgba.size[0], x1 + padx), min(rgba.size[1], y1 + pady))
    base = rgba.crop(crop)
    print(f"content bbox {bbox} -> crop {crop} {base.size} aspect {base.size[0]/base.size[1]:.3f}")

    for target_w in WIDTHS:
        target_h = round(target_w * base.size[1] / base.size[0])
        resized = base.resize((target_w, target_h), Image.LANCZOS)
        png, webp = f"{OUT}-{target_w}.png", f"{OUT}-{target_w}.webp"
        resized.save(png, optimize=True)
        resized.save(webp, quality=90, method=6)
        print(f"  {png}  {target_w}x{target_h}")


if __name__ == "__main__":
    main()
