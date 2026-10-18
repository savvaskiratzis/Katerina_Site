#!/usr/bin/env python3
"""Diagnose the welcome layout in a real browser: computed sizes + boxes + which fonts
actually applied. Guessing from a screenshot is how you misdiagnose a 1.2px font as a
'ghost'. Run: ~/.venvs/fortinet/bin/python tools/inspect-welcome.py <url> [width]
"""
import json
import sys
from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "https://staging.tsigalogo-staging.pages.dev/"
width = int(sys.argv[2]) if len(sys.argv) > 2 else 1280

JS = """() => {
  const out = {};
  const box = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return 'MISSING';
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
             fs: cs.fontSize, ff: cs.fontFamily.split(',')[0], lh: cs.lineHeight,
             color: cs.color, bg: cs.backgroundColor, display: cs.display };
  };
  for (const s of ['.welcome-stage', '.welcome-art', '.welcome-card', '.w-badge',
                   '.welcome-card h1', '.welcome-card h1 .w-name', '.highlight',
                   '.w-divider', '.w-quote', '.w-lead', '.w-pills', '.w-cta', '.w-feats',
                   '.welcome-values', '.welcome-values li', '.welcome-values i',
                   '.welcome-note', '#cookieBar', '.cookie-inner'])
    out[s] = box(s);
  // what font actually rendered the name?
  out.fontsLoaded = {
    literata: document.fonts.check("600 40px Literata", "Κατερίνα"),
    literataLatin: document.fonts.check("600 40px Literata", "Katerina"),
    faGlyph: (() => {
      const i = document.querySelector('.welcome-values i');
      return i ? getComputedStyle(i, '::before').content + ' | ' + getComputedStyle(i).fontFamily : null;
    })(),
  };
  // the artwork's natural size and how it is cropped in the stage
  const img = document.querySelector('.welcome-art');
  if (img) out.art = { natural: img.naturalWidth + 'x' + img.naturalHeight,
                       rendered: Math.round(img.getBoundingClientRect().width) + 'x' +
                                 Math.round(img.getBoundingClientRect().height),
                       currentSrc: img.currentSrc, objectFit: getComputedStyle(img).objectFit,
                       objectPosition: getComputedStyle(img).objectPosition };
  out.scrollH = document.documentElement.scrollHeight;
  out.viewport = window.innerWidth + 'x' + window.innerHeight;
  // does the values row overlap the baked icon row region? print the stage fraction
  const stage = document.querySelector('.welcome-stage').getBoundingClientRect();
  for (const sel of ['.welcome-values', '.welcome-note']) {
    const el = document.querySelector(sel);
    if (!el) continue;
    const r = el.getBoundingClientRect();
    out[sel + '_fracTop'] = ((r.y - stage.y) / stage.height).toFixed(3);
  }
  return out;
}"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": width, "height": max(700, int(width * 0.7))})
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(600)
    print(json.dumps(pg.evaluate(JS), indent=1, ensure_ascii=False))
    b.close()
