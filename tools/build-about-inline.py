#!/usr/bin/env python3
"""Φτιάχνει τις δύο εικόνες που μπαίνουν ΔΙΠΛΑ στα κείμενα του «Σχετικά με Εμένα».

ΓΙΑΤΙ ΥΠΑΡΧΕΙ. Οι πηγές είναι δύο αρχεία που έστειλε η ιδιοκτήτρια (18/10/2026) και ΔΕΝ είναι
φωτογραφίες έτοιμες για web:
  * το πρόσωπο: 288×288 px — πολύ μικρό, με σκληρό backlight (παράθυρο καμένο) και σκιές
    κολλημένες· μπαίνει σε ΚΥΚΛΙΚΟ πλαίσιο ~200px, άρα θέλει crop που να αφήνει αέρα πάνω/κάτω
    από το πρόσωπο, άνοιγμα σκιών, ζεστό τόνο (η παλέτα του site είναι #fdf4ec) και απαλό
    vignette ώστε να μη «τραβάει» το παράθυρο.
  * η εικονογράφηση «κύκλος οικογένειας»: 1122×1402 px, κρεμ φόντο — μόνο καθαρισμός άκρων,
    μέγεθος για retina και μετατροπή σε webp/jpg.

Οι πηγές ΔΕΝ αλλάζουν ποτέ (artwork-src λογική): το script ξαναφτιάχνει τα παράγωγα από αυτές.
Τα παράγωγα παίρνουν ΝΕΟ όνομα, γιατί το /images/* σερβίρεται immutable για 1 χρόνο.

Χρήση: python3 tools/build-about-inline.py
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "images"
SRC_FACE = Path.home() / ".hermes/images/dashboard_20261018_154833_e20d4a5e_pasted-image.jpg"
SRC_CIRCLE = Path.home() / ".hermes/images/dashboard_20261018_154847_625b18d3_pasted-image.png"
SRC_VALUES = Path.home() / ".hermes/images/dashboard_20261018_161125_1fc91dfe_pasted-image.png"
SRC_APPROACH = Path.home() / ".hermes/images/dashboard_20261018_162849_789948c2_pasted-image.png"

FACE_OUT = "katerina-tsiga-face-640"
CIRCLE_OUT = "tsiga-family-circle-760"
VALUES_OUT = "tsiga-values-fingerprint-760"
APPROACH_OUT = "tsiga-approach-session-760"
FACE_BOX = (0.014, 0.000, 0.986, 0.972)     # μετρημένο: το πρόσωπο κάθεται κεντρικά, ίσιο crop
FACE_SIZE = 640


def ink_bbox(img, thresh=18):
    """Όριο μελάνης πάνω στο κρεμ φόντο. ΓΙΑΤΙ: τα δύο PNG έχουν μεγάλα κρεμ περιθώρια
    (μετρημένο: «κύκλος» T12.3%, «αποτύπωμα» L13.7%), που στο site εμφανίζονταν σαν μισοάδειο
    κάδρο και η ζωγραφιά ξεκινούσε ~125px πιο κάτω από τον τίτλο «Πώς δουλεύω» — δηλαδή η εικόνα
    «δεν ευθυγραμμιζόταν» με το κείμενο ενώ το κουτί της ήταν στην ίδια γραμμή."""
    w, h = img.size
    samples = [img.getpixel((5, 5)), img.getpixel((w - 6, 5)), img.getpixel((5, h - 6)), img.getpixel((w - 6, h - 6))]
    bg = tuple(sorted(s[i] for s in samples)[1] for i in range(3))
    diff = ImageChops.difference(img, Image.new("RGB", img.size, bg)).convert("L")
    diff = diff.point(lambda v: 255 if v > thresh else 0)
    return diff.getbbox()


def crop_to_ink(img, pad_frac=0.03):
    """Περικόπτει το περιττό κρεμ περιθώριο κρατώντας ΟΜΟΙΟΜΟΡΦΟ «αέρα» γύρω από τη ζωγραφιά."""
    bbox = ink_bbox(img)
    if not bbox:
        return img
    l, t, r, b = bbox
    pad = int(round(img.width * pad_frac))
    return img.crop((max(0, l - pad), max(0, t - pad),
                     min(img.width, r + pad), min(img.height, b + pad)))


def shadow_lift(img, amount=0.34):
    """Ανοίγει τις σκιές χωρίς να κάψει τα φώτα (gamma lift + ήπια προστασία highlights)."""
    lut = []
    for i in range(256):
        x = i / 255
        y = x ** (1 - amount) if x > 0 else 0.0
        y *= 1 - 0.10 * x ** 3
        lut.append(max(0, min(255, int(round(y * 255)))))
    return img.point(lut * 3)


def warm(img, r=1.03, g=1.00, b=0.97):
    ch = img.split()
    ch = (ch[0].point(lambda v: min(255, int(v * r))),
          ch[1].point(lambda v: min(255, int(v * g))),
          ch[2].point(lambda v: min(255, int(v * b))))
    return Image.merge("RGB", ch)


def vignette(img, strength=0.34, start=0.55):
    """Απαλό σκούρεμα προς τις άκρες — κρύβει το καμένο παράθυρο χωρίς να φαίνεται «φίλτρο»."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    cx, cy = w / 2, h / 2
    maxr = (w ** 2 + h ** 2) ** 0.5 / 2
    steps = 60
    for i in range(steps, 0, -1):
        f = i / steps
        rr = maxr * f
        val = int(255 * (1 - strength * max(0.0, (f - start) / (1 - start)) ** 1.4))
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=val)
    mask = mask.filter(ImageFilter.GaussianBlur(maxr * 0.04))
    return Image.composite(img, Image.new("RGB", (w, h), (26, 22, 20)), mask)


def save_pair(img, name, quality_webp=88, quality_jpg=90):
    webp = IMAGES / f"{name}.webp"
    jpg = IMAGES / f"{name}.jpg"
    img.save(webp, "WEBP", quality=quality_webp, method=6)
    img.save(jpg, "JPEG", quality=quality_jpg, optimize=True, progressive=False, subsampling=0)
    return webp, jpg


def main():
    if not SRC_FACE.exists() or not SRC_CIRCLE.exists():
        raise SystemExit(f"λείπει πηγή: {SRC_FACE if not SRC_FACE.exists() else SRC_CIRCLE}")

    # ---- 1. πρόσωπο (κυκλικό πλαίσιο) -------------------------------------
    face = Image.open(SRC_FACE).convert("RGB")
    l, t, r, b = FACE_BOX
    face = face.crop((int(l * face.width), int(t * face.height),
                      int(r * face.width), int(b * face.height)))
    face = shadow_lift(face)
    face = ImageEnhance.Brightness(face).enhance(1.05)
    face = ImageEnhance.Contrast(face).enhance(1.05)
    face = warm(face)
    face = ImageEnhance.Color(face).enhance(1.06)
    face = vignette(face)
    face = face.resize((FACE_SIZE, FACE_SIZE), Image.Resampling.LANCZOS)
    face = face.filter(ImageFilter.UnsharpMask(radius=1.6, percent=78, threshold=3))
    for p in save_pair(face, FACE_OUT, quality_webp=88, quality_jpg=91):
        print(f"  ✓ {p.relative_to(ROOT)}  {face.width}×{face.height}  {p.stat().st_size // 1024} KB")

    # ---- 2. εικονογραφήσεις: «κύκλος οικογένειας» + «αποτύπωμα αξιών» ---------
    for src, out in ((SRC_CIRCLE, CIRCLE_OUT), (SRC_VALUES, VALUES_OUT)):
        if not src.exists():
            raise SystemExit(f"λείπει πηγή: {src}")
        art = Image.open(src).convert("RGB")
        # Πρώτα κόβεται το περιττό κρεμ περιθώριο (ομοιόμορφος αέρας 3%), ώστε η ζωγραφιά να
        # ξεκινά σχεδόν από την κορυφή του κάδρου και να «κάθεται» στην ίδια γραμμή με τον τίτλο.
        art = crop_to_ink(art, pad_frac=0.03)
        target_w = 760
        art = art.resize((target_w, round(art.height * target_w / art.width)), Image.Resampling.LANCZOS)
        art = ImageEnhance.Contrast(art).enhance(1.02)
        art = ImageEnhance.Color(art).enhance(1.02)
        for p in save_pair(art, out, quality_webp=82, quality_jpg=86):
            print(f"  ✓ {p.relative_to(ROOT)}  {art.width}×{art.height}  {p.stat().st_size // 1024} KB")

    # ---- 3. εικονογράφηση «Η δική μου προσέγγιση» --------------------------
    # ΠΡΟΣΟΧΗ: ΔΕΝ περνάει από crop_to_ink — αυτή η ζωγραφιά είναι full-bleed (η απαλή
    # ροζ/κρεμ διαβάθμιση καλύπτει όλο τον καμβά), οπότε «όριο μελάνης» δεν υπάρχει και ένα
    # crop θα έκοβε τη σύνθεση. Μόνο resize + ήπια ρύθμιση.
    if not SRC_APPROACH.exists():
        raise SystemExit(f"λείπει πηγή: {SRC_APPROACH}")
    art = Image.open(SRC_APPROACH).convert("RGB")
    target_w = 760
    art = art.resize((target_w, round(art.height * target_w / art.width)), Image.Resampling.LANCZOS)
    art = ImageEnhance.Contrast(art).enhance(1.02)
    art = ImageEnhance.Color(art).enhance(1.02)
    for p in save_pair(art, APPROACH_OUT, quality_webp=82, quality_jpg=86):
        print(f"  ✓ {p.relative_to(ROOT)}  {art.width}×{art.height}  {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
