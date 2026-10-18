#!/usr/bin/env python3
"""Φτιάχνει την πορτραίτο έκδοση της φωτογραφίας του «Σχετικά με Εμένα» — ΑΥΤΟΜΑΤΑ.

ΤΟ ΠΡΟΒΛΗΜΑ. Ο ιδιοκτήτης θέλει η φωτογραφία να «ταιριάζει με το διπλανό κείμενο, από τη
γραμμή-εισαγωγή ως το «…επικοινωνίας»». Το ύψος εκείνου του κειμένου αλλάζει με ΚΑΘΕ αλλαγή
κειμένου ή γραμματοσειράς: 702px → 604px → 651px μέσα σε μία μέρα. Κάθε φορά η φωτογραφία
περίσσευε ή έλειπε, και κάθε φορά χρειαζόταν χειροκίνητο ξαναμέτρημα.

Η ΛΥΣΗ. Το εργαλείο ΜΕΤΡΑΕΙ τη σελίδα (tools/measure-about.py), βγάζει την αναλογία, ξαναφτιάχνει
τα assets με το ύψος ΜΕΣΑ στο όνομα (`katerina-tsiga-p651-…` — αυτό κρατά το immutable cache
σωστό) και **γράφει μόνο του** την αναλογία στο css/style.css και τα νέα ονόματα στο index.html.
Έτσι το «ταιριάζει» δεν εξαρτάται από το αν θυμήθηκα να ξαναμετρήσω.

ΤΟ 4:3 ΔΕΝ ΚΑΤΑΡΓΕΙΤΑΙ: στο κινητό/tablet το about-grid γίνεται μία στήλη και η φωτογραφία μπαίνει
σε 4:3 κουτί, οπότε το 4:3 σετ σερβίρεται μέσω `<picture media>`.

Χρήση:
  ~/.venvs/img/bin/python tools/build-about-portrait.py --measure [url]   # μετράει μόνο του
  ~/.venvs/img/bin/python tools/build-about-portrait.py --text-h 651      # ή με ρητό ύψος
  ... --preview                                                          # 3 υποψήφια καρέ -> /tmp
Μετά την εκτέλεση: python3 tools/version-assets.py && bash tools/deploy-staging.sh
"""
import glob
import json
import os
import re
import subprocess
import sys

from PIL import Image

ROOT = os.path.expanduser("~/tsiga-speech-therapy-v2")
IMG = f"{ROOT}/images"
MASTER = f"{IMG}/katerina-tsiga.jpg"
CSS = f"{ROOT}/css/style.css"
HTML = f"{ROOT}/index.html"
MEASURE_TOOL = f"{ROOT}/tools/measure-about.py"
PW_PY = os.path.expanduser("~/.venvs/fortinet/bin/python")
URL = "https://staging.tsigalogo-staging.pages.dev/"

WIDTHS = [550, 750, 1100]                # 550 -> 1x desktop, 750 -> 2x phone, 1100 -> 2x desktop
QUALITY = {"avif": 70, "webp": 88, "jpg": 88}
LANDSCAPE_PREFIX = "katerina-tsiga-v2"   # 4:3 για κινητό/tablet
LANDSCAPE_TOP = 0                        # από y=0, αλλιώς κόβεται το κεφάλι (ήταν 82)
PREVIEW = "--preview" in sys.argv


def text_height() -> int:
    """Ύψος του εισαγωγικού κειμένου: ρητό (--text-h) ή μετρημένο από τη σελίδα (--measure)."""
    if "--text-h" in sys.argv:
        return int(sys.argv[sys.argv.index("--text-h") + 1])
    if "--measure" in sys.argv:
        i = sys.argv.index("--measure")
        url = sys.argv[i + 1] if len(sys.argv) > i + 1 and sys.argv[i + 1].startswith("http") else URL
        r = subprocess.run([PW_PY, MEASURE_TOOL, url, "--json"], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"η μέτρηση απέτυχε:\n{r.stdout}\n{r.stderr}")
        d = json.loads(r.stdout.strip().splitlines()[-1])
        print(f"μέτρηση από {url}: κείμενο {d['text_h']}px, στήλη {d['col_w']}px, "
              f"φωτογραφία τώρα {d['photo_now'][0]}x{d['photo_now'][1]} (Δκάτω {d['d_bottom_now']}px)")
        return int(d["text_h"])
    sys.exit("δώσε --measure [url] ή --text-h <px>")


H_TEXT = text_height()
RATIO = 550 / H_TEXT                     # στήλη 550px / ύψος κειμένου
PREFIX = f"katerina-tsiga-p{H_TEXT}"     # το νούμερο ΜΕΝΕΙ στο όνομα (immutable cache)

master = Image.open(MASTER).convert("RGB")
if master.size != (1100, 1100):
    sys.exit(f"προσδοκούσα master 1100x1100, βρήκα {master.size}")

# Ύψος = όλο το master (δεν χάνεται τίποτα κατακόρυφα)· το πλάτος βγαίνει από την αναλογία.
H = master.height
W = round(H * RATIO)
print(f"ύψος κειμένου {H_TEXT}px -> αναλογία 550:{H_TEXT} ({RATIO:.4f})")
print(f"master {master.size} -> crop {W}x{H}")

CANDIDATES = {
    "center": (master.width - W) // 2,               # μοιράζει το κόψιμο στις δύο άκρες
    "left":   44,                                    # κρατά αριστερή άκρη (μαλλιά/πρόσωπο)
    "right":  master.width - W - 44,
}

if PREVIEW:
    tiles = []
    for name, x in CANDIDATES.items():
        c = master.crop((x, 0, x + W, H)).resize((330, 420), Image.LANCZOS)
        tiles.append((name, c))
    gap = 12
    strip = Image.new("RGB", (len(tiles) * 330 + (len(tiles) + 1) * gap, 420 + 2 * gap), (250, 245, 240))
    for i, (_n, t) in enumerate(tiles):
        strip.paste(t, (gap + i * (330 + gap), gap))
    strip.save("/tmp/about-portrait-candidates.png")
    print("υποψήφια (αριστερά→δεξιά: " + ", ".join(CANDIDATES) + ") -> /tmp/about-portrait-candidates.png")
    sys.exit(0)

X = int(os.environ.get("ABOUT_CROP_X", CANDIDATES["center"]))
crop = master.crop((X, 0, X + W, H))
print(f"οριζόντιο παράθυρο x {X}..{X + W} (master πλάτος {master.width})")

written = []
for w in WIDTHS:
    im = crop.resize((w, round(w / RATIO)), Image.LANCZOS)
    for ext, kw in (("avif", dict(format="AVIF", quality=QUALITY["avif"])),
                    ("webp", dict(format="WEBP", quality=QUALITY["webp"], method=6))):
        n = f"{PREFIX}-{w}.{ext}"
        im.save(f"{IMG}/{n}", **kw)
        written.append(n)
n = f"{PREFIX}-750.jpg"     # ένα JPEG: fallback για browsers χωρίς AVIF/WebP
crop.resize((750, round(750 / RATIO)), Image.LANCZOS).save(
    f"{IMG}/{n}", format="JPEG", quality=QUALITY["jpg"], optimize=True, progressive=True)
written.append(n)

print()
for n in sorted(written):
    print(f"  {n:32} {os.path.getsize(f'{IMG}/{n}'):>9,} B")

# ---------------------------------------------------------------- 4:3 σετ (κινητό/tablet)
LH = round(master.width * 3 / 4)
landscape = master.crop((0, LANDSCAPE_TOP, master.width, LANDSCAPE_TOP + LH))
print(f"\n4:3 σετ: crop {landscape.size}, y {LANDSCAPE_TOP}..{LANDSCAPE_TOP + LH}")
for w in WIDTHS:
    im = landscape.resize((w, round(w * 3 / 4)), Image.LANCZOS)
    for ext, kw in (("avif", dict(format="AVIF", quality=QUALITY["avif"])),
                    ("webp", dict(format="WEBP", quality=QUALITY["webp"], method=6))):
        n = f"{LANDSCAPE_PREFIX}-{w}.{ext}"
        im.save(f"{IMG}/{n}", **kw)
landscape.resize((750, 562), Image.LANCZOS).save(f"{IMG}/{LANDSCAPE_PREFIX}-750.jpg", format="JPEG",
                                                quality=QUALITY["jpg"], optimize=True, progressive=True)
print(f"  ενημερώθηκε το {LANDSCAPE_PREFIX}-* σετ")

# ---------------------------------------------------------------- ΕΦΑΡΜΟΓΗ σε CSS + HTML
# Χωρίς αυτό, τα assets αλλάζουν αλλά η σελίδα δείχνει τα παλιά (ίδια λογική με το immutable cache).
css = open(CSS, encoding="utf-8").read()
new_css, n_css = re.subn(r"aspect-ratio: 550 /\s*\d+;", f"aspect-ratio: 550 / {H_TEXT};", css)
if n_css != 1:
    sys.exit(f"css: βρήκα {n_css} φορές το «aspect-ratio: 550 / N» — δεν το πειράζω")
open(CSS, "w", encoding="utf-8").write(new_css)
print(f"\ncss/style.css: aspect-ratio -> 550 / {H_TEXT}")

html = open(HTML, encoding="utf-8").read()
old_prefixes = sorted(set(re.findall(r"katerina-tsiga-p(\d+)", html)))
new_html, n_html = re.subn(r"katerina-tsiga-p\d+", PREFIX, html)
if n_html == 0:
    sys.exit("html: δεν βρήκα αναφορές katerina-tsiga-pNNN — δεν το πειράζω")
open(HTML, "w", encoding="utf-8").write(new_html)
print(f"index.html: {n_html} αναφορές -> {PREFIX}")

# Καθαρισμός: τα παλιά πορτραίτο assets γίνονται ορφανά (και δεν πρέπει να σταλούν στο deploy)
for old in old_prefixes:
    if old == str(H_TEXT):
        continue
    for f in glob.glob(f"{IMG}/katerina-tsiga-p{old}-*"):
        os.remove(f)
        print(f"  διαγράφηκε το ορφανό {os.path.basename(f)}")

print(f"\nmaster (για το JSON-LD, δεν σερβίρεται): katerina-tsiga.jpg {os.path.getsize(MASTER):,} B")
print("επόμενο: python3 tools/version-assets.py && bash tools/deploy-staging.sh")
