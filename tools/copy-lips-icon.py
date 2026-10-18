#!/usr/bin/env python3
"""Αντιγράφει ΑΥΤΟΥΣΙΟ το glyph των χειλιών από το artwork, με διαφάνεια.

ΓΙΑΤΙ ΕΤΣΙ. «Δεν μπορείς να το αντιγράψεις;» — ναι, και είναι καλύτερο από SVG: ίδιο πάχος,
ίδια καμπύλη, ίδιο anti-aliasing, γιατί είναι ΤΑ ΙΔΙΑ pixel. Το glyph ζει πάνω σε ροδαλό δίσκο,
οπότε δεν αρκεί ένα ορθογώνιο crop (θα φαινόταν τετράγωνο μέσα στον κύκλο του hero). Αντί γι'
αυτό βγαίνει **alpha από τη μελάνη**: για κάθε pixel,
    alpha = (φωτεινότητα_δίσκου - φωτεινότητα) / (φωτεινότητα_δίσκου - φωτεινότητα_μελάνης)
και χρώμα = το χρώμα της μελάνης. Έτσι η κάλυψη (anti-aliasing) του πρωτότυπου διατηρείται
ακριβώς, και το αποτέλεσμα κάθεται καθαρά πάνω σε ΟΠΟΙΟ χρώμα badge θέλει το CSS.

Ανάλυση: το glyph είναι ~63x32px στο artwork — δηλαδή στα 32px εμφάνισης το 2x (64px) είναι
σχεδόν NATIVE. Δεν ανεβάζουμε τίποτα· εξάγουμε 1x και 2x.
"""
import os
import numpy as np
from PIL import Image

SRC = "images/katerina-welcome.jpg"
OUT = "images"
# Δίσκος: x 1218-1300, y 1418-1500 (μετρημένο με πλέγμα, tools/locate-lips-icon.py)
DISC = (1218, 1418, 1300, 1500)


def main() -> None:
    im = Image.open(SRC).convert("RGB")
    disc = im.crop(DISC)
    a = np.asarray(disc).astype(float)
    lum = a.mean(axis=2)

    # φόντο του δίσκου: το φωτεινό 85% (η μελάνη είναι σκούρα και λίγη)
    bg_lum = float(np.percentile(lum, 85))
    ink_lum = float(np.percentile(lum, 1))
    # χρώμα μελάνης = μέσος όρος του σκουρότερου 2%
    ink_rgb = a[lum <= np.percentile(lum, 2)].mean(axis=0)
    print(f"δίσκος φωτεινότητα: bg {bg_lum:.1f}  ink {ink_lum:.1f}  |  ink rgb {np.round(ink_rgb).astype(int)}")

    # ΚΑΤΩΦΛΙ: ο δίσκος δεν έχει απόλυτα ομοιόμορφο φόντο (νερόχρωμα/κόκκος), οπότε ένα
    # αυστηρό (bg - lum)/(bg - ink) αφήνει υπόλειμμα λίγων μονάδων σε ΟΛΟ το crop -> ορατό
    # αχνό ορθογώνιο μέσα στον κύκλο του hero. Αφαιρούμε το υπόλειμμα: ό,τι είναι πιο κοντά
    # στο φόντο από FLOOR μονάδες γίνεται πλήρως διαφανές. Το glyph έχει διαφορά ~164 μονάδες,
    # άρα το FLOOR=10 δεν το αγγίζει.
    FLOOR = 10.0
    alpha = np.clip(((bg_lum - lum) - FLOOR) / (bg_lum - ink_lum - FLOOR), 0.0, 1.0)
    print(f"alpha: {100 * (alpha > 0.02).mean():.1f}% των pixel ενεργά (πριν το κατώφλι ήταν περισσότερα)")
    # --- bbox της μελάνης, για tight crop ---
    strong = alpha > 0.25
    ys, xs = np.where(strong)
    if len(xs) == 0:
        raise SystemExit("δεν βρέθηκε μελάνη — δες το DISC")
    bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max()
    print(f"glyph bbox μέσα στον δίσκο: x {bx0}..{bx1}  y {by0}..{by1}  ({bx1-bx0+1}x{by1-by0+1})")
    # περιθώριο 3px ώστε να μη κόβεται ο anti-aliased κύκλος των άκρων
    m = 3
    sl = (slice(max(0, by0 - m), by1 + 1 + m), slice(max(0, bx0 - m), bx1 + 1 + m))
    al = alpha[sl]
    gw, gh = al.shape[1], al.shape[0]
    print(f"crop με περιθώριο: {gw}x{gh}px (native)")

    # RGBA: χρώμα μελάνης + το alpha της κάλυψης
    rgba = np.zeros((gh, gw, 4), dtype=np.uint8)
    rgba[:, :, 0], rgba[:, :, 1], rgba[:, :, 2] = [int(round(v)) for v in ink_rgb]
    rgba[:, :, 3] = np.round(al * 255).astype(np.uint8)
    master = Image.fromarray(rgba, "RGBA")

    os.makedirs("artwork-src", exist_ok=True)
    master.save("artwork-src/icon-lips-master.png")
    print(f"master (native, διαφάνεια): artwork-src/icon-lips-master.png  {gw}x{gh}")

    # 2x = native (64px πλάτος ζητάμε), 1x = μισό. Καμία αύξηση.
    for w in (60, 30):          # 30px εμφάνιση (οπτικό βάρος σαν τα γειτονικά) + 2x
        h = max(1, round(gh * w / gw))
        out = master.resize((w, h), Image.LANCZOS)
        for ext, kw in (("webp", dict(quality=95, method=6)), ("png", dict(optimize=True))):
            p = f"{OUT}/icon-lips-{w}.{ext}"
            out.save(p, **kw)
            print(f"  {p:32} {os.path.getsize(p):>6,} B  ({w}x{h})")


if __name__ == "__main__":
    main()
