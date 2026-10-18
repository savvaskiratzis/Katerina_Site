#!/usr/bin/env python3
"""Εντοπίζει ΑΚΡΙΒΩΣ τον δίσκο του εικονιδίου των χειλιών, με πλέγμα συντεταγμένων.

Ο δίσκος είναι λίγο πιο σκούρος/θερμότερος από το κρεμ φόντο (διαφορά λίγων μονάδων), γι' αυτό
το απλό threshold χρώματος απέτυχε. Εδώ:
  1) τυπώνεται το προφίλ φωτεινότητας ανά γραμμή/στήλη (ο δίσκος ξεχωρίζει ως τοπικό ελάχιστο),
  2) σώζεται το crop με πλέγμα ανά 10px για οπτική ανάγνωση.
"""
import numpy as np
from PIL import Image, ImageDraw

SRC = "images/katerina-welcome.jpg"
WIN = (1100, 1310, 1350, 1540)          # x0,y0,x1,y1 γύρω από τα χείλη

im = Image.open(SRC).convert("RGB")
x0, y0, x1, y1 = WIN
crop = im.crop(WIN)
a = np.asarray(crop).astype(float)
lum = a.mean(axis=2)

# Το φόντο είναι το φωτεινότερο· ο δίσκος τοπικά πιο σκούρος.
print(f"παράθυρο {WIN}  φωτεινότητα: min {lum.min():.0f}  max {lum.max():.0f}")
bg = np.median(lum)
print(f"διάμεσος (φόντο) = {bg:.1f}")
mask = lum < bg - 2.0
ys, xs = np.where(mask)
print(f"pixels πιο σκούρα από bg-2: {len(xs)}")
if len(xs):
    print(f"bbox: x {x0+xs.min()}..{x0+xs.max()}  y {y0+ys.min()}..{y0+ys.max()}"
          f"  ({xs.max()-xs.min()+1}x{ys.max()-ys.min()+1})")

# προφίλ: μέση φωτεινότητα ανά γραμμή και ανά στήλη (σε σχέση με το bg)
rows = lum.mean(axis=1) - bg
cols = lum.mean(axis=0) - bg
dark_rows = [i for i, v in enumerate(rows) if v < -1.0]
dark_cols = [i for i, v in enumerate(cols) if v < -1.0]
if dark_rows and dark_cols:
    print(f"από το προφίλ: y {y0+dark_rows[0]}..{y0+dark_rows[-1]}"
          f"  x {x0+dark_cols[0]}..{x0+dark_cols[-1]}"
          f"  -> {dark_cols[-1]-dark_cols[0]+1}x{dark_rows[-1]-dark_rows[0]+1}")

# πλέγμα ανά 10px, με ετικέτες ανά 50
vis = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS).convert("RGB")
d = ImageDraw.Draw(vis)
for gx in range(x0, x1, 10):
    px = (gx - x0) * 3
    col = (255, 0, 0) if (gx - x0) % 50 == 0 else (200, 200, 220)
    d.line([(px, 0), (px, vis.height)], fill=col, width=1)
    if (gx - x0) % 50 == 0:
        d.text((px + 2, 2), str(gx), fill=(255, 0, 0))
for gy in range(y0, y1, 10):
    py = (gy - y0) * 3
    col = (255, 0, 0) if (gy - y0) % 50 == 0 else (200, 200, 220)
    d.line([(0, py), (vis.width, py)], fill=col, width=1)
    if (gy - y0) % 50 == 0:
        d.text((2, py + 2), str(gy), fill=(255, 0, 0))
vis.save("/tmp/lips-grid.png")
print("πλέγμα -> /tmp/lips-grid.png  (3x, ετικέτες = συντεταγμένες στο artwork)")
