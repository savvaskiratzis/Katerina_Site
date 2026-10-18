#!/usr/bin/env python3
"""Verify the invisible hit-area really sits ON the painted button in the pop-up image.

The button is part of the JPEG, so "the button works" means: the HTML overlay's own box,
measured in the rendered page, must match the button's pixel bounds inside the image
(41.30–58.74% × 55.34–59.73%, from tools/measure-cta.py).

This does not trust the CSS: it reads the live geometry, converts it to fractions of the
DISPLAYED image box, and compares. It also taps the centre of the hit-area through the real
event path (elementFromPoint) the way a finger would, then asserts the pop-up actually closed.

Run: ~/.venvs/fortinet/bin/python tools/check-cta-hitarea.py <url> [width]
"""
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://staging.tsigalogo-staging.pages.dev/"
WANT = (41.30, 55.34, 58.74, 59.73)          # x0, y0, x1, y1 in % of the image
CENTRE = (50.02, 57.535)
TOL_CENTRE = 1.2                              # percentage points
TOL_TIGHT = 1.2                               # only enforced where the 44px tap-minimum is inactive

JS = """() => {
  const img = document.querySelector('.welcome-img');
  const hit = document.querySelector('.welcome-enter');
  if (!img || !hit) return { error: 'image or hit-area missing' };
  const i = img.getBoundingClientRect(), h = hit.getBoundingClientRect();
  const pct = (v, base, off) => ((v - off) / base) * 100;
  return {
    img: { w: Math.round(i.width), h: Math.round(i.height), x: Math.round(i.x), y: Math.round(i.y) },
    hit: { w: Math.round(h.width), h: Math.round(h.height) },
    box: [pct(h.left, i.width, i.left), pct(h.top, i.height, i.y),
          pct(h.right, i.width, i.left), pct(h.bottom, i.height, i.y)].map(v => +v.toFixed(2)),
    // what is on top at the middle of the painted button?
    at_centre: (() => {
      const el = document.elementFromPoint(i.left + i.width * 0.5002, i.y + i.height * 0.57535);
      return el ? (el.className || el.tagName).toString() : null;
    })(),
    min_tap_ok: h.width >= 44 || h.height >= 44,
  };
}"""

TAP = """() => {
  const i = document.querySelector('.welcome-img').getBoundingClientRect();
  const el = document.elementFromPoint(i.left + i.width * 0.5002, i.y + i.height * 0.57535);
  if (el) el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
  return true;
}"""

fails = 0
with sync_playwright() as p:
    b = p.chromium.launch()
    for width in (1600, 1280, 900, 390):
        pg = b.new_page(viewport={"width": width, "height": 1000 if width > 899 else 844})
        pg.goto(URL, wait_until="networkidle")
        pg.wait_for_timeout(500)
        r = pg.evaluate(JS)
        if r.get("error"):
            print(f"  {width:5d}px  ✗ {r['error']}")
            fails += 1
            pg.close()
            continue
        box = r["box"]
        # Το σωστό κριτήριο σε κάθε μέγεθος:
        #   (α) το hit-area ΠΕΡΙΕΧΕΙ το ζωγραφισμένο κουμπί (αλλιώς μένουν νεκρά pixel του),
        #   (β) το ΚΕΝΤΡΟ του συμπίπτει με το κέντρο του κουμπιού,
        #   (γ) μόνο όπου ΔΕΝ ενεργοποιείται το ελάχιστο 44px (touch target) απαιτείται και ταύτιση
        #       των ορίων — σε μικρές οθόνες το 44px μεγαλώνει σκόπιμα το κουτί, κεντραρισμένα.
        contains = (box[0] <= WANT[0] + 0.1 and box[1] <= WANT[1] + 0.1
                    and box[2] >= WANT[2] - 0.1 and box[3] >= WANT[3] - 0.1)
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        dc = max(abs(cx - CENTRE[0]), abs(cy - CENTRE[1]))
        tight_needed = r["min_tap_ok"] and abs(box[3] - box[1] - (WANT[3] - WANT[1])) < 0.6
        if tight_needed:
            dt = max(abs(box[i] - WANT[i]) for i in range(4))
            ok = contains and dc <= TOL_CENTRE and dt <= TOL_TIGHT
            detail = f"Δορίων {dt:.2f}"
        else:
            ok = contains and dc <= TOL_CENTRE
            detail = f"κουτί {box[3]-box[1]:.1f}% ψηλό (min 44px ενεργό)"
        print(f"  {width:5d}px  hit-area {box[0]:6.2f}–{box[2]:6.2f}% × {box[1]:5.2f}–{box[3]:5.2f}%"
              f"   κέντρο {cx:5.2f}/{cy:5.2f} (θέλουμε {CENTRE[0]}/{CENTRE[1]}, Δ {dc:.2f})"
              f"   {detail}   {'✓' if ok else '✗'}")
        if not ok or "welcome-enter" not in (r["at_centre"] or ""):
            fails += 1
        # πραγματικό πάτημα στο κέντρο του ζωγραφισμένου κουμπιού
        pg.evaluate(TAP)
        pg.wait_for_timeout(700)
        closed = pg.evaluate("() => { const o = document.getElementById('welcomeOverlay'); return !o || o.hidden; }")
        print(f"          πάτημα στο κέντρο του ζωγραφισμένου κουμπιού → pop-up κλειστό: {closed}")
        if not closed:
            fails += 1
        pg.close()
    b.close()

print()
if fails:
    sys.exit(f"✗ {fails} αποτυχίες — το hit-area ΔΕΝ κάθεται σωστά πάνω στο ζωγραφισμένο κουμπί.")
print("✅ Το αόρατο hit-area πέφτει ακριβώς πάνω στο ζωγραφισμένο «Μάθετε περισσότερα» και το πάτημα μπαίνει στο site.")
