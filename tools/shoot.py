#!/usr/bin/env python3
"""Screenshot a live URL at desktop + phone sizes (and optionally the full page).

The owner works without me being able to "see" a build in another way, and a JSON
assertion cannot tell whether a redesign reads well. So: capture, then look.

Run: ~/.venvs/fortinet/bin/python tools/shoot.py <url> <outdir> [--full] [--lang en]
"""
import os
import sys
from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "https://staging.tsigalogo-staging.pages.dev/"
out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/shots"
full = "--full" in sys.argv
lang = "en" if "--lang" in sys.argv and "en" in sys.argv else "el"
os.makedirs(out, exist_ok=True)

SIZES = {
    "desktop-1600": (1600, 1000),
    "laptop-1280": (1280, 800),
    "tablet-900": (900, 1200),
    "phone-390": (390, 844),
}

# The cookie bar is a first-visit-only overlay and it covers the bottom of the hero, so shoot
# BOTH states: as a first-time visitor (with the welcome pop-up, if any) and as a returning one.
ACCEPT_JS = """() => {
  const b = Array.from(document.querySelectorAll('.ck-accept, .ck-btn'))
    .find(el => /Αποδοχή|Accept/.test(el.textContent));
  if (b) b.click();
  return !!b;
}"""

# close the welcome pop-up the way a visitor does (its own CTA), so the shots below the fold
# show the real site and not the modal
ENTER_JS = """() => {
  const o = document.getElementById('welcomeOverlay');
  if (!o || o.hidden) return false;
  const a = o.querySelector('.welcome-enter');
  if (a) a.click(); else o.click();
  return true;
}"""

with sync_playwright() as p:
    b = p.chromium.launch()
    for name, (w, h) in SIZES.items():
        for state, dismiss in (("welcome", False), ("site", True)):
            pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            pg.goto(url, wait_until="networkidle")
            pg.evaluate(f"() => {{ try {{ switchLang('{lang}') }} catch (e) {{}}; window.scrollTo(0, 0); }}")
            if dismiss:
                pg.wait_for_timeout(300)
                entered = pg.evaluate(ENTER_JS)
                if entered:
                    pg.wait_for_timeout(700)          # let the fade + scroll settle
                if not pg.evaluate(ACCEPT_JS):
                    print(f"    (no cookie bar to dismiss at {name})")
                pg.wait_for_timeout(400)
            pg.wait_for_timeout(300)
            suffix = "-en" if lang == "en" else ""
            path = os.path.join(out, f"{name}{suffix}-{state}.png")
            pg.screenshot(path=path, full_page=full)
            print(f"  {path}")
            pg.close()
    b.close()
print("ok")
