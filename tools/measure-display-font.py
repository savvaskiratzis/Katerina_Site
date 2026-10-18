#!/usr/bin/env python3
"""Measure Literata against fallbacks — v2, with a guard against the trap that fooled v1.

v1 returned identical numbers for Literata, Georgia, Times and serif: the font had NOT
loaded (page.set_content() runs on about:blank, whose base URL blocks file:// fetches), so
every measurement was the same fallback. It "looked like data" and was worthless. v2 writes
a real file:// page next to the fonts and asserts the webfont actually applied
(document.fonts.check + a width difference) before reporting anything.

Run: ~/.venvs/fortinet/bin/python tools/measure-display-font.py
"""
import os
from playwright.sync_api import sync_playwright

ROOT = os.path.expanduser("~/tsiga-speech-therapy-v2")
PAGE = os.path.join(ROOT, "_fontmetric.html")
SAMPLE = "Κατερίνα Τσίγα Λογοθεραπεύτρια"
SAMPLE_LATIN = "Katerina Tsiga Speech Therapist"

HTML = """<!doctype html><meta charset="utf-8"><title>m</title>
<style>
  @font-face{font-family:'Literata';src:url('fonts/literata-greek.woff2') format('woff2');
    font-weight:400 700;font-style:normal;font-display:block;}
  body{margin:0}
  .box{font-size:100px;line-height:normal;white-space:nowrap;display:inline-block;}
</style>
<body>
  <span class="box" id="lit"    style="font-family:'Literata'">%s</span>
  <span class="box" id="geo"    style="font-family:Georgia">%s</span>
  <span class="box" id="times"  style="font-family:'Times New Roman'">%s</span>
  <span class="box" id="litlat" style="font-family:'Literata'">%s</span>
  <span class="box" id="geolat" style="font-family:Georgia">%s</span>
</body>""" % (SAMPLE, SAMPLE, SAMPLE, SAMPLE_LATIN, SAMPLE_LATIN)

open(PAGE, "w", encoding="utf-8").write(HTML)

JS = """() => {
  const r = {};
  for (const id of ['lit','geo','times','litlat','geolat']) {
    const el = document.getElementById(id);
    r[id] = {w: el.getBoundingClientRect().width, h: el.getBoundingClientRect().height};
  }
  r.loadedGreek = document.fonts.check("100px Literata", "Κατερίνα");
  r.loadedLatin = document.fonts.check("100px Literata", "Katerina");
  return r;
}"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto("file://" + PAGE)
    pg.evaluate("() => document.fonts.ready")
    pg.wait_for_timeout(900)
    r = pg.evaluate(JS)
    b.close()

os.remove(PAGE)

for k, v in r.items():
    if isinstance(v, dict):
        print(f"  {k:8s} width {v['w']:8.2f}px  line-box height {v['h']:6.2f}px")
    else:
        print(f"  {k}: {v}")

# HARD GUARD: if the webfont did not apply, every number below is meaningless.
if not (r["loadedGreek"] and r["loadedLatin"]):
    raise SystemExit("✗ Το Literata ΔΕΝ φόρτωσε — τα νούμερα είναι άχρηστα (αυτό ακριβώς "
                     "συνέβη στην v1). Διορθώσε τη διαδρομή και ξανά.")

if abs(r["lit"]["w"] - r["geo"]["w"]) < 1:
    raise SystemExit("✗ Ίδιο πλάτος Literata/Georgia -> το font δεν εφαρμόστηκε.")

print("\n== υπολογισμένο metric-matched fallback (στοιχείο = Literata) ==")
for name, key in (("Georgia", "geo"), ("Times New Roman", "times")):
    greek = r["lit"]["w"] / r[key]["w"]
    latin = r["litlat"]["w"] / r["geolat"]["w"] if key == "geo" else None
    print(f"\n  {name}:")
    print(f"    size-adjust: {greek*100:.1f}%;   /* greek width ratio */")
    if latin:
        print(f"    (latin width ratio: {latin*100:.1f}%  — ΜΗΝ το χρησιμοποιήσεις: το "
              f"size-adjust είναι ένα ανά @font-face, άρα κρατάμε το greek, που είναι το "
              f"κείμενο του hero)")
    print(f"    ascent-override: {r['lit']['h']/r[key]['h']*100:.1f}%;")
    print(f"    descent-override: 0%;")
    print(f"    line-gap-override: 0%;")
