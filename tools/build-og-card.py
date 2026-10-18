#!/usr/bin/env python3
"""build-og-card.py — εικόνα κοινοποίησης (og:image) + τετράγωνο logo για το schema.org,
από το σήμα «σπίτι + χαμόγελο». ΚΑΝΕΝΑ πρόσωπο: ζητήθηκε ρητά 18/10/2026.

Παράγει (images/):
  og-tsigalogo-1200x630.jpg   κάρτα κοινοποίησης (Facebook/WhatsApp/Viber/LinkedIn/X)
  logo-kt-512.png             512x512, για το `logo` του JSON-LD (η Google ζητά ≥112, ιδανικά 512)

Τυπογραφία: Literata *italic* για το όνομα (τερρακότα), Open Sans για ελληνικά κεφαλαία/κείμενο
(το `--font-heading` Mulish δεν έχει ελληνικό subset — στο site τα ελληνικά πέφτουν στο Open Sans).

Τα woff2 δεν διαβάζονται από το PIL → προσωρινά ttf με fontTools (+brotli).
Τα subsets είναι γλώσσα-συγκεκριμένα, γι' αυτό κάθε χαρακτήρας ζωγραφίζεται με το πρώτο font που
τον ΕΧΕΙ (π.χ. η αποστρόφο του «κατ' οίκον» από το Mulish Latin). Χωρίς αυτό η φράση έβγαινε
«κατ  οίκον» με κενό — σιωπηλά λείπον γλύφο.

Χρήση: python3 tools/build-og-card.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
MARK_SRC = Path("/home/ubuntu/.hermes/images/dashboard_20261018_184046_4d5f70dd_Embracing_Family_House_Logo.png")
CREAM = (253, 244, 236)
TERRACOTTA = (163, 95, 69)
SAGE = (107, 115, 99)
MUTED = (95, 95, 86)

W, H = 1200, 630
NAME = "Κατερίνα Τσίγα"
ROLE = "ΛΟΓΟΘΕΡΑΠΕΥΤΡΑ"
TAG = "Λογοθεραπεία κατ' οίκον  ·  Νότια Προάστια Αττικής"

WHITE_BG = 254.0
LO, HI = 10.0, 45.0


class Face:
    """Ένα font σε δεδομένο μέγεθος, μαζί με το cmap του (για την επιλογή ανά χαρακτήρα)."""

    def __init__(self, font: ImageFont.FreeTypeFont, cmap: set[int]):
        self.font = font
        self.cmap = cmap

    def has(self, ch: str) -> bool:
        return ord(ch) in self.cmap


def load_face(fonts_dir: Path, name: str, size: int, tmp: Path) -> Face:
    src = fonts_dir / name
    ttf = tmp / (src.stem + ".ttf")
    if not ttf.exists():
        f = TTFont(str(src))
        f.flavor = None
        f.save(str(ttf))
    cmap = set(TTFont(str(src)).getBestCmap())
    return Face(ImageFont.truetype(str(ttf), size), cmap)


def mark_rgba() -> Image.Image:
    """Το σήμα με διαφανές φόντο (ίδια λογική με το tools/build-logo-mark.py)."""
    im = Image.open(MARK_SRC).convert("RGB")
    w, h = im.size
    sp = im.load()
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dp = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b = sp[x, y]
            d = WHITE_BG - min(r, g, b)
            if d <= LO:
                continue
            a = 1.0 if d >= HI else (d - LO) / (HI - LO)
            if a < 1.0:
                r, g, b = (max(0, min(255, round((c - WHITE_BG * (1 - a)) / a))) for c in (r, g, b))
            dp[x, y] = (r, g, b, round(a * 255))
    bbox = out.getbbox()
    if not bbox:
        raise SystemExit("άδειο σήμα — δεν βρέθηκε μελάνι")
    return out.crop(bbox)


def pick(faces: list[Face], ch: str) -> ImageFont.FreeTypeFont:
    for f in faces:
        if f.has(ch):
            return f.font
    return faces[0].font


def draw_centered(draw, text: str, faces: list[Face], y: int, fill, tracking: int = 0) -> None:
    widths = [draw.textlength(ch, font=pick(faces, ch)) for ch in text]
    total = sum(widths) + tracking * max(0, len(text) - 1)
    x = (W - total) / 2
    for ch, cw in zip(text, widths):
        draw.text((x, y), ch, font=pick(faces, ch), fill=fill)
        x += cw + tracking


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ogcard-"))
    fonts = ROOT / "fonts"

    name_faces = [load_face(fonts, "literata-italic-greek.woff2", 96, tmp),
                  load_face(fonts, "mulish-latin.woff2", 96, tmp)]
    role_faces = [load_face(fonts, "opensans-greek.woff2", 27, tmp),
                  load_face(fonts, "mulish-latin.woff2", 27, tmp)]
    tag_faces = [load_face(fonts, "opensans-greek.woff2", 29, tmp),
                 load_face(fonts, "mulish-latin.woff2", 29, tmp)]

    card = Image.new("RGB", (W, H), CREAM)
    draw = ImageDraw.Draw(card)

    # 1) σήμα, κεντραρισμένο
    mark = mark_rgba()
    mh = 190
    mw = round(mark.width * mh / mark.height)
    mark = mark.resize((mw, mh), Image.LANCZOS)
    card.paste(mark, ((W - mw) // 2, 62), mark)

    # 2) όνομα
    bbox = draw.textbbox((0, 0), NAME, font=name_faces[0].font)
    draw_centered(draw, NAME, name_faces, 262 - bbox[1], TERRACOTTA)

    # 3) λεπτή sage γραμμή
    draw.line([(W // 2 - 70, 402), (W // 2 + 70, 402)], fill=SAGE, width=2)

    # 4) ιδιότητα σε spaced caps
    draw_centered(draw, ROLE, role_faces, 428, SAGE, tracking=7)

    # 5) tagline
    draw_centered(draw, TAG, tag_faces, 500, MUTED)

    og = ROOT / "images" / "og-tsigalogo-1200x630.jpg"
    card.save(og, "JPEG", quality=90, optimize=True, progressive=True)
    print(f"  {og.relative_to(ROOT)}  {W}x{H}  {og.stat().st_size / 1024:.0f} KB")

    # 6) τετράγωνο logo 512 για το JSON-LD (αδιάφανο cream — η Google προτιμά τετράγωνο, απλό)
    sq = Image.new("RGB", (512, 512), CREAM)
    m2 = mark_rgba()
    mh2 = 380
    mw2 = round(m2.width * mh2 / m2.height)
    m2 = m2.resize((mw2, mh2), Image.LANCZOS)
    sq.paste(m2, ((512 - mw2) // 2, (512 - mh2) // 2), m2)
    logo = ROOT / "images" / "logo-kt-512.png"
    sq.save(logo, "PNG", optimize=True)
    print(f"  {logo.relative_to(ROOT)}  512x512  {logo.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
