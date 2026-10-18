#!/usr/bin/env python3
"""Self-host the display serif (Literata) and emit its @font-face block.

WHY Literata and not the obvious Playfair Display: **Playfair has no Greek subset**
(only latin/cyrillic/vietnamese), so it cannot render "Κατερίνα Τσίγα". Candidates were
probed via the Google CSS API and only the ones actually carrying `/* greek */` were kept:
Literata, EB Garamond, GFS Didot, Alegreya, Noto Serif, Gentium Book Plus, Vollkorn,
Source Serif 4. Literata won on screen-optimisation + real italics + variable weights.

Same self-hosting rules as the existing Mulish/Open Sans files: one woff2 per subset, the
browser downloads a file only when a rendered character falls inside its unicode-range.
Output: fonts/literata-*.woff2 + a ready @font-face block printed to stdout.
"""
import os
import re
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0 Safari/537.36")
API = ("https://fonts.googleapis.com/css2?family=Literata:ital,wght@0,400..700;1,400..700"
       "&display=swap")
ROOT = os.path.expanduser("~/tsiga-speech-therapy-v2/fonts")
WANT = {"greek", "greek-ext", "latin"}

req = urllib.request.Request(API, headers={"User-Agent": UA})
css = urllib.request.urlopen(req, timeout=60).read().decode()

blocks = re.findall(r"/\* ([a-z-]+) \*/\s*@font-face \{(.*?)\}", css, re.S)
out = []
total = 0
for subset, body in blocks:
    if subset not in WANT:
        continue
    style = "italic" if "font-style: italic" in body else "normal"
    url = re.search(r"url\((https://[^)]+\.woff2)\)", body).group(1)
    urange = re.search(r"unicode-range: ([^;]+);", body).group(1).strip()
    name = f"literata{'-italic' if style == 'italic' else ''}-{subset}.woff2"
    path = os.path.join(ROOT, name)
    data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                  timeout=60).read()
    open(path, "wb").write(data)
    total += len(data)
    print(f"  {name:34s} {len(data)//1024:4d} KB   unicode-range: {urange[:52]}…")
    out.append((style, name, urange))

print(f"\nσύνολο Literata: {total//1024} KB σε {len(out)} αρχεία\n")
print("/* ---- display serif: Literata (self-hosted, variable 400-700) ---- */")
for style, name, urange in sorted(out):
    print(f"""@font-face {{
  font-family: 'Literata';
  font-style: {style};
  font-weight: 400 700;
  font-display: swap;
  src: url('../fonts/{name}') format('woff2');
  unicode-range: {urange};
}}""")
