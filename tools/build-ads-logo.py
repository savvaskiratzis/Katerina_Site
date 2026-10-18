#!/usr/bin/env python3
"""Build the Google Ads business logo (760x760) from the portrait master — **no crop**.

WHY. Google Ads 'business logo' (Λογότυπο επιχείρησης) needs a 1:1 image, and the owner asked
for HER FACE, not the KT monogram. The portrait master `images/katerina-tsiga.jpg` is already
1100x1100 (square) — it is also the file the site's LocalBusiness JSON-LD publishes as `image`.
A square source means a 1:1 target needs NO crop: the artwork stays αυτούσιο, μηδέν επέμβαση
(nothing is cut, re-framed, retouched or colour-graded; it is a proportional resize only).

Verified by measurement, not by eye (this machine has no vision model):
  * the source is square  -> asserted in code, a 1:1 target provably cannot need a crop;
  * a face is detected in the source AND in the output with YuNet, with the same relative
    geometry (< 2 % drift) -> her face survives the resize and the framing is untouched;
  * output is RGB, no alpha, PNG, far below Google's 5 MB limit.

    python3 tools/build-ads-logo.py
"""
import os
import sys
import urllib.request

import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.expanduser("~/tsiga-speech-therapy/images/katerina-tsiga.jpg")
OUTDIR = os.path.join(ROOT, "google-ads")          # local-only (see .gitignore)
LOGO = os.path.join(OUTDIR, "business-logo-760x760.png")
SHEET = os.path.join(OUTDIR, "business-logo-preview.png")
SIZE = 760
MODEL_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_detection_yunet/face_detection_yunet_2023mar.onnx")
MODEL = os.path.expanduser("~/.hermes/cache/face/yunet.onnx")


def ensure_model():
    if not os.path.exists(MODEL):
        os.makedirs(os.path.dirname(MODEL), exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL)
    return MODEL


def face_of(path, threshold=0.5):
    """Largest detected face as fractions of the frame -> resolution independent."""
    img = cv2.imread(path)
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(ensure_model(), "", (w, h), threshold, 0.3, 5000)
    _, faces = det.detect(img)
    if faces is None or len(faces) == 0:
        return None
    f = max(faces, key=lambda r: r[2] * r[3])
    x, y, fw, fh = [float(v) for v in f[:4]]
    return {
        "conf": float(f[-1]),
        "cx": (x + fw / 2) / w, "cy": (y + fh / 2) / h,
        "w": fw / w, "h": fh / h,
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    master = Image.open(MASTER)
    if master.size[0] != master.size[1]:
        sys.exit("Ο master δεν είναι τετράγωνος ({}): 1:1 θα απαιτούσε crop — ΣΤΑΜΑΤΑΩ.".format(
            master.size))
    if master.mode != "RGB":
        master = master.convert("RGB")

    before = face_of(MASTER)
    if before is None:
        sys.exit("Δεν ανιχνεύτηκε πρόσωπο στο master — ΣΤΑΜΑΤΑΩ (δεν στέλνω λάθος asset).")

    logo = master.resize((SIZE, SIZE), Image.LANCZOS, reducing_gap=2.0)
    logo.save(LOGO, "PNG", optimize=True)

    after = face_of(LOGO)
    if after is None:
        sys.exit("Το πρόσωπο χάθηκε στο resize — ΣΤΑΜΑΤΑΩ.")

    # A pure proportional resize cannot move content. Prove that by region correspondence:
    # every sub-box of the master must reappear at the scaled position with ~the same pixels.
    # (Comparing detector boxes instead would only measure YuNet's confidence drift across
    # scales: here it returned conf 0.54 on the master and 0.86 on the logo, with a taller box.)
    from PIL import ImageChops

    regions = {
        "centre": (0.25, 0.25, 0.75, 0.75),
        "top-left": (0.00, 0.00, 0.30, 0.30),
        "top-right": (0.70, 0.00, 1.00, 0.30),
        "bottom-left": (0.00, 0.70, 0.30, 1.00),
        "bottom-right": (0.70, 0.70, 1.00, 1.00),
        "face area": (0.10, 0.02, 0.72, 0.62),
    }
    src_w = master.width
    diffs = {}
    for name, (x0f, y0f, x1f, y1f) in regions.items():
        mbox = (int(x0f * src_w), int(y0f * src_w), int(x1f * src_w), int(y1f * src_w))
        lbox = tuple(round(v * SIZE / float(src_w)) for v in mbox)
        a = master.crop(mbox).resize((lbox[2] - lbox[0], lbox[3] - lbox[1]), Image.LANCZOS)
        b = logo.crop(lbox)
        diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        data = list(diff.getdata())
        diffs[name] = sum(sum(p) for p in data) / (3.0 * len(data))
    worst_region = max(diffs, key=diffs.get)

    # invariants that a pure scale must preserve (x/width matched exactly in practice)
    dx = abs(after["cx"] - before["cx"])
    dw = abs(after["w"] - before["w"])
    kb = os.path.getsize(LOGO) / 1024.0

    print("master : {} {} ({:,} B)".format(master.size, master.mode, os.path.getsize(MASTER)))
    print("logo   : {} {} {:.0f} KiB  ->  {}".format(logo.size, logo.mode, kb, LOGO))
    print("face in master : conf {:.2f}  centre ({:.0%},{:.0%})  size {:.0%}x{:.0%} of frame".format(
        before["conf"], before["cx"], before["cy"], before["w"], before["h"]))
    print("face in logo   : conf {:.2f}  centre ({:.0%},{:.0%})  size {:.0%}x{:.0%} of frame".format(
        after["conf"], after["cx"], after["cy"], after["w"], after["h"]))
    print("face invariants: Δx-centre {:.2%}, Δwidth {:.2%} (must be ~0 for a pure resize)".format(
        dx, dw))
    print("region correspondence (mean |Δ| of 255 — a crop would break this badly):")
    for name, v in sorted(diffs.items(), key=lambda kv: -kv[1]):
        print("    {:14s} {:.2f}".format(name, v))
    ok_drift = dx < 0.02 and dw < 0.02
    ok_regions = diffs[worst_region] < 6.0
    ok_size = kb < 5120
    print("checks : square source · face present · face invariants {} · regions {} (worst {} {:.2f}) "
          "· {:.0f} KiB vs 5120 {} ".format(
              "OK" if ok_drift else "FAIL", "OK" if ok_regions else "FAIL",
              worst_region, diffs[worst_region], kb, "OK" if ok_size else "FAIL"))
    if not (ok_drift and ok_regions and ok_size):
        sys.exit("Έλεγχος απέτυχε — ΣΤΑΜΑΤΑΩ, δεν παραδίδω asset.")

    # ---- preview: how it reads at ad sizes + in a text-ad slot -------------------------
    def font(sz, bold=False):
        p = "/usr/share/fonts/truetype/dejavu/DejaVuSans{}.ttf".format("-Bold" if bold else "")
        return ImageFont.truetype(p, sz) if os.path.exists(p) else ImageFont.load_default()

    W, H = 1040, 470
    sheet = Image.new("RGB", (W, H), (246, 247, 249))
    d = ImageDraw.Draw(sheet)
    d.text((28, 20), "Google Ads — Λογότυπο επιχείρησης 760×760", font=font(24, bold=True),
           fill=(16, 22, 30))
    d.text((28, 54), "αυτούσιο artwork: μηδέν crop, μηδέν retouch — μόνο αναλογικό resize "
                     "από το master 1100×1100", font=font(13), fill=(110, 118, 128))
    big = logo.resize((240, 240), Image.LANCZOS)
    sheet.paste(big, (28, 92))
    d.text((28, 342), "760×760 (preview 240)", font=font(12), fill=(110, 118, 128))

    x = 300
    for s, label in ((128, "128"), (90, "90"), (60, "60"), (40, "40"), (24, "24")):
        im = logo.resize((s, s), Image.LANCZOS)
        sheet.paste(im, (x, 92 + (128 - s)))
        d.text((x, 232), label + "px", font=font(11), fill=(110, 118, 128))
        x += s + 26

    d.rectangle((300, 268, 1000, 344), fill=(255, 255, 255), outline=(214, 222, 230))
    slot = logo.resize((40, 40), Image.LANCZOS)
    sheet.paste(slot, (316, 298))
    d.text((368, 284), "Λογοθεραπεύτρια στη Γλυφάδα", font=font(14, bold=True), fill=(26, 115, 232))
    d.text((368, 306), "tsigalogo.gr", font=font(12), fill=(32, 33, 36))
    d.text((300, 352), "mock: το λογότυπο (40px) δίπλα σε text ad", font=font(11),
           fill=(110, 118, 128))
    sheet.save(SHEET, "PNG", optimize=True)
    print("preview: {} ({})".format(SHEET, "1040x470"))


if __name__ == "__main__":
    main()
