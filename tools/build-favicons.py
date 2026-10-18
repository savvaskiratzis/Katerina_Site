#!/usr/bin/env python3
"""build-favicons.py — παράγει το σετ favicon/app-icon του tsigalogo.gr από το ΣΗΜΑ του λογοτύπου.

ΑΛΛΑΓΗ 18/10/2026: η πηγή ήταν η φωτογραφία (images/katerina-tsiga.jpg). Τώρα είναι το σήμα
«σπίτι + χαμόγελο» (images/logo-kt-house-192.png), δηλαδή το ίδιο artwork με το header icon —
ζητήθηκε από τον ιδιοκτήτη («μπορεί το σπίτι με το χαμόγελο να γίνει και favicon;»).

ΔΕΝ γίνεται κανένα redraw: μόνο alpha από το λευκό (un-premultiply), τετραγώνισμα με διαφανές
περιθώριο και downscale. Στα 16-24px το σήμα είναι μικρό, γι' αυτό:
  * το padding είναι μικρό (6%) ώστε το σπίτι να γεμίζει το πλακίδιο,
  * τα μικρά μεγέθη παίρνουν ελαφρύ UnsharpMask (55%) — το καθαρό LANCZOS από 192 → 16 μαλακώνει,
  * τα PNG του browser μένουν ΔΙΑΦΑΝΗ (φαίνονται σωστά σε light και dark tab bar),
  * apple-touch & android γίνονται ΑΔΙΑΦΑΝΗ σε cream (253,244,236): το iOS συνθέτει τη διαφάνεια
    πάνω σε μαύρο και το Android την κόβει σε mask.

ΠΑΡΑΓΕΙ (root):
  favicon.ico (16+32+48), favicon-{16,32,48,96}x{...}.png, apple-touch-icon.png (180),
  android-chrome-{192,512}.png, site.webmanifest

Χρήση:  python3 tools/build-favicons.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
import sys
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "images" / "logo-kt-house-192.png"     # έτοιμο RGBA, διαφανές, κομμένο

ICO_FRAMES = (16, 32, 48)
PNG_SMALL = (16, 32, 48, 96)
APPLE_TOUCH = 180
ANDROID = (192, 512)
SHARPEN_MAX = 48
SHARPEN = dict(radius=0.8, percent=55, threshold=2)
PAD = 0.03                                    # 3% περιθώριο: στα 16px το σπίτι πρέπει να
                                              # γεμίζει το πλακίδιο (6% έτρωγε πολύτιμα pixel)
CREAM = (253, 244, 236, 255)                  # ίδιο με το φόντο του header

MANIFEST_NAME = "Κατερίνα Τσίγα - Λογοθεραπεύτρια"
MANIFEST_SHORT = "Κατερίνα Τσίγα"
THEME_COLOR = "#1a1a2e"                       # <meta name="theme-color"> του index.html


def load_source() -> Image.Image:
    im = Image.open(SOURCE).convert("RGBA")
    if im.getbbox() is None:
        sys.exit(f"✗ Το {SOURCE.name} δεν έχει ορατό περιεχόμενο.")
    if max(im.size) < 150:
        sys.exit(f"✗ Η πηγή είναι μόνο {im.size} — χρειάζεται ≥150px για καθαρό 96/180.")
    return im


def squared(src: Image.Image) -> Image.Image:
    """Κεντράρει το σήμα σε τετράγωνο καμβά με διαφανές περιθώριο PAD."""
    w, h = src.size
    side = round(max(w, h) * (1 + 2 * PAD))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(src, ((side - w) // 2, (side - h) // 2), src)
    return canvas


def render(base: Image.Image, size: int, opaque: bool) -> Image.Image:
    im = base.resize((size, size), Image.LANCZOS)
    if size <= SHARPEN_MAX:
        # Το sharpen γίνεται στα χρώματα (RGB) και μετά ξανακολλάει το alpha.
        alpha = im.getchannel("A")
        rgb = im.convert("RGB").filter(ImageFilter.UnsharpMask(**SHARPEN))
        im = rgb.convert("RGBA")
        im.putalpha(alpha)
    if opaque:
        bg = Image.new("RGBA", im.size, CREAM)
        bg.alpha_composite(im)
        return bg.convert("RGB")
    return im


def png_bytes(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def build_ico(payloads: list[tuple[bytes, int]]) -> bytes:
    """Χειροποίητο .ico: το PIL δεν βάζει ΞΕΧΩΡΙΣΤΗ τέχνη ανά frame."""
    n = len(payloads)
    header = struct.pack("<HHH", 0, 1, n)
    offset = 6 + 16 * n
    entries, blobs = b"", b""
    for data, size in payloads:
        entries += struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return header + entries + blobs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="μόνο σύγκριση, χωρίς εγγραφή")
    args = ap.parse_args()

    base = squared(load_source())
    print(f"πηγή: {SOURCE.relative_to(ROOT)} → τετράγωνο {base.size[0]}x{base.size[1]} (κανένα redraw)")

    outputs: dict[str, bytes] = {}
    for s in PNG_SMALL:
        outputs[f"favicon-{s}x{s}.png"] = png_bytes(render(base, s, opaque=False))
    outputs["apple-touch-icon.png"] = png_bytes(render(base, APPLE_TOUCH, opaque=True))
    for s in ANDROID:
        outputs[f"android-chrome-{s}x{s}.png"] = png_bytes(render(base, s, opaque=True))

    outputs["favicon.ico"] = build_ico([(outputs[f"favicon-{s}x{s}.png"], s) for s in ICO_FRAMES])

    outputs["site.webmanifest"] = (
        json.dumps(
            {
                "name": MANIFEST_NAME,
                "short_name": MANIFEST_SHORT,
                "icons": [
                    {"src": f"/android-chrome-{s}x{s}.png", "sizes": f"{s}x{s}", "type": "image/png"}
                    for s in ANDROID
                ],
                "theme_color": THEME_COLOR,
                "background_color": "#ffffff",
                "display": "standalone",
                "start_url": "/",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")

    changed, missing = [], []
    for name, data in outputs.items():
        path = ROOT / name
        old = path.read_bytes() if path.exists() else None
        if old is None:
            missing.append(name)
        elif old != data:
            changed.append(name)
        if not args.check:
            path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()[:12]
        state = "νέο" if old is None else ("ίδιο" if old == data else "άλλαξε")
        print(f"  {name:28s} {len(data):>7,} B  sha256:{digest}  {state}")

    print()
    if args.check:
        if changed or missing:
            print(f"✗ check: λείπουν {missing} / διαφέρουν {changed} — τρέξε χωρίς --check")
            return 1
        print("✓ check: όλα τα αρχεία ταυτίζονται με ό,τι παράγει το script")
        return 0
    print(f"✓ γράφτηκαν {len(outputs)} αρχεία στη ρίζα (νέα: {len(missing)}, αλλαγμένα: {len(changed)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
