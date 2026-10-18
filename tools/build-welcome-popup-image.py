#!/usr/bin/env python3
"""Prepare the welcome pop-up image — WITHOUT altering the artwork.

Ο κανόνας του ιδιοκτήτη: η εικόνα χρησιμοποιείται ΟΠΩΣ στάλθηκε, χωρίς καμία επέμβαση.
(Η 1η έκδοση του artwork έλεγε «Μάθετσ» και διορθώθηκε τότε σε 16×17 px με το
tools/fix-cta-typo.py· η Κατερίνα ξαναδημιούργησε την εικόνα με σωστό «Μάθετε», οπότε τώρα
δεν χρειάζεται ΚΑΜΙΑ επέμβαση — το εργαλείο μένει μόνο ως καταγεγραμμένη δυνατότητα.)

Αυτό το script:
  1. αντιγράφει το πρωτότυπο ΑΥΤΟΥΣΙΟ στο artwork-src/ και ελέγχει το sha256,
  2. ΑΠΟΔΕΙΚΝΥΕΙ ότι το deployed JPEG είναι byte-identical με αυτό (κανένα patch),
  3. γράφει AVIF/WebP ΙΔΙΩΝ διαστάσεων (χωρίς resize) με PSNR ≥ 45 dB έναντι του master.

Χρήση: ~/.venvs/img/bin/python tools/build-welcome-popup-image.py
"""
import hashlib
import math
import os
import shutil

from PIL import Image, ImageChops

ROOT = os.path.expanduser("~/tsiga-speech-therapy-v2")
SRC = "/home/azureadmin/.hermes/images/dashboard_20260919_163521_e064133d_Gemini_Generated_Image_4qtahm4qtahm4qta.jpg"
KEEP = os.path.join(ROOT, "artwork-src", "katerina-welcome-original.jpg")
OUT = os.path.join(ROOT, "images", "katerina-welcome.jpg")
NAME = "katerina-welcome"

os.makedirs(os.path.dirname(KEEP), exist_ok=True)
if not (os.path.exists(KEEP) and
        hashlib.sha256(open(KEEP, "rb").read()).hexdigest() ==
        hashlib.sha256(open(SRC, "rb").read()).hexdigest()):
    shutil.copyfile(SRC, KEEP)          # νέα έκδοση artwork → αντικαθιστά την παλιά
src_sha = hashlib.sha256(open(SRC, "rb").read()).hexdigest()
keep_sha = hashlib.sha256(open(KEEP, "rb").read()).hexdigest()
if not os.path.exists(OUT) or hashlib.sha256(open(OUT, "rb").read()).hexdigest() != src_sha:
    shutil.copyfile(SRC, OUT)           # deployed = το αρχικό αρχείο, byte-identical
out_sha = hashlib.sha256(open(OUT, "rb").read()).hexdigest()

print(f"πρωτότυπο (αυτούσιο στο artwork-src/): {keep_sha[:16]}")
print(f"deployed images/{NAME}.jpg          : {out_sha[:16]}")
assert keep_sha == src_sha, "το φυλαγμένο πρωτότυπο ΔΕΝ είναι το αρχικό αρχείο!"
assert out_sha == src_sha, "το deployed αρχείο ΔΕΝ είναι το αρχικό αρχείο!"
orig = Image.open(OUT).convert("RGB")
W, H = orig.size
print(f"✓ byte-identical με το αρχείο που έστειλε η Κατερίνα — ΚΑΜΙΑ επέμβαση "
      f"({os.path.getsize(OUT)//1024} KB, {W}×{H})")


def psnr(pa, pb):
    h = ImageChops.difference(pa, pb).convert("L").histogram()
    mse = sum(i * i * n for i, n in enumerate(h)) / sum(h)
    return float("inf") if mse == 0 else 10 * math.log10(255.0 ** 2 / mse)


MIN_PSNR = 45.0
print("\nπαράγωγα (ίδια pixel & διαστάσεις, μικρότερο αρχείο):")
for ext, kw in (("webp", dict(quality=92, method=6)), ("avif", dict(quality=80))):
    path = os.path.join(ROOT, "images", f"{NAME}.{ext}")
    try:
        orig.save(path, **kw)
    except Exception as e:
        print(f"  {NAME}.{ext} skipped ({e})")
        continue
    chk = Image.open(path).convert("RGB")
    assert chk.size == (W, H), f"άλλαξαν διαστάσεις: {chk.size}"
    p = psnr(orig, chk)
    kb = os.path.getsize(path) // 1024
    ok = p >= MIN_PSNR
    print(f"  {NAME}.{ext:4s} {kb:5d} KB   PSNR {p:5.2f} dB   {'OK' if ok else 'ΑΠΟΡΡΙΨΗ'}")
    if not ok:
        os.remove(path)
print(f"\nόριο PSNR ≥ {MIN_PSNR} dB — πάνω από ~45 dB η διαφορά δεν είναι ορατή με μάτι.")
print("Το JPEG είναι το <img src> fallback και είναι το ΑΥΤΟΥΣΙΟ αρχείο της Κατερίνας.")

# ---------------------------------------------------------------- RESPONSIVE ΠΑΡΑΛΛΑΓΕΣ
# ΓΙΑΤΙ ΥΠΑΡΧΕΙ ΑΥΤΟ. Το PageSpeed/Lighthouse έδειξε LCP κινητού **4,5s** στο staging (όριο 2,5s)
# ενώ το live ήταν 2,3s: η αιτία ήταν ότι η εικόνα σερνόταν σε ΟΛΕΣ τις συσκευές ως ένα αρχείο
# 225KB, ενώ στο κινητό εμφανίζεται ~366px πλάτος (και το lcp-discovery ήταν OK — πρόβλημα
# ΜΕΓΕΘΟΥΣ, όχι ανακάλυψης). Εδώ βγαίνουν μικρότερες παραλλαγές + srcset/sizes στο HTML.
# ΤΟ ΑΥΤΟΥΣΙΟ JPEG ΔΕΝ ΑΓΓΙΖΕΤΑΙ: μένει byte-identical και μπαίνει στο srcset ως η μεγαλύτερη
# (2528w) επιλογή, ώστε να μη χάνεται κανένα pixel όταν χρειάζεται.
RESPONSIVE_W = [760, 1200, 1700]      # 760 -> κινητό (366px @2x), 1200/1700 -> desktop
print("\nresponsive παραλλαγές (ίδια εικόνα, μικρότερο αρχείο για μικρές οθόνες):")
for w in RESPONSIVE_W:
    h = round(H * w / W)
    small = orig.resize((w, h), Image.LANCZOS)
    for ext, kw in (("avif", dict(format="AVIF", quality=80)),
                    ("webp", dict(format="WEBP", quality=92, method=6)),
                    ("jpg", dict(format="JPEG", quality=86, optimize=True, progressive=True))):
        p = os.path.join(ROOT, "images", f"{NAME}-{w}.{ext}")
        small.save(p, **kw)
        print(f"  {NAME}-{w}.{ext:4s} {os.path.getsize(p)//1024:5d} KB  ({w}×{h})")
print(f"  {NAME}.avif    (native) {os.path.getsize(os.path.join(ROOT,'images',NAME+'.avif'))//1024:5d} KB  ({W}×{H})")
print(f"  {NAME}.jpg     (native, ΑΥΤΟΥΣΙΟ fallback) {os.path.getsize(OUT)//1024:5d} KB")
