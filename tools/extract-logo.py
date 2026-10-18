#!/usr/bin/env python3
"""Εξάγει τον κύκλο του λογοτύπου από τη νέα εικόνα + μετράει το nav (prod vs v2).

Ο κύκλος είναι sage (#7d8977-ish) πάνω σε κρεμ φόντο — μεγάλη αντίθεση, άρα μια μάσκα χρώματος
δουλεύει εδώ (σε αντίθεση με το εικονίδιο των χειλιών, όπου χρειάστηκε πλέγμα).
"""
import numpy as np
from PIL import Image

SRC = "/home/azureadmin/.hermes/images/dashboard_20260919_185245_b57e0cd6_Gemini_Generated_Image_9su0pa9su0pa9su0.jpg"
OUT = "images"

im = Image.open(SRC).convert("RGB")
W, H = im.size
a = np.asarray(im).astype(int)

# Απόσταση από το sage του κύκλου. Ο απλός κανόνας «G>=R-6 και σκούρο» έπιασε και τη βινιέτα του
# φόντου (bbox 1916x1077, άκυρο). Εδώ: απόσταση από το μετρημένο sage + ΠΡΟΦΙΛ ΠΥΚΝΟΤΗΤΑΣ, γιατί
# ο κύκλος είναι η μόνη περιοχή όπου το χρώμα εμφανίζεται σε συνεχόμενες στήλες/γραμμές.
TARGET = np.array([125, 137, 119])
dist = np.sqrt(((a - TARGET) ** 2).sum(axis=2))
mask = dist < 30
rows, cols = mask.sum(axis=1), mask.sum(axis=0)
dense_rows = np.where(rows > 0.35 * rows.max())[0]
dense_cols = np.where(cols > 0.35 * cols.max())[0]
print(f"εικόνα {W}x{H} | pixels κοντά στο sage: {int(mask.sum())} ({100*mask.sum()/(W*H):.1f}%)")
x0, x1 = int(dense_cols[0]), int(dense_cols[-1])
y0, y1 = int(dense_rows[0]), int(dense_rows[-1])
w, h = x1 - x0 + 1, y1 - y0 + 1
print(f"bbox κύκλου: x {x0}..{x1}  y {y0}..{y1}  ->  {w}x{h}")
print(f"κέντρο: ({x0 + w//2}, {y0 + h//2})  |  διαφορά πλευρών: {abs(w - h)}px "
      f"({'τετράγωνος' if abs(w-h) <= 8 else 'ΟΧΙ τετράγωνος — δες το με πλέγμα'})")
# χρώμα: μέσος όρος του πυρήνα (να μην πιάσει τις λευκές γραμμές)
cy, cx = y0 + h // 2, x0 + w // 2
core = a[cy - 8:cy + 8, cx - h//4:cx - h//4 + 10].reshape(-1, 3).mean(axis=0)
print("χρώμα κύκλου (δείγμα):", np.round(core).astype(int))

# crop τετράγωνο, με 6px αέρα (ο anti-aliased κύκλος), και έξοδος
# -2px: κόβουμε ΛΙΓΟ ΜΕΣΑ στον κύκλο, ώστε το εξωτερικό pixel να είναι sage και όχι κρεμ
# (το badge έχει border-radius 50%· μια κρεμ λουρίδα 0.4px θα φαινόταν σαν δαχτυλίδι).
half = max(w, h) // 2 - 2
box = (x0 + w // 2 - half, y0 + h // 2 - half, x0 + w // 2 + half, y0 + h // 2 + half)
print("τετράγωνο crop:", box, "->", box[2] - box[0], "px")
master = im.crop(box)
master.save("artwork-src/logo-kt-master.png")
print(f"master: artwork-src/logo-kt-master.png {master.width}x{master.height}")

import os
for size in (100, 50):   # 50px = το .logo-icon, 100 = 2x
    out = master.resize((size, size), Image.LANCZOS)
    for ext, kw in (("webp", dict(quality=92, method=6)), ("png", dict(optimize=True))):
        p = f"{OUT}/logo-kt-{size}.{ext}"
        out.save(p, **kw)
        print(f"  {p:28} {os.path.getsize(p):>7,} B  ({size}x{size})")
