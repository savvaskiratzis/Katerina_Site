#!/usr/bin/env python3
"""Διόρθωση ΤΥΠΟΓΡΑΦΙΚΟΥ ΛΑΘΟΥΣ στο κουμπί της εικόνας: «Μάθετσ» → «Μάθετε».

Το AI-generated artwork γράφει «Μάθετσ περισσότερα» — το τελευταίο γράμμα του ρήματος είναι
ΣΙΓΜΑ αντί για ΕΨΙΛΟΝ. Ο ιδιοκτήτης ζήτησε να διορθωθεί ΧΩΡΙΣ να πειραχτεί η εικόνα.

Λύση: δεν ζωγραφίζουμε νέο γράμμα με «ταιριαστή» γραμματοσειρά (θα ξεχώριζε αμέσως). Το σωστό
**ε** υπάρχει ήδη μέσα στην ίδια λέξη — στο «Μάθετ[ε]» — στην ΙΔΙΑ γραμματοσειρά, μέγεθος, θέση
και anti-aliasing. Αντιγράφουμε τα pixel του γράμματος από εκεί.

Η επέμβαση περιορίζεται σε ένα ορθογώνιο ~20×26 px μέσα σε κουμπί 442×75 px, και το εργαλείο
το ΑΠΟΔΕΙΚΝΥΕΙ: μετρά τα αλλαγμένα pixel και αποτυγχάνει αν έστω ένα βγει έξω από το δηλωμένο
ορθογώνιο. Το αρχικό αρχείο φυλάσσεται ΑΥΤΟΥΣΙΟ στο artwork-src/katerina-welcome-original.jpg.

Δύο παγίδες που κόστισαν επαναλήψεις (καταγεγραμμένες για την επόμενη φορά):
  1. Οριζόντιο προφίλ στηλών με «ένωσε ό,τι απέχει ≤7px» κόλλησε ΟΛΗ τη λέξη σε ένα κομμάτι:
     εδώ τα γράμματα απέχουν 1–3px και τα κενά λέξεων 9–12px — πολύ κοντά για ένα κατώφλι.
     Λύση: connected components + συγχώνευση μόνο ό,τι είναι καθέτως στοιβαγμένο (τόνοι, και
     το «σ» που σπάει σε δύο τόξα).
  2. Το φωτεινό χείλος της στρογγυλής άκρης του κουμπιού δίνει 4-7px «γράμματα» στο επάνω και
     κάτω άκρο της ζώνης. Χωρίς φίλτρο ύψους, οι δείκτες μετατοπίζονται και το εργαλείο
     «διόρθωνε» το σωστό γράμμα.

Χρήση: ~/.venvs/img/bin/python tools/fix-cta-typo.py [--dry-run]
"""
import hashlib
import os
import shutil
import sys

import numpy as np
from PIL import Image

ROOT = os.path.expanduser("~/tsiga-speech-therapy-v2")
SRC = "/home/azureadmin/.hermes/images/dashboard_20260919_130014_a2bfcca0_Gemini_Generated_Image_4qtahm4qtahm4qta.jpg"
KEEP = os.path.join(ROOT, "artwork-src", "katerina-welcome-original.jpg")
OUT = os.path.join(ROOT, "images", "katerina-welcome.jpg")
DRY = "--dry-run" in sys.argv

BTN = (1044, 933, 1486, 1008)             # το ζωγραφισμένο κουμπί (tools/measure-cta.py)
TEXT_BAND = (BTN[1] + 4, BTN[3] - 4)
MIN_GLYPH_H, MIN_GLYPH_W = 10, 6          # τα αληθινά γράμματα είναι ≥13px ψηλά

os.makedirs(os.path.dirname(KEEP), exist_ok=True)
if not os.path.exists(KEEP):
    shutil.copyfile(SRC, KEEP)
assert hashlib.sha256(open(SRC, "rb").read()).hexdigest() == \
       hashlib.sha256(open(KEEP, "rb").read()).hexdigest(), "το πρωτότυπο δεν είναι το αρχικό!"
print(f"πρωτότυπο (άθικτο): artwork-src/katerina-welcome-original.jpg  "
      f"sha256 {hashlib.sha256(open(KEEP, 'rb').read()).hexdigest()[:16]}")

im = Image.open(KEEP).convert("RGB")
px = np.asarray(im).astype(np.int16)

by0, by1 = TEXT_BAND
IX0, IX1 = BTN[0] + 10, BTN[2] - 10       # εσωτερικό, χωρίς τη στρογγυλή άκρη
bright = (px.min(axis=2) > 205)
mask = np.zeros_like(bright)
mask[by0:by1, IX0:IX1] = bright[by0:by1, IX0:IX1]


def components(mask):
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or seen[sy, sx]:
                continue
            stack, pts = [(sy, sx)], []
            seen[sy, sx] = True
            while stack:
                y, x = stack.pop()
                pts.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            ys = [p[0] for p in pts]
            xs = [p[1] for p in pts]
            out.append({"x0": min(xs), "y0": min(ys), "x1": max(xs) + 1, "y1": max(ys) + 1,
                        "n": len(pts), "pts": pts})
    return out


comps = [c for c in components(mask) if c["n"] >= 6]      # μόνο κόκκοι θορύβου έξω
comps.sort(key=lambda c: c["x0"])
print(f"\nσυνδεδεμένα κομμάτια: {len(comps)}")


def vstack(a, b):
    """Ίδιο γράμμα σε δύο κομμάτια; (τόνος από πάνω, ή το «σ» που σπάει σε δύο τόξα)"""
    ox = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
    return ox > 0.5 * min(a["x1"] - a["x0"], b["x1"] - b["x0"]) and abs(b["y0"] - a["y1"]) <= 4


# ΣΗΜΑΝΤΙΚΟ: η συγχώνευση γίνεται ΠΡΙΝ το φίλτρο ύψους. Με το φίλτρο πρώτα, το «σ» (δύο τόξα
# των ~7px, το μεσαίο τόξο δεν περνά το threshold του άσπρου) διαγραφόταν ως θόρυβος και ο
# δείκτης 5 έδειχνε το επόμενο γράμμα — δηλαδή το εργαλείο θα «διόρθωνε» το «π» της επόμενης λέξης.
merged = []
for c in comps:
    if merged and vstack(merged[-1], c):
        p = merged[-1]
        p["x0"], p["y0"] = min(p["x0"], c["x0"]), min(p["y0"], c["y0"])
        p["x1"], p["y1"] = max(p["x1"], c["x1"]), max(p["y1"], c["y1"])
        p["pts"] += c["pts"]
        p["n"] += c["n"]
    else:
        merged.append(dict(c))

merged = [c for c in merged
          if (c["y1"] - c["y0"]) >= MIN_GLYPH_H and (c["x1"] - c["x0"]) >= MIN_GLYPH_W]
print(f"γράμματα μετά τη συγχώνευση και το φίλτρο: {len(merged)}")

for i, c in enumerate(merged):
    print(f"  #{i:2d}  x {c['x0']:4d}–{c['x1']:4d}  y {c['y0']:4d}–{c['y1']:4d}"
          f"  (πλάτος {c['x1']-c['x0']:2d}, ύψος {c['y1']-c['y0']:2d})")

assert len(merged) >= 6, "δεν βρήκα τα γράμματα του κουμπιού — άλλαξαν οι συντεταγμένες;"
sig, eps = merged[5], merged[3]           # «Μάθετσ»: 6ο = λάθος σ, 4ο = σωστό ε
print(f"\nλάθος γράμμα (σ) : x {sig['x0']}–{sig['x1']}  y {sig['y0']}–{sig['y1']}")
print(f"πηγή σωστού ε   : x {eps['x0']}–{eps['x1']}  y {eps['y0']}–{eps['y1']}")

eps_pts = np.zeros_like(mask)
for y, x in eps["pts"]:
    eps_pts[y, x] = True

# --- 2. σβήσε το λάθος γράμμα και κόλλα τα pixel του σωστού ----------------------
PAD = 2
# ΜΟΝΟ το ορθογώνιο του ΛΑΘΟΣ γράμματος σβήνεται. Αν σβήναμε την ένωση με το «ε», θα
# εξαφανίζαμε και τα γράμματα ανάμεσά τους («Μάθετ[ε][τ][σ]» → το «τ» θα χανόταν, γιατί μόνο
# τα pixel του «ε» επανατοποθετούνται). Το πρώτο run είχε 794 αλλαγμένα pixel για 57
# αντιγραμμένα — αυτή η αναλογία ήταν η ένδειξη.
erase = (sig["x0"] - PAD, sig["y0"] - PAD, sig["x1"] + PAD, sig["y1"] + PAD)
ex0, ey0, ex1, ey1 = erase
print(f"\nορθογώνιο επέμβασης: {erase}  ({ex1-ex0}×{ey1-ey0} px)")


def fill_from_sides(arr, box):
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        left = arr[y, x0 - 1].astype(np.float32)
        right = arr[y, x1].astype(np.float32)
        t = np.linspace(0, 1, x1 - x0, dtype=np.float32)[:, None]
        arr[y, x0:x1] = (left[None, :] * (1 - t) + right[None, :] * t).round().astype(np.int16)


def ring_mean(arr, box, ring=2):
    x0, y0, x1, y1 = box
    ring_px = np.concatenate([arr[y0 - ring:y0, x0:x1].reshape(-1, 3),
                              arr[y1:y1 + ring, x0:x1].reshape(-1, 3)])
    return ring_px.mean(axis=0)


work = px.copy()
fill_from_sides(work, erase)

# τα pixel του ε: ίδιο ύψος βάσης, κεντραρισμένα στον x του λάθος γράμματος
src_bbox = (eps["x0"], eps["y0"], eps["x1"], eps["y1"])
dst_shift_x = ((sig["x0"] + sig["x1"]) - (eps["x0"] + eps["x1"])) // 2
dst_shift_y = (sig["y1"] - eps["y1"])                       # στοίχιση στη βάση του γράμματος
off = ring_mean(work, (sig["x0"] - 1, sig["y0"] - 1, sig["x1"] + 1, sig["y1"] + 1)) - \
      ring_mean(px, (eps["x0"] - 1, eps["y0"] - 1, eps["x1"] + 1, eps["y1"] + 1))
print(f"διόρθωση απόχρωσης κουμπιού: {off.round(1)}")

n_pts = 0
for y, x in eps["pts"]:
    dy, dx = y + dst_shift_y, x + dst_shift_x
    if 0 <= dy < px.shape[0] and 0 <= dx < px.shape[1]:
        work[dy, dx] = np.clip(px[y, x].astype(np.float32) + off, 0, 255).round().astype(np.int16)
        n_pts += 1
print(f"αντιγράφηκαν {n_pts} pixel του σωστού «ε»")

diff = (np.abs(work - px).max(axis=2) > 0)
ys, xs = np.where(diff)
if len(ys):
    print(f"\nάλλαξαν {len(ys)} pixel, εύρος x {xs.min()}–{xs.max()}, y {ys.min()}–{ys.max()}")
    outside = ((xs < ex0) | (xs >= ex1) | (ys < ey0) | (ys >= ey1)).sum()
    print(f"pixel ΕΞΩ από το δηλωμένο ορθογώνιο: {outside}")
    assert outside == 0, f"η επέμβαση ξέφυγε από το ορθογώνιο ({outside} pixel)!"
    print("✓ όλη η επέμβαση μέσα στο ορθογώνιο — έξω από αυτό το αρχείο είναι pixel-προς-pixel ίδιο")

out = Image.fromarray(work.astype(np.uint8))
if DRY:
    out.save("/tmp/cta-fixed-preview.png")
    print(f"\ndry-run: /tmp/cta-fixed-preview.png  (ορθογώνιο {erase})")
else:
    out.save(OUT, quality=98, subsampling=0, optimize=True)
    print(f"\nγράφτηκε {OUT}  ({os.path.getsize(OUT)//1024} KB)")
    # sidecar: το ορθογώνιο της επέμβασης, ώστε το build/verify να ΑΠΟΔΕΙΚΝΥΟΥΝ ότι καμία
    # άλλη διαφορά δεν υπάρχει — αντί να το «ξέρει» κάποιος από τα σχόλια.
    import json
    side = os.path.join(ROOT, "artwork-src", "cta-typo-patch.json")
    json.dump({"source_sha256": hashlib.sha256(open(KEEP, "rb").read()).hexdigest(),
               "rect": list(erase), "changed_pixels": int(len(ys)),
               "note": "«Μάθετσ» -> «Μάθετε»: το ε αντιγράφηκε από το 4ο γράμμα της ίδιας λέξης"},
              open(side, "w"), indent=2, ensure_ascii=False)
    print(f"γράφτηκε {side}")
