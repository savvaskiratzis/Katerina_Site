#!/usr/bin/env python3
"""Turn Katerina's welcome artwork into deployable assets (v2).

Her image has ALL text/icons/logos BAKED IN — Greek only. The site is bilingual, so every
word must become real HTML. Therefore the artwork is cleaned into a pure illustration:

  * the central card panel is flattened to the EXACT CSS card colour, so an HTML card drawn
    on top cannot show a seam (any mismatch is the same colour by construction);
  * the two baked clusters OUTSIDE the card (the 4-icon row, the left handwritten note) are
    removed with a HARMONIC fill (Laplace/Jacobi at 1/6 scale, then upsampled and feathered).
    A plain per-column lerp was tried first and left visible vertical streaks — the harmonic
    solve has no preferred direction, so a smooth gradient is reproduced without banding;
  * the illustration itself (tree, bird, house, sun, hills, books) is untouched.

Master + exports go to two DIFFERENT places on purpose: the clean master lives in
artwork-src/ (never deployed — `images/*` ships wholesale), the web assets in images/.

Run:  ~/.venvs/img/bin/python tools/build-welcome-assets.py
Verify: ~/.venvs/img/bin/python tools/check-welcome-assets.py
"""
import os
from PIL import Image, ImageDraw, ImageFilter

SRC = "/home/azureadmin/.hermes/images/dashboard_20260919_130014_a2bfcca0_Gemini_Generated_Image_4qtahm4qtahm4qta.jpg"
ROOT = os.path.expanduser("~/tsiga-speech-therapy-v2")
OUT = os.path.join(ROOT, "images")
SRC_DIR = os.path.join(ROOT, "artwork-src")
os.makedirs(OUT, exist_ok=True)
os.makedirs(SRC_DIR, exist_ok=True)

im = Image.open(SRC).convert("RGB")
W, H = im.size
print(f"master {W}x{H}")

# ---------------------------------------------------------------- 1. card colour
flat = im.convert("L").filter(ImageFilter.MedianFilter(31))
g, f = im.convert("L").load(), flat.load()
samples = []
for y in range(int(0.10 * H), int(0.74 * H), 3):
    for x in range(int(0.32 * W), int(0.68 * W), 3):
        if abs(g[x, y] - f[x, y]) <= 10:
            samples.append(im.getpixel((x, y)))
samples.sort(key=lambda c: c[0] + c[1] + c[2])
mid = samples[len(samples) // 4: len(samples) // 2]
CARD = tuple(sum(c[i] for c in mid) // len(mid) for i in range(3))
print(f"card fill from {len(samples)} flat px -> #{CARD[0]:02x}{CARD[1]:02x}{CARD[2]:02x}")

CARD_BOX = (0.315, 0.085, 0.685, 0.750)      # from the scanline probe
R = int(0.021 * W)
x0, y0, x1, y1 = (int(CARD_BOX[0] * W), int(CARD_BOX[1] * H),
                  int(CARD_BOX[2] * W), int(CARD_BOX[3] * H))
panel = Image.new("L", (W, H), 0)
ImageDraw.Draw(panel).rounded_rectangle([x0, y0, x1, y1], radius=R, fill=255)
panel = panel.filter(ImageFilter.GaussianBlur(6))
im = Image.composite(Image.new("RGB", (W, H), CARD), im, panel)
print(f"card panel flattened ({x0},{y0})-({x1},{y1}) r={R}px")


# ---------------------------------------------------------------- 2. harmonic inpaint
def local_contrast_mask(img, box, thr=8, dilate=9, scale=6):
    """Mask of the *artwork's own* high-frequency content (text strokes, icon outlines,
    pale discs) inside `box`."""
    bx0, by0, bx1, by1 = (int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H))
    sub = img.crop((bx0, by0, bx1, by1)).convert("L")
    med = sub.filter(ImageFilter.MedianFilter(31))
    p, q = sub.load(), med.load()
    m = Image.new("L", sub.size, 0)
    mp = m.load()
    for y in range(sub.size[1]):
        for x in range(sub.size[0]):
            if abs(p[x, y] - q[x, y]) > thr:
                mp[x, y] = 255
    m = m.filter(ImageFilter.MaxFilter(dilate))
    small = m.resize((max(4, sub.size[0] // scale), max(4, sub.size[1] // scale)), Image.LANCZOS)
    return small.point(lambda v: 255 if v > 40 else 0).filter(ImageFilter.MaxFilter(3)), (bx0, by0, bx1, by1)


def grain_stats(img, box, ring=60):
    """σ of the artwork's own fine grain around the patch, per channel, from a ring
    just outside it. The fill must be re-textured with the SAME grain, otherwise the
    patched area reads as a smooth 'plateau' inside a textured drawing (observed)."""
    bx0, by0, bx1, by1 = (int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H))
    rx0, ry0 = max(0, bx0 - ring), max(0, by0 - ring)
    rx1, ry1 = min(W, bx1 + ring), min(H, by1 + ring)
    sub = img.crop((rx0, ry0, rx1, ry1))
    med = sub.filter(ImageFilter.MedianFilter(31))
    a, b = sub.load(), med.load()
    ss = [0.0, 0.0, 0.0]
    n = 0
    for y in range(0, sub.size[1], 3):
        for x in range(0, sub.size[0], 3):
            inside = bx0 <= rx0 + x <= bx1 and by0 <= ry0 + y <= by1
            if inside:
                continue
            for c in range(3):
                ss[c] += (a[x, y][c] - b[x, y][c]) ** 2
            n += 1
    return [max(1.0, (ss[c] / max(1, n)) ** 0.5) for c in range(3)]


def harmonic_fill(img, box, thr=8, scale=6, iters=2500, feather=14, full_box=True):
    """Fill everything inside `box` with a harmonic (Laplace) solve, then re-add the
    surrounding grain.

    full_box=True is the important bit and it was learned by looking at the output: masking
    only the artwork's strokes (full_box=False) leaves the mask ~2 px wide, and the edge
    feather then blends the ORIGINAL back over the glyphs at ~20% — the baked labels came
    back as legible grey ghosts. Covering the whole cluster box and painting it from its own
    boundary does remove them.
    """
    import random
    rnd = random.Random(20260919)                     # deterministic output
    mask_small, (bx0, by0, bx1, by1) = local_contrast_mask(img, box, thr=thr, scale=scale)
    if full_box:
        mask_small = Image.new("L", mask_small.size, 255)
    sigma = grain_stats(img, box)
    pad = 14
    sx0, sy0 = max(0, bx0 - pad), max(0, by0 - pad)
    sx1, sy1 = min(W, bx1 + pad), min(H, by1 + pad)
    sw, sh = max(4, (sx1 - sx0) // scale), max(4, (sy1 - sy0) // scale)
    small = img.crop((sx0, sy0, sx1, sy1)).resize((sw, sh), Image.LANCZOS)
    p = small.load()
    aligned = Image.new("L", (sw, sh), 0)
    aligned.paste(mask_small, (max(0, (bx0 - sx0) // scale), max(0, (by0 - sy0) // scale)))
    mm = aligned.load()
    todo = [(x, y) for y in range(sh) for x in range(sw) if mm[x, y] > 128]
    for _ in range(iters):
        for x, y in todo:
            a = p[x - 1, y] if x > 0 else p[x, y]
            b = p[x + 1, y] if x + 1 < sw else p[x, y]
            c = p[x, y - 1] if y > 0 else p[x, y]
            d = p[x, y + 1] if y + 1 < sh else p[x, y]
            p[x, y] = tuple((a[i] + b[i] + c[i] + d[i]) // 4 for i in range(3))
    patch = small.resize((sx1 - sx0, sy1 - sy0), Image.BICUBIC)
    out = img.copy()
    out.paste(patch, (sx0, sy0))
    m = Image.new("L", (W, H), 0)
    m.paste(mask_small.resize((bx1 - bx0, by1 - by0), Image.LANCZOS), (bx0, by0))
    m = m.filter(ImageFilter.GaussianBlur(feather))
    res = Image.composite(out, img, m)
    # Re-texture AT FULL RESOLUTION and proportionally to the mask's own alpha: adding the
    # noise before the 6x upsample just gets averaged away by the interpolation, and adding
    # it flat would put a hard-grained patch on a soft-edged drawing.
    ap, rp = m.load(), res.load()
    for y in range(max(0, by0 - feather), min(H, by1 + feather)):
        for x in range(max(0, bx0 - feather), min(W, bx1 + feather)):
            a = ap[x, y] / 255.0
            if a <= 0.02:
                continue
            c = rp[x, y]
            rp[x, y] = tuple(max(0, min(255, int(c[i] + rnd.gauss(0, sigma[i] * a)))) for i in range(3))
    return res, sigma, len(todo)


for name, (box, thr) in {
    "bottom 4-icon row": ((0.325, 0.856, 0.672, 0.950), 6),
    "left handwritten note": ((0.028, 0.782, 0.232, 0.925), 8),
}.items():
    im, sigma, npx = harmonic_fill(im, box, thr=thr)
    print(f"harmonically inpainted {name} {box}  (masked px at 1/6 scale: {npx}, "
          f"grain σ R{sigma[0]:.1f} G{sigma[1]:.1f} B{sigma[2]:.1f})")

master = os.path.join(SRC_DIR, "welcome-art-clean.png")
im.save(master, optimize=True)
print(f"clean master -> {master}  (artwork-src/ is NOT deployed)")

# ---------------------------------------------------------------- 3. responsive exports
def exports(img, stem, widths, quality_webp=80, quality_avif=52):
    for w in widths:
        if w > img.width:
            continue
        r = img.resize((w, round(w * img.height / img.width)), Image.LANCZOS)
        wp = os.path.join(OUT, f"{stem}-{w}.webp")
        r.save(wp, quality=quality_webp, method=6)
        try:
            ap = os.path.join(OUT, f"{stem}-{w}.avif")
            r.save(ap, quality=quality_avif)
            sizes = f"webp {os.path.getsize(wp)//1024}K  avif {os.path.getsize(ap)//1024}K"
        except Exception as e:
            sizes = f"webp {os.path.getsize(wp)//1024}K  (avif unavailable: {e})"
        print(f"  {stem}-{w}: {sizes}")

print("desktop exports (whole artwork, fit-to-height):")
exports(im, "welcome-art", [1600, 1100, 700])
print("mobile band exports (whole artwork scaled to width):")
exports(im, "welcome-band", [900, 600])
